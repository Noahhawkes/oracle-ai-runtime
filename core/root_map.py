"""
Ratified ORACLE runtime and state root authority.

This module is intentionally deterministic and local. It does not sync roots,
does not inspect cloud mirrors, and does not promote any cloud-sync path to
canonical authority.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

RATIFIED_RUNTIME_ROOT = Path(r"C:\Oracle\ORACLE.AI-runtime")
RATIFIED_STATE_ROOT = Path(r"C:\Oracle\state")
BOOT_RECEIPTS_DIR = RATIFIED_STATE_ROOT / "boot_receipts"

FORBIDDEN_RUNTIME_ROOTS = (
    Path(r"C:\ORACLE.AI"),
    Path(r"G:\My Drive\HawkesNest LLC\ORACLE.AI"),
)

LAUNCHER_FILES = (
    "oracle.bat",
    "oracle_desktop.bat",
    "oracle_console.bat",
    "Launch_ORACLE.ps1",
)


@dataclass(frozen=True)
class RootAuthorityStatus:
    ok: bool
    runtime_root: Path
    state_root: Path
    boot_receipts_dir: Path
    evidence_roots: dict[str, str]
    evidence_roots_status: str
    warnings: list[str] = field(default_factory=list)
    stop_reason: str = ""


class RootAuthorityError(RuntimeError):
    """Raised when a ratified root boundary fails closed."""


def _norm(path: Path | str) -> str:
    return os.path.normcase(os.path.abspath(str(path)))


def same_path(a: Path | str, b: Path | str) -> bool:
    return _norm(a) == _norm(b)


def runtime_root_from_module() -> Path:
    return Path(__file__).resolve().parent.parent


def evidence_root_map(runtime_root: Path | None = None) -> tuple[dict[str, str], str]:
    root = runtime_root or RATIFIED_RUNTIME_ROOT
    roots = {
        "runtime_memory": str(root / "Memory"),
        "runtime_messages": str(root / "Messages"),
        "state_boot_receipts": str(BOOT_RECEIPTS_DIR),
    }
    mapped = all(Path(path).exists() for path in roots.values())
    return roots, "mapped" if mapped else "unmapped"


def launcher_authority_violations(runtime_root: Path | None = None) -> list[str]:
    root = runtime_root or RATIFIED_RUNTIME_ROOT
    violations: list[str] = []
    forbidden = [str(path).lower() for path in FORBIDDEN_RUNTIME_ROOTS]
    authority_words = ("cd ", "cd /d", "push-location", "set-location", "python", "pythonw")

    for rel in LAUNCHER_FILES:
        path = root / rel
        if not path.exists():
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except Exception as exc:
            violations.append(f"{rel}: launcher unreadable: {type(exc).__name__}: {exc}")
            continue
        lower = text.lower()
        if any(forbidden_root in lower for forbidden_root in forbidden) and any(word in lower for word in authority_words):
            violations.append(f"{rel}: launcher references forbidden runtime authority")
    return violations


def validate_root_authority(*, create_boot_dir: bool = True) -> RootAuthorityStatus:
    runtime_root = runtime_root_from_module()
    warnings: list[str] = []

    if not same_path(runtime_root, RATIFIED_RUNTIME_ROOT):
        return RootAuthorityStatus(
            ok=False,
            runtime_root=runtime_root,
            state_root=RATIFIED_STATE_ROOT,
            boot_receipts_dir=BOOT_RECEIPTS_DIR,
            evidence_roots={},
            evidence_roots_status="unmapped",
            stop_reason=(
                "runtime root mismatch: "
                f"expected {RATIFIED_RUNTIME_ROOT}, got {runtime_root}"
            ),
        )

    if not RATIFIED_RUNTIME_ROOT.exists():
        return RootAuthorityStatus(
            ok=False,
            runtime_root=runtime_root,
            state_root=RATIFIED_STATE_ROOT,
            boot_receipts_dir=BOOT_RECEIPTS_DIR,
            evidence_roots={},
            evidence_roots_status="unmapped",
            stop_reason=f"runtime root missing: {RATIFIED_RUNTIME_ROOT}",
        )

    if not RATIFIED_STATE_ROOT.exists():
        return RootAuthorityStatus(
            ok=False,
            runtime_root=runtime_root,
            state_root=RATIFIED_STATE_ROOT,
            boot_receipts_dir=BOOT_RECEIPTS_DIR,
            evidence_roots={},
            evidence_roots_status="unmapped",
            stop_reason=f"state root unavailable: {RATIFIED_STATE_ROOT}",
        )

    if create_boot_dir:
        try:
            BOOT_RECEIPTS_DIR.mkdir(parents=False, exist_ok=True)
        except Exception as exc:
            return RootAuthorityStatus(
                ok=False,
                runtime_root=runtime_root,
                state_root=RATIFIED_STATE_ROOT,
                boot_receipts_dir=BOOT_RECEIPTS_DIR,
                evidence_roots={},
                evidence_roots_status="unmapped",
                stop_reason=f"boot receipt directory unavailable: {type(exc).__name__}: {exc}",
            )

    if not BOOT_RECEIPTS_DIR.exists():
        return RootAuthorityStatus(
            ok=False,
            runtime_root=runtime_root,
            state_root=RATIFIED_STATE_ROOT,
            boot_receipts_dir=BOOT_RECEIPTS_DIR,
            evidence_roots={},
            evidence_roots_status="unmapped",
            stop_reason=f"boot receipt directory missing: {BOOT_RECEIPTS_DIR}",
        )

    violations = launcher_authority_violations(runtime_root)
    if violations:
        return RootAuthorityStatus(
            ok=False,
            runtime_root=runtime_root,
            state_root=RATIFIED_STATE_ROOT,
            boot_receipts_dir=BOOT_RECEIPTS_DIR,
            evidence_roots={},
            evidence_roots_status="unmapped",
            stop_reason="; ".join(violations),
        )

    evidence_roots, evidence_status = evidence_root_map(runtime_root)
    if evidence_status != "mapped":
        warnings.append("evidence roots unmapped")

    return RootAuthorityStatus(
        ok=True,
        runtime_root=runtime_root,
        state_root=RATIFIED_STATE_ROOT,
        boot_receipts_dir=BOOT_RECEIPTS_DIR,
        evidence_roots=evidence_roots,
        evidence_roots_status=evidence_status,
        warnings=warnings,
    )


def require_root_authority() -> RootAuthorityStatus:
    status = validate_root_authority(create_boot_dir=True)
    if not status.ok:
        raise RootAuthorityError(status.stop_reason)
    return status
