"""
core/oracle_tui.py — ORACLE Split TUI

Two-panel terminal UI:
  TOP    — conversation between Noah and ORACLE (voice + replies)
  BOTTOM — ORACLE's thinking: tool calls, cycle output, background work

Usage:
    python core/oracle_tui.py
    python core/oracle_tui.py --local
"""

from __future__ import annotations

import os
import sys
import threading
from datetime import datetime
from pathlib import Path

if getattr(sys, "frozen", False):
    ROOT = Path(sys.executable).parent
else:
    ROOT = Path(__file__).parent.parent

sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "core"))

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.widgets import RichLog, Input, Label, Footer
from textual.containers import Vertical
from textual import work

# ── Output router ─────────────────────────────────────────────────────────────
# Other modules call print() — we intercept and route to the right panel.

_app_ref: "OracleTUI | None" = None


class _TuiWriter:
    """sys.stdout replacement that routes lines to the correct TUI panel."""

    def __init__(self, original):
        self._orig = original
        self._buf = ""

    def write(self, text: str):
        self._buf += text
        while "\n" in self._buf:
            line, self._buf = self._buf.split("\n", 1)
            self._route(line)

    def flush(self):
        if self._buf:
            self._route(self._buf)
            self._buf = ""
        self._orig.flush()

    def _route(self, line: str):
        if _app_ref is None:
            self._orig.write(line + "\n")
            return
        stripped = _strip_ansi(line)
        # Thinking / background work → bottom panel
        if any(stripped.startswith(p) for p in (
            "[thinking:", "  [thinking:", "[Oracle →", "[cycle", "[self-",
            "[boot", "[session", "[audit", "[ERROR", "[WARN",
            "  [", "Running ", "Refresh", "Dashboard",
        )):
            _app_ref.post_think(stripped)
        # Oracle's spoken reply → top panel (already printed separately)
        elif stripped.startswith("Oracle:"):
            pass  # handled directly by the chat worker
        else:
            # Everything else (boot messages, errors) → bottom
            _app_ref.post_think(stripped)

    # Make it a proper file-like object
    def isatty(self): return False
    def fileno(self): raise OSError
    def readable(self): return False
    def writable(self): return True


def _strip_ansi(text: str) -> str:
    import re
    return re.sub(r"\x1b\[[0-9;]*m", "", text)


# ── TUI App ───────────────────────────────────────────────────────────────────

CSS = """
Screen {
    layers: base;
}

#header-bar {
    height: 1;
    background: $primary-darken-3;
    color: $text-muted;
    padding: 0 1;
}

#convo-label {
    height: 1;
    background: #0a1020;
    color: #00c8ff;
    padding: 0 1;
    text-style: bold;
}

#think-label {
    height: 1;
    background: #0a0a0a;
    color: #444466;
    padding: 0 1;
}

#convo {
    height: 1fr;
    background: #080c18;
    border: tall #1a2a3a;
    padding: 0 1;
    scrollbar-color: #1a2a3a;
}

#think {
    height: 1fr;
    background: #060608;
    border: tall #1a1a2a;
    padding: 0 1;
    scrollbar-color: #1a1a2a;
    color: #555577;
}

#input-bar {
    height: 3;
    background: #060810;
    border: tall #003344;
    padding: 0 1;
    color: #e0f0ff;
}

Vertical {
    height: 100%;
}
"""


