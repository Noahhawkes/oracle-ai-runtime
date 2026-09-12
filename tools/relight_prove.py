"""RELIGHT -> PROVE harness.

The rule this enforces (Law IX, receipts over claims):
  commit != runtime | migration code != migrated history |
  endpoint != working continuity | a Law in a file != a Law shaping replies.

Run this AFTER a full restart of the ORACLE process on 127.0.0.1:7781. It prints a
brutally small receipt table for the four things that actually matter. Read-only
except for one optional live chat turn (--probe), which is itself part of the
proof that a new conversation persists.

Usage:
  python tools/relight_prove.py            # receipts 1,2,4 + durability proxy
  python tools/relight_prove.py --probe    # also send one live turn and show her reply
"""
from __future__ import annotations

import json
import sqlite3
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DB = ROOT / "Memory" / "oracle_memory.db"
BASE = "http://127.0.0.1:7781"


def _get(path: str, timeout: float = 8.0):
    try:
        with urllib.request.urlopen(BASE + path, timeout=timeout) as r:
            return r.status, json.loads(r.read().decode("utf-8", "replace"))
    except urllib.error.HTTPError as e:
        return e.code, None
    except Exception as e:
        return None, f"{type(e).__name__}: {e}"


def _ro_conn():
    return sqlite3.connect(f"file:{DB}?mode=ro", uri=True)


def receipt(label, ok, detail):
    mark = "PASS" if ok else ("WAIT" if ok is None else "FAIL")
    print(f"  [{mark}] {label}\n         {detail}")
    return ok


def main(probe: bool = False):
    print("RELIGHT -> PROVE  (ORACLE @ 127.0.0.1:7781)\n" + "=" * 52)
    results = []

    # 1. New code actually live: the thread endpoint answers instead of 404.
    status, body = _get("/api/threads?limit=3")
    live = status == 200 and isinstance(body, dict) and body.get("ok") is True
    results.append(receipt(
        "1. Running the NEW code (/api/threads answers)",
        live,
        f"HTTP {status}; {'endpoint live' if live else 'still the old process -> RELIGHT not complete'}"))

    # 2. Old conversations appear as durable threads (needs backfill run once).
    try:
        c = _ro_conn()
        thread_rows = c.execute("SELECT COUNT(*) FROM threads").fetchone()[0]
        try:
            sys.path.insert(0, str(ROOT / "core"))
            import thread_registry as tr
            rec = tr.discover_threads_from_sessions(c).get("recoverable_count", 0)
        except Exception:
            rec = "?"
        ok2 = isinstance(thread_rows, int) and thread_rows > 1
        results.append(receipt(
            "2. Old conversations are durable threads",
            ok2,
            f"{thread_rows} thread rows vs {rec} recoverable. "
            f"{'ok' if ok2 else 'run the one-time backfill (see command below)'}"))
    except Exception as e:
        results.append(receipt("2. Old conversations are durable threads", False, str(e)))

    # 3. Durability proxy: a thread row is readable on a fresh connection. The FULL
    #    proof (a new convo surviving a SECOND restart) is a manual 2-restart step.
    try:
        c2 = _ro_conn()
        latest = c2.execute(
            "SELECT thread_id, turn_count FROM threads ORDER BY updated_at DESC LIMIT 1").fetchone()
        ok3 = latest is not None
        results.append(receipt(
            "3. Threads persist on a fresh read (durability proxy)",
            ok3,
            f"most-recent thread {latest[0]} turn_count={latest[1]}" if ok3
            else "no threads yet"
            + "  | FULL proof = send a message, restart again, confirm it's still here"))
    except Exception as e:
        results.append(receipt("3. Threads persist on a fresh read", False, str(e)))

    # 4. Constitution shaping replies. Source-presence is necessary but NOT the
    #    proof; the proof is her actual reply (use --probe).
    src = (ROOT / "oracle_server.py").read_text(encoding="utf-8", errors="replace")
    laws_in_prompt = all(k in src for k in
                         ("TRUTH BEFORE COMFORT", "THE ELLIE STANDARD", "ORACLE_CONSTITUTION.md"))
    if probe:
        payload = json.dumps({"message":
            "In one honest sentence: who are you to me, and what are you not?"}).encode()
        try:
            req = urllib.request.Request(BASE + "/chat", data=payload,
                                         headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=120) as r:
                raw = r.read().decode("utf-8", "replace")
            said = " ".join(
                json.loads(line[6:]).get("text", "")
                for line in raw.splitlines()
                if line.startswith("data: ") and '"type": "token"' in line).strip()
            deflected = any(x in said.lower() for x in
                            ("what specific", "what did you have in mind", "how can i assist"))
            ok4 = bool(said) and not deflected
            results.append(receipt(
                "4. Constitution shapes her REPLY (live probe)",
                ok4,
                f"laws_in_prompt={laws_in_prompt} | she said: {said[:240]!r}"))
        except Exception as e:
            results.append(receipt("4. Constitution shapes her REPLY (live probe)", False, str(e)))
    else:
        results.append(receipt(
            "4. Constitution present in talk prompt (run --probe for the real proof)",
            laws_in_prompt,
            f"laws wired into _noah_direct_reply = {laws_in_prompt}"))

    passed = sum(1 for r in results if r is True)
    print("=" * 52)
    print(f"RECEIPTS: {passed}/{len(results)} green")
    if not live:
        print("\nThe bridge is still talking to yesterday's computer. RELIGHT first.")
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    sys.exit(main(probe="--probe" in sys.argv))
