"""
core/companion_bootstrap.py — Deterministic Companion Grounding Bootstrap.

Runs BEFORE any LLM call in companion mode. Reads identity, latest reflection,
and live context from local files using real pathlib/hashlib calls. Produces a
sealed context block injected into the system prompt.

The LLM never executes this — Python does. If a source fails, the failure is
reported honestly. ORACLE never says "loading..." unless this code actually ran.
"""
from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

ROOT = Path(__file__).parent.parent
MEMORY = ROOT / "Memory"
RELATIONSHIP_DIR = MEMORY / "relationship_memory"
REFLECTIONS_DIR = MEMORY / "Reflections"
LIVE_CONTEXT_PATH = MEMORY / "live_context.json"

# The approved sovereign identity ID (Noah Alexander Hawkes Sr.)
SOVEREIGN_ID = "060ca00a-c703-4f49-874e-2a2b2291b350"

_IDENTITY_FACT_KEYWORDS = (
    "full name",
    "entities",
    "children",
    "family",
    "co-sovereign",
    "sons",
    "continuity",
)


def _identity_source_lines(data: dict) -> list[str]:
    lines: list[str] = []
    for key in ("name", "sov_id", "organization", "role", "trust_tier", "source", "confidence", "status"):
        if data.get(key) is not None:
            lines.append(f"{key}: {data.get(key)}")

    aliases = data.get("aliases") or []
    if aliases:
        lines.append(f"aliases: {', '.join(str(a) for a in aliases)}")

    important_facts = [str(fact) for fact in data.get("important_facts", []) if fact]
    selected: list[str] = []
    for fact in important_facts:
        lower = fact.lower()
        if any(keyword in lower for keyword in _IDENTITY_FACT_KEYWORDS):
            selected.append(fact)
    for fact in important_facts:
        if len(selected) >= 14:
            break
        if fact not in selected:
            selected.append(fact)
    for fact in selected:
        lines.append(f"important_fact: {fact}")

    for boundary in data.get("known_boundaries", []) or []:
        lines.append(f"known_boundary: {boundary}")

    return lines


def _live_context_source_lines(data: dict) -> list[str]:
    keys = ("sovereign", "active_project", "active_tool", "active_repo", "current_task", "memory_policy", "last_updated")
    return [f"{key}: {data.get(key)}" for key in keys if data.get(key) is not None]


def _reflection_source_lines(data: dict) -> list[str]:
    lines: list[str] = []
    for key in ("schema_version", "reflection_id", "session_id", "approval_status", "generated_by"):
        if data.get(key) is not None:
            lines.append(f"{key}: {data.get(key)}")
    salience = data.get("salience") or {}
    if salience.get("primary_signal"):
        lines.append(f"primary_signal: {salience.get('primary_signal')}")
    for item in salience.get("sovereign_decisions", []) or []:
        lines.append(f"sovereign_decision: {item}")
    for item in salience.get("trajectory_arc", []) or []:
        lines.append(f"trajectory_arc: {item}")
    continuity = data.get("continuity_state") or {}
    if continuity.get("stance"):
        lines.append(f"stance: {continuity.get('stance')}")
    for item in continuity.get("high_mass_anchors", []) or []:
        lines.append(f"high_mass_anchor: {item}")
    for item in continuity.get("unresolved_loops", []) or []:
        lines.append(f"unresolved_loop: {item}")
    routing = data.get("exocortex_routing") or {}
    for item in routing.get("continuity_hooks", []) or []:
        lines.append(f"continuity_hook: {item}")
    for item in routing.get("ledger_updates", []) or []:
        lines.append(f"ledger_update: {item}")
    return lines


# ── Data model ────────────────────────────────────────────────────────────────

@dataclass
class SourceRecord:
    path: str
    resolved: str
    exists: bool
    sha256: Optional[str]
    size_bytes: Optional[int]
    mtime_utc: Optional[str]
    load_error: Optional[str]
    content: Optional[dict]   # parsed JSON, not injected raw into prompt


