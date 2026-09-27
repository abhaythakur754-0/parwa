"""POST /remember — per-customer memory store. Phase 3, LIVE.

Decision (Abhay, 2026-09-25): memory lives in a DATABASE so the 4GB box
spends zero local disk on it. Supabase Postgres (free tier) is the target;
local SQLite stays the zero-config default so the box works out of the zip.

  SKILLS_MEM_STORE=sqlite     (default) → data/memory.db next to main.py
  SKILLS_MEM_STORE=postgres   SKILLS_MEM_DB_URL=postgresql://… (Supabase DSN)

Retrieval is full-text search (Postgres tsvector / SQLite FTS5) + a recency
boost. NO embedding model, NO vector RAM, NO text-generation LLM — matching
the box rule. Recall is sharpened for free by extracting keywords (order
ids, emails, phones, amounts, dates) at write time.

Actions (POST /remember, JSON body):
  add     {"user_id", "text", "meta?", "mask?"}        → {"id","keywords"}
  search  {"user_id", "query", "k?"}                   → {"results":[…]}
  list    {"user_id", "limit?"}                        → {"results":[…]}
  delete  {"user_id", "memory_id?" | "all"?: true}     → {"deleted": n}
  count   {"user_id"}                                  → {"count": n}

Failures raise ValueError (→ 400, bad input) or RuntimeError (→ 500,
store unreachable); the box itself never crashes on a bad DSN because
connections are per-request.
"""
from __future__ import annotations

import json
import math
import os
import re
import sqlite3
import threading
import time
import uuid
from typing import Any, Dict, List, Optional

from core import config

ACTIONS = ("add", "search", "list", "delete", "count")

# ── keyword extraction (zero deps, regex floor spirit) ──────────────
_KW_PATTERNS = [
    re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.-]+\b"),                              # email
    re.compile(r"\b(?:order|ticket|ref|invoice|tracking|txn)?[\s#:.-]*\d{4,}\b", re.I),  # ids
    re.compile(r"(?<![\w.])\$\s?\d+(?:[.,]\d{1,2})?|\b\d+(?:[.,]\d{1,2})?\s?(?:usd|eur|inr|rs\.?|€|£)\b|\b₹\s?\d+\b", re.I),  # money
    re.compile(r"\b\d{4}-\d{2}-\d{2}\b|\b\d{1,2}[/.]\d{1,2}[/.]\d{2,4}\b"),   # dates
    re.compile(r"\b\+?\d[\d\s().-]{7,}\d\b"),                                 # phone-ish
]


def _extract_keywords(text: str) -> List[str]:
    found: List[str] = []
    for pattern in _KW_PATTERNS:
        for match in pattern.findall(text or ""):
            token = match.strip() if isinstance(match, str) else match[0].strip()
            if token and token not in found:
                found.append(token)
    return found[:24]  # keep rows lean


def _score(rows: List[Dict[str, Any]], k: int) -> List[Dict[str, Any]]:
    """Rank fetched candidates: relevance position (0.8) + recency (0.2).

    Rows arrive already ordered best-first by the backend (bm25 / ts_rank_cd),
    so position scoring keeps the ordering stable and monotonic without
    needing to normalize bm25 across queries.
    """
    now = time.time()
    n = len(rows)
    out: List[Dict[str, Any]] = []
    for i, row in enumerate(rows):
        rel = 1.0 if n <= 1 else 1.0 - 0.5 * (i / (n - 1))
        age_days = max(0.0, (now - float(row["created_at"])) / 86400.0)
        recency = math.exp(-age_days / 30.0)
        out.append({
            "id": row["id"],
            "text": row["text"],
            "meta": row.get("meta") or {},
            "created_at": int(float(row["created_at"])),
            "score": round(rel * 0.8 + recency * 0.2, 3),
        })
    out.sort(key=lambda r: r["score"], reverse=True)
    return out[:k]


def _norm_meta(raw: Any) -> Dict[str, Any]:
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, (bytes, str)):
        try:
            parsed = json.loads(raw)
            return parsed if isinstance(parsed, dict) else {"value": parsed}
        except Exception:  # noqa: BLE001
            return {}
    return {}


