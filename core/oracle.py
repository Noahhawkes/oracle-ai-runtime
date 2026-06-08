#!/usr/bin/env python3
"""
ORACLE.AI — Core Runtime
Run: python core/oracle.py
"""

import os
import sys
import time
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
from identity_compliance import handle_in_repl
from audit_log import log
from tools.definitions import TOOL_DEFINITIONS
from tools.executor import execute_tool
from llm import is_local, make_client, get_model, to_openai_tools, startup_status
from voice import speak, set_voice_enabled, is_voice_enabled

MAX_TOKENS = 4096
MAX_TOOL_CALLS_PER_TURN = 12   # hard cap — stops infinite tool spirals


def _ansi(code: str) -> str:
    """Return ANSI escape string. Safe on Windows 10+ terminals."""
    return f"\033[{code}m"


C = {
    "reset":   _ansi("0"),
    "bold":    _ansi("1"),
    "dim":     _ansi("2"),
    "cyan":    _ansi("36"),
    "bcyan":   _ansi("96"),
    "green":   _ansi("32"),
    "bgreen":  _ansi("92"),
    "yellow":  _ansi("33"),
    "byellow": _ansi("93"),
    "red":     _ansi("31"),
    "bred":    _ansi("91"),
    "magenta": _ansi("35"),
    "bmagenta":_ansi("95"),
    "white":   _ansi("97"),
    "grey":    _ansi("90"),
}


def _print_slow(text: str, delay: float = 0.018, end: str = "\n"):
    import sys
    for ch in text:
        sys.stdout.write(ch)
        sys.stdout.flush()
        time.sleep(delay)
    sys.stdout.write(end)
    sys.stdout.flush()


def _startup_stats():
    """Pull live numbers from the DB for the boot screen."""
    try:
        from memory import get_conn
        with get_conn() as conn:
            fact_count   = conn.execute("SELECT COUNT(*) FROM facts").fetchone()[0]
            session_count= conn.execute("SELECT COUNT(*) FROM sessions").fetchone()[0]
            msg_count    = conn.execute("SELECT COUNT(*) FROM messages").fetchone()[0]
            project_count= conn.execute("SELECT COUNT(*) FROM projects WHERE status='active'").fetchone()[0]
            last_msg     = conn.execute(
                "SELECT content FROM messages WHERE role='assistant' ORDER BY id DESC LIMIT 1"
            ).fetchone()
        last_line = (last_msg[0][:72] + "…") if last_msg and len(last_msg[0]) > 72 else (last_msg[0] if last_msg else None)
        return dict(facts=fact_count, sessions=session_count, messages=msg_count,
                    projects=project_count, last=last_line)
    except Exception:
        return dict(facts=0, sessions=0, messages=0, projects=0, last=None)


def _top_lootdrop():
    """Return the single highest-tier recent lootdrop, or None."""
    try:
        from lootdrop import last_drops
        drops = last_drops(n=1, min_tier="rare")
        return drops[0] if drops else None
    except Exception:
        return None


def _pending_count():
    try:
        from integration_gate import ApprovalGate
        return len(ApprovalGate().list_pending())
    except Exception:
        return 0


