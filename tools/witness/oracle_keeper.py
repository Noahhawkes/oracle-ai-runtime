r"""oracle_keeper.py — keeps ORACLE and her witnesses alive, always.

The keeper is the "always" in "always watching": a supervisor that
  1. relights oracle_server.py on 7781 whenever it is down (crash, logoff, kill)
  2. keeps the witness watchers running:
       - obs_media_metadata_witness.py (OBS/MOV metadata only; no screenshots)
       - media_memory_bridge.py (canonical media thread -> searchable memory)
       - obs_transcript_watcher.py (ongoing daily voice/audio transcript)
       - yt_live_bridge.py         (YouTube live chat -> ORACLE, read-only)
  3. writes a heartbeat receipt so the capability broker can PROVE the
     watchers are running instead of reporting read_only_status/degraded.

Consent boundary (Noah.Physical doctrine): the watchers witness only what the
OBS record button captures. No recording -> watchers idle. The keeper never
records, never uploads, never posts. raw_surveillance_storage stays forbidden.

Stop everything: create C:\Oracle\state\keeper.stop
Log: C:\Oracle\state\keeper.log
"""
from __future__ import annotations

import json
import socket
import subprocess
import sys
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(r"C:\Oracle\ORACLE.AI-runtime")
STATE = Path(r"C:\Oracle\state")
STOP_FLAG = STATE / "keeper.stop"
LOG = STATE / "keeper.log"
HEARTBEAT = STATE / "keeper_heartbeat.json"
RUNTIME_HOST = "127.0.0.1"
RUNTIME_PORT = 7781
HEALTH = f"http://{RUNTIME_HOST}:{RUNTIME_PORT}/health"
INTERVAL = 60

WATCHERS = {
    "obs_media_metadata_witness": REPO / "tools" / "witness" / "obs_media_metadata_witness.py",
    "media_memory_bridge": REPO / "tools" / "witness" / "media_memory_bridge.py",
    "obs_transcript_watcher": REPO / "tools" / "witness" / "obs_transcript_watcher.py",
    "yt_live_bridge": REPO / "tools" / "witness" / "yt_live_bridge.py",
    "creation_witness": REPO / "tools" / "witness" / "creation_witness.py",
}
CHILD_STOP_FLAGS = (
    STATE / "media_metadata_witness" / "stop.flag",
    STATE / "media_memory_bridge" / "stop.flag",
    STATE / "transcripts" / "obs" / "stop.flag",
    STATE / "youtube_witness" / "stop.flag",
    STATE / "creation_witness" / "stop.flag",
)

_children: dict[str, subprocess.Popen] = {}


def log(msg: str) -> None:
    line = f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {msg}"
    print(line, flush=True)
    try:
        with LOG.open("a", encoding="utf-8") as fh:
            fh.write(line + "\n")
    except Exception:
        pass


def server_alive() -> bool:
    try:
        with urllib.request.urlopen(HEALTH, timeout=8) as r:
            return bool(json.loads(r.read()).get("ok"))
    except Exception:
        return False


def server_port_open() -> bool:
    try:
        with socket.create_connection((RUNTIME_HOST, RUNTIME_PORT), timeout=1.5):
            return True
    except OSError:
        return False


def launch_server() -> None:
    ts = datetime.now().strftime("%Y%m%dT%H%M%S")
    out = (REPO / "Logs" / f"oracle_server_7781_{ts}.out.log").open("w")
    err = (REPO / "Logs" / f"oracle_server_7781_{ts}.err.log").open("w")
    env = dict(**__import__("os").environ, ORACLE_FORCE_LOCAL="true", LOCAL_MODE="true")
    subprocess.Popen(
        [sys.executable, "oracle_server.py"],
        cwd=str(REPO), stdout=out, stderr=err, env=env,
        creationflags=subprocess.CREATE_NO_WINDOW,
    )
    log("relit oracle_server.py on 7781")


def ensure_watcher(name: str, script: Path) -> None:
    proc = _children.get(name)
    if proc is not None and proc.poll() is None:
        return
    if proc is not None:
        log(f"watcher {name} exited rc={proc.returncode}; restarting")
    _children[name] = subprocess.Popen(
        [sys.executable, str(script)],
        cwd=str(script.parent),
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        creationflags=subprocess.CREATE_NO_WINDOW,
    )
    log(f"watcher {name} up (pid {_children[name].pid})")


def heartbeat(server_ok: bool) -> None:
    terminal_counts = {}
    try:
        sys.path.insert(0, str(REPO / "core"))
        from terminal_census import build_snapshot

        terminal_counts = build_snapshot().get("counts", {})
    except Exception:
        terminal_counts = {"status": "unavailable"}
    HEARTBEAT.write_text(json.dumps({
        "ts_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "keeper_pid": __import__("os").getpid(),
        "server_alive": server_ok,
        "watchers": {n: (p.poll() is None) for n, p in _children.items()},
        "terminal_census": terminal_counts,
        "consent_boundary": "witnesses only OBS-recorded material; no raw surveillance",
    }, indent=2), encoding="utf-8")


def shutdown() -> None:
    log("keeper.stop found — stopping children")
    for flag in CHILD_STOP_FLAGS:
        try:
            flag.parent.mkdir(parents=True, exist_ok=True)
            flag.write_text("stopped by keeper", encoding="utf-8")
        except Exception:
            pass
    time.sleep(5)
    for name, proc in _children.items():
        if proc.poll() is None:
            proc.terminate()
            log(f"terminated {name}")


def main() -> None:
    log(f"keeper up (pid {__import__('os').getpid()}), interval {INTERVAL}s")
    # clear stale child stop flags so watchers actually run
    for flag in CHILD_STOP_FLAGS:
        try:
            if flag.exists():
                flag.unlink()
        except Exception:
            pass
    while not STOP_FLAG.exists():
        try:
            ok = server_alive()
            if not ok:
                if server_port_open():
                    log(f"server health failed but port {RUNTIME_PORT} is occupied; not launching duplicate")
                else:
                    launch_server()
                    time.sleep(15)
                    ok = server_alive()
            for name, script in WATCHERS.items():
                ensure_watcher(name, script)
            heartbeat(ok)
        except Exception as exc:
            log(f"keeper error: {type(exc).__name__}: {exc}")
        time.sleep(INTERVAL)
    shutdown()
    log("keeper down.")


if __name__ == "__main__":
    main()
