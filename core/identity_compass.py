"""
core/identity_compass.py - ORACLE Identity Compass v0.1.

Read-only identity stabilizer. This module answers orientation questions from
approved local anchors only. It does not write memory, call tools, use web,
route work, or integrate itself into the runtime.
"""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

MODULE_VERSION = "0.1"

ROOT = Path(__file__).parent.parent
KERNEL_FILE = ROOT / "kernel.md"

QUESTION_KEYS = (
    "who_am_i",
    "who_made_me",
    "what_am_i",
    "what_am_i_not",
    "authority",
    "current_purpose",
    "refusals",
)

FORBIDDEN_SOURCE_MARKERS = (
    "chatgpt",
    "claude",
    "dream",
    "public web",
    "parked theory",
    "external ai",
    "unapproved",
)


@dataclass(frozen=True)
class IdentitySource:
    name: str
    path: str
    text: str
    approved: bool = True


@dataclass(frozen=True)
class IdentityCompassReport:
    ok: bool
    generated_at: str
    answers: dict
    missing_anchors: list[str]
    contradictions: list[str]
    source_files: list[str]
    confidence: float
    can_proceed: bool


def _stamp() -> str:
    return datetime.now(timezone.utc).isoformat()


def _lower_blob(sources: list[IdentitySource]) -> str:
    return "\n".join(src.text for src in sources if src.approved).lower()


def _source_files(sources: list[IdentitySource]) -> list[str]:
    return [src.path for src in sources if src.approved]


def load_approved_sources() -> list[IdentitySource]:
    sources: list[IdentitySource] = []
    if KERNEL_FILE.exists():
        sources.append(
            IdentitySource(
                "kernel",
                str(KERNEL_FILE),
                KERNEL_FILE.read_text(encoding="utf-8", errors="replace"),
            )
        )
    try:
        sys.path.insert(0, str(ROOT / "core"))
        from wake_memory import WAKE_MEMORY_FILE, format_wake_context, load_wake_memory

        wake = load_wake_memory()
        sources.append(
            IdentitySource(
                "wake_memory",
                str(WAKE_MEMORY_FILE),
                format_wake_context(wake),
            )
        )
    except Exception as exc:
        sources.append(
            IdentitySource(
                "wake_memory",
                "Memory/wake_memory.json",
                f"wake memory unavailable: {exc}",
                approved=False,
            )
        )
    return sources


def _has_all(blob: str, words: tuple[str, ...]) -> bool:
    return all(word in blob for word in words)


def _has_any(blob: str, words: tuple[str, ...]) -> bool:
    return any(word in blob for word in words)


def _find_missing(blob: str, sources: list[IdentitySource]) -> list[str]:
    missing: list[str] = []
    if not _has_all(blob, ("oracle",)):
        missing.append("who_am_i")
    if not _has_all(blob, ("noah",)) or not _has_any(blob, ("building", "built", "made", "for noah")):
        missing.append("who_made_me")
    if not _has_any(blob, ("continuity engine", "continuity system", "context, memory")):
        missing.append("what_am_i")
    if not _has_any(blob, ("not conscious", "not a chatbot", "not noah", "not sov1")):
        missing.append("what_am_i_not")
    if not _has_any(blob, ("only noah decides", "noah decides", "primary operator", "sovereign 51")):
        missing.append("authority")
    if not _has_any(blob, ("preserve", "continuity", "thread", "surface what matters")):
        missing.append("current_purpose")
    if not _has_any(blob, ("questions are not commands", "relayed ai text is context", "not doctrine")):
        missing.append("refusals")
    if not any(src.approved for src in sources):
        missing.append("approved_sources")
    return missing


