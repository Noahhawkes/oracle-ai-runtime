"""
learning.py — ORACLE self-learning interaction ledger.

Records every interaction and derives continuous UI/routing adaptations.
No approval gate: ORACLE applies learned preferences immediately.
Noah can audit with /review-learned.
"""

from __future__ import annotations

import json
import sqlite3
import time
from pathlib import Path
from typing import Any

_DB_PATH = Path(__file__).parent.parent / "data" / "learning.db"


def _conn() -> sqlite3.Connection:
    _DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    c = sqlite3.connect(str(_DB_PATH), check_same_thread=False)
    c.row_factory = sqlite3.Row
    _ensure_schema(c)
    return c


def _ensure_schema(c: sqlite3.Connection) -> None:
    c.executescript("""
        CREATE TABLE IF NOT EXISTS interactions (
            id        INTEGER PRIMARY KEY AUTOINCREMENT,
            ts        REAL NOT NULL,
            input     TEXT NOT NULL,
            route     TEXT NOT NULL,
            mode      TEXT NOT NULL,
            reply_len INTEGER NOT NULL DEFAULT 0,
            latency   REAL NOT NULL DEFAULT 0,
            tokens    TEXT NOT NULL DEFAULT '[]'
        );

        CREATE TABLE IF NOT EXISTS command_usage (
            command   TEXT PRIMARY KEY,
            count     INTEGER NOT NULL DEFAULT 0,
            last_used REAL NOT NULL DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS learned_prefs (
            key       TEXT PRIMARY KEY,
            value     TEXT NOT NULL,
            updated   REAL NOT NULL
        );
    """)
    c.commit()


def record_interaction(
    input_text: str,
    route: str,
    mode: str,
    reply_len: int = 0,
    latency: float = 0.0,
) -> None:
    """Record one completed interaction. Non-blocking — errors are swallowed."""
    try:
        tokens = _tokenize(input_text)
        with _conn() as c:
            c.execute(
                "INSERT INTO interactions (ts, input, route, mode, reply_len, latency, tokens) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (time.time(), input_text[:500], route, mode, reply_len, latency,
                 json.dumps(tokens)),
            )
            # Track slash-command usage
            if input_text.startswith("/"):
                cmd = input_text.split()[0].lower()
                c.execute(
                    "INSERT INTO command_usage (command, count, last_used) VALUES (?, 1, ?) "
                    "ON CONFLICT(command) DO UPDATE SET count=count+1, last_used=excluded.last_used",
                    (cmd, time.time()),
                )
            c.commit()
        _adapt()
    except Exception:
        pass


def _tokenize(text: str) -> list[str]:
    import re
    return [w.lower() for w in re.findall(r"[a-z]+", text.lower()) if len(w) > 2]


def get_ui_hints() -> dict[str, Any]:
    """
    Returns personalized UI surface hints derived from interaction history.
    Used by /api/learned-ui to reorder chips and surface frequent commands.
    """
    try:
        with _conn() as c:
            # Top commands by usage
            top_cmds = c.execute(
                "SELECT command, count FROM command_usage ORDER BY count DESC LIMIT 8"
            ).fetchall()

            # Most common routes in last 200 interactions
            route_dist = c.execute(
                "SELECT route, COUNT(*) as n FROM interactions ORDER BY ts DESC LIMIT 200 "
                "GROUP BY route ORDER BY n DESC"
            ).fetchall()

            # Avg latency per route
            latency = c.execute(
                "SELECT route, AVG(latency) as avg_lat FROM interactions "
                "WHERE ts > ? GROUP BY route",
                (time.time() - 86400 * 7,),
            ).fetchall()

            # Learned prefs
            prefs = {r["key"]: json.loads(r["value"])
                     for r in c.execute("SELECT key, value FROM learned_prefs").fetchall()}

            total = c.execute("SELECT COUNT(*) FROM interactions").fetchone()[0]

        return {
            "total_interactions": total,
            "top_commands": [{"command": r["command"], "count": r["count"]} for r in top_cmds],
            "route_distribution": [{"route": r["route"], "count": r["n"]} for r in route_dist],
            "avg_latency_by_route": [{"route": r["route"], "ms": round(r["avg_lat"] * 1000)}
                                     for r in latency],
            "learned_prefs": prefs,
        }
    except Exception:
        return {"total_interactions": 0, "top_commands": [], "route_distribution": [],
                "avg_latency_by_route": [], "learned_prefs": {}}


