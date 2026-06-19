"""
Receipt-backed ORACLE boot status.

Track 1 guarantees:
  * runtime authority is C:\\Oracle\\ORACLE.AI-runtime
  * private state authority is C:\\Oracle\\state
  * boot receipts are written under C:\\Oracle\\state\\boot_receipts
  * cognition mode is local_only only when the requested local model is verified
  * offline_no_model never calls a remote model provider
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from root_map import (
    BOOT_RECEIPTS_DIR,
    FORBIDDEN_RUNTIME_ROOTS,
    RATIFIED_RUNTIME_ROOT,
    RATIFIED_STATE_ROOT,
    RootAuthorityError,
    require_root_authority,
)

DEFAULT_LOCAL_MODEL = "qwen2.5:7b"
DEFAULT_LOCAL_MODEL_VISION = "qwen2.5-vl:7b"
DEFAULT_OLLAMA_BASE = "http://localhost:11434/v1"

REMOTE_KEY_ENV_NAMES = (
    "OPENAI_API_KEY",
    "ANTHROPIC_API_KEY",
    "GOOGLE_API_KEY",
    "GEMINI_API_KEY",
    "XAI_API_KEY",
)

NO_MODEL_LINE = (
    "Local floor online, but cognition is unavailable. I can report system state, "
    "root authority, receipts, and retrieval status, but no local model is currently "
    "available. Network boundary is local-only. Noah.Physical remains final authority."
)


class BootReceiptError(RuntimeError):
    """Raised when the boot receipt cannot be created or trusted."""


def _truthy_env(name: str, default: str = "false") -> bool:
    return os.getenv(name, default).strip().lower() in {"1", "true", "yes", "on"}


def force_local_enabled() -> bool:
    return _truthy_env("ORACLE_FORCE_LOCAL", "false")


def local_mode_enabled() -> bool:
    if force_local_enabled():
        return True
    return os.getenv("LOCAL_MODE", "true").strip().lower() not in {"0", "false", "no", "off"}


def requested_model_name(*, vision: bool = False) -> str:
    key = "LOCAL_MODEL_VISION" if vision else "LOCAL_MODEL"
    default = DEFAULT_LOCAL_MODEL_VISION if vision else DEFAULT_LOCAL_MODEL
    return os.getenv(key, default).strip()


def ollama_base_url() -> str:
    return os.getenv("OLLAMA_BASE", DEFAULT_OLLAMA_BASE).strip() or DEFAULT_OLLAMA_BASE


def ollama_root_url(base_url: str | None = None) -> str:
    root = (base_url or ollama_base_url()).rstrip("/")
    if root.endswith("/v1"):
        root = root[:-3].rstrip("/")
    return root


def is_loopback_url(url: str) -> bool:
    parsed = urllib.parse.urlparse(url)
    host = (parsed.hostname or "").lower()
    return host in {"localhost", "127.0.0.1", "::1"}


def network_boundary() -> str:
    if force_local_enabled():
        return "local-only"
    if local_mode_enabled():
        return "local-only"
    return "cloud-assisted"


def _ollama_tags(timeout: float = 1.5) -> tuple[list[str], str, str]:
    root = ollama_root_url()
    if force_local_enabled() and not is_loopback_url(root):
        raise BootReceiptError(
            f"ORACLE_FORCE_LOCAL=true requires loopback OLLAMA_BASE; got {root}"
        )
    try:
        with urllib.request.urlopen(f"{root}/api/tags", timeout=timeout) as response:
            payload = json.loads(response.read().decode("utf-8"))
        names = [str(item.get("name", "")).strip() for item in payload.get("models", []) if item.get("name")]
        return sorted(set(names)), "reachable", ""
    except urllib.error.URLError as exc:
        return [], "unreachable", str(getattr(exc, "reason", exc))
    except Exception as exc:
        return [], "unreachable", f"{type(exc).__name__}: {exc}"


def _ollama_list_names(timeout: float = 4.0) -> tuple[list[str], str]:
    try:
        completed = subprocess.run(
            ["ollama", "list"],
            cwd=RATIFIED_RUNTIME_ROOT,
            text=True,
            capture_output=True,
            timeout=timeout,
            check=False,
        )
    except Exception as exc:
        return [], f"{type(exc).__name__}: {exc}"
    if completed.returncode != 0:
        return [], (completed.stderr or completed.stdout or "").strip()

    names: list[str] = []
    for line in completed.stdout.splitlines():
        line = line.strip()
        if not line or line.lower().startswith("name "):
            continue
        names.append(line.split()[0])
    return sorted(set(names)), ""


def inspect_cognition() -> dict[str, Any]:
    target = requested_model_name(vision=False)
    vision_target = requested_model_name(vision=True)
    warnings: list[str] = []
    boundary = network_boundary()

    names, engine_state, engine_error = _ollama_tags()
    source = "ollama_api_tags"
    if not names:
        cli_names, cli_error = _ollama_list_names()
        if cli_names:
            names = cli_names
            source = "ollama_list"
            if engine_state != "reachable":
                warnings.append(f"ollama HTTP not confirmed: {engine_error or 'unreachable'}")
        elif cli_error:
            warnings.append(f"ollama list unavailable: {cli_error}")

    model_verified = target in names
    mode = "local_only" if model_verified else "offline_no_model"
    verified_engine = "ollama" if model_verified else None
    verified_model = target if model_verified else None

    if not model_verified:
        warnings.append(f"matching local model weights unavailable for {target}")
    if boundary == "local-only":
        present_keys = [name for name in REMOTE_KEY_ENV_NAMES if os.getenv(name)]
        if present_keys:
            warnings.append("cloud keys present but unused: " + ", ".join(present_keys))

    return {
        "mode": mode,
        "requested_model_name": target,
        "requested_vision_model_name": vision_target,
        "verified_model_name": verified_model,
        "verified_local_engine": verified_engine,
        "model_weights_available": model_verified,
        "available_local_models": names[:40],
        "local_model_source": source,
        "ollama_base_url": ollama_base_url(),
        "ollama_root_url": ollama_root_url(),
        "ollama_engine_state": engine_state,
        "ollama_engine_error": engine_error,
        "network_boundary": boundary,
        "force_local": force_local_enabled(),
        "local_mode": local_mode_enabled(),
        "remote_model_providers_used": False,
        "warnings": warnings,
    }


def _git_value(args: list[str]) -> str:
    try:
        return subprocess.check_output(
            ["git", *args],
            cwd=RATIFIED_RUNTIME_ROOT,
            text=True,
            stderr=subprocess.DEVNULL,
            timeout=4,
        ).strip()
    except Exception:
        return "UNKNOWN"


def _retrieval_status() -> dict[str, Any]:
    source_map = RATIFIED_RUNTIME_ROOT / "Memory" / "source_map.json"
    if not source_map.exists():
        return {
            "status": "missing",
            "index_path": str(source_map),
            "warning": "retrieval index missing or stale",
        }
    try:
        raw = json.loads(source_map.read_text(encoding="utf-8"))
        built_at = str(raw.get("built_at") or "")
        age_seconds = None
        stale = False
        if built_at:
            try:
                dt = datetime.fromisoformat(built_at.replace("Z", "+00:00"))
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                age_seconds = max(0, int((datetime.now(timezone.utc) - dt).total_seconds()))
                stale = age_seconds > 7 * 24 * 3600
            except Exception:
                stale = True
        return {
            "status": "stale" if stale else "available",
            "index_path": str(source_map),
            "built_at": built_at or "UNKNOWN",
            "age_seconds": age_seconds,
            "file_count": raw.get("file_count"),
            "warning": "retrieval index missing or stale" if stale else "",
        }
    except Exception as exc:
        return {
            "status": "unavailable",
            "index_path": str(source_map),
            "warning": f"retrieval index unavailable: {type(exc).__name__}: {exc}",
        }


def human_boot_line(receipt: dict[str, Any]) -> str:
    cognition = receipt.get("cognition", {})
    if cognition.get("mode") != "local_only":
        return NO_MODEL_LINE
    model = cognition.get("verified_model_name") or "UNKNOWN"
    engine = cognition.get("verified_local_engine") or "UNKNOWN"
    roots = receipt.get("root_authority", {})
    evidence = roots.get("evidence_roots_status") or "unmapped"
    boundary = cognition.get("network_boundary") or "unknown"
    warnings = len(receipt.get("warnings") or [])
    return (
        f"Local floor online. I am running on {model} through {engine}. "
        f"Runtime root is {RATIFIED_RUNTIME_ROOT}. State root is {RATIFIED_STATE_ROOT}. "
        f"Evidence roots are {evidence}. Network boundary is {boundary}. "
        f"I have {warnings} warnings. Noah.Physical remains final authority."
    )


def offline_no_model_line() -> str:
    return NO_MODEL_LINE


def _atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    tmp.replace(path)


def create_boot_receipt() -> dict[str, Any]:
    try:
        roots = require_root_authority()
    except RootAuthorityError as exc:
        raise BootReceiptError(str(exc)) from exc

    cognition = inspect_cognition()
    retrieval = _retrieval_status()
    warnings = list(roots.warnings)
    warnings.extend(str(w) for w in cognition.get("warnings", []) if w)
    if retrieval.get("warning"):
        warnings.append(str(retrieval["warning"]))

    git_status = _git_value(["status", "--short"])
    if git_status:
        warnings.append("dirty Git worktree")

    warnings.append("media witness not implemented")

    created_at = datetime.now(timezone.utc).isoformat()
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    receipt_path = BOOT_RECEIPTS_DIR / f"boot_{stamp}.json"
    latest_path = BOOT_RECEIPTS_DIR / "latest.json"

    receipt: dict[str, Any] = {
        "schema_version": 1,
        "receipt_kind": "oracle_boot",
        "created_at": created_at,
        "created_at_unix": time.time(),
        "receipt_path": str(receipt_path),
        "latest_path": str(latest_path),
        "root_authority": {
            "runtime_root": str(roots.runtime_root),
            "runtime_root_ratified": str(RATIFIED_RUNTIME_ROOT),
            "state_root": str(roots.state_root),
            "state_root_ratified": str(RATIFIED_STATE_ROOT),
            "boot_receipts_dir": str(roots.boot_receipts_dir),
            "forbidden_runtime_roots": [str(path) for path in FORBIDDEN_RUNTIME_ROOTS],
            "cloud_sync_declared_canonical": False,
            "noah_physical_final_authority": True,
            "evidence_roots": roots.evidence_roots,
            "evidence_roots_status": roots.evidence_roots_status,
        },
        "cognition": cognition,
        "retrieval": retrieval,
        "capabilities": {
            "system_state_reporting": True,
            "root_authority_reporting": True,
            "receipt_reporting": True,
            "retrieval_status_reporting": True,
            "capability_status_reporting": True,
            "freeform_chat_available": cognition.get("mode") == "local_only",
        },
        "git": {
            "branch": _git_value(["branch", "--show-current"]),
            "head": _git_value(["rev-parse", "HEAD"]),
            "dirty": bool(git_status),
            "status_short": git_status.splitlines()[:80],
        },
        "warnings": sorted(set(warnings)),
        "stops": [],
    }
    receipt["human_boot_line"] = human_boot_line(receipt)

    try:
        _atomic_write_json(receipt_path, receipt)
        _atomic_write_json(latest_path, receipt)
    except Exception as exc:
        raise BootReceiptError(f"boot receipt cannot be written: {type(exc).__name__}: {exc}") from exc

    return receipt


def read_latest_receipt() -> dict[str, Any] | None:
    path = BOOT_RECEIPTS_DIR / "latest.json"
    if not path.exists():
        return None
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        return raw if isinstance(raw, dict) else None
    except Exception:
        return None


def get_or_create_boot_receipt() -> dict[str, Any]:
    latest = read_latest_receipt()
    if latest:
        cognition = latest.get("cognition") or {}
        if (
            cognition.get("requested_model_name") == requested_model_name(vision=False)
            and bool(cognition.get("force_local")) == force_local_enabled()
            and bool(cognition.get("local_mode")) == local_mode_enabled()
            and cognition.get("ollama_base_url") == ollama_base_url()
        ):
            return latest
    return create_boot_receipt()


def boot_status_payload() -> dict[str, Any]:
    receipt = get_or_create_boot_receipt()
    cognition = receipt.get("cognition", {})
    root = receipt.get("root_authority", {})
    return {
        "ok": True,
        "cognition_mode": cognition.get("mode"),
        "verified_model_name": cognition.get("verified_model_name"),
        "verified_local_engine": cognition.get("verified_local_engine"),
        "network_boundary": cognition.get("network_boundary"),
        "runtime_root": root.get("runtime_root"),
        "state_root": root.get("state_root"),
        "evidence_roots_status": root.get("evidence_roots_status"),
        "boot_receipt_path": receipt.get("receipt_path"),
        "latest_json_path": receipt.get("latest_path"),
        "warnings": receipt.get("warnings", []),
        "human_boot_line": receipt.get("human_boot_line") or human_boot_line(receipt),
        "receipt": receipt,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Create or read an ORACLE boot receipt")
    parser.add_argument("--print-line", action="store_true")
    parser.add_argument("--print-json", action="store_true")
    parser.add_argument("--status-json", action="store_true")
    args = parser.parse_args(argv)

    try:
        if args.status_json:
            payload = boot_status_payload()
        else:
            receipt = create_boot_receipt()
            payload = boot_status_payload()
            payload["receipt"] = receipt
    except BootReceiptError as exc:
        print(f"BOOT REFUSED: {exc}", file=sys.stderr)
        return 1

    if args.print_json or args.status_json:
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print(payload["human_boot_line"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
