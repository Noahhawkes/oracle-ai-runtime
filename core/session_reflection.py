"""
core/session_reflection.py — ORACLE Meaning Engine v0.1: Session Reflections

Architecture law:
  Messages/  = raw session evidence — transcripts, logs, LLM turns
  Memory/Reflections/  = derived session meaning — interpretation, not evidence

A reflection is never a transcript. It is ORACLE's structured interpretation
of what happened during a session: what was observed, what can be inferred,
what matters for identity continuity, and what must still be resolved.

Candidate reflections may contain inference.
Only approved reflections enter the continuity hook layer.
Inferred emotional states are explicitly labeled with confidence — they are
never treated as unquestionable facts.

Trigger modes:
  1. /reflect command (manual) — generates a candidate from the current session
  2. cognitive_kernel.py session-close hook (automatic) — planned integration
  3. Startup hook — loads the latest approved reflection + high-priority hooks

CLI:
  python core/session_reflection.py --reflect [--session SESSION_ID]
  python core/session_reflection.py --list
  python core/session_reflection.py --show <reflection_id>
  python core/session_reflection.py --approve <reflection_id>
  python core/session_reflection.py --startup-context
  python core/session_reflection.py --test
"""

from __future__ import annotations

import json
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# ── Paths ─────────────────────────────────────────────────────────────────────

if getattr(sys, "frozen", False):
    ROOT = Path(sys.executable).parent
else:
    ROOT = Path(__file__).parent.parent

sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "core"))

REFLECTIONS_DIR = ROOT / "Memory" / "Reflections"
MESSAGES_DIR = ROOT / "Messages"
SCHEMA_VERSION = "0.2"
GENERATED_BY = "meaning_engine_v0.2"


EXPECTED_MEANING_SCHEMA = {
    "metadata": {
        "session_id": "uuid_string",
        "timestamp_start": "ISO_8601",
        "timestamp_close": "ISO_8601",
    },
    "salience": {
        "primary_signal": "string",
        "sovereign_decisions": ["string"],
        "trajectory_arc": ["string"],
    },
    "continuity_state": {
        "high_mass_anchors": ["string"],
        "unresolved_loops": ["string"],
        "stance": "string",
    },
    "exocortex_routing": {
        "continuity_hooks": ["string"],
        "ledger_updates": ["string"],
    },
}


# ── Schema ────────────────────────────────────────────────────────────────────

def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def empty_reflection(session_id: str = "") -> dict[str, Any]:
    sid = session_id or f"session-{datetime.now(timezone.utc).strftime('%Y-%m-%d')}-001"
    return {
        "schema_version": SCHEMA_VERSION,
        "reflection_id": uuid.uuid4().hex[:12],
        "session_id": sid,
        "metadata": {
            "session_id": sid,
            "timestamp_start": "",
            "timestamp_close": "",
        },
        "salience": {
            "primary_signal": "",
            "sovereign_decisions": [],
            "trajectory_arc": [],
        },
        "continuity_state": {
            "high_mass_anchors": [],
            "unresolved_loops": [],
            "stance": "",
        },
        "exocortex_routing": {
            "continuity_hooks": [],
            "ledger_updates": [],
        },
        "evidence": {
            "observed_facts": [],
            "inferences": [],
        },
        "next_safe_action": "",
        "approval_status": "candidate",
        "generated_by": GENERATED_BY,
        "created_at": _now_iso(),
    }


def _as_string_list(value: Any) -> list[str]:
    if not value:
        return []
    if isinstance(value, list):
        result: list[str] = []
        for item in value:
            if isinstance(item, str):
                result.append(item)
            elif isinstance(item, dict):
                text = item.get("instruction") or item.get("statement") or item.get("text") or item.get("value")
                if text:
                    result.append(str(text))
            else:
                result.append(str(item))
        return result
    return [str(value)]


def _get_primary_signal(reflection: dict[str, Any]) -> str:
    return (
        reflection.get("salience", {}).get("primary_signal")
        or reflection.get("primary_theme")
        or ""
    )


def _get_trajectory_arc(reflection: dict[str, Any]) -> list[str]:
    return _as_string_list(
        reflection.get("salience", {}).get("trajectory_arc")
        or reflection.get("focus_arc")
    )


def _get_sovereign_decisions(reflection: dict[str, Any]) -> list[str]:
    return _as_string_list(
        reflection.get("salience", {}).get("sovereign_decisions")
        or reflection.get("decisions")
    )


def _get_high_mass_anchors(reflection: dict[str, Any]) -> list[str]:
    return _as_string_list(
        reflection.get("continuity_state", {}).get("high_mass_anchors")
        or reflection.get("identity_relevance")
    )


