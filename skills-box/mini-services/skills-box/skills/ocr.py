"""POST /ocr — screenshots/attachments → text. PaddleOCR.

Request:  {"image_base64": "...", |  "image_url": "https://...", "lang": "en"}
Response data: {"text": "...", "n_lines": 12, "lang": "en"}

Supports both PaddleOCR 2.x (.ocr) and 3.x (.predict) APIs.
"""
from __future__ import annotations

import base64
import logging
import os
import threading

from core import config
from core.registry import registry

# Paddle 3.x PIR executor bugs on CPU (stride/onednn attribute conversion) —
# legacy mode is stable. Flags must be set BEFORE paddle/paddleocr import.
os.environ.setdefault("FLAGS_enable_pir_api", "0")
os.environ.setdefault("FLAGS_enable_pir_in_executor", "0")

log = logging.getLogger("skills.ocr")
_infer_lock = threading.Lock()


def _load():
    from paddleocr import PaddleOCR

    try:  # PaddleOCR >= 3.0
        return PaddleOCR(
            lang="en",
            use_doc_orientation_classify=False,
            use_doc_unwarping=False,
            use_textline_orientation=False,
            enable_mkldnn=False,  # onednn path crashes on paddle 3.x CPU
        )
    except TypeError:  # PaddleOCR 2.x
        return PaddleOCR(lang="en", use_angle_cls=True, show_log=False)


registry.register("ocr", _load)


def _image_from_payload(image_base64: str, image_url: str):
    import numpy as np

    if image_base64:
        payload = image_base64
        if "," in payload and payload.strip().startswith("data:"):
            payload = payload.split(",", 1)[1]
        raw = base64.b64decode(payload, validate=False)
        if not raw:
            raise ValueError("image_base64 decoded to zero bytes")
    elif image_url:
        import requests

        res = requests.get(image_url, timeout=20)
        res.raise_for_status()
        raw = res.content
    else:
        raise ValueError("provide image_base64 or image_url")

    import cv2

    arr = np.frombuffer(raw, dtype=np.uint8)
    img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    if img is None:
        raise ValueError("could not decode image (unsupported format?)")
    return img


def _texts_from_result_3x(res) -> list:
    # OCRResult supports dict-style access to rec_texts
    try:
        texts = res["rec_texts"]
        if texts is not None:
            return list(texts)
    except Exception:  # noqa: BLE001
        pass
    try:
        data = getattr(res, "json")
        data = data() if callable(data) else data
        if isinstance(data, dict):
            nested = data.get("res", data)
            return list(nested.get("rec_texts") or [])
    except Exception:  # noqa: BLE001
        pass
    if isinstance(res, dict):
        return list(res.get("rec_texts") or [])
    return []


def ocr(image_base64: str = "", image_url: str = "", lang: str = "en") -> dict:
    if lang and lang != "en":
        log.info("non-en lang '%s' requested — engine stays en for now", lang)

    engine = registry.get("ocr")
    img = _image_from_payload(image_base64, image_url)

    lines: list = []
    with _infer_lock:
        if hasattr(engine, "predict"):  # 3.x
            for res in engine.predict(img):
                lines.extend(_texts_from_result_3x(res))
        else:  # 2.x
            result = engine.ocr(img, cls=True)
            for page in result or []:
                for line in page or []:
                    try:
                        lines.append(str(line[1][0]))
                    except (IndexError, TypeError):
                        continue

    text = "\n".join(l for l in lines if l)
    return {"text": text, "n_lines": len(lines), "lang": "en"}
