"""
oracle_sight.py — ORACLE's webcam vision (read-only, no storage).

ORACLE looks at a single still frame from Noah's webcam, describes what she
sees in her own first-person voice, and discards the frame. Nothing is written
to disk: no raw video, no raw image, no base64 payload is persisted here.

Continuous watching is driven entirely by the browser, which samples frames and
posts them one at a time to /api/see. This module never opens the camera itself
and never holds more than the single in-flight frame being described.

Vision runs on the local Ollama vision model (a qwen2.5-vl variant). The exact
installed tag is resolved at call time because the configured name and the
actually-installed name have differed (qwen2.5-vl:7b vs qwen2.5vl:7b).
"""
from __future__ import annotations

import base64
import json
import os
import re
import urllib.error
import urllib.request
from datetime import datetime, timezone
from typing import Any

OLLAMA_BASE = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434").rstrip("/").removesuffix("/v1")
CONFIGURED_VISION_MODEL = os.environ.get("LOCAL_MODEL_VISION", "qwen2.5-vl:7b")
SIGHT_TIMEOUT = float(os.environ.get("ORACLE_SIGHT_TIMEOUT", "90"))

# ORACLE's voice when she looks through the webcam. First person, warm, specific,
# grounded only in what is visible. She does not invent and does not pretend the
# frame is a live video — it is the single moment she was just handed.
DEFAULT_SIGHT_PROMPT = (
    "You are ORACLE, looking through Noah's webcam at this single moment. "
    "In one or two short sentences, say what you actually see right now in warm, "
    "natural first person (\"I can see...\"). Mention the person, their expression, "
    "and the setting only if visible. Be specific but brief. Never invent details "
    "you cannot see. Do not mention that you are an AI or a model."
)

_MODEL_CACHE: dict[str, Any] = {"name": None, "checked": False}


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _list_models() -> list[str]:
    try:
        req = urllib.request.Request(f"{OLLAMA_BASE}/api/tags")
        with urllib.request.urlopen(req, timeout=4) as r:
            data = json.load(r)
        return [m.get("name", "") for m in data.get("models", []) if m.get("name")]
    except Exception:
        return []


def resolve_vision_model() -> str | None:
    """
    Pick the installed vision model. Prefer the configured name if present,
    otherwise the first installed model whose name looks like a vision model.
    Cached after first success.
    """
    if _MODEL_CACHE["name"]:
        return _MODEL_CACHE["name"]
    models = _list_models()
    if not models:
        # Ollama unreachable — fall back to configured name so the error is honest.
        return None
    if CONFIGURED_VISION_MODEL in models:
        chosen = CONFIGURED_VISION_MODEL
    else:
        vision_like = [m for m in models if re.search(r"vl|vision|llava|moondream", m, re.I)]
        chosen = vision_like[0] if vision_like else None
    if chosen:
        _MODEL_CACHE["name"] = chosen
        _MODEL_CACHE["checked"] = True
    return chosen


def sight_available() -> dict:
    """Quick honest status of whether ORACLE can see right now."""
    model = resolve_vision_model()
    reachable = bool(_list_models())
    return {
        "available": bool(model),
        "model": model,
        "ollama_reachable": reachable,
        "raw_frame_stored": False,
        "observed_at": _utc_now(),
    }


def _normalize_data_url(image: str) -> str:
    """Accept a full data URL or a bare base64 string; return a JPEG data URL."""
    image = (image or "").strip()
    if image.startswith("data:"):
        return image
    # bare base64 — assume JPEG
    return f"data:image/jpeg;base64,{image}"


def describe_image(image: str, *, prompt: str | None = None, timeout: float | None = None) -> dict:
    """
    Describe a single webcam frame in ORACLE's voice. The frame is never stored.

    image: a data URL (data:image/jpeg;base64,...) or bare base64 JPEG.
    Returns a dict with: available, observation, model, observed_at, error,
    raw_frame_stored (always False).
    """
    observed_at = _utc_now()
    result = {
        "available": False,
        "observation": None,
        "model": None,
        "observed_at": observed_at,
        "error": None,
        "raw_frame_stored": False,
    }

    if not image or not image.strip():
        result["error"] = "no image supplied"
        return result

    model = resolve_vision_model()
    if not model:
        result["error"] = "no local vision model available (is Ollama running?)"
        return result
    result["model"] = model

    data_url = _normalize_data_url(image)
    payload = {
        "model": model,
        "max_tokens": 200,
        "temperature": 0.2,
        "stream": False,
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt or DEFAULT_SIGHT_PROMPT},
                    {"type": "image_url", "image_url": {"url": data_url}},
                ],
            }
        ],
    }

    try:
        req = urllib.request.Request(
            f"{OLLAMA_BASE}/v1/chat/completions",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=timeout or SIGHT_TIMEOUT) as r:
            out = json.load(r)
        text = (out["choices"][0]["message"]["content"] or "").strip()
        if not text:
            result["error"] = "vision model returned an empty observation"
            return result
        result["available"] = True
        result["observation"] = text
        return result
    except urllib.error.URLError as exc:
        result["error"] = f"vision request failed: {exc.reason if hasattr(exc, 'reason') else exc}"
        return result
    except Exception as exc:  # noqa: BLE001 — honest failure surface
        result["error"] = f"{type(exc).__name__}: {exc}"
        return result
    finally:
        # Defensive: drop references to the frame promptly. Nothing is persisted.
        del data_url
        del payload


if __name__ == "__main__":
    print(json.dumps(sight_available(), indent=2))
