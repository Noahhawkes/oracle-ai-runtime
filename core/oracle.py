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

from memory import init_db, new_session, save_message, get_recent_messages
from context_loader import build_system_prompt, load_identity, index_summary
from audit_log import log
from tools.definitions import TOOL_DEFINITIONS
from tools.executor import execute_tool
from llm import is_local, make_client, get_model, to_openai_tools, startup_status

MAX_TOKENS = 4096


def banner(identity):
    name = identity.get("name", "Noah")
    constructs = identity.get("echo_constructs", [])
    hour = datetime.now().hour
    greeting = "Good morning" if hour < 12 else "Good afternoon" if hour < 18 else "Good evening"

    st = startup_status()

    print("\n" + "═" * 56)
    print("  ORACLE.AI  |  SOV1 OPERATOR MODULE")
    print("═" * 56)
    print(f"  Mode        : {st['mode']}")
    print(f"  Text model  : {st['model']}")
    print(f"  Vision model: {st['vision_model']}")
    if st["mode"] == "LOCAL":
        ollama_icon = "[OK]" if st.get("ollama_ok") else "[!!]"
        print(f"  Ollama      : {ollama_icon} {st.get('ollama_msg', '')}")
    sov1_icon = "[OK]" if st["sov1_available"] else "[--]"
    print(f"  SOV1 hands  : {sov1_icon} {st['sov1_msg']}")
    print("  Memory DB   : connected")
    print("═" * 56)
    print(f"\n{greeting}, {name.split()[0]}.\n")
    if constructs:
        print(f"Echo constructs: {', '.join(constructs[:4])}")
    print("\nType your message or tell me to do something on screen.")
    print("Commands: /help /memory /projects /quit\n")


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


def _handle_lootdrop(user_input: str):
    """
    /lootdrop                          — show recap of recent drops
    /lootdrop <tier> <project> <reason>  — award a drop
    Tiers: common uncommon rare epic legendary mythic
    """
    from lootdrop import award, recap_summary, TIER_NAMES
    parts = user_input.strip().split(None, 3)
    # /lootdrop (no args) → show recap
    if len(parts) == 1:
        print()
        print(recap_summary())
        print()
        return
    # /lootdrop <tier> <project> <reason>
    if len(parts) < 4:
        print(f"\n  Usage: /lootdrop <tier> <project> <reason>")
        print(f"  Tiers: {', '.join(TIER_NAMES)}")
        print(f"  Example: /lootdrop mythic ORACLE SOV1 vision loop working end-to-end\n")
        return
    tier = parts[1].lower()
    project = parts[2]
    reason = parts[3]
    try:
        award(tier, source_activity="manual /lootdrop command", reason_earned=reason,
              related_project=project)
    except ValueError as e:
        print(f"\n  {e}\n")


def _has_tool_use(content):
    """True if an assistant message's content contains a tool_use block."""
    if not isinstance(content, list):
        return False
    for block in content:
        btype = getattr(block, "type", None) or (block.get("type") if isinstance(block, dict) else None)
        if btype == "tool_use":
            return True
    return False


def _repair_history(history):
    """
    Trim history back to the last clean boundary after an interrupted tool call.
    A clean boundary is an assistant message with no dangling tool_use blocks.
    Drops the trailing (now-stale) user input so the retry re-adds it cleanly.
    """
    repaired = list(history)
    # Walk backward, dropping messages until we land on a complete assistant turn
    while repaired:
        last = repaired[-1]
        role = last.get("role")
        content = last.get("content")
        if role == "assistant" and not _has_tool_use(content):
            break  # clean end_turn assistant message — safe stopping point
        repaired.pop()
    return repaired


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


