"""
ORACLE.AI Daemon — autonomous background operator.

Conservative observe-and-propose mode:
  1. Pre-flight: check source map freshness, retrieve goal-relevant docs
  2. LLM cycle: observe, reason, propose — safe tools only
  3. Post-cycle: write action proposal to Projects/daemon_proposals/
  4. Risk gate: blocks destructive tools; requires human approval for anything irreversible

Launch: python core/daemon.py
"""

import os
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

if getattr(sys, "frozen", False):
    ROOT = Path(sys.executable).parent
else:
    ROOT = Path(__file__).parent.parent

sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "core"))

from dotenv import load_dotenv
load_dotenv(ROOT / ".env")

from memory import init_db, new_session, save_message, get_facts
from context_loader import build_system_prompt
from audit_log import log
from tools.definitions import TOOL_DEFINITIONS
from tools.executor import execute_tool
from llm import is_local, make_client, get_model, to_openai_tools

# ── Config ────────────────────────────────────────────────────────────────────

TICK_INTERVAL   = 600   # seconds between daemon wakes (10 min default)
SOURCE_MAP_TTL  = 4     # hours before source map is considered stale
MAX_INGEST_DOCS = 3     # max docs ingested per cycle
PROPOSALS_DIR   = ROOT / "Projects" / "daemon_proposals"

# ── Risk gate — tools the daemon may call without approval ────────────────────
# Everything NOT in this set is blocked and logged as a proposal instead.

SAFE_TOOLS = {
    "read_file",
    "list_directory",
    "recall_facts",
    "remember_fact",
    "source_map_scan",
    "source_map_search",
    "source_map_ingest",
    "filesystem_scan",
    "filesystem_search",
    "filesystem_summary",
    "browser_navigate",
    "browser_search",
}

# ── Active goals — keywords the daemon searches for each cycle ────────────────

GOALS = [
    {"name": "AI Compliance Sales",   "keywords": ["AICC", "compliance", "SOP", "AI compliance"]},
    {"name": "TOUCHFLAME iOS App",    "keywords": ["TOUCHFLAME", "iOS", "Swift", "App Store"]},
    {"name": "Consulting Revenue",    "keywords": ["consulting", "SOP King", "Upwork", "LinkedIn"]},
    {"name": "Rendered Reality Book", "keywords": ["Rendered Reality", "manuscript", "KDP", "publishing"]},
    {"name": "ORACLE.AI Development", "keywords": ["ORACLE", "oracle.py", "daemon", "source map"]},
]


# ── Pre-flight: source map freshness + goal context retrieval ─────────────────

def _source_map_stale() -> bool:
    """True if the source map is missing or older than SOURCE_MAP_TTL hours."""
    from source_map import INDEX_PATH
    if not INDEX_PATH.exists():
        return True
    age = datetime.now() - datetime.fromtimestamp(INDEX_PATH.stat().st_mtime)
    return age > timedelta(hours=SOURCE_MAP_TTL)


def _preflight() -> str:
    """
    Run before the LLM cycle.
    1. Refresh source map if stale.
    2. Search for each active goal's keywords.
    3. Return a context string to inject into the daemon prompt.
    """
    from source_map import build_index, save_index, search_index, get_index_summary, load_index

    lines = ["=== PRE-FLIGHT CONTEXT ===\n"]

    # 1. Freshness check
    if _source_map_stale():
        log("DAEMON", "Source map stale — scanning")
        print("[Daemon] Source map stale — scanning key folders...")
        index = build_index()
        save_index(index)
        lines.append(f"Source map refreshed: {index['file_count']} files indexed.\n")
    else:
        idx = load_index()
        built = idx["built_at"][:16] if idx else "unknown"
        lines.append(f"Source map current (built {built}, {idx['file_count'] if idx else '?'} files).\n")

    # 2. Goal-context retrieval
    lines.append("Goal-relevant files found:\n")
    seen_paths = set()
    for goal in GOALS:
        hits = []
        for kw in goal["keywords"]:
            for r in search_index(kw, max_results=5):
                if r["path"] not in seen_paths:
                    hits.append(r)
                    seen_paths.add(r["path"])
        if hits:
            lines.append(f"  [{goal['name']}]")
            for h in hits[:3]:
                lines.append(f"    {h['path']}  [{h['ext']} | {h['modified']}]")
        else:
            lines.append(f"  [{goal['name']}] — no matching files found")

    return "\n".join(lines)


