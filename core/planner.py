"""
ORACLE.AI — Daily Planning Loop
The "employee shows up at 8 AM" module.

Reads Noah's standing objectives, scans the Projects/ folders, pulls ORACLE's
memory, and produces a prioritized morning brief: open actions, the order to do
them in, a time estimate, and ONE revenue activity for Noah AI Technologies.

Writes the brief to a file and opens it so Noah can actually read it.

Run: python core/planner.py   (or double-click DAILY.bat)
"""

import os
import sys
import subprocess
from pathlib import Path
from datetime import datetime

if getattr(sys, "frozen", False):
    ROOT = Path(sys.executable).parent
else:
    ROOT = Path(__file__).parent.parent

sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "core"))

from dotenv import load_dotenv
load_dotenv(ROOT / ".env")

import anthropic
import yaml
from memory import init_db, get_facts
from audit_log import log

MODEL = "claude-sonnet-4-6"
PROJECTS_DIR = ROOT / "Projects"
OBJECTIVES_FILE = ROOT / "objectives.yaml"
BRIEF_DIR = ROOT / "Projects"


def load_objectives():
    if not OBJECTIVES_FILE.exists():
        return {}
    with open(OBJECTIVES_FILE, encoding="utf-8") as f:
        return yaml.safe_load(f)


def scan_projects():
    """List each project folder and the files in it, so ORACLE sees current work."""
    if not PROJECTS_DIR.exists():
        return "No Projects/ folder yet."
    lines = []
    for proj in sorted(PROJECTS_DIR.iterdir()):
        if not proj.is_dir():
            continue
        lines.append(f"\n[{proj.name}]")
        files = [p for p in proj.rglob("*") if p.is_file()]
        if not files:
            lines.append("  (empty — no work tracked here yet)")
            continue
        for f in sorted(files, key=lambda p: p.stat().st_mtime, reverse=True)[:15]:
            age_days = (datetime.now().timestamp() - f.stat().st_mtime) / 86400
            tag = "Active" if age_days < 7 else "Waiting" if age_days < 30 else "Archive?"
            rel = f.relative_to(proj)
            lines.append(f"  [{tag}] {rel}")
    return "\n".join(lines)


def memory_summary():
    facts = get_facts()
    if not facts:
        return "No memory facts yet."
    return "\n".join(f"[{f['category']}] {f['key']}: {f['value']}" for f in facts[:25])


def build_brief(client):
    objectives = load_objectives()
    obj_text = yaml.safe_dump(objectives, sort_keys=False) if objectives else "None set."
    projects = scan_projects()
    memory = memory_summary()

    today = datetime.now().strftime("%A, %B %d, %Y")
    prompt = f"""You are ORACLE, Noah Hawkes' executive operator. Produce his morning brief.

TODAY: {today}

NOAH'S STANDING OBJECTIVES (revenue first):
{obj_text}

CURRENT PROJECTS & WORK ON DISK:
{projects}

WHAT YOU REMEMBER ABOUT NOAH:
{memory}

Write a SHORT, punchy morning brief in plain language, formatted like this:

GOOD MORNING, NOAH.

OPEN ACTIONS:
 - (list the concrete things that need doing, inferred from objectives + projects)

RECOMMENDED ORDER:
 1. (most important first — revenue and time-sensitive items lead)
 2. ...

TODAY'S ONE REVENUE MOVE (Noah AI Technologies / SOV1.AI):
 - (ONE specific, doable-today action to move toward the first dollar:
    e.g. draft an outreach message, research 5 prospects, build a demo page)

ESTIMATED FOCUSED TIME: (a realistic number of hours)

Be concrete and decisive. No fluff, no disclaimers. If a project folder is empty,
suggest the first thing to put in it. Map everything back to an objective."""

    resp = client.messages.create(
        model=MODEL, max_tokens=1500,
        messages=[{"role": "user", "content": prompt}],
    )
    return "".join(b.text for b in resp.content if hasattr(b, "text"))


def main():
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        print("ERROR: ANTHROPIC_API_KEY not found in .env")
        sys.exit(1)

    init_db()
    client = anthropic.Anthropic(api_key=api_key)
    log("PLANNER", "Generating daily brief")

    print("Generating your morning brief...\n")
    brief = build_brief(client)

    # Save and open it so Noah can read it
    stamp = datetime.now().strftime("%Y%m%d")
    out = BRIEF_DIR / f"Daily_Brief_{stamp}.txt"
    header = f"ORACLE.AI DAILY BRIEF — {datetime.now().strftime('%A, %B %d, %Y  %I:%M %p')}\n"
    out.write_text(header + "=" * 60 + "\n\n" + brief + "\n", encoding="utf-8")

    print(header)
    print("=" * 60)
    print(brief)
    print("\n" + "=" * 60)
    print(f"\nSaved to: {out}")
    log("PLANNER", f"Brief saved: {out}")

    # Pop it open in Notepad
    try:
        subprocess.Popen(["notepad.exe", str(out)])
    except Exception:
        pass


if __name__ == "__main__":
    main()
