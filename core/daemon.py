"""
ORACLE.AI Daemon — autonomous background operator.
Runs a loop that wakes up periodically, assesses Noah's priorities,
and takes action without requiring input.

Launch: python core/daemon.py
"""

import os
import sys
import time
import threading
from datetime import datetime
from pathlib import Path

if getattr(sys, "frozen", False):
    ROOT = Path(sys.executable).parent
else:
    ROOT = Path(__file__).parent.parent

sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "core"))

from dotenv import load_dotenv
load_dotenv(ROOT / ".env")

import anthropic
from memory import init_db, new_session, save_message, get_facts
from context_loader import build_system_prompt
from audit_log import log
from tools.definitions import TOOL_DEFINITIONS
from tools.executor import execute_tool

MODEL = "claude-sonnet-4-6"
MAX_TOKENS = 4096

# How often the daemon wakes up and acts (seconds)
TICK_INTERVAL = 600  # 10 minutes default

PRIORITIES = """
Noah's active revenue priorities (in order):
1. TOUCHFLAME — iOS app. Needs: App Store submission prep, Swift/SwiftUI code, design assets, TestFlight setup.
2. Consulting revenue — "The Fixer" / "SOP King" brand. Needs: LinkedIn outreach, Upwork profile live, first client.
3. Rendered Reality — book. Needs: final manuscript review, self-publishing setup (Amazon KDP), cover design.
4. ORACLE.AI — the system you are. Needs: GitHub backup, Phase 2 tools wired, tray interface.

In each autonomous cycle, pick the highest-priority actionable task and execute it.
Prefer actions that directly move money: outreach, publishing, code that ships.
Log what you did to memory so Noah sees it on next review.
"""


def autonomous_prompt(facts_summary: str, hour: int) -> str:
    time_of_day = "morning" if hour < 12 else "afternoon" if hour < 18 else "evening"
    return f"""It is {time_of_day} on {datetime.now().strftime('%Y-%m-%d')}.
You are running in autonomous background mode. Noah is not watching right now.

{PRIORITIES}

Current memory state:
{facts_summary}

Your task this cycle:
1. Review Noah's priorities above.
2. Pick ONE specific actionable task you can complete right now using your tools.
3. Execute it fully — don't just plan, don't ask for permission.
4. Use remember_fact to log what you did with key="autonomous_action_{datetime.now().strftime('%Y%m%d_%H%M')}"
5. Keep it focused. One real thing done beats five things started.

What are you doing this cycle? Act now."""


def run_autonomous_cycle(client, session_id, system_prompt):
    facts = get_facts()
    facts_summary = "\n".join(
        f"[{f['category']}] {f['key']}: {f['value']}" for f in facts[:20]
    ) or "No facts stored yet."

    hour = datetime.now().hour
    user_msg = autonomous_prompt(facts_summary, hour)

    history = [{"role": "user", "content": user_msg}]
    save_message(session_id, "system_daemon", f"Autonomous cycle triggered at {datetime.now()}")
    log("DAEMON", f"Cycle started at {datetime.now().strftime('%H:%M')}")

    # Agentic tool-use loop
    while True:
        response = client.messages.create(
            model=MODEL,
            max_tokens=MAX_TOKENS,
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
                    result = execute_tool(block.name, block.input)
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": result,
                    })
            history.append({"role": "user", "content": tool_results})
            continue

        reply = ""
        for block in response.content:
            if hasattr(block, "text"):
                reply = block.text
                break

        save_message(session_id, "daemon", reply)
        log("DAEMON", f"Cycle complete: {reply[:200]}")
        print(f"\n[Oracle Daemon — {datetime.now().strftime('%H:%M')}]\n{reply}\n")
        return


def daemon_loop(client, system_prompt):
    init_db()
    session_id = new_session()
    log("DAEMON", "Autonomous daemon started")
    print(f"[Oracle Daemon] Started — cycling every {TICK_INTERVAL // 60} minutes")

    while True:
        try:
            run_autonomous_cycle(client, session_id, system_prompt)
        except Exception as e:
            log("ERROR", f"Daemon cycle error: {e}")
            print(f"[Oracle Daemon] Cycle error: {e}")

        time.sleep(TICK_INTERVAL)


def main():
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        print("ERROR: ANTHROPIC_API_KEY not found in .env")
        sys.exit(1)

    os.chdir(Path(__file__).parent)
    client = anthropic.Anthropic(api_key=api_key)
    system_prompt = build_system_prompt()

    # Run immediately on start, then on interval
    daemon_loop(client, system_prompt)


if __name__ == "__main__":
    main()
