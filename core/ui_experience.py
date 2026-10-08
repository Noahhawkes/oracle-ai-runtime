"""core/ui_experience.py — ORACLE UI Experience Patch v0.1.

The bridge between natural human phrasing and ORACLE's command handlers. ORACLE
has the command infrastructure; this is the thin UX layer that was missing, so
phrases like "Show me the Evidence Vault" or "Context recall" resolve to useful,
deterministic cards BEFORE any local-model call — instead of the dead
local_timeout fallback blob.

Everything here is read-only and deterministic: no model call, no durable memory
write, no external/network action. Proposals (e.g. /ui-patch) route through the
Guard approval lane via [[pending_actions]].
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

RUNTIME_ROOT = Path(__file__).resolve().parent.parent
_SM_DIR = RUNTIME_ROOT / "Memory" / "source_maps"

try:
    from root_map import RATIFIED_STATE_ROOT
    _STATE_ROOT = Path(RATIFIED_STATE_ROOT)
except Exception:
    _STATE_ROOT = Path(r"C:\Oracle\state")

# ── Natural-language alias groups ────────────────────────────────────────────
_EVIDENCE_VAULT = (
    "show me the evidence vault", "open evidence vault", "evidence vault",
    "show receipts", "show witness artifacts",
)
_CONTEXT_RECALL = (
    "context recall", "recall context", "what do you remember about this build",
    "current context", "thread state",
)
_UI_PATCH = (
    "improve ui experience", "ui sucks", "make this easier",
    "make oracle feel alive", "better interface", "stop fallback blob",
)


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", str(text or "").strip().lower()).strip(" .!?:;")


# ── Helpers ──────────────────────────────────────────────────────────────────
def _count_lines(p: Path) -> int:
    try:
        return sum(1 for l in p.read_text(encoding="utf-8").splitlines() if l.strip())
    except Exception:
        return 0


def _latest_glob(directory: Path, pattern: str) -> Path | None:
    try:
        items = sorted(directory.glob(pattern), key=lambda x: x.stat().st_mtime, reverse=True)
        return items[0] if items else None
    except Exception:
        return None


def _sourcemap_count() -> int:
    """Concrete, true metric: SourceMap artifacts under Memory/source_maps."""
    try:
        return len([p for p in _SM_DIR.glob("*.json")]) if _SM_DIR.exists() else 0
    except Exception:
        return 0


def _pending_memory_candidates() -> int:
    try:
        from approval_center import list_pending
        return sum(1 for p in list_pending() if p.get("source") in ("memory", "intake"))
    except Exception:
        return 0


# ── Evidence Vault ───────────────────────────────────────────────────────────
def evidence_vault() -> str:
    lines: list[str] = ["EVIDENCE VAULT"]
    found_any = False

    live = _latest_glob(_STATE_ROOT / "receipts", "unified_oracle_receipt_*.json")
    if live:
        lines.append(f"- Latest route receipt: {live.name}")
        found_any = True

    try:
        from current_observation import current_observation_state
        obs = current_observation_state()
        lines.append(f"- Current observation receipt: {obs.get('receipt_status', 'unknown')}")
        found_any = True
    except Exception:
        pass

    run_log = _SM_DIR / "run_log.jsonl"
    n_run = _count_lines(run_log)
    if n_run:
        lines.append(f"- Audit receipts (run_log.jsonl): {n_run}")
        found_any = True

    hb = _SM_DIR / "alive_heartbeat.jsonl"
    n_hb = _count_lines(hb)
    if n_hb:
        lines.append(f"- Alive heartbeats: {n_hb}")
        found_any = True

    intake_manifest = _latest_glob(RUNTIME_ROOT / "intake" / "manifests", "intake_manifest_*.json")
    if intake_manifest:
        lines.append(f"- Latest intake manifest: {intake_manifest.name}")
        found_any = True

    sm_count = _sourcemap_count()
    lines.append(f"- SourceMap artifacts (Memory/source_maps): {sm_count}")
    pend_mem = _pending_memory_candidates()
    lines.append(f"- Pending memory/intake candidates: {pend_mem}")

    # Screenshot drop / witness artifacts.
    try:
        from witness_artifacts import count_drops, list_receipts
        n_shots = count_drops()
        n_notes = sum(1 for r in list_receipts() if r.get("kind") == "witness_note")
        if n_shots or n_notes:
            lines.append(f"- Witness artifacts: {n_shots} screenshot(s), {n_notes} note(s)")
            found_any = True
    except Exception:
        pass

    if sm_count <= 1:
        lines.append("WARNING: SourceMap has 1 or 0 artifacts loaded — context may be thin.")

    if not found_any and sm_count == 0:
        return (
            "Evidence Vault is not fully implemented yet. Available evidence sources are: "
            "SourceMap, live receipt, camera receipt, Memory/source_maps, Logs, "
            "screenshot receipts if installed."
        )
    lines.append("BOUNDARY: read-only; no durable memory write; no external action.")
    return "\n".join(lines)


# ── Context Recall ───────────────────────────────────────────────────────────
def context_recall() -> str:
    lines: list[str] = ["CONTEXT RECALL"]

    try:
        from unified_oracle_router import latest_route_status
        rs = latest_route_status()
        lines.append(f"- Mode: {rs.get('mode')} · lane {rs.get('lane_label')} · {rs.get('safety_status')}")
    except Exception:
        lines.append("- Mode: unified_oracle")

    try:
        from boot_receipt import get_or_create_boot_receipt
        cog = get_or_create_boot_receipt().get("cognition", {})
        lines.append(f"- Cognition: {cog.get('mode')} · {cog.get('network_boundary')}")
    except Exception:
        pass

    lines.append(f"- Repo/root: {RUNTIME_ROOT}")
    try:
        from runtime_config import runtime_authority
        lines.append(f"- Runtime: {runtime_authority()}")
    except Exception:
        pass

    try:
        from operational_state import _git_state
        g = _git_state()
        lines.append(f"- Branch/commit: {g.get('branch')} @ {g.get('commit')} ({g.get('working_tree')})")
    except Exception:
        pass

    lines.append(f"- SourceMap artifacts: {_sourcemap_count()}")

    try:
        from approval_center import list_pending
        lines.append(f"- Pending approvals: {len(list_pending())}")
    except Exception:
        pass

    # Active blocker / suggested next action from the resident heartbeat brain.
    try:
        from alive_loop import gather_context, classify_outcome
        meaning = classify_outcome(gather_context(), None)
        lines.append(f"- Active signal: {meaning['outcome']} — {meaning['summary']}")
        if meaning.get("proposed_action"):
            lines.append(f"- Suggested next action: {meaning['proposed_action']}")
    except Exception:
        pass

    lines.append("BOUNDARY: read-only; no durable memory write; no external action.")
    return "\n".join(lines)


# ── UI self-patch proposal ───────────────────────────────────────────────────
UI_PATCH_INTENT = (
    "UI Experience Patch: add natural command aliases, Evidence Vault card, "
    "Context Recall card, Screenshot Drop card, and better timeout fallback."
)


def ui_patch() -> str:
    try:
        from pending_actions import create_pending_action
        token = create_pending_action(
            action_type="ui_self_patch",
            intent_summary=UI_PATCH_INTENT,
            boundary="proposal only; reversible local UI change; Noah.Physical approval; no external action",
        )
        return (
            "UI SELF-PATCH PROPOSED (pending approval)\n"
            f"Proposal: {UI_PATCH_INTENT}\n"
            f"Route ID: {token.route_id}\n"
            f"Approve with: {token.approval_text_rendered}\n"
            "BOUNDARY: proposal only — nothing changed; no durable memory write; no external action."
        )
    except Exception as exc:
        return (
            "UI SELF-PATCH PROPOSED (broker unavailable, not persisted)\n"
            f"Proposal: {UI_PATCH_INTENT}\n"
            f"(reason: {type(exc).__name__}: {exc})"
        )


# ── Improved timeout fallback ────────────────────────────────────────────────
def improved_fallback(user_text: str = "") -> str:
    return (
        "I heard you. Local cognition timed out, so I am using safe command routing. "
        "I can still help with: /status, /focus, /current-observation, /capabilities, "
        "/self-patch, Evidence Vault, Context Recall, Screenshot Drop. "
        "No durable memory or external action was taken."
    )


# ── The bridge: natural phrase → handler (before any model call) ─────────────
def route_phrase(text: str) -> dict[str, Any] | None:
    """Return {handled, kind, text} for a recognized phrase, else None.

    None means "not a UX alias" — the caller falls through to its normal path.
    """
    n = _norm(text)
    if not n:
        return None
    if n in _EVIDENCE_VAULT:
        return {"handled": True, "kind": "evidence_vault", "text": evidence_vault()}
    if n in _CONTEXT_RECALL:
        return {"handled": True, "kind": "context_recall", "text": context_recall()}
    if n in _UI_PATCH:
        return {"handled": True, "kind": "ui_patch", "text": ui_patch()}
    return None


# ── Smoke test ───────────────────────────────────────────────────────────────
def run_smoke_tests() -> int:
    import tempfile
    failures = 0

    def check(label: str, cond: bool) -> None:
        nonlocal failures
        print(f"  [{'PASS' if cond else 'FAIL'}] {label}")
        if not cond:
            failures += 1

    # Isolate broker writes so /ui-patch doesn't touch the real queue.
    try:
        import pending_actions as pa
        import trusted_build as tb
        tmp = Path(tempfile.mkdtemp())
        pa.PENDING_ACTIONS_PATH = tmp / "pending_actions.jsonl"
        pa.RUN_LOG_PATH = tmp / "run_log.jsonl"
        tb._STATE_FILE = tmp / "tb_state.json"
    except Exception:
        pass

    ev = route_phrase("Show me the Evidence Vault")
    check("'Show me the Evidence Vault' routes without model call",
          ev is not None and ev["kind"] == "evidence_vault" and bool(ev["text"]))

    cr = route_phrase("Context recall")
    check("'Context recall' routes without model call",
          cr is not None and cr["kind"] == "context_recall" and bool(cr["text"]))

    up = route_phrase("improve UI experience")
    check("'improve UI experience' creates/displays a patch proposal",
          up is not None and up["kind"] == "ui_patch"
          and ("UI SELF-PATCH PROPOSED" in up["text"]))

    fb = improved_fallback()
    check("timeout fallback lists useful actions",
          all(s in fb for s in ("/status", "Evidence Vault", "Context Recall", "/capabilities")))
    check("fallback states no durable/external action", "No durable memory or external action" in fb)

    check("unrecognized phrase falls through (returns None)",
          route_phrase("what is the meaning of the ocean") is None)

    # Evidence vault and context recall are pure reads (no exceptions, return text).
    check("evidence_vault returns text", isinstance(evidence_vault(), str) and len(evidence_vault()) > 0)
    check("context_recall returns text", isinstance(context_recall(), str) and len(context_recall()) > 0)

    print(f"\n{'ALL PASS' if failures == 0 else str(failures) + ' FAILURES'}")
    return 0 if failures == 0 else 1


if __name__ == "__main__":
    import sys
    if "--smoke-test" in sys.argv:
        raise SystemExit(run_smoke_tests())
    print(route_phrase("evidence vault"))