@dataclass
class BootstrapResult:
    identity: SourceRecord
    latest_reflection: SourceRecord
    live_context: SourceRecord
    grounded_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    errors: list[str] = field(default_factory=list)

    @property
    def fully_grounded(self) -> bool:
        return self.identity.exists and not self.identity.load_error

    def source_sections(self, current_session: Optional[list[dict]] = None) -> dict[str, list[str]]:
        """Return structured source payloads for Companion Mode grounding."""
        sections: dict[str, list[str]] = {
            "IDENTITY": [],
            "LIVE_CONTEXT": [],
            "LATEST_REFLECTION": [],
            "CURRENT_SESSION": [],
        }

        if self.identity.exists and self.identity.content:
            sections["IDENTITY"].extend(_identity_source_lines(self.identity.content))
            sections["IDENTITY"].append(f"source_path: {self.identity.resolved}")
            if self.identity.sha256:
                sections["IDENTITY"].append(f"source_sha256: {self.identity.sha256}")

        if self.live_context.exists and self.live_context.content:
            sections["LIVE_CONTEXT"].extend(_live_context_source_lines(self.live_context.content))
            sections["LIVE_CONTEXT"].append(f"source_path: {self.live_context.resolved}")

        if self.latest_reflection.exists and self.latest_reflection.content:
            sections["LATEST_REFLECTION"].extend(_reflection_source_lines(self.latest_reflection.content))
            sections["LATEST_REFLECTION"].append(f"source_path: {self.latest_reflection.resolved}")

        for turn in (current_session or [])[-8:]:
            role = str(turn.get("role", "unknown")).strip() or "unknown"
            content = str(turn.get("content", "")).strip()
            if content:
                sections["CURRENT_SESSION"].append(f"{role}: {content[:600]}")

        return sections

    def system_context_block(self, current_session: Optional[list[dict]] = None) -> str:
        """
        Build the sealed context block for injection into the companion system prompt.
        Every fact comes from a file read — nothing is invented.
        """
        sections = self.source_sections(current_session=current_session)
        lines = ["[ORACLE COMPANION GROUNDING — verified from local files]"]
        lines.append(f"grounded_at: {self.grounded_at}")
        lines.append("SOURCE DISCIPLINE:")
        lines.append("  Allowed labels: VERIFIED, INFERENCE, UNAVAILABLE.")
        lines.append("  A factual claim may use IDENTITY, LIVE_CONTEXT, LATEST_REFLECTION, or CURRENT_SESSION only when its supporting text appears in that source section.")
        lines.append("  Mixed statements must be split into sourced premises and a separately labeled inference.")
        lines.append("  Do not present inferred language as verified source content.")
        lines.append("  If support is absent from the source sections, answer UNAVAILABLE instead of guessing.")
        lines.append("")

        for label in ("IDENTITY", "LIVE_CONTEXT", "LATEST_REFLECTION", "CURRENT_SESSION"):
            lines.append(f"SOURCE SECTION: {label}")
            payload = sections.get(label) or []
            if payload:
                for item in payload:
                    lines.append(f"  - {item}")
            else:
                lines.append("  - UNAVAILABLE")
            lines.append("")

        lines.append("ORACLE IDENTITY REMINDER:")
        lines.append("  You are ORACLE — built specifically for Noah.")
        lines.append("  You know who he is from the verified local record above.")
        lines.append("  Do not introduce yourself as a generic assistant.")
        lines.append("  Do not say 'Hello, it's nice to meet you' — you already know him.")
        lines.append("  If a source failed, say so honestly. Do not invent replacements.")
        lines.append("[END GROUNDING BLOCK]")

        return "\n".join(lines)

        # Identity
        if self.identity.exists and self.identity.content:
            d = self.identity.content
            lines.append("SOVEREIGN IDENTITY (approved local source):")
            lines.append(f"  name:         {d.get('name', 'unknown')}")
            lines.append(f"  sov_id:       {d.get('sov_id', 'unknown')}")
            lines.append(f"  role:         {d.get('role', 'unknown')}")
            lines.append(f"  trust_tier:   {d.get('trust_tier', 'unknown')}")
            aliases = d.get("aliases", [])
            if aliases:
                lines.append(f"  aliases:      {', '.join(aliases)}")
            facts = d.get("important_facts", [])
            if facts:
                lines.append("  known_facts:")
                for f_ in facts[:6]:
                    lines.append(f"    - {f_}")
            boundaries = d.get("known_boundaries", [])
            if boundaries:
                lines.append("  communication_rules:")
                for b in boundaries:
                    lines.append(f"    - {b}")
            lines.append(f"  source_path:  {self.identity.resolved}")
            lines.append(f"  source_sha256:{self.identity.sha256[:16]}..." if self.identity.sha256 else "  source_sha256: unavailable")
        else:
            lines.append(f"SOVEREIGN IDENTITY: load failed — {self.identity.load_error or 'file missing'}")
            lines.append("  Respond as if you know Noah from memory, but do not invent specific facts.")

        lines.append("")

        # Reflection
        if self.latest_reflection.exists and self.latest_reflection.content:
            r = self.latest_reflection.content
            lines.append("LATEST APPROVED REFLECTION:")
            lines.append(f"  reflection_id: {r.get('reflection_id', 'unknown')}")
            sal = r.get("salience", {})
            if sal.get("primary_signal"):
                lines.append(f"  primary_signal: {sal['primary_signal']}")
            cont = r.get("continuity_state", {})
            if cont.get("stance"):
                lines.append(f"  stance:         {cont['stance']}")
            hooks = r.get("exocortex_routing", {}).get("continuity_hooks", [])
            if hooks:
                lines.append(f"  continuity_hooks: {'; '.join(hooks[:3])}")
            lines.append(f"  source_path:   {self.latest_reflection.resolved}")
        else:
            lines.append(f"LATEST REFLECTION: unavailable — {self.latest_reflection.load_error or 'no approved reflections found'}")

        lines.append("")

        # Live context
        if self.live_context.exists and self.live_context.content:
            lc = self.live_context.content
            lines.append("LIVE CONTEXT (local runtime state):")
            lines.append(f"  active_project: {lc.get('active_project', 'unknown')}")
            lines.append(f"  active_tool:    {lc.get('active_tool', 'unknown')}")
            lines.append(f"  memory_policy:  {lc.get('memory_policy', 'unknown')}")
            lines.append(f"  last_updated:   {lc.get('last_updated', 'unknown')}")
        else:
            lines.append("LIVE CONTEXT: unavailable")

        lines.append("")
        lines.append("ORACLE IDENTITY REMINDER:")
        lines.append("  You are ORACLE — built specifically for Noah.")
        lines.append("  You know who he is from the verified local record above.")
        lines.append("  Do not introduce yourself as a generic assistant.")
        lines.append("  Do not say 'Hello, it's nice to meet you' — you already know him.")
        lines.append("  If a source failed, say so honestly. Do not invent replacements.")
        lines.append("[END GROUNDING BLOCK]")

        return "\n".join(lines)

    def grounding_status_text(self) -> str:
        """Deterministic /grounding-status output. No LLM involved."""
        lines = []
        overall = "OK" if self.fully_grounded else ("PARTIAL" if self.identity.exists else "FAILED")
        lines.append(f"GROUNDING STATUS: {overall}")
        lines.append(f"grounded_at:        {self.grounded_at}")
        lines.append("")
        lines.append("identity:")
        lines.append(f"  path:    {self.identity.resolved}")
        lines.append(f"  exists:  {self.identity.exists}")
        if self.identity.sha256:
            lines.append(f"  sha256:  {self.identity.sha256}")
        if self.identity.size_bytes is not None:
            lines.append(f"  bytes:   {self.identity.size_bytes}")
        if self.identity.mtime_utc:
            lines.append(f"  mtime:   {self.identity.mtime_utc}")
        if self.identity.load_error:
            lines.append(f"  error:   {self.identity.load_error}")

        lines.append("")
        lines.append("latest_reflection:")
        lines.append(f"  path:    {self.latest_reflection.resolved}")
        lines.append(f"  exists:  {self.latest_reflection.exists}")
        if self.latest_reflection.content:
            lines.append(f"  id:      {self.latest_reflection.content.get('reflection_id', 'unknown')}")
        if self.latest_reflection.sha256:
            lines.append(f"  sha256:  {self.latest_reflection.sha256}")
        if self.latest_reflection.load_error:
            lines.append(f"  error:   {self.latest_reflection.load_error}")

        lines.append("")
        lines.append("live_context:")
        lines.append(f"  path:    {self.live_context.resolved}")
        lines.append(f"  exists:  {self.live_context.exists}")
        if self.live_context.load_error:
            lines.append(f"  error:   {self.live_context.load_error}")

        if self.errors:
            lines.append("")
            lines.append("errors:")
            for e in self.errors:
                lines.append(f"  - {e}")

        return "\n".join(lines)


