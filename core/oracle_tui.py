"""
core/oracle_tui.py — ORACLE Split TUI  (v3)

Layout:
  TOP BAR   — live status: loop state · mode · pending · clock
  LEFT      — conversation (top) + thinking (bottom)
  RIGHT     — system state: memory / lessons / loop / last experience
  BOTTOM    — input bar

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
from textual.widgets import RichLog, Input, Label, Footer, Static
from textual.containers import Vertical, Horizontal
from textual.reactive import reactive
from textual import work

# ── ANSI strip ─────────────────────────────────────────────────────────────────

import re as _re

def _strip_ansi(text: str) -> str:
    return _re.sub(r"\x1b\[[0-9;]*m", "", text)


# ── Output router ──────────────────────────────────────────────────────────────

_app_ref: "OracleTUI | None" = None


class _TuiWriter:
    """sys.stdout replacement — routes print() lines to the correct TUI panel."""

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
        if any(stripped.startswith(p) for p in (
            "[thinking:", "  [thinking:", "[Oracle →", "[cycle",
            "[self-", "[boot", "[session", "[audit", "[ERROR", "[WARN",
            "  [", "Running ", "Refresh", "Dashboard",
        )):
            _app_ref.post_think(stripped)
        elif stripped.startswith("Oracle:"):
            pass
        else:
            _app_ref.post_think(stripped)

    def isatty(self): return False
    def fileno(self): raise OSError
    def readable(self): return False
    def writable(self): return True


# ── Source chips ───────────────────────────────────────────────────────────────

_CHIP = {
    "local":      "[bold white on #1a1a3a] LOCAL [/bold white on #1a1a3a]",
    "claude":     "[bold black on #00c844] CLAUDE CODE [/bold black on #00c844]",
    "governance": "[bold black on #c87800] GOVERNANCE [/bold black on #c87800]",
    "memory":     "[bold white on #1a2a44] MEMORY [/bold white on #1a2a44]",
    "blocked":    "[bold white on #aa0000] BLOCKED [/bold white on #aa0000]",
    "experience": "[bold black on #886600] LESSON [/bold black on #886600]",
    "system":     "[bold white on #1a3a1a] SYSTEM [/bold white on #1a3a1a]",
    "loop":       "[bold black on #006688] LOOP [/bold black on #006688]",
}

def _chip(key: str, ts: str, body: str) -> str:
    return f"{_CHIP[key]} [dim]{ts}[/dim]  {body}"


# ── Implementation response guard ──────────────────────────────────────────────

_IMPL_PATTERNS = [
    "def ", "class ", "```python", "```\npython", "i'll create", "i'll implement",
    "here's the implementation", "i'll write", "i'll add", "i'll build",
    "touch core/", "## step", "# step 1",
]

def _is_impl_response(text: str) -> bool:
    lower = text.lower()
    return any(p.lower() in lower for p in _IMPL_PATTERNS)


# ── Status bar widget ──────────────────────────────────────────────────────────

class StatusBar(Static):
    """Top bar — refreshes every 2 seconds."""

    DEFAULT_CSS = """
    StatusBar {
        height: 1;
        background: #050810;
        color: #334466;
        padding: 0 1;
    }
    """

    def on_mount(self) -> None:
        self.set_interval(2.0, self.refresh_status)
        self.refresh_status()

    def refresh_status(self) -> None:
        parts = []

        # Loop state
        try:
            from oracle_loop import is_running, loop_status
            if is_running():
                parts.append("[bold cyan]◉ LOOP ON[/bold cyan]")
            else:
                parts.append("[dim]◌ LOOP OFF[/dim]")
        except Exception:
            parts.append("[dim]LOOP ?[/dim]")

        # Mode
        try:
            from llm import is_local, get_model
            mode = "LOCAL" if is_local() else "CLOUD"
            model = get_model(vision=False) or ""
            short = model.split("/")[-1][:16] if "/" in model else model[:16]
            col = "yellow" if mode == "LOCAL" else "green"
            parts.append(f"[{col}]{mode}[/{col}] [dim]{short}[/dim]")
        except Exception:
            parts.append("[dim]MODE ?[/dim]")

        # Pending
        try:
            from action_candidates import list_active
            pend = len(list_active())
            if pend:
                parts.append(f"[bold yellow]⚑ PENDING {pend}[/bold yellow]")
            else:
                parts.append("[dim]◆ NO PENDING[/dim]")
        except Exception:
            pass

        # Memory count
        try:
            from light_compression import list_memories
            n = len(list_memories())
            parts.append(f"[dim]MEM {n}[/dim]")
        except Exception:
            pass

        # Experience count
        try:
            from experience_compression import list_experiences
            n = len(list_experiences(limit=999))
            parts.append(f"[dim]EXP {n}[/dim]")
        except Exception:
            pass

        # Clock
        ts = datetime.now().strftime("%H:%M")
        parts.append(f"[dim]{ts}[/dim]")

        sep = "  [dim]│[/dim]  "
        self.update("  " + sep.join(parts))


# ── System state sidebar ───────────────────────────────────────────────────────

class SystemPanel(RichLog):
    """Right sidebar — operator state, lessons, loop info."""

    DEFAULT_CSS = """
    SystemPanel {
        background: #04060c;
        border: tall #0a0f1a;
        padding: 0 1;
        color: #334466;
        scrollbar-color: #0a0f1a;
    }
    """

    def on_mount(self) -> None:
        self.set_interval(5.0, self.refresh_panel)
        self.refresh_panel()

    def refresh_panel(self) -> None:
        self.clear()
        self._section("◆ SYSTEM STATE")

        # Mode / model
        try:
            from llm import is_local, get_model
            mode = "LOCAL" if is_local() else "CLOUD"
            model = (get_model(vision=False) or "?").split("/")[-1][:20]
            col = "yellow" if mode == "LOCAL" else "green"
            self.write(f"  Mode   [{col}]{mode}[/{col}] [dim]{model}[/dim]")
        except Exception:
            pass

        # Loop
        try:
            from oracle_loop import is_running, _stats
            state = "[bold cyan]RUNNING[/bold cyan]" if is_running() else "[dim]stopped[/dim]"
            sent  = _stats.get("tasks_sent", 0)
            resp  = _stats.get("responses_read", 0)
            self.write(f"  Loop   {state}")
            if sent:
                self.write(f"  [dim]  tasks {sent}  resp {resp}[/dim]")
        except Exception:
            pass

        # Pending
        try:
            from action_candidates import list_active
            items = list_active()
            col = "yellow" if items else "dim"
            self.write(f"  [{col}]Pending  {len(items)}[/{col}]")
        except Exception:
            pass

        # Memory
        try:
            from light_compression import list_memories
            mems = list_memories()
            self.write(f"  [dim]Memory   {len(mems)} items[/dim]")
        except Exception:
            pass

        # Experiences / lessons
        try:
            from experience_compression import list_experiences, OUTCOME_FAILURE, OUTCOME_SUCCESS
            all_e  = list_experiences(limit=999)
            fails  = [e for e in all_e if e.outcome == OUTCOME_FAILURE]
            wins   = [e for e in all_e if e.outcome == OUTCOME_SUCCESS]
            self.write(f"  [dim]Lessons  {len(all_e)}  "
                       f"[red]✗{len(fails)}[/red] [green]✓{len(wins)}[/green][/dim]")
        except Exception:
            pass

        self.write("")
        self._section("◆ TOP LESSONS")

        try:
            from experience_compression import recall_lessons
            for e in recall_lessons("", min_conf=0.7, top_k=6):
                icon = "[red]✗[/red]" if "fail" in e.outcome or "block" in e.outcome else "[green]✓[/green]"
                self.write(f"  {icon} [dim]{e.lesson[:42]}[/dim]")
        except Exception:
            self.write("  [dim]none yet[/dim]")

        self.write("")
        self._section("◆ LAST EXPERIENCE")
        try:
            from experience_compression import list_experiences
            recent = list_experiences(limit=1)
            if recent:
                e = recent[0]
                self.write(f"  [dim]{e.domain.upper()}[/dim]")
                self.write(f"  [dim]{e.observation[:44]}[/dim]")
                self.write(f"  [dim]→ {e.lesson[:44]}[/dim]")
        except Exception:
            pass

    def _section(self, title: str) -> None:
        self.write(f"[bold #334466]{title}[/bold #334466]")


# ── Main TUI App ───────────────────────────────────────────────────────────────

CSS = """
Screen {
    layers: base;
}

