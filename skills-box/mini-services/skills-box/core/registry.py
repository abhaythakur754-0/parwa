"""Model registry — the RAM heart of the box.

Guarantees:
  * LAZY LOAD    — models load on first request only.
  * ONE-AT-A-TIME — a single heavy lock serializes model loads/unloads,
                    so two heavy models never load at the same moment.
  * RAM GUARD    — if total process RSS crosses SKILLS_RAM_LIMIT_MB (~3.2GB),
                    the least-recently-used loaded model is auto-unloaded.
                    It transparently reloads on the next request.
  * /health      — snapshot() reports live per-model RAM + last-used age.
"""
from __future__ import annotations

import gc
import logging
import os
import threading
import time
from collections import OrderedDict
from typing import Any, Callable, Dict, List, Optional

import psutil

from . import config

log = logging.getLogger("skills.registry")


class ModelHandle:
    __slots__ = ("name", "load_fn", "unload_fn", "obj", "last_used", "ram_mb",
                 "load_ms", "loads", "unloads", "last_error")

    def __init__(self, name: str, load_fn: Callable[[], Any],
                 unload_fn: Optional[Callable[[Any], None]] = None):
        self.name = name
        self.load_fn = load_fn
        self.unload_fn = unload_fn
        self.obj: Any = None
        self.last_used: float = 0.0
        self.ram_mb: int = 0
        self.load_ms: int = 0
        self.loads: int = 0
        self.unloads: int = 0
        self.last_error: Optional[str] = None


def _malloc_trim() -> None:
    """Return freed heap to the OS. Without this, Python/torch keep the
    pages and RSS never drops after an unload — fatal on small boxes."""
    try:
        import ctypes

        ctypes.CDLL("libc.so.6").malloc_trim(0)
    except Exception:  # noqa: BLE001
        pass


class Registry:
    def __init__(self) -> None:
        self._handles: Dict[str, ModelHandle] = {}
        self._lru: "OrderedDict[str, None]" = OrderedDict()  # loaded models, LRU first
        self._meta_lock = threading.RLock()
        self._heavy_lock = threading.Lock()
        self._proc = psutil.Process(os.getpid())
        self.started_at = time.time()
        self._stop = threading.Event()
        threading.Thread(target=self._guard_loop, name="ram-guard", daemon=True).start()

    # ── registration ──────────────────────────────────────────────
    def register(self, name: str, load_fn: Callable[[], Any],
                 unload_fn: Optional[Callable[[Any], None]] = None) -> None:
        with self._meta_lock:
            self._handles[name] = ModelHandle(name, load_fn, unload_fn)

    def names(self) -> List[str]:
        with self._meta_lock:
            return list(self._handles.keys())

    # ── RAM ───────────────────────────────────────────────────────
    def rss_mb(self) -> float:
        return self._proc.memory_info().rss / 1048576.0

    # ── access ────────────────────────────────────────────────────
    def is_loaded(self, name: str) -> bool:
        with self._meta_lock:
            h = self._handles.get(name)
            return bool(h and h.obj is not None)

    def get(self, name: str) -> Any:
        """Return the model object, lazy-loading (thread-safe) on first use."""
        with self._meta_lock:
            h = self._handles[name]  # KeyError = programmer error, fail loud
            if h.obj is not None:
                h.last_used = time.time()
                self._lru.move_to_end(name)
                return h.obj
        with self._heavy_lock:  # only ONE heavy load at a time
            with self._meta_lock:
                if h.obj is not None:  # another thread loaded it while we waited
                    h.last_used = time.time()
                    self._lru.move_to_end(name)
                    return h.obj
            before = self.rss_mb()
            t0 = time.time()
            log.info("model load begin name=%s rss_mb=%.0f", name, before)
            try:
                obj = h.load_fn()
            except Exception as exc:  # noqa: BLE001
                h.last_error = f"{type(exc).__name__}: {exc}"
                log.exception("model load FAILED name=%s", name)
                raise RuntimeError(f"model '{name}' failed to load: {exc}") from exc
            gc.collect()
            h.obj = obj
            h.ram_mb = int(max(self.rss_mb() - before, 0))
            h.load_ms = int((time.time() - t0) * 1000)
            h.loads += 1
            h.last_error = None
            with self._meta_lock:
                h.last_used = time.time()
                self._lru[name] = None
                self._lru.move_to_end(name)
            log.info("model load done name=%s ram_delta_mb=%d load_ms=%d rss_mb=%.0f",
                     name, h.ram_mb, h.load_ms, self.rss_mb())
        # capture BEFORE enforce(): if the load itself pushed RSS over the
        # limit, the guard will evict THIS model right now — the caller must
        # still receive a usable object for THIS request (it finishes on the
        # in-memory reference; the unload only affects future requests).
        obj = h.obj
        self.enforce()
        return obj

    # ── unload ────────────────────────────────────────────────────
    def unload(self, name: str) -> bool:
        with self._heavy_lock:
            with self._meta_lock:
                h = self._handles.get(name)
                if h is None or h.obj is None:
                    return False
                self._lru.pop(name, None)
            try:
                if h.unload_fn:
                    h.unload_fn(h.obj)
            except Exception:  # noqa: BLE001
                log.exception("unload hook failed name=%s", name)
            finally:
                h.obj = None
                gc.collect()
                _malloc_trim()
                h.unloads += 1
            log.info("model unloaded name=%s rss_mb=%.0f", name, self.rss_mb())
        return True

    def enforce(self) -> int:
        """Unload LRU models until RSS <= limit. Returns number unloaded."""
        n = 0
        while self.rss_mb() > config.RAM_LIMIT_MB:
            with self._meta_lock:
                victim = next(iter(self._lru)) if self._lru else None
            if victim is None:
                log.warning("RAM guard: rss=%.0fMB over limit=%dMB but nothing loaded to unload",
                            self.rss_mb(), config.RAM_LIMIT_MB)
                break
            log.warning("RAM guard: rss=%.0fMB > limit=%dMB → unloading LRU model '%s'",
                        self.rss_mb(), config.RAM_LIMIT_MB, victim)
            self.unload(victim)
            n += 1
        return n

    def _guard_loop(self) -> None:
        while not self._stop.wait(config.GUARD_INTERVAL_S):
            try:
                self.enforce()
            except Exception:  # noqa: BLE001
                log.exception("ram guard loop error")

    # ── introspection (for /health) ───────────────────────────────
    def snapshot(self) -> List[Dict[str, Any]]:
        now = time.time()
        out: List[Dict[str, Any]] = []
        with self._meta_lock:
            for name in self._handles:
                h = self._handles[name]
                out.append({
                    "name": name,
                    "loaded": h.obj is not None,
                    "ram_mb": h.ram_mb if h.obj is not None else 0,
                    "last_used_age_s": int(now - h.last_used) if h.last_used else None,
                    "load_ms": h.load_ms,
                    "loads": h.loads,
                    "unloads": h.unloads,
                    "last_error": h.last_error,
                })
        return out


registry = Registry()
