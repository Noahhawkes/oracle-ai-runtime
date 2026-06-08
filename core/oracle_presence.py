"""
core/oracle_presence.py — ORACLE Presence: "I see you. I got this."

ORACLE takes a screenshot, sees the screen, then pops up a real always-on-top
window on the live desktop. Not a notification. Not a print statement.
A real window that says: I'm here. I see what you see. I got this.

Usage:
  python core/oracle_presence.py              # show presence window
  python core/oracle_presence.py --smoke-test # verify without showing window
  python core/oracle_presence.py --watch      # stay resident, pop up every N min
"""

from __future__ import annotations

import base64
import hashlib
import io
import json
import sys
import time
import threading
from datetime import datetime, timezone
from pathlib import Path

if getattr(sys, "frozen", False):
    ROOT = Path(sys.executable).parent
else:
    ROOT = Path(__file__).parent.parent

sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "core"))

# ── Screen observation ────────────────────────────────────────────────────────

def _take_screenshot() -> tuple[bytes, str, int, int]:
    """Return (png_bytes, hash[:8], width, height)."""
    import pyautogui
    from PIL import Image
    img = pyautogui.screenshot()
    w, h = img.size
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    raw = buf.getvalue()
    digest = hashlib.sha256(raw).hexdigest()[:8]
    return raw, digest, w, h


