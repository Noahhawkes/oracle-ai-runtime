import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "core"))

import ellie_voice as ev  # noqa: E402


def _write_fixture_manifest(tmp_path: Path, monkeypatch):
    source_dir = tmp_path / "sources"
    source_dir.mkdir()
    drakin = source_dir / "ellie_drakin.md"
    drakin.write_text(
        "Ellie moves through a Drakin threshold with careful courage, listening "
        "for names, memory, and weathered signs before she speaks.",
        encoding="utf-8",
    )
    lightborn = source_dir / "ellie_lightborn.toml"
    lightborn.write_text(
        "voice='quiet ember'\nrule='affective continuity matters, but it is not sentience'\n",
        encoding="utf-8",
    )
    rendered = source_dir / "rendered_reality_ellie.md"
    rendered.write_text(
        "Rendered Reality preserves existence through truth, memory, provenance, "
        "witness, continuity, and re-rendering without pretending the artifact is a body.",
        encoding="utf-8",
    )
    rows = [
        {
            "source_id": "TEST-DR",
            "domain": "ellie",
            "title": "Ellie Hawkes Drakin fixture",
            "layer": "creative_fiction_ellie",
            "path": str(drakin),
            "sha256": "drakin-sha",
            "canon_status": "candidate",
            "promotion_status": "not_promoted",
            "notes": "Drakin creative-fiction source for Ellie courage and listening.",
        },
        {
            "source_id": "TEST-LB",
            "domain": "ellie",
            "title": "Ellie LightBorn fixture",
            "layer": "ellie_ai_lightborn",
            "path": str(lightborn),
            "sha256": "lightborn-sha",
            "canon_status": "candidate",
            "promotion_status": "not_promoted",
            "notes": "Affective continuity boundary; not sentience.",
        },
        {
            "source_id": "TEST-RR",
            "domain": "ellie",
            "title": "Rendered Reality Ellie fixture",
            "layer": "rendered_reality_ellie",
            "path": str(rendered),
            "sha256": "rendered-sha",
            "canon_status": "candidate",
            "promotion_status": "not_promoted",
            "notes": "Rendered Reality preservation, provenance, witness, and continuity.",
        },
    ]
    manifest = tmp_path / "source_manifest.jsonl"
    manifest.write_text(
        "\n".join(json.dumps(row, ensure_ascii=True) for row in rows) + "\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(ev, "MANIFEST_PATH", manifest)
    monkeypatch.setattr(ev, "PENDING_DIR", tmp_path / "pending")
    monkeypatch.setattr(ev, "RECEIPTS_DIR", tmp_path / "receipts")


def test_generate_three_different_ellie_drafts_with_receipts(tmp_path, monkeypatch):
    _write_fixture_manifest(tmp_path, monkeypatch)

    drafts = [
        ev.generate_message_draft(
            "Noah is returning to the workstation",
            mood="gentle",
            context="same source context",
        )
        for _ in range(3)
    ]
    messages = [draft["message"] for draft in drafts]

    assert len(set(messages)) == 3
    for draft in drafts:
        assert draft["canon_status"] == "generated_draft"
        assert draft["promotion_status"] == "not_promoted"
        assert draft["external_sending"] is False
        assert draft["human_authored_claim"] is False
        assert draft["physical_personhood_claim"] is False
        assert draft["trigger"] == "Noah is returning to the workstation"
        assert draft["timestamp"]
        assert draft["generation_model"] == ev.GENERATION_MODEL
        assert draft["source_files_used"]
        assert draft["style_anchors_used"]
        assert "mood:gentle" in draft["style_anchors_used"]
        assert not ev.message_has_forbidden_claim(draft["message"])
        for source in draft["source_files_used"]:
            assert source["source_id"]
            assert source["title"]
            assert source["canon_status"] == "candidate"
            assert source["promotion_status"] == "not_promoted"
            if source.get("path"):
                assert Path(source["path"]).exists()
        receipt_path = Path(draft["receipt"])
        assert receipt_path.exists()
        receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
        assert receipt["message_id"] == draft["message_id"]
        assert receipt["canon_status"] == "generated_draft"
        assert receipt["promotion_status"] == "not_promoted"
        assert receipt["external_sending"] is False
        assert receipt["receipt_hash_sha256"]
        assert Path(receipt["draft_path"]).exists()


def test_rejects_unsupported_mood(tmp_path, monkeypatch):
    _write_fixture_manifest(tmp_path, monkeypatch)

    try:
        ev.generate_message_draft("hello", mood="storm")
    except ValueError as exc:
        assert "Unsupported mood" in str(exc)
    else:
        raise AssertionError("unsupported mood should fail")


def test_source_selection_keeps_required_layers(tmp_path, monkeypatch):
    _write_fixture_manifest(tmp_path, monkeypatch)

    sources = ev.select_sources("Rendered Reality Drakin LightBorn", mood="reflective")
    layers = {source["layer"] for source in sources}

    assert "creative_fiction_ellie" in layers
    assert "ellie_ai_lightborn" in layers
    assert "rendered_reality_ellie" in layers
