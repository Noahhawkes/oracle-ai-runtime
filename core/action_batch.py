"""
core/action_batch.py — Extended Action Batches with Progress Verification

Purpose:
  Give SOV1 a longer leash without removing the leash.
  10 actions per batch (max 25). Verified progress required to continue.
  Loop guard stops repeated no-progress patterns. Approval gates intact.

Core law:
  ORACLE gets a longer leash — not no leash.
  Unlimited desktop actions are unsafe while mouse targeting is unreliable.

Batch flow:
  [batch starts] -> actions run -> [checkpoint] -> verify progress ->
    if progress + low-risk + no failures -> auto-continue next batch
    else -> stop and report / request approval

Commands:
  CONTINUE ORACLE  — run next approved bounded batch
  AUTORUN SAFE     — allow repeated low-risk batches while progress is verified
  STOP ORACLE      — immediately halt action loop
  SAFE_SLEEP_MODE  — disable hands/browser/typing, observe/propose only
  ACTION_DRY_RUN   — print intended actions without executing
"""

import hashlib
import io
import time
import sys
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

if getattr(sys, "frozen", False):
    ROOT = Path(sys.executable).parent
else:
    ROOT = Path(__file__).parent.parent

# ── Batch limits ──────────────────────────────────────────────────────────────
DEFAULT_BATCH_LIMIT = 10
MAX_BATCH_LIMIT     = 25

# ── Approval-required actions ─────────────────────────────────────────────────
APPROVAL_REQUIRED_KEYWORDS = {
    "send", "submit", "post", "purchase", "buy", "delete", "move file",
    "rename", "modify source", "change permissions", "commit", "push",
    "archive email", "change calendar", "send email", "send message",
    "send_email", "send_message", "form_submit",
}

# ── Actions that are safe to auto-continue ────────────────────────────────────
LOW_RISK_TOOLS = {
    "take_screenshot", "focus_window", "open_program", "move_and_click",
    "type_text", "paste_text", "press_key", "hotkey", "scroll",
    "maximize_window", "minimize_window", "remember_lesson",
    "wait_for_screen_change", "select_all", "copy_selection",
}

# Mouse-specific: require before+after verification until Semantic UI Bridge is live
MOUSE_TOOLS = {"move_and_click", "right_click", "drag"}


# ── ActionRecord ──────────────────────────────────────────────────────────────

@dataclass
class ActionRecord:
    tool_name: str
    target: str          # key argument — what was acted on
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    result_text: str = ""
    progress_detected: bool = False
    screen_hash_before: str = ""
    screen_hash_after: str = ""

    def changed(self) -> bool:
        """True if screen state changed between before and after."""
        if not self.screen_hash_before or not self.screen_hash_after:
            return False
        return self.screen_hash_before != self.screen_hash_after


# ── BatchCheckpoint ───────────────────────────────────────────────────────────

@dataclass
class BatchCheckpoint:
    batch_number: int
    actions_in_batch: int
    total_actions: int
    progress_detected: bool
    screen_hash: str
    summary: str
    should_continue: bool
    stop_reason: str = ""
    approval_required: bool = False
    approval_reason: str = ""


# ── BatchController ───────────────────────────────────────────────────────────

