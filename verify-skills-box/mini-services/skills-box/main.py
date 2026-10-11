"""Parwa Skills Box — ONE FastAPI service, ONE port (8055), ONE key.

9 abilities as HTTP endpoints; small local models do the work, never a
text-generation LLM. Parwa's 512MB Render backend calls this box the same
way it calls SuperGlue: one URL env var + one key.

  POST /classify    GLiClass zero-shot intent      (Phase 1)
  POST /entities    GLiNER entities                (Phase 1)
  POST /mask        Presidio + regex floor         (Phase 1)
  POST /ocr         PaddleOCR                      (Phase 2)
  POST /transcribe  faster-whisper base int8       (Phase 2)
  POST /translate   Argos Translate                (Phase 3)
  POST /speak       Piper TTS                      (Phase 3)
  POST /remember    customer memory (SQLite/Supabase) (Phase 3)
  POST /browse      browser-use — 501 until LLM    (Phase 3)
  GET  /health      liveness + models + live RAM   (no auth)
  POST /warm        pre-load skills after boot     (auth)

Auth: header  X-Skills-Key: <SKILLS_BOX_KEY>  on everything except /health.
Every response: {"ok": true, "data": {...}, "ms": <latency>}
Errors:         4xx/5xx {"ok": false, "error": "..."}
"""
from __future__ import annotations

import hmac
import logging
import os
import threading
import time
from typing import List, Optional

from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from core import config
from core.envelope import ms_since, ok
from core.registry import registry
from core.timeout import TimeoutError as InferTimeout
from core.timeout import run_with_timeout

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
log = logging.getLogger("skills.main")

# skills register themselves into the registry at import time
from skills import browse as sk_browse          # noqa: E402,F401
from skills import classify as sk_classify      # noqa: E402
from skills import entities as sk_entities      # noqa: E402
from skills import mask as sk_mask              # noqa: E402
from skills import ocr as sk_ocr                # noqa: E402
from skills import remember as sk_remember      # noqa: E402,F401
from skills import speak as sk_speak            # noqa: E402
from skills import transcribe as sk_transcribe  # noqa: E402
from skills import translate as sk_translate    # noqa: E402

# CPU budget: small box, keep torch polite
try:
    import torch

    torch.set_num_threads(max(1, config.TORCH_THREADS))
    log.info("torch threads set to %d", config.TORCH_THREADS)
except Exception:  # noqa: BLE001
    pass

VERSION = "1.0.0"

app = FastAPI(
    title="Parwa Skills Box",
    version=VERSION,
    docs_url=None,
    redoc_url=None,
    openapi_url=None,
)


# ── auth: ONE key on ALL endpoints except /health ─────────────────
def require_key(
    x_skills_key: Optional[str] = Header(default=None, alias="X-Skills-Key"),
) -> None:
    if not x_skills_key or not hmac.compare_digest(
        x_skills_key.encode("utf-8"), config.SKILLS_KEY.encode("utf-8")
    ):
        raise HTTPException(status_code=401, detail="invalid or missing X-Skills-Key")


# ── error format: {"ok": false, "error": "..."} ───────────────────
@app.exception_handler(HTTPException)
async def _http_err(request: Request, exc: HTTPException):
    return JSONResponse(status_code=exc.status_code,
                        content={"ok": False, "error": str(exc.detail)})


@app.exception_handler(RequestValidationError)
async def _validation_err(request: Request, exc: RequestValidationError):
    return JSONResponse(status_code=422,
                        content={"ok": False, "error": f"bad input: {exc.errors()[:3]}"})


@app.exception_handler(ValueError)
async def _value_err(request: Request, exc: ValueError):
    return JSONResponse(status_code=400, content={"ok": False, "error": str(exc)})


@app.exception_handler(InferTimeout)
async def _timeout_err(request: Request, exc: InferTimeout):
    return JSONResponse(status_code=504, content={"ok": False, "error": str(exc)})


@app.exception_handler(Exception)
async def _gen_err(request: Request, exc: Exception):
    log.exception("unhandled error on %s", request.url.path)
    return JSONResponse(status_code=500,
                        content={"ok": False, "error": f"{type(exc).__name__}: {exc}"})


# ── request bodies ────────────────────────────────────────────────
class ClassifyIn(BaseModel):
    text: str
    labels: List[str]
    multilabel: bool = False
    threshold: float = 0.0


class EntitiesIn(BaseModel):
    text: str
    labels: Optional[List[str]] = None
    threshold: float = 0.4


class MaskIn(BaseModel):
    text: str
    entities: Optional[List[str]] = None


class OcrIn(BaseModel):
    image_base64: Optional[str] = None
    image_url: Optional[str] = None
    lang: str = "en"


class TranscribeIn(BaseModel):
    audio_base64: str
    fmt: str = "webm"
    language: Optional[str] = None
    timeout_s: int = config.TRANSCRIBE_TIMEOUT_S


class TranslateIn(BaseModel):
    text: str
    target: str
    source: str = "en"


class SpeakIn(BaseModel):
    text: str
    voice: Optional[str] = None


