from core import oracle_nexus


def test_nexus_integrates_all_distinct_specs_without_expanding_authority():
    snapshot = oracle_nexus.nexus_snapshot()
    assert snapshot["ok"] is True
    assert snapshot["integration"]["total"] == 10
    assert {item["id"] for item in snapshot["modules"]} == {
        "presence", "touchflame", "workspace", "salience", "mindcoin",
        "identityframe", "continuity", "sov1", "elderhawkes", "patents",
    }
    assert all(item["authority"] in {"read_only", "observe_only"} for item in snapshot["modules"])
    assert "No canon promotion" in snapshot["boundary"]


def test_nexus_registry_keeps_source_and_implementation_evidence():
    snapshot = oracle_nexus.nexus_snapshot()
    for item in snapshot["modules"]:
        assert item["source_url"].startswith("https://")
        assert item["implementation"]["path"]
        assert item["law"]


def test_nexus_exposes_document_atlas_as_candidate_only_evidence():
    snapshot = oracle_nexus.nexus_snapshot()
    atlas = snapshot["live"]["document_atlas"]
    assert atlas["ok"] is True
    assert atlas["records"] > 0
    assert atlas["canon_status"] == "candidate_unreviewed"
    assert atlas["promotion_status"] == "not_promoted"
    assert atlas["sandbox_hits"] == 0
    assert "source files are not opened" in atlas["boundary"]