def chat_local(client, session_id, system_prompt, history, user_input, model):
    """OpenAI-compatible agentic loop for local Ollama models."""
    import json

    history.append({"role": "user", "content": user_input})
    save_message(session_id, "user", user_input)
    log("INPUT", user_input)

    oai_tools = to_openai_tools(TOOL_DEFINITIONS)

    while True:
        messages = [{"role": "system", "content": system_prompt}] + history
        response = client.chat.completions.create(
            model=model,
            max_tokens=MAX_TOKENS,
            messages=messages,
            tools=oai_tools,
        )
        msg = response.choices[0].message
        finish = response.choices[0].finish_reason

        # Store assistant turn in history
        assistant_entry = {"role": "assistant", "content": msg.content or ""}
        if msg.tool_calls:
            assistant_entry["tool_calls"] = [
                {
                    "id": tc.id,
                    "type": "function",
                    "function": {"name": tc.function.name, "arguments": tc.function.arguments},
                }
                for tc in msg.tool_calls
            ]
        history.append(assistant_entry)

        if finish in ("tool_calls", "tool_use") and msg.tool_calls:
            for tc in msg.tool_calls:
                print(f"\n[Oracle → Tool: {tc.function.name}]")
                try:
                    inp = json.loads(tc.function.arguments)
                except (json.JSONDecodeError, TypeError):
                    inp = {}
                result = execute_tool(tc.function.name, inp)
                history.append({"role": "tool", "tool_call_id": tc.id, "content": result})
            continue

        reply = msg.content or ""
        save_message(session_id, "assistant", reply)
        log("OUTPUT", reply[:200] + ("..." if len(reply) > 200 else ""))
        return reply, history


def main():
    os.chdir(Path(__file__).parent)
    init_db()
    session_id = new_session()
    identity = load_identity()
    system_prompt = build_system_prompt()
    history = []

    local = is_local()
    try:
        client = make_client()
    except RuntimeError as e:
        print(f"ERROR: {e}")
        sys.exit(1)
    model = get_model(vision=False)

    if local:
        print(f"\n[LOCAL MODE] Using Ollama model: {model}")
        print("[LOCAL MODE] Make sure Ollama is running and the model is pulled.")
        print(f"[LOCAL MODE] Pull command: ollama pull {model}\n")

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

        if user_input.lower().startswith("/lootdrop"):
            _handle_lootdrop(user_input)
            continue

        if user_input.lower() == "/propose-build":
            print("\n[propose-build] Starting read-only build recommendation...\n")
            try:
                from propose_build import run_propose_build
                proposal = run_propose_build(client, model, local)
                print(proposal)
            except Exception as e:
                log("ERROR", f"/propose-build failed: {e}")
                print(f"\n[propose-build error: {e}]\n")
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
  /propose-build                     Read build docs and recommend one next task (read-only)
  /lootdrop                          Show recent LootDrop momentum recap
  /lootdrop <tier> <project> <reason>  Award a LootDrop (tiers: common uncommon rare epic legendary mythic)
  /quit                              Exit

Brain tools (reasoning, files, web):
  read_file / write_file / list_directory
  run_shell       Run any PowerShell command
  browser_navigate / browser_search
  filesystem_scan / filesystem_search
  remember_fact / recall_facts
  scheduler_control

Hands tools (SOV1 — operates the screen):
  computer_operator   Tell Oracle to do something on screen and it uses SOV1.
                      Just speak naturally: "open Chrome", "click X", etc.
                      Abort anytime: slam mouse into a screen corner.
""")
            continue

        try:
            if local:
                reply, history = chat_local(client, session_id, system_prompt, history, user_input, model)
            else:
                reply, history = chat(client, session_id, system_prompt, history, user_input)
            print(f"\nOracle: {reply}\n")
        except Exception as e:
            msg = str(e)
            log("ERROR", msg)
            # Self-heal dangling tool_use/tool_result mismatch (Anthropic cloud error pattern)
            if not local and "tool_use" in msg and "tool_result" in msg:
                history = _repair_history(history)
                print("\n[Oracle recovered from an interrupted tool call. Retrying...]\n")
                try:
                    reply, history = chat(client, session_id, system_prompt, history, user_input)
                    print(f"\nOracle: {reply}\n")
                    continue
                except Exception as e2:
                    log("ERROR", f"Retry failed: {e2}")
                    history = []
                    print("\n[Oracle reset its conversation buffer. Memory is intact. Try again.]\n")
            else:
                print(f"\n[Error: {e}]\n")


if __name__ == "__main__":
    main()
