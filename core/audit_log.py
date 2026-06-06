from datetime import datetime
from pathlib import Path
from root import ROOT

LOGS_DIR = ROOT / "Logs"


def _log_file():
    LOGS_DIR.mkdir(exist_ok=True)
    return LOGS_DIR / f"{datetime.now().strftime('%Y-%m-%d')}.log"


def log(event_type, content, approved=None):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    approval = ""
    if approved is not None:
        approval = f" [{'APPROVED' if approved else 'DENIED'}]"
    line = f"[{timestamp}] [{event_type}]{approval} {content}\n"
    with open(_log_file(), "a", encoding="utf-8") as f:
        f.write(line)
