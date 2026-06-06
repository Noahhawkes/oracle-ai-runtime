"""
LLM adapter — runs Oracle/SOV1 against either:
  - Anthropic cloud  (default, requires ANTHROPIC_API_KEY)
  - Local Ollama     (free, set LOCAL_MODE=true in .env)

Set in .env:
  LOCAL_MODE=true
  LOCAL_MODEL=qwen2.5:7b          # text/reasoning model
  LOCAL_MODEL_VISION=qwen2.5-vl:7b  # vision model for SOV1 (needs a GPU)
  OLLAMA_BASE=http://localhost:11434/v1  # default Ollama address
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
    return os.getenv("CLOUD_MODEL", DEFAULT_CLOUD_MODEL)


def make_client():
    """Return the right SDK client for the current mode."""
    if is_local():
        try:
            from openai import OpenAI
        except ImportError:
            raise RuntimeError(
                "openai package not installed. Run: pip install openai\n"
                "Also make sure Ollama is running: https://ollama.com"
            )
        base = os.getenv("OLLAMA_BASE", DEFAULT_OLLAMA_BASE)
        return OpenAI(base_url=base, api_key="ollama")

    import anthropic
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        raise RuntimeError("ANTHROPIC_API_KEY not set. Add it to .env or set LOCAL_MODE=true to run free locally.")
    return anthropic.Anthropic(api_key=api_key)


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