# ── Risk gate ─────────────────────────────────────────────────────────────────

def _gated_execute(tool_name: str, tool_input: dict, blocked_proposals: list) -> str:
    """
    Execute a tool only if it's in SAFE_TOOLS.
    Blocked calls are recorded as proposals rather than run.
    """
    if tool_name in SAFE_TOOLS:
        log("DAEMON", f"Safe tool: {tool_name}")
        return execute_tool(tool_name, tool_input)

    # Risky — record and refuse
    proposal = f"PROPOSED (requires approval): {tool_name}({tool_input})"
    blocked_proposals.append(proposal)
    log("DAEMON", f"Blocked (risk gate): {tool_name}")
    return (
        f"[RISK GATE] '{tool_name}' requires human approval in daemon mode. "
        f"This action has been added to the proposal list for Noah to review."
    )


# ── Proposal writer ───────────────────────────────────────────────────────────

def _write_proposal(content: str, blocked: list):
    """Write the daemon's output to a dated proposal file."""
    PROPOSALS_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y-%m-%d_%H%M")
    fpath = PROPOSALS_DIR / f"{ts}.md"

    sections = [
        f"# Oracle Daemon Proposal — {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        "",
        content,
    ]
    if blocked:
        sections += [
            "",
            "---",
            "## Actions Requiring Approval",
            "",
            *[f"- {b}" for b in blocked],
            "",
            "_Review and run manually, or tell Oracle to proceed with a specific item._",
        ]

    fpath.write_text("\n".join(sections), encoding="utf-8")
    log("DAEMON", f"Proposal written: {fpath.name}")
    print(f"[Daemon] Proposal → {fpath}")
    return str(fpath)


# ── Daemon prompt ─────────────────────────────────────────────────────────────

def _daemon_prompt(preflight_context: str, facts_summary: str) -> str:
    hour = datetime.now().hour
    time_label = "morning" if hour < 12 else "afternoon" if hour < 18 else "evening"
    date_str = datetime.now().strftime("%Y-%m-%d")

    return f"""It is {time_label} on {date_str}. You are ORACLE.AI running in autonomous daemon mode.

OPERATING MODE: Observe and Propose.
- You MAY: read files, search the source map, recall facts, store facts, browse the web for research.
- You MAY NOT (in this cycle): write or edit files, run shell commands, open apps, push to git, send messages, or take any irreversible action.
- If you want to propose a risky action, describe it clearly — it will be logged for Noah's review.

ACTIVE GOALS (in priority order):
1. AI Compliance Sales — find and surface AICC docs useful for revenue/sales
2. TOUCHFLAME iOS App — track progress, surface blockers
3. Consulting Revenue — SOP King / Upwork / LinkedIn outreach
4. Rendered Reality Book — manuscript, KDP, publishing readiness
5. ORACLE.AI Development — system health, what's missing

{preflight_context}

Current memory:
{facts_summary}

YOUR CYCLE TASK:
1. Pick the highest-priority goal where you can do real work TODAY.
2. Use source_map_search and read_file to retrieve the most relevant doc(s) — max {MAX_INGEST_DOCS} reads.
3. Use source_map_ingest to save a crisp summary of any doc you read (max {MAX_INGEST_DOCS} ingests).
4. Write a clear action proposal: what you found, what you recommend Noah does next, and any specific actions that need his approval.
5. Use remember_fact to log this cycle's key finding.

Be concrete. Name specific files, quote key passages, give Noah something actionable."""


# ── Core cycle ────────────────────────────────────────────────────────────────