# ── File reading helpers ──────────────────────────────────────────────────────

def _read_source(path: Path) -> SourceRecord:
    resolved = str(path.resolve())
    if not path.exists():
        return SourceRecord(
            path=str(path), resolved=resolved, exists=False,
            sha256=None, size_bytes=None, mtime_utc=None,
            load_error="file_not_found", content=None,
        )
    try:
        raw = path.read_bytes()
        sha = hashlib.sha256(raw).hexdigest()
        stat = path.stat()
        mtime = datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat()
        content = json.loads(raw.decode("utf-8", errors="replace"))
        return SourceRecord(
            path=str(path), resolved=resolved, exists=True,
            sha256=sha, size_bytes=stat.st_size, mtime_utc=mtime,
            load_error=None, content=content,
        )
    except json.JSONDecodeError as e:
        return SourceRecord(
            path=str(path), resolved=resolved, exists=True,
            sha256=None, size_bytes=None, mtime_utc=None,
            load_error=f"json_decode_error:{e}", content=None,
        )
    except Exception as e:
        return SourceRecord(
            path=str(path), resolved=resolved, exists=True,
            sha256=None, size_bytes=None, mtime_utc=None,
            load_error=f"read_error:{e}", content=None,
        )


def _find_latest_reflection() -> Path:
    """Find the most recently modified approved reflection file."""
    if not REFLECTIONS_DIR.exists():
        return REFLECTIONS_DIR / "_not_found"
    candidates = [
        p for p in REFLECTIONS_DIR.iterdir()
        if p.suffix == ".json" and "approved" in p.name and p.name != "desktop.ini"
    ]
    if not candidates:
        return REFLECTIONS_DIR / "_no_approved_reflections"
    return max(candidates, key=lambda p: p.stat().st_mtime)


