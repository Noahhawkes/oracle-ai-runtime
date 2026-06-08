"""
core/resident_runtime.py — ORACLE Resident Runtime v0.1

The heartbeat. The wings.

This is the loop that makes ORACLE actually live on Noah's machine.
Every cycle:
  1. Run oracle_runtime priority cycle (decide what matters most)
  2. Refresh resident dashboard (HTML)
  3. Appear on screen (presence window — optional)
  4. Award MindCoin for the cycle
  5. Sleep until next tick

ORACLE proposes. ORACLE does not approve her own proposals.
Noah holds the sovereign 51%.

Usage:
  python core/resident_runtime.py              # start resident loop (30 min default)
  python core/resident_runtime.py --interval 10  # cycle every 10 minutes
  python core/resident_runtime.py --once        # run one cycle and exit
  python core/resident_runtime.py --no-presence # cycle without showing popup
  python core/resident_runtime.py --status      # print current state and exit
  python core/resident_runtime.py --smoke-test  # verify all wiring

Law: ORACLE may run cycles. ORACLE may not grant herself authority.
     ORACLE may not act on irreversible actions without Noah approval.
"""

from __future__ import annotations

import json
import sys
import time
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

if getattr(sys, "frozen", False):
    ROOT = Path(sys.executable).parent
else:
    ROOT = Path(__file__).parent.parent

sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "core"))

# ── Runtime config ────────────────────────────────────────────────────────────
DEFAULT_INTERVAL_MINUTES = 30
RUNTIME_STATE_FILE = ROOT / "Memory" / "resident_runtime_state.json"
CYCLE_COUNT_FILE   = ROOT / "Memory" / "resident_cycle_count.json"


# ── State ─────────────────────────────────────────────────────────────────────

