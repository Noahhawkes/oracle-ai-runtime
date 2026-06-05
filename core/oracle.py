#!/usr/bin/env python3
"""
ORACLE.AI — Core Runtime
Run: python core/oracle.py
"""

import os
import sys
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv

# Load .env from project root
ROOT = Path(__file__).parent.parent
load_dotenv(ROOT / ".env")

import anthropic
from memory import init_db, new_session, save_message, get_recent_messages
from context_loader import build_system_prompt, load_identity, index_summary
from audit_log import log

MODEL = "claude-sonnet-4-6"
MAX_TOKENS = 4096


def banner(identity):
    name = identity.get("name", "Noah")
    constructs = identity.get("echo_constructs", [])
    hour = datetime.now().hour
    greeting = "Good morning" if hour < 12 else "Good afternoon" if hour < 18 else "Good evening"

    print("\n" + "═" * 50)
    print("  ORACLE.AI ONLINE")
    print("═" * 50)
    print("  Identity Anchor Loaded")
    print("  Memory Database Connected")
    print(f"  Context Repository Indexed")
    print("═" * 50)
    print(f"\n{greeting}, {name.split()[0]}.\n")
    if constructs:
        print(f"Echo constructs available: {', '.join(constructs[:4])}")
    print("\nType your message. Commands: /quit /memory /clear\n")


def show_memory(session_id):
    from memory import get_facts, get_recent_messages
    facts = get_facts()
    msgs = get_recent_messages(session_id, limit=5)
    print("\n--- Memory Snapshot ---")
    if facts:
        for f in facts[:10]:
            print(f"  [{f['category']}] {f['key']}: {f['value']}")
    else:
        print("  No facts stored yet.")
    print(f"\n  Recent messages this session: {len(msgs)}")
    print("-----------------------\n")


def chat(client, session_id, system_prompt, history, user_input):
    history.append({"role": "user", "content": user_input})
    save_message(session_id, "user", user_input)
    log("INPUT", user_input)

    response = client.messages.create(
        model=MODEL,
        max_tokens=MAX_TOKENS,
        system=system_prompt,
        messages=history,
    )

    reply = response.content[0].text
    history.append({"role": "assistant", "content": reply})
    save_message(session_id, "assistant", reply)
    log("OUTPUT", reply[:200] + ("..." if len(reply) > 200 else ""))

    return reply, history


def main():
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        print("ERROR: ANTHROPIC_API_KEY not found in .env")
        print(f"Create {ROOT / '.env'} with: ANTHROPIC_API_KEY=your_key_here")
        sys.exit(1)

    # Change working dir so relative imports work
    os.chdir(Path(__file__).parent)

    init_db()
    session_id = new_session()
    identity = load_identity()
    system_prompt = build_system_prompt()
    client = anthropic.Anthropic(api_key=api_key)
    history = []

    banner(identity)
    log("SESSION_START", f"Session {session_id} started")

    while True:
        try:
            user_input = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n\nOracle offline. Session saved.")
            log("SESSION_END", f"Session {session_id} ended")
            break

        if not user_input:
            continue

        if user_input.lower() in ("/quit", "/exit"):
            print("\nOracle offline. Session saved.")
            log("SESSION_END", f"Session {session_id} ended")
            break

        if user_input.lower() == "/memory":
            show_memory(session_id)
            continue

        if user_input.lower() == "/clear":
            history = []
            print("Conversation history cleared. Memory persists.\n")
            continue

        try:
            reply, history = chat(client, session_id, system_prompt, history, user_input)
            print(f"\nOracle: {reply}\n")
        except anthropic.APIError as e:
            print(f"\n[API Error: {e}]\n")
            log("ERROR", str(e))


if __name__ == "__main__":
    main()