#main-row {
    height: 1fr;
}

#left-col {
    width: 3fr;
    height: 100%;
}

#right-col {
    width: 28;
    height: 100%;
}

#convo-label {
    height: 1;
    background: #080c18;
    color: #0088cc;
    padding: 0 1;
    text-style: bold;
}

#think-label {
    height: 1;
    background: #05070d;
    color: #223344;
    padding: 0 1;
}

#convo {
    height: 1fr;
    background: #070b16;
    border: tall #101828;
    padding: 0 1;
    scrollbar-color: #101828;
}

#think {
    height: 12;
    background: #040608;
    border: tall #0d0d1a;
    padding: 0 1;
    scrollbar-color: #0d0d1a;
    color: #334466;
}

#system-label {
    height: 1;
    background: #030508;
    color: #223344;
    padding: 0 1;
}

SystemPanel {
    height: 1fr;
}

#input-bar {
    height: 3;
    background: #050810;
    border: tall #002233;
    padding: 0 1;
    color: #c0d8f0;
}

Footer {
    background: #030508;
    color: #223344;
}
"""


class OracleTUI(App):
    CSS = CSS
    BINDINGS = [
        Binding("ctrl+c",  "quit",         "Quit",           show=True),
        Binding("ctrl+l",  "clear_think",  "Clear thinking", show=False),
        Binding("ctrl+r",  "refresh_sys",  "Refresh state",  show=False),
        Binding("ctrl+p",  "show_pending", "Pending",        show=False),
    ]

    def __init__(self, session_state: dict):
        super().__init__()
        self._ss = session_state

    def compose(self) -> ComposeResult:
        yield StatusBar(id="status-bar")
        with Horizontal(id="main-row"):
            with Vertical(id="left-col"):
                yield Label("  ◆ ORACLE  ·  CONVERSATION", id="convo-label")
                yield RichLog(id="convo", highlight=False, markup=True,
                              wrap=True, auto_scroll=True)
                yield Label("  ◆ THINKING", id="think-label")
                yield RichLog(id="think", highlight=False, markup=True,
                              wrap=True, auto_scroll=True)
            with Vertical(id="right-col"):
                yield Label("  ◆ STATE", id="system-label")
                yield SystemPanel(id="system", highlight=False, markup=True,
                                  wrap=True, auto_scroll=False)
        yield Input(placeholder="You:  type freely, use /help for commands …",
                    id="input-bar")
        yield Footer()

    def on_mount(self) -> None:
        global _app_ref
        _app_ref = self
        self.query_one("#input-bar", Input).focus()
        self._run_boot_cycle()

    # ── Thread-safe write helpers ──────────────────────────────────────────────

    def post_convo(self, text: str) -> None:
        self.call_from_thread(self._write_convo, text)

    def post_think(self, text: str) -> None:
        self.call_from_thread(self._write_think, text)

    def _write_convo(self, text: str) -> None:
        self.query_one("#convo", RichLog).write(text)

    def _write_think(self, text: str) -> None:
        if not text.strip():
            return
        self.query_one("#think", RichLog).write(f"[dim]{text}[/dim]")

    def _refresh_sys(self) -> None:
        try:
            self.query_one(SystemPanel).refresh_panel()
        except Exception:
            pass

    # ── Input handling ─────────────────────────────────────────────────────────

    def on_input_submitted(self, event: Input.Submitted) -> None:
        text = event.value.strip()
        if not text:
            return
        event.input.value = ""
        self._handle_input(text)

    def _handle_input(self, raw: str) -> None:  # noqa: C901
        lower = raw.lower().strip()
        ts = datetime.now().strftime("%H:%M")

        # ── Hard commands ──────────────────────────────────────────────────────
        if lower in ("/quit", "/exit"):
            self._on_quit()
            self.exit()
            return

        if lower in ("/clear",):
            self.query_one("#convo", RichLog).clear()
            return

        if lower in ("/clear-think", "/ct"):
            self.query_one("#think", RichLog).clear()
            return

        if lower in ("/help",):
            self._show_help()
            return

        if lower in ("/cycle", "/self-prompt"):
            self.post_think("▶ running cycle…")
            threading.Thread(target=self._run_cycle, daemon=True).start()
            return

        if lower in ("/loop", "/loop status"):
            try:
                from oracle_loop import loop_status
                self.post_convo(_chip("loop", ts, f"[cyan]{loop_status()}[/cyan]"))
            except Exception as e:
                self.post_convo(f"[red]loop status error: {e}[/red]")
            return

        if lower in ("/loop on", "loop on", "start loop", "loop start"):
            try:
                from oracle_loop import loop_start, set_callbacks
                from voice import speak
                set_callbacks(self.post_think, speak)
                loop_start()
                self.post_convo(_chip("loop", ts, "[bold cyan]Autonomous loop started.[/bold cyan]"))
            except Exception as e:
                self.post_convo(f"[red]loop start error: {e}[/red]")
            return

        if lower in ("/loop off", "loop off", "stop loop", "loop stop"):
            try:
                from oracle_loop import loop_stop
                loop_stop()
                self.post_convo(_chip("loop", ts, "[dim]Loop stopped.[/dim]"))
            except Exception as e:
                self.post_convo(f"[red]loop stop error: {e}[/red]")
            return

        if lower in ("/pending",):
            threading.Thread(target=self._show_pending, daemon=True).start()
            return

        if lower in ("/lessons",):
            threading.Thread(target=self._show_lessons, daemon=True).start()
            return

        if lower in ("/memory",):
            threading.Thread(target=self._show_memory, daemon=True).start()
            return

        if lower in ("/voice on",):
            try:
                from voice import set_voice_enabled
                set_voice_enabled(True)
                self.post_convo(_chip("system", ts, "[green]Voice enabled.[/green]"))
            except Exception as e:
                self.post_convo(f"[red]{e}[/red]")
            return

        if lower in ("/voice off",):
            try:
                from voice import set_voice_enabled
                set_voice_enabled(False)
                self.post_convo(_chip("system", ts, "[dim]Voice disabled.[/dim]"))
            except Exception as e:
                self.post_convo(f"[red]{e}[/red]")
            return

        _SELF_BUILD = {
            "/self-build", "/selfbuild", "build yourself", "improve yourself",
            "self build", "self-build", "self improve",
            "what should you build", "what should you improve",
        }
        if lower in _SELF_BUILD:
            self.post_think("▶ scanning codebase for highest-value improvement…")
            threading.Thread(target=self._run_self_build, daemon=True).start()
            return

        # /claude <question> — non-interactive ask
        if lower.startswith("/claude "):
            question = raw[8:].strip()
            if question:
                self.post_think(f"▶ routing to Claude Code: {question[:50]}")
                threading.Thread(target=self._ask_claude_code, args=(question,), daemon=True).start()
            else:
                self.post_convo("[yellow]Usage: /claude <question>[/yellow]")
            return

        # /cc — open interactive session
        if lower in ("/cc", "/claude-code", "/open-claude"):
            self.post_think("▶ opening Claude Code session…")
            threading.Thread(target=self._open_claude_session, daemon=True).start()
            return

        # ── Show Noah's message ────────────────────────────────────────────────
        self.post_convo(f"[dim]{ts}[/dim]  [bold white]You:[/bold white] {raw}")

        # ── Auto-route to Claude Code ──────────────────────────────────────────
        try:
            from claude_code_bridge import is_claude_directed, is_code_task
            if is_claude_directed(raw):
                self.post_convo(_chip("governance", ts, "[green]↗ Routing to Claude Code…[/green]"))
                self.post_think("▶ Claude-directed — routing to Claude Code window")
                threading.Thread(target=self._type_into_claude, args=(raw,), daemon=True).start()
                return
            if is_code_task(raw):
                self.post_convo(_chip("governance", ts, "[green]↗ Code task — handing off to Claude Code…[/green]"))
                self.post_think("▶ code task — handing off to Claude Code window")
                threading.Thread(target=self._type_into_claude, args=(raw,), daemon=True).start()
                return
        except Exception as e:
            self.post_think(f"[WARN] bridge routing: {e}")

        # ── Local ORACLE ───────────────────────────────────────────────────────
        threading.Thread(target=self._chat, args=(raw,), daemon=True).start()

    # ── Chat worker ────────────────────────────────────────────────────────────

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

            if _is_impl_response(reply):
                self.post_convo(
                    _chip("governance", ts,
                          "[yellow]⚠ Local model attempted implementation — re-routing to Claude Code.[/yellow]")
                )
                self.post_think("▶ post-LLM guard: implementation detected — routing to Claude Code")
                threading.Thread(target=self._ask_claude_code, args=(user_input,), daemon=True).start()
                return

            self.post_convo(_chip("local", ts, f"[bold cyan]Oracle:[/bold cyan]  {reply}"))
            try:
                from voice import speak
                speak(reply)
            except Exception:
                pass
            self.call_from_thread(self._refresh_sys)
        except Exception as e:
            self.post_convo(f"[red]Error: {e}[/red]")
            self.post_think(f"chat error: {e}")

    # ── Claude Code workers ────────────────────────────────────────────────────

    def _ask_claude_code(self, prompt: str) -> None:
        try:
            from claude_code_bridge import ask_claude, contains_secret, scrub_secrets
            ok, reply = ask_claude(prompt)
            ts = datetime.now().strftime("%H:%M")
            if contains_secret(reply):
                self.post_convo(_chip("blocked", ts,
                    "[bold red]Response contained secret pattern — redacted.[/bold red]"))
                reply = scrub_secrets(reply)
            body = f"[bold green]{reply}[/bold green]" if ok else f"[red]{reply}[/red]"
            self.post_convo(_chip("claude", ts, body))
            try:
                from voice import speak
                speak(reply[:300])
            except Exception:
                pass
        except Exception as e:
            self.post_convo(f"[red]Claude Code bridge error: {e}[/red]")

    def _type_into_claude(self, prompt: str) -> None:
        try:
            from claude_code_bridge import type_into_claude
            ok, detail = type_into_claude(prompt, open_if_missing=True)
            ts = datetime.now().strftime("%H:%M")
            if ok:
                self.post_convo(_chip("claude", ts,
                    f"[bold green]↗ Handed off to Claude Code.[/bold green]  [dim]{detail}[/dim]"))
                try:
                    from voice import speak
                    speak("Handed off to Claude Code.")
                except Exception:
                    pass
            else:
                self.post_convo(_chip("governance", ts,
                    f"[yellow]Claude Code hand-off failed: {detail}[/yellow]"))
        except Exception as e:
            self.post_convo(f"[red]type_into_claude error: {e}[/red]")

    def _open_claude_session(self) -> None:
        try:
            from claude_code_bridge import open_claude_session
            ok, detail = open_claude_session(
                prompt="ORACLE is handing off to you. What's the status of the current build and what should we work on next?",
            )
            ts = datetime.now().strftime("%H:%M")
            chip = "claude" if ok else "governance"
            body = f"[bold green]Claude Code session opened.[/bold green] [dim]{detail}[/dim]" \
                   if ok else f"[red]{detail}[/red]"
            self.post_convo(_chip(chip, ts, body))
        except Exception as e:
            self.post_convo(f"[red]Could not open Claude Code session: {e}[/red]")

    # ── Inline display helpers ─────────────────────────────────────────────────

    def _show_pending(self) -> None:
        ts = datetime.now().strftime("%H:%M")
        try:
            from action_candidates import list_active
            items = list_active()
            if not items:
                self.post_convo(_chip("governance", ts, "[dim]No pending candidates.[/dim]"))
                return
            self.post_convo(_chip("governance", ts,
                f"[bold yellow]{len(items)} pending:[/bold yellow]"))
            for c in items[:10]:
                label = getattr(c, "title", None) or getattr(c, "action", str(c))[:60]
                self.post_convo(f"  [dim]·[/dim] [yellow]{label}[/yellow]")
        except Exception as e:
            self.post_convo(f"[red]pending error: {e}[/red]")

    def _show_lessons(self) -> None:
        ts = datetime.now().strftime("%H:%M")
        try:
            from experience_compression import recall_lessons
            hits = recall_lessons("", min_conf=0.5, top_k=10)
            if not hits:
                self.post_convo(_chip("experience", ts, "[dim]No lessons recorded yet.[/dim]"))
                return
            self.post_convo(_chip("experience", ts, f"[bold]{len(hits)} lessons:[/bold]"))
            for e in hits:
                icon = "[red]✗[/red]" if "fail" in e.outcome or "block" in e.outcome else "[green]✓[/green]"
                self.post_convo(
                    f"  {icon} [dim]{e.domain:10}[/dim] conf={e.confidence:.0%}  {e.lesson[:70]}"
                )
        except Exception as e:
            self.post_convo(f"[red]lessons error: {e}[/red]")

    def _show_memory(self) -> None:
        ts = datetime.now().strftime("%H:%M")
        try:
            from light_compression import list_memories
            items = list_memories()
            if not items:
                self.post_convo(_chip("memory", ts, "[dim]No memories stored.[/dim]"))
                return
            self.post_convo(_chip("memory", ts, f"[bold]{len(items)} memories:[/bold]"))
            for m in items[:12]:
                self.post_convo(
                    f"  [dim]{getattr(m, 'memory_type', '?'):12}[/dim]  {(m.compressed or m.raw_signal or '')[:70]}"
                )
        except Exception as e:
            self.post_convo(f"[red]memory error: {e}[/red]")

    def _show_help(self) -> None:
        self.post_convo("[bold cyan]◆ ORACLE COMMANDS[/bold cyan]")
        cmds = [
            ("/cycle           ", "run one governed cycle"),
            ("/pending         ", "show pending approvals"),
            ("/lessons         ", "show top experience lessons"),
            ("/memory          ", "show compressed memory"),
            ("/loop            ", "show loop status"),
            ("/loop on|off     ", "start or stop autonomous loop"),
            ("/voice on|off    ", "toggle voice output"),
            ("/claude <q>      ", "ask Claude Code (non-interactive)"),
            ("/cc              ", "open interactive Claude Code session"),
            ("/self-build      ", "generate self-improvement proposal"),
            ("/clear           ", "clear conversation panel"),
            ("/clear-think     ", "clear thinking panel"),
            ("Ctrl+R           ", "force refresh system state panel"),
            ("Ctrl+P           ", "show pending (shortcut)"),
            ("/quit            ", "exit"),
        ]
        for cmd, desc in cmds:
            self.post_convo(f"  [bold white]{cmd}[/bold white]  [dim]{desc}[/dim]")

    # ── Boot & cycle workers ───────────────────────────────────────────────────

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
            self.post_think(f"◆ boot  {priority}  {conf}%")
            if action:
                self.post_think(f"  {action}")
            if next_s:
                marker = "▶ ACTION NEEDED:" if r.approval_required else "Next:"
                self.post_think(f"  {marker} {next_s}")
            if r.approval_required:
                ts = datetime.now().strftime("%H:%M")
                self.post_convo(_chip("governance", ts,
                    f"[bold yellow]◆ ACTION NEEDED:[/bold yellow] [dim]{next_s}[/dim]"))
            try:
                from voice import speak_prompt
                speak_prompt("I'm up." if not r.approval_required else f"I'm up. {action[:60]}")
            except Exception:
                pass
            self.call_from_thread(self._refresh_sys)
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
            ts = datetime.now().strftime("%H:%M")
            self.post_think(f"◆ CYCLE  {priority}  {conf}%")
            if action:
                self.post_think(f"  {action}")
            if next_s:
                marker = "▶ ACTION NEEDED:" if r.approval_required else "Next:"
                self.post_think(f"  {marker} {next_s}")
            if r.approval_required:
                self.post_convo(_chip("governance", ts,
                    f"[bold yellow]◆ ACTION NEEDED:[/bold yellow] [dim]{next_s}[/dim]"))
            self.call_from_thread(self._refresh_sys)
        except Exception as e:
            self.post_think(f"cycle error: {e}")

    def _run_self_build(self) -> None:
        try:
            from self_build import run_self_build
            ss = self._ss
            result = run_self_build(ss["client"], ss["model"], ss["local"], implement=False)
            ts = datetime.now().strftime("%H:%M")
            if "TITLE" in result:
                line = next((l for l in result.splitlines() if "TITLE" in l), "")
                summary = line.replace("TITLE", "").replace(":", "").strip()
                self.post_convo(_chip("local", ts,
                    f"[bold cyan]◆ SELF-BUILD PROPOSAL:[/bold cyan] [dim]{summary}[/dim]"))
            self.post_think(result)
        except Exception as e:
            self.post_think(f"self-build error: {e}")

    # ── Actions (keyboard bindings) ────────────────────────────────────────────

    def action_clear_think(self) -> None:
        self.query_one("#think", RichLog).clear()

    def action_refresh_sys(self) -> None:
        try:
            self.query_one(SystemPanel).refresh_panel()
        except Exception:
            pass

    def action_show_pending(self) -> None:
        threading.Thread(target=self._show_pending, daemon=True).start()

    # ── Quit ──────────────────────────────────────────────────────────────────

    def _on_quit(self) -> None:
        try:
            from project_state import load_state, save_state
            from datetime import datetime, timezone
            ps = load_state("ORACLE.AI")
            if ps:
                ps.lessons_learned.append(
                    f"[session] oracle_tui v3 ended {datetime.now(timezone.utc).isoformat()[:16]} UTC"
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

    sys.stdout = _TuiWriter(sys.__stdout__)

    session_state = {
        "client":        client,
        "session_id":    session_id,
        "system_prompt": system_prompt,
        "history":       [],
        "local":         local,
        "model":         model,
    }

    app = OracleTUI(session_state)
    app.run()


if __name__ == "__main__":
    main()
