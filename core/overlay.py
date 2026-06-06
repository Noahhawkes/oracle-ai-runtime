"""
ORACLE Overlay OS — always-on-top desktop control panel.

Provides a persistent GUI window with:
  - Chat input / response panel (drives existing chat_local / chat loops)
  - 6 quick-action buttons
  - Status bar (mode, models, Ollama, memory)

Does NOT duplicate brain logic — all intelligence routes through
existing oracle.py, llm.py, memory.py, and tools/.

Run: pythonw core/overlay.py   (or double-click overlay.bat)
"""

import os
import sys
import subprocess
import threading
from pathlib import Path
import tkinter as tk
from tkinter import scrolledtext

if getattr(sys, "frozen", False):
    ROOT = Path(sys.executable).parent
else:
    ROOT = Path(__file__).parent.parent

sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "core"))

from dotenv import load_dotenv
load_dotenv(ROOT / ".env")

from llm import is_local, make_client, get_model, startup_status, to_openai_tools
from memory import init_db, new_session, save_message, get_facts
from context_loader import build_system_prompt
from audit_log import log
from tools.definitions import TOOL_DEFINITIONS
from tools.executor import execute_tool

# ── Colours ───────────────────────────────────────────────────────────────────

BG       = "#0d0d1a"
BG2      = "#13132b"
BG3      = "#1a1a38"
ACCENT   = "#00c8ff"
TEXT     = "#dde0f0"
MUTED    = "#5a5a88"
SUCCESS  = "#00e87a"
WARNING  = "#ffaa00"
ERR      = "#ff4455"
BTN_BG   = "#1c1c3a"
BTN_ACT  = "#2a2a56"
ENTRY_BG = "#10102a"

FONT_MONO  = ("Consolas", 10)
FONT_SMALL = ("Segoe UI", 9)
FONT_BOLD  = ("Segoe UI", 9, "bold")
FONT_TITLE = ("Segoe UI", 11, "bold")


# ── Chat helpers (mirror oracle.py loops without re-importing oracle module) ──

MAX_TOKENS = 4096