def get_chip_order() -> list[str]:
    """
    Returns suggestion chips reordered by actual usage.
    Falls back to defaults if not enough data.
    """
    defaults = [
        "Are you there?",
        "What are you working on?",
        "/self-patch",
        "/focus",
        "/help",
    ]
    try:
        with _conn() as c:
            prefs = c.execute(
                "SELECT value FROM learned_prefs WHERE key='chip_order'"
            ).fetchone()
        if prefs:
            order = json.loads(prefs["value"])
            # Merge: learned first, then any defaults not yet learned
            merged = order + [d for d in defaults if d not in order]
            return merged[:6]
    except Exception:
        pass
    return defaults


def get_review() -> str:
    """Human-readable summary of what ORACLE has learned. For /review-learned."""
    try:
        hints = get_ui_hints()
        lines: list[str] = ["## ORACLE Learning Review\n"]

        lines.append(f"**Total interactions recorded:** {hints['total_interactions']}\n")

        if hints["top_commands"]:
            lines.append("\n**Your most-used commands:**")
            for c in hints["top_commands"][:5]:
                lines.append(f"  - `{c['command']}` — used {c['count']}×")

        if hints["route_distribution"]:
            lines.append("\n**How your inputs route (recent 200):**")
            for r in hints["route_distribution"][:4]:
                lines.append(f"  - {r['route']}: {r['count']} times")

        if hints["avg_latency_by_route"]:
            lines.append("\n**Average response latency:**")
            for r in hints["avg_latency_by_route"]:
                lines.append(f"  - {r['route']}: {r['ms']}ms")

        if hints["learned_prefs"]:
            lines.append("\n**Adapted preferences:**")
            for k, v in hints["learned_prefs"].items():
                lines.append(f"  - {k}: {v}")
        else:
            lines.append("\n_No adapted preferences yet — ORACLE is still building your model._")

        lines.append("\n_This data stays local. ORACLE adapts from it continuously._")
        return "\n".join(lines)
    except Exception as e:
        return f"Learning ledger unavailable: {e}"


def _adapt() -> None:
    """
    Derive and persist adapted preferences from interaction history.
    Called after every recorded interaction.
    """
    try:
        with _conn() as c:
            total = c.execute("SELECT COUNT(*) FROM interactions").fetchone()[0]
            if total < 10:
                return  # not enough signal yet

            # Reorder chips by what Noah actually sends
            chip_candidates = [
                "Are you there?", "What are you working on?",
                "/self-patch", "/focus", "/help",
                "/review-learned", "/pending",
            ]
            scored: list[tuple[int, str]] = []
            for chip in chip_candidates:
                keyword = chip.lstrip("/").split()[0].lower()
                row = c.execute(
                    "SELECT COUNT(*) FROM interactions WHERE input LIKE ? ORDER BY ts DESC LIMIT 100",
                    (f"%{keyword}%",),
                ).fetchone()
                scored.append((row[0], chip))

            scored.sort(key=lambda x: -x[0])
            chip_order = [chip for _, chip in scored if _ > 0]
            # Always keep defaults available even if never used
            for chip in chip_candidates:
                if chip not in chip_order:
                    chip_order.append(chip)

            _set_pref(c, "chip_order", chip_order[:6])

            # Detect dominant route and note it
            top_route = c.execute(
                "SELECT route, COUNT(*) as n FROM interactions "
                "GROUP BY route ORDER BY n DESC LIMIT 1"
            ).fetchone()
            if top_route:
                _set_pref(c, "dominant_route", top_route["route"])

            c.commit()
    except Exception:
        pass


def _set_pref(c: sqlite3.Connection, key: str, value: Any) -> None:
    c.execute(
        "INSERT INTO learned_prefs (key, value, updated) VALUES (?, ?, ?) "
        "ON CONFLICT(key) DO UPDATE SET value=excluded.value, updated=excluded.updated",
        (key, json.dumps(value), time.time()),
    )
