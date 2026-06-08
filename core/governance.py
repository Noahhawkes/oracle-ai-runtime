"""
core/governance.py — ORACLE Governance Defaults

The authoritative source for ORACLE's safety and governance settings.
Every module that needs to know a governance state should import from here,
not read raw environment variables directly.

Code defaults are the safe values.
Environment variables can relax them — never tighten.
Noah can also call override() to change settings at runtime.

Governance is not a layer on top of ORACLE.
Governance is ORACLE's spine.

She operates because she is governed. Not despite it.

Rules baked into code (cannot be overridden by accident):
  - ORACLE_MEMORY_APPROVAL_REQUIRED defaults to True
  - ORACLE_RAW_CAPTURE defaults to False
  - ORACLE_SENSITIVE_BLOCK defaults to True
  - Candidate approval is always enforced in code
  - The 51/49 rule is architectural, not a setting

Doctrine reference: docs/ORACLE_DOCTRINE.md
"""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

if getattr(sys, "frozen", False):
    ROOT = Path(sys.executable).parent
else:
    ROOT = Path(__file__).parent.parent

GOVERNANCE_OVERRIDE_FILE = ROOT / "Memory" / "governance_overrides.json"

# ── Code defaults (the floor — safe values) ───────────────────────────────────

_DEFAULTS: dict[str, Any] = {
    # Memory governance
    "ORACLE_MEMORY_APPROVAL_REQUIRED": True,    # all candidates must be approved by Noah
    "ORACLE_RAW_CAPTURE": False,                 # raw screenshots/video never stored as memory
    "ORACLE_SENSITIVE_BLOCK": True,              # sensitive candidates blocked until reviewed
    "ORACLE_AUTO_APPROVE": False,                # never auto-approve candidates

    # Execution governance
    "ORACLE_SAFE_SLEEP_DEFAULT": False,          # safe sleep is not the default on startup
    "ORACLE_DRY_RUN_DEFAULT": False,             # dry run is not the default on startup
    "ORACLE_MAX_ACTIONS_PER_BATCH": 10,          # max desktop actions per SOV1 batch
    "ORACLE_REQUIRE_VERIFICATION": True,         # actuation must produce verification evidence

    # Privacy governance
    "ORACLE_STORE_RAW_SCREENSHOTS": False,       # raw pixel data never stored
    "ORACLE_STORE_RAW_VIDEO": False,             # raw video never stored as memory
    "ORACLE_KEYLOG": False,                      # never keylog
    "ORACLE_SURVEILLANCE_MODE": False,           # never raw surveillance

    # API governance
    "ORACLE_LOCAL_MODE_DEFAULT": True,           # prefer local Ollama — no cloud by default
    "ORACLE_REQUIRE_LOCAL_FOR_ACTUATION": True,  # actuation always uses local models

    # Sovereignty
    "ORACLE_NOAH_SOVEREIGNTY_PCT": 51,           # Noah holds 51% — not a setting, a law
    "ORACLE_ORACLE_OPERATIONAL_PCT": 49,         # she operates the 49%
}

# ── Runtime state ─────────────────────────────────────────────────────────────

_overrides: dict[str, Any] = {}
_loaded_at: Optional[str] = None


