"""Track terminal-like processes without assuming ownership.

ORACLE is allowed to use the machine, but visible shells need receipts.  This
module gives the runtime a small terminal census that can distinguish likely
ORACLE-owned helpers from Codex, browser extension helpers, and unknown shells.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping

if getattr(sys, "frozen", False):
    ROOT = Path(sys.executable).parent
else:
    ROOT = Path(__file__).parent.parent

MEMORY = ROOT / "Memory"
STATE = Path(r"C:\Oracle\state") if os.name == "nt" else MEMORY

LATEST_JSON = MEMORY / "terminal_census_latest.json"
LATEST_MD = MEMORY / "terminal_census_latest.md"
HISTORY_JSONL = MEMORY / "terminal_census_history.jsonl"
SPAWN_RECEIPTS = MEMORY / "terminal_spawn_receipts.jsonl"

STATE_LATEST_JSON = STATE / "terminal_census_latest.json"
STATE_HISTORY_JSONL = STATE / "terminal_census_history.jsonl"

TERMINAL_PROCESS_NAMES = {
    "windowsterminal.exe",
    "wt.exe",
    "openconsole.exe",
    "powershell.exe",
    "pwsh.exe",
    "cmd.exe",
    "conhost.exe",
}
SHELL_PROCESS_NAMES = TERMINAL_PROCESS_NAMES - {"conhost.exe"}

ORACLE_HINTS = (
    str(ROOT).lower(),
    "oracle.ai-runtime",
    "oracle_server.py",
    "core\\oracle.py",
    "core/oracle.py",
    "oracle.bat",
    "oracle_local.bat",
    "oracle_home.bat",
    "oracledesk",
    "oracle.ai",
)

CODEX_HINTS = (
    "\\.codex\\",
    "/.codex/",
    "openai codex",
    "codex",
)

EXTERNAL_HELPER_HINTS = (
    "icloudpasswordsextensionhelper.exe",
    "icloudchrome.exe",
    "extension-host.exe",
    "chrome.native",
)

OBSERVER_HINTS = (
    "terminal_census",
    "get-ciminstance win32_process",
)

VISIBLE_TERMINAL_TITLE_HINTS = (
    "terminal",
    "windows powershell",
    "powershell",
    "command prompt",
    "cmd.exe",
)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _creationflags() -> int:
    if os.name != "nt":
        return 0
    return getattr(subprocess, "CREATE_NO_WINDOW", 0)


def _append_jsonl(path: Path, row: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(dict(row), ensure_ascii=False, sort_keys=True) + "\n")


def record_spawn(
    *,
    kind: str,
    pid: int,
    command: str,
    cwd: str,
    visible_window: bool,
    cleanup_policy: str,
) -> None:
    """Record an ORACLE-owned terminal-like helper process."""
    _append_jsonl(
        SPAWN_RECEIPTS,
        {
            "event": "spawn",
            "ts_utc": _now(),
            "kind": kind,
            "pid": int(pid),
            "command": command,
            "cwd": cwd,
            "visible_window": bool(visible_window),
            "cleanup_policy": cleanup_policy,
        },
    )


def record_exit(*, kind: str, pid: int, reason: str) -> None:
    _append_jsonl(
        SPAWN_RECEIPTS,
        {
            "event": "exit",
            "ts_utc": _now(),
            "kind": kind,
            "pid": int(pid),
            "reason": reason,
        },
    )


def load_owned_terminal_pids(receipt_path: Path = SPAWN_RECEIPTS) -> set[int]:
    """Return PIDs from ORACLE spawn receipts that have not been closed."""
    active: set[int] = set()
    if not receipt_path.exists():
        return active
    try:
        for line in receipt_path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            row = json.loads(line)
            pid = int(row.get("pid", 0) or 0)
            if not pid:
                continue
            if row.get("event") == "spawn":
                active.add(pid)
            elif row.get("event") == "exit":
                active.discard(pid)
    except Exception:
        return set()
    return active


def _query_windows_processes() -> list[dict[str, Any]]:
    if os.name != "nt":
        return []
    script = r"""
$ErrorActionPreference = 'SilentlyContinue'
$selfPid = $PID
Get-CimInstance Win32_Process |
  Where-Object {
    $_.Name -match '^(WindowsTerminal|wt|OpenConsole|powershell|pwsh|cmd|conhost)\.exe$' -and
    $_.ProcessId -ne $selfPid -and
    $_.ParentProcessId -ne $selfPid
  } |
  Select-Object Name,ProcessId,ParentProcessId,CreationDate,CommandLine |
  ConvertTo-Json -Depth 3