def banner(identity):
    import time as _time

    # Enable ANSI + UTF-8 on Windows
    try:
        import ctypes
        kernel32 = ctypes.windll.kernel32
        kernel32.SetConsoleMode(kernel32.GetStdHandle(-11), 7)
        kernel32.SetConsoleOutputCP(65001)
    except Exception:
        pass
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

    name       = identity.get("name", "Noah")
    first      = name.split()[0]
    constructs = identity.get("echo_constructs", [])
    hour       = datetime.now().hour
    now        = datetime.now()

    if hour < 5:
        greeting, tone = "Still burning the midnight oil", "[LATE]"
    elif hour < 12:
        greeting, tone = "Good morning", "[AM]"
    elif hour < 18:
        greeting, tone = "Good afternoon", "[PM]"
    else:
        greeting, tone = "Good evening", "[EVE]"

    st   = startup_status()
    db   = _startup_stats()
    drop = _top_lootdrop()
    pend = _pending_count()

    W = C["reset"]
    print()

    # ── ASCII header ────────────────────────────────────────────────────────
    header_lines = [
        f"{C['bcyan']}  ██████╗ ██████╗  █████╗  ██████╗██╗     ███████╗{W}",
        f"{C['bcyan']} ██╔═══██╗██╔══██╗██╔══██╗██╔════╝██║     ██╔════╝{W}",
        f"{C['cyan']} ██║   ██║██████╔╝███████║██║     ██║     █████╗  {W}",
        f"{C['cyan']} ██║   ██║██╔══██╗██╔══██║██║     ██║     ██╔══╝  {W}",
        f"{C['bmagenta']} ╚██████╔╝██║  ██║██║  ██║╚██████╗███████╗███████╗{W}",
        f"{C['bmagenta']}  ╚═════╝ ╚═╝  ╚═╝╚═╝  ╚═╝ ╚═════╝╚══════╝╚══════╝{W}",
    ]
    for line in header_lines:
        print(line)
        _time.sleep(0.06)

    print(f"\n{C['grey']}  {'─' * 50}{W}")
    print(f"  {C['bold']}{C['white']}SOVEREIGN OPERATOR LAYER  |  v2.0  |  GOVERNED{W}")
    print(f"{C['grey']}  {'─' * 50}{W}\n")
    _time.sleep(0.15)

    # ── System boot checks ──────────────────────────────────────────────────
    checks = []
    mode_color = C["bgreen"] if st["mode"] == "CLOUD" else C["byellow"]
    checks.append((f"  MODE", f"{mode_color}{st['mode']}{W}  {C['grey']}{st['model']}{W}"))

    vision_ok = bool(st.get("vision_model"))
    checks.append(("  VISION", f"{C['bgreen']}READY{W}  {C['grey']}{st.get('vision_model','')}{W}" if vision_ok
                               else f"{C['yellow']}OFFLINE{W}"))

    sov1_color = C["bgreen"] if st["sov1_available"] else C["grey"]
    sov1_label = "HANDS READY" if st["sov1_available"] else "HANDS OFFLINE"
    checks.append(("  SOV1", f"{sov1_color}{sov1_label}{W}"))

    if st["mode"] == "LOCAL" and not st.get("ollama_ok"):
        checks.append(("  OLLAMA", f"{C['bred']}NOT RUNNING{W}  {C['grey']}run: ollama serve{W}"))

    mem_color = C["bgreen"] if db["facts"] > 0 else C["yellow"]
    checks.append(("  MEMORY", f"{mem_color}CONNECTED{W}  "
                               f"{C['grey']}{db['facts']} facts · {db['messages']} messages · "
                               f"{db['sessions']} sessions{W}"))

    proj_label = f"{db['projects']} active project{'s' if db['projects'] != 1 else ''}"
    checks.append(("  PROJECTS", f"{C['bgreen']}{proj_label}{W}" if db["projects"] > 0 else f"{C['grey']}none{W}"))

    if pend > 0:
        checks.append(("  PENDING", f"{C['byellow']}{pend} candidate{'s' if pend!=1 else ''} await approval{W}"))

    label_w = max(len(k) for k, _ in checks) + 2
    for label, value in checks:
        padded = label.ljust(label_w)
        print(f"{C['grey']}{padded}{W}  {value}")
        _time.sleep(0.07)

    # ── Top lootdrop callout ─────────────────────────────────────────────────
    if drop:
        tier_label = drop.get("tier", "").upper()
        reason     = drop.get("reason_earned", "")[:60]
        project    = drop.get("related_project", "")
        print(f"\n{C['grey']}  {'─' * 50}{W}")
        print(f"  {C['byellow']}◆ LAST MILESTONE{W}  {C['bold']}{C['white']}{tier_label}{W}  "
              f"{C['grey']}{project}{W}")
        if reason:
            print(f"  {C['dim']}{reason}{W}")
        _time.sleep(0.1)

    # ── Project state resumption ──────────────────────────────────────────────
    try:
        from project_state import load_state
        ps = load_state("ORACLE.AI")
        if ps and ps.next_recommended_step:
            print(f"\n{C['grey']}  {'─' * 50}{W}")
            print(f"  {C['yellow']}◆ RESUMING{W}  {C['grey']}{ps.current_phase}{W}")
            print(f"  {C['dim']}Next: {ps.next_recommended_step[:70]}{W}")
            if ps.current_blocker:
                print(f"  {C['bred']}Blocker:{W} {C['dim']}{ps.current_blocker[:70]}{W}")
            _time.sleep(0.05)
    except Exception:
        pass

    # ── Last session echo ─────────────────────────────────────────────────────
    if db["last"]:
        print(f"\n{C['grey']}  {'─' * 50}{W}")
        print(f"  {C['grey']}Last session:{W}")
        _print_slow(f"  {C['dim']}{db['last']}{W}", delay=0.008, end="\n")
        _time.sleep(0.05)

    # ── Greeting ──────────────────────────────────────────────────────────────
    print(f"\n{C['grey']}  {'─' * 50}{W}\n")
    _time.sleep(0.2)
    _print_slow(f"  {C['bold']}{C['white']}{greeting}, {first}.{W}  {tone}", delay=0.04)

    if constructs:
        _time.sleep(0.1)
        print(f"\n  {C['grey']}Active constructs:{W} {C['cyan']}{', '.join(constructs[:5])}{W}")

    ts = now.strftime("%A, %B ") + str(now.day) + now.strftime("  %H:%M")
    print(f"\n{C['grey']}  {ts}{W}")
    print(f"\n{C['grey']}  {'─' * 50}{W}")
    print(f"\n  {C['dim']}Type a message · /help for commands · /quit to exit{W}\n")


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
    _tool_call_count = 0
    while True:
        if _tool_call_count >= MAX_TOOL_CALLS_PER_TURN:
            # Enter ERROR_RECOVERY — gives structured diagnostic, not just prose
            _lg_diag = f"Loop guard: {_tool_call_count} tool calls without finishing."
            _lg_hint = (
                "Type ACTION_DIAGNOSTIC to see which tool repeated. "
                "Type STOP ORACLE to halt all action. "
                "Type CLEAR_PROMPT to clear any stale terminal prompt."
            )
            try:
                from session_state import enter_recovery, action_diagnostic
                enter_recovery(reason=_lg_diag, hint=_lg_hint)
                _diag_output = action_diagnostic()
            except Exception:
                _diag_output = ""
            reply = (
                f"[Loop guard] {_lg_diag}\n"
                f"{_diag_output}\n"
                f"Hint: {_lg_hint}"
            )
            save_message(session_id, "assistant", reply)
            return reply, history
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
                    _tool_call_count += 1
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

    _tool_call_count = 0
    while True:
        if _tool_call_count >= MAX_TOOL_CALLS_PER_TURN:
            reply = (
                f"[Loop guard] I made {_tool_call_count} tool calls without finishing. "
                f"Stopping. Tell me the next step."
            )
            save_message(session_id, "assistant", reply)
            return reply, history
        messages = [{"role": "system", "content": system_prompt}] + history
        response = client.chat.completions.create(
            model=model,
            max_tokens=MAX_TOKENS,
            messages=messages,
            tools=oai_tools,
            temperature=0.7,
            extra_body={
                "num_ctx": 16384,      # large context window
                "num_predict": MAX_TOKENS,
                "repeat_penalty": 1.1, # reduce repetition
                "top_p": 0.9,
            },
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
                _tool_call_count += 1
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
    history = []

    local = is_local()
    try:
        client = make_client()
    except RuntimeError as e:
        print(f"ERROR: {e}")
        sys.exit(1)
    model = get_model(vision=False)
    system_prompt = build_system_prompt(local=local)

    if local:
        print(f"\n[LOCAL MODE] Using Ollama model: {model}")
        print("[LOCAL MODE] Make sure Ollama is running and the model is pulled.")
        print(f"[LOCAL MODE] Pull command: ollama pull {model}\n")

    # Initialise LiveContext — loads persisted state, stamps last_updated
    from live_context import get_live_context
    _ctx = get_live_context()
    _ctx.set_task("Interactive session")

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

        # ── Session State Controller — intercept BEFORE any LLM or tool call ──
        try:
            from session_state import (
                handle_command as ss_handle_command,
                classify_user_input, should_consume_as_prompt_answer,
                record_tool_call as ss_record_tool_call,
                detect_stale_prompt, set_mode as ss_set_mode,
                MODE_BUILD_PASS, MODE_IDLE, action_diagnostic,
            )
            # Stale prompt sweep on every input
            was_stale, stale_reason = detect_stale_prompt()
            if was_stale:
                print(f"\n  [SESSION] Stale prompt cleared: {stale_reason[:100]}\n")

            # Hard-intercept: is this a session state command?
            ss_handled, ss_response = ss_handle_command(user_input)
            if ss_handled:
                print(ss_response)
                continue

            # Classify input and warn if it would have been hijacked
            clf = classify_user_input(user_input)
            if clf.override_active_prompt:
                # Don't stop — but log that a stale prompt was overridden
                log("SESSION", f"Input override: classified as {clf.classified_as} — {clf.reason[:80]}")

            # Track BUILD_PASS mode for MYTHIC BUILD PASS inputs
            if clf.is_build_instruction:
                ss_set_mode(MODE_BUILD_PASS, reason=f"Build instruction detected: {user_input[:60]}")
        except ImportError:
            pass
        except Exception as _ss_err:
            log("SESSION_WARN", f"session_state error: {_ss_err}")
        # ── End session state intercept ────────────────────────────────────────

        if user_input.lower() in ("/quit", "/exit"):
            print("\nOracle offline. Session saved.")
            log("SESSION_END", f"Session {session_id} ended")
            from voice import shutdown as voice_shutdown
            voice_shutdown()
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

        # ── LiveContext / privacy commands ────────────────────────────────────
        if user_input.lower() in ("/context", "/ctx"):
            from live_context import get_live_context
            print(get_live_context().show())
            continue

        if user_input.lower() in ("/privacy on", "/privacy-on"):
            from live_context import get_live_context
            print(f"\n  {get_live_context().set_privacy_mode(True)}\n")
            continue

        if user_input.lower() in ("/privacy off", "/privacy-off"):
            from live_context import get_live_context
            print(f"\n  {get_live_context().set_privacy_mode(False)}\n")
            continue

        if user_input.lower() in ("/pause-context", "/pause"):
            from live_context import get_live_context
            print(f"\n  {get_live_context().pause()}\n")
            continue

        if user_input.lower() in ("/resume-context", "/resume"):
            from live_context import get_live_context
            print(f"\n  {get_live_context().resume()}\n")
            continue

        if user_input.lower() in ("/purge-buffer", "/purge"):
            from live_context import get_live_context
            answer = input("\n  Purge live context buffer? Pending candidates will be discarded. (y/n): ").strip().lower()
            if answer in ("y", "yes"):
                print(f"  {get_live_context().purge_buffer()}\n")
            else:
                print("  Cancelled.\n")
            continue

        if user_input.lower() in ("/pending", "/pending-candidates"):
            from integration_gate import ApprovalGate
            gate = ApprovalGate()
            candidates = gate.list_pending()
            if not candidates:
                print("\n  No pending candidates.\n")
            else:
                print(f"\n--- Pending Approval ({len(candidates)}) ---")
                for c in candidates:
                    flag = " [SENSITIVE - blocked]" if c.get("sensitive_flag") else ""
                    print(f"  [{c['confidence'].upper()}] {c['source']} | "
                          f"{c['rendered_category']}/{c['rendered_key']}{flag}")
                    print(f"    Value  : {c['rendered_value'][:80]}")
                    print(f"    Excerpt: {c['raw_excerpt'][:60]}...")
                    print(f"    ID     : {c['id']}")
                print()
            continue

        if user_input.lower() in ("/voice on", "/voice"):
            set_voice_enabled(True)
            print("\n  Voice ON — Oracle will speak her replies.\n")
            continue

        if user_input.lower() == "/voice off":
            set_voice_enabled(False)
            print("\n  Voice OFF — text only.\n")
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

        if user_input.lower() in ("/self-prompt", "/selfprompt", "/cycle"):
            print("\n[self-prompt] Running one governed cycle...\n")
            try:
                from self_prompt_loop import run_once, MODE_MANUAL
                result = run_once(mode=MODE_MANUAL)
                print(result.report())
                speak(f"Cycle complete. Priority: {result.selected_priority[:60]}")
            except Exception as e:
                log("ERROR", f"/self-prompt failed: {e}")
                print(f"\n[self-prompt error: {e}]\n")
            continue

        if user_input.lower() in ("/project-state", "/ps", "/resume", "/where-was-i"):
            try:
                from project_state import summarize_state, list_projects
                projects = list_projects()
                if not projects:
                    print("\nNo project state saved yet. Run: python core/project_state.py --seed\n")
                else:
                    for p in projects:
                        print(f"\n{'─'*54}")
                        print(summarize_state(p))
            except Exception as e:
                print(f"\n[project-state error: {e}]\n")
            continue

        if user_input.lower() in ("/runtime", "/oracle-runtime", "/run-cycle"):
            print("\n[runtime] Running one governed runtime cycle...\n")
            try:
                from oracle_runtime import run_cycle, MODE_MANUAL
                result = run_cycle(mode=MODE_MANUAL)
                print(result.report())
                speak(f"Runtime cycle complete. Priority: {result.selected_priority[:60]}")
            except Exception as e:
                log("ERROR", f"/runtime failed: {e}")
                print(f"\n[runtime error: {e}]\n")
            continue

        if user_input.lower() in ("/runtime-status", "/cycle-status"):
            try:
                from oracle_runtime import status_report
                print(status_report())
            except Exception as e:
                print(f"\n[runtime-status error: {e}]\n")
            continue

        if user_input.lower() in ("/bridge-chatgpt-status", "/bridge-status"):
            try:
                from chatgpt_bridge import get_bridge
                print(get_bridge().status())
            except Exception as e:
                print(f"\n[bridge-status error: {e}]\n")
            continue

        if user_input.lower().startswith("/bridge-chatgpt-draft"):
            request_text = user_input[len("/bridge-chatgpt-draft"):].strip()
            if not request_text:
                print("\nUsage: /bridge-chatgpt-draft <your question for ChatGPT>\n")
            else:
                try:
                    from chatgpt_bridge import get_bridge
                    msg, status = get_bridge().bridge(request=request_text, dry_run=True)
                    print(msg.summary())
                    print(f"Status: {status}\n")
                except Exception as e:
                    print(f"\n[bridge-draft error: {e}]\n")
            continue

        if user_input.lower() in ("/window-snapshot", "/win-snap"):
            try:
                from window_janitor import get_janitor
                snap = get_janitor().snapshot_windows()
                print(f"\n  Current windows ({len(snap)}):")
                for w in snap[:15]:
                    print(f"    {w.get('title', '?')[:70]}")
                if len(snap) > 15:
                    print(f"    ... and {len(snap) - 15} more")
                print()
            except Exception as e:
                print(f"\n[window-snapshot error: {e}]\n")
            continue

        if user_input.lower().startswith("/actuate ") or user_input.lower().startswith("/type-into "):
            # /actuate <window_hint> | <text to type>
            raw = user_input.split(" ", 1)[1].strip() if " " in user_input else ""
            if "|" not in raw:
                print("\n  Usage: /actuate <window_hint> | <text to type>\n"
                      "  Example: /actuate ChatGPT | Hello from ORACLE\n")
                continue
            win_hint, text = [p.strip() for p in raw.split("|", 1)]
            print(f"\n[actuate] Target window: {win_hint!r}")
            print(f"          Text to inject: {text!r}")
            print("  Noah approval required. Type 'yes' to proceed or anything else to cancel.")
            try:
                confirm = input("  Approve? ").strip().lower()
            except (EOFError, KeyboardInterrupt):
                confirm = ""
            if confirm in ("yes", "y", "approve"):
                try:
                    from actuation_engine import type_into_window
                    result = type_into_window(win_hint, text, approved=True)
                    print(result.explain())
                    if result.success and result.verified:
                        speak(f"Text injected and verified in {win_hint}.")
                    elif result.success:
                        speak(f"Text injected but not verified. Check window.")
                    else:
                        speak(f"Actuation failed: {result.failure_stage}")
                except Exception as e:
                    log("ERROR", f"/actuate failed: {e}")
                    print(f"\n[actuate error: {e}]\n")
            else:
                print("\n  Actuation cancelled.\n")
            continue

        if user_input.lower().startswith("/actuate-dry "):
            raw = user_input.split(" ", 1)[1].strip()
            if "|" not in raw:
                print("\n  Usage: /actuate-dry <window_hint> | <text>\n")
                continue
            win_hint, text = [p.strip() for p in raw.split("|", 1)]
            try:
                from actuation_engine import type_into_window
                result = type_into_window(win_hint, text, dry_run=True)
                print(result.explain())
            except Exception as e:
                print(f"\n[actuate-dry error: {e}]\n")
            continue

        if user_input.lower().startswith("/video-analyze "):
            raw_path = user_input[len("/video-analyze "):].strip()
            print(f"\n[video] Analyzing: {raw_path}")
            print("  Noah approval required. Type 'yes' to confirm or anything else to cancel.")
            try:
                confirm = input("  Approve analysis? ").strip().lower()
            except (EOFError, KeyboardInterrupt):
                confirm = ""
            if confirm in ("yes", "y", "approve"):
                try:
                    from video_intelligence import analyze_video
                    candidate = analyze_video(raw_path, approved_by_noah=True)
                    print(f"\n{candidate.full_summary()}\n")
                    print(f"  Saved as PENDING. Use /video-approve {candidate.id} to approve for recall.\n")
                    speak(f"Video observation candidate created. Status: pending. ID: {candidate.id[:6]}.")
                except Exception as e:
                    log("ERROR", f"/video-analyze failed: {e}")
                    print(f"\n[video error: {e}]\n")
            else:
                print("\n  Analysis cancelled. Noah approval not confirmed.\n")
            continue

        if user_input.lower() in ("/video-pending", "/video pending"):
            try:
                from video_intelligence import list_pending
                pending = list_pending()
                if not pending:
                    print("\n  No pending video candidates.\n")
                else:
                    print(f"\n  Pending video candidates ({len(pending)}):\n")
                    for c in pending:
                        print(f"    {c.summary_line()}")
                    print()
            except Exception as e:
                print(f"\n[video-pending error: {e}]\n")
            continue

        if user_input.lower().startswith("/video-approve "):
            cid = user_input[len("/video-approve "):].strip()
            try:
                from video_intelligence import approve_candidate
                c = approve_candidate(cid, approved_by="Noah")
                print(f"\n  Approved: {c.summary_line()}\n")
                speak(f"Video candidate {cid[:6]} approved for recall.")
            except Exception as e:
                print(f"\n[video-approve error: {e}]\n")
            continue

        if user_input.lower() in ("/session", "/session-state", "/session-status"):
            try:
                from session_state import action_diagnostic
                print(action_diagnostic())
            except Exception as e:
                print(f"\n[session error: {e}]\n")
            continue

        if user_input.lower().startswith("/route-task") or user_input.lower().startswith("/route "):
            raw = user_input.split(" ", 1)[1].strip() if " " in user_input else ""
            if not raw:
                print("\n  Usage: /route-task <describe what you want to do>\n")
                continue
            try:
                from brain_router import create_task_from_text, route_task, explain_route
                task = create_task_from_text(raw)
                decision = route_task(task)
                print(f"\n  Task text  : {raw[:80]}")
                print(f"  Classified : {task.task_type}  complexity={task.complexity}  sensitivity={task.sensitivity}")
                print(explain_route(decision))
                if decision.blocked:
                    speak(f"Task blocked. {decision.block_reason[:80]}")
                else:
                    speak(f"Routed to {decision.selected_engine}. {decision.reason[:60]}")
            except Exception as e:
                log("ERROR", f"/route-task failed: {e}")
                print(f"\n[route-task error: {e}]\n")
            continue

        if user_input.lower() in ("/self-build", "/selfbuild"):
            print("\n[self-build] Scanning codebase for highest-value improvement...\n")
            try:
                from self_build import run_self_build
                result = run_self_build(client, model, local, implement=False)
                print(result)
                speak(f"Self-build proposal ready. {result.split('TITLE')[1][:80] if 'TITLE' in result else 'Review the proposal.'}")
            except Exception as e:
                log("ERROR", f"/self-build failed: {e}")
                print(f"\n[self-build error: {e}]\n")
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
  /self-build                        Scan own codebase and propose the single best improvement
  /self-prompt                       Run one governed self-prompt cycle (state, memory, gaps, priority, proposal)
  /project-state                     Show current project state — what was active, what's blocked, what's next
  /runtime                           Run one governed runtime cycle (heartbeat — picks priority, invokes module, persists result)
  /runtime-status                    Show runtime state: SOV1, Ollama, pending queues, next priority
  /bridge-chatgpt-draft <question>   Draft a governed message to ChatGPT (does not send — dry run)
  /bridge-chatgpt-status             Show ChatGPT bridge status and pending drafts
  /window-snapshot                   List currently visible windows on the desktop
  /route-task <description>          Route a task to the correct cognitive engine (brain router)
  /actuate <window> | <text>         Governed desktop injection: find window → find control → inject → verify
  /actuate-dry <window> | <text>     Dry run actuation — shows what would happen without executing
  /video-analyze <path>              Analyze an approved video file — creates pending candidate
  /video-pending                     List pending video observation candidates
  /video-approve <id>                Approve a video candidate for recall
  /session                           Show full session state diagnostic (mode, prompt, tool history)
  ACTION_DIAGNOSTIC                  Real structured diagnostic (not prose) — mode, prompt, tool calls, recovery hint
  CLEAR_PROMPT                       Clear any active terminal prompt (stop prompt hijacking)
  RESET_SESSION_STATE                Full session reset to IDLE (preserves tool history)
  STOP ORACLE                        Halt all action, clear prompts, enter SAFE_SLEEP
  SET_MODE BUILD_PASS                Force BUILD_PASS mode
  SET_MODE IDLE                      Force IDLE mode
  /lootdrop                          Show recent LootDrop momentum recap
  /lootdrop <tier> <project> <reason>  Award a LootDrop (tiers: common uncommon rare epic legendary mythic)
  /context                           Show current live operational context state
  /privacy on | /privacy off         Toggle privacy mode (clears buffer, suspends context)
  /pause-context                     Pause context updates without full privacy mode
  /resume-context                    Resume context updates
  /purge-buffer                      Discard live context buffer without approving candidates
  /pending                           List external integration candidates pending approval
  /voice on | /voice off             Toggle voice output (Oracle speaks replies)
  /quit                              Exit

Brain tools (reasoning, files, web):
  read_file / write_file / list_directory
  run_shell       Run a one-off PowerShell command (stateless)
  terminal_run    Run a command in ORACLE's own persistent terminal (state carries between calls)
  terminal_cd     Change directory in the persistent terminal
  terminal_status Check terminal session state
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

        # ── Governance pre-classification ─────────────────────────────────────────
        # Intercept governance, identity, memory, and sovereignty statements before
        # they reach the LLM. The LLM receives governance statements and responds
        # with generic assistant language because it cannot distinguish them from
        # ordinary conversation. identity_compliance.py handles them with precision.
        governance_response = handle_in_repl(user_input)
        if governance_response is not None:
            print(governance_response)
            speak(governance_response)
            continue

        try:
            if local:
                reply, history = chat_local(client, session_id, system_prompt, history, user_input, model)
            else:
                reply, history = chat(client, session_id, system_prompt, history, user_input)
            print(f"\nOracle: {reply}\n")
            speak(reply)
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
                    speak(reply)
                    continue
                except Exception as e2:
                    log("ERROR", f"Retry failed: {e2}")
                    history = []
                    print("\n[Oracle reset its conversation buffer. Memory is intact. Try again.]\n")
            else:
                print(f"\n[Error: {e}]\n")


if __name__ == "__main__":
    main()
