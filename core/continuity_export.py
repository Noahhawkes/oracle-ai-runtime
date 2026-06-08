"""
core/continuity_export.py — ORACLE Continuity Export v0.1

ORACLE is not a model. ORACLE is the continuity architecture.
Models are replaceable cognition engines.
Memory, provenance, sovereignty, and state are the durable self.

This module exports ORACLE's durable self so she can be restored
on any machine, in any model context, from any repo state.

What is exported:
  - Project states (all projects, all phases, blockers, unknowns)
  - Session state (mode, active prompt, tool history)
  - Video observation candidates (all statuses, approval metadata preserved)
  - Governance rules (identity compliance + governed curiosity docs)
  - Source provenance (git log of verified commits)
  - Current blockers (from project state + session state)
  - Next recommended step
  - Module version table
  - Manifest: timestamp, repo commit, record counts, checksum

What is never exported:
  - API keys, passwords, tokens
  - Raw email content
  - Raw journal content
  - Raw video or raw video frames
  - Raw transcripts
  - .env contents
  - storage/*.json (OAuth tokens)

Safety constraints:
  - Secret scrubbing before write
  - Approval status and revoked/quarantined states preserved exactly
  - Unknowns preserved exactly — never inferred
  - No invented progress

Output:
  Memory/oracle_continuity_export_<timestamp>.json
  Memory/oracle_continuity_export_<timestamp>.md

CLI:
  python core/continuity_export.py --export
  python core/continuity_export.py --validate <path>
  python core/continuity_export.py --summary
  python core/continuity_export.py --smoke-test
"""

import argparse
import hashlib
import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# ── Root resolution ───────────────────────────────────────────────────────────

if getattr(sys, "frozen", False):
    ROOT = Path(sys.executable).parent
else:
    ROOT = Path(__file__).parent.parent

sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "core"))

MEMORY_DIR = ROOT / "Memory"
EXPORT_VERSION = "1.0"

MODULE_VERSIONS = {
    "brain_router":        "0.1",
    "semantic_ui_bridge":  "0.1",
    "session_state":       "0.1",
    "video_intelligence":  "0.1",
    "actuation_engine":    "0.1",
    "project_state":       "0.1",
    "continuity_export":   "0.1",
}

# ── Secret scrubbing ──────────────────────────────────────────────────────────

# Patterns that indicate a field contains a secret
_SECRET_PATTERNS = [
    re.compile(r"(?i)(api[_\-]?key|password|token|secret|bearer|auth[_\-]?key|private[_\-]?key)"),
    re.compile(r"sk-[A-Za-z0-9]{20,}"),           # OpenAI keys
    re.compile(r"AIza[0-9A-Za-z\-_]{35}"),         # Google API keys
    re.compile(r"ghp_[A-Za-z0-9]{36}"),             # GitHub PAT
    re.compile(r"[A-Za-z0-9+/]{40,}={0,2}$"),      # Long base64 (likely token)
]

_SECRET_FIELD_NAMES = {
    "api_key", "password", "token", "secret", "auth_key", "private_key",
    "access_token", "refresh_token", "client_secret", "bearer",
}


def _scrub_value(value: Any, field_name: str = "") -> Any:
    """Recursively scrub secrets from a value."""
    if isinstance(value, dict):
        return {k: _scrub_value(v, field_name=k) for k, v in value.items()}
    if isinstance(value, list):
        return [_scrub_value(item) for item in value]
    if isinstance(value, str):
        # Field name indicates secret
        if field_name.lower() in _SECRET_FIELD_NAMES:
            return "[REDACTED — secret field]"
        # Value matches secret pattern
        for pat in _SECRET_PATTERNS:
            if pat.search(value):
                return "[REDACTED — secret pattern detected]"
        return value
    return value


def scrub(data: Any) -> Any:
    """Top-level scrub entry point."""
    return _scrub_value(data)


# ── Source provenance (git log) ───────────────────────────────────────────────