"""
    result = subprocess.run(
        ["powershell", "-NoProfile", "-NonInteractive", "-Command", script],
        capture_output=True,
        text=True,
        timeout=12,
        creationflags=_creationflags(),
    )
    raw = result.stdout.strip()
    if not raw:
        return []
    data = json.loads(raw)
    if isinstance(data, dict):
        return [data]
    if isinstance(data, list):
        return [d for d in data if isinstance(d, dict)]
    return []


def _as_int(value: Any) -> int:
    try:
        return int(value)
    except Exception:
        return 0


def _classify(name: str, command_line: str, pid: int, parent_pid: int, owned_pids: set[int]) -> tuple[str, str]:
    text = f"{name} {command_line}".lower()
    if any(hint in text for hint in OBSERVER_HINTS):
        return "observer", "terminal census observer"
    if pid in owned_pids:
        return "oracle_owned", "pid has ORACLE spawn receipt"
    if parent_pid in owned_pids:
        return "oracle_child", "parent pid has ORACLE spawn receipt"
    if name in {"windowsterminal.exe", "openconsole.exe"} and "-embedding" in text:
        return "windows_terminal_host", "Windows Terminal host/session"
    if any(hint in text for hint in ORACLE_HINTS):
        return "oracle_related", "command line contains ORACLE runtime hint"
    if any(hint in text for hint in CODEX_HINTS):
        return "codex_related", "command line contains Codex hint"
    if any(hint in text for hint in EXTERNAL_HELPER_HINTS):
        return "external_helper", "browser/cloud helper shell"
    return "unclassified", "no ownership signal"


def normalize_processes(
    rows: Iterable[Mapping[str, Any]],
    owned_pids: set[int] | None = None,
) -> list[dict[str, Any]]:
    owned = owned_pids if owned_pids is not None else load_owned_terminal_pids()
    records: list[dict[str, Any]] = []
    for row in rows:
        name = str(row.get("Name") or row.get("name") or "").lower()
        if name and name not in TERMINAL_PROCESS_NAMES:
            continue
        pid = _as_int(row.get("ProcessId") or row.get("pid"))
        parent_pid = _as_int(row.get("ParentProcessId") or row.get("parent_pid"))
        command_line = str(row.get("CommandLine") or row.get("command_line") or "")
        owner, reason = _classify(name, command_line, pid, parent_pid, owned)
        records.append(
            {
                "name": name,
                "pid": pid,
                "parent_pid": parent_pid,
                "created": str(row.get("CreationDate") or row.get("created") or ""),
                "command_line": command_line,
                "owner": owner,
                "reason": reason,
                "is_shell": name in SHELL_PROCESS_NAMES,
            }
        )
    owner_by_pid = {r["pid"]: r["owner"] for r in records if r["pid"]}
    reason_by_pid = {r["pid"]: r["reason"] for r in records if r["pid"]}
    for rec in records:
        if rec["owner"] != "unclassified":
            continue
        parent_owner = owner_by_pid.get(rec["parent_pid"])
        if parent_owner and parent_owner not in {"unclassified", "observer"}:
            rec["owner"] = parent_owner
            rec["reason"] = f"child of {parent_owner}: {reason_by_pid.get(rec['parent_pid'], '')}"
    return records


def visible_terminal_windows() -> list[dict[str, Any]]:
    """Return visible terminal-ish window titles, if pygetwindow is available."""
    try:
        import pygetwindow as gw
    except Exception:
        return []
    windows = []
    try:
        for win in gw.getAllWindows():
            title = (win.title or "").strip()
            if not title:
                continue
            lower = title.lower()
            if any(hint in lower for hint in VISIBLE_TERMINAL_TITLE_HINTS):
                windows.append(
                    {
                        "title": title,
                        "handle": int(getattr(win, "_hWnd", 0) or 0),
                    }
                )
    except Exception:
        return []
    return windows


def build_snapshot(
    rows: Iterable[Mapping[str, Any]] | None = None,
    *,
    owned_pids: set[int] | None = None,
    max_shells: int = 4,
) -> dict[str, Any]:
    queried_live = rows is None
    if rows is None:
        rows = _query_windows_processes()
    records = normalize_processes(rows, owned_pids=owned_pids)
    counted = [r for r in records if r["owner"] != "observer"]
    shell_count = sum(1 for r in counted if r["is_shell"])
    visible_windows = visible_terminal_windows() if queried_live else []
    counts = {
        "terminal_processes": len(counted),
        "shell_processes": shell_count,
        "conhost_processes": sum(1 for r in counted if r["name"] == "conhost.exe"),
        "visible_terminal_windows": len(visible_windows),
        "windows_terminal_hosts": sum(1 for r in counted if r["owner"] == "windows_terminal_host"),
        "oracle_related": sum(1 for r in counted if r["owner"] in {"oracle_owned", "oracle_child", "oracle_related"}),
        "codex_related": sum(1 for r in counted if r["owner"] == "codex_related"),
        "external_helpers": sum(1 for r in counted if r["owner"] == "external_helper"),
        "unclassified": sum(1 for r in counted if r["owner"] == "unclassified"),
        "excess_shells_over_limit": max(0, shell_count - max_shells),
        "excess_visible_windows_over_limit": max(0, len(visible_windows) - max_shells),
    }
    return {
        "generated_at": _now(),
        "root": str(ROOT),
        "max_shells": max_shells,
        "counts": counts,
        "visible_windows": visible_windows,
        "records": counted,
        "safety": {
            "read_only": True,
            "no_windows_closed": True,
            "no_processes_killed": True,
            "ownership_is_inferred_unless_receipted": True,
        },
    }


def _short_command(command_line: str, limit: int = 120) -> str:
    one_line = " ".join(command_line.split())
    if len(one_line) <= limit:
        return one_line
    return one_line[: limit - 3] + "..."


def format_markdown(snapshot: Mapping[str, Any]) -> str:
    counts = snapshot.get("counts", {})
    lines = [
        "# ORACLE Terminal Census",
        f"Generated: {snapshot.get('generated_at', '')}",
        "",
        "## Counts",
        f"- Terminal-like processes: {counts.get('terminal_processes', 0)}",
        f"- Shell processes: {counts.get('shell_processes', 0)}",
        f"- Visible terminal windows: {counts.get('visible_terminal_windows', 0)}",
        f"- Windows Terminal hosts/sessions: {counts.get('windows_terminal_hosts', 0)}",
        f"- ORACLE-related: {counts.get('oracle_related', 0)}",
        f"- Codex-related: {counts.get('codex_related', 0)}",
        f"- External helpers: {counts.get('external_helpers', 0)}",
        f"- Unclassified: {counts.get('unclassified', 0)}",
        f"- Excess over limit: {counts.get('excess_shells_over_limit', 0)}",
        "",
        "## Processes",
        "| owner | process | pid | parent | reason | command |",
        "| --- | --- | ---: | ---: | --- | --- |",
    ]
    for rec in snapshot.get("records", [])[:60]:
        command = _short_command(str(rec.get("command_line", ""))).replace("|", "\\|")
        lines.append(
            f"| {rec.get('owner', '')} | {rec.get('name', '')} | "
            f"{rec.get('pid', 0)} | {rec.get('parent_pid', 0)} | "
            f"{rec.get('reason', '')} | `{command}` |"
        )
    lines += [
        "",
        "## Safety",
        "- Census only. No windows closed.",
        "- No processes killed.",
        "- Unknown ownership stays unclaimed.",
    ]
    return "\n".join(lines) + "\n"


def write_snapshot(snapshot: Mapping[str, Any] | None = None) -> dict[str, Any]:
    snap = dict(snapshot or build_snapshot())
    MEMORY.mkdir(parents=True, exist_ok=True)
    LATEST_JSON.write_text(json.dumps(snap, indent=2, ensure_ascii=False), encoding="utf-8")
    LATEST_MD.write_text(format_markdown(snap), encoding="utf-8")
    _append_jsonl(HISTORY_JSONL, {"ts_utc": snap["generated_at"], "counts": snap["counts"]})
    try:
        STATE.mkdir(parents=True, exist_ok=True)
        STATE_LATEST_JSON.write_text(json.dumps(snap, indent=2, ensure_ascii=False), encoding="utf-8")
        _append_jsonl(STATE_HISTORY_JSONL, {"ts_utc": snap["generated_at"], "counts": snap["counts"]})
    except Exception:
        pass
    return snap


def status_text(snapshot: Mapping[str, Any] | None = None) -> str:
    snap = snapshot or build_snapshot()
    counts = snap["counts"]
    return (
        "Terminal census: "
        f"{counts['visible_terminal_windows']} visible terminal window(s), "
        f"{counts['shell_processes']} shell process(es), "
        f"{counts['terminal_processes']} terminal-like process(es), "
        f"{counts['windows_terminal_hosts']} Windows Terminal host/session process(es), "
        f"{counts['oracle_related']} ORACLE-related, "
        f"{counts['codex_related']} Codex-related, "
        f"{counts['external_helpers']} external helper(s), "
        f"{counts['unclassified']} unclassified."
    )


def watch(interval: int = 30) -> None:
    stop = STATE / "terminal_census.stop"
    while not stop.exists():
        try:
            write_snapshot()
        except Exception:
            pass
        time.sleep(max(5, interval))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="ORACLE terminal process census")
    parser.add_argument("--status", action="store_true", help="Write and print one census")
    parser.add_argument("--json", action="store_true", help="Print JSON for the current census")
    parser.add_argument("--watch", action="store_true", help="Continuously update terminal census receipts")
    parser.add_argument("--interval", type=int, default=30, help="Watch interval in seconds")
    args = parser.parse_args(argv)

    if args.watch:
        watch(args.interval)
        return 0
    snap = write_snapshot()
    if args.json:
        print(json.dumps(snap, indent=2, ensure_ascii=False))
    else:
        print(status_text(snap))
        print(f"Latest: {LATEST_JSON}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