# ═══════════════════════════ SQLite backend ══════════════════════════
class _SQLiteStore:
    name = "sqlite"

    def __init__(self, path: str) -> None:
        self.path = path
        parent = os.path.dirname(path)
        if parent:
            os.makedirs(parent, exist_ok=True)
        self.fts = self._init_schema()

    def _conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path, timeout=10)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout=5000")
        conn.execute("PRAGMA foreign_keys=ON")
        return conn

    def _init_schema(self) -> bool:
        with self._conn() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS memories (
                    id         TEXT PRIMARY KEY,
                    user_id    TEXT NOT NULL,
                    text       TEXT NOT NULL,
                    keywords   TEXT NOT NULL DEFAULT '',
                    meta       TEXT NOT NULL DEFAULT '{}',
                    created_at REAL NOT NULL
                );
                CREATE INDEX IF NOT EXISTS ix_mem_user
                    ON memories(user_id, created_at DESC);
                """
            )
            try:
                conn.executescript(
                    """
                    CREATE VIRTUAL TABLE IF NOT EXISTS memories_fts USING fts5(
                        text, keywords, user_id UNINDEXED,
                        content='memories', content_rowid='rowid',
                        tokenize='porter unicode61'
                    );
                    CREATE TRIGGER IF NOT EXISTS mem_fts_ai AFTER INSERT ON memories BEGIN
                        INSERT INTO memories_fts(rowid, text, keywords, user_id)
                        VALUES (new.rowid, new.text, new.keywords, new.user_id);
                    END;
                    CREATE TRIGGER IF NOT EXISTS mem_fts_ad AFTER DELETE ON memories BEGIN
                        INSERT INTO memories_fts(memories_fts, rowid, text, keywords, user_id)
                        VALUES ('delete', old.rowid, old.text, old.keywords, old.user_id);
                    END;
                    """
                )
                # smoke-test that MATCH actually works on this build
                conn.execute(
                    "SELECT rowid FROM memories_fts WHERE memories_fts MATCH 'x' LIMIT 1"
                ).fetchone()
                return True
            except sqlite3.OperationalError:
                conn.rollback()
                return False  # FTS5 missing → LIKE fallback below

    # ── write ────────────────────────────────────────────────────────
    def add(self, user_id: str, text: str, keywords: str, meta: str) -> str:
        mem_id = uuid.uuid4().hex
        with self._conn() as conn:
            conn.execute(
                "INSERT INTO memories (id, user_id, text, keywords, meta, created_at)"
                " VALUES (?, ?, ?, ?, ?, ?)",
                (mem_id, user_id, text, keywords, meta, time.time()),
            )
        return mem_id

    def _prune(self, user_id: str) -> int:
        cap = config.MEM_MAX_PER_USER
        with self._conn() as conn:
            row = conn.execute(
                "SELECT COUNT(*) FROM memories WHERE user_id = ?", (user_id,)
            ).fetchone()
            extra = int(row[0]) - cap
            if extra <= 0:
                return 0
            conn.execute(
                "DELETE FROM memories WHERE id IN ("
                "  SELECT id FROM memories WHERE user_id = ?"
                "  ORDER BY created_at ASC LIMIT ?)",
                (user_id, extra),
            )
        return extra

    # ── read ─────────────────────────────────────────────────────────
    def search(self, user_id: str, fts_query: str, tokens: List[str]) -> List[Dict[str, Any]]:
        with self._conn() as conn:
            if self.fts and fts_query:
                rows = conn.execute(
                    "SELECT m.id, m.text, m.meta, m.created_at FROM memories_fts f"
                    " JOIN memories m ON m.rowid = f.rowid"
                    " WHERE memories_fts MATCH ? AND m.user_id = ?"
                    " ORDER BY bm25(memories_fts) LIMIT 30",
                    (fts_query, user_id),
                ).fetchall()
            else:
                where = " OR ".join(["text LIKE ?"] * len(tokens)) if tokens else "0"
                params = [f"%{t}%" for t in tokens] + [user_id]
                rows = conn.execute(
                    f"SELECT id, text, meta, created_at FROM memories"
                    f" WHERE ({where}) AND user_id = ?"
                    f" ORDER BY created_at DESC LIMIT 30",
                    params,
                ).fetchall()
        return [
            {"id": r[0], "text": r[1], "meta": _norm_meta(r[2]), "created_at": r[3]}
            for r in rows
        ]

    def list(self, user_id: str, limit: int) -> List[Dict[str, Any]]:
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT id, text, meta, created_at FROM memories"
                " WHERE user_id = ? ORDER BY created_at DESC LIMIT ?",
                (user_id, limit),
            ).fetchall()
        return [
            {"id": r[0], "text": r[1], "meta": _norm_meta(r[2]), "created_at": r[3]}
            for r in rows
        ]

    def count(self, user_id: str) -> int:
        with self._conn() as conn:
            row = conn.execute(
                "SELECT COUNT(*) FROM memories WHERE user_id = ?", (user_id,)
            ).fetchone()
        return int(row[0])

    def delete(self, user_id: str, memory_id: Optional[str]) -> int:
        with self._conn() as conn:
            if memory_id:
                cur = conn.execute(
                    "DELETE FROM memories WHERE id = ? AND user_id = ?",
                    (memory_id, user_id),
                )
            else:
                cur = conn.execute("DELETE FROM memories WHERE user_id = ?", (user_id,))
            return cur.rowcount if cur.rowcount and cur.rowcount > 0 else 0


# ═══════════════════════════ Postgres backend ════════════════════════
class _PostgresStore:
    """Supabase Postgres (free tier) via psycopg — data lives in the cloud.

    Needs `psycopg[binary]` (in requirements.txt) and a DSN in
    SKILLS_MEM_DB_URL. `sslmode=require` is appended automatically
    (Supabase refuses plaintext). Use the Session-pooler host (port 5432)
    from the Supabase dashboard on home boxes without IPv4.
    """

    name = "postgres"

    def __init__(self, dsn: str) -> None:
        if not dsn:
            raise RuntimeError(
                "SKILLS_MEM_STORE=postgres but SKILLS_MEM_DB_URL is empty — "
                "paste the Supabase connection string"
            )
        if "sslmode=" not in dsn:
            dsn += ("&" if "?" in dsn else "?") + "sslmode=require"
        self.dsn = dsn
        self._schema_ready = False
        self._schema_lock = threading.Lock()

    def _conn(self):
        try:
            import psycopg  # lazy: sqlite users never pay for this import
        except ImportError as exc:  # pragma: no cover
            raise RuntimeError(
                "psycopg is not installed — run: pip install 'psycopg[binary]'"
            ) from exc
        return psycopg.connect(self.dsn, connect_timeout=8)

    def _init_schema(self) -> None:
        if self._schema_ready:
            return
        with self._schema_lock:
            if self._schema_ready:
                return
            with self._conn() as conn, conn.cursor() as cur:
                cur.execute(
                    """
                    CREATE TABLE IF NOT EXISTS memories (
                        id         TEXT PRIMARY KEY,
                        user_id    TEXT NOT NULL,
                        text       TEXT NOT NULL,
                        keywords   TEXT NOT NULL DEFAULT '',
                        meta       JSONB NOT NULL DEFAULT '{}'::jsonb,
                        created_at TIMESTAMPTZ NOT NULL DEFAULT now()
                    )
                    """
                )
                cur.execute(
                    "CREATE INDEX IF NOT EXISTS ix_mem_user"
                    " ON memories (user_id, created_at DESC)"
                )
                cur.execute(
                    "CREATE INDEX IF NOT EXISTS ix_mem_fts ON memories USING GIN"
                    " (to_tsvector('english', text || ' ' || keywords))"
                )
            self._schema_ready = True

    # ── write ────────────────────────────────────────────────────────
    def add(self, user_id: str, text: str, keywords: str, meta: str) -> str:
        self._init_schema()
        mem_id = uuid.uuid4().hex
        with self._conn() as conn, conn.cursor() as cur:
            cur.execute(
                "INSERT INTO memories (id, user_id, text, keywords, meta)"
                " VALUES (%s, %s, %s, %s, %s::jsonb)",
                (mem_id, user_id, text, keywords, meta),
            )
        return mem_id

    def _prune(self, user_id: str) -> int:
        cap = config.MEM_MAX_PER_USER
        with self._conn() as conn, conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM memories WHERE user_id = %s", (user_id,))
            extra = int(cur.fetchone()[0]) - cap
            if extra <= 0:
                return 0
            cur.execute(
                "DELETE FROM memories WHERE id IN ("
                "  SELECT id FROM memories WHERE user_id = %s"
                "  ORDER BY created_at ASC LIMIT %s)",
                (user_id, extra),
            )
            return extra

    # ── read ─────────────────────────────────────────────────────────
    def search(self, user_id: str, fts_query: str, tokens: List[str]) -> List[Dict[str, Any]]:
        self._init_schema()
        tsq = fts_query.strip() if fts_query else ""
        with self._conn() as conn, conn.cursor() as cur:
            if tsq:
                cur.execute(
                    "SELECT id, text, meta, EXTRACT(EPOCH FROM created_at)"
                    " FROM memories WHERE user_id = %s AND"
                    " to_tsvector('english', text || ' ' || keywords)"
                    " @@ websearch_to_tsquery('english', %s)"
                    " ORDER BY ts_rank_cd("
                    "   to_tsvector('english', text || ' ' || keywords),"
                    "   websearch_to_tsquery('english', %s)) DESC"
                    " LIMIT 30",
                    (user_id, tsq, tsq),
                )
            else:
                # fallback: recency only (query was stopwords-only)
                cur.execute(
                    "SELECT id, text, meta, EXTRACT(EPOCH FROM created_at)"
                    " FROM memories WHERE user_id = %s"
                    " ORDER BY created_at DESC LIMIT 30",
                    (user_id,),
                )
            rows = cur.fetchall()
        return [
            {"id": r[0], "text": r[1], "meta": _norm_meta(r[2]), "created_at": float(r[3])}
            for r in rows
        ]

    def list(self, user_id: str, limit: int) -> List[Dict[str, Any]]:
        self._init_schema()
        with self._conn() as conn, conn.cursor() as cur:
            cur.execute(
                "SELECT id, text, meta, EXTRACT(EPOCH FROM created_at)"
                " FROM memories WHERE user_id = %s"
                " ORDER BY created_at DESC LIMIT %s",
                (user_id, limit),
            )
            rows = cur.fetchall()
        return [
            {"id": r[0], "text": r[1], "meta": _norm_meta(r[2]), "created_at": float(r[3])}
            for r in rows
        ]

    def count(self, user_id: str) -> int:
        self._init_schema()
        with self._conn() as conn, conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM memories WHERE user_id = %s", (user_id,))
            return int(cur.fetchone()[0])

    def delete(self, user_id: str, memory_id: Optional[str]) -> int:
        self._init_schema()
        with self._conn() as conn, conn.cursor() as cur:
            if memory_id:
                cur.execute(
                    "DELETE FROM memories WHERE id = %s AND user_id = %s",
                    (memory_id, user_id),
                )
            else:
                cur.execute("DELETE FROM memories WHERE user_id = %s", (user_id,))
            return cur.rowcount or 0


# ═══════════════════════════ public surface ══════════════════════════
_store: Optional[Any] = None
_store_lock = threading.Lock()


def _get_store() -> Any:
    global _store
    with _store_lock:
        if _store is None:
            if config.MEM_STORE == "postgres":
                _store = _PostgresStore(config.MEM_DB_URL)
            else:
                _store = _SQLiteStore(config.MEM_DB_PATH)
        return _store


def _fts_query(query: str) -> tuple:
    """Sanitize free text → (fts_query, tokens).

    SQLite: quoted tokens joined with OR (implicit AND is too strict for
    recall). Postgres: raw text through websearch_to_tsquery (never throws).
    """
    tokens = re.findall(r"\w+", (query or "").lower())[:12]
    sqlite_q = " OR ".join(f'"{t}"' for t in tokens)
    return " ".join(tokens), sqlite_q, tokens


def handle(
    action: str,
    user_id: str,
    text: Optional[str] = None,
    query: Optional[str] = None,
    meta: Optional[dict] = None,
    k: int = 5,
    mask: bool = False,
    memory_id: Optional[str] = None,
    all_items: bool = False,
    limit: int = 50,
) -> Dict[str, Any]:
    if action not in ACTIONS:
        raise ValueError(f"unknown action '{action}' — use one of {', '.join(ACTIONS)}")
    if not user_id or not str(user_id).strip():
        raise ValueError("user_id is required (e.g. 'customer:123' or 'email:x@y.z')")
    user_id = str(user_id).strip()
    store = _get_store()

    if action == "add":
        if not text or not str(text).strip():
            raise ValueError("add needs non-empty 'text'")
        text = str(text).strip()
        if len(text) > config.MAX_TEXT_CHARS:
            raise ValueError(f"text too long ({len(text)} > {config.MAX_TEXT_CHARS} chars)")
        if mask:
            from skills.regex_floor import redact

            text, _found = redact(text)
        keywords = ", ".join(_extract_keywords(text))
        mem_id = store.add(user_id, text, keywords, json.dumps(meta or {}))
        pruned = store._prune(user_id)
        return {
            "id": mem_id,
            "keywords": keywords,
            "pruned": pruned,
            "store": store.name,
        }

    if action == "search":
        if not query or not str(query).strip():
            raise ValueError("search needs non-empty 'query'")
        pg_q, sqlite_q, tokens = _fts_query(str(query))
        rows = store.search(user_id, pg_q if store.name == "postgres" else sqlite_q, tokens)
        return {"query": query, "results": _score(rows, max(1, min(int(k), 20))),
                "store": store.name}

    if action == "list":
        rows = store.list(user_id, max(1, min(int(limit), 200)))
        return {"results": [
            {"id": r["id"], "text": r["text"], "meta": r["meta"],
             "created_at": int(float(r["created_at"]))} for r in rows
        ], "store": store.name}

    if action == "delete":
        if not memory_id and not all_items:
            raise ValueError("delete needs 'memory_id' or \"all\": true (wipes the user)")
        deleted = store.delete(user_id, memory_id)
        return {"deleted": max(deleted, 0), "store": store.name}

    # count
    return {"count": store.count(user_id), "store": store.name}


def status() -> Dict[str, Any]:
    """Cheap info for /health — never touches the database."""
    info: Dict[str, Any] = {
        "backend": config.MEM_STORE,
        "max_per_user": config.MEM_MAX_PER_USER,
    }
    if config.MEM_STORE == "postgres":
        info["db_url_set"] = bool(config.MEM_DB_URL)
    else:
        info["path"] = config.MEM_DB_PATH
    return info
