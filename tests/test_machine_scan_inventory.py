"""Tests for the machine_scan_inventory source type (TP_019).

The point under test is the boundary, not the plumbing: discovery is not
authorship, ingestion, or approval.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "core"))
from machine_scan_inventory import (  # noqa: E402
    MachineScanInventory, DiscoveredItem, DISCOVERY_RULE,
)

HUMAN_CONTEXT = (
    "Noah clarified live on OBS that the MiricleDrive file came from a file/tool "
    "he made that pulled every file from his computer and organized it by file "
    "type. He is logging the recall live on OBS for context."
)


def _inventory():
    inv = MachineScanInventory(
        inventory_name="MiricleDrive Scanner: Singularity Primitive v0",
        scan_origin="MiricleDrive tool (Noah-made), local machine scan",
        scan_scope="Noah.Physical local file universe, grouped by file type",
        file_type_grouping=["md", "txt", "docx"],
        obs_context_available=True,
        human_context_summary=HUMAN_CONTEXT,
    )
    inv.add_item(DiscoveredItem(
        discovered_path_or_title="OracleAI NoahEternal Drive Grok",
        discovered_file_type="doc",
    ))
    return inv


def test_required_fields_present():
    inv = _inventory()
    for fld in (
        "inventory_id", "inventory_name", "scan_origin", "scan_scope",
        "file_type_grouping", "authorship_status", "approval_status",
        "ingestion_status", "provenance_notes", "obs_context_available",
        "human_context_summary", "source_type", "receipt_hash",
    ):
        assert fld in inv.to_dict(), f"missing inventory field: {fld}"
    item = inv.items[0].__dict__
    for fld in (
        "discovered_path_or_title", "discovered_file_type",
        "discovered_timestamp_if_available", "authorship_status",
        "approval_status", "ingestion_status", "provenance_notes",
    ):
        assert fld in item, f"missing item field: {fld}"


def test_discovery_does_not_imply_authorship_or_approval():
    inv = _inventory()
    item = inv.items[0]
    assert item.authorship_status == "unknown"
    assert item.approval_status == "pending_noah_physical"
    assert item.ingestion_status == "discovered_not_ingested"
    assert item.can_ingest() is False


def test_nothing_is_ingestible_until_explicit_approval():
    inv = _inventory()
    assert inv.discovered_count() == 1
    assert inv.ingestible_count() == 0
    # only an explicit approval opens the gate
    inv.items[0].approval_status = "approved_by_noah_physical"
    assert inv.ingestible_count() == 1


def test_source_type_and_rule_are_set():
    inv = _inventory()
    assert inv.source_type == "machine_scan_inventory"
    assert "not automatically ingested" in inv.discovery_rule
    assert inv.discovery_rule == DISCOVERY_RULE


def test_obs_recall_is_witnessed_human_context():
    inv = _inventory()
    assert inv.obs_context_available is True
    assert inv.human_context_summary == HUMAN_CONTEXT


def test_inventory_describes_the_tool_not_the_files():
    # the inventory authorship is about the Noah-made tool, never the discovered files
    inv = _inventory()
    assert inv.authorship_status == "noah_made_tool_under_direction"
    assert inv.items[0].authorship_status == "unknown"


def test_receipt_hash_present_and_hashed():
    inv = _inventory()
    assert inv.receipt_hash and inv.receipt_hash.startswith("sha256:")
