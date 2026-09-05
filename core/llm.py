"""
LLM adapter — runs Oracle/SOV1 against either:
  - Local Ollama  (DEFAULT — API-independent, no key required)
  - Anthropic cloud  (opt-in — requires ANTHROPIC_API_KEY and LOCAL_MODE=false)

API Independence policy:
  LOCAL_MODE defaults to TRUE. To use cloud you must explicitly set LOCAL_MODE=false.
  Use require_local() at any entry point that must never call the cloud.

Set in .env (optional — defaults are local-first):
  LOCAL_MODE=true                     # default; set false to opt into cloud
  LOCAL_MODEL=qwen2.5:7b             # text/reasoning model
  LOCAL_MODEL_VISION=qwen2.5-vl:7b   # vision model for SOV1
  OLLAMA_BASE=http://localhost:11434/v1
"""

import os
import urllib.parse

# ── Defaults ─────────────────────────────────────────────────────────────────

DEFAULT_LOCAL_MODEL        = "qwen2.5:7b"
DEFAULT_LOCAL_MODEL_VISION = "qwen2.5-vl:7b"
DEFAULT_OLLAMA_BASE        = "http://localhost:11434/v1"
DEFAULT_CLOUD_MODEL        = "claude-sonnet-4-6"


class OfflineNoModelError(RuntimeError):
    """Raised when local-only cognition has no verified local model."""


def is_force_local() -> bool:
    """Return True when cloud fallback is explicitly forbidden."""
    return os.getenv("ORACLE_FORCE_LOCAL", "false").lower() in ("1", "true", "yes", "on")


def _is_loopback_url(url: str) -> bool:
    parsed = urllib.parse.urlparse(url)
    host = (parsed.hostname or "").lower()
    return host in ("localhost", "127.0.0.1", "::1")


def is_local() -> bool:
    """Return True if running in local Ollama mode. Defaults to True (API-independent)."""
    if is_force_local():
        return True
    # Default is "true" — cloud requires explicit LOCAL_MODE=false opt-in
    return os.getenv("LOCAL_MODE", "true").lower() not in ("0", "false", "no")


def is_api_independent() -> bool:
    """Return True when SOV1/ORACLE are running without any cloud API dependency."""
    return is_local()


def require_local(caller: str = "") -> None:
    """
    Raise RuntimeError immediately if not in local mode.
    Call at any entry point that must never touch the cloud API.
    """
    if not is_local():
        prefix = f"[{caller}] " if caller else ""
        raise RuntimeError(
            f"{prefix}API independence violated: LOCAL_MODE is set to false. "
            "SOV1.AI is configured to run on local Ollama only. "
            "To restore independence: set LOCAL_MODE=true in .env (or remove LOCAL_MODE entirely). "
            "To intentionally use cloud: do not call require_local()."
        )
    if is_force_local():
        base = os.getenv("OLLAMA_BASE", DEFAULT_OLLAMA_BASE)
        root = base.rstrip("/")
        if root.endswith("/v1"):
            root = root[:-3]
        if not _is_loopback_url(root):
            prefix = f"[{caller}] " if caller else ""
            raise RuntimeError(
                f"{prefix}API independence violated: ORACLE_FORCE_LOCAL=true but "
                f"OLLAMA_BASE is not loopback ({root})."
            )


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
        require_local("make_client")
        try:
            from boot_receipt import get_or_create_boot_receipt, offline_no_model_line
            receipt = get_or_create_boot_receipt()
            cognition = receipt.get("cognition", {})
            if cognition.get("mode") == "offline_no_model":
                raise OfflineNoModelError(offline_no_model_line())
        except OfflineNoModelError:
            raise
        except Exception:
            # Boot refusal is handled at runtime startup. If an older import path
            # reaches here, keep the local client path rather than falling through
            # to cloud.
            pass
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

    if is_force_local():
        raise RuntimeError(
            "API independence violated: ORACLE_FORCE_LOCAL=true blocks cloud model clients."
        )

    # Cloud mode — delegate to the shared, independence-respecting factory.
    return make_anthropic_client()


def make_anthropic_client():
    """Return an Anthropic SDK client for opt-in frontier paths, or raise clearly.

    Independence-respecting: refuses when ORACLE_FORCE_LOCAL=true. Requires the
    anthropic package and ANTHROPIC_API_KEY. Lets a single lane (e.g. the
    talk-lane mouth) opt into cloud WITHOUT flipping the global LOCAL_MODE
    default. Never logs or returns the key.
    """
    if is_force_local():
        raise RuntimeError(
            "API independence violated: ORACLE_FORCE_LOCAL=true blocks cloud model clients."
        )
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
    if is_force_local() and not _is_loopback_url(root):
        return False, f"Ollama base blocked under ORACLE_FORCE_LOCAL=true: {root}"
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
    receipt = None
    cognition = {}
    try:
        from boot_receipt import get_or_create_boot_receipt
        receipt = get_or_create_boot_receipt()
        cognition = receipt.get("cognition", {})
    except Exception:
        cognition = {}

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
        "mode": (
            "LOCAL"
            if cognition.get("mode") == "local_only"
            else ("OFFLINE_NO_MODEL" if local else "CLOUD")
        ),
        "cognition_mode": cognition.get("mode", "unknown"),
        "model": cognition.get("verified_model_name") or model,
        "vision_model": vision_model if local else "N/A (cloud handles vision)",
        "sov1_available": sov1_ok,
        "sov1_msg": sov1_msg,
        "network_boundary": cognition.get("network_boundary", "unknown"),
        "boot_receipt_path": receipt.get("receipt_path") if receipt else None,
        "latest_json_path": receipt.get("latest_path") if receipt else None,
        "human_boot_line": receipt.get("human_boot_line") if receipt else None,
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
