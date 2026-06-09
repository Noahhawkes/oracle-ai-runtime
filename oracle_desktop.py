#!/usr/bin/env python3
"""
ORACLE Desktop Console
Tkinter wrapper around core/oracle.py — provides a clean desktop interface
while keeping core/oracle.py as the active runtime backend.

Launch: python oracle_desktop.py  (from the ORACLE.AI project root)
"""

import os
import sys
import re
import threading
import queue
import time
import subprocess
from pathlib import Path
import tkinter as tk
from tkinter import scrolledtext, ttk, font as tkfont

# ── Path setup ─────────────────────────────────────────────────────────────
ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "core"))

# ── ANSI strip ─────────────────────────────────────────────────────────────
_ANSI_RE = re.compile(r"\x1b\[[0-9;]*[mA-Za-z]|\x1b\][^\x07]*\x07")

def _strip_ansi(text: str) -> str:
    return _ANSI_RE.sub("", text)

# ── Source label colors ────────────────────────────────────────────────────
_LABEL_COLORS: dict[str, str] = {
    "[CHAT]":             "#5bc0f8",
    "[WORK]":             "#a0d8a0",
    "[BUILD]":            "#f0c040",
    "[LOCAL]":            "#888888",
    "[DIAGNOSTIC]":       "#f0a000",
    "[BLOCKED]":          "#e05050",
    "[CLAUDE CODE]":      "#68d468",
    "[CLAUDE DESKTOP]":   "#68d468",
    "[CLAUDE UNAVAILABLE]": "#e05050",
    "[GOVERNANCE]":       "#c0c000",
    "[HANDS]":            "#c080ff",
    "[MEMORY]":           "#80c0ff",
    "[GIT]":              "#88aacc",
    "You:":               "#cccccc",
    "[ERROR]":            "#e05050",
}

# ─────────────────────────────────────────────────────────────────────────────
# OracleProcess — subprocess wrapper that drives core/oracle.py
# ─────────────────────────────────────────────────────────────────────────────

class OracleProcess:
    """
    Runs oracle.py as a subprocess, pipes stdin/stdout.
    Output lines are pushed onto self.output_q.
    Status lines ([STATUS] key=value ...) are parsed separately.
    """

    def __init__(self):
        self.output_q: queue.Queue[str] = queue.Queue()
        self.proc: subprocess.Popen | None = None
        self._reader_thread: threading.Thread | None = None
        self._running = False
        self.last_status: dict = {
            "mode": "LOCAL",
            "claude_window": False,
            "claude_cli": False,
            "hands_ready": True,
            "memory_connected": True,
            "pending": 0,
            "model": "qwen2.5:7b",
        }

    def start(self):
        """Launch oracle.py subprocess."""
        env = os.environ.copy()
        env["LOCAL_MODE"] = "true"
        env["PYTHONIOENCODING"] = "utf-8"
        env["PYTHONUNBUFFERED"] = "1"

        self.proc = subprocess.Popen(
            [sys.executable, "-u", str(ROOT / "core" / "oracle.py")],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            env=env,
            cwd=str(ROOT),
            text=True,
            encoding="utf-8",
            errors="replace",
            bufsize=1,
        )
        self._running = True
        self._reader_thread = threading.Thread(
            target=self._read_loop, daemon=True
        )
        self._reader_thread.start()

    def send(self, text: str):
        """Send a line to oracle stdin."""
        if self.proc and self.proc.poll() is None:
            try:
                self.proc.stdin.write(text + "\n")
                self.proc.stdin.flush()
            except BrokenPipeError:
                pass

    def stop(self):
        self._running = False
        if self.proc:
            try:
                self.send("/quit")
                self.proc.wait(timeout=3)
            except Exception:
                self.proc.terminate()

    def _read_loop(self):
        assert self.proc is not None
        for line in self.proc.stdout:
            if not self._running:
                break
            clean = _strip_ansi(line.rstrip())
            # Parse [STATUS] lines for the panel — don't show them in chat
            if clean.startswith("[STATUS]"):
                self._parse_status(clean)
                continue
            self.output_q.put(clean)
        self.output_q.put("[ORACLE OFFLINE]")

    def _parse_status(self, line: str):
        """Parse: [STATUS] mode=LOCAL claude_window=True pending=3 ..."""
        parts = line[len("[STATUS]"):].strip().split()
        for p in parts:
            if "=" in p:
                k, _, v = p.partition("=")
                if v in ("True", "False"):
                    self.last_status[k] = (v == "True")
                elif v.isdigit():
                    self.last_status[k] = int(v)
                else:
                    self.last_status[k] = v

    def refresh_status(self):
        """Re-import oracle and pull a fresh status snapshot."""
        try:
            from core.oracle import get_oracle_status
            self.last_status = get_oracle_status()
        except Exception:
            pass