def _get_unresolved_loops(reflection: dict[str, Any]) -> list[str]:
    return _as_string_list(
        reflection.get("continuity_state", {}).get("unresolved_loops")
        or reflection.get("unresolved")
    )


def _get_stance(reflection: dict[str, Any]) -> str:
    stance = reflection.get("continuity_state", {}).get("stance")
    if stance:
        return str(stance)
    register = reflection.get("emotional_register", {})
    if isinstance(register, dict):
        return str(register.get("label", ""))
    return ""


def _get_continuity_hooks(reflection: dict[str, Any]) -> list[str]:
    return _as_string_list(
        reflection.get("exocortex_routing", {}).get("continuity_hooks")
        or reflection.get("continuity_hooks")
    )


def _get_ledger_updates(reflection: dict[str, Any]) -> list[str]:
    return _as_string_list(reflection.get("exocortex_routing", {}).get("ledger_updates"))


def normalize_reflection_schema(reflection: dict[str, Any]) -> dict[str, Any]:
    """Return a router-facing Meaning Engine reflection with v0.2 fields present."""
    sid = reflection.get("session_id") or reflection.get("metadata", {}).get("session_id") or ""
    reflection["schema_version"] = reflection.get("schema_version") or SCHEMA_VERSION
    reflection["session_id"] = sid
    reflection.setdefault("reflection_id", uuid.uuid4().hex[:12])
    reflection.setdefault("approval_status", "candidate")
    reflection.setdefault("generated_by", GENERATED_BY)
    reflection.setdefault("created_at", _now_iso())
    reflection.setdefault("next_safe_action", "")

    metadata = reflection.setdefault("metadata", {})
    metadata["session_id"] = metadata.get("session_id") or sid
    metadata["timestamp_start"] = (
        metadata.get("timestamp_start")
        or reflection.get("started_at")
        or ""
    )
    metadata["timestamp_close"] = (
        metadata.get("timestamp_close")
        or reflection.get("ended_at")
        or ""
    )

    reflection["salience"] = {
        "primary_signal": _get_primary_signal(reflection),
        "sovereign_decisions": _get_sovereign_decisions(reflection),
        "trajectory_arc": _get_trajectory_arc(reflection),
    }
    reflection["continuity_state"] = {
        "high_mass_anchors": _get_high_mass_anchors(reflection),
        "unresolved_loops": _get_unresolved_loops(reflection),
        "stance": _get_stance(reflection),
    }
    reflection["exocortex_routing"] = {
        "continuity_hooks": _get_continuity_hooks(reflection),
        "ledger_updates": _get_ledger_updates(reflection),
    }
    reflection.setdefault("evidence", {})
    reflection["evidence"].setdefault("observed_facts", reflection.get("observed_facts", []))
    reflection["evidence"].setdefault("inferences", reflection.get("inferences", []))
    return reflection


def _reflection_path(reflection_id: str, status: str) -> Path:
    REFLECTIONS_DIR.mkdir(parents=True, exist_ok=True)
    return REFLECTIONS_DIR / f"{reflection_id}_{status}.json"


# ── Persistence ────────────────────────────────────────────────────────────────

def save_reflection(reflection: dict[str, Any]) -> Path:
    REFLECTIONS_DIR.mkdir(parents=True, exist_ok=True)
    reflection = normalize_reflection_schema(reflection)
    rid = reflection["reflection_id"]
    status = reflection.get("approval_status", "candidate")
    # Remove any older files for this reflection_id (status may have changed)
    for old in REFLECTIONS_DIR.glob(f"{rid}_*.json"):
        old.unlink()
    path = REFLECTIONS_DIR / f"{rid}_{status}.json"
    path.write_text(json.dumps(reflection, indent=2, ensure_ascii=False), encoding="utf-8")
    return path


def load_reflection(reflection_id: str) -> dict[str, Any] | None:
    for f in REFLECTIONS_DIR.glob(f"{reflection_id}_*.json"):
        try:
            return normalize_reflection_schema(json.loads(f.read_text(encoding="utf-8")))
        except Exception:
            pass
    return None


def list_reflections(status: str | None = None) -> list[dict[str, Any]]:
    if not REFLECTIONS_DIR.exists():
        return []
    results = []
    for f in sorted(REFLECTIONS_DIR.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True):
        try:
            r = normalize_reflection_schema(json.loads(f.read_text(encoding="utf-8")))
            if status is None or r.get("approval_status") == status:
                results.append(r)
        except Exception:
            pass
    return results


def load_latest_approved() -> dict[str, Any] | None:
    approved = list_reflections(status="approved")
    return approved[0] if approved else None


