"""core/machine_scan_inventory.py - source type for a local machine scan / file inventory.

MiricleDrive is a *map of the cave*: a tool Noah made that pulled files from his
computer and grouped them by file type. The map is not the territory. A file
showing up in a scan is DISCOVERED material - it is not thereby authored by
Noah, approved, ingested, or canonical.

Hard boundaries baked in (do not relax without Noah.Physical approval):
  * LOCAL_FILE_PRESENCE != AUTHORSHIP
  * SCANNER_DISCOVERY    != APPROVAL
  * USER_CHANNEL         != AUTOMATIC_AUTHORSHIP
  * TRANSPORT            != ORIGIN
  * OBS_RECALL_CONTEXT    = HUMAN_WITNESS_EVENT (lived provenance, recorded live)

Every discovered item starts ingestion_status=discovered_not_ingested,
authorship_status=unknown, approval_status=pending_noah_physical. The schema
cannot promote any of those without an explicit human-authority decision.

Continues TP_015 (lived context is continuity material) and TP_018 (MiricleDrive
connector restore). Smallest working schema - not a re-architecture.
"""
from __future__ import annotations

import json
import sys
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "rendered_reality" / "receipts"))
from receipt import content_hash  # noqa: E402  (shared hash so records match the receipt gate)

# The rule, stated once, enforced by the defaults below.
DISCOVERY_RULE = (
    "A file discovered in an inventory may be indexed as discovered material, "
    "but it is not automatically ingested, authored, approved, or canonical."
)


def _utc() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class DiscoveredItem:
    """One reference found by the scanner. Preserve-first: filename/type/path/
    timestamp are kept verbatim; nothing about origin or approval is assumed."""
    discovered_path_or_title: str
    discovered_file_type: str = "unknown"
    discovered_timestamp_if_available: str | None = None
    authorship_status: str = "unknown"                 # never inferred from presence
    approval_status: str = "pending_noah_physical"
    ingestion_status: str = "discovered_not_ingested"  # discovery != ingestion
    provenance_notes: str = ""

    def can_ingest(self) -> bool:
        """Discovery never auto-promotes. Only an explicit approved status opens
        the gate."""
        return self.approval_status == "approved_by_noah_physical"


@dataclass
class MachineScanInventory:
    """A machine_scan_inventory source: the scan artifact itself (the map)."""
    inventory_name: str
    scan_origin: str                                   # the tool/machine that produced it
    scan_scope: str = ""                               # what it swept (e.g. "local C: drive")
    source_type: str = "machine_scan_inventory"
    file_type_grouping: list[str] = field(default_factory=list)
    items: list[DiscoveredItem] = field(default_factory=list)
    # lived provenance of the recall moment
    obs_context_available: bool = False
    human_context_summary: str = ""
    # governance
    authorship_status: str = "noah_made_tool_under_direction"  # the TOOL, not the files
    approval_status: str = "pending_noah_physical"
    ingestion_status: str = "inventory_indexed_not_ingested"
    provenance_notes: str = ""
    discovery_rule: str = DISCOVERY_RULE
    # auto
    inventory_id: str = ""
    timestamp: str = field(default_factory=_utc)
    receipt_hash: str | None = None

    def __post_init__(self) -> None:
        if not self.inventory_id:
            self.inventory_id = "msi_" + content_hash(
                self.inventory_name + self.scan_origin + self.timestamp
            ).split(":", 1)[1][:12]
        if self.receipt_hash is None:
            self.receipt_hash = content_hash(self._canonical())

    def add_item(self, item: DiscoveredItem) -> DiscoveredItem:
        self.items.append(item)
        self.receipt_hash = content_hash(self._canonical())
        return item

    def discovered_count(self) -> int:
        return len(self.items)

    def ingestible_count(self) -> int:
        """How many items have actually been approved for ingestion (should be 0
        until Noah.Physical explicitly approves)."""
        return sum(1 for i in self.items if i.can_ingest())

    def _canonical(self) -> str:
        d = asdict(self)
        d.pop("receipt_hash", None)
        return json.dumps(d, sort_keys=True, ensure_ascii=False)

    def to_dict(self) -> dict:
        return asdict(self)

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2, ensure_ascii=False)


if __name__ == "__main__":
    inv = MachineScanInventory(
        inventory_name="MiricleDrive Scanner: Singularity Primitive v0",
        scan_origin="MiricleDrive tool (Noah-made), local machine scan",
        scan_scope="Noah.Physical local file universe, grouped by file type",
        file_type_grouping=["md", "txt", "docx", "pdf", "json"],
        obs_context_available=True,
        human_context_summary=(
            "Noah clarified live on OBS that the MiricleDrive file came from a "
            "file/tool he made that pulled every file from his computer and "
            "organized it by file type. He is logging the recall live on OBS for context."
        ),
        provenance_notes="Continues TP_018; recall witnessed live on OBS.",
    )
    inv.add_item(DiscoveredItem(
        discovered_path_or_title="OracleAI NoahEternal Drive Grok",
        discovered_file_type="doc",
        provenance_notes="Title attributes Grok - TRANSPORT != ORIGIN; authorship not collapsed.",
    ))
    print(inv.to_json())
    print(f"\ndiscovered={inv.discovered_count()} ingestible={inv.ingestible_count()}")
