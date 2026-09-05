"""
core/desktop_ai_bridge.py — ORACLE Desktop AI Bridge v0.1

Supervised bridge for routing prompts to visible desktop AI tools.

Supported targets: ChatGPT · Claude · Codex · SOV1 · Browser (generic)

Architecture (one confirmed action at a time):
  1. ORACLE drafts a prompt          (always free — green)
  2. ORACLE stages it                (always free — green)
  3. Noah reviews the staged prompt  (always free — green)
  4. Noah confirms /send-staged      (yellow — needs "yes")
  5. Bridge copies prompt to clipboard and focuses target window
  6. Noah presses Ctrl+V or ORACLE pastes (second confirmation gate)
  7. /capture-response attempts OCR or instructs manual paste-back

Safety laws (enforced in code, not just docs):
  - send_staged() refuses to execute without confirmed=True (Noah approval)
  - stage_prompt() scans for credential patterns and refuses to stage them
  - No empty prompts
  - Codex target uses existing file bridge (no new channel)
  - SOV1 target routes to sov1.py subprocess
  - All sends logged to audit_log
  - Clear failure message if pyautogui or clipboard are unavailable

Risk levels:
  GREEN  — draft, stage, list targets, /desktop-doctor
  YELLOW — focus window, copy to clipboard, paste/inject, capture
  RED    — credentials, governance, scope approval, git commit/push/delete
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

if getattr(sys, "frozen", False):
    ROOT = Path(sys.executable).parent
else:
    ROOT = Path(__file__).parent.parent

sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "core"))

STAGED_PROMPT_FILE = ROOT / "Memory" / "desktop_ai_staged_prompt.json"
RESPONSE_INBOX_FILE = ROOT / "Messages" / "desktop_ai_response.md"

# ── Credential scanner (reuses patterns from claude_code_bridge) ──────────────

_CREDENTIAL_PATTERNS = [
    re.compile(r"sk-[A-Za-z0-9]{20,}", re.I),
    re.compile(r"api[_\-]?key\s*[=:]\s*\S+", re.I),
    re.compile(r"secret\s*[=:]\s*\S{6,}", re.I),
    re.compile(r"password\s*[=:]\s*\S{4,}", re.I),
    re.compile(r"token\s*[=:]\s*[A-Za-z0-9\-._~+/]{20,}", re.I),
    re.compile(r"bearer\s+[A-Za-z0-9\-._~+/]{20,}", re.I),
    re.compile(r"[A-Za-z0-9+/]{40,}={0,2}"),  # base64-like blobs — likely encoded secrets
]

# Actions that are always red — never allow via this bridge
_RED_VERBS = frozenset([
    "commit", "push to", "delete", "rm -", "drop table", "truncate",
    "approve memory", "approve scope", "approve path", "set governance",
    "change doctrine", "update identity", "alter soul", "store api key",
    "store password", "store secret", "send credentials",
])


def contains_credential(text: str) -> tuple[bool, str]:
    """Return (True, matched_snippet) if text contains credential patterns."""
    for pat in _CREDENTIAL_PATTERNS:
        m = pat.search(text)
        if m:
            snippet = m.group(0)[:30]
            return True, snippet
    return False, ""


def contains_red_verb(text: str) -> tuple[bool, str]:
    """Return (True, verb) if text contains a red-level action verb."""
    lower = text.lower()
    for verb in _RED_VERBS:
        if verb in lower:
            return True, verb
    return False, ""


# ── Target definitions ────────────────────────────────────────────────────────

HANDOFF_CLIPBOARD = "clipboard_paste"
HANDOFF_FILE      = "file_channel"
HANDOFF_SUBPROCESS = "subprocess"

CAPTURE_MANUAL    = "manual"
CAPTURE_FILE      = "file_watch"
CAPTURE_STDOUT    = "stdout"

RISK_GREEN  = "green"
RISK_YELLOW = "yellow"
RISK_RED    = "red"

STATUS_FOUND   = "found"
STATUS_UNKNOWN = "unknown"
STATUS_MISSING = "not_found"


@dataclass(frozen=True)
class DesktopAITarget:
    key: str
    name: str
    description: str
    window_title_keywords: tuple         # substrings to look for in window titles (case-insensitive)
    process_names: tuple                 # exe names to check via tasklist
    launch_url: str                      # URL to open if browser launch needed
    handoff_method: str                  # HANDOFF_* constant
    response_capture: str               # CAPTURE_* constant
    risk_level: str                      # RISK_* constant
    confirmation_required: bool = True   # always True for external targets


TARGETS: dict[str, DesktopAITarget] = {
    "chatgpt": DesktopAITarget(
        key="chatgpt",
        name="ChatGPT",
        description="OpenAI ChatGPT via browser",
        window_title_keywords=("chatgpt", "chat.openai.com"),
        process_names=("chrome.exe", "msedge.exe", "firefox.exe", "brave.exe"),
        launch_url="https://chat.openai.com",
        handoff_method=HANDOFF_CLIPBOARD,
        response_capture=CAPTURE_MANUAL,
        risk_level=RISK_YELLOW,
        confirmation_required=True,
    ),
    "claude": DesktopAITarget(
        key="claude",
        name="Claude Desktop / Claude Code",
        description="Anthropic Claude Desktop app or Claude Code CLI",
        window_title_keywords=("claude", "claude code", "claude desktop", "claude-code"),
        process_names=("claude.exe", "node.exe"),
        launch_url="https://claude.ai",
        handoff_method=HANDOFF_CLIPBOARD,
        response_capture=CAPTURE_MANUAL,
        risk_level=RISK_YELLOW,
        confirmation_required=True,
    ),
    "codex": DesktopAITarget(
        key="codex",
        name="Codex",
        description="OpenAI Codex via file-backed channel (Messages/oracle_to_codex.md)",
        window_title_keywords=("codex",),
        process_names=("codex.exe",),
        launch_url="",
        handoff_method=HANDOFF_FILE,
        response_capture=CAPTURE_FILE,
        risk_level=RISK_YELLOW,
        confirmation_required=True,
    ),
    "sov1": DesktopAITarget(
        key="sov1",
        name="SOV1 Computer Use",
        description="ORACLE's own SOV1 computer-use operator layer (core/sov1.py)",
        window_title_keywords=(),
        process_names=(),
        launch_url="",
        handoff_method=HANDOFF_SUBPROCESS,
        response_capture=CAPTURE_STDOUT,
        risk_level=RISK_YELLOW,
        confirmation_required=True,
    ),
    "browser": DesktopAITarget(
        key="browser",
        name="Browser (generic)",
        description="Any open browser window",
        window_title_keywords=("chrome", "edge", "firefox", "brave", "opera", "safari"),
        process_names=("chrome.exe", "msedge.exe", "firefox.exe", "brave.exe"),
        launch_url="",
        handoff_method=HANDOFF_CLIPBOARD,
        response_capture=CAPTURE_MANUAL,
        risk_level=RISK_YELLOW,
        confirmation_required=True,
    ),
}


# ── Staged prompt ─────────────────────────────────────────────────────────────

@dataclass
class StagedPrompt:
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:8])
    target: str = ""
    prompt: str = ""
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    source: str = "user"
    risk: str = RISK_YELLOW
    requires_confirmation: bool = True
    sent: bool = False
    sent_at: str = ""
    existence_stage_event_id: str = ""
    existence_stage_event_hash: str = ""
    existence_handoff_event_id: str = ""
    existence_handoff_event_hash: str = ""


def save_staged(sp: StagedPrompt) -> None:
    STAGED_PROMPT_FILE.parent.mkdir(parents=True, exist_ok=True)
    STAGED_PROMPT_FILE.write_text(
        json.dumps(asdict(sp), indent=2) + "\n", encoding="utf-8"
    )


def load_staged() -> Optional[StagedPrompt]:
    if not STAGED_PROMPT_FILE.exists():
        return None
    try:
        data = json.loads(STAGED_PROMPT_FILE.read_text(encoding="utf-8"))
        return StagedPrompt(**{k: v for k, v in data.items() if k in StagedPrompt.__dataclass_fields__})
    except Exception:
        return None


def clear_staged() -> None:
    if STAGED_PROMPT_FILE.exists():
        try:
            STAGED_PROMPT_FILE.unlink()
        except Exception:
            pass


# ── Platform probes ───────────────────────────────────────────────────────────

def _probe_pyautogui() -> tuple[bool, str]:
    try:
        import pyautogui  # noqa
        return True, "pyautogui importable"
    except ImportError:
        return False, "pyautogui not installed (pip install pyautogui pillow)"
    except Exception as e:
        return False, f"pyautogui error: {e}"


def _probe_clipboard() -> tuple[bool, str]:
    """Try to write and read back a test string from the clipboard."""
    # Method 1: pyperclip (preferred)
    try:
        import pyperclip
        pyperclip.copy("__oracle_clipboard_test__")
        back = pyperclip.paste()
        if "__oracle_clipboard_test__" in back:
            return True, "pyperclip clipboard OK"
    except Exception:
        pass

    # Method 2: ctypes (Windows built-in, no install required)
    try:
        import ctypes
        CF_UNICODETEXT = 13
        GMEM_MOVEABLE = 0x0002
        test_str = "__oracle_clipboard_test__"
        encoded = test_str.encode("utf-16-le")
        ctypes.windll.user32.OpenClipboard(0)
        ctypes.windll.user32.EmptyClipboard()
        handle = ctypes.windll.kernel32.GlobalAlloc(GMEM_MOVEABLE, len(encoded) + 2)
        ptr = ctypes.windll.kernel32.GlobalLock(handle)
        ctypes.memmove(ptr, encoded, len(encoded))
        ctypes.windll.kernel32.GlobalUnlock(handle)
        ctypes.windll.user32.SetClipboardData(CF_UNICODETEXT, handle)
        ctypes.windll.user32.CloseClipboard()
        return True, "ctypes clipboard OK (Windows built-in)"
    except Exception as e:
        return False, f"clipboard unavailable: {e}"


def copy_to_clipboard(text: str) -> tuple[bool, str]:
    """Copy text to clipboard. Returns (success, message)."""
    # Method 1: pyperclip
    try:
        import pyperclip
        pyperclip.copy(text)
        return True, "Copied to clipboard via pyperclip."
    except Exception:
        pass

    # Method 2: ctypes
    try:
        import ctypes
        CF_UNICODETEXT = 13
        GMEM_MOVEABLE = 0x0002
        encoded = text.encode("utf-16-le")
        ctypes.windll.user32.OpenClipboard(0)
        ctypes.windll.user32.EmptyClipboard()
        handle = ctypes.windll.kernel32.GlobalAlloc(GMEM_MOVEABLE, len(encoded) + 2)
        ptr = ctypes.windll.kernel32.GlobalLock(handle)
        ctypes.memmove(ptr, encoded, len(encoded))
        ctypes.windll.kernel32.GlobalUnlock(handle)
        ctypes.windll.user32.SetClipboardData(CF_UNICODETEXT, handle)
        ctypes.windll.user32.CloseClipboard()
        return True, "Copied to clipboard via ctypes (Windows)."
    except Exception as e:
        return False, f"Clipboard copy failed: {e}. Paste manually."


def _probe_screenshot() -> tuple[bool, str]:
    try:
        import pyautogui
        _ = pyautogui.screenshot()
        return True, "pyautogui screenshot OK"
    except ImportError:
        return False, "pyautogui not installed"
    except Exception as e:
        return False, f"screenshot failed: {e}"


def _enum_window_titles() -> list[str]:
    """Enumerate all visible top-level window titles (Windows ctypes)."""
    titles: list[str] = []
    try:
        import ctypes
        WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_int, ctypes.c_int)

        def _cb(hwnd, _):
            if ctypes.windll.user32.IsWindowVisible(hwnd):
                length = ctypes.windll.user32.GetWindowTextLengthW(hwnd)
                if length > 0:
                    buf = ctypes.create_unicode_buffer(length + 1)
                    ctypes.windll.user32.GetWindowTextW(hwnd, buf, length + 1)
                    titles.append(buf.value)
            return True

        ctypes.windll.user32.EnumWindows(WNDENUMPROC(_cb), 0)
    except Exception:
        pass
    return titles


def _probe_window_list() -> tuple[bool, list[str]]:
    titles = _enum_window_titles()
    if titles:
        return True, titles
    return False, []


def _find_target_window(target: DesktopAITarget) -> tuple[str, str]:
    """
    Search open windows for a target.
    Returns (status, matched_title): status is STATUS_FOUND / STATUS_UNKNOWN / STATUS_MISSING.
    """
    titles = _enum_window_titles()
    if not titles:
        return STATUS_UNKNOWN, ""
    for title in titles:
        lower = title.lower()
        if any(kw in lower for kw in target.window_title_keywords):
            return STATUS_FOUND, title
    return STATUS_MISSING, ""


def _probe_process_list(target: DesktopAITarget) -> tuple[bool, str]:
    """Check tasklist for target process names."""
    if not target.process_names:
        return False, "no process names defined for this target"
    try:
        result = subprocess.run(
            ["tasklist"], capture_output=True, text=True, timeout=4
        )
        lower_output = result.stdout.lower()
        for proc in target.process_names:
            if proc.lower() in lower_output:
                return True, f"{proc} running"
        return False, f"none of {target.process_names} in process list"
    except Exception as e:
        return False, f"tasklist failed: {e}"


# ── Staging ───────────────────────────────────────────────────────────────────

class StagingError(Exception):
    pass


def stage_prompt(
    target_key: str,
    prompt: str,
    source: str = "user",
) -> StagedPrompt:
    """
    Validate and stage a prompt for a target AI tool.
    Does NOT send anything.  Always safe to call.

    Raises StagingError if:
    - target is unknown
    - prompt is empty or whitespace-only
    - prompt contains credential patterns
    - prompt contains red-level action verbs
    """
    if target_key not in TARGETS:
        raise StagingError(
            f"Unknown target: {target_key!r}. "
            f"Known targets: {', '.join(TARGETS.keys())}"
        )

    target = TARGETS[target_key]

    prompt = prompt.strip()
    if not prompt:
        raise StagingError("Prompt is empty. Provide a non-empty prompt before staging.")

    if len(prompt) > 8000:
        raise StagingError(
            f"Prompt is {len(prompt)} characters — exceeds 8000 char safety limit. "
            "Trim the prompt or split into smaller requests."
        )

    has_cred, cred_snippet = contains_credential(prompt)
    if has_cred:
        raise StagingError(
            f"Prompt appears to contain a credential or secret (matched: {cred_snippet!r}). "
            "ORACLE will not stage or send prompts containing credentials. "
            "Remove all secrets from the prompt before staging."
        )

    has_red, red_verb = contains_red_verb(prompt)
    if has_red:
        raise StagingError(
            f"Prompt contains a red-level action verb ({red_verb!r}). "
            "ORACLE will not stage prompts with destructive / governance-altering requests. "
            "Rephrase to ask a question or plan a safe action."
        )

    sp = StagedPrompt(
        target=target_key,
        prompt=prompt,
        source=source,
        risk=target.risk_level,
        requires_confirmation=target.confirmation_required,
    )
    if target_key == "sov1":
        try:
            from existence_integration import record_sov1_task_staged

            existence_event = record_sov1_task_staged(
                stage_id=sp.id,
                prompt=sp.prompt,
                source=sp.source,
                risk=sp.risk,
                requires_confirmation=sp.requires_confirmation,
            )
            sp.existence_stage_event_id = existence_event["event_id"]
            sp.existence_stage_event_hash = existence_event["event_hash"]
        except Exception as exc:
            raise StagingError(
                "SOV1 staging blocked because the ORACLE existence ledger "
                f"could not create a receipt: {type(exc).__name__}: {exc}"
            ) from exc
    save_staged(sp)
    _audit(
        "STAGE",
        (
            f"target={target_key} source={source} len={len(prompt)} "
            f"existence_event={sp.existence_stage_event_id or 'not_applicable'}"
        ),
    )
    return sp


# ── Send ──────────────────────────────────────────────────────────────────────

class SendError(Exception):
    pass


def send_staged(*, confirmed: bool = False) -> dict:
    """
    Execute the currently staged prompt.

    confirmed=True means Noah has explicitly approved this send.
    Without confirmed=True this function raises SendError immediately.

    Returns a result dict with keys: success, target, method, detail, prompt_snippet.
    """
    if not confirmed:
        raise SendError(
            "send_staged() requires confirmed=True. "
            "Noah must explicitly approve before any prompt is sent to an external tool."
        )

    sp = load_staged()
    if sp is None:
        raise SendError(
            "No staged prompt found. "
            "Use /ask-<target> <prompt> to stage a prompt first."
        )

    if sp.sent:
        raise SendError(
            f"This prompt was already sent at {sp.sent_at}. "
            "Stage a new prompt with /ask-<target> <prompt>."
        )

    target = TARGETS.get(sp.target)
    if target is None:
        raise SendError(f"Staged prompt has unknown target: {sp.target!r}.")

    _audit("SEND_START", f"target={sp.target} id={sp.id}")

    result = _dispatch(target, sp)

    sp.sent = result.get("success", False)
    sp.sent_at = datetime.now(timezone.utc).isoformat()
    if sp.target == "sov1":
        try:
            from existence_integration import record_sov1_handoff_result

            existence_event = record_sov1_handoff_result(
                stage_id=sp.id,
                prompt=sp.prompt,
                source=sp.source,
                confirmed=confirmed,
                result=result,
            )
            sp.existence_handoff_event_id = existence_event["event_id"]
            sp.existence_handoff_event_hash = existence_event["event_hash"]
            result["existence_event_id"] = existence_event["event_id"]
            result["existence_event_hash"] = existence_event["event_hash"]
        except Exception as exc:
            result["existence_logging_error"] = f"{type(exc).__name__}: {exc}"
            result["success"] = False
            sp.sent = False
    save_staged(sp)

    _audit(
        "SEND_COMPLETE" if result.get("success") else "SEND_FAILED",
        f"target={sp.target} id={sp.id} method={result.get('method')} detail={result.get('detail','')[:80]}"
    )
    return result


def _dispatch(target: DesktopAITarget, sp: StagedPrompt) -> dict:
    """Route to the correct handoff method for this target."""
    method = target.handoff_method

    if method == HANDOFF_FILE:
        return _dispatch_file(target, sp)
    elif method == HANDOFF_SUBPROCESS:
        return _dispatch_subprocess(target, sp)
    elif method == HANDOFF_CLIPBOARD:
        return _dispatch_clipboard(target, sp)
    else:
        return {
            "success": False,
            "target": sp.target,
            "method": method,
            "detail": f"Unknown handoff method: {method}",
            "prompt_snippet": sp.prompt[:80],
        }


def _dispatch_file(target: DesktopAITarget, sp: StagedPrompt) -> dict:
    """Codex: write to oracle_to_codex.md channel file."""
    try:
        from oracle_codex_channel import send_to_codex, ORACLE_TO_CODEX
        ok = send_to_codex(sp.prompt)
        return {
            "success": ok,
            "target": sp.target,
            "method": HANDOFF_FILE,
            "detail": f"Written to {ORACLE_TO_CODEX}" if ok else "send_to_codex() returned False",
            "prompt_snippet": sp.prompt[:80],
            "next_action": "Use /read-codex to retrieve Codex reply when ready.",
        }
    except Exception as e:
        return {
            "success": False,
            "target": sp.target,
            "method": HANDOFF_FILE,
            "detail": f"Codex channel error: {e}",
            "prompt_snippet": sp.prompt[:80],
        }


def _dispatch_subprocess(target: DesktopAITarget, sp: StagedPrompt) -> dict:
    """Release a SOV1 task to ORACLE's governed execution boundary.

    This handoff does not claim the desktop task has executed. The current
    repository has no durable worker that consumes the staged file.
    """
    return {
        "success": True,
        "target": sp.target,
        "method": HANDOFF_SUBPROCESS,
        "detail": (
            "SOV1 task released by ORACLE and receipted. "
            "No SOV1 execution worker consumed it in this handoff."
        ),
        "prompt_snippet": sp.prompt[:80],
        "next_action": (
            "Run SOV1 explicitly with the reviewed task until a durable "
            "ORACLE-to-SOV1 execution worker is implemented."
        ),
        "execution_completed": False,
    }


def _dispatch_clipboard(target: DesktopAITarget, sp: StagedPrompt) -> dict:
    """
    ChatGPT / Claude / Browser:
    1. Copy prompt to clipboard.
    2. Attempt to focus target window via actuation_engine.
    3. Report next step (paste Ctrl+V + press Enter).

    Does NOT press Enter automatically — that's a separate Noah confirmation.
    """
    clip_ok, clip_msg = copy_to_clipboard(sp.prompt)
    if not clip_ok:
        return {
            "success": False,
            "target": sp.target,
            "method": HANDOFF_CLIPBOARD,
            "detail": clip_msg,
            "prompt_snippet": sp.prompt[:80],
            "next_action": (
                f"Clipboard unavailable. Copy this prompt manually and paste into "
                f"{target.name}:\n\n{sp.prompt}"
            ),
        }

    # Try to focus the window
    win_status, win_title = _find_target_window(target)
    focus_detail = ""
    focus_ok = False
    if win_status == STATUS_FOUND:
        try:
            from actuation_engine import focus_target_window
            r = focus_target_window(win_title, dry_run=False)
            focus_ok = r.success or r.window_found
            focus_detail = f"Focused window: {win_title!r}"
        except Exception as e:
            focus_detail = f"Window found ({win_title!r}) but focus failed: {e}"
    elif win_status == STATUS_MISSING:
        focus_detail = (
            f"{target.name} window not found. "
            f"Open it manually ({target.launch_url or 'no launch URL'}) then paste."
        )
    else:
        focus_detail = (
            f"Window enumeration unavailable — paste manually into {target.name}."
        )

    return {
        "success": True,
        "target": sp.target,
        "method": HANDOFF_CLIPBOARD,
        "detail": f"{clip_msg} | {focus_detail}",
        "prompt_snippet": sp.prompt[:80],
        "clipboard_ok": clip_ok,
        "window_found": win_status == STATUS_FOUND,
        "window_title": win_title,
        "next_action": (
            f"Prompt is in your clipboard. "
            f"{'Click the {target.name} window then ' if not focus_ok else ''}"
            f"press Ctrl+V to paste, then press Enter to send."
        ),
    }


# ── Response capture ──────────────────────────────────────────────────────────

def capture_response(target_key: str = "") -> dict:
    """
    Attempt to capture a response from the target.
    Honest about what is and is not available.
    """
    # Check for a waiting file-channel response
    sp = load_staged()
    effective_target = target_key or (sp.target if sp else "")

    if effective_target == "codex":
        try:
            from oracle_codex_channel import CODEX_TO_ORACLE
            from oracle_codex_watcher import unread_status, mark_read
            s = unread_status()
            if s.get("unread"):
                content = CODEX_TO_ORACLE.read_text(encoding="utf-8").strip()
                mark_read()
                return {
                    "success": True,
                    "source": "codex_file_channel",
                    "content": content,
                    "detail": f"Read {len(content)} chars from {CODEX_TO_ORACLE}",
                }
            else:
                return {
                    "success": False,
                    "source": "codex_file_channel",
                    "content": "",
                    "detail": "No unread Codex reply. Use /ask-codex to send a task first.",
                }
        except Exception as e:
            return {"success": False, "source": "codex", "content": "", "detail": str(e)}

    # For clipboard/browser targets: try screenshot OCR, otherwise manual
    screenshot_ok, _ = _probe_screenshot()
    if screenshot_ok:
        return {
            "success": False,
            "source": "screenshot",
            "content": "",
            "detail": (
                "Screenshot captured but OCR is not yet implemented. "
                "Paste the response manually: write it to "
                f"{RESPONSE_INBOX_FILE} and type /capture-response again."
            ),
        }

    # Check if Noah pasted a response into the inbox file
    if RESPONSE_INBOX_FILE.exists():
        content = RESPONSE_INBOX_FILE.read_text(encoding="utf-8").strip()
        if content:
            _audit("CAPTURE", f"Manual response captured from {RESPONSE_INBOX_FILE}")
            try:
                RESPONSE_INBOX_FILE.unlink()
            except Exception:
                pass
            return {
                "success": True,
                "source": "manual_paste",
                "content": content,
                "detail": f"Read {len(content)} chars from {RESPONSE_INBOX_FILE}",
            }

    target_name = TARGETS.get(effective_target, DesktopAITarget(
        key="unknown", name="the AI tool", description="", window_title_keywords=(),
        process_names=(), launch_url="", handoff_method="", response_capture="",
        risk_level=RISK_YELLOW,
    )).name

    return {
        "success": False,
        "source": "unavailable",
        "content": "",
        "detail": (
            f"Automatic response capture is not available for {target_name}. "
            f"To use manual capture:\n"
            f"  1. Copy the response from {target_name}.\n"
            f"  2. Create the file: {RESPONSE_INBOX_FILE}\n"
            f"  3. Paste the response into that file.\n"
            f"  4. Type /capture-response and ORACLE will read it."
        ),
    }


# ── Target status listing ─────────────────────────────────────────────────────

def list_targets_with_status() -> list[dict]:
    """Probe each target and return a status dict per target."""
    results = []
    all_titles = _enum_window_titles()

    for key, target in TARGETS.items():
        # Window detection
        win_status = STATUS_UNKNOWN
        win_title = ""
        if all_titles:
            for title in all_titles:
                lower = title.lower()
                if any(kw in lower for kw in target.window_title_keywords):
                    win_status = STATUS_FOUND
                    win_title = title[:60]
                    break
            else:
                win_status = STATUS_MISSING if target.window_title_keywords else STATUS_UNKNOWN

        # Process detection
        proc_ok = False
        proc_detail = ""
        if target.process_names:
            proc_ok, proc_detail = _probe_process_list(target)

        # Special status for Codex: use file channel probe
        if key == "codex":
            ch_exists = (ROOT / "core" / "oracle_codex_channel.py").exists()
            results.append({
                "key": key,
                "name": target.name,
                "description": target.description,
                "window_status": win_status,
                "window_title": win_title,
                "process_running": proc_ok,
                "handoff_method": target.handoff_method,
                "channel_file_ok": ch_exists,
                "confirmation_required": target.confirmation_required,
                "launch_url": target.launch_url,
                "note": "Uses file channel — process status is informational only",
            })
            continue

        results.append({
            "key": key,
            "name": target.name,
            "description": target.description,
            "window_status": win_status,
            "window_title": win_title,
            "process_running": proc_ok,
            "process_detail": proc_detail,
            "handoff_method": target.handoff_method,
            "confirmation_required": target.confirmation_required,
            "launch_url": target.launch_url,
        })
    return results


def format_target_list(statuses: list[dict] | None = None) -> str:
    """Format the target list as a human-readable string."""
    if statuses is None:
        statuses = list_targets_with_status()

    lines = ["", "  [DESKTOP AI TARGETS]", ""]
    for s in statuses:
        win = s.get("window_status", STATUS_UNKNOWN)
        win_marker = {"found": "OPEN", "not_found": "NOT OPEN", "unknown": "?"}
        proc = "running" if s.get("process_running") else "not detected"
        lines.append(f"  {s['key'].upper():<12} {s['name']}")
        lines.append(f"    Window   : {win_marker.get(win, '?')} {('— ' + s.get('window_title','')[:50]) if s.get('window_title') else ''}")
        if s.get("handoff_method") == HANDOFF_FILE:
            lines.append(f"    Channel  : {'OK' if s.get('channel_file_ok') else 'MISSING'} (file bridge)")
        else:
            lines.append(f"    Process  : {proc}")
        lines.append(f"    Send via : {s['handoff_method']}")
        lines.append(f"    Confirm  : {'required' if s['confirmation_required'] else 'not required'}")
        if s.get("launch_url"):
            lines.append(f"    Launch   : {s['launch_url']}")
        lines.append("")

    # Show any staged prompt
    sp = load_staged()
    if sp and not sp.sent:
        lines += [
            f"  [STAGED PROMPT]",
            f"  Target  : {sp.target}",
            f"  Preview : {sp.prompt[:100]}{'...' if len(sp.prompt) > 100 else ''}",
            f"  Created : {sp.created_at[:19].replace('T',' ')} UTC",
            f"  Status  : awaiting Noah confirmation (/send-staged)",
            "",
        ]
    return "\n".join(lines)


# ── Desktop doctor ────────────────────────────────────────────────────────────

def desktop_doctor() -> str:
    """
    Run live probes of all desktop actuation capabilities.
    Returns a human-readable report. Read-only — never changes state.
    """
    lines = ["", "  [ORACLE /desktop-doctor — LIVE DESKTOP PROBE]", ""]

    pyautogui_ok, pyautogui_msg = _probe_pyautogui()
    clip_ok, clip_msg = _probe_clipboard()
    screen_ok, screen_msg = _probe_screenshot()
    win_ok, win_titles = _probe_window_list()

    lines += [
        f"  pyautogui      : {'OK' if pyautogui_ok else 'MISSING'} — {pyautogui_msg}",
        f"  clipboard      : {'OK' if clip_ok else 'FAIL'} — {clip_msg}",
        f"  screenshot     : {'OK' if screen_ok else 'UNAVAILABLE'} — {screen_msg}",
        f"  window list    : {'OK' if win_ok else 'FAIL'} — {len(win_titles)} windows found",
        "",
    ]

    # Per-target window check
    lines.append("  [TARGET WINDOW DETECTION]")
    for key, target in TARGETS.items():
        if not target.window_title_keywords:
            lines.append(f"  {target.name:<30} no window keywords defined")
            continue
        status, found_title = _find_target_window(target)
        mark = {"found": "OPEN", "not_found": "NOT OPEN", "unknown": "?"}[status]
        detail = f"  (title: {found_title[:50]!r})" if found_title else ""
        lines.append(f"  {target.name:<30} {mark}{detail}")
    lines.append("")

    # Clipboard paste path
    lines.append("  [PASTE PATH]")
    if clip_ok and pyautogui_ok:
        lines.append("  FULL — clipboard write + pyautogui Ctrl+V available")
    elif clip_ok:
        lines.append("  PARTIAL — clipboard write OK, but pyautogui missing (can't auto-paste Ctrl+V)")
        lines.append("  Noah can paste manually with Ctrl+V after /send-staged")
    else:
        lines.append("  UNAVAILABLE — clipboard not writable; manual paste required")
    lines.append("")

    # Codex file channel
    ch_ok = (ROOT / "core" / "oracle_codex_channel.py").exists()
    lines.append(f"  Codex file channel : {'OK' if ch_ok else 'MISSING'}")

    # Staged prompt
    sp = load_staged()
    if sp and not sp.sent:
        lines += [
            "",
            f"  [STAGED PROMPT PENDING]",
            f"  Target  : {sp.target}",
            f"  Preview : {sp.prompt[:100]}{'...' if len(sp.prompt) > 100 else ''}",
            f"  Use /send-staged (then type 'yes') to send with Noah confirmation.",
        ]

    lines.append("")
    return "\n".join(lines)


# ── Audit helper ──────────────────────────────────────────────────────────────

def _audit(action: str, detail: str = "") -> None:
    try:
        from audit_log import log
        log("DESKTOP_BRIDGE", f"{action} {detail}".strip())
    except Exception:
        pass


# ── Smoke tests ───────────────────────────────────────────────────────────────

def run_smoke_tests() -> int:
    import tempfile, shutil as _sh

    checks = 0
    passed = 0

    def check(name: str, cond: bool, detail: str = "") -> None:
        nonlocal checks, passed
        checks += 1
        if cond:
            passed += 1
            print(f"  [PASS] {name}")
        else:
            print(f"  [FAIL] {name}" + (f" — {detail}" if detail else ""))

    # Use temp file so smoke tests don't pollute real staged prompt
    import os
    original_staged = STAGED_PROMPT_FILE
    tmp_dir = Path(tempfile.mkdtemp())
    tmp_staged = tmp_dir / "test_staged.json"

    # Patch the module's own globals dict so save_staged / load_staged / clear_staged
    # all use the temp path.  Re-importing via `import desktop_ai_bridge` would create
    # a second module object (separate __dict__), so the patch wouldn't reach the
    # functions already bound to __main__.__dict__.
    _mod_globals = globals()
    _mod_globals["STAGED_PROMPT_FILE"] = tmp_staged

    try:
        # 1. Target listing
        targets = list(TARGETS.keys())
        check("targets list is non-empty", len(targets) >= 5)
        check("chatgpt in targets", "chatgpt" in targets)
        check("claude in targets", "claude" in targets)
        check("codex in targets", "codex" in targets)
        check("sov1 in targets", "sov1" in targets)
        check("browser in targets", "browser" in targets)

        # 2. format_target_list returns string
        listing = format_target_list()
        check("format_target_list returns string", isinstance(listing, str))
        check("listing contains DESKTOP AI TARGETS header", "DESKTOP AI TARGETS" in listing)
        check("listing contains chatgpt", "chatgpt" in listing.lower())

        # 3. desktop_doctor returns string
        doc = desktop_doctor()
        check("desktop_doctor returns string", isinstance(doc, str))
        check("desktop_doctor contains probe header", "DESKTOP PROBE" in doc)
        check("desktop_doctor contains clipboard row", "clipboard" in doc.lower())
        check("desktop_doctor contains window list row", "window list" in doc.lower())

        # 4. stage_prompt — happy path
        sp = stage_prompt("chatgpt", "How should ORACLE improve her local actuation layer?", "test")
        check("stage_prompt returns StagedPrompt", isinstance(sp, StagedPrompt))
        check("staged prompt has correct target", sp.target == "chatgpt")
        check("staged prompt stored to disk", tmp_staged.exists())
        check("staged prompt not yet sent", not sp.sent)
        check("staged prompt requires confirmation", sp.requires_confirmation)

        # 5. Load and verify staged prompt
        loaded = load_staged()
        check("load_staged recovers staged prompt", loaded is not None)
        check("loaded prompt matches original", loaded.prompt == sp.prompt)
        check("loaded target matches original", loaded.target == "chatgpt")

        # 6. Confirmation gate — send without confirmed must raise
        raised = False
        try:
            send_staged(confirmed=False)
        except SendError:
            raised = True
        check("send_staged without confirmed raises SendError", raised)

        # 7. No credential staging
        cred_blocked = False
        try:
            stage_prompt("chatgpt", "my api key is sk-abcdefghijklmnopqrstu123456", "test")
        except StagingError as e:
            cred_blocked = "credential" in str(e).lower() or "secret" in str(e).lower()
        check("credential prompt staging is blocked", cred_blocked)

        # 8. No empty prompt
        empty_blocked = False
        try:
            stage_prompt("chatgpt", "   ", "test")
        except StagingError as e:
            empty_blocked = "empty" in str(e).lower()
        check("empty prompt staging is blocked", empty_blocked)

        # 9. Unknown target
        bad_target = False
        try:
            stage_prompt("unknown_ai_tool", "hello", "test")
        except StagingError as e:
            bad_target = "unknown target" in str(e).lower()
        check("unknown target is rejected", bad_target)

        # 10. Red verb blocked
        red_blocked = False
        try:
            stage_prompt("chatgpt", "commit all my changes and push to main", "test")
        except StagingError as e:
            red_blocked = "red" in str(e).lower() or "verb" in str(e).lower() or "commit" in str(e).lower()
        check("red verb in prompt is blocked", red_blocked)

        # 11. Prompt too long
        long_blocked = False
        try:
            stage_prompt("chatgpt", "x" * 9000, "test")
        except StagingError as e:
            long_blocked = "8000" in str(e) or "limit" in str(e).lower()
        check("prompt >8000 chars is blocked", long_blocked)

        # 12. pyautogui missing handled cleanly
        pyauto_ok, pyauto_msg = _probe_pyautogui()
        check(
            "pyautogui probe returns (bool, str)",
            isinstance(pyauto_ok, bool) and isinstance(pyauto_msg, str),
        )
        check("pyautogui probe message is non-empty", len(pyauto_msg) > 0)

        # 13. Clipboard probe runs without crash
        cb_ok, cb_msg = _probe_clipboard()
        check("clipboard probe returns (bool, str)", isinstance(cb_ok, bool) and isinstance(cb_msg, str))

        # 14. Window probe runs without crash
        win_ok, win_list = _probe_window_list()
        check("window probe returns (bool, list)", isinstance(win_ok, bool) and isinstance(win_list, list))

        # 15. Contains_credential detects secrets
        check("contains_credential detects sk- key", contains_credential("sk-abcdefghijklmnopqrstu123456")[0])
        check("contains_credential clean prompt", not contains_credential("How does ORACLE improve actuation?")[0])

        # 16. Contains_red_verb
        check("contains_red_verb detects commit", contains_red_verb("commit this change")[1] == "commit")
        check("contains_red_verb clean prompt", not contains_red_verb("analyze the architecture")[0])

        # 17. Clear staged
        clear_staged()
        check("clear_staged removes file", not tmp_staged.exists())

        # 18. load_staged returns None when no file
        check("load_staged returns None when no staged prompt", load_staged() is None)

        # 19. send_staged with no staged prompt raises
        no_staged = False
        try:
            send_staged(confirmed=True)
        except SendError as e:
            no_staged = "no staged" in str(e).lower() or "found" in str(e).lower()
        check("send_staged with no staged prompt raises SendError", no_staged)

        # 20. Codex target uses file channel
        codex_target = TARGETS["codex"]
        check("codex target uses file channel", codex_target.handoff_method == HANDOFF_FILE)

        # 21. All targets have confirmation_required=True
        all_confirmed = all(t.confirmation_required for t in TARGETS.values())
        check("all targets require confirmation", all_confirmed)

        # 22. list_targets_with_status runs without crash
        statuses = list_targets_with_status()
        check("list_targets_with_status returns list", isinstance(statuses, list))
        check("list contains entry per target", len(statuses) == len(TARGETS))

        # 23. capture_response returns dict
        cr = capture_response("chatgpt")
        check("capture_response returns dict", isinstance(cr, dict))
        check("capture_response has success key", "success" in cr)
        check("capture_response has detail key", "detail" in cr)

    finally:
        _mod_globals["STAGED_PROMPT_FILE"] = original_staged
        try:
            _sh.rmtree(tmp_dir)
        except Exception:
            pass

    print(f"\n{passed}/{checks} desktop_ai_bridge smoke tests passed.")
    return 0 if passed == checks else 1


# ── CLI ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse

    ap = argparse.ArgumentParser()
    ap.add_argument("--smoke-test", action="store_true")
    ap.add_argument("--doctor", action="store_true")
    ap.add_argument("--list", action="store_true")
    args = ap.parse_args()

    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

    if args.smoke_test:
        raise SystemExit(run_smoke_tests())
    if args.doctor:
        print(desktop_doctor())
    elif args.list:
        print(format_target_list())
    else:
        print(format_target_list())
        print(desktop_doctor())