class OracleTUI(App):
    CSS = CSS
    BINDINGS = [
        Binding("ctrl+c", "quit", "Quit", show=True),
        Binding("ctrl+l", "clear_think", "Clear thinking panel", show=False),
    ]

    def __init__(self, session_state: dict):
        super().__init__()
        self._ss = session_state  # shared dict: client, session_id, system_prompt, history, local, model

    def compose(self) -> ComposeResult:
        yield Label("  ORACLE  ·  SOVEREIGN OPERATOR LAYER  ·  GOVERNED", id="header-bar")
        with Vertical():
            yield Label("  ◆ CONVERSATION", id="convo-label")
            yield RichLog(id="convo", highlight=False, markup=True, wrap=True, auto_scroll=True)
            yield Label("  ◆ ORACLE THINKING", id="think-label")
            yield RichLog(id="think", highlight=False, markup=True, wrap=True, auto_scroll=True)
            yield Input(placeholder="You: type a message or /help …", id="input-bar")
        yield Footer()

    def on_mount(self) -> None:
        global _app_ref
        _app_ref = self
        self.query_one("#input-bar", Input).focus()
        self._run_boot_cycle()

    def post_convo(self, text: str, style: str = "white") -> None:
        """Write to the conversation panel (thread-safe)."""
        self.call_from_thread(self._write_convo, text, style)

    def post_think(self, text: str) -> None:
        """Write to the thinking panel (thread-safe)."""
        self.call_from_thread(self._write_think, text)

    def _write_convo(self, text: str, style: str = "white") -> None:
        log = self.query_one("#convo", RichLog)
        log.write(f"[{style}]{text}[/{style}]")

    def _write_think(self, text: str) -> None:
        if not text.strip():
            return
        log = self.query_one("#think", RichLog)
        log.write(f"[dim]{text}[/dim]")

    def on_input_submitted(self, event: Input.Submitted) -> None:
        text = event.value.strip()
        if not text:
            return
        event.input.value = ""
        self._handle_input(text)

    def _handle_input(self, text: str) -> None:
        lower = text.lower()

        if lower in ("/quit", "/exit"):
            self._on_quit()
            self.exit()
            return

        if lower in ("/cycle", "/self-prompt"):
            self.post_think("▶ running cycle…")
            threading.Thread(target=self._run_cycle, daemon=True).start()
            return

        _SELF_BUILD_TRIGGERS = {
            "/self-build", "/selfbuild", "build yourself", "build yourself.",
            "improve yourself", "self build", "self-build", "self improve",
            "what should you build", "what should you improve",
        }
        if lower in _SELF_BUILD_TRIGGERS:
            self.post_think("▶ scanning codebase for highest-value improvement…")
            threading.Thread(target=self._run_self_build, daemon=True).start()
            return

        if lower == "/clear":
            self.query_one("#convo", RichLog).clear()
            return

        if lower == "/clear-think":
            self.query_one("#think", RichLog).clear()
            return

        if lower == "/help":
            self.post_convo("[bold cyan]Commands:[/bold cyan]", "white")
            for cmd in [
                "/cycle    — run one governed cycle",
                "/pending  — show pending approvals",
                "/memory   — show memory snapshot",
                "/voice on | off — toggle voice",
                "/claude <question> — ask Claude Code (code/build questions)",
                "/cc       — open interactive Claude Code session",
                "/clear    — clear conversation",
                "/quit     — exit",
            ]:
                self.post_convo(f"  [dim]{cmd}[/dim]", "white")
            return

        # /claude <question> — non-interactive ask to Claude Code
        if lower.startswith("/claude "):
            question = text[8:].strip()
            if question:
                self.post_think("▶ routing to Claude Code…")
                threading.Thread(
                    target=self._ask_claude_code, args=(question,), daemon=True
                ).start()
            else:
                self.post_convo("[yellow]Usage: /claude <your question>[/yellow]")
            return

        # /cc — open interactive Claude Code session
        if lower in ("/cc", "/claude-code", "/open-claude"):
            self.post_think("▶ opening Claude Code session…")
            threading.Thread(target=self._open_claude_session, daemon=True).start()
            return

        # Show Noah's message
        ts = datetime.now().strftime("%H:%M")
        self.post_convo(f"[dim]{ts}[/dim]  [bold white]You:[/bold white] {text}")

        # Auto-route code tasks to Claude Code, everything else to local model
        try:
            from claude_code_bridge import is_code_task
            if is_code_task(text):
                self.post_think("▶ code task detected — routing to Claude Code…")
                threading.Thread(
                    target=self._ask_claude_code, args=(text,), daemon=True
                ).start()
                return
        except Exception:
            pass

        # Send to ORACLE in background thread
        threading.Thread(target=self._chat, args=(text,), daemon=True).start()

    def _chat(self, user_input: str) -> None:
        ss = self._ss
        try:
            self.post_think(f"▶ {user_input[:60]}")
            if ss["local"]:
                from oracle import chat_local
                reply, ss["history"] = chat_local(
                    ss["client"], ss["session_id"], ss["system_prompt"],
                    ss["history"], user_input, ss["model"]
                )
            else:
                from oracle import chat
                reply, ss["history"] = chat(
                    ss["client"], ss["session_id"], ss["system_prompt"],
                    ss["history"], user_input, ss["model"]
                )
            ts = datetime.now().strftime("%H:%M")
            self.post_convo(f"[dim]{ts}[/dim]  [bold cyan]Oracle:[/bold cyan] {reply}")
            # Voice
            try:
                from voice import speak
                speak(reply)
            except Exception:
                pass
        except Exception as e:
            self.post_convo(f"[red]Error: {e}[/red]")
            self.post_think(f"chat error: {e}")

    def _ask_claude_code(self, prompt: str) -> None:
        try:
            from claude_code_bridge import ask_claude
            ok, reply = ask_claude(prompt)
            ts = datetime.now().strftime("%H:%M")
            label = "[bold green]Claude Code:[/bold green]" if ok else "[bold red]Claude Code error:[/bold red]"
            self.post_convo(f"[dim]{ts}[/dim]  {label} {reply}")
            try:
                from voice import speak
                speak(reply[:300])  # cap TTS length for long code answers
            except Exception:
                pass
        except Exception as e:
            self.post_convo(f"[red]Claude Code bridge error: {e}[/red]")

    def _open_claude_session(self) -> None:
        try:
            from claude_code_bridge import open_claude_session
            ok, detail = open_claude_session(
                prompt="ORACLE is handing off to you. What's the status of the MYTHIC BUILD PASS and what should we work on next?",
            )
            self.post_convo(
                f"[bold green]Claude Code session opened.[/bold green] {detail}"
                if ok else f"[red]{detail}[/red]"
            )
        except Exception as e:
            self.post_convo(f"[red]Could not open Claude Code session: {e}[/red]")

    def _run_boot_cycle(self) -> None:
        threading.Thread(target=self._boot_cycle_thread, daemon=True).start()

    def _boot_cycle_thread(self) -> None:
        try:
            from oracle_runtime import run_cycle, MODE_DAEMON_SAFE
            self.post_think("▶ boot cycle starting…")
            r = run_cycle(mode=MODE_DAEMON_SAFE)
            priority = r.selected_priority or "maintenance"
            action   = (r.action_taken or "")[:100]
            next_s   = (r.next_recommended_step or "")[:100]
            conf     = int(r.confidence * 100)

            self.post_think(f"◆ {priority}  {conf}%")
            if action:
                self.post_think(f"  {action}")
            if next_s:
                marker = "▶ ACTION NEEDED:" if r.approval_required else "Next:"
                self.post_think(f"  {marker} {next_s}")

            if r.approval_required:
                self.post_convo(f"[bold yellow]◆ ACTION NEEDED:[/bold yellow] [dim]{next_s}[/dim]")
                try:
                    from voice import speak_prompt
                    speak_prompt(f"I'm up. {action[:60]}")
                except Exception:
                    pass
            else:
                try:
                    from voice import speak_prompt
                    speak_prompt("I'm up.")
                except Exception:
                    pass
        except Exception as e:
            self.post_think(f"boot cycle error: {e}")

    def _run_cycle(self) -> None:
        try:
            from oracle_runtime import run_cycle, MODE_MANUAL
            r = run_cycle(mode=MODE_MANUAL)
            priority = r.selected_priority or "maintenance"
            action   = (r.action_taken or "")[:100]
            next_s   = (r.next_recommended_step or "")[:100]
            conf     = int(r.confidence * 100)
            self.post_think(f"◆ CYCLE  {priority}  {conf}%")
            if action:
                self.post_think(f"  {action}")
            if next_s:
                marker = "▶ ACTION NEEDED:" if r.approval_required else "Next:"
                self.post_think(f"  {marker} {next_s}")
            if r.approval_required:
                self.post_convo(f"[bold yellow]◆ ACTION NEEDED:[/bold yellow] [dim]{next_s}[/dim]")
        except Exception as e:
            self.post_think(f"cycle error: {e}")

    def _run_self_build(self) -> None:
        try:
            from self_build import run_self_build
            ss = self._ss
            result = run_self_build(ss["client"], ss["model"], ss["local"], implement=False)
            # Split at TITLE for a clean convo-panel summary
            if "TITLE" in result:
                title_line = [l for l in result.splitlines() if "TITLE" in l]
                summary = title_line[0].replace("TITLE", "").replace(":", "").strip() if title_line else ""
                self.post_convo(f"[bold cyan]◆ SELF-BUILD PROPOSAL:[/bold cyan] [dim]{summary}[/dim]")
            self.post_think(result)
        except Exception as e:
            self.post_think(f"self-build error: {e}")

    def action_clear_think(self) -> None:
        self.query_one("#think", RichLog).clear()

    def _on_quit(self) -> None:
        try:
            from project_state import load_state, save_state
            from datetime import datetime, timezone
            ps = load_state("ORACLE.AI")
            if ps:
                ps.lessons_learned.append(
                    f"[session] oracle_tui session ended {datetime.now(timezone.utc).isoformat()[:16]} UTC"
                )
                ps.lessons_learned = ps.lessons_learned[-40:]
                save_state(ps)
        except Exception:
            pass
        try:
            from voice import shutdown as voice_shutdown
            voice_shutdown()
        except Exception:
            pass


# ── Entry point ───────────────────────────────────────────────────────────────

def main():
    os.chdir(Path(__file__).parent)

    from memory import init_db, new_session
    from llm import is_local, make_client, get_model
    from context_loader import build_system_prompt

    init_db()
    session_id = new_session()
    local = is_local()

    try:
        client = make_client()
    except RuntimeError as e:
        print(f"ERROR: {e}")
        sys.exit(1)

    model = get_model(vision=False)
    system_prompt = build_system_prompt(local=local)

    from live_context import get_live_context
    get_live_context().set_task("TUI session")

    # Intercept stdout so print() calls route to the right panel
    sys.stdout = _TuiWriter(sys.__stdout__)

    session_state = {
        "client": client,
        "session_id": session_id,
        "system_prompt": system_prompt,
        "history": [],
        "local": local,
        "model": model,
    }

    app = OracleTUI(session_state)
    app.run()


if __name__ == "__main__":
    main()