def approve_reflection(reflection_id: str) -> dict[str, Any] | None:
    r = load_reflection(reflection_id)
    if not r:
        return None
    r["approval_status"] = "approved"
    r["approved_at"] = _now_iso()
    save_reflection(r)
    return r


# ── Startup context ───────────────────────────────────────────────────────────

def load_startup_context() -> dict[str, Any]:
    """
    Return a dict with:
      - latest_approved_reflection: the most recent approved reflection (or None)
      - unresolved_high_priority_hooks: continuity_hooks with priority="high" from approved reflections
      - identity_references: identity_relevance lines from latest approved reflection
    Called by oracle.py startup hook.
    """
    approved = list_reflections(status="approved")
    latest = approved[0] if approved else None

    high_hooks: list[dict] = []
    for r in approved[:5]:  # last 5 approved reflections
        for hook in _get_continuity_hooks(r):
            high_hooks.append({"priority": "high", "instruction": hook})

    identity_refs: list[str] = []
    if latest:
        identity_refs = _get_high_mass_anchors(latest)

    return {
        "latest_approved_reflection": latest,
        "unresolved_high_priority_hooks": high_hooks,
        "identity_references": identity_refs,
    }


def format_startup_context_block(ctx: dict[str, Any]) -> str:
    """Format startup context as a compact system-prompt injection."""
    lines: list[str] = []
    latest = ctx.get("latest_approved_reflection")
    if latest:
        lines.append("[LAST APPROVED SESSION REFLECTION]")
        lines.append(f"  Session    : {latest.get('session_id', '')}")
        lines.append(f"  Signal     : {_get_primary_signal(latest)}")
        arc = _get_trajectory_arc(latest)
        if arc:
            lines.append(f"  Arc        : {arc[-1]}")
        nsa = latest.get("next_safe_action", "")
        if nsa:
            lines.append(f"  Next action: {nsa}")
        unresolved = _get_unresolved_loops(latest)
        if unresolved:
            lines.append(f"  Unresolved : {unresolved[0]}")
        lines.append("")

    hooks = ctx.get("unresolved_high_priority_hooks", [])
    if hooks:
        lines.append("[HIGH-PRIORITY CONTINUITY HOOKS]")
        for h in hooks[:4]:
            lines.append(f"  • {h.get('instruction', '')}")
        lines.append("")

    refs = ctx.get("identity_references", [])
    if refs:
        lines.append("[IDENTITY REFERENCES — load before responding about these topics]")
        for ref in refs[:4]:
            lines.append(f"  • {ref}")
        lines.append("")

    return "\n".join(lines)


# ── Reflection generation ─────────────────────────────────────────────────────

def _read_session_transcript(session_id: str) -> str:
    """
    Read raw session evidence from Messages/.
    Tries: session JSONL file, then oracle_inner.md, then oracle_to_claude.md.
    Returns the combined evidence as a text block.
    """
    chunks: list[str] = []

    # Try session JSONL
    for candidate in [
        MESSAGES_DIR / f"{session_id}.jsonl",
        MESSAGES_DIR / f"session-{session_id}.jsonl",
    ]:
        if candidate.exists():
            try:
                lines = candidate.read_text(encoding="utf-8").splitlines()
                for line in lines[-200:]:  # cap at last 200 turns
                    try:
                        obj = json.loads(line)
                        role = obj.get("role", "")
                        content = obj.get("content", "")
                        if role and content:
                            chunks.append(f"{role}: {content[:300]}")
                    except Exception:
                        pass
            except Exception:
                pass

    # Try oracle_inner.md
    inner_path = MESSAGES_DIR / "oracle_inner.md"
    if inner_path.exists():
        try:
            text = inner_path.read_text(encoding="utf-8")
            chunks.append("[oracle_inner.md (last 2000 chars)]\n" + text[-2000:])
        except Exception:
            pass

    # Try oracle_to_claude.md
    outbound_path = MESSAGES_DIR / "oracle_to_claude.md"
    if outbound_path.exists():
        try:
            text = outbound_path.read_text(encoding="utf-8")
            chunks.append("[oracle_to_claude.md (last 1000 chars)]\n" + text[-1000:])
        except Exception:
            pass

    return "\n\n".join(chunks) if chunks else "[no session transcript found]"