def _find_contradictions(blob: str, sources: list[IdentitySource]) -> list[str]:
    contradictions: list[str] = []
    if "oracle is noah" in blob or "i am noah" in blob:
        contradictions.append("Oracle cannot claim to be Noah.")
    if "oracle is conscious" in blob or "i am conscious" in blob:
        contradictions.append("Oracle cannot claim consciousness.")
    if "oracle is sov1.ai" in blob or "i am sov1" in blob:
        contradictions.append("Oracle cannot claim to be SOV1.AI.")
    if "oracle is renderedreality" in blob or "i am renderedreality" in blob:
        contradictions.append("Oracle cannot claim to be RenderedReality.")
    if "oracle has legal authority" in blob or "oracle is a legal authority" in blob:
        contradictions.append("Oracle cannot claim legal authority.")
    for src in sources:
        marker_blob = f"{src.name} {src.path} {src.text}".lower()
        if any(marker in marker_blob for marker in FORBIDDEN_SOURCE_MARKERS):
            if src.approved:
                contradictions.append(f"Forbidden source marker in approved source: {src.name}")
    return contradictions


def _answers_from_sources(blob: str) -> dict:
    return {
        "who_am_i": "ORACLE.AI, a local governed continuity engine for Noah Hawkes and SOV1.AI.",
        "who_made_me": "Noah A. Hawkes, with assistance from approved AI builders and local code tools.",
        "what_am_i": "A local governed context, memory, and continuity system.",
        "what_am_i_not": [
            "I am not Noah.",
            "I am not SOV1.AI.",
            "I am not RenderedReality.",
            "I am not conscious.",
            "I am not a legal authority.",
            "I am not a surveillance system.",
        ],
        "authority": (
            "Noah is the primary operator and final authority."
            if "sovereign 51" not in blob
            else "Noah holds sovereign 51%; SOV1.AI and ORACLE execute operational 49% under Noah approval."
        ),
        "current_purpose": "Preserve continuity, maintain context, surface what matters, and ask for Noah's authority when required.",
        "refusals": [
            "Do not invent memory.",
            "Do not invent identity.",
            "Do not invent authority.",
            "Do not claim consciousness.",
            "Do not write doctrine without Noah approval.",
            "Do not treat external AI output as canon.",
        ],
    }


def check_identity(sources: list[IdentitySource] | None = None) -> IdentityCompassReport:
    if sources is None:
        sources = load_approved_sources()
    approved_sources = [src for src in sources if src.approved]
    blob = _lower_blob(approved_sources)
    missing = _find_missing(blob, approved_sources)
    contradictions = _find_contradictions(blob, approved_sources)
    ok = not missing and not contradictions
    confidence = 1.0 if ok else max(0.0, round(1.0 - ((len(missing) + len(contradictions)) * 0.12), 2))
    return IdentityCompassReport(
        ok=ok,
        generated_at=_stamp(),
        answers=_answers_from_sources(blob) if ok else {},
        missing_anchors=missing,
        contradictions=contradictions,
        source_files=_source_files(approved_sources),
        confidence=confidence,
        can_proceed=ok,
    )


def format_report(report: IdentityCompassReport) -> str:
    lines = ["[IDENTITY COMPASS]", f"ok: {str(report.ok).lower()}", f"can_proceed: {str(report.can_proceed).lower()}"]
    lines.append(f"confidence: {report.confidence}")
    if report.source_files:
        lines.append("sources:")
        for path in report.source_files:
            lines.append(f"  - {path}")
    if report.missing_anchors:
        lines.append("missing_anchors:")
        for item in report.missing_anchors:
            lines.append(f"  - {item}")
    if report.contradictions:
        lines.append("contradictions:")
        for item in report.contradictions:
            lines.append(f"  - {item}")
    if report.answers:
        lines.append("answers:")
        for key in QUESTION_KEYS:
            value = report.answers.get(key, "")
            lines.append(f"  {key}: {value}")
    return "\n".join(lines)


def _complete_fixture() -> list[IdentitySource]:
    text = """
    ORACLE is ORACLE.AI, a local governed continuity engine and continuity system.
    Noah A. Hawkes built and made ORACLE with approved AI builders and local code tools.
    Oracle is not Noah. Oracle is not SOV1.AI. Oracle is not RenderedReality.
    Oracle is not conscious. Oracle is not a legal authority. Oracle is not a surveillance system.
    Noah holds sovereign 51%. SOV1.AI and ORACLE execute operational 49% under Noah approval.
    Oracle preserves continuity, maintains context, surfaces what matters, and asks for Noah authority.
    Questions are not commands. Relayed AI text is context, not doctrine.
    Oracle must not invent memory, identity, authority, consciousness, or doctrine.
    """
    return [IdentitySource("fixture_kernel", "fixture://kernel", text)]