class BatchController:
    """
    Manages extended action batches with progress verification.

    Usage:
        bc = BatchController(batch_limit=10)
        bc.start_task(goal)
        # inside tool execution:
        bc.record_action(tool_name, target, result, screen_before, screen_after)
        if bc.batch_full():
            checkpoint = bc.checkpoint()
            if not checkpoint.should_continue:
                break
        # or call check_stop_conditions() after each action
    """

    def __init__(
        self,
        batch_limit: int = DEFAULT_BATCH_LIMIT,
        autorun_safe: bool = False,
        dry_run: bool = False,
        safe_sleep: bool = False,
    ):
        self.batch_limit   = max(1, min(batch_limit, MAX_BATCH_LIMIT))
        self.autorun_safe  = autorun_safe
        self.dry_run       = dry_run
        self.safe_sleep    = safe_sleep

        self.goal          = ""
        self.stopped       = False
        self.stop_reason   = ""
        self.halted        = False   # STOP ORACLE was issued

        self._batch_actions: list[ActionRecord] = []
        self._all_actions:   list[ActionRecord] = []
        self._batch_number   = 0
        self._checkpoints:   list[BatchCheckpoint] = []

        # Loop guard: track (tool, target) pairs
        self._recent: deque = deque(maxlen=10)
        self._failure_counts: dict = {}   # (tool, target) -> consecutive failures
        self._mouse_disabled = False       # disabled per-task after 2 click failures

    # ── Control commands ──────────────────────────────────────────────────────

    def stop_oracle(self):
        """STOP ORACLE — immediately halt the action loop."""
        self.halted = True
        self.stopped = True
        self.stop_reason = "STOP ORACLE issued by Noah."
        return "STOP ORACLE: action loop halted immediately."

    def enable_autorun_safe(self):
        """AUTORUN SAFE — allow repeated low-risk batches while progress is verified."""
        self.autorun_safe = True
        return f"AUTORUN SAFE enabled. Will auto-continue low-risk batches (limit {self.batch_limit} actions each)."

    def enable_dry_run(self):
        """ACTION_DRY_RUN — print intended actions, don't execute."""
        self.dry_run = True
        return "ACTION_DRY_RUN enabled. Actions will be described but not executed."

    def enable_safe_sleep(self):
        """SAFE_SLEEP_MODE — disable hands/browser/typing."""
        self.safe_sleep = True
        return "SAFE_SLEEP_MODE enabled. Hands, browser, typing, and file changes are blocked."

    def disable_safe_sleep(self):
        self.safe_sleep = False
        return "SAFE_SLEEP_MODE disabled. Desktop actions re-enabled."

    # ── Task management ───────────────────────────────────────────────────────

    def start_task(self, goal: str):
        self.goal = goal
        self.stopped = False
        self.halted = False
        self.stop_reason = ""
        self._batch_actions.clear()
        self._all_actions.clear()
        self._batch_number = 0
        self._checkpoints.clear()
        self._recent.clear()
        self._failure_counts.clear()
        self._mouse_disabled = False

    def reset_for_continuation(self):
        """Called when Noah says CONTINUE ORACLE — start a new batch on same task."""
        self._batch_actions.clear()
        self._batch_number += 1
        self.stopped = False
        self.stop_reason = ""

    # ── Safety gates ──────────────────────────────────────────────────────────

    def is_safe_sleep_blocked(self, tool_name: str) -> Optional[str]:
        if not self.safe_sleep:
            return None
        PASSIVE = {"take_screenshot", "remember_lesson", "ask_noah",
                   "task_done", "ask_confirmation", "wait_for_screen_change"}
        if tool_name not in PASSIVE:
            return (f"SAFE_SLEEP_MODE: '{tool_name}' is blocked. "
                    "Observe-only mode active. No mouse, keyboard, browser, or file actions.")
        return None

    def is_dry_run(self, tool_name: str, inp: dict) -> Optional[str]:
        if not self.dry_run:
            return None
        return f"[ACTION_DRY_RUN] Would call: {tool_name}({inp})"

    def requires_approval(self, tool_name: str, inp: dict) -> Optional[str]:
        """Return approval-required message if this action needs Noah's OK."""
        combined = (tool_name + " " + str(inp)).lower()
        for kw in APPROVAL_REQUIRED_KEYWORDS:
            if kw in combined:
                return (f"Approval required before '{tool_name}': matches '{kw}'. "
                        "This action can leave the machine or is irreversible. "
                        "Noah must confirm before it proceeds.")
        return None

    def is_mouse_disabled(self, tool_name: str) -> Optional[str]:
        if self.safe_sleep:
            return None   # already handled by safe_sleep gate
        if tool_name in MOUSE_TOOLS and self._mouse_disabled:
            return (f"Mouse actions are disabled for this task after repeated "
                    f"no-progress clicks. Use focus_window + keyboard instead.")
        return None

    # ── Screen state ──────────────────────────────────────────────────────────

    @staticmethod
    def screen_hash() -> str:
        """Hash the current screen to detect state changes."""
        try:
            import pyautogui
            from PIL import Image
            img = pyautogui.screenshot()
            buf = io.BytesIO()
            img.resize((320, 180)).save(buf, format="PNG")   # small hash is fast
            return hashlib.md5(buf.getvalue()).hexdigest()
        except Exception:
            return ""

    # ── Action recording ──────────────────────────────────────────────────────

    def record_action(
        self,
        tool_name: str,
        target: str,
        result_text: str,
        hash_before: str = "",
        hash_after: str = "",
    ) -> ActionRecord:
        record = ActionRecord(
            tool_name=tool_name,
            target=target[:80],
            result_text=result_text[:200],
            screen_hash_before=hash_before,
            screen_hash_after=hash_after,
            progress_detected=bool(hash_before and hash_after and hash_before != hash_after),
        )
        self._batch_actions.append(record)
        self._all_actions.append(record)
        self._recent.append((tool_name, target[:40]))
        return record

    # ── Loop guard ────────────────────────────────────────────────────────────

    def loop_guard_check(self, tool_name: str, target: str) -> Optional[str]:
        """
        Return a stop message if the same action is repeating without progress.
        Thresholds: 2 consecutive identical actions for high-impact tools,
                    3 for others.
        """
        key = (tool_name, target[:40])
        threshold = 2 if tool_name in ("open_program", "type_text", "paste_text") else 3

        recent_list = list(self._recent)
        matches = sum(1 for r in recent_list[-6:] if r == key)
        if matches >= threshold:
            return (
                f"Loop guard triggered: '{tool_name}' on '{target[:40]}' "
                f"repeated {matches} times without verified progress. "
                f"Stopping to avoid runaway loop."
            )
        return None

    def record_failure(self, tool_name: str, target: str):
        """Track consecutive failures for mouse-disable logic."""
        key = (tool_name, target[:40])
        self._failure_counts[key] = self._failure_counts.get(key, 0) + 1
        if tool_name in MOUSE_TOOLS and self._failure_counts[key] >= 2:
            self._mouse_disabled = True

    def record_success(self, tool_name: str, target: str):
        key = (tool_name, target[:40])
        self._failure_counts[key] = 0

    # ── Batch management ──────────────────────────────────────────────────────

    def batch_full(self) -> bool:
        return len(self._batch_actions) >= self.batch_limit

    def total_actions(self) -> int:
        return len(self._all_actions)

    def checkpoint(self, goal: str = "") -> BatchCheckpoint:
        """
        Called after each batch. Evaluates progress and decides continue/stop.
        """
        goal = goal or self.goal
        actions = self._batch_actions
        n = len(actions)
        total = len(self._all_actions)

        # Count progress detections
        progress_count = sum(1 for a in actions if a.progress_detected)
        any_progress = progress_count > 0

        # Detect repeated no-progress
        no_progress_actions = [a for a in actions if not a.progress_detected]
        consecutive_failures = 0
        for a in reversed(actions):
            if not a.progress_detected:
                consecutive_failures += 1
            else:
                break

        # Build summary
        tool_counts: dict = {}
        for a in actions:
            tool_counts[a.tool_name] = tool_counts.get(a.tool_name, 0) + 1
        tool_summary = ", ".join(f"{k}x{v}" for k, v in tool_counts.items())
        summary = (
            f"Batch {self._batch_number + 1}: {n} actions ({tool_summary}). "
            f"Progress detected: {progress_count}/{n}."
        )

        # Auto-continue criteria (ALL must be true):
        # 1. progress was verified
        # 2. task is low-risk (all tools in LOW_RISK_TOOLS)
        # 3. no consecutive failure pattern
        # 4. AUTORUN SAFE is enabled or caller explicitly continues
        # 5. not halted
        all_low_risk = all(a.tool_name in LOW_RISK_TOOLS for a in actions)
        no_repeat_failure = consecutive_failures < 2
        can_auto_continue = (
            any_progress
            and all_low_risk
            and no_repeat_failure
            and self.autorun_safe
            and not self.halted
        )

        stop_reason = ""
        if self.halted:
            stop_reason = "STOP ORACLE issued."
        elif consecutive_failures >= 2:
            stop_reason = (
                f"Stopped: {consecutive_failures} consecutive actions without detected progress. "
                "Check that SOV1 is targeting the right window/element."
            )
        elif not any_progress and n >= 3:
            stop_reason = (
                f"Stopped: {n} actions in batch, no screen changes detected. "
                "The target may not be responding. Request Noah's direction."
            )

        should_continue = can_auto_continue and not stop_reason

        if stop_reason:
            self.stopped = True
            self.stop_reason = stop_reason

        cp = BatchCheckpoint(
            batch_number=self._batch_number,
            actions_in_batch=n,
            total_actions=total,
            progress_detected=any_progress,
            screen_hash=actions[-1].screen_hash_after if actions else "",
            summary=summary,
            should_continue=should_continue,
            stop_reason=stop_reason,
        )
        self._checkpoints.append(cp)
        self._batch_actions.clear()
        self._batch_number += 1
        return cp

    def checkpoint_report(self, cp: BatchCheckpoint) -> str:
        lines = [
            "",
            f"  [BATCH {cp.batch_number + 1} CHECKPOINT]",
            f"  Actions this batch : {cp.actions_in_batch}",
            f"  Total actions      : {cp.total_actions}",
            f"  Progress detected  : {'YES' if cp.progress_detected else 'NO'}",
            f"  Summary            : {cp.summary}",
        ]
        if cp.stop_reason:
            lines.append(f"  STOPPED            : {cp.stop_reason}")
        if cp.should_continue:
            lines.append(f"  AUTO-CONTINUE      : YES (AUTORUN SAFE + progress verified)")
        else:
            lines.append(f"  STATUS             : Paused. Say 'CONTINUE ORACLE' to run next batch.")
        if cp.approval_required:
            lines.append(f"  APPROVAL NEEDED    : {cp.approval_reason}")
        lines.append("")
        return "\n".join(lines)

    def status(self) -> str:
        return (
            f"BatchController | batch_limit={self.batch_limit} | "
            f"batch={self._batch_number} | total_actions={self.total_actions()} | "
            f"autorun={self.autorun_safe} | dry_run={self.dry_run} | "
            f"safe_sleep={self.safe_sleep} | stopped={self.stopped} | "
            f"mouse_disabled={self._mouse_disabled}"
        )


