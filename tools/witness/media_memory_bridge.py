r"""Continuously index the canonical OBS/media thread into ORACLE memory.

Stop: create C:\Oracle\state\media_memory_bridge\stop.flag
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

REPO = Path(r"C:\Oracle\ORACLE.AI-runtime")
CORE = REPO / "core"
if str(CORE) not in sys.path:
    sys.path.insert(0, str(CORE))

from media_thread_memory import bridge_status, sync_thread

STATE_DIR = Path(r"C:\Oracle\state\media_memory_bridge")
STOP_FLAG = STATE_DIR / "stop.flag"
INTERVAL = 30


def main() -> None:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    print("media-memory bridge up", flush=True)
    while not STOP_FLAG.exists():
        result = sync_thread()
        status = bridge_status()
        print(
            f"sync indexed={result['indexed']} existing={result['already_indexed']} "
            f"errors={len(result['errors'])} remaining={status['remaining']}",
            flush=True,
        )
        time.sleep(INTERVAL)
    print("stop.flag found - media-memory bridge down", flush=True)


if __name__ == "__main__":
    main()