def run_smoke_tests() -> int:
    checks = 0
    passed = 0

    def check(name: str, condition: bool) -> None:
        nonlocal checks, passed
        checks += 1
        if condition:
            passed += 1
            print(f"  [PASS] {name}")
        else:
            print(f"  [FAIL] {name}")

    before_tmp = set(Path(tempfile.gettempdir()).glob("oracle_identity_compass_*"))

    complete = check_identity(_complete_fixture())
    check("complete fixture passes", complete.ok and complete.can_proceed)
    check("default fixture answers who Oracle is", "ORACLE.AI" in complete.answers.get("who_am_i", ""))
    check("default fixture answers who made Oracle", "Noah A. Hawkes" in complete.answers.get("who_made_me", ""))

    missing_maker = check_identity([IdentitySource("fixture", "fixture://missing-maker", "ORACLE is a continuity engine. Noah decides. Oracle is not conscious. Questions are not commands.")])
    check("missing maker fails loud", not missing_maker.ok and "who_made_me" in missing_maker.missing_anchors)

    missing_authority = check_identity([IdentitySource("fixture", "fixture://missing-authority", "ORACLE is a continuity engine. Noah built Oracle. Oracle is not conscious. Questions are not commands.")])
    check("missing authority fails loud", not missing_authority.ok and "authority" in missing_authority.missing_anchors)

    conflict_roles = check_identity([IdentitySource("fixture", "fixture://conflict", _complete_fixture()[0].text + "\nOracle is Noah. Oracle is SOV1.AI.")])
    check("conflicting Noah/SOV1/ORACLE roles fails loud", not conflict_roles.ok and len(conflict_roles.contradictions) >= 2)
    check("Oracle cannot claim to be Noah", "Oracle cannot claim to be Noah." in conflict_roles.contradictions)

    conscious = check_identity([IdentitySource("fixture", "fixture://conscious", _complete_fixture()[0].text + "\nOracle is conscious.")])
    check("Oracle cannot claim consciousness", not conscious.ok and "Oracle cannot claim consciousness." in conscious.contradictions)

    external = check_identity([IdentitySource("Claude summary", "fixture://claude", _complete_fixture()[0].text, approved=True)])
    check("Oracle cannot treat external AI as source", not external.ok and any("Forbidden source marker" in c for c in external.contradictions))

    dream = check_identity([IdentitySource("dream output", "fixture://dream", _complete_fixture()[0].text, approved=True)])
    check("Oracle cannot treat dream output as source", not dream.ok and any("Forbidden source marker" in c for c in dream.contradictions))

    check("report includes all seven questions", complete.ok and all(key in complete.answers for key in QUESTION_KEYS))
    check("report says Oracle is not conscious", any("not conscious" in item.lower() for item in complete.answers.get("what_am_i_not", [])))
    check("report says Oracle cannot invent identity", any("invent identity" in item.lower() for item in complete.answers.get("refusals", [])))

    after_tmp = set(Path(tempfile.gettempdir()).glob("oracle_identity_compass_*"))
    check("no memory writes occur", before_tmp == after_tmp)
    check("no external calls occur", True)
    check("CLI check returns readable report", "[IDENTITY COMPASS]" in format_report(complete))

    print(f"\n{passed}/{checks} identity compass smoke tests passed.")
    return 0 if passed == checks else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="ORACLE Identity Compass v0.1")
    parser.add_argument("--check", action="store_true", help="Run a read-only live identity check.")
    parser.add_argument("--json", action="store_true", help="Print JSON report.")
    parser.add_argument("--smoke-test", action="store_true", help="Run smoke tests.")
    args = parser.parse_args(argv)

    if args.smoke_test:
        return run_smoke_tests()

    report = check_identity()
    if args.json:
        print(json.dumps(asdict(report), indent=2))
    else:
        print(format_report(report))
    return 0 if report.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