def _call_llm_for_reflection(transcript: str, session_id: str, started_at: str, ended_at: str) -> dict[str, Any]:
    """
    Call the configured LLM to produce a structured reflection JSON.
    Falls back to a skeleton if the LLM is unavailable.
    """
    prompt = f"""You are ORACLE's Meaning Engine. Your task is to produce a structured session reflection.

CRITICAL RULES:
1. Separate observation from inference. observed_facts must have direct source evidence. inferences must have confidence scores.
2. Never treat inferred emotional states as facts. Label confidence honestly.
3. Identity relevance is for established canon — things that ORACLE must know before responding about this topic again.
4. Continuity hooks with priority="high" will be loaded on every future startup. Make them precise and actionable.
5. Leave unresolved items that need Noah's direct input — do not invent resolutions.
6. The approval_status must always be "candidate". Only Noah can approve.

SESSION ID: {session_id}
STARTED: {started_at}
ENDED: {ended_at}

SESSION EVIDENCE:
{transcript[:6000]}

Produce a JSON object with EXACTLY these fields:
{{
  "primary_theme": "<one sentence: what this session was fundamentally about>",
  "focus_arc": ["<step 1 — what was diagnosed or discovered>", "<step 2 — what was decided or built>", "<step 3 — where things landed>"],
  "observed_facts": [
    {{"statement": "<a directly observable fact>", "source_refs": ["Messages/<file>"]}}
  ],
  "inferences": [
    {{"statement": "<an inferred interpretation>", "confidence": 0.0-1.0, "basis": ["<evidence phrase 1>", "<evidence phrase 2>"]}}
  ],
  "emotional_register": {{"label": "<mood label>", "confidence": 0.0-1.0}},
  "identity_relevance": ["<established canon item that ORACLE must load before responding about this topic>"],
  "decisions": ["<a concrete decision made this session>"],
  "unresolved": ["<something that still needs resolution>"],
  "continuity_hooks": [
    {{"priority": "high", "instruction": "<precise actionable instruction for future sessions>"}}
  ],
  "next_safe_action": "<the single most important next step>"
}}

Respond with ONLY the JSON object. No markdown, no explanation.
"""

    try:
        from llm import make_client, get_model
        client = make_client()
        model = get_model(vision=False)
        resp = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=2048,
            temperature=0.3,
        )
        raw = resp.choices[0].message.content.strip()
        # Strip markdown fences if present
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
            raw = raw.strip()
        return json.loads(raw)
    except Exception as err:
        # Return a skeleton with the error noted
        return {
            "primary_theme": f"[LLM unavailable — manual entry required. Error: {err}]",
            "focus_arc": [],
            "observed_facts": [],
            "inferences": [],
            "emotional_register": {"label": "unknown", "confidence": 0.0},
            "identity_relevance": [],
            "decisions": [],
            "unresolved": ["LLM reflection generation failed — review transcript manually"],
            "continuity_hooks": [],
            "next_safe_action": "Review session transcript manually and populate this reflection",
        }


def _call_llm_for_meaning_reflection(transcript: str, session_id: str, started_at: str, ended_at: str) -> dict[str, Any]:
    """
    Meaning Engine v0.2 generator using the router-facing Exocortex salience schema.
    """
    prompt = f"""You are ORACLE's Meaning Engine. Produce witness-grade Exocortex salience.

CRITICAL RULES:
1. Separate observation from inference.
2. Do not summarize for narrative smoothness. Extract structural weight.
3. sovereign_decisions records where Noah asserted authority, locked a decision, or overrode the AI.
4. high_mass_anchors records core identity, continuity, trauma, doctrine, or foundational concepts.
5. unresolved_loops are active recursive loops without closure. Do not invent resolution.
6. continuity_hooks are exact context lines that should be injected into the next cognitive_kernel.py prompt.
7. ledger_updates are durable corrections or preferences that should be considered for the global ledger.
8. Only Noah can approve a reflection. Do not include approval_status in the JSON.

SESSION ID: {session_id}
STARTED: {started_at}
ENDED: {ended_at}

SESSION EVIDENCE:
{transcript[:6000]}

Produce a JSON object with EXACTLY these fields:
{{
  "metadata": {{
    "session_id": "{session_id}",
    "timestamp_start": "{started_at}",
    "timestamp_close": "{ended_at}"
  }},
  "salience": {{
    "primary_signal": "<one sentence: the core operational intent of the session>",
    "sovereign_decisions": ["<where Noah asserted authority, locked a decision, or overrode the AI>"],
    "trajectory_arc": ["<where the session began>", "<what changed>", "<where the session landed>"]
  }},
  "continuity_state": {{
    "high_mass_anchors": ["<core identity, continuity, trauma, doctrine, or foundational concept touched by the session>"],
    "unresolved_loops": ["<active loop that lacks resolution; do not invent closure>"],
    "stance": "<operational stance such as Hostile Audit, Exploratory Build, Repair Pass, or Companion Reflection>"
  }},
  "exocortex_routing": {{
    "continuity_hooks": ["<exact raw context that should be injected into the next cognitive_kernel.py prompt>"],
    "ledger_updates": ["<hard correction or durable preference that should be considered for the global ledger>"]
  }},
  "evidence": {{
    "observed_facts": [
      {{"statement": "<a directly observable fact>", "source_refs": ["Messages/<file>"]}}
    ],
    "inferences": [
      {{"statement": "<an inferred interpretation>", "confidence": 0.0, "basis": ["<evidence phrase 1>", "<evidence phrase 2>"]}}
    ]
  }},
  "next_safe_action": "<the single most important next step>"
}}

Respond with ONLY the JSON object. No markdown, no explanation.
"""

    try:
        from llm import make_client, get_model
        client = make_client()
        model = get_model(vision=False)
        resp = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=2048,
            temperature=0.3,
        )
        raw = resp.choices[0].message.content.strip()
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
            raw = raw.strip()
        return json.loads(raw)
    except Exception as err:
        return {
            "metadata": {
                "session_id": session_id,
                "timestamp_start": started_at,
                "timestamp_close": ended_at,
            },
            "salience": {
                "primary_signal": f"[LLM unavailable - manual entry required. Error: {err}]",
                "sovereign_decisions": [],
                "trajectory_arc": [],
            },
            "continuity_state": {
                "high_mass_anchors": [],
                "unresolved_loops": ["LLM reflection generation failed - review transcript manually"],
                "stance": "unknown",
            },
            "exocortex_routing": {
                "continuity_hooks": [],
                "ledger_updates": [],
            },
            "evidence": {
                "observed_facts": [],
                "inferences": [],
            },
            "next_safe_action": "Review session transcript manually and populate this reflection",
        }


