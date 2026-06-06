"""
LLM adapter — runs Oracle/SOV1 against either:
  - Local Ollama     (default, free — set LOCAL_MODE=true in .env)
  - Anthropic cloud  (turbo mode — requires ANTHROPIC_API_KEY)

Set in .env:
  LOCAL_MODE=true
  LOCAL_MODEL=qwen2.5:7b             # text/reasoning model
  LOCAL_MODEL_VISION=qwen2.5-vl:7b   # vision model for SOV1
  OLLAMA_BASE=http://localhost:11434/v1
"""

import os

# ── Defaults ─────────────────────────────────────────────────────────────────

DEFAULT_LOCAL_MODEL        = "qwen2.5:7b"
DEFAULT_LOCAL_MODEL_VISION = "qwen2.5-vl:7b"
DEFAULT_OLLAMA_BASE        = "http://localhost:11434/v1"
DEFAULT_CLOUD_MODEL        = "claude-sonnet-4-6"


def is_local() -> bool:
    return os.getenv("LOCAL_MODE", "").lower() in ("1", "true", "yes")


def get_model(vision: bool = False) -> str:
    if is_local():
        key = "LOCAL_MODEL_VISION" if vision else "LOCAL_MODEL"
        default = DEFAULT_LOCAL_MODEL_VISION if vision else DEFAULT_LOCAL_MODEL
        return os.getenv(key, default)
    # Cloud: check config.yaml, then env, then default
    try:
        import yaml
        from pathlib import Path
        cfg_path = Path(__file__).parent.parent / "config.yaml"
        if cfg_path.exists():
            cfg = yaml.safe_load(cfg_path.read_text(encoding="utf-8"))
            model = cfg.get("oracle", {}).get("model")
            if model:
                return model
    except Exception:
        pass
    return os.getenv("CLOUD_MODEL", DEFAULT_CLOUD_MODEL)


def make_client():
    """Return the right SDK client for the current mode."""
    if is_local():
        try:
            from openai import OpenAI
        except ImportError:
            raise RuntimeError(
                "openai package not installed.\n"
                "Run: pip install openai\n"
                "Then make sure Ollama is running: https://ollama.com"
            )
        base = os.getenv("OLLAMA_BASE", DEFAULT_OLLAMA_BASE)
        return OpenAI(base_url=base, api_key="ollama")

    # Cloud mode — anthropic is optional; only imported here
    try:
        import anthropic
    except ImportError:
        raise RuntimeError(
            "anthropic package not installed.\n"
            "Run: pip install anthropic  OR  set LOCAL_MODE=true in .env to use Ollama."
        )
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        raise RuntimeError(
            "ANTHROPIC_API_KEY not set.\n"
            "Add it to .env  OR  set LOCAL_MODE=true to run free locally with Ollama."
        )
    return anthropic.Anthropic(api_key=api_key)


def check_ollama() -> tuple[bool, str]:
    """
    Ping Ollama to verify it is reachable.
    Returns (ok: bool, message: str).
    """
    import urllib.request
    import urllib.error
    base = os.getenv("OLLAMA_BASE", DEFAULT_OLLAMA_BASE)
    # Strip /v1 suffix — Ollama root health endpoint is at /
    root = base.rstrip("/")
    if root.endswith("/v1"):
        root = root[:-3]
    try:
        with urllib.request.urlopen(root, timeout=2) as r:
            return True, f"Ollama reachable at {root}"
    except urllib.error.URLError as e:
        return False, f"Ollama not reachable at {root} — is it running? ({e.reason})"
    except Exception as e:
        return False, f"Ollama check failed: {e}"


def startup_status() -> dict:
    """
    Return a dict describing the current runtime configuration.
    Used by oracle.py banner and planner.py header.
    """
    local = is_local()
    model = get_model(vision=False)
    vision_model = get_model(vision=True)

    # SOV1 / computer control availability
    try:
        import sys
        from pathlib import Path
        sys.path.insert(0, str(Path(__file__).parent))
        import computer_control as cc
        sov1_ok = cc.HANDS_AVAILABLE
        sov1_msg = "available" if sov1_ok else "unavailable (install pyautogui + pillow)"
    except Exception:
        sov1_ok = False
        sov1_msg = "unavailable (computer_control import failed)"

    status = {
        "mode": "LOCAL" if local else "CLOUD",
        "model": model,
        "vision_model": vision_model if local else "N/A (cloud handles vision)",
        "sov1_available": sov1_ok,
        "sov1_msg": sov1_msg,
    }

    if local:
        ollama_ok, ollama_msg = check_ollama()
        status["ollama_ok"] = ollama_ok
        status["ollama_msg"] = ollama_msg

    return status


# ── Tool definition conversion ────────────────────────────────────────────────

def to_openai_tools(anthropic_tools: list) -> list:
    """Convert Anthropic-format tool definitions to OpenAI format."""
    return [
        {
            "type": "function",
            "function": {
                "name": t["name"],
                "description": t.get("description", ""),
                "parameters": t.get("input_schema", {"type": "object", "properties": {}}),
            },
        }
        for t in anthropic_tools
    ]


# ── Image block helpers ───────────────────────────────────────────────────────

def anthropic_image_block(b64: str, media_type: str = "image/png") -> dict:
    return {"type": "image", "source": {"type": "base64", "media_type": media_type, "data": b64}}


def openai_image_block(b64: str, media_type: str = "image/png") -> dict:
    return {"type": "image_url", "image_url": {"url": f"data:{media_type};base64,{b64}"}}


def image_block(b64: str, media_type: str = "image/png") -> dict:
    """Return an image block in the correct format for the current mode."""
    return openai_image_block(b64, media_type) if is_local() else anthropic_image_block(b64, media_type)
