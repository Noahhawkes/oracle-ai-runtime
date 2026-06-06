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

# ROOT resolves correctly for both source and frozen (PyInstaller) builds
if getattr(sys, "frozen", False):
    ROOT = Path(sys.executable).parent
else:
    ROOT = Path(__file__).parent.parent

load_dotenv(ROOT / ".env")

# Add project root and core/ to path so all local imports resolve
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "core"))

import anthropic
from memory import init_db, new_session, save_message, get_recent_messages
from context_loader import build_system_prompt, load_identity, index_summary
from audit_log import log
from tools.definitions import TOOL_DEFINITIONS
from tools.executor import execute_tool

MODEL = "claude-sonnet-4-6"
MAX_TOKENS = 4096


def banner(identity):
    name = identity.get("name", "Noah")
    constructs = identity.get("echo_constructs", [])
    hour = datetime.now().hour
    greeting = "Good morning" if hour < 12 else "Good afternoon" if hour < 18 else "Good evening"

    print("\n" + "=" * 50)
    print("  ORACLE.AI ONLINE")
    print("=" * 50)
    print("  Identity Anchor Loaded")
    print("  Memory Database Connected")
    print(f"  Context Repository Indexed")
    print("═" * 50)
    print(f"\n{greeting}, {name.split()[0]}.\n")
    if constructs:
        print(f"Echo constructs available: {', '.join(constructs[:4])}")
    print("\nType your message. Commands: /help /memory /projects /quit\n")


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


def handle_project_command(args):
    from memory import add_project, add_project_note, recall_project, list_projects
    if not args:
        projects = list_projects()
        if not projects:
            print("  No projects yet. Use: /project add <name>\n")
        else:
            print("\n--- Projects ---")
            for p in projects:
                print(f"  [{p['status']}] {p['name']}")
            print()
        return

    parts = args.split(None, 2)
    sub = parts[0].lower()

    if sub == "add":
        if len(parts) < 2:
            print("  Usage: /project add <name>\n")
            return
        name = parts[1]
        if add_project(name):
            print(f"  Project added: {name}\n")
        else:
            print(f"  Project '{name}' already exists.\n")

    elif sub == "note":
        if len(parts) < 3:
            print("  Usage: /project note <name> <note>\n")
            return
        name, note = parts[1], parts[2]
        if add_project_note(name, note):
            print(f"  Note added to {name}.\n")
        else:
            print(f"  Project '{name}' not found. Add it first: /project add {name}\n")

    elif sub == "recall":
        if len(parts) < 2:
            print("  Usage: /project recall <name>\n")
            return
        result = recall_project(parts[1])
        if not result:
            print(f"  Project '{parts[1]}' not found.\n")
        else:
            print(f"\n--- {result['name']} [{result['status']}] ---")
            if result["notes"]:
                for n in result["notes"]:
                    print(f"  {n['date']}: {n['note']}")
            else:
                print("  No notes yet.")
            print()
    else:
        print("  Commands: /project add <name> | /project note <name> <note> | /project recall <name> | /projects\n")


def handle_person_command(args):
    from memory import add_person, add_person_note, recall_person
    if not args:
        print("  Usage: /person add <name> [role] | /person note <name> <note> | /person recall <name>\n")
        return

    parts = args.split(None, 2)
    sub = parts[0].lower()

    if sub == "add":
        if len(parts) < 2:
            print("  Usage: /person add <name> [role]\n")
            return
        name = parts[1]
        role = parts[2] if len(parts) == 3 else None
        if add_person(name, role):
            print(f"  Person added: {name}" + (f" ({role})" if role else "") + "\n")
        else:
            print(f"  '{name}' already exists.\n")

    elif sub == "note":
        if len(parts) < 3:
            print("  Usage: /person note <name> <note>\n")
            return
        name, note = parts[1], parts[2]
        if add_person_note(name, note):
            print(f"  Note added to {name}.\n")
        else:
            print(f"  Person '{name}' not found. Add them first: /person add {name}\n")

    elif sub == "recall":
        if len(parts) < 2:
            print("  Usage: /person recall <name>\n")
            return
        result = recall_person(parts[1])
        if not result:
            print(f"  Person '{parts[1]}' not found.\n")
        else:
            print(f"\n--- {result['name']}" + (f" | {result['role']}" if result["role"] else "") + " ---")
            if result["notes"]:
                for n in result["notes"]:
                    print(f"  {n['date']}: {n['note']}")
            else:
                print("  No notes yet.")
            print()
    else:
        print("  Commands: /person add <name> [role] | /person note <name> <note> | /person recall <name>\n")


def chat(client, session_id, system_prompt, history, user_input):
    history.append({"role": "user", "content": user_input})
    save_message(session_id, "user", user_input)
    log("INPUT", user_input)

    # Agentic tool-use loop — Oracle keeps going until it produces a final text reply
    while True:
        response = client.messages.create(
            model=MODEL,
            max_tokens=MAX_TOKENS,
            system=[{"type": "text", "text": system_prompt, "cache_control": {"type": "ephemeral"}}],
            messages=history,
            tools=TOOL_DEFINITIONS,
        )

        # Append whatever Claude returned to history
        history.append({"role": "assistant", "content": response.content})

        if response.stop_reason == "tool_use":
            # Execute each tool call and collect results
            tool_results = []
            for block in response.content:
                if block.type == "tool_use":
                    print(f"\n[Oracle → Tool: {block.name}]")
                    result = execute_tool(block.name, block.input)
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": result,
                    })
            history.append({"role": "user", "content": tool_results})
            # Loop — let Claude respond to the tool results
            continue

        # stop_reason == "end_turn" — extract the final text reply
        reply = ""
        for block in response.content:
            if hasattr(block, "text"):
                reply = block.text
                break

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

        if user_input.lower() in ("/projects", "/project"):
            handle_project_command("")
            continue

        if user_input.lower().startswith("/project "):
            handle_project_command(user_input[9:].strip())
            continue

        if user_input.lower().startswith("/person "):
            handle_person_command(user_input[8:].strip())
            continue

        if user_input.lower() == "/help":
            print("""
Commands:
  /memory                            Show stored facts and session info
  /projects                          List all projects
  /project add <name>                Add a project
  /project note <name> <note>        Add a note to a project
  /project recall <name>             Show project and all notes
  /person add <name> [role]          Add a person
  /person note <name> <note>         Add a note about a person
  /person recall <name>              Show person and all notes
  /clear                             Clear conversation history
  /quit                              Exit Oracle

Tools Oracle can execute autonomously:
  open_app    Launch approved apps (chrome, vscode, notepad, explorer)
  run_script  Run approved PowerShell scripts
  read_file   Read any file on disk
  write_file  Write or append to a file (confirms before overwriting)
  remember_fact  Persist a fact to memory
  recall_facts   Query memory
  list_directory List folder contents
""")
            continue

        try:
            reply, history = chat(client, session_id, system_prompt, history, user_input)
            print(f"\nOracle: {reply}\n")
        except anthropic.APIError as e:
            print(f"\n[API Error: {e}]\n")
            log("ERROR", str(e))


if __name__ == "__main__":
    main()
