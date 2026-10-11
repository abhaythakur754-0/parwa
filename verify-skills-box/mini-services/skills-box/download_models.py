"""Pre-download every model the box uses. Idempotent — skips what exists.

Run by start.sh; safe to re-run. Each step fails soft (logged, next step
continues) so a flaky mirror can't take the whole box down.
"""
from __future__ import annotations

import os
import subprocess
import sys
import tempfile

from core import config

OK, FAIL = "OK  ", "FAIL"


def step(name: str, fn):
    try:
        fn()
        print(f"[{OK}] {name}", flush=True)
        return True
    except Exception as exc:  # noqa: BLE001
        print(f"[{FAIL}] {name}: {type(exc).__name__}: {exc}", flush=True)
        return False


def hf_snapshot(repo_id: str):
    from huggingface_hub import snapshot_download

    # *.safetensors only — skips duplicate pytorch_model.bin / onnx copies
    # (saves ~2GB per model on the box)
    snapshot_download(
        repo_id=repo_id,
        allow_patterns=["*.json", "*.safetensors", "*.model", "*.txt", "*.md"],
    )
    print(f"       → {repo_id} cached", flush=True)


def dl_gliclass():
    hf_snapshot(config.GLICLASS_MODEL)


def dl_gliner():
    hf_snapshot(config.GLINER_MODEL)


def dl_whisper():
    from faster_whisper import WhisperModel

    WhisperModel(config.WHISPER_MODEL, device="cpu", compute_type=config.WHISPER_COMPUTE)
    print(f"       → faster-whisper '{config.WHISPER_MODEL}' ({config.WHISPER_COMPUTE}) cached", flush=True)


def dl_paddle():
    import numpy as np

    from skills import ocr as sk_ocr

    engine = sk_ocr._load()  # downloads det/rec/cls models
    # tiny synthetic image so paddle writes its inference cache
    import cv2

    img = np.full((80, 300, 3), 255, dtype=np.uint8)
    cv2.putText(img, "ORDER 12345 TOTAL $99.00", (10, 50),
                cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 0, 0), 2, cv2.LINE_AA)
    if hasattr(engine, "predict"):
        list(engine.predict(img))
    else:
        engine.ocr(img, cls=True)
    print("       → paddleocr models cached + smoke inference done", flush=True)


def dl_argos():
    import argostranslate.package
    import argostranslate.translate

    argostranslate.package.update_package_index()
    have = {(p.from_code, p.to_code) for p in argostranslate.package.get_installed_packages()}
    available = argostranslate.package.get_available_packages()
    for pair in config.ARGOS_PAIRS.split(","):
        src, dst = pair.strip().split("-")
        for a, b in ((src, dst), (dst, src)):  # install BOTH directions (en↔de)
            if (a, b) in have or a == b:
                continue
            matches = [x for x in available if x.from_code == a and x.to_code == b]
            if not matches:
                print(f"       → no index entry for {a}->{b}", flush=True)
                continue
            argostranslate.package.install_from_path(matches[0].download())
            print(f"       → installed {a}->{b}", flush=True)
    # warmup triggers any lazy sentence-splitter download
    argostranslate.translate.translate("hello world", "en", "es")
    print("       → argos warmup done", flush=True)


def dl_spacy():
    r = subprocess.run([sys.executable, "-m", "spacy", "download", "en_core_web_sm"],
                       capture_output=True, text=True, timeout=600)
    if r.returncode != 0:
        raise RuntimeError((r.stderr or r.stdout)[-300:])
    print("       → en_core_web_sm installed", flush=True)


def dl_piper():
    import requests

    MODELS_DIR = config.BASE_DIR / "models" / "piper"
    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    name = "en_US-lessac-medium.onnx"
    onnx = MODELS_DIR / name
    if not onnx.is_file():
        url = ("https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0/"
               "en/en_US/lessac/medium/" + name)
        res = requests.get(url, timeout=300)
        res.raise_for_status()
        onnx.write_bytes(res.content)
    cfg = MODELS_DIR / (name + ".json")
    if not cfg.is_file():
        url2 = url + ".json"
        res2 = requests.get(url2, timeout=120)
        res2.raise_for_status()
        cfg.write_bytes(res2.content)
    print(f"       → piper voice cached at {onnx}", flush=True)


def dl_piper_bin():
    """Piper binary (self-contained) — primary /speak engine."""
    import requests
    import tarfile

    bin_dir = config.BASE_DIR / "bin"
    target = bin_dir / "piper" / "piper"
    if target.is_file():
        print("       → piper binary already present", flush=True)
        return
    bin_dir.mkdir(parents=True, exist_ok=True)
    url = "https://github.com/rhasspy/piper/releases/download/2023.11.14-2/piper_linux_x86_64.tar.gz"
    print("       → downloading piper binary...", flush=True)
    with tempfile.NamedTemporaryFile(suffix=".tar.gz", delete=False) as tmp:
        with requests.get(url, stream=True, timeout=300) as r:
            r.raise_for_status()
            for chunk in r.iter_content(chunk_size=1 << 20):
                tmp.write(chunk)
        tmp_path = tmp.name
    try:
        with tarfile.open(tmp_path) as tf:
            tf.extractall(bin_dir)  # noqa: S202 — fixed upstream tarball
    finally:
        os.unlink(tmp_path)
    target.chmod(0o755)
    print(f"       → piper binary at {target}", flush=True)


def main() -> int:
    print(f"skills-box model pre-download — ram_limit={config.RAM_LIMIT_MB}MB", flush=True)
    results = {
        "spacy+presidio": step("spacy en_core_web_sm (mask engine)", dl_spacy),
        "gliclass": step(f"gliclass {config.GLICLASS_MODEL}", dl_gliclass),
        "gliner": step(f"gliner {config.GLINER_MODEL}", dl_gliner),
        "whisper": step(f"whisper {config.WHISPER_MODEL}/{config.WHISPER_COMPUTE}", dl_whisper),
        "paddle": step("paddleocr det+rec models", dl_paddle),
        "argos": step(f"argos pairs [{config.ARGOS_PAIRS}]", dl_argos),
        "piper_bin": step("piper binary", dl_piper_bin),
        "piper_voice": step("piper voice (lessac-medium)", dl_piper),
    }
    failed = [k for k, v in results.items() if not v]
    print("\nSummary: " + ", ".join(f"{k}={'ok' if v else 'FAIL'}" for k, v in results.items()), flush=True)
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
