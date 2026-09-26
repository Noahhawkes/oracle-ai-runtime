from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_oracle_iceberg_doctrine_preserves_stack_boundary():
    text = (ROOT / "docs" / "ORACLE_ICEBERG_DOCTRINE.md").read_text(encoding="utf-8")

    assert "Canon status: candidate, not promoted" in text
    assert "ORACLE preserves continuity without lying." in text
    assert "Noah.Physical" in text
    assert "SOV1.AI" in text
    assert "Rendered Reality" in text
    assert "Legacy.GI" in text
    assert "AI Compliance Core" in text
    assert "AI Compliance Core is not ORACLE in total." in text
    assert "Do not promote this document to canon automatically." in text


def test_existing_doctrines_link_to_iceberg_map():
    oracle = (ROOT / "docs" / "ORACLE_DOCTRINE.md").read_text(encoding="utf-8")
    compliance = (ROOT / "docs" / "AI_COMPLIANCE_CORE_DOCTRINE.md").read_text(encoding="utf-8")

    assert "docs/ORACLE_ICEBERG_DOCTRINE.md" in oracle
    assert "docs/ORACLE_ICEBERG_DOCTRINE.md" in compliance
    assert "it must not collapse the entire ORACLE project into a compliance product" in compliance