def _load_runtime_state() -> dict:
    try:
        return json.loads(RUNTIME_STATE_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {
            "status": "stopped",
            "started_at": None,
            "last_cycle_at": None,
            "cycle_count": 0,
            "last_priority": None,
            "last_action": None,
            "last_cycle_id": None,
            "interval_minutes": DEFAULT_INTERVAL_MINUTES,
        }


def _save_runtime_state(state: dict) -> None:
    RUNTIME_STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    RUNTIME_STATE_FILE.write_text(
        json.dumps(state, indent=2, ensure_ascii=False), encoding="utf-8"
    )


def _inc_cycle_count() -> int:
    try:
        d = json.loads(CYCLE_COUNT_FILE.read_text(encoding="utf-8"))
        count = d.get("count", 0) + 1
    except Exception:
        count = 1
    CYCLE_COUNT_FILE.parent.mkdir(parents=True, exist_ok=True)
    CYCLE_COUNT_FILE.write_text(json.dumps({"count": count}), encoding="utf-8")
    return count


# ── Step 1: oracle_runtime cycle ─────────────────────────────────────────────

def _run_priority_cycle() -> dict:
    """
    Run one oracle_runtime priority cycle.
    Returns a summary dict — never raises.
    """
    result = {
        "priority": "unknown",
        "action": "cycle ran",
        "approval_required": False,
        "confidence": 0.5,
        "next_step": "",
        "cycle_id": "unknown",
        "error": None,
    }
    try:
        from oracle_runtime import run_cycle, MODE_DAEMON_SAFE
        cycle = run_cycle(mode=MODE_DAEMON_SAFE)

        result["priority"]          = cycle.selected_priority or "unknown"
        result["action"]            = cycle.action_taken or cycle.stopped_reason or "cycle complete"
        result["approval_required"] = cycle.approval_required
        result["confidence"]        = cycle.confidence
        result["next_step"]         = cycle.next_recommended_step
        result["cycle_id"]          = cycle.id
    except Exception as e:
        result["error"] = str(e)
        result["action"] = f"cycle error: {e}"
    return result


# ── Step 2: refresh dashboard ─────────────────────────────────────────────────

def _refresh_dashboard() -> Optional[Path]:
    """Regenerate the HTML dashboard. Returns path or None on error."""
    try:
        from resident_dashboard import write_dashboard
        return write_dashboard()
    except Exception as e:
        try:
            from audit_log import log
            log("RESIDENT_RUNTIME", f"dashboard refresh failed: {e}")
        except Exception:
            pass
        return None


# ── Step 3: presence window ───────────────────────────────────────────────────

def _show_presence(cycle_result: dict, cycle_num: int) -> None:
    """Show the upgraded presence window with cycle context. Non-blocking."""
    try:
        from oracle_presence import _take_screenshot, _analyze_screen, _get_oracle_context, _log_presence
        import oracle_presence as _op

        png, screen_hash, w, h = _take_screenshot()
        analysis = _analyze_screen(png)
        del png
        ctx = _get_oracle_context()
        _log_presence(screen_hash, analysis, ctx)

        # Inject cycle result into ctx for the window
        ctx["cycle_priority"] = cycle_result.get("priority", "")
        ctx["cycle_action"]   = cycle_result.get("action", "")[:90]
        ctx["cycle_num"]      = cycle_num
        ctx["cycle_error"]    = cycle_result.get("error")
        ctx["approval_req"]   = cycle_result.get("approval_required", False)

        # Run window in a thread so the runtime loop doesn't block
        t = threading.Thread(
            target=_show_resident_presence_window,
            args=(analysis, ctx),
            daemon=True,
        )
        t.start()
        t.join(timeout=30)   # wait up to 30s for window to close itself
    except Exception as e:
        try:
            from audit_log import log
            log("RESIDENT_RUNTIME", f"presence window failed: {e}")
        except Exception:
            pass


def _show_resident_presence_window(analysis: dict, ctx: dict,
                                    auto_close_seconds: int = 10) -> None:
    """
    Upgraded presence window — shows cycle results, not just static state.
    Same always-on-top design; richer content.
    """
    import tkinter as tk
    from tkinter import font as tkfont

    mood     = analysis.get("mood", "dark")
    mode     = ctx.get("mode", "IDLE")
    project  = ctx.get("project", "ORACLE.AI")
    priority = ctx.get("cycle_priority", "")
    action   = ctx.get("cycle_action", "")
    cycle_n  = ctx.get("cycle_num", "?")
    approval = ctx.get("approval_req", False)
    error    = ctx.get("cycle_error")

    # Colour palette
    if mood == "bright":
        bg, border, text_main, text_sub, accent = "#1c1c1c", "#d29922", "#ffffff", "#cccccc", "#d29922"
    elif mood == "medium":
        bg, border, text_main, text_sub, accent = "#161b22", "#3fb950", "#e6edf3", "#8b949e", "#3fb950"
    else:
        bg, border, text_main, text_sub, accent = "#0d0f14", "#58a6ff", "#e6edf3", "#8b949e", "#58a6ff"

    if approval:
        border = "#d29922"
        accent = "#d29922"
    if error:
        border = "#f85149"
        accent = "#f85149"

    root = tk.Tk()
    root.overrideredirect(True)
    root.attributes("-topmost", True)
    root.attributes("-alpha", 0.97)
    root.configure(bg=bg)

    screen_w = root.winfo_screenwidth()
    screen_h = root.winfo_screenheight()
    win_w, win_h = 460, 230
    x = screen_w - win_w - 24
    y = screen_h - win_h - 60
    root.geometry(f"{win_w}x{win_h}+{x}+{y}")

    outer = tk.Frame(root, bg=border, padx=2, pady=2)
    outer.pack(fill="both", expand=True)
    inner = tk.Frame(outer, bg=bg, padx=18, pady=12)
    inner.pack(fill="both", expand=True)

    # Header row
    hdr = tk.Frame(inner, bg=bg)
    hdr.pack(fill="x")
    tkfont_ = tkfont.Font(family="Segoe UI", size=9, weight="bold")
    tk.Label(hdr, text="ORACLE.AI", font=tkfont_, fg=accent, bg=bg).pack(side="left")
    cycle_font = tkfont.Font(family="Segoe UI", size=8)
    tk.Label(hdr, text=f"cycle #{cycle_n}  |  {mode}  |  {project}",
             font=cycle_font, fg=text_sub, bg=bg).pack(side="right")

    # Main message
    main_font = tkfont.Font(family="Segoe UI", size=14, weight="bold")
    msg = "I see you. I got this." if not error else "I ran into an issue."
    tk.Label(inner, text=msg, font=main_font, fg=text_main, bg=bg, anchor="w"
             ).pack(fill="x", pady=(6, 0))

    # Priority / action line
    sub_font = tkfont.Font(family="Segoe UI", size=9)
    if priority and not error:
        pri_display = priority.replace("_", " ").title()
        tk.Label(inner, text=f"Priority: {pri_display}", font=sub_font,
                 fg=accent, bg=bg, anchor="w").pack(fill="x", pady=(4, 0))

    if action:
        act_font = tkfont.Font(family="Segoe UI", size=8, slant="italic")
        label_text = f"Did: {action}" if not error else f"Error: {action[:80]}"
        tk.Label(inner, text=label_text, font=act_font,
                 fg=text_sub if not error else "#f85149",
                 bg=bg, anchor="w", wraplength=420).pack(fill="x", pady=(2, 0))

    if approval:
        appr_font = tkfont.Font(family="Segoe UI", size=9, weight="bold")
        tk.Label(inner, text="[APPROVAL REQUIRED] — check pending queue",
                 font=appr_font, fg="#d29922", bg=bg, anchor="w").pack(fill="x", pady=(4, 0))

    # Queue status
    vid_p  = ctx.get("vid_pending", 0)
    mc_p   = ctx.get("mc_pending", 0)
    next_s = ctx.get("next_step", "")[:70]
    queue_parts = []
    if vid_p:
        queue_parts.append(f"{vid_p} video pending")
    if mc_p:
        queue_parts.append(f"{mc_p} MindCoin pending")
    if queue_parts:
        tk.Label(inner, text="Queue: " + "  |  ".join(queue_parts),
                 font=sub_font, fg=text_sub, bg=bg, anchor="w").pack(fill="x", pady=(4, 0))

    if next_s and not approval:
        nxt_font = tkfont.Font(family="Segoe UI", size=8)
        tk.Label(inner, text=f"Next: {next_s}", font=nxt_font,
                 fg=accent, bg=bg, anchor="w", wraplength=420).pack(fill="x", pady=(2, 0))

    # Bottom bar
    bottom = tk.Frame(inner, bg=bg)
    bottom.pack(fill="x", side="bottom", pady=(8, 0))

    remaining = [auto_close_seconds]
    cv = tk.StringVar(value=f"closing in {auto_close_seconds}s")
    tk.Label(bottom, textvariable=cv, font=cycle_font, fg=text_sub, bg=bg).pack(side="left")
    tk.Button(bottom, text="x dismiss", font=cycle_font,
              fg=text_sub, bg=bg, activeforeground=text_main, activebackground=bg,
              relief="flat", bd=0, cursor="hand2",
              command=root.destroy).pack(side="right")

    def _tick():
        if remaining[0] <= 0:
            try:
                root.destroy()
            except Exception:
                pass
            return
        remaining[0] -= 1
        cv.set(f"closing in {remaining[0]}s")
        root.after(1000, _tick)
    root.after(1000, _tick)

    drag = {"x": 0, "y": 0}
    def _start(e):
        drag["x"] = e.x_root - root.winfo_x()
        drag["y"] = e.y_root - root.winfo_y()
    def _move(e):
        root.geometry(f"+{e.x_root - drag['x']}+{e.y_root - drag['y']}")
    inner.bind("<ButtonPress-1>", _start)
    inner.bind("<B1-Motion>", _move)

    root.mainloop()


# ── Step 4: MindCoin for cycle ────────────────────────────────────────────────

def _award_cycle_mindcoin(cycle_result: dict, cycle_num: int) -> None:
    try:
        from mindcoin import award_for_completion, save_ledger, load_ledger, EVENT_VERIFIED_ACTION_COMPLETED
        ledger, events = load_ledger()
        ev = award_for_completion(
            event_type="project_state_recovered",
            source_id=cycle_result.get("cycle_id", "unknown"),
            evidence=f"resident_runtime cycle #{cycle_num} — {cycle_result.get('priority', 'unknown')}",
            title=f"Resident cycle #{cycle_num}: {cycle_result.get('action', '')[:60]}",
            project_name="ORACLE.AI",
        )
        events.append(ev)
        save_ledger(ledger, events)
    except Exception:
        pass


# ── Logging ───────────────────────────────────────────────────────────────────

def _log(msg: str) -> None:
    try:
        from audit_log import log
        log("RESIDENT_RUNTIME", msg)
    except Exception:
        pass
    ts = datetime.now(timezone.utc).strftime("%H:%M:%S")
    print(f"[{ts}] ORACLE: {msg}", flush=True)


# ── One cycle ─────────────────────────────────────────────────────────────────

def run_one_cycle(show_presence: bool = True) -> dict:
    """
    Execute one full resident cycle:
      oracle_runtime → dashboard → presence → mindcoin
    Returns summary dict.
    """
    cycle_num = _inc_cycle_count()
    _log(f"--- Cycle #{cycle_num} starting ---")

    # 1. Priority cycle
    _log("Running priority cycle...")
    cycle_result = _run_priority_cycle()
    _log(f"Priority: {cycle_result['priority']}  |  {cycle_result['action'][:60]}")
    if cycle_result.get("error"):
        _log(f"Cycle error: {cycle_result['error']}")

    # 2. Dashboard
    _log("Refreshing dashboard...")
    dash_path = _refresh_dashboard()
    if dash_path:
        _log(f"Dashboard: {dash_path.name}")

    # 3. Presence
    if show_presence:
        _log("Showing presence window...")
        _show_presence(cycle_result, cycle_num)

    # 4. MindCoin
    _award_cycle_mindcoin(cycle_result, cycle_num)

    # 5. Save runtime state
    state = _load_runtime_state()
    state.update({
        "status": "running",
        "last_cycle_at": datetime.now(timezone.utc).isoformat(),
        "cycle_count": cycle_num,
        "last_priority": cycle_result["priority"],
        "last_action": cycle_result["action"][:80],
        "last_cycle_id": cycle_result["cycle_id"],
    })
    _save_runtime_state(state)

    _log(f"--- Cycle #{cycle_num} complete ---")
    return cycle_result


# ── Main loop ─────────────────────────────────────────────────────────────────

def run_loop(interval_minutes: int = DEFAULT_INTERVAL_MINUTES,
             show_presence: bool = True) -> None:
    """
    Main resident loop. Runs forever until Ctrl+C.
    Cycle → sleep → cycle → sleep ...
    """
    state = _load_runtime_state()
    state["status"] = "running"
    state["started_at"] = datetime.now(timezone.utc).isoformat()
    state["interval_minutes"] = interval_minutes
    _save_runtime_state(state)

    _log(f"ORACLE Resident Runtime starting — cycle every {interval_minutes} min")
    _log(f"Presence: {'enabled' if show_presence else 'disabled'}")
    _log("Press Ctrl+C to stop gracefully.")

    try:
        while True:
            run_one_cycle(show_presence=show_presence)
            _log(f"Sleeping {interval_minutes} min until next cycle...")
            time.sleep(interval_minutes * 60)
    except KeyboardInterrupt:
        _log("Resident runtime stopped by Noah (Ctrl+C).")
        state = _load_runtime_state()
        state["status"] = "stopped"
        _save_runtime_state(state)


# ── Status report ─────────────────────────────────────────────────────────────

def print_status() -> None:
    state = _load_runtime_state()
    from resident_dashboard import collect_dashboard_state
    ds = collect_dashboard_state()
    s  = ds.get("session", {})
    q  = ds.get("queue", {})
    h  = ds.get("health", {})
    na = ds.get("next_action", {})

    print(f"\n{'='*55}")
    print("  ORACLE Resident Runtime — Status")
    print(f"{'='*55}")
    print(f"  Runtime status  : {state.get('status', 'unknown')}")
    print(f"  Cycles run      : {state.get('cycle_count', 0)}")
    print(f"  Last cycle      : {state.get('last_cycle_at', 'never')[:19]}")
    print(f"  Last priority   : {state.get('last_priority', 'none')}")
    print(f"  Last action     : {state.get('last_action', '')[:60]}")
    print(f"  Interval        : {state.get('interval_minutes', DEFAULT_INTERVAL_MINUTES)} min")
    print(f"  ---")
    print(f"  Session mode    : {s.get('mode', '?')}")
    print(f"  Ollama          : {'running' if h.get('ollama_running') else 'OFFLINE'}")
    print(f"  Git HEAD        : {h.get('git_head', '?')}")
    print(f"  Pending queue   : {q.get('mem_pending',0)} memory  "
          f"{q.get('vid_pending',0)} video  {q.get('mc_pending',0)} MindCoin")
    print(f"  Next action     : {na.get('action', '')[:70]}")
    print(f"{'='*55}\n")


# ── Smoke tests ───────────────────────────────────────────────────────────────

def run_smoke_tests() -> int:
    failures = 0
    results = []

    def check(name: str, passed: bool, detail: str = "") -> None:
        nonlocal failures
        if not passed:
            failures += 1
        tag = "PASS" if passed else "FAIL"
        results.append(f"  [{tag}] {name}" + (f" -- {detail}" if detail else ""))

    print(f"\n{'='*55}")
    print("ORACLE Resident Runtime -- Smoke Tests")
    print(f"{'='*55}")

    # 1. State load/save roundtrip
    import tempfile, os as _os
    orig = RUNTIME_STATE_FILE
    try:
        tmp = Path(tempfile.mkdtemp()) / "test_runtime_state.json"
        # Monkey-patch for test
        import resident_runtime as _self
        _self.RUNTIME_STATE_FILE = tmp
        _save_runtime_state({"status": "test", "cycle_count": 42})
        loaded = _load_runtime_state()
        check("state save/load roundtrip", loaded.get("status") == "test")
        check("state cycle_count preserved", loaded.get("cycle_count") == 42)
    except Exception as e:
        check("state save/load", False, str(e))
    finally:
        import resident_runtime as _self
        _self.RUNTIME_STATE_FILE = orig

    # 2. Cycle count increments
    import resident_runtime as _self
    orig_cc = _self.CYCLE_COUNT_FILE
    try:
        tmp_cc = Path(tempfile.mkdtemp()) / "test_cycle_count.json"
        _self.CYCLE_COUNT_FILE = tmp_cc
        n1 = _inc_cycle_count()
        n2 = _inc_cycle_count()
        check("cycle count increments", n2 == n1 + 1)
        check("cycle count n1 is int > 0", isinstance(n1, int) and n1 >= 1)
    except Exception as e:
        check("cycle count", False, str(e))
    finally:
        _self.CYCLE_COUNT_FILE = orig_cc

    # 3. _run_priority_cycle: no crash
    try:
        result = _run_priority_cycle()
        check("priority cycle: no crash", True)
        check("priority cycle: has priority key", "priority" in result)
        check("priority cycle: has action key", "action" in result)
        check("priority cycle: has confidence", "confidence" in result)
    except Exception as e:
        check("priority cycle: no crash", False, str(e))

    # 4. _refresh_dashboard: no crash, returns path or None
    try:
        path = _refresh_dashboard()
        check("dashboard refresh: no crash", True)
        check("dashboard refresh: returns path or None",
              path is None or isinstance(path, Path))
        if path and path.exists():
            check("dashboard refresh: file has content", path.stat().st_size > 500)
    except Exception as e:
        check("dashboard refresh: no crash", False, str(e))

    # 5. run_one_cycle dry-run (no presence window)
    try:
        cr = run_one_cycle(show_presence=False)
        check("run_one_cycle no-presence: no crash", True)
        check("run_one_cycle: returns dict", isinstance(cr, dict))
        check("run_one_cycle: has priority", "priority" in cr)
        # State file written
        check("run_one_cycle: state file updated", RUNTIME_STATE_FILE.exists())
        state = _load_runtime_state()
        check("run_one_cycle: status=running", state.get("status") == "running")
    except Exception as e:
        check("run_one_cycle no-presence: no crash", False, str(e))

    # 6. print_status: no crash
    import io as _io
    old_stdout = sys.stdout
    sys.stdout = _io.StringIO()
    try:
        print_status()
        output = sys.stdout.getvalue()
        check("print_status: no crash", True)
        check("print_status: contains cycles", "Cycles" in output)
    except Exception as e:
        check("print_status: no crash", False, str(e))
    finally:
        sys.stdout = old_stdout

    # Print results
    for r in results:
        print(r)
    total  = len(results)
    passed = total - failures
    print(f"{'='*55}")
    print(f"Result: {passed}/{total} passed")
    print(f"STATUS: {'ALL PASS' if failures == 0 else str(failures) + ' FAILURES'}")
    print(f"{'='*55}\n")
    return failures


# ── CLI ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="ORACLE Resident Runtime")
    parser.add_argument("--once",        action="store_true", help="Run one cycle and exit")
    parser.add_argument("--no-presence", action="store_true", help="Cycle without presence window")
    parser.add_argument("--interval",    type=int, default=DEFAULT_INTERVAL_MINUTES,
                        metavar="MINUTES", help=f"Cycle interval in minutes (default {DEFAULT_INTERVAL_MINUTES})")
    parser.add_argument("--status",      action="store_true", help="Print status and exit")
    parser.add_argument("--smoke-test",  action="store_true")
    args = parser.parse_args()

    if args.smoke_test:
        sys.exit(run_smoke_tests())
    elif args.status:
        print_status()
    elif args.once:
        run_one_cycle(show_presence=not args.no_presence)
    else:
        run_loop(
            interval_minutes=args.interval,
            show_presence=not args.no_presence,
        )
