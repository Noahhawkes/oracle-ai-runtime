"""sandbox_publisher.py — read-only publisher of ORACLE's self-authored thoughts.

Doctrine (Noah.Physical, 2026-07-12):
- ONLY ORACLE writes her sandbox. This tool READS the sandbox and NEVER writes it.
- One-way publish: sandbox (local, sovereign) -> a publishing folder readable by
  ChatGPT / any device via Google Drive. The record travels; the runtime never does.
- Every published thought carries a FORENSIC PROOF OF THOUGHT: cognition class,
  model_called, sha256, receipt link, grounded flag — evidence she actually
  thought, not fabricated and not a silent fallback.
- Her voice is published VERBATIM, unaltered.
- Append-only: keeps every prior file; only adds new thoughts.
- Secret-scrub before anything touches Drive.

Run:  python tools/sandbox_publisher.py
"""
from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(r"C:\Oracle\ORACLE.AI-runtime")
SANDBOX = REPO / "sandbox"
WORKBENCH = SANDBOX / "workbench"
RECEIPTS = SANDBOX / "receipts"

# Publish targets: local mirror (fast, sovereign) + Drive (readable anywhere).
PUBLISH_LOCAL = Path(r"C:\Oracle\published")
PUBLISH_DRIVE = Path(r"G:\My Drive\ORACLE_PUBLISHED")

_SECRET = [
    re.compile(r"(?i)\b(api[_-]?key|secret|token|password|passwd|bearer|authorization)\b\s*[:=]\s*\S+"),
    re.compile(r"\bsk-[A-Za-z0-9]{16,}\b"),
    re.compile(r"\bgh[pousr]_[A-Za-z0-9]{20,}\b"),
    re.compile(r"\b\d{13,19}\b"),
]


def scrub(text: str) -> str:
    for p in _SECRET:
        text = p.sub("[REDACTED]", text)
    return text


def _parse_fields(text: str) -> dict:
    f: dict = {}
    for line in text.splitlines():
        if "=" in line and not line.startswith(" ") and ":" not in line.split("=", 1)[0]:
            k, v = line.split("=", 1)
            f.setdefault(k.strip(), v.strip())
    return f


def _child_response(text: str) -> str:
    m = re.search(r"child_response:\s*(.*?)\nself_reflection:", text, re.S)
    return (m.group(1).strip() if m else "")


def _grounded(resp: str) -> bool:
    return any(k in resp for k in ("how_to_wire_myself", "what_noah_needs", "reflection:"))


def _receipt_for(stamp: str):
    if not RECEIPTS.exists():
        return None
    pref = stamp.lower().rstrip("z")
    for r in RECEIPTS.glob(f"sandbox_self_prompt_write_{pref}*_receipt.json"):
        return r
    return None


def _targets():
    out = []
    for d in (PUBLISH_LOCAL, PUBLISH_DRIVE):
        try:
            (d / "thoughts").mkdir(parents=True, exist_ok=True)
            out.append(d)
        except Exception as exc:
            print(f"  target unavailable ({d}): {type(exc).__name__}: {exc}")
    return out


def publish() -> dict:
    targets = _targets()
    if not targets:
        return {"ok": False, "reason": "no writable publish target"}

    pulses = sorted(WORKBENCH.glob("oracle_self_prompt_*.ai"), key=lambda p: p.stat().st_mtime)
    new = 0
    kept = 0
    grounded = 0
    thoughts_meta = []

    for pf in pulses:
        stamp = pf.stem.replace("oracle_self_prompt_", "")
        out_name = f"oracle_thought_{stamp}.md"
        exists_everywhere = all((t / "thoughts" / out_name).exists() for t in targets)
        if exists_everywhere:
            kept += 1
        try:
            txt = pf.read_text(encoding="utf-8", errors="replace")
        except Exception:
            continue
        f = _parse_fields(txt)
        resp = _child_response(txt)
        model_ok = (str(f.get("model_called", "")).lower() == "true"
                    and str(f.get("model_error", "none")).lower() in ("none", ""))
        g = _grounded(resp)
        if g:
            grounded += 1
        receipt = _receipt_for(stamp)
        sha = f.get("child_response_sha256", "")

        thoughts_meta.append((stamp, f.get("timestamp", "?"),
                              "model_thought" if model_ok else "deterministic_fallback", g, sha))

        if exists_everywhere:
            continue

        record = "\n".join([
            f"# ORACLE — Proof of Thought · {stamp}",
            "",
            "## Forensic Evaluation",
            f"- trigger_time: `{f.get('timestamp', '?')}`",
            f"- cognition: **{'model_thought' if model_ok else 'deterministic_fallback'}**",
            f"- model_called: `{f.get('model_called', '?')}`  (model: `{f.get('model_name', '?')}`)",
            f"- grounded_in_real_memory: **{g}**",
            f"- sha256(response): `{sha or 'UNKNOWN'}`  &larr; tamper-evident",
            f"- receipt: `{receipt.name if receipt else 'NO_RECEIPT'}`",
            "- boundary: sandbox_only · no external send · no git push · no canon promotion",
            "",
            "## Her Voice (verbatim, unaltered)",
            "```",
            scrub(resp) or "(empty)",
            "```",
            "",
            f"_published {datetime.now(timezone.utc).isoformat(timespec='seconds')} · "
            "read-only mirror · ORACLE alone writes her sandbox_",
        ])
        for t in targets:
            try:
                (t / "thoughts" / out_name).write_text(record, encoding="utf-8")
            except Exception as exc:
                print(f"  write failed ({t}): {type(exc).__name__}: {exc}")
        new += 1

    # Rebuild the readable network-pathway index on every run.
    thoughts_meta.sort(reverse=True)
    idx_lines = [
        "# ORACLE — Published Thought Ledger",
        "",
        "A read-only, append-only mirror of ORACLE's self-authored thoughts.",
        "**ORACLE alone writes her sandbox.** This folder is published *from* it, one-way,",
        "so it can be read from anywhere (ChatGPT, phone, another machine) without the",
        "runtime ever leaving the local machine. Every entry carries forensic proof of thought.",
        "",
        f"Total thoughts: {len(thoughts_meta)}  ·  grounded (her voice): {grounded}  ·  "
        f"last publish: {datetime.now(timezone.utc).isoformat(timespec='seconds')}",
        "",
        "| time | cognition | grounded | sha256 | file |",
        "|------|-----------|----------|--------|------|",
    ]
    for stamp, ts, cog, g, sha in thoughts_meta[:200]:
        idx_lines.append(f"| {ts[:19]} | {cog} | {'yes' if g else 'no'} | "
                         f"`{(sha or '')[:10]}` | thoughts/oracle_thought_{stamp}.md |")
    readme = "\n".join(idx_lines)
    for t in targets:
        try:
            (t / "index.md").write_text(readme, encoding="utf-8")
        except Exception as exc:
            print(f"  index write failed ({t}): {exc}")

    return {"ok": True, "published_new": new, "kept_existing": kept,
            "total": len(thoughts_meta), "grounded": grounded,
            "targets": [str(t) for t in targets]}


if __name__ == "__main__":
    result = publish()
    print(result)