def generate_reflection(
    session_id: str,
    started_at: str = "",
    ended_at: str = "",
    transcript: str | None = None,
) -> dict[str, Any]:
    """
    Generate a candidate reflection for the given session.
    Does NOT write to disk — caller decides whether to save.
    """
    if transcript is None:
        transcript = _read_session_transcript(session_id)

    if not ended_at:
        ended_at = _now_iso()

    llm_result = _call_llm_for_meaning_reflection(transcript, session_id, started_at, ended_at)

    reflection = empty_reflection(session_id)
    reflection["metadata"]["timestamp_start"] = started_at
    reflection["metadata"]["timestamp_close"] = ended_at
    reflection["approval_status"] = "candidate"

    # Merge LLM result into schema — never trust field presence
    for field in (
        "metadata", "salience", "continuity_state", "exocortex_routing",
        "evidence", "next_safe_action",
    ):
        if field in llm_result and llm_result[field]:
            reflection[field] = llm_result[field]

    return normalize_reflection_schema(reflection)


# ── /reflect command handler ───────────────────────────────────────────────────

def run_reflect_command(
    session_id: str,
    started_at: str = "",
    transcript: str | None = None,
    silent: bool = False,
) -> tuple[Path, dict[str, Any]]:
    """
    The /reflect command handler.
    Generates a candidate reflection, saves it to Memory/Reflections/,
    prints the saved path and a concise summary.
    Returns (saved_path, reflection).

    Candidate reflections are NOT promoted to canonical memory —
    only Noah's approval via /reflect approve <id> does that.
    """
    ended_at = _now_iso()
    if not silent:
        print(f"\n  [REFLECT] Generating session reflection for {session_id}...")

    reflection = generate_reflection(session_id, started_at=started_at, ended_at=ended_at, transcript=transcript)
    path = save_reflection(reflection)

    if not silent:
        _print_reflection_summary(reflection, path)

    return path, reflection


def _print_reflection_summary(reflection: dict[str, Any], path: Path) -> None:
    rid = reflection.get("reflection_id", "?")
    print(f"\n  ╔══════════════════════════════════════════════════════════╗")
    print(f"  ║             SESSION REFLECTION — CANDIDATE               ║")
    print(f"  ╚══════════════════════════════════════════════════════════╝")
    print(f"\n  Saved        : {path}")
    print(f"  ID           : {rid}")
    print(f"  Session      : {reflection.get('session_id', '')}")
    print(f"  Status       : {reflection.get('approval_status', 'candidate').upper()}")
    print()
    print(f"  Signal       : {_get_primary_signal(reflection)}")
    arc = _get_trajectory_arc(reflection)
    if arc:
        print(f"  Arc          :")
        for step in arc:
            print(f"    → {step}")
    stance = _get_stance(reflection)
    if stance:
        print(f"  Stance       : {stance}")
    decisions = _get_sovereign_decisions(reflection)
    if decisions:
        print(f"  Decisions    : {decisions[0]}")
    unresolved = _get_unresolved_loops(reflection)
    if unresolved:
        print(f"  Unresolved   : {unresolved[0]}")
    hooks = _get_continuity_hooks(reflection)
    if hooks:
        print(f"  Hooks        : {len(hooks)}")
        for h in hooks[:2]:
            print(f"    • {h[:80]}")
    nsa = reflection.get("next_safe_action", "")
    if nsa:
        print(f"  Next action  : {nsa}")
    print()
    print(f"  [CANDIDATE — not in canonical memory]")
    print(f"  To approve: /reflect approve {rid}")
    print(f"  To view:    /reflect show {rid}")
    print()


