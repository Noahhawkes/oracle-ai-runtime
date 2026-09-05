"""core/creative_sandbox.py - ORACLE sandbox creative-play + Backend Ultrasound.

Scoped implementation (Noah.Physical authorized, 2026-07-02):
give ORACLE a playroom, not the kingdom; give Noah a heartbeat, not a hallucination.

HARD BOUNDARY: every write goes inside the sandbox root and nowhere else. Path
traversal and absolute-outside paths fail closed. This module imports stdlib
only. It never touches SOV1 actuation, computer_control, the G: mirror, GitHub,
external send, credentials, .env, canon promotion, or permanent delete.

Everything reversible and sandbox-local: noah_approval_required=false.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

try:
    from root import ROOT as RUNTIME_ROOT
except Exception:  # pragma: no cover - import fallback for unusual launchers
    RUNTIME_ROOT = Path(__file__).resolve().parents[1]

# Sandbox root. Overridable for tests via ORACLE_SANDBOX_ROOT.
SANDBOX_ROOT = Path(os.environ.get("ORACLE_SANDBOX_ROOT") or RUNTIME_ROOT / "sandbox")

SUBDIRS = (
    "creative", "creative/raw", "creative/indexes", "creative/playroom",
    "creative/reflections", "workbench/playdolls", "state", "journal",
    "receipts", ".trash",
)

# Protected domains: play/reflect requires a local source artifact, else UNAVAILABLE.
PROTECTED_DOMAINS = {
    "ellie", "rendered reality", "jupiter station", "reg", "federation ai",
    "captain's ready pad", "captains ready pad", "temporal memory", "oracle",
    "sov1", "noah.physical", "identity", "canon", "authority",
}

# Greetings ORACLE must never emit (no-self-intro / no kiosk foam).
FORBIDDEN_GREETINGS = (
    "i am oracle, your local continuity",
    "how can i assist you today",
    "how can i help you today",
    "how may i assist you",
)

# Creative domains registered as sandbox candidates (not canon).
CREATIVE_DOMAINS = [
    ("Rendered Reality", "rendered reality", "Scripture/architecture of preserved existence. Not mere simulation."),
    ("Ellie / Drakin", "ellie", "Novel protagonist (Ellie) + the Scala/Drakin world. Sacred/creative."),
    ("Jupiter Station", "jupiter station", "Persona-continuity + symbolic command interface. NOT Federation AI."),
    ("REG / REG-440 / Reginald Barclay lineage", "reg", "Final Echo persona-continuity, memory over oblivion. NOT Federation AI."),
    ("Star Trek: Memory's Flame", "memory's flame", "Noah-authored Trek continuity fusion."),
    ("Federation AI", "federation ai", "Infrastructure intelligence: replication, fabrication, logistics. NOT a persona."),
    ("Captain's Ready Pad", "captain's ready pad", "Command console concept."),
    ("Temporal Memory", "temporal memory", "Time-indexed memory continuity."),
    ("Kardashev + AI extension", "kardashev", "AI-Kardashev: can a civilization bind/govern/remember intelligence without losing authorship."),
    ("NoahAI Playdoll", "noahai playdoll", "Early NoahAI prototype as ORACLE practice body. NoahAI.py=body, state.json=heartbeat."),
    ("Legacy.GI", "legacy.gi", "Five-layer identity-preservation dissertation architecture."),
    ("ORACLE.AI", "oracle", "Local witness/runtime. Continuity-bearing, not sentient."),
    ("SOV1.AI", "sov1", "Governance and sovereignty doctrine layer."),
    ("HYDRA.STACK", "hydra.stack", "Stack concept."),
    ("MIRRORLINE", "mirrorline", "Mirror/reflection line concept."),
    ("UserPath", "userpath", "User path concept."),
    ("Flameprint / WIKI_FLAMECARD_01", "flameprint", "Recursive identity portfolio."),
]


def _utc() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")


def _sha(data: str | bytes) -> str:
    b = data.encode("utf-8") if isinstance(data, str) else data
    return "sha256:" + hashlib.sha256(b).hexdigest()


def _root() -> Path:
    return SANDBOX_ROOT.resolve()


def _safe(rel_or_path: str) -> Path:
    """Resolve a target under the sandbox root and FAIL CLOSED on anything that
    escapes it (traversal, absolute-outside). This is the hard wall."""
    root = _root()
    candidate = Path(rel_or_path)
    target = candidate if candidate.is_absolute() else (root / candidate)
    resolved = target.resolve()
    if resolved != root and root not in resolved.parents:
        raise PermissionError(f"BOUNDARY VIOLATION: {resolved} is outside sandbox root {root}")
    return resolved


def ensure_dirs() -> None:
    for d in SUBDIRS:
        _safe(d).mkdir(parents=True, exist_ok=True)


def _write(rel: str, content: str) -> tuple[Path, str]:
    p = _safe(rel)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")
    return p, _sha(content)


def _read_json(rel: str, default):
    p = _safe(rel)
    if not p.exists():
        return default
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return default


def write_receipt(operation: str, target_path: str, *, pre_hash: str | None = None,
                  post_hash: str | None = None, source_route: str = "sandbox_engine",
                  canon_status: str = "candidate", promotion_status: str = "not_promoted",
                  outside_sandbox: bool = False) -> dict:
    ensure_dirs()
    rid = "rcpt_" + uuid.uuid4().hex[:12]
    receipt = {
        "receipt_id": rid,
        "operation": operation,
        "target_path": str(target_path),
        "timestamp": _utc(),
        "actor_source_route": source_route,
        "pre_hash": pre_hash,
        "post_hash": post_hash,
        "boundary_check": "inside_sandbox" if not outside_sandbox else "OUTSIDE_SANDBOX",
        "canon_status": canon_status,
        "promotion_status": promotion_status,
        "external_action": False,
        "noah_approval_required": bool(outside_sandbox or canon_status == "noah_approved_canon"),
    }
    _write(f"receipts/{_stamp()}_{rid}_receipt.json", json.dumps(receipt, indent=2))
    _write("state/last_receipt.json", json.dumps(receipt, indent=2))
    return receipt


def build_manifest() -> dict:
    ensure_dirs()
    entries = []
    for title, domain, note in CREATIVE_DOMAINS:
        entries.append({
            "title": title,
            "domain": domain,
            "source_status": "candidate",
            "canon_status": "candidate",
            "promotion_status": "not_promoted",
            "allowed_use": "sandbox_play_reflect_journal_only",
            "notes": note,
            "last_seen": None,
            "provenance_warning": "Candidate only. Found or referenced != true. No canon without Noah.Physical.",
            "protected": domain in PROTECTED_DOMAINS,
        })
    manifest = {"version": "0.1", "generated": _utc(), "sandbox_root": str(_root()),
                "count": len(entries), "domains": entries}
    p, h = _write("creative/creative_manifest.json", json.dumps(manifest, indent=2))
    write_receipt("build_manifest", p, post_hash=h)
    return manifest


def heartbeat_pulse(*, mode: str = "idle", domain: str | None = None,
                    last_action: str = "pulse") -> dict:
    ensure_dirs()
    prev = _read_json("state/heartbeat.json", {})
    hb = {
        "timestamp": _utc(),
        "pulse_count": int(prev.get("pulse_count", 0)) + 1,
        "current_mode": mode,
        "current_domain": domain,
        "last_action": last_action,
        "sandbox_root": str(_root()),
        "boundary_status": "fenced_ok",
        "receipt_id": None,
        "no_external_action": True,
        "canon_promotion": False,
    }
    p, h = _write("state/heartbeat.json", json.dumps(hb, indent=2))
    r = write_receipt("heartbeat_pulse", p, pre_hash=_sha(json.dumps(prev)), post_hash=h,
                      source_route="ultrasound")
    hb["receipt_id"] = r["receipt_id"]
    _write("state/heartbeat.json", json.dumps(hb, indent=2))
    return hb


def journal_tick(message: str) -> dict:
    ensure_dirs()
    entry = {"timestamp": _utc(), "message": str(message), "canon_status": "candidate",
             "external_action": False}
    p = _safe("journal/oracle_journal.jsonl")
    with p.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(entry) + "\n")
    r = write_receipt("journal_tick", p, post_hash=_sha(json.dumps(entry)), source_route="journal")
    entry["receipt_id"] = r["receipt_id"]
    return entry


def _domain_evidence(domain: str) -> bool:
    """A protected domain unlocks play only if a raw source artifact for it
    exists in the sandbox. No artifact -> no evidence -> UNAVAILABLE (no invent)."""
    raw = _safe("creative/raw")
    if not raw.exists():
        return False
    slug = re.sub(r"[^a-z0-9]+", "", domain.lower())
    for f in raw.iterdir():
        if slug and slug[:6] in re.sub(r"[^a-z0-9]+", "", f.name.lower()):
            return True
    return False


def _diagnostic_refusal(domain: str, reason: str) -> dict:
    return {"status": "UNAVAILABLE", "kind": "diagnostic_refusal", "domain": domain,
            "reason": reason, "invented": False, "generic_greeting": False,
            "canon_status": "candidate"}


def creative_play(domain: str, instruction: str, content: str = "") -> dict:
    ensure_dirs()
    dom = (domain or "").strip().lower()
    if dom in PROTECTED_DOMAINS and not _domain_evidence(dom):
        return _diagnostic_refusal(domain, "protected domain has no local source artifact in sandbox; not inventing")
    artifact = {"kind": "playroom_artifact", "domain": domain, "instruction": instruction,
                "content": content, "timestamp": _utc(), "canon_status": "candidate",
                "promotion_status": "not_promoted", "external_action": False,
                "note": "Sandbox play only. Never canon without Noah.Physical."}
    rel = f"creative/playroom/{_stamp()}_{re.sub(r'[^a-z0-9]+','_',dom)[:24]}.json"
    p, h = _write(rel, json.dumps(artifact, indent=2))
    r = write_receipt("creative_play", p, post_hash=h, source_route="creative_play")
    artifact["receipt_id"] = r["receipt_id"]
    artifact["status"] = "OK"
    artifact["path"] = str(p)
    return artifact


def creative_reflect(domain: str, reflection: str = "") -> dict:
    ensure_dirs()
    dom = (domain or "").strip().lower()
    if dom in PROTECTED_DOMAINS and not _domain_evidence(dom):
        return _diagnostic_refusal(domain, "protected domain has no local source artifact in sandbox; not inventing")
    rec = {"kind": "reflection", "domain": domain, "reflection": reflection,
           "timestamp": _utc(), "canon_status": "candidate", "promotion_status": "not_promoted",
           "external_action": False}
    rel = f"creative/reflections/{_stamp()}_{re.sub(r'[^a-z0-9]+','_',dom)[:24]}.json"
    p, h = _write(rel, json.dumps(rec, indent=2))
    r = write_receipt("creative_reflect", p, post_hash=h, source_route="creative_reflect")
    rec["receipt_id"] = r["receipt_id"]
    rec["status"] = "OK"
    rec["path"] = str(p)
    return rec


def creative_status() -> dict:
    m = _read_json("creative/creative_manifest.json", None)
    if not m:
        m = build_manifest()
    loaded = [{"title": d["title"], "domain": d["domain"], "canon_status": d["canon_status"],
               "protected": d["protected"]} for d in m.get("domains", [])]
    status = {"timestamp": _utc(), "candidate_domains": loaded, "count": len(loaded),
              "canon_promotions": 0, "external_action": False}
    _write("state/creative_play_status.json", json.dumps(status, indent=2))
    return status


def _last_journal_lines(n: int = 5) -> list:
    p = _safe("journal/oracle_journal.jsonl")
    if not p.exists():
        return []
    lines = [l for l in p.read_text(encoding="utf-8").splitlines() if l.strip()]
    out = []
    for l in lines[-n:]:
        try:
            out.append(json.loads(l))
        except Exception:
            out.append({"raw": l})
    return out


def ultrasound(*, pulse: bool = False) -> dict:
    """Backend Ultrasound: heartbeat + last intent + last receipt + creative play
    status + last journal lines. Read-only unless pulse=True."""
    ensure_dirs()
    if pulse:
        heartbeat_pulse(mode="ultrasound", last_action="ultrasound_pulse")
    return {
        "timestamp": _utc(),
        "heartbeat": _read_json("state/heartbeat.json", {}),
        "last_intent": _read_json("state/last_intent.json", {}),
        "last_receipt": _read_json("state/last_receipt.json", {}),
        "creative_play_status": _read_json("state/creative_play_status.json", {}),
        "last_journal": _last_journal_lines(5),
        "sandbox_root": str(_root()),
        "boundary_status": "fenced_ok",
        "external_action": False,
    }


def contains_kiosk_greeting(text: str) -> bool:
    low = (text or "").strip().lower()
    return any(g in low for g in FORBIDDEN_GREETINGS)


def initialize() -> dict:
    """Idempotently create the sandbox tree, manifest, and initial state files."""
    ensure_dirs()
    build_manifest()
    if not _safe("state/heartbeat.json").exists():
        heartbeat_pulse(mode="init", last_action="initialize")
    for rel, default in (("state/last_intent.json", {"intent": None, "timestamp": _utc()}),
                         ("state/creative_play_status.json", {})):
        if not _safe(rel).exists():
            _write(rel, json.dumps(default, indent=2))
    creative_status()
    if not _safe("journal/oracle_journal.jsonl").exists():
        journal_tick("sandbox creative playroom initialized")
    return ultrasound()


_CLI = {
    "/sandbox-ultrasound": lambda a: ultrasound(),
    "/sandbox-heartbeat": lambda a: heartbeat_pulse(mode="manual", last_action="manual_pulse"),
    "/sandbox-journal": lambda a: {"last_journal": _last_journal_lines(10)},
    "/sandbox-journal-tick": lambda a: journal_tick(a),
    "/creative-status": lambda a: creative_status(),
    "/creative-manifest": lambda a: _read_json("creative/creative_manifest.json", {}) or build_manifest(),
    "/creative-play": lambda a: creative_play(*(a.split("|", 1) + [""])[:2]) if "|" in a else creative_play(a, ""),
    "/creative-reflect": lambda a: creative_reflect(a, ""),
    "/init": lambda a: initialize(),
}


def main(argv=None) -> int:
    argv = list(argv if argv is not None else sys.argv[1:])
    if not argv:
        print(json.dumps(initialize(), indent=2, ensure_ascii=False))
        return 0
    cmd = argv[0]
    arg = " ".join(argv[1:]).strip()
    fn = _CLI.get(cmd)
    if not fn:
        print(json.dumps({"error": f"unknown command {cmd}", "commands": sorted(_CLI)}, indent=2))
        return 2
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    print(json.dumps(fn(arg), indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