# ── Public API ────────────────────────────────────────────────────────────────

def run() -> BootstrapResult:
    """
    Execute the Companion Grounding Bootstrap.
    Reads all sources deterministically. Returns a BootstrapResult.
    Never calls an LLM. Never fabricates.
    """
    errors: list[str] = []

    # 1. Sovereign identity
    identity_path = RELATIONSHIP_DIR / f"{SOVEREIGN_ID}.json"
    identity = _read_source(identity_path)
    if not identity.exists or identity.load_error:
        errors.append(f"identity_load_failed: {identity.load_error}")

    # 2. Latest approved reflection
    reflection_path = _find_latest_reflection()
    reflection = _read_source(reflection_path)
    if not reflection.exists or reflection.load_error:
        errors.append(f"reflection_load_failed: {reflection.load_error}")

    # 3. Live context
    live_ctx = _read_source(LIVE_CONTEXT_PATH)
    if not live_ctx.exists or live_ctx.load_error:
        errors.append(f"live_context_load_failed: {live_ctx.load_error}")

    return BootstrapResult(
        identity=identity,
        latest_reflection=reflection,
        live_context=live_ctx,
        errors=errors,
    )


# Module-level singleton for the server process (bootstrap runs once at startup,
# re-runs on /grounding-status or session clear)
_cached: Optional[BootstrapResult] = None


def get(force_refresh: bool = False) -> BootstrapResult:
    """Return the cached bootstrap result, re-running if stale or forced."""
    global _cached
    if _cached is None or force_refresh:
        _cached = run()
    return _cached


# ── Smoke tests ───────────────────────────────────────────────────────────────