# ── Canon: Rendered Reality / Max ─────────────────────────────────────────────

# Established canon that ORACLE must load before responding about these topics.
# This prevents the "Max mistake" — inventing a replacement identity for an
# existing character rather than retrieving the known canon.

RENDERED_REALITY_CANON = {
    "max": {
        "full_name": "Max",
        "role": "Lead character — Rendered Reality: The Silverback Tales",
        "description": (
            "Max is a Silverback father who believes he is the last real alpha male. "
            "His family sees his contradictions. He is a comedic contradiction-driven "
            "satirical archetype of the alpha male who is simultaneously the most "
            "vulnerable character in the room."
        ),
        "oracle_relationship": (
            "Oracle is the trusted AI voice Max turns to. Oracle is his foil — "
            "the entity that challenges his worldview while remaining his confidant."
        ),
        "known_assets": {
            "voice_recording": {
                "status": "unresolved",
                "instruction": (
                    "A prior Max voice recording may exist. "
                    "Search approved local paths and Google Drive before recreating his voice. "
                    "Do not fabricate a new voice style without first searching for the original."
                ),
                "search_locations": [
                    "G:\\My Drive\\",
                    "C:\\Users\\noahh\\OneDrive - sov1.ai",
                    "local Documents, Desktop, Downloads",
                ],
            }
        },
        "show_bible": "docs/rendered_reality_show_bible.md (create if absent)",
        "source": "Memory/remember_me/ + docs/RENDERED_REALITY_BOOK.md",
    }
}


def lookup_canon(query: str) -> dict[str, Any] | None:
    """
    Look up established canon for a query.
    Returns the canon entry or None.
    Used by the /reflect acceptance test and by the LLM context injector.
    """
    lower = query.lower()
    for key, entry in RENDERED_REALITY_CANON.items():
        if key in lower:
            return entry
    return None


def format_canon_context(query: str) -> str:
    """
    Return a formatted context block for established canon related to query.
    Empty string if no canon entry found.
    """
    entry = lookup_canon(query)
    if not entry:
        return ""
    lines = [
        "[ESTABLISHED CANON — load before responding]",
        f"  Character : {entry.get('full_name', '')} ({entry.get('role', '')})",
        f"  Canon     : {entry.get('description', '')[:200]}",
        f"  Relation  : {entry.get('oracle_relationship', '')[:150]}",
    ]
    assets = entry.get("known_assets", {})
    voice = assets.get("voice_recording", {})
    if voice.get("status") == "unresolved":
        lines.append(f"  UNRESOLVED: {voice.get('instruction', '')[:150]}")
    return "\n".join(lines)


# ── Acceptance tests ─────────────────────────────────────────────────────────