class RememberIn(BaseModel):
    action: str = "add"          # add | search | list | delete | count
    user_id: str
    text: Optional[str] = None
    query: Optional[str] = None
    meta: Optional[dict] = None
    k: int = 5                   # search: max hits
    mask: bool = False           # add: redact emails/cards/SSN before storing
    memory_id: Optional[str] = None  # delete: one memory
    all: bool = False            # delete: wipe the user (needs explicit true)
    limit: int = 50              # list


class BrowseIn(BaseModel):
    url: str
    task: str
    actions: Optional[List[dict]] = None


class WarmIn(BaseModel):
    skills: List[str]


# ── /health (no auth) ─────────────────────────────────────────────
@app.get("/health")
def health():
    t0 = time.time()
    rss = registry.rss_mb()
    data = {
        "service": "parwa-skills-box",
        "version": VERSION,
        "uptime_s": int(time.time() - registry.started_at),
        "ram": {
            "rss_mb": round(rss, 1),
            "limit_mb": config.RAM_LIMIT_MB,
            "over_limit": rss > config.RAM_LIMIT_MB,
        },
        "models": registry.snapshot(),
        "auth": {"header": "X-Skills-Key", "required": True},
        "memory": sk_remember.status(),
        "phases": {
            "1": ["classify", "entities", "mask"],
            "2": ["ocr", "transcribe"],
            "3": ["translate", "speak", "remember", "browse(pending)"],
        },
    }
    return ok(data, t0)


# ── /warm (auth) — pre-load models after boot so first ticket is fast ──
@app.post("/warm")
def warm(body: WarmIn, _: None = Depends(require_key)):
    t0 = time.time()
    results = {}
    for name in body.skills:
        if name not in registry.names():
            results[name] = {"loaded": False, "error": "unknown skill"}
            continue
        try:
            registry.get(name)
            results[name] = {"loaded": True, "error": None}
        except Exception as exc:  # noqa: BLE001
            results[name] = {"loaded": False, "error": str(exc)[:200]}
    return ok({"skills": results}, t0)


def _warmup_thread() -> None:
    if config.WARMUP == "none":
        return
    targets = config.PHASE1_SKILLS + (config.PHASE2_SKILLS if config.WARMUP == "all" else [])
    for name in targets:
        try:
            registry.get(name)
            log.info("warmup loaded %s", name)
        except Exception:  # noqa: BLE001
            log.exception("warmup failed for %s", name)


@app.on_event("startup")
def _startup() -> None:
    log.info("skills box v%s up — port %s, ram_limit=%dMB, key file=%s",
             VERSION, os.environ.get("SKILLS_PORT", "8055"),
             config.RAM_LIMIT_MB, config.KEY_FILE)
    threading.Thread(target=_warmup_thread, name="warmup", daemon=True).start()


# ── Phase 1 ───────────────────────────────────────────────────────
@app.post("/classify")
def ep_classify(body: ClassifyIn, _: None = Depends(require_key)):
    t0 = time.time()
    return ok(sk_classify.classify(body.text, body.labels,
                                   body.multilabel, body.threshold), t0)


@app.post("/entities")
def ep_entities(body: EntitiesIn, _: None = Depends(require_key)):
    t0 = time.time()
    return ok(sk_entities.extract(body.text, body.labels, body.threshold), t0)


@app.post("/mask")
def ep_mask(body: MaskIn, _: None = Depends(require_key)):
    t0 = time.time()
    return ok(sk_mask.mask(body.text, body.entities), t0)


# ── Phase 2 ───────────────────────────────────────────────────────
@app.post("/ocr")
def ep_ocr(body: OcrIn, _: None = Depends(require_key)):
    t0 = time.time()
    return ok(sk_ocr.ocr(body.image_base64 or "", body.image_url or "", body.lang), t0)


@app.post("/transcribe")
def ep_transcribe(body: TranscribeIn, _: None = Depends(require_key)):
    t0 = time.time()
    model = sk_transcribe.ensure()  # load untimed
    result = run_with_timeout(
        sk_transcribe.infer, model, body.audio_base64, body.fmt,
        body.language, timeout_s=float(body.timeout_s),
    )
    return ok(result, t0)


# ── Phase 3 ───────────────────────────────────────────────────────
@app.post("/translate")
def ep_translate(body: TranslateIn, _: None = Depends(require_key)):
    t0 = time.time()
    return ok(sk_translate.translate(body.text, body.target, body.source), t0)


@app.post("/speak")
def ep_speak(body: SpeakIn, _: None = Depends(require_key)):
    t0 = time.time()
    return ok(sk_speak.speak(body.text, body.voice), t0)


@app.post("/remember")
def ep_remember(body: RememberIn, _: None = Depends(require_key)):
    t0 = time.time()
    return ok(sk_remember.handle(
        action=body.action,
        user_id=body.user_id,
        text=body.text,
        query=body.query,
        meta=body.meta,
        k=body.k,
        mask=body.mask,
        memory_id=body.memory_id,
        all_items=body.all,
        limit=body.limit,
    ), t0)


@app.post("/browse")
def ep_browse(body: BrowseIn, _: None = Depends(require_key)):
    raise HTTPException(status_code=501, detail=sk_browse.NOT_ENABLED)