def _chat_local(client, session_id, system_prompt, history, user_input, model,
                tool_cb=None):
    """
    OpenAI-compatible agentic loop (Ollama).  Identical logic to oracle.chat_local
    but accepts an optional tool_cb(name) for UI feedback.
    """
    import json

    history.append({"role": "user", "content": user_input})
    save_message(session_id, "user", user_input)
    log("INPUT", user_input)

    oai_tools = to_openai_tools(TOOL_DEFINITIONS)

    while True:
        messages = [{"role": "system", "content": system_prompt}] + history
        response = client.chat.completions.create(
            model=model, max_tokens=MAX_TOKENS,
            messages=messages, tools=oai_tools,
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
                if tool_cb:
                    tool_cb(tc.function.name)
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


def _chat_cloud(client, session_id, system_prompt, history, user_input, model,
                tool_cb=None):
    """Anthropic-format agentic loop (cloud turbo mode)."""
    history.append({"role": "user", "content": user_input})
    save_message(session_id, "user", user_input)
    log("INPUT", user_input)

    while True:
        response = client.messages.create(
            model=model, max_tokens=MAX_TOKENS,
            system=[{"type": "text", "text": system_prompt,
                     "cache_control": {"type": "ephemeral"}}],
            messages=history, tools=TOOL_DEFINITIONS,
        )
        history.append({"role": "assistant", "content": response.content})

        if response.stop_reason == "tool_use":
            tool_results = []
            for block in response.content:
                if getattr(block, "type", None) == "tool_use":
                    if tool_cb:
                        tool_cb(block.name)
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
        save_message(session_id, "assistant", reply)
        log("OUTPUT", reply[:200] + ("..." if len(reply) > 200 else ""))
        return reply, history


# ── Overlay window ────────────────────────────────────────────────────────────

class OracleOverlay(tk.Tk):

    def __init__(self, client, session_id, system_prompt, local, model):
        super().__init__()

        self._client      = client
        self._session_id  = session_id
        self._system      = system_prompt
        self._local       = local
        self._model       = model
        self._history     = []
        self._busy        = False   # True while waiting for model reply

        self._build_window()
        self._build_layout()
        self.after(200, self._refresh_status)

    # ── Window chrome ─────────────────────────────────────────────────────────

    def _build_window(self):
        self.title("ORACLE.AI")
        self.configure(bg=BG)
        self.geometry("920x620")
        self.minsize(720, 480)
        self.attributes("-topmost", True)
        # Allow toggling always-on-top with a right-click on the title label later
        self.protocol("WM_DELETE_WINDOW", self._quit)

    # ── Layout ────────────────────────────────────────────────────────────────

    def _build_layout(self):
        # ── Title bar ──
        title_bar = tk.Frame(self, bg=BG, pady=4)
        title_bar.pack(fill=tk.X, padx=10)
        tk.Label(title_bar, text="⬡  ORACLE.AI  |  OVERLAY OS",
                 bg=BG, fg=ACCENT, font=FONT_TITLE).pack(side=tk.LEFT)
        self._topmost_var = tk.BooleanVar(value=True)
        tk.Checkbutton(title_bar, text="Always on top", variable=self._topmost_var,
                       bg=BG, fg=MUTED, selectcolor=BG2, activebackground=BG,
                       font=FONT_SMALL, command=self._toggle_topmost).pack(side=tk.RIGHT)

        # ── Status bar ──
        self._status_frame = tk.Frame(self, bg=BG2, pady=3)
        self._status_frame.pack(fill=tk.X, padx=10, pady=(0, 4))
        self._status_labels = {}
        for key in ("mode", "model", "vision", "ollama", "memory"):
            lbl = tk.Label(self._status_frame, text="...", bg=BG2, fg=MUTED,
                           font=FONT_SMALL, padx=8)
            lbl.pack(side=tk.LEFT)
            self._status_labels[key] = lbl

        # ── Main body: buttons left, output right ──
        body = tk.Frame(self, bg=BG)
        body.pack(fill=tk.BOTH, expand=True, padx=10)

        btn_col = tk.Frame(body, bg=BG, width=170)
        btn_col.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 8))
        btn_col.pack_propagate(False)
        self._build_buttons(btn_col)

        out_col = tk.Frame(body, bg=BG)
        out_col.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self._build_output(out_col)

        # ── Input row ──
        self._build_input()

    def _build_buttons(self, parent):
        tk.Label(parent, text="QUICK ACTIONS", bg=BG, fg=MUTED,
                 font=("Segoe UI", 8)).pack(pady=(6, 4))

        actions = [
            ("Start ORACLE Local",    self._btn_start_local,   ACCENT),
            ("Daily Brief",           self._btn_daily_brief,   TEXT),
            ("Memory Snapshot",       self._btn_memory,        TEXT),
            ("SOV1 Look at Screen",   self._btn_sov1_look,     WARNING),
            ("Open ORACLE Folder",    self._btn_open_folder,   TEXT),
            ("Quit",                  self._quit,              ERR),
        ]
        for label, cmd, colour in actions:
            btn = tk.Button(parent, text=label, command=cmd,
                            bg=BTN_BG, fg=colour, activebackground=BTN_ACT,
                            activeforeground=colour, relief=tk.FLAT,
                            font=FONT_SMALL, cursor="hand2",
                            padx=6, pady=7, width=18, anchor="w")
            btn.pack(fill=tk.X, pady=2)

    def _build_output(self, parent):
        self._output = scrolledtext.ScrolledText(
            parent, bg=BG2, fg=TEXT, font=FONT_MONO,
            relief=tk.FLAT, wrap=tk.WORD, state=tk.DISABLED,
            insertbackground=ACCENT,
        )
        self._output.pack(fill=tk.BOTH, expand=True)
        # Tag colours for different message types
        self._output.tag_config("you",    foreground=ACCENT)
        self._output.tag_config("oracle", foreground=TEXT)
        self._output.tag_config("tool",   foreground=MUTED)
        self._output.tag_config("info",   foreground=SUCCESS)
        self._output.tag_config("err",    foreground=ERR)
        self._output.tag_config("warn",   foreground=WARNING)

        self._append("ORACLE.AI Overlay OS — LOCAL MODE\n"
                     "Type a message below or use the quick-action buttons.\n\n",
                     "info")

    def _build_input(self):
        row = tk.Frame(self, bg=BG, pady=6)
        row.pack(fill=tk.X, padx=10)

        self._input = tk.Entry(row, bg=ENTRY_BG, fg=TEXT, font=FONT_MONO,
                               insertbackground=ACCENT, relief=tk.FLAT,
                               highlightthickness=1, highlightcolor=ACCENT,
                               highlightbackground=MUTED)
        self._input.pack(side=tk.LEFT, fill=tk.X, expand=True, ipady=6, padx=(0, 6))
        self._input.bind("<Return>", lambda _e: self._send())
        self._input.focus_set()

        self._send_btn = tk.Button(row, text="Send", command=self._send,
                                   bg=ACCENT, fg=BG, font=FONT_BOLD,
                                   relief=tk.FLAT, cursor="hand2",
                                   padx=14, pady=6)
        self._send_btn.pack(side=tk.RIGHT)

    # ── Status bar ────────────────────────────────────────────────────────────

    def _refresh_status(self):
        try:
            st = startup_status()
            mode_col  = SUCCESS if st["mode"] == "LOCAL" else WARNING
            ollama_col = SUCCESS if st.get("ollama_ok") else ERR
            sov1_col   = SUCCESS if st["sov1_available"] else MUTED

            self._status_labels["mode"].config(
                text=f"[{st['mode']}]", fg=mode_col)
            self._status_labels["model"].config(
                text=f"txt: {st['model']}", fg=TEXT)
            self._status_labels["vision"].config(
                text=f"vis: {st['vision_model']}", fg=TEXT)
            self._status_labels["ollama"].config(
                text="Ollama [OK]" if st.get("ollama_ok") else "Ollama [!!]",
                fg=ollama_col)
            self._status_labels["memory"].config(
                text="Memory [OK]", fg=SUCCESS)
        except Exception as e:
            self._status_labels["mode"].config(text=f"Status error: {e}", fg=ERR)

    # ── Output helpers ────────────────────────────────────────────────────────

    def _append(self, text: str, tag: str = "oracle"):
        self._output.config(state=tk.NORMAL)
        self._output.insert(tk.END, text, tag)
        self._output.see(tk.END)
        self._output.config(state=tk.DISABLED)

    def _set_busy(self, busy: bool):
        self._busy = busy
        state = tk.DISABLED if busy else tk.NORMAL
        self._send_btn.config(state=state)
        self._input.config(state=state)
        cursor = "watch" if busy else "xterm"
        self._input.config(cursor=cursor)

    # ── Chat ──────────────────────────────────────────────────────────────────

    def _send(self):
        if self._busy:
            return
        text = self._input.get().strip()
        if not text:
            return
        self._input.delete(0, tk.END)
        self._append(f"You: {text}\n", "you")
        self._set_busy(True)
        threading.Thread(target=self._run_chat, args=(text,), daemon=True).start()

    def _run_chat(self, user_input: str):
        def tool_cb(name):
            self.after(0, self._append, f"  [Tool: {name}]\n", "tool")

        try:
            if self._local:
                reply, self._history = _chat_local(
                    self._client, self._session_id, self._system,
                    self._history, user_input, self._model, tool_cb=tool_cb,
                )
            else:
                reply, self._history = _chat_cloud(
                    self._client, self._session_id, self._system,
                    self._history, user_input, self._model, tool_cb=tool_cb,
                )
            self.after(0, self._append, f"\nOracle: {reply}\n\n", "oracle")
        except Exception as e:
            log("ERROR", str(e))
            self.after(0, self._append, f"\n[Error: {e}]\n\n", "err")
        finally:
            self.after(0, self._set_busy, False)
            self.after(0, self._input.focus_set)

    # ── Button handlers ───────────────────────────────────────────────────────

    def _btn_start_local(self):
        bat = ROOT / "oracle_local.bat"
        if bat.exists():
            subprocess.Popen(["cmd", "/c", "start", "ORACLE.AI Local",
                              str(bat)], shell=False)
            self._append("Launched ORACLE Local in a new terminal window.\n", "info")
        else:
            self._append("oracle_local.bat not found. Run python core/oracle.py manually.\n", "warn")

    def _btn_daily_brief(self):
        if self._busy:
            return
        self._append("Generating daily brief...\n", "info")
        self._set_busy(True)

        def run():
            try:
                result = subprocess.run(
                    [sys.executable, str(ROOT / "core" / "planner.py")],
                    capture_output=True, text=True, timeout=120,
                    env={**os.environ, "LOCAL_MODE": "true"},
                    cwd=str(ROOT),
                )
                out = result.stdout.strip() or result.stderr.strip() or "(no output)"
                self.after(0, self._append, f"\n{out}\n\n", "oracle")
            except subprocess.TimeoutExpired:
                self.after(0, self._append, "[Daily brief timed out.]\n", "err")
            except Exception as e:
                self.after(0, self._append, f"[Brief error: {e}]\n", "err")
            finally:
                self.after(0, self._set_busy, False)

        threading.Thread(target=run, daemon=True).start()

    def _btn_memory(self):
        if self._busy:
            return
        self._append("Memory snapshot:\n", "info")
        self._set_busy(True)

        def run():
            try:
                facts = get_facts()
                if facts:
                    lines = "\n".join(
                        f"  [{f['category']}] {f['key']}: {f['value'][:120]}"
                        for f in facts[:20]
                    )
                    out = f"{lines}\n  ({len(facts)} total facts)\n"
                else:
                    out = "  No facts stored yet.\n"
                self.after(0, self._append, out + "\n", "oracle")
            except Exception as e:
                self.after(0, self._append, f"[Memory error: {e}]\n", "err")
            finally:
                self.after(0, self._set_busy, False)

        threading.Thread(target=run, daemon=True).start()

    def _btn_sov1_look(self):
        if self._busy:
            return
        self._append("Asking SOV1 to look at the screen...\n", "info")
        self._set_busy(True)

        def run():
            try:
                result = execute_tool(
                    "computer_operator",
                    {"goal": "Take a screenshot and describe in detail what you see on the screen. Call task_done with your description."}
                )
                self.after(0, self._append, f"\nSOV1 sees:\n{result}\n\n", "oracle")
            except Exception as e:
                self.after(0, self._append, f"[SOV1 error: {e}]\n", "err")
            finally:
                self.after(0, self._set_busy, False)

        threading.Thread(target=run, daemon=True).start()

    def _btn_open_folder(self):
        os.startfile(str(ROOT))
        self._append(f"Opened: {ROOT}\n", "info")

    def _quit(self):
        log("SESSION_END", f"Overlay session {self._session_id} ended")
        self.destroy()

    def _toggle_topmost(self):
        self.attributes("-topmost", self._topmost_var.get())


# ── Entry point ───────────────────────────────────────────────────────────────

def main():
    os.chdir(ROOT)
    init_db()
    session_id    = new_session()
    system_prompt = build_system_prompt()
    local         = is_local()

    try:
        client = make_client()
    except RuntimeError as e:
        # Show error in a minimal tk window rather than crashing silently
        root = tk.Tk()
        root.title("ORACLE.AI — Startup Error")
        root.configure(bg="#0d0d1a")
        root.geometry("500x160")
        tk.Label(root, text=f"Startup error:\n\n{e}",
                 bg="#0d0d1a", fg="#ff4455",
                 font=("Consolas", 10), wraplength=460, justify="left").pack(
                     padx=20, pady=20)
        tk.Button(root, text="Close", command=root.destroy,
                  bg="#1c1c3a", fg="white").pack()
        root.mainloop()
        return

    model = get_model(vision=False)
    log("SESSION_START", f"Overlay session {session_id} started ({('LOCAL' if local else 'CLOUD')})")

    app = OracleOverlay(client, session_id, system_prompt, local, model)
    app.mainloop()


if __name__ == "__main__":
    main()