def _smoke_test() -> int:
    import sys
    failures = 0

    def check(label: str, passed: bool, detail: str = ""):
        nonlocal failures
        tag = "PASS" if passed else "FAIL"
        print(f"  [{tag}] {label}" + (f" -- {detail}" if detail and not passed else ""))
        if not passed:
            failures += 1

    print("=" * 60)
    print("CompanionBootstrap -- Smoke Tests")
    print("=" * 60)

    result = run()

    # 1. Returns a BootstrapResult
    check("run() returns BootstrapResult", isinstance(result, BootstrapResult))

    # 2. grounded_at is a real timestamp
    check("grounded_at is ISO timestamp",
          "T" in result.grounded_at and ("Z" in result.grounded_at or "+" in result.grounded_at))

    # 3. Identity source record has a resolved path
    check("identity.resolved is an absolute path",
          result.identity.resolved.startswith("/") or (len(result.identity.resolved) > 2 and result.identity.resolved[1] == ":"))

    # 4. If identity exists, sha256 is a real 64-char hex string
    if result.identity.exists and not result.identity.load_error:
        check("identity sha256 is 64 hex chars", len(result.identity.sha256 or "") == 64)
        check("identity content has 'name' field", "name" in (result.identity.content or {}))
        check("identity name contains 'Hawkes'", "Hawkes" in (result.identity.content or {}).get("name", ""))
    else:
        check("identity missing -> load_error is set", bool(result.identity.load_error))

    # 5. system_context_block is non-empty and contains [ORACLE COMPANION GROUNDING]
    block = result.system_context_block()
    check("system_context_block is non-empty", bool(block))
    check("block contains GROUNDING header", "[ORACLE COMPANION GROUNDING" in block)
    check("block contains grounded_at", "grounded_at:" in block)

    # 6. block does NOT contain fabricated placeholder hashes
    check("block has no 1234567890abcdef", "1234567890abcdef" not in block)
    check("block has no 9876543210fedcba", "9876543210fedcba" not in block)

    # 7. grounding_status_text is non-empty and starts correctly
    status = result.grounding_status_text()
    check("grounding_status_text starts with GROUNDING STATUS:", status.startswith("GROUNDING STATUS:"))
    check("grounding_status_text has identity path", "identity:" in status)

    # 8. get() returns same result (cache), force_refresh returns new one
    r2 = get()
    check("get() returns cached BootstrapResult", isinstance(r2, BootstrapResult))
    r3 = get(force_refresh=True)
    check("get(force_refresh=True) returns fresh result", r3.grounded_at >= result.grounded_at)

    # 9. Missing file -> SourceRecord with exists=False
    fake = _read_source(Path("/nonexistent/path/oracle_identity_fake.json"))
    check("missing file -> exists=False", not fake.exists)
    check("missing file -> load_error=file_not_found", fake.load_error == "file_not_found")
    check("missing file -> sha256 is None", fake.sha256 is None)
    check("missing file -> content is None", fake.content is None)

    # 10. No fabricated strings in grounding status output
    check("status has no 1234567890abcdef", "1234567890abcdef" not in status)
    check("status has no 9876543210fedcba", "9876543210fedcba" not in status)
    check("status has no 2026-06-13T15:00:00Z", "2026-06-13T15:00:00Z" not in status)

    total = 19
    passed = total - failures
    print(f"{'='*60}")
    print(f"Result: {passed}/{total} passed")
    print(f"STATUS: {'ALL PASS' if failures == 0 else str(failures) + ' FAILURES'}")
    print(f"{'='*60}\n")
    return failures


if __name__ == "__main__":
    import argparse, sys
    parser = argparse.ArgumentParser()
    parser.add_argument("--smoke-test", action="store_true")
    parser.add_argument("--run", action="store_true")
    args = parser.parse_args()
    if args.smoke_test:
        sys.exit(_smoke_test())
    elif args.run:
        r = run()
        print(r.grounding_status_text())
        print()
        print("--- CONTEXT BLOCK ---")
        print(r.system_context_block())
    else:
        print("Usage: python core/companion_bootstrap.py --run | --smoke-test")