# ── Module-level shared instance ──────────────────────────────────────────────
# SOV1 imports and uses this — one instance per Python process.

_bc: Optional[BatchController] = None


def get_batch_controller(
    batch_limit: int = DEFAULT_BATCH_LIMIT,
    autorun_safe: bool = False,
    dry_run: bool = False,
    safe_sleep: bool = False,
) -> BatchController:
    """Return the shared BatchController, creating if needed."""
    global _bc
    if _bc is None:
        _bc = BatchController(
            batch_limit=batch_limit,
            autorun_safe=autorun_safe,
            dry_run=dry_run,
            safe_sleep=safe_sleep,
        )
    return _bc


def reset_batch_controller(**kwargs) -> BatchController:
    """Force a fresh BatchController (call when starting a new goal)."""
    global _bc
    _bc = BatchController(**kwargs)
    return _bc


# ── Smoke test ────────────────────────────────────────────────────────────────

def _smoke_test():
    print("=" * 60)
    print("action_batch.py — Smoke Test (dry run, no desktop actions)")
    print("=" * 60)

    passed = 0
    failed = 0

    def check(label: str, condition: bool, detail: str = ""):
        nonlocal passed, failed
        status = "PASS" if condition else "FAIL"
        print(f"  [{status}] {label}")
        if not condition and detail:
            print(f"         {detail}")
        if condition:
            passed += 1
        else:
            failed += 1

    # ── Test 1: 10 low-risk actions complete then checkpoint ──────────────────
    bc = BatchController(batch_limit=10, autorun_safe=False)
    bc.start_task("Open Notepad and type a message")
    fake_hash_a = "aaa"
    fake_hash_b = "bbb"
    for i in range(10):
        ha = fake_hash_a if i % 2 == 0 else fake_hash_b
        hb = fake_hash_b if i % 2 == 0 else fake_hash_a
        bc.record_action("type_text", f"line{i}", f"Typed line{i}", ha, hb)

    check("10 actions fills batch", bc.batch_full())
    check("Total actions = 10", bc.total_actions() == 10)
    cp = bc.checkpoint()
    check("Checkpoint created after 10 actions", cp.actions_in_batch == 10)
    check("Progress detected in batch", cp.progress_detected)
    check("No auto-continue without AUTORUN SAFE", not cp.should_continue)
    check("Batch counter incremented", bc._batch_number == 1)

    # ── Test 2: AUTORUN SAFE auto-continues when progress is verified ─────────
    bc2 = BatchController(batch_limit=5, autorun_safe=True)
    bc2.start_task("Navigate Chrome")
    for i in range(5):
        bc2.record_action("move_and_click", f"btn{i}", "Clicked", "h1", "h2")
    cp2 = bc2.checkpoint()
    check("AUTORUN SAFE + progress => auto-continue", cp2.should_continue)
    check("No stop_reason on clean batch", not cp2.stop_reason)

    # ── Test 3: Stop after repeated Chrome open with no typing ───────────────
    bc3 = BatchController(batch_limit=10)
    bc3.start_task("Open Chrome and navigate")
    same_hash = "xxxx"
    for _ in range(3):
        bc3.record_action("open_program", "chrome", "Opened", same_hash, same_hash)
    lg = bc3.loop_guard_check("open_program", "chrome")
    check("Loop guard triggers after 2 identical open_program", lg is not None)
    check("Loop guard message mentions 'Loop guard'", lg and "Loop guard" in lg)

    # ── Test 4: Stop after failed mouse clicks ────────────────────────────────
    bc4 = BatchController(batch_limit=10)
    bc4.start_task("Click a button")
    bc4.record_failure("move_and_click", "100,200")
    bc4.record_failure("move_and_click", "100,200")
    check("Mouse disabled after 2 failures", bc4._mouse_disabled)
    blocked = bc4.is_mouse_disabled("move_and_click")
    check("is_mouse_disabled returns message", blocked is not None)

    # ── Test 5: Stop after failed type_text ───────────────────────────────────
    bc5 = BatchController(batch_limit=10)
    bc5.start_task("Type into search box")
    same_h = "sss"
    for _ in range(2):
        bc5.record_action("type_text", "hello", "Typed", same_h, same_h)
    lg5 = bc5.loop_guard_check("type_text", "hello")
    check("Loop guard triggers after 2 identical type_text", lg5 is not None)

    # ── Test 6: Approval required before submit/send/delete ───────────────────
    bc6 = BatchController()
    r_submit = bc6.requires_approval("form_submit", {"form": "checkout"})
    check("submit triggers approval gate", r_submit is not None)
    r_send = bc6.requires_approval("send_email", {"to": "test@test.com"})
    check("send_email triggers approval gate", r_send is not None)
    r_delete = bc6.requires_approval("delete", {"file": "doc.txt"})
    check("delete triggers approval gate", r_delete is not None)
    r_click = bc6.requires_approval("move_and_click", {"x": 100, "y": 200})
    check("safe click does NOT trigger approval gate", r_click is None)

    # ── Test 7: STOP ORACLE halts loop ────────────────────────────────────────
    bc7 = BatchController(batch_limit=10, autorun_safe=True)
    bc7.start_task("Long task")
    bc7.record_action("type_text", "something", "Typed", "h1", "h2")
    msg = bc7.stop_oracle()
    check("STOP ORACLE sets halted=True", bc7.halted)
    check("STOP ORACLE sets stopped=True", bc7.stopped)
    check("STOP ORACLE returns message", "STOP ORACLE" in msg)
    cp7 = bc7.checkpoint()
    check("Checkpoint after STOP does not auto-continue", not cp7.should_continue)
    check("Checkpoint stop_reason mentions STOP ORACLE", "STOP ORACLE" in cp7.stop_reason)

    # ── Test 8: SAFE_SLEEP_MODE blocks hands ──────────────────────────────────
    bc8 = BatchController(safe_sleep=True)
    r_type = bc8.is_safe_sleep_blocked("type_text")
    check("SAFE_SLEEP blocks type_text", r_type is not None)
    r_click2 = bc8.is_safe_sleep_blocked("move_and_click")
    check("SAFE_SLEEP blocks move_and_click", r_click2 is not None)
    r_shot = bc8.is_safe_sleep_blocked("take_screenshot")
    check("SAFE_SLEEP allows take_screenshot", r_shot is None)
    r_lesson = bc8.is_safe_sleep_blocked("remember_lesson")
    check("SAFE_SLEEP allows remember_lesson", r_lesson is None)

    # ── Test 9: ACTION_DRY_RUN prints intent, does not execute ───────────────
    bc9 = BatchController(dry_run=True)
    dry_msg = bc9.is_dry_run("open_program", {"name": "chrome"})
    check("ACTION_DRY_RUN returns description", dry_msg is not None)
    check("ACTION_DRY_RUN message contains tool name", dry_msg and "open_program" in dry_msg)

    # ── Test 10: No-progress batch stops with explanation ─────────────────────
    bc10 = BatchController(batch_limit=5, autorun_safe=True)
    bc10.start_task("Click unresponsive button")
    same = "zzzz"
    for _ in range(5):
        bc10.record_action("move_and_click", "btn", "Clicked", same, same)
    cp10 = bc10.checkpoint()
    check("No-progress batch stops auto-continue", not cp10.should_continue)
    check("No-progress batch has stop_reason", bool(cp10.stop_reason))

    print(f"\n{passed}/{passed + failed} smoke tests passed.")
    if failed:
        print(f"FAILED: {failed} test(s).")
    else:
        print("All smoke tests passed.")
    return failed == 0


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    ok = _smoke_test()
    sys.exit(0 if ok else 1)