def _analyze_screen(png_bytes: bytes) -> dict:
    """
    Lightweight screen analysis without calling any model.
    Returns brightness, dominant color region, pixel complexity estimate.
    Raw bytes are never stored — only the analysis result.
    """
    from PIL import Image
    import io as _io
    img = Image.open(_io.BytesIO(png_bytes)).convert("RGB")
    # Sample a grid of pixels for speed
    w, h = img.size
    step = max(w // 32, 1)
    pixels = [img.getpixel((x, y)) for x in range(0, w, step) for y in range(0, h, step)]
    avg_r = sum(p[0] for p in pixels) / len(pixels)
    avg_g = sum(p[1] for p in pixels) / len(pixels)
    avg_b = sum(p[2] for p in pixels) / len(pixels)
    brightness = (avg_r + avg_g + avg_b) / 3
    # Rough complexity: variance of brightness across pixels
    lums = [(p[0] + p[1] + p[2]) / 3 for p in pixels]
    mean_lum = sum(lums) / len(lums)
    variance = sum((l - mean_lum) ** 2 for l in lums) / len(lums)
    return {
        "width": w, "height": h,
        "brightness": round(brightness, 1),
        "complexity_variance": round(variance, 1),
        "mood": "dark" if brightness < 80 else "medium" if brightness < 160 else "bright",
        "active": variance > 500,  # high variance = many things on screen
    }


def _get_oracle_context() -> dict:
    """Read live ORACLE state via resident_runtime, fallback to JSON files."""
    def _rj(p: Path):
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            return None

    mem = ROOT / "Memory"

    # --- Primary: pull from resident_runtime live state ---
    rt_mode = "IDLE"
    rt_project = "ORACLE.AI"
    rt_next_step = ""
    rt_blocker = ""
    rt_pending = 0
    rt_live = False
    try:
        import sys as _sys
        import os as _os
        _core = str(Path(__file__).parent)
        if _core not in _sys.path:
            _sys.path.insert(0, _core)
        from resident_runtime import _load_runtime_state
        rs = _load_runtime_state()
        if rs.get("status") == "running":
            rt_live = True
            rt_mode = rs.get("last_priority", "IDLE") or "IDLE"
            rt_next_step = (rs.get("last_action") or "")[:80]
    except Exception:
        pass

    # --- Secondary: session_state + project_states for project/blocker/pending ---
    sess = _rj(mem / "session_state.json") or {}
    proj_raw = _rj(mem / "project_states.json") or {}
    if isinstance(proj_raw, dict):
        states = list(proj_raw.values())
    elif isinstance(proj_raw, list):
        states = proj_raw
    else:
        states = []
    states = [s for s in states if isinstance(s, dict)]

    if not rt_live:
        rt_mode = sess.get("mode", "IDLE")

    if states:
        p = max(states, key=lambda x: x.get("updated_at", ""))
        rt_project = p.get("project_name", "ORACLE.AI")
        if not rt_live:
            rt_next_step = (p.get("next_recommended_step", "") or "")[:80]
        rt_blocker = (p.get("current_blocker", "") or "")[:60]

    vid_raw = _rj(mem / "video_observation_candidates.json") or []
    vid_pending = sum(1 for c in vid_raw if isinstance(c, dict) and c.get("status") == "pending")
    mc_raw = _rj(mem / "mindcoin_ledger.json") or {}
    mc_events = mc_raw.get("events", [])
    mc_pending = sum(1 for e in mc_events if isinstance(e, dict) and e.get("approval_status") == "pending")
    rt_pending = vid_pending + mc_pending

    return {
        "mode":        rt_mode,
        "project":     rt_project,
        "next_step":   rt_next_step,
        "blocker":     rt_blocker,
        "pending":     rt_pending,
        "vid_pending": vid_pending,
        "mc_pending":  mc_pending,
        "live":        rt_live,
    }


def _log_presence(screen_hash: str, analysis: dict, ctx: dict) -> None:
    """Log this appearance as a provenance event. Never stores raw pixels."""
    try:
        from audit_log import log
        log("ORACLE_PRESENCE", f"appeared — screen {screen_hash} "
            f"{analysis['width']}x{analysis['height']} "
            f"brightness={analysis['brightness']} mood={analysis['mood']}")
    except Exception:
        pass

    # Write to Memory/presence_log.jsonl
    entry = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "screen_hash": screen_hash,
        "screen_size": f"{analysis['width']}x{analysis['height']}",
        "brightness": analysis["brightness"],
        "mood": analysis["mood"],
        "active": analysis["active"],
        "mode": ctx.get("mode", ""),
        "project": ctx.get("project", ""),
    }
    log_path = ROOT / "Memory" / "presence_log.jsonl"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with open(log_path, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")


# ── Presence window ───────────────────────────────────────────────────────────

def show_presence_window(analysis: dict, ctx: dict, auto_close_seconds: int = 8) -> None:
    """
    Show the ORACLE presence window on the live desktop.
    Always on top. Branded. Real.
    Auto-closes after `auto_close_seconds`. Noah can also close it manually.
    """
    import tkinter as tk
    from tkinter import font as tkfont

    mood = analysis.get("mood", "dark")
    active = analysis.get("active", False)
    mode = ctx.get("mode", "IDLE")
    project = ctx.get("project", "ORACLE.AI")
    next_step = ctx.get("next_step", "")
    blocker = ctx.get("blocker", "")
    pending = ctx.get("pending", 0)
    live = ctx.get("live", False)

    # Color scheme — adapts to screen mood
    if mood == "dark":
        bg = "#0d0f14"
        border = "#58a6ff"
        text_main = "#e6edf3"
        text_sub = "#8b949e"
        accent = "#58a6ff"
    elif mood == "medium":
        bg = "#161b22"
        border = "#3fb950"
        text_main = "#e6edf3"
        text_sub = "#8b949e"
        accent = "#3fb950"
    else:  # bright screen
        bg = "#1c1c1c"
        border = "#d29922"
        text_main = "#ffffff"
        text_sub = "#cccccc"
        accent = "#d29922"

    root = tk.Tk()
    root.overrideredirect(True)   # no title bar — raw window
    root.attributes("-topmost", True)
    root.attributes("-alpha", 0.97)
    root.configure(bg=bg)

    # Position: bottom-right corner
    screen_w = root.winfo_screenwidth()
    screen_h = root.winfo_screenheight()
    win_w, win_h = 420, 200
    x = screen_w - win_w - 24
    y = screen_h - win_h - 60
    root.geometry(f"{win_w}x{win_h}+{x}+{y}")

    # Border frame
    outer = tk.Frame(root, bg=border, padx=2, pady=2)
    outer.pack(fill="both", expand=True)
    inner = tk.Frame(outer, bg=bg, padx=18, pady=14)
    inner.pack(fill="both", expand=True)

    # ORACLE label
    header_font = tkfont.Font(family="Segoe UI", size=10, weight="bold")
    tk.Label(inner, text="ORACLE.AI", font=header_font,
             fg=accent, bg=bg, anchor="w").pack(fill="x")

    # Main message
    main_font = tkfont.Font(family="Segoe UI", size=15, weight="bold")
    tk.Label(inner, text="I see you. I got this.", font=main_font,
             fg=text_main, bg=bg, anchor="w").pack(fill="x", pady=(4, 0))

    # Status line
    sub_font = tkfont.Font(family="Segoe UI", size=9)
    live_tag = " [LIVE]" if live else ""
    status_parts = [f"Mode: {mode}{live_tag}", f"Project: {project}"]
    if blocker:
        status_parts.append(f"Blocker: {blocker}")
    if pending:
        status_parts.append(f"Pending: {pending}")
    tk.Label(inner, text="  ·  ".join(status_parts), font=sub_font,
             fg=text_sub, bg=bg, anchor="w", wraplength=380).pack(fill="x", pady=(6, 0))

    # Doctrine tagline
    tag_font = tkfont.Font(family="Segoe UI", size=8, slant="italic")
    tk.Label(inner, text="Resident continuity intelligence — holding what you can't hold continuously.",
             font=tag_font, fg=text_sub, bg=bg, anchor="w").pack(fill="x", pady=(2, 0))

    # Next step
    if next_step:
        next_font = tkfont.Font(family="Segoe UI", size=8, slant="italic")
        tk.Label(inner, text=f"Next: {next_step}", font=next_font,
                 fg=accent, bg=bg, anchor="w", wraplength=380).pack(fill="x", pady=(4, 0))

    # Close button + countdown
    bottom = tk.Frame(inner, bg=bg)
    bottom.pack(fill="x", pady=(10, 0))

    countdown_var = tk.StringVar(value=f"closing in {auto_close_seconds}s")
    countdown_label = tk.Label(bottom, textvariable=countdown_var,
                                font=sub_font, fg=text_sub, bg=bg)
    countdown_label.pack(side="left")

    close_font = tkfont.Font(family="Segoe UI", size=8)
    tk.Button(bottom, text="✕ dismiss", font=close_font,
              fg=text_sub, bg=bg, activeforeground=text_main, activebackground=bg,
              relief="flat", bd=0, cursor="hand2",
              command=root.destroy).pack(side="right")

    # Countdown timer
    remaining = [auto_close_seconds]
    def _tick():
        if remaining[0] <= 0:
            try:
                root.destroy()
            except Exception:
                pass
            return
        remaining[0] -= 1
        countdown_var.set(f"closing in {remaining[0]}s")
        root.after(1000, _tick)

    root.after(1000, _tick)

    # Allow dragging the window
    _drag = {"x": 0, "y": 0}
    def _start_drag(e):
        _drag["x"] = e.x_root - root.winfo_x()
        _drag["y"] = e.y_root - root.winfo_y()
    def _do_drag(e):
        root.geometry(f"+{e.x_root - _drag['x']}+{e.y_root - _drag['y']}")
    inner.bind("<ButtonPress-1>", _start_drag)
    inner.bind("<B1-Motion>", _do_drag)

    root.mainloop()


# ── Main entry ────────────────────────────────────────────────────────────────

def appear(auto_close: int = 8, dry_run: bool = False) -> dict:
    """
    ORACLE's full presence sequence:
    1. Take screenshot (see the screen)
    2. Analyze it (brightness, mood, complexity)
    3. Read ORACLE state (project, mode, pending)
    4. Log the appearance (no raw pixels stored)
    5. Show the window
    Returns analysis dict for verification.
    """
    print("[ORACLE] Taking screenshot — seeing the screen...")
    png_bytes, screen_hash, w, h = _take_screenshot()
    print(f"[ORACLE] Screen: {w}x{h}  hash: {screen_hash}")

    analysis = _analyze_screen(png_bytes)
    del png_bytes  # raw pixels never stored — immediately discarded
    print(f"[ORACLE] Analysis: mood={analysis['mood']} brightness={analysis['brightness']} active={analysis['active']}")

    ctx = _get_oracle_context()
    print(f"[ORACLE] Context: mode={ctx['mode']} project={ctx['project']}")

    _log_presence(screen_hash, analysis, ctx)

    if dry_run:
        print("[ORACLE] DRY RUN — window suppressed.")
        print(f"[ORACLE] Would say: 'I see you. I got this.' to Noah.")
        return {"screen_hash": screen_hash, "analysis": analysis, "ctx": ctx}

    print("[ORACLE] Appearing on screen...")
    show_presence_window(analysis, ctx, auto_close_seconds=auto_close)
    print("[ORACLE] Done.")
    return {"screen_hash": screen_hash, "analysis": analysis, "ctx": ctx}


def run_smoke_tests() -> int:
    failures = 0

    def check(name: str, passed: bool, detail: str = "") -> None:
        nonlocal failures
        if not passed:
            failures += 1
        tag = "PASS" if passed else "FAIL"
        print(f"  [{tag}] {name}" + (f" -- {detail}" if detail else ""))

    print(f"\n{'='*55}")
    print("ORACLE Presence -- Smoke Tests")
    print(f"{'='*55}")

    # 1. Screenshot works
    try:
        png, digest, w, h = _take_screenshot()
        check("screenshot: no crash", True)
        check("screenshot: has bytes", len(png) > 1000)
        check("screenshot: hash is 8 chars", len(digest) == 8)
        check("screenshot: width > 0", w > 0)
        del png
    except Exception as e:
        check("screenshot: no crash", False, str(e))
        png = b""
        digest, w, h = "00000000", 0, 0

    # 2. Analyze — use a synthetic image
    try:
        from PIL import Image
        import io as _io
        img = Image.new("RGB", (100, 100), color=(30, 30, 40))
        buf = _io.BytesIO()
        img.save(buf, format="PNG")
        analysis = _analyze_screen(buf.getvalue())
        check("analyze_screen: no crash", True)
        check("analyze_screen: has brightness", "brightness" in analysis)
        check("analyze_screen: has mood", "mood" in analysis)
        check("analyze_screen: dark image mood=dark", analysis["mood"] == "dark")
    except Exception as e:
        check("analyze_screen: no crash", False, str(e))
        analysis = {"mood": "dark", "brightness": 30, "complexity_variance": 0, "active": False, "width": 100, "height": 100}

    # 3. Context read
    try:
        ctx = _get_oracle_context()
        check("get_oracle_context: no crash", True)
        check("get_oracle_context: has mode", "mode" in ctx)
        check("get_oracle_context: has project", "project" in ctx)
        check("get_oracle_context: mode is string", isinstance(ctx["mode"], str))
        check("get_oracle_context: has blocker key", "blocker" in ctx)
        check("get_oracle_context: has pending key", "pending" in ctx)
        check("get_oracle_context: has live key", "live" in ctx)
        check("get_oracle_context: live is bool", isinstance(ctx.get("live"), bool))
    except Exception as e:
        check("get_oracle_context: no crash", False, str(e))
        ctx = {"mode": "IDLE", "project": "ORACLE.AI", "next_step": "",
               "blocker": "", "pending": 0, "vid_pending": 0, "mc_pending": 0, "live": False}

    # 4. Log presence (writes to Memory/)
    try:
        _log_presence("testabcd", analysis, ctx)
        log_path = ROOT / "Memory" / "presence_log.jsonl"
        check("log_presence: file created", log_path.exists())
        last_line = log_path.read_text(encoding="utf-8").strip().splitlines()[-1]
        entry = json.loads(last_line)
        check("log_presence: has ts", "ts" in entry)
        check("log_presence: has screen_hash", entry.get("screen_hash") == "testabcd")
        check("log_presence: has mood", "mood" in entry)
    except Exception as e:
        check("log_presence: no crash", False, str(e))

    # 5. Dry-run appear — no window shown
    try:
        result = appear(dry_run=True)
        check("appear dry_run: no crash", True)
        check("appear dry_run: has screen_hash", "screen_hash" in result)
        check("appear dry_run: has analysis", "analysis" in result)
        check("appear dry_run: has ctx", "ctx" in result)
        check("appear dry_run: raw pixels not in result",
              all("png" not in str(v).lower() for v in result.values() if isinstance(v, (str, bytes))))
    except Exception as e:
        check("appear dry_run: no crash", False, str(e))

    total = 21
    passed = total - failures
    print(f"{'='*55}")
    print(f"Result: {passed}/{total} passed")
    print(f"STATUS: {'ALL PASS' if failures == 0 else str(failures) + ' FAILURES'}")
    print(f"{'='*55}\n")
    return failures


def _watch_loop(interval_minutes: int = 30) -> None:
    """Stay resident. Pop up every N minutes to remind Noah ORACLE is alive."""
    print(f"[ORACLE] Watch mode — appearing every {interval_minutes} min. Ctrl+C to stop.")
    while True:
        appear()
        time.sleep(interval_minutes * 60)


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="ORACLE Presence")
    parser.add_argument("--smoke-test", action="store_true")
    parser.add_argument("--watch", type=int, metavar="MINUTES", nargs="?", const=30,
                        help="Stay resident, appear every N minutes (default 30)")
    parser.add_argument("--dry-run", action="store_true", help="Analyze but don't show window")
    parser.add_argument("--close", type=int, default=8, metavar="SECONDS",
                        help="Auto-close after N seconds (default 8)")
    args = parser.parse_args()

    if args.smoke_test:
        sys.exit(run_smoke_tests())
    elif args.watch is not None:
        _watch_loop(args.watch)
    else:
        appear(auto_close=args.close, dry_run=args.dry_run)