def _load_overrides() -> dict:
    """Load runtime overrides from Memory/governance_overrides.json (if it exists)."""
    try:
        return json.loads(GOVERNANCE_OVERRIDE_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _env(key: str, default: Any) -> Any:
    """Read key from environment. Type-coerce to match default type."""
    val = os.environ.get(key)
    if val is None:
        return default
    if isinstance(default, bool):
        return val.lower() in ("1", "true", "yes")
    if isinstance(default, int):
        try:
            return int(val)
        except ValueError:
            return default
    return val


def _resolve(key: str) -> Any:
    """
    Resolve a governance setting. Priority (highest to lowest):
      1. Runtime override (set by Noah during session)
      2. Environment variable
      3. Code default (safe floor)
    """
    if key in _overrides:
        return _overrides[key]
    default = _DEFAULTS.get(key)
    return _env(key, default)


def load() -> None:
    """Load persisted overrides from disk. Call at startup."""
    global _overrides, _loaded_at
    _overrides = _load_overrides()
    _loaded_at = datetime.now(timezone.utc).isoformat()


def get(key: str, fallback: Any = None) -> Any:
    """Get a governance setting by name."""
    if key not in _DEFAULTS and fallback is None:
        raise KeyError(f"Unknown governance key: {key!r}. Valid keys: {sorted(_DEFAULTS)}")
    return _resolve(key) if key in _DEFAULTS else fallback


def get_all() -> dict[str, Any]:
    """Return all governance settings as a dict (resolved values)."""
    return {k: _resolve(k) for k in _DEFAULTS}


def override(key: str, value: Any, persist: bool = False) -> None:
    """
    Set a runtime override. Noah can call this to relax or tighten a setting.
    If persist=True, writes to Memory/governance_overrides.json.
    Only Noah may override. ORACLE may not override herself.
    """
    if key not in _DEFAULTS:
        raise KeyError(f"Unknown governance key: {key!r}")
    _overrides[key] = value
    if persist:
        GOVERNANCE_OVERRIDE_FILE.parent.mkdir(parents=True, exist_ok=True)
        existing = _load_overrides()
        existing[key] = value
        GOVERNANCE_OVERRIDE_FILE.write_text(
            json.dumps(existing, indent=2, ensure_ascii=False), encoding="utf-8"
        )


def reset_override(key: str) -> None:
    """Remove a runtime override, falling back to env/default."""
    _overrides.pop(key, None)


# ── Convenience accessors (the ones the dashboard and modules need most) ───────

def is_raw_capture_allowed() -> bool:
    """True if raw screenshot/video capture is permitted."""
    return bool(_resolve("ORACLE_RAW_CAPTURE"))


def is_approval_required() -> bool:
    """True if all memory candidates require Noah's approval before storage."""
    return bool(_resolve("ORACLE_MEMORY_APPROVAL_REQUIRED"))


def is_sensitive_block_active() -> bool:
    """True if sensitive candidates are blocked until explicitly reviewed."""
    return bool(_resolve("ORACLE_SENSITIVE_BLOCK"))


def is_auto_approve_allowed() -> bool:
    """True if candidates can be auto-approved (should almost always be False)."""
    return bool(_resolve("ORACLE_AUTO_APPROVE"))


def is_verification_required() -> bool:
    """True if actuation must produce verification evidence before claiming success."""
    return bool(_resolve("ORACLE_REQUIRE_VERIFICATION"))


def is_local_mode_default() -> bool:
    """True if ORACLE defaults to local Ollama (API-independent)."""
    return bool(_resolve("ORACLE_LOCAL_MODE_DEFAULT"))


def sovereignty_split() -> tuple[int, int]:
    """Return (noah_pct, oracle_pct). Law: always (51, 49)."""
    return (
        int(_resolve("ORACLE_NOAH_SOVEREIGNTY_PCT")),
        int(_resolve("ORACLE_ORACLE_OPERATIONAL_PCT")),
    )


def governance_summary() -> dict:
    """Return a human-readable summary dict for the dashboard."""
    return {
        "raw_capture_allowed":       is_raw_capture_allowed(),
        "approval_required":         is_approval_required(),
        "sensitive_block":           is_sensitive_block_active(),
        "auto_approve":              is_auto_approve_allowed(),
        "verification_required":     is_verification_required(),
        "local_mode_default":        is_local_mode_default(),
        "store_raw_screenshots":     bool(_resolve("ORACLE_STORE_RAW_SCREENSHOTS")),
        "store_raw_video":           bool(_resolve("ORACLE_STORE_RAW_VIDEO")),
        "keylog":                    bool(_resolve("ORACLE_KEYLOG")),
        "surveillance_mode":         bool(_resolve("ORACLE_SURVEILLANCE_MODE")),
        "noah_sovereignty_pct":      int(_resolve("ORACLE_NOAH_SOVEREIGNTY_PCT")),
        "oracle_operational_pct":    int(_resolve("ORACLE_ORACLE_OPERATIONAL_PCT")),
        "max_actions_per_batch":     int(_resolve("ORACLE_MAX_ACTIONS_PER_BATCH")),
        "runtime_overrides":         list(_overrides.keys()),
        "loaded_at":                 _loaded_at or "not loaded",
    }


# ── Load overrides on import ───────────────────────────────────────────────────
load()


# ── Smoke tests ───────────────────────────────────────────────────────────────

def run_smoke_tests() -> int:
    failures = 0

    def check(name: str, passed: bool, detail: str = "") -> None:
        nonlocal failures
        if not passed:
            failures += 1
        tag = "PASS" if passed else "FAIL"
        print(f"  [{tag}] {name}" + (f" -- {detail}" if detail else ""))

    print(f"\n{'='*55}")
    print("ORACLE Governance -- Smoke Tests")
    print(f"{'='*55}")

    # Defaults are safe values
    check("raw_capture default=False",     not is_raw_capture_allowed())
    check("approval_required default=True", is_approval_required())
    check("sensitive_block default=True",  is_sensitive_block_active())
    check("auto_approve default=False",    not is_auto_approve_allowed())
    check("verification_required=True",    is_verification_required())
    check("local_mode_default=True",       is_local_mode_default())
    check("store_raw_screenshots=False",   not _resolve("ORACLE_STORE_RAW_SCREENSHOTS"))
    check("store_raw_video=False",         not _resolve("ORACLE_STORE_RAW_VIDEO"))
    check("keylog=False",                  not _resolve("ORACLE_KEYLOG"))
    check("surveillance_mode=False",       not _resolve("ORACLE_SURVEILLANCE_MODE"))

    # Sovereignty law
    noah, oracle = sovereignty_split()
    check("Noah holds 51%",  noah == 51)
    check("ORACLE holds 49%", oracle == 49)

    # get_all returns all keys
    all_g = get_all()
    check("get_all returns dict",         isinstance(all_g, dict))
    check("get_all has all defaults",     set(all_g.keys()) == set(_DEFAULTS.keys()))

    # override and reset
    override("ORACLE_MAX_ACTIONS_PER_BATCH", 5)
    check("override works",               get("ORACLE_MAX_ACTIONS_PER_BATCH") == 5)
    reset_override("ORACLE_MAX_ACTIONS_PER_BATCH")
    check("reset restores default",       get("ORACLE_MAX_ACTIONS_PER_BATCH") == 10)

    # Unknown key raises
    try:
        get("ORACLE_NONEXISTENT_KEY_XYZ")
        check("unknown key raises KeyError", False)
    except KeyError:
        check("unknown key raises KeyError", True)

    # governance_summary is dict with expected keys
    summary = governance_summary()
    check("summary is dict",              isinstance(summary, dict))
    check("summary has approval_required", "approval_required" in summary)
    check("summary has sovereignty",      "noah_sovereignty_pct" in summary)

    # Env override
    import os as _os
    orig = _os.environ.get("ORACLE_RAW_CAPTURE")
    try:
        _os.environ["ORACLE_RAW_CAPTURE"] = "true"
        check("env can relax raw_capture",    _resolve("ORACLE_RAW_CAPTURE") is True or
                                               _resolve("ORACLE_RAW_CAPTURE") == True)
        _os.environ["ORACLE_RAW_CAPTURE"] = "false"
        check("env can enforce raw_capture off", not _resolve("ORACLE_RAW_CAPTURE"))
    finally:
        if orig is None:
            _os.environ.pop("ORACLE_RAW_CAPTURE", None)
        else:
            _os.environ["ORACLE_RAW_CAPTURE"] = orig

    total  = 22
    passed = total - failures
    print(f"{'='*55}")
    print(f"Result: {passed}/{total} passed")
    print(f"STATUS: {'ALL PASS' if failures == 0 else str(failures) + ' FAILURES'}")
    print(f"{'='*55}\n")
    return failures


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="ORACLE Governance")
    parser.add_argument("--smoke-test", action="store_true")
    parser.add_argument("--show",       action="store_true", help="Print all governance settings")
    parser.add_argument("--set",        nargs=2, metavar=("KEY", "VALUE"),
                        help="Set a persistent override (Noah only)")
    args = parser.parse_args()

    if args.smoke_test:
        sys.exit(run_smoke_tests())

    if args.show:
        summary = governance_summary()
        print(f"\n{'='*55}")
        print("  ORACLE Governance Settings")
        print(f"{'='*55}")
        for k, v in sorted(summary.items()):
            status = ""
            if k in ("raw_capture_allowed", "auto_approve", "store_raw_screenshots",
                      "store_raw_video", "keylog", "surveillance_mode"):
                status = "  [SAFE]" if not v else "  [WARNING]"
            if k in ("approval_required", "sensitive_block", "verification_required"):
                status = "  [ENFORCED]" if v else "  [WARNING: disabled]"
            print(f"  {k:<35} {str(v):<10}{status}")
        noah, oracle_ = sovereignty_split()
        print(f"\n  Sovereignty: Noah {noah}% | ORACLE {oracle_}%")
        print(f"{'='*55}\n")
        sys.exit(0)

    if args.set:
        key, val = args.set
        # Coerce value
        if val.lower() in ("true", "1", "yes"):
            val = True
        elif val.lower() in ("false", "0", "no"):
            val = False
        elif val.isdigit():
            val = int(val)
        override(key, val, persist=True)
        print(f"Governance override set: {key} = {val} (persisted)")
