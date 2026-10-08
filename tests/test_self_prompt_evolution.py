from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CORE = ROOT / "core"
for path in (ROOT, CORE):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

import self_prompt_evolution as spe  # noqa: E402


JOURNAL = """
.AI:ORACLE_SELF_PROMPT_CYCLE
child_prompt:
Write these fields:
selected_task: (the one small sandbox-only next step you choose from the above)

child_response:
reflection: old loop
selected_task: Develop a granular permission system within the sandbox environment to grant Noah specific file access securely.
self_reflection:
stop

.AI:ORACLE_SELF_PROMPT_CYCLE
child_response:
reflection: same loop again
selected_task: Develop a granular permission system within the sandbox environment to grant Noah specific file access securely.
self_reflection:
stop

.AI:ORACLE_SELF_PROMPT_CYCLE
child_response:
reflection: a little broader
selected_task: create a small sandbox data-review plan from the approved index map
self_reflection:
stop
"""


def _capsule() -> dict:
    return {
        "ok": True,
        "sources": [
            {
                "source_id": "src_a",
                "name": "Alpha.md",
                "category": "text",
                "path": r"C:\Oracle\ORACLE.AI-runtime\Alpha.md",
                "sha256_prefix": "aaa",
                "query_hits": ["ORACLE"],
            },
            {
                "source_id": "src_b",
                "name": "Beta.md",
                "category": "text",
                "path": r"C:\Oracle\ORACLE.AI-runtime\Beta.md",
                "sha256_prefix": "bbb",
                "query_hits": ["Jupiter Station"],
            },
            {
                "source_id": "src_c",
                "name": "Gamma.md",
                "category": "text",
                "path": r"C:\Oracle\ORACLE.AI-runtime\Gamma.md",
                "sha256_prefix": "ccc",
                "query_hits": ["AI Compliance Core"],
            },
        ],
    }


def test_recent_selected_tasks_dedupes_newest_first():
    tasks = spe.recent_selected_tasks(JOURNAL)

    assert tasks == [
        "create a small sandbox data-review plan from the approved index map",
        "Develop a granular permission system within the sandbox environment to grant Noah specific file access securely.",
    ]


def test_evolution_brief_contains_blacklist_and_focus_sources():
    brief = spe.render_evolution_brief(seed_text="tick one", journal_text=JOURNAL, capsule=_capsule())

    assert ".AI:SELF_PROMPT_EVOLUTION_BRIEF" in brief
    assert "repeated_task_blacklist:" in brief
    assert "granular permission system" in brief
    assert "rotating_focus_sources:" in brief
    assert "src_" in brief
    assert "sandbox_write=false" in brief
    assert "external_send=false" in brief


def test_rotated_sources_change_with_seed():
    first = spe.rotated_focus_sources(_capsule(), seed_text="tick one", recent_tasks=[], limit=2)
    second = spe.rotated_focus_sources(_capsule(), seed_text="tick two", recent_tasks=[], limit=2)

    assert len(first) == 2
    assert len(second) == 2
    assert {source["source_id"] for source in first}.issubset({"src_a", "src_b", "src_c"})
    assert {source["source_id"] for source in second}.issubset({"src_a", "src_b", "src_c"})


def test_fallback_response_avoids_repeated_permission_task():
    response = spe.fallback_response(
        seed_text="autonomous tick",
        journal_text=JOURNAL,
        capsule=_capsule(),
        reason="model_disabled",
    )

    assert "selected_task:" in response
    assert "granular permission system" not in response.lower()
    assert "model_fallback_reason: model_disabled" in response
    assert "candidate reflection only" in response
    assert "git push" in response.lower()


def test_overlap_similarity_detects_repeated_task_family():
    a = "Develop a granular permission system within the sandbox environment"
    b = "Build granular sandbox permission controls for file access"
    c = "Audit Jupiter Station timeline source gaps"

    assert spe.overlap_similarity(a, b) >= 0.5
    assert spe.overlap_similarity(a, c) < 0.4