def run_autonomous_cycle(client, session_id, system_prompt, local: bool, model: str):
    # Pre-flight
    preflight_ctx = _preflight()
    facts = get_facts()
    facts_summary = "\n".join(
        f"[{f['category']}] {f['key']}: {f['value']}" for f in facts[:20]
    ) or "No facts stored yet."

    user_msg = _daemon_prompt(preflight_ctx, facts_summary)
    history = [{"role": "user", "content": user_msg}]
    blocked_proposals = []

    save_message(session_id, "system_daemon", f"Autonomous cycle at {datetime.now()}")
    log("DAEMON", f"Cycle started at {datetime.now().strftime('%H:%M')}")

    # Agentic tool-use loop
    while True:
        if local:
            import json
            oai_tools = to_openai_tools(TOOL_DEFINITIONS)
            messages = [{"role": "system", "content": system_prompt}] + history
            response = client.chat.completions.create(
                model=model, max_tokens=4096, messages=messages, tools=oai_tools,
            )
            msg = response.choices[0].message
            finish = response.choices[0].finish_reason

            assistant_entry = {"role": "assistant", "content": msg.content or ""}
            if msg.tool_calls:
                assistant_entry["tool_calls"] = [
                    {"id": tc.id, "type": "function",
                     "function": {"name": tc.function.name, "arguments": tc.function.arguments}}
                    for tc in msg.tool_calls
                ]
            history.append(assistant_entry)

            if finish in ("tool_calls", "tool_use") and msg.tool_calls:
                for tc in msg.tool_calls:
                    try:
                        inp = json.loads(tc.function.arguments)
                    except Exception:
                        inp = {}
                    log("DAEMON", f"Tool call: {tc.function.name}")
                    result = _gated_execute(tc.function.name, inp, blocked_proposals)
                    history.append({"role": "tool", "tool_call_id": tc.id, "content": result})
                continue

            reply = msg.content or ""

        else:
            import anthropic as _anthropic
            response = client.messages.create(
                model=model,
                max_tokens=4096,
                system=[{"type": "text", "text": system_prompt, "cache_control": {"type": "ephemeral"}}],
                messages=history,
                tools=TOOL_DEFINITIONS,
            )
            history.append({"role": "assistant", "content": response.content})

            if response.stop_reason == "tool_use":
                tool_results = []
                for block in response.content:
                    if block.type == "tool_use":
                        log("DAEMON", f"Tool call: {block.name}")
                        result = _gated_execute(block.name, block.input, blocked_proposals)
                        tool_results.append({
                            "type": "tool_result",
                            "tool_use_id": block.id,
                            "content": result,
                        })
                history.append({"role": "user", "content": tool_results})
                continue

            reply = next(
                (block.text for block in response.content if hasattr(block, "text")), ""
            )

        # End of cycle — write proposal and return
        save_message(session_id, "daemon", reply)
        log("DAEMON", f"Cycle complete: {reply[:200]}")
        print(f"\n[Oracle Daemon — {datetime.now().strftime('%H:%M')}]\n{reply}\n")
        proposal_path = _write_proposal(reply, blocked_proposals)
        return proposal_path


# ── Daemon loop ───────────────────────────────────────────────────────────────

def daemon_loop(client, system_prompt, local: bool, model: str):
    init_db()
    session_id = new_session()
    log("DAEMON", "Autonomous daemon started (observe-and-propose mode)")
    print(f"[Oracle Daemon] Started — cycling every {TICK_INTERVAL // 60} minutes")
    print(f"[Oracle Daemon] Mode: {'local (' + model + ')' if local else 'cloud (' + model + ')'}")
    print(f"[Oracle Daemon] Proposals → {PROPOSALS_DIR}\n")

    while True:
        try:
            proposal = run_autonomous_cycle(client, session_id, system_prompt, local, model)
            print(f"[Oracle Daemon] Proposal written: {proposal}")
        except Exception as e:
            log("ERROR", f"Daemon cycle error: {e}")
            print(f"[Oracle Daemon] Cycle error: {e}")

        time.sleep(TICK_INTERVAL)


# ── Entry point ───────────────────────────────────────────────────────────────

def main():
    os.chdir(Path(__file__).parent)

    local = is_local()
    try:
        client = make_client()
    except RuntimeError as e:
        print(f"ERROR: {e}")
        sys.exit(1)
    model = get_model(vision=False)
    system_prompt = build_system_prompt()

    daemon_loop(client, system_prompt, local, model)


if __name__ == "__main__":
    main()