# ─────────────────────────────────────────────────────────────────────────────
# OracleDesktopApp — Tkinter UI
# ─────────────────────────────────────────────────────────────────────────────

class OracleDesktopApp:

    BG        = "#0f1117"
    BG_PANEL  = "#151922"
    BG_INPUT  = "#171d29"
    BG_CARD   = "#1c2430"
    FG        = "#eef2f7"
    FG_DIM    = "#8c98a8"
    ACCENT    = "#58a6ff"
    RED       = "#ff6b6b"
    GREEN     = "#6ee7a8"
    YELLOW    = "#f0c674"
    BLUE      = "#7aa2f7"
    FONT_MONO = ("Consolas", 11)
    FONT_UI   = ("Segoe UI", 10)
    FONT_HEADING = ("Segoe UI", 11, "bold")

    def __init__(self, root: tk.Tk):
        self.root = root
        self.oracle = OracleProcess()
        self._build_ui()
        self._start_oracle()
        self._poll_output()
        self._poll_status()

    # ── UI construction ───────────────────────────────────────────────────

    def _build_ui(self):
        self.root.title("ORACLE Resident Console")
        self.root.configure(bg=self.BG)
        self.root.geometry("1180x760")
        self.root.minsize(900, 580)

        # ── Top bar: mode + source labels ──────────────────────────────
        top = tk.Frame(self.root, bg=self.BG, height=32)
        top.pack(side=tk.TOP, fill=tk.X, padx=14, pady=(12, 6))

        tk.Label(
            top, text="ORACLE", bg=self.BG, fg=self.ACCENT,
            font=("Segoe UI", 17, "bold")
        ).pack(side=tk.LEFT, padx=(0, 10))

        tk.Label(
            top, text="Resident Console", bg=self.BG, fg=self.FG_DIM,
            font=("Segoe UI", 11)
        ).pack(side=tk.LEFT, padx=(0, 18))

        self._lbl_mode = tk.Label(
            top, text="LOCAL", bg=self.BG_CARD, fg=self.YELLOW,
            font=self.FONT_HEADING, padx=12, pady=4
        )
        self._lbl_mode.pack(side=tk.LEFT, padx=4)

        self._lbl_claude = tk.Label(
            top, text="Claude: ●", bg=self.BG, fg=self.RED,
            font=self.FONT_UI
        )
        self._lbl_claude.config(bg=self.BG_CARD, font=self.FONT_HEADING, padx=12, pady=4)
        self._lbl_claude.pack(side=tk.LEFT, padx=4)

        self._lbl_autonomy = tk.Label(
            top, text="Delegated autonomy", bg=self.BG_CARD, fg=self.GREEN,
            font=self.FONT_HEADING, padx=12, pady=4
        )
        self._lbl_autonomy.pack(side=tk.LEFT, padx=4)

        self._lbl_last = tk.Label(
            top, text="", bg=self.BG, fg=self.FG_DIM,
            font=self.FONT_UI
        )
        self._lbl_last.pack(side=tk.RIGHT, padx=8)

        # ── Main area: conversation + status panel ──────────────────────
        main = tk.Frame(self.root, bg=self.BG)
        main.pack(side=tk.TOP, fill=tk.BOTH, expand=True, padx=14, pady=6)

        # Conversation pane
        self._chat = scrolledtext.ScrolledText(
            main, bg="#0b0f16", fg=self.FG,
            font=self.FONT_MONO,
            relief=tk.FLAT, wrap=tk.WORD,
            padx=14, pady=12,
            state=tk.DISABLED,
            insertbackground=self.ACCENT,
            selectbackground="#24364a",
        )
        self._chat.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # Configure label color tags
        for label, color in _LABEL_COLORS.items():
            self._chat.tag_configure(label, foreground=color)
        self._chat.tag_configure("dim", foreground=self.FG_DIM)
        self._chat.tag_configure("bold", font=("Consolas", 11, "bold"))
        self._chat.tag_configure("oracle", foreground=self.ACCENT, font=("Consolas", 11, "bold"))
        self._chat.tag_configure("system", foreground=self.GREEN)
        self._chat.tag_configure("warn", foreground=self.YELLOW)

        # Status panel
        panel = tk.Frame(main, bg=self.BG_PANEL, width=290)
        panel.pack(side=tk.RIGHT, fill=tk.Y, padx=(10, 0))
        panel.pack_propagate(False)

        tk.Label(
            panel, text="SYSTEM", bg=self.BG_PANEL, fg=self.FG,
            font=self.FONT_HEADING
        ).pack(pady=(16, 4))

        self._summary = tk.Label(
            panel, text="Awake, local, governed.", bg=self.BG_PANEL,
            fg=self.FG_DIM, font=self.FONT_UI, wraplength=250, justify=tk.LEFT
        )
        self._summary.pack(fill=tk.X, padx=16, pady=(0, 10))

        ttk.Separator(panel, orient=tk.HORIZONTAL).pack(fill=tk.X, padx=12, pady=4)

        self._status_vars: dict[str, tk.StringVar] = {}
        _rows = [
            ("Mode",     "mode"),
            ("Claude",   "claude"),
            ("Autonomy", "autonomy"),
            ("Hands",    "hands"),
            ("Memory",   "memory"),
            ("Pending",  "pending"),
            ("Model",    "model_name"),
        ]
        for label, key in _rows:
            row = tk.Frame(panel, bg=self.BG_PANEL)
            row.pack(fill=tk.X, padx=14, pady=4)
            tk.Label(
                row, text=f"{label}:", bg=self.BG_PANEL, fg=self.FG_DIM,
                font=self.FONT_UI, width=9, anchor="w"
            ).pack(side=tk.LEFT)
            var = tk.StringVar(value="—")
            self._status_vars[key] = var
            tk.Label(
                row, textvariable=var, bg=self.BG_PANEL, fg=self.FG,
                font=self.FONT_UI, anchor="w"
            ).pack(side=tk.LEFT)

        ttk.Separator(panel, orient=tk.HORIZONTAL).pack(fill=tk.X, padx=12, pady=8)

        # Quick-action buttons
        tk.Label(
            panel, text="QUICK ACTIONS", bg=self.BG_PANEL, fg=self.FG_DIM,
            font=("Segoe UI", 9, "bold")
        ).pack(anchor="w", padx=14, pady=(2, 6))

        for label, cmd, color in [
            ("Wake cycle", "run one resident cycle", self.GREEN),
            ("Pending approvals", "/pending", self.YELLOW),
            ("Memory", "/memory", self.BLUE),
            ("Status", "show me your status", self.ACCENT),
            ("Clear view", "/clear", self.FG_DIM),
        ]:
            b = tk.Button(
                panel, text=label, command=lambda c=cmd: self._send_command(c),
                bg=self.BG_CARD, fg=color, relief=tk.FLAT,
                font=self.FONT_UI, cursor="hand2", activebackground="#2a2a42",
                anchor="w", padx=10,
            )
            b.pack(fill=tk.X, padx=14, pady=3)

        # ── Bottom: input box + send button ────────────────────────────
        bottom = tk.Frame(self.root, bg=self.BG_INPUT, height=48)
        bottom.pack(side=tk.BOTTOM, fill=tk.X, padx=14, pady=(6, 14))

        self._input = tk.Entry(
            bottom, bg=self.BG_INPUT, fg=self.FG,
            font=self.FONT_MONO, relief=tk.FLAT,
            insertbackground=self.ACCENT,
        )
        self._input.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(14, 6), pady=12)
        self._input.bind("<Return>", self._on_send)
        self._input.bind("<Up>", self._history_up)
        self._input.bind("<Down>", self._history_down)
        self._input.focus_set()

        send_btn = tk.Button(
            bottom, text="Send", command=self._on_send,
            bg=self.ACCENT, fg="#09111c", relief=tk.FLAT,
            font=("Segoe UI", 10, "bold"), cursor="hand2",
            padx=22, pady=7,
            activebackground="#3ab0e8",
        )
        send_btn.pack(side=tk.RIGHT, padx=(0, 14), pady=9)

        # Input history
        self._input_history: list[str] = []
        self._history_idx: int = -1

        # Keyboard shortcut: Ctrl+L to clear chat
        self.root.bind("<Control-l>", lambda e: self._send_command("/clear"))
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

    # ── Oracle process ────────────────────────────────────────────────────

    def _start_oracle(self):
        self._append_line("  Starting ORACLE runtime…", tag="dim")
        self._append_line("ORACLE Resident Console", tag="oracle")
        self._append_line("Awake on local runtime. Routine in-scope work is delegated; major changes still come back to Noah.", tag="system")
        self._append_line("Try: 'run one resident cycle' or 'show me your status'.", tag="dim")
        self._append_line("", tag="dim")
        self.oracle.start()
        # Kick off a background status refresh in 3 seconds
        self.root.after(3000, self._do_status_refresh)

    # ── Output polling ────────────────────────────────────────────────────

    def _poll_output(self):
        """Drain output queue and write to chat pane."""
        try:
            while True:
                line = self.oracle.output_q.get_nowait()
                self._append_line(line)
        except queue.Empty:
            pass
        self.root.after(50, self._poll_output)

    # ── Status polling ────────────────────────────────────────────────────

    def _poll_status(self):
        self._update_status_panel(self.oracle.last_status)
        self.root.after(5000, self._poll_status)

    def _do_status_refresh(self):
        self.oracle.refresh_status()
        self._update_status_panel(self.oracle.last_status)

    def _update_status_panel(self, s: dict):
        mode = s.get("mode", "LOCAL")
        self._status_vars["mode"].set(mode)
        self._lbl_mode.config(text=mode, fg=self.YELLOW if mode == "LOCAL" else self.GREEN)

        claude_ok = s.get("claude_window") or s.get("claude_cli")
        claude_txt = "Connected" if claude_ok else "Not connected"
        self._status_vars["claude"].set(claude_txt)
        self._lbl_claude.config(
            text=f"Claude: ● {claude_txt}",
            fg=self.GREEN if claude_ok else self.RED,
        )

        self._status_vars["autonomy"].set("Delegated")
        self._lbl_autonomy.config(text="Delegated autonomy", fg=self.GREEN)
        self._status_vars["hands"].set("Ready" if s.get("hands_ready", True) else "Blocked")
        self._status_vars["memory"].set("Connected" if s.get("memory_connected", True) else "—")
        pending = int(s.get("pending", 0) or 0)
        self._status_vars["pending"].set(str(pending))
        if hasattr(self, "_summary"):
            pending_note = "No pending approvals" if pending == 0 else f"{pending} approval item(s) waiting"
            self._summary.config(text=f"Awake locally. Delegated routine work is enabled. {pending_note}.")
        self._status_vars["model_name"].set(str(s.get("model", "—")))

    # ── Chat pane helpers ─────────────────────────────────────────────────

    def _append_line(self, text: str, tag: str | None = None):
        self._chat.config(state=tk.NORMAL)
        if not tag:
            # Auto-detect a label at the start of the line
            for label in _LABEL_COLORS:
                if text.strip().startswith(label):
                    tag = label
                    break
        if tag:
            self._chat.insert(tk.END, text + "\n", tag)
        else:
            self._chat.insert(tk.END, text + "\n")
        self._chat.config(state=tk.DISABLED)
        self._chat.see(tk.END)

    # ── Send / input ──────────────────────────────────────────────────────

    def _on_send(self, event=None):
        text = self._input.get().strip()
        if not text:
            return
        self._input.delete(0, tk.END)
        self._input_history.append(text)
        self._history_idx = -1
        # Show in chat
        self._append_line(f"You: {text}", tag="You:")
        # Push to oracle
        self.oracle.send(text)
        # Update last-action label
        self._lbl_last.config(text=f"Last: {text[:40]}")

    def _send_command(self, cmd: str):
        self._append_line(f"You: {cmd}", tag="You:")
        self.oracle.send(cmd)

    def _history_up(self, event=None):
        if not self._input_history:
            return
        if self._history_idx < len(self._input_history) - 1:
            self._history_idx += 1
        val = self._input_history[-(self._history_idx + 1)]
        self._input.delete(0, tk.END)
        self._input.insert(0, val)

    def _history_down(self, event=None):
        if self._history_idx <= 0:
            self._history_idx = -1
            self._input.delete(0, tk.END)
            return
        self._history_idx -= 1
        val = self._input_history[-(self._history_idx + 1)]
        self._input.delete(0, tk.END)
        self._input.insert(0, val)

    # ── Close ─────────────────────────────────────────────────────────────

    def _on_close(self):
        self.oracle.stop()
        self.root.destroy()


# ─────────────────────────────────────────────────────────────────────────────

def main():
    root = tk.Tk()
    app = OracleDesktopApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
