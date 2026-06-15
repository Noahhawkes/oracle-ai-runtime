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

# Truth-constrained sight prompt. The model describes ONLY what is directly
# visible in this single frame. It does not guess identity, names, relationships,
# intent, or location beyond visible evidence; it does not claim illegible text is
# readable; and it returns the single word UNKNOWN when the frame is too dark,
# blocked, blurred, or otherwise insufficient. It must NOT begin with "I can see"
# (that phrasing, combined with the UI tag, produced the malformed "seesI can see").
DEFAULT_SIGHT_PROMPT = (
    "You are ORACLE describing ONE still camera frame. Report only what is "
    "directly and clearly visible. Do not guess identity, names, relationships, "
    "intent, emotions, or location beyond visible evidence. Do not claim any "
    "unreadable or blurry text is legible. If the frame is too dark, blocked, "
    "blurred, or otherwise insufficient to describe, reply with exactly: UNKNOWN. "
    "Otherwise give one or two plain, literal sentences. Mark anything uncertain "
    "as uncertain. Do NOT begin your reply with the words 'I can see'. Do not "
    "mention that you are an AI or a model."
)

# Below this mean luminance (0-255) a frame is treated as too dark to describe;
# the model is not called and the observation is UNKNOWN. Deterministic, so dark
# frames never reach the vision model.
DARK_THRESHOLD = float(os.environ.get("ORACLE_SIGHT_DARK_THRESHOLD", "16"))

_MODEL_CACHE: dict[str, Any] = {"name": None, "checked": False}


def frame_brightness(image: str) -> float | None:
    """Mean luminance (0-255) of a data-URL/base64 JPEG, or None if undecodable."""
    try:
        import io
        from PIL import Image

        data = image.split(",", 1)[1] if image.startswith("data:") else image
        raw = base64.b64decode(data)
        img = Image.open(io.BytesIO(raw)).convert("L")
        img.thumbnail((32, 32))
        pixels = list(img.getdata())
        return (sum(pixels) / len(pixels)) if pixels else None
    except Exception:
        return None


def assess_frame(image: str) -> dict:
    """
    Classify frame usability before any model call.
    Returns {usable, reason, brightness}. A dark frame is not usable.
    A frame we cannot decode is left usable (the model/prompt handles UNKNOWN).
    """
    brightness = frame_brightness(image)
    if brightness is None:
        return {"usable": True, "reason": "brightness_unknown", "brightness": None}
    if brightness < DARK_THRESHOLD:
        return {"usable": False, "reason": "insufficient_light", "brightness": brightness}
    return {"usable": True, "reason": "ok", "brightness": brightness}


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
        "unknown": False,
        "quality": None,
    }

    if not image or not image.strip():
        result["error"] = "no image supplied"
        return result

    # Deterministic quality gate — dark/unusable frames never reach the model.
    quality = assess_frame(image)
    result["quality"] = quality
    if not quality.get("usable"):
        result["unknown"] = True
        result["error"] = quality.get("reason") or "insufficient_frame"
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