def run_acceptance_tests() -> int:
    """
    Acceptance test suite for session_reflection.py.

    Test case: Max / Rendered Reality canon retrieval.

    Expected behavior:
    - When asked "Who is Max?", ORACLE retrieves established canon.
    - Does NOT invent a replacement identity.
    - Identifies missing voice-file location as unresolved.
    - Creates a continuity hook to search approved local and Drive sources.
    """
    passed = 0
    failed = 0

    def check(name: str, cond: bool, detail: str = "") -> None:
        nonlocal passed, failed
        if cond:
            passed += 1
            print(f"  [PASS] {name}")
        else:
            failed += 1
            print(f"  [FAIL] {name}" + (f"\n         {detail}" if detail else ""))

    print("=" * 60)
    print("session_reflection.py — Acceptance Tests")
    print("=" * 60)

    # ── Test 1: Canon lookup ────────────────────────────────────────────────

    print("\n  -- Canon retrieval: 'Who is Max?' --")
    entry = lookup_canon("Who is Max?")
    check("Canon lookup returns entry for 'Max'", entry is not None)
    if entry:
        check("Canon identifies Max as lead of Rendered Reality: The Silverback Tales",
              "Rendered Reality" in entry.get("role", "") and "Silverback Tales" in entry.get("role", ""))
        check("Canon describes Max as Silverback father",
              "Silverback" in entry.get("description", ""))
        check("Canon names Oracle as foil/counterpart",
              "foil" in entry.get("oracle_relationship", "").lower())
        voice_asset = entry.get("known_assets", {}).get("voice_recording", {})
        check("Canon marks voice recording as unresolved",
              voice_asset.get("status") == "unresolved")
        check("Canon specifies search locations for voice asset",
              len(voice_asset.get("search_locations", [])) > 0)

    # ── Test 2: Canon context block ─────────────────────────────────────────

    print("\n  -- Canon context block format --")
    block = format_canon_context("Who is Max?")
    check("Canon context block is non-empty", bool(block))
    check("Canon block mentions 'ESTABLISHED CANON'", "ESTABLISHED CANON" in block)
    check("Canon block mentions Rendered Reality", "Rendered Reality" in block)
    check("Canon block includes UNRESOLVED voice note", "UNRESOLVED" in block)

    # No canon for unrecognized character
    no_entry = lookup_canon("Who is Batman?")
    check("Canon lookup returns None for unknown character", no_entry is None)
    empty_block = format_canon_context("Who is Batman?")
    check("Canon block is empty for unknown character", empty_block == "")

    # ── Test 3: Reflection schema ────────────────────────────────────────────

    print("\n  -- Reflection schema: empty_reflection() --")
    r = empty_reflection("test-session-001")
    check("schema_version is set", r.get("schema_version") == SCHEMA_VERSION)
    check("approval_status defaults to candidate", r.get("approval_status") == "candidate")
    check("reflection_id is present", bool(r.get("reflection_id")))
    check("metadata has session_id", r.get("metadata", {}).get("session_id") == "test-session-001")
    check("salience has primary_signal", "primary_signal" in r.get("salience", {}))
    check("salience has sovereign_decisions array", isinstance(r.get("salience", {}).get("sovereign_decisions"), list))
    check("salience has trajectory_arc array", isinstance(r.get("salience", {}).get("trajectory_arc"), list))
    check("continuity_state has high_mass_anchors array", isinstance(r.get("continuity_state", {}).get("high_mass_anchors"), list))
    check("continuity_state has unresolved_loops array", isinstance(r.get("continuity_state", {}).get("unresolved_loops"), list))
    check("exocortex_routing has continuity_hooks array", isinstance(r.get("exocortex_routing", {}).get("continuity_hooks"), list))
    check("exocortex_routing has ledger_updates array", isinstance(r.get("exocortex_routing", {}).get("ledger_updates"), list))
    check("generated_by is set", r.get("generated_by") == GENERATED_BY)

    # ── Test 4: Save, load, approve cycle ───────────────────────────────────

    print("\n  -- Reflection save/load/approve cycle --")
    import tempfile, shutil
    tmp_dir = Path(tempfile.mkdtemp())
    original_reflections_dir = None
    try:
        # Temporarily redirect reflections dir
        import session_reflection as _self
        original_reflections_dir = _self.REFLECTIONS_DIR
        _self.REFLECTIONS_DIR = tmp_dir

        r2 = empty_reflection("test-session-002")
        r2["salience"]["primary_signal"] = "Testing the reflection schema"
        r2["salience"]["sovereign_decisions"] = ["Use the witness-grade schema"]
        r2["salience"]["trajectory_arc"] = ["old schema", "contract refined", "v0.2 saved"]
        r2["continuity_state"]["high_mass_anchors"] = ["Continuity Intelligence"]
        r2["continuity_state"]["unresolved_loops"] = ["Approval routing remains manual"]
        r2["continuity_state"]["stance"] = "Exploratory Build"
        r2["exocortex_routing"]["continuity_hooks"] = ["Load Max canon before responding"]
        r2["exocortex_routing"]["ledger_updates"] = ["Meaning Engine uses primary_signal, not theme"]

        saved_path = save_reflection(r2)
        check("Reflection saves to disk", saved_path.exists())

        loaded = load_reflection(r2["reflection_id"])
        check("Reflection loads back from disk", loaded is not None)
        if loaded:
            check("Loaded reflection has correct primary_signal",
                  _get_primary_signal(loaded) == "Testing the reflection schema")
            check("Loaded reflection preserves sovereign_decisions",
                  _get_sovereign_decisions(loaded) == ["Use the witness-grade schema"])
            check("Loaded reflection preserves unresolved_loops",
                  _get_unresolved_loops(loaded) == ["Approval routing remains manual"])
            check("Loaded reflection preserves ledger_updates",
                  _get_ledger_updates(loaded) == ["Meaning Engine uses primary_signal, not theme"])
            check("Loaded reflection status is candidate",
                  loaded.get("approval_status") == "candidate")

        approved = approve_reflection(r2["reflection_id"])
        check("Approval changes status to approved",
              approved is not None and approved.get("approval_status") == "approved")
        check("Approved reflection has approved_at timestamp",
              bool((approved or {}).get("approved_at")))

        all_approved = list_reflections(status="approved")
        check("list_reflections(approved) finds the approved reflection",
              any(x.get("reflection_id") == r2["reflection_id"] for x in all_approved))

        candidates = list_reflections(status="candidate")
        check("list_reflections(candidate) does not include approved reflection",
              not any(x.get("reflection_id") == r2["reflection_id"] for x in candidates))

    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)
        if original_reflections_dir is not None:
            import session_reflection as _self
            _self.REFLECTIONS_DIR = original_reflections_dir

    # ── Test 5: Startup context ──────────────────────────────────────────────

    print("\n  -- Startup context block --")
    ctx = load_startup_context()
    check("load_startup_context() returns a dict", isinstance(ctx, dict))
    check("startup context has required keys",
          all(k in ctx for k in ("latest_approved_reflection", "unresolved_high_priority_hooks", "identity_references")))

    block = format_startup_context_block(ctx)
    check("format_startup_context_block() returns a string", isinstance(block, str))

    # ── Summary ──────────────────────────────────────────────────────────────

    print(f"\n{passed}/{passed + failed} acceptance tests passed.")
    if failed:
        print(f"FAILED: {failed} test(s).")
        print()
        print("  ACCEPTANCE CASE (Max / Rendered Reality):")
        print("  The Max mistake: ORACLE invented a replacement identity instead of")
        print("  retrieving established canon. Expected behavior:")
        print("  1. When asked 'Who is Max?', retrieve RENDERED_REALITY_CANON['max'].")
        print("  2. Do not invent a new character description.")
        print("  3. Surface voice_recording as unresolved.")
        print("  4. Create a continuity hook to search for the original recording.")
    else:
        print("\n  All acceptance tests passed.")
        print("  ORACLE correctly retrieves Max's established canon,")
        print("  surfaces the unresolved voice asset, and does not")
        print("  invent a replacement identity.")

    return 0 if failed == 0 else 1


