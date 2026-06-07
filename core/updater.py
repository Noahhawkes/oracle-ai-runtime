"""
core/updater.py — ORACLE Self-Upgrade & Patch Notes

Shows what changed, pulls updates from git remote when available.
Noah approves before any files change on disk.
"""

import sys
import subprocess
import tkinter as tk
from tkinter import scrolledtext, ttk
from pathlib import Path
from datetime import datetime

if getattr(sys, "frozen", False):
    ROOT = Path(sys.executable).parent
else:
    ROOT = Path(__file__).parent.parent

VERSION_FILE = ROOT / "VERSION"


def _git(*args, cwd=None) -> tuple[int, str]:
    result = subprocess.run(
        ["git"] + list(args),
        cwd=str(cwd or ROOT),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    return result.returncode, (result.stdout + result.stderr).strip()


def current_version() -> str:
    if VERSION_FILE.exists():
        return VERSION_FILE.read_text(encoding="utf-8").strip()
    code, out = _git("describe", "--tags", "--always", "--dirty")
    if code == 0 and out:
        return out
    code, out = _git("rev-parse", "--short", "HEAD")
    return out if code == 0 else "unknown"


def get_patch_notes(max_commits: int = 30) -> list[dict]:
    """Return list of recent commits as structured dicts."""
    fmt = "%H|%h|%ad|%an|%s"
    code, out = _git(
        "log",
        f"--max-count={max_commits}",
        f"--format={fmt}",
        "--date=format:%Y-%m-%d %H:%M",
    )
    if code != 0 or not out:
        return []

    entries = []
    for line in out.splitlines():
        parts = line.split("|", 4)
        if len(parts) == 5:
            entries.append({
                "hash":    parts[0],
                "short":   parts[1],
                "date":    parts[2],
                "author":  parts[3],
                "subject": parts[4],
            })
    return entries


def _categorize(subject: str) -> tuple[str, str]:
    """Return (emoji, category) based on conventional commit prefix."""
    s = subject.lower()
    if s.startswith("feat"):   return "NEW", subject
    if s.startswith("fix"):    return "FIX", subject
    if s.startswith("perf"):   return "PERF", subject
    if s.startswith("refact"): return "REFACTOR", subject
    if s.startswith("docs"):   return "DOCS", subject
    if s.startswith("test"):   return "TEST", subject
    if s.startswith("chore") or s.startswith("build"): return "CHORE", subject
    return "UPDATE", subject


def format_patch_notes(entries: list[dict]) -> str:
    if not entries:
        return "No commits found."

    lines = []
    lines.append(f"ORACLE.AI — Patch Notes")
    lines.append(f"Version: {current_version()}")
    lines.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    lines.append("=" * 60)
    lines.append("")

    current_date = None
    for e in entries:
        date = e["date"][:10]
        if date != current_date:
            if current_date is not None:
                lines.append("")
            lines.append(f"── {date} " + "─" * (48 - len(date)))
            current_date = date

        tag, subject = _categorize(e["subject"])
        lines.append(f"  [{tag}] {subject}")
        lines.append(f"         {e['short']} · {e['date'][11:]}")

    lines.append("")
    lines.append("=" * 60)
    return "\n".join(lines)


def has_remote() -> bool:
    code, out = _git("remote")
    return code == 0 and out.strip() != ""


def fetch_updates() -> tuple[bool, str]:
    """Fetch from remote. Returns (success, message)."""
    if not has_remote():
        return False, "No remote configured — ORACLE is running from local repo only."
    code, out = _git("fetch", "--all")
    if code != 0:
        return False, f"Fetch failed: {out}"
    return True, out


def pending_commits() -> list[dict]:
    """Commits on remote main not yet applied locally."""
    if not has_remote():
        return []
    code, out = _git("log", "HEAD..origin/main", "--format=%H|%h|%ad|%an|%s", "--date=format:%Y-%m-%d %H:%M")
    if code != 0 or not out.strip():
        return []
    entries = []
    for line in out.splitlines():
        parts = line.split("|", 4)
        if len(parts) == 5:
            entries.append({"hash": parts[0], "short": parts[1], "date": parts[2], "author": parts[3], "subject": parts[4]})
    return entries


def apply_update() -> tuple[bool, str]:
    """Pull latest from remote. Noah must confirm before calling this."""
    if not has_remote():
        return False, "No remote configured."
    code, out = _git("pull", "--ff-only", "origin", "main")
    if code == 0:
        new_ver = current_version()
        return True, f"Updated to {new_ver}.\n\n{out}"
    return False, f"Update failed:\n{out}"


# ── GUI ───────────────────────────────────────────────────────────────────────

def show_patch_notes_window(fetch_first: bool = False):
    """Open a dark-themed scrollable patch notes window."""

    BG       = "#0a0a14"
    FG       = "#c8d8e8"
    ACCENT   = "#00c8ff"
    HEADER   = "#1a1a2e"
    BTN_BG   = "#1e3050"
    BTN_FG   = "#00c8ff"
    MONO     = ("Consolas", 10)

    root = tk.Tk()
    root.title("ORACLE.AI — Patch Notes")
    root.configure(bg=BG)
    root.geometry("720x560")
    root.resizable(True, True)

    # Title bar
    title_frame = tk.Frame(root, bg=HEADER, pady=8)
    title_frame.pack(fill=tk.X)
    tk.Label(title_frame, text="ORACLE.AI", font=("Consolas", 16, "bold"),
             bg=HEADER, fg=ACCENT).pack(side=tk.LEFT, padx=16)
    tk.Label(title_frame, text=f"v{current_version()}",
             font=("Consolas", 10), bg=HEADER, fg=FG).pack(side=tk.LEFT)

    # Status bar
    status_var = tk.StringVar(value="Loading patch notes...")
    status_bar = tk.Label(root, textvariable=status_var, font=("Consolas", 9),
                          bg=HEADER, fg=FG, anchor="w", padx=12, pady=4)
    status_bar.pack(fill=tk.X)

    # Text area
    text_frame = tk.Frame(root, bg=BG)
    text_frame.pack(fill=tk.BOTH, expand=True, padx=12, pady=(8, 4))

    text = scrolledtext.ScrolledText(
        text_frame, bg=BG, fg=FG, font=MONO, wrap=tk.WORD,
        insertbackground=ACCENT, selectbackground="#1e3050",
        relief=tk.FLAT, borderwidth=0, padx=10, pady=10,
    )
    text.pack(fill=tk.BOTH, expand=True)

    # Tag styles
    text.tag_configure("header",   foreground=ACCENT, font=("Consolas", 11, "bold"))
    text.tag_configure("date",     foreground="#607080", font=("Consolas", 9, "bold"))
    text.tag_configure("new",      foreground="#00ff99")
    text.tag_configure("fix",      foreground="#ff9944")
    text.tag_configure("perf",     foreground="#cc88ff")
    text.tag_configure("update",   foreground=FG)
    text.tag_configure("hash",     foreground="#405060", font=("Consolas", 9))
    text.tag_configure("divider",  foreground="#203040")

    def render(entries):
        text.config(state=tk.NORMAL)
        text.delete("1.0", tk.END)

        text.insert(tk.END, f"ORACLE.AI Patch Notes\n", "header")
        text.insert(tk.END, f"Version {current_version()}  ·  {datetime.now().strftime('%Y-%m-%d %H:%M')}\n\n", "hash")

        current_date = None
        for e in entries:
            date = e["date"][:10]
            if date != current_date:
                if current_date:
                    text.insert(tk.END, "\n")
                text.insert(tk.END, f"{'─' * 60}\n", "divider")
                text.insert(tk.END, f"  {date}\n", "date")
                current_date = date

            tag_name, subject = _categorize(e["subject"])
            color_map = {"NEW": "new", "FIX": "fix", "PERF": "perf"}
            tag = color_map.get(tag_name, "update")

            label = f"[{tag_name}]".ljust(10)
            text.insert(tk.END, f"  {label} ", tag)
            text.insert(tk.END, f"{subject}\n", "update")
            text.insert(tk.END, f"{'':13}{e['short']}  {e['date'][11:]}\n", "hash")

        text.config(state=tk.DISABLED)

    # Button row
    btn_frame = tk.Frame(root, bg=BG, pady=8)
    btn_frame.pack(fill=tk.X, padx=12)

    def do_check():
        status_var.set("Checking for updates...")
        root.update()
        ok, msg = fetch_updates()
        pending = pending_commits()
        if pending:
            status_var.set(f"{len(pending)} update(s) available from remote.")
            if tk.messagebox.askyesno("Updates Available",
                f"{len(pending)} new commit(s) are available.\n\nApply update now?",
                parent=root):
                do_apply()
        else:
            if ok:
                status_var.set("ORACLE is up to date.")
            else:
                status_var.set(msg)

    def do_apply():
        status_var.set("Applying update...")
        root.update()
        ok, msg = apply_update()
        if ok:
            entries = get_patch_notes(30)
            render(entries)
            status_var.set("Update applied. Restart ORACLE to load new code.")
        else:
            status_var.set(f"Update failed: {msg}")

    tk.Button(btn_frame, text="Check for Updates", command=do_check,
              bg=BTN_BG, fg=BTN_FG, font=("Consolas", 10), relief=tk.FLAT,
              activebackground="#2a4060", activeforeground=ACCENT,
              padx=12, pady=4, cursor="hand2").pack(side=tk.LEFT, padx=(0, 8))

    tk.Button(btn_frame, text="Close", command=root.destroy,
              bg=HEADER, fg=FG, font=("Consolas", 10), relief=tk.FLAT,
              activebackground="#1a1a2e", activeforeground=FG,
              padx=12, pady=4, cursor="hand2").pack(side=tk.RIGHT)

    # Load notes
    entries = get_patch_notes(40)
    render(entries)
    if fetch_first and has_remote():
        status_var.set("Fetching latest...")
        root.after(500, do_check)
    else:
        pending = pending_commits()
        if pending:
            status_var.set(f"{len(pending)} update(s) available.")
        else:
            status_var.set("Up to date." if has_remote() else "Local build — no remote configured.")

    root.mainloop()


if __name__ == "__main__":
    show_patch_notes_window()