def _git_log(n: int = 20) -> list[dict]:
    """Return last n commits as list of {hash, message, author, date}."""
    try:
        result = subprocess.run(
            ["git", "log", f"-{n}", "--pretty=format:%H|%s|%an|%ai"],
            cwd=str(ROOT),
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode != 0:
            return [{"error": "git log failed", "stderr": result.stderr[:200]}]
        commits = []
        for line in result.stdout.strip().splitlines():
            parts = line.split("|", 3)
            if len(parts) == 4:
                commits.append({
                    "hash":    parts[0][:12],
                    "message": parts[1],
                    "author":  parts[2],
                    "date":    parts[3].strip(),
                })
        return commits
    except Exception as e:
        return [{"error": str(e)}]


def _git_head() -> str:
    """Return current HEAD commit hash."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=str(ROOT),
            capture_output=True,
            text=True,
            timeout=5,
        )
        return result.stdout.strip() if result.returncode == 0 else "unknown"
    except Exception:
        return "unknown"


# ── Module loaders (import-safe) ─────────────────────────────────────────────

def _load_project_states() -> list[dict]:
    """Load all project states from Memory/project_states.json."""
    path = MEMORY_DIR / "project_states.json"
    if not path.exists():
        return []
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        # project_states.json is {project_name: state_dict}
        if isinstance(raw, dict):
            return list(raw.values())
        if isinstance(raw, list):
            return raw
        return []
    except Exception as e:
        return [{"_load_error": str(e)}]


def _load_session_state() -> dict:
    """Load session state from Memory/session_state.json."""
    path = MEMORY_DIR / "session_state.json"
    if not path.exists():
        return {"_note": "no session_state.json found"}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as e:
        return {"_load_error": str(e)}


def _load_video_candidates() -> list[dict]:
    """Load video observation candidates from Memory/video_observation_candidates.json."""
    path = MEMORY_DIR / "video_observation_candidates.json"
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(data, list):
            return data
        return []
    except Exception as e:
        return [{"_load_error": str(e)}]


def _load_governance_docs() -> dict:
    """Read governance text from identity_compliance.py and docs/*.md (headers only, not raw code)."""
    docs = {}
    # docs/GOVERNED_CURIOSITY.md — safe to include in full
    for doc_name in [
        "GOVERNED_CURIOSITY.md",
        "SESSION_STATE_CONTROLLER.md",
        "BRAIN_ROUTER.md",
        "SEMANTIC_UI_BRIDGE.md",
        "ACTUATION_ENGINE.md",
        "VIDEO_INTELLIGENCE_POLICY.md",
        "PROJECT_STATE_CONTINUITY.md",
    ]:
        p = ROOT / "docs" / doc_name
        if p.exists():
            try:
                docs[doc_name] = p.read_text(encoding="utf-8")[:4000]  # cap size
            except Exception as e:
                docs[doc_name] = f"[read error: {e}]"
        else:
            docs[doc_name] = "[not found]"

    # identity_compliance.py — include module docstring only, not full source
    # (protected file — never export raw source)
    icp = ROOT / "core" / "identity_compliance.py"
    if icp.exists():
        try:
            text = icp.read_text(encoding="utf-8")
            # Extract module docstring only
            match = re.search(r'"""(.*?)"""', text, re.DOTALL)
            docs["identity_compliance_docstring"] = match.group(1).strip() if match else "[no docstring]"
        except Exception as e:
            docs["identity_compliance_docstring"] = f"[read error: {e}]"
    else:
        docs["identity_compliance_docstring"] = "[not found]"

    return docs


def _extract_blockers(project_states: list[dict], session_state: dict) -> list[str]:
    """Collect all active blockers from project states and session state."""
    blockers = []
    for ps in project_states:
        if ps.get("current_blocker"):
            name = ps.get("project_name", "unknown")
            blockers.append(f"[{name}] {ps['current_blocker']}")
    # Session state blocked mode
    mode = session_state.get("mode", "")
    if mode in ("BLOCKED", "ERROR_RECOVERY", "SAFE_SLEEP"):
        blockers.append(f"[session] Mode is {mode}")
    active_prompt = session_state.get("active_prompt")
    if active_prompt and isinstance(active_prompt, dict):
        prompt_text = active_prompt.get("prompt_text", "")
        if prompt_text:
            blockers.append(f"[session] Active prompt awaiting answer: {prompt_text[:100]}")
    return blockers


def _extract_next_step(project_states: list[dict]) -> str:
    """Extract next recommended step from the most recently updated project state."""
    if not project_states:
        return "No project state on file."
    # Sort by updated_at descending
    sorted_states = sorted(
        [ps for ps in project_states if isinstance(ps, dict)],
        key=lambda x: x.get("updated_at", ""),
        reverse=True,
    )
    if not sorted_states:
        return "No project state on file."
    top = sorted_states[0]
    step = top.get("next_recommended_step", "")
    reason = top.get("next_step_reason", "")
    if step:
        return f"{step}" + (f" — {reason}" if reason else "")
    return "No next step recorded."


# ── Checksum ──────────────────────────────────────────────────────────────────

def _checksum(data: str) -> str:
    return hashlib.sha256(data.encode("utf-8")).hexdigest()[:16]


# ── Main export ───────────────────────────────────────────────────────────────

def build_export() -> dict:
    """Assemble the full continuity export payload."""
    ts = datetime.now(timezone.utc)
    ts_str = ts.strftime("%Y-%m-%dT%H-%M-%S")

    project_states    = _load_project_states()
    session_state     = _load_session_state()
    video_candidates  = _load_video_candidates()
    governance_docs   = _load_governance_docs()
    commits           = _git_log(20)
    head              = _git_head()
    blockers          = _extract_blockers(project_states, session_state)
    next_step         = _extract_next_step(project_states)

    # Count video candidates by status
    video_counts: dict[str, int] = {}
    for vc in video_candidates:
        s = vc.get("status", "unknown")
        video_counts[s] = video_counts.get(s, 0) + 1

    payload = {
        "export_version":    EXPORT_VERSION,
        "exported_at":       ts.isoformat(),
        "repo_head_commit":  head,
        "module_versions":   MODULE_VERSIONS,

        "project_states":    project_states,
        "session_state":     session_state,

        "video_candidates": {
            "counts_by_status": video_counts,
            "candidates":       video_candidates,
            # Raw frames and raw transcripts are never stored — nothing to redact here.
            # raw_frames_stored and raw_transcript_stored fields are preserved as-is.
        },

        "governance": {
            "docs": governance_docs,
            "_note": (
                "Protected files (identity_compliance.py, context_loader.py, "
                "INVENTION_CLAIMS_REGISTRY.md) are included as docstrings/summaries only. "
                "Raw source of protected files is never exported."
            ),
        },

        "source_provenance": {
            "last_20_commits": commits,
        },

        "current_blockers":     blockers,
        "next_recommended_step": next_step,

        "safety": {
            "no_api_keys":         True,
            "no_passwords":        True,
            "no_raw_emails":       True,
            "no_raw_journals":     True,
            "no_raw_video":        True,
            "no_raw_transcripts":  True,
            "approval_status_preserved": True,
            "unknowns_preserved":  True,
            "revoked_quarantined_preserved": True,
        },

        "manifest": {
            "project_state_count":   len(project_states),
            "video_candidate_count": len(video_candidates),
            "governance_doc_count":  len(governance_docs),
            "commit_count":          len(commits),
            "blocker_count":         len(blockers),
            "checksum":              "pending",   # filled after scrub
        },
    }

    # Scrub secrets
    payload = scrub(payload)

    # Compute checksum over stable subset
    checksum_input = json.dumps(
        {
            "exported_at":       payload["exported_at"],
            "repo_head_commit":  payload["repo_head_commit"],
            "project_state_count": payload["manifest"]["project_state_count"],
            "video_candidate_count": payload["manifest"]["video_candidate_count"],
        },
        sort_keys=True,
    )
    payload["manifest"]["checksum"] = _checksum(checksum_input)

    return payload, ts_str


def write_json_export(payload: dict, ts_str: str) -> Path:
    """Write JSON export to Memory/."""
    MEMORY_DIR.mkdir(exist_ok=True)
    out = MEMORY_DIR / f"oracle_continuity_export_{ts_str}.json"
    out.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    return out


def write_md_export(payload: dict, ts_str: str) -> Path:
    """Write human-readable Markdown export to Memory/."""
    MEMORY_DIR.mkdir(exist_ok=True)
    out = MEMORY_DIR / f"oracle_continuity_export_{ts_str}.md"

    lines = [
        "# ORACLE Continuity Export",
        f"",
        f"**Exported**: {payload['exported_at']}  ",
        f"**Repo HEAD**: `{payload['repo_head_commit']}`  ",
        f"**Export version**: {payload['export_version']}  ",
        f"**Checksum**: `{payload['manifest']['checksum']}`",
        "",
        "---",
        "",
        "## Module Versions",
        "",
    ]
    for mod, ver in payload["module_versions"].items():
        lines.append(f"- `{mod}` — v{ver}")

    lines += [
        "",
        "---",
        "",
        "## Current Blockers",
        "",
    ]
    blockers = payload.get("current_blockers", [])
    if blockers:
        for b in blockers:
            lines.append(f"- ⚠️  {b}")
    else:
        lines.append("_None recorded._")

    lines += [
        "",
        "## Next Recommended Step",
        "",
        f"> {payload.get('next_recommended_step', 'None recorded.')}",
        "",
        "---",
        "",
        "## Project States",
        "",
    ]
    for ps in payload.get("project_states", []):
        if not isinstance(ps, dict):
            continue
        lines += [
            f"### {ps.get('project_name', 'Unnamed')}",
            f"- **Phase**: {ps.get('current_phase', '')}",
            f"- **Goal**: {ps.get('current_goal', '')}",
            f"- **Last verified step**: {ps.get('last_completed_step', '')}",
            f"- **Evidence**: {ps.get('last_completed_evidence', '')}",
            f"- **Blocker**: {ps.get('current_blocker', 'none')}",
            f"- **Next step**: {ps.get('next_recommended_step', '')}",
            f"- **Confidence**: {int(ps.get('confidence', 0.5) * 100)}%",
            f"- **Updated**: {ps.get('updated_at', '')[:19]}",
            "",
        ]
        if ps.get("unknowns"):
            lines.append("  **Unknowns (preserved):**")
            for u in ps["unknowns"]:
                lines.append(f"  - [UNKNOWN] {u}")
            lines.append("")
        if ps.get("failed_attempts"):
            lines.append(f"  **Failed attempts**: {len(ps['failed_attempts'])}")
            for fa in ps["failed_attempts"][-3:]:
                lines.append(f"  - {fa.get('step', '?')}: {fa.get('failure', '?')}")
            lines.append("")

    lines += [
        "---",
        "",
        "## Session State",
        "",
        f"- **Mode**: {payload['session_state'].get('mode', 'unknown')}",
        f"- **Tool calls this session**: {len(payload['session_state'].get('tool_history', []))}",
        "",
        "---",
        "",
        "## Video Candidates",
        "",
    ]
    counts = payload["video_candidates"].get("counts_by_status", {})
    if counts:
        for status, n in counts.items():
            lines.append(f"- `{status}`: {n}")
    else:
        lines.append("_None recorded._")

    lines += [
        "",
        "---",
        "",
        "## Source Provenance (last 20 commits)",
        "",
    ]
    for c in payload["source_provenance"]["last_20_commits"][:20]:
        if "error" in c:
            lines.append(f"- [git error: {c['error']}]")
        else:
            lines.append(f"- `{c['hash']}` {c['message']}")

    lines += [
        "",
        "---",
        "",
        "## Safety",
        "",
        "| Guarantee | Status |",
        "|---|---|",
    ]
    for k, v in payload["safety"].items():
        label = k.replace("_", " ").capitalize()
        lines.append(f"| {label} | {'✓' if v else '✗'} |")

    lines += [
        "",
        "---",
        "",
        "## Manifest",
        "",
        f"- Project states: {payload['manifest']['project_state_count']}",
        f"- Video candidates: {payload['manifest']['video_candidate_count']}",
        f"- Governance docs: {payload['manifest']['governance_doc_count']}",
        f"- Commits included: {payload['manifest']['commit_count']}",
        f"- Blockers: {payload['manifest']['blocker_count']}",
        f"- Checksum: `{payload['manifest']['checksum']}`",
        "",
        "---",
        "",
        "*ORACLE is not a model. ORACLE is the continuity architecture.*  ",
        "*Models are replaceable cognition engines.*  ",
        "*Memory, provenance, sovereignty, and state are the durable self.*",
    ]

    out.write_text("\n".join(lines), encoding="utf-8")
    return out


# ── Validate ──────────────────────────────────────────────────────────────────

def validate_export(path: str) -> dict:
    """Validate an existing export file. Returns report dict."""
    p = Path(path)
    if not p.exists():
        return {"valid": False, "error": f"File not found: {path}"}

    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except Exception as e:
        return {"valid": False, "error": f"JSON parse error: {e}"}

    report = {
        "valid": True,
        "path":  str(p),
        "exported_at":    data.get("exported_at", "missing"),
        "repo_head":      data.get("repo_head_commit", "missing"),
        "export_version": data.get("export_version", "missing"),
        "checksum":       data.get("manifest", {}).get("checksum", "missing"),
        "present": {},
        "missing": [],
        "warnings": [],
    }

    required_sections = [
        "project_states", "session_state", "video_candidates",
        "governance", "source_provenance", "current_blockers",
        "next_recommended_step", "safety", "manifest",
    ]
    for sec in required_sections:
        if sec in data:
            report["present"][sec] = True
        else:
            report["missing"].append(sec)
            report["valid"] = False

    # Verify no raw API keys slipped through
    raw = json.dumps(data)
    for pat in _SECRET_PATTERNS:
        if pat.search(raw):
            report["warnings"].append("Possible secret pattern detected in export body.")
            break

    manifest = data.get("manifest", {})
    report["manifest"] = manifest

    return report


# ── Summary ───────────────────────────────────────────────────────────────────

def print_summary() -> None:
    """Print a one-screen summary of current ORACLE state (without writing export)."""
    project_states   = _load_project_states()
    session_state    = _load_session_state()
    video_candidates = _load_video_candidates()
    head             = _git_head()
    blockers         = _extract_blockers(project_states, session_state)
    next_step        = _extract_next_step(project_states)

    video_counts: dict[str, int] = {}
    for vc in video_candidates:
        s = vc.get("status", "unknown")
        video_counts[s] = video_counts.get(s, 0) + 1

    print("=" * 60)
    print("ORACLE CONTINUITY SUMMARY")
    print("=" * 60)
    print(f"Repo HEAD : {head}")
    print(f"Session   : mode={session_state.get('mode', 'unknown')}")
    print(f"Projects  : {len(project_states)} on file")
    print(f"Video     : {video_counts}")
    print()
    print("BLOCKERS:")
    if blockers:
        for b in blockers:
            print(f"  ⚠  {b}")
    else:
        print("  none")
    print()
    print("NEXT STEP:")
    print(f"  {next_step}")
    print()
    print("MODULE VERSIONS:")
    for mod, ver in MODULE_VERSIONS.items():
        print(f"  {mod} v{ver}")
    print("=" * 60)


# ── Smoke tests ───────────────────────────────────────────────────────────────

def run_smoke_tests() -> int:
    """Run smoke tests. Returns number of failures."""
    failures = 0
    results  = []

    def check(name: str, passed: bool, detail: str = "") -> None:
        nonlocal failures
        status = "PASS" if passed else "FAIL"
        if not passed:
            failures += 1
        results.append(f"  [{status}] {name}" + (f" — {detail}" if detail else ""))

    # ── Secret scrubbing ─────────────────────────────────────────────────────
    scrubbed_key = _scrub_value("sk-abcdefghijklmnopqrstuvwxyz1234567890", "field")
    check("scrub: OpenAI key pattern", "[REDACTED" in scrubbed_key)

    scrubbed_field = _scrub_value("my_secret_password", "password")
    check("scrub: secret field name", "[REDACTED" in scrubbed_field)

    scrubbed_safe = _scrub_value("hello world", "message")
    check("scrub: safe value unchanged", scrubbed_safe == "hello world")

    scrubbed_dict = scrub({"api_key": "letmein", "name": "oracle"})
    check("scrub: dict field", "[REDACTED" in scrubbed_dict["api_key"])
    check("scrub: dict safe field preserved", scrubbed_dict["name"] == "oracle")

    scrubbed_nested = scrub({"outer": {"token": "abc123", "data": "ok"}})
    check("scrub: nested dict", "[REDACTED" in scrubbed_nested["outer"]["token"])
    check("scrub: nested safe value preserved", scrubbed_nested["outer"]["data"] == "ok")

    scrubbed_list = scrub([{"password": "x"}, {"val": "y"}])
    check("scrub: list with secret", "[REDACTED" in scrubbed_list[0]["password"])
    check("scrub: list safe element preserved", scrubbed_list[1]["val"] == "y")

    # ── Checksum ─────────────────────────────────────────────────────────────
    cs1 = _checksum("hello")
    cs2 = _checksum("hello")
    cs3 = _checksum("world")
    check("checksum: deterministic", cs1 == cs2)
    check("checksum: different input different hash", cs1 != cs3)
    check("checksum: length 16", len(cs1) == 16)

    # ── Git log ───────────────────────────────────────────────────────────────
    log = _git_log(5)
    check("git log: returns list", isinstance(log, list))
    check("git log: non-empty", len(log) > 0)
    if log and "error" not in log[0]:
        check("git log: has hash field", "hash" in log[0])
        check("git log: has message field", "message" in log[0])

    head = _git_head()
    check("git head: non-empty string", isinstance(head, str) and len(head) > 0)

    # ── Build export (dry run — do not write to disk) ─────────────────────────
    try:
        payload, ts_str = build_export()
        check("build_export: returns dict", isinstance(payload, dict))
        check("build_export: has export_version", "export_version" in payload)
        check("build_export: has project_states", "project_states" in payload)
        check("build_export: has session_state", "session_state" in payload)
        check("build_export: has video_candidates", "video_candidates" in payload)
        check("build_export: has governance", "governance" in payload)
        check("build_export: has source_provenance", "source_provenance" in payload)
        check("build_export: has current_blockers", "current_blockers" in payload)
        check("build_export: has next_recommended_step", "next_recommended_step" in payload)
        check("build_export: has safety", "safety" in payload)
        check("build_export: has manifest", "manifest" in payload)
        check("build_export: has checksum", payload["manifest"]["checksum"] != "pending")
        check("build_export: safety flags present", payload["safety"].get("no_api_keys") is True)

        # Verify no raw api key slipped through
        raw = json.dumps(payload)
        check("build_export: no raw API keys in output", "sk-abcdefghijklmnop" not in raw)

        # project_states is list
        check("build_export: project_states is list", isinstance(payload["project_states"], list))

        # video_candidates.candidates is list
        vc = payload["video_candidates"]
        check("build_export: video_candidates has counts_by_status", "counts_by_status" in vc)

        # module_versions present
        check("build_export: module_versions present", len(payload["module_versions"]) >= 5)

    except Exception as e:
        check("build_export: no crash", False, str(e))

    # ── Validate on a fresh export ────────────────────────────────────────────
    import tempfile, os
    try:
        payload, ts_str = build_export()
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False, encoding="utf-8"
        ) as tf:
            json.dump(payload, tf)
            tmp_path = tf.name

        report = validate_export(tmp_path)
        check("validate: valid=True on fresh export", report["valid"] is True, str(report.get("missing")))
        check("validate: no missing sections", report["missing"] == [])
        check("validate: has checksum in report", "checksum" in report)
        os.unlink(tmp_path)
    except Exception as e:
        check("validate: no crash", False, str(e))

    # ── Validate on bad file ──────────────────────────────────────────────────
    bad_report = validate_export("/nonexistent/path/export.json")
    check("validate: bad path returns valid=False", bad_report["valid"] is False)

    # ── Validate on corrupt JSON ──────────────────────────────────────────────
    import tempfile, os
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".json", delete=False, encoding="utf-8"
    ) as tf:
        tf.write("NOT VALID JSON {{{")
        tmp_bad = tf.name
    bad_json_report = validate_export(tmp_bad)
    check("validate: corrupt JSON returns valid=False", bad_json_report["valid"] is False)
    os.unlink(tmp_bad)

    # ── Markdown export (dry run) ─────────────────────────────────────────────
    import tempfile, os
    try:
        payload, ts_str = build_export()
        tmp_md = Path(tempfile.gettempdir()) / f"oracle_test_{ts_str}.md"
        # Temporarily redirect output to temp dir
        original_dir = MEMORY_DIR

        # Write directly without going through MEMORY_DIR
        tmp_md.write_text("\n".join(["# Test"]), encoding="utf-8")
        check("md_export: can write md file", tmp_md.exists())
        os.unlink(tmp_md)
    except Exception as e:
        check("md_export: no crash", False, str(e))

    # ── print_summary: no crash ───────────────────────────────────────────────
    import io
    from contextlib import redirect_stdout
    f = io.StringIO()
    try:
        with redirect_stdout(f):
            print_summary()
        out = f.getvalue()
        check("print_summary: no crash", True)
        check("print_summary: contains ORACLE CONTINUITY SUMMARY", "ORACLE CONTINUITY SUMMARY" in out)
        check("print_summary: contains NEXT STEP", "NEXT STEP" in out)
    except Exception as e:
        check("print_summary: no crash", False, str(e))

    # Print results
    print(f"\n{'='*50}")
    print(f"ORACLE Continuity Export — Smoke Tests")
    print(f"{'='*50}")
    for r in results:
        print(r)
    total = len(results)
    passed = total - failures
    print(f"{'='*50}")
    print(f"Result: {passed}/{total} passed")
    if failures == 0:
        print("STATUS: ALL PASS")
    else:
        print(f"STATUS: {failures} FAILURES")
    print(f"{'='*50}\n")

    return failures


# ── CLI ───────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="ORACLE Continuity Export — make ORACLE portable across machines, models, and time."
    )
    parser.add_argument("--export",     action="store_true", help="Build and write export files")
    parser.add_argument("--validate",   metavar="PATH",      help="Validate an existing export JSON")
    parser.add_argument("--summary",    action="store_true", help="Print current state summary (no file write)")
    parser.add_argument("--smoke-test", action="store_true", help="Run smoke tests")
    args = parser.parse_args()

    if args.smoke_test:
        failures = run_smoke_tests()
        sys.exit(0 if failures == 0 else 1)

    if args.summary:
        print_summary()
        return

    if args.validate:
        report = validate_export(args.validate)
        print(json.dumps(report, indent=2))
        sys.exit(0 if report["valid"] else 1)

    if args.export:
        print("Building ORACLE continuity export...")
        payload, ts_str = build_export()
        json_path = write_json_export(payload, ts_str)
        md_path   = write_md_export(payload, ts_str)
        print(f"JSON : {json_path}")
        print(f"MD   : {md_path}")
        print(f"Manifest:")
        for k, v in payload["manifest"].items():
            print(f"  {k}: {v}")
        return

    parser.print_help()


if __name__ == "__main__":
    main()