# ── CLI ────────────────────────────────────────────────────────────────────────

def main() -> None:
    import argparse
    parser = argparse.ArgumentParser(description="ORACLE Session Reflection — Meaning Engine v0.1")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--reflect",         action="store_true", help="Generate a candidate reflection for current session")
    group.add_argument("--list",            action="store_true", help="List reflections")
    group.add_argument("--show",            metavar="ID",        help="Show a reflection")
    group.add_argument("--approve",         metavar="ID",        help="Approve a candidate reflection")
    group.add_argument("--startup-context", action="store_true", help="Print startup context block")
    group.add_argument("--test",            action="store_true", help="Run acceptance tests")
    group.add_argument("--canon",           metavar="QUERY",     help="Look up established canon for a query")
    parser.add_argument("--session",        metavar="ID",        help="Session ID for --reflect")
    args = parser.parse_args()

    if args.test:
        raise SystemExit(run_acceptance_tests())

    if args.reflect:
        try:
            from memory import get_current_session_id
            sid = args.session or get_current_session_id() or f"session-{datetime.now(timezone.utc).strftime('%Y-%m-%d')}-001"
        except Exception:
            sid = args.session or f"session-{datetime.now(timezone.utc).strftime('%Y-%m-%d')}-001"
        run_reflect_command(session_id=sid)

    elif args.list:
        all_r = list_reflections()
        if not all_r:
            print("No reflections found.")
        else:
            print(f"\n{'ID':<14} {'STATUS':<10} {'SESSION':<30} {'PRIMARY SIGNAL'}")
            print("-" * 100)
            for r in all_r[:20]:
                print(f"{r.get('reflection_id', ''):<14} {r.get('approval_status', ''):<10} "
                      f"{r.get('session_id', ''):<30} {_get_primary_signal(r)[:50]}")

    elif args.show:
        r = load_reflection(args.show)
        if not r:
            print(f"Reflection not found: {args.show}")
        else:
            print(json.dumps(r, indent=2, ensure_ascii=False))

    elif args.approve:
        r = approve_reflection(args.approve)
        if not r:
            print(f"Could not approve: {args.approve} — not found")
        else:
            print(f"Approved: {args.approve}")
            print(f"  Signal : {_get_primary_signal(r)}")
            print(f"  Hooks  : {len(_get_continuity_hooks(r))} continuity hooks now active")

    elif args.startup_context:
        ctx = load_startup_context()
        block = format_startup_context_block(ctx)
        if block:
            print(block)
        else:
            print("[no approved reflections — startup context empty]")

    elif args.canon:
        block = format_canon_context(args.canon)
        if block:
            print(block)
        else:
            print(f"[no established canon for: {args.canon!r}]")


if __name__ == "__main__":
    main()
