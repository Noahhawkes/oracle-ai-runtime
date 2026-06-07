"""
core/integration_gate.py — External Integration ApprovalGate

The mandatory intermediary between ALL external data sources and the
ORACLE memory ledger. No connector may call memory.upsert_fact() directly.

Architecture:
  ExternalConnector -> CandidateEvent -> ApprovalGate -> ApprovedMemory

The 51/49 Human Sovereignty Rule is enforced here:
  - ORACLE renders candidates (49%)
  - Noah approves, rejects, or corrects them (51%)
  - Only approved candidates write to memory

See docs/EXTERNAL_INTEGRATION_SOVEREIGNTY.md for full design.
"""

import json
import re
import uuid
from datetime import datetime
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).parent))
from root import ROOT

PENDING_DIR = ROOT / "Projects" / "pending_candidates"

# ── Sensitive data patterns — candidates matching these are never ingested ────

_SENSITIVE_PATTERNS = [
    re.compile(r"sk-[A-Za-z0-9]{20,}"),                    # OpenAI-style keys
    re.compile(r"AKIA[0-9A-Z]{16}"),                        # AWS access keys
    re.compile(r"ya29\.[A-Za-z0-9_\-]+"),                   # Google OAuth access tokens
    re.compile(r"-----BEGIN [A-Z ]+-----"),                  # Private keys
    re.compile(r"Bearer [A-Za-z0-9_\-\.]+"),                # Bearer tokens
    re.compile(r"\b(?:\d[ -]?){13,16}\b"),                  # Credit card numbers
    re.compile(r"\b\d{3}-\d{2}-\d{4}\b"),                   # SSNs
    re.compile(r"(?i)(password|passwd|secret|api_key)\s*[:=]\s*\S+"),  # Key-value secrets
]


def _check_sensitive(text: str) -> bool:
    """Return True if text matches any sensitive pattern."""
    for pattern in _SENSITIVE_PATTERNS:
        if pattern.search(text):
            return True
    return False


# ── CandidateEvent ────────────────────────────────────────────────────────────

class CandidateEvent:
    """
    A structured, pending memory proposal from an external source.
    Immutable after creation except for status fields set by the gate.

    Parameters
    ----------
    source          : str — origin system (gmail, calendar, drive, file, browser)
    source_ref      : str — reference in source system (email ID, file path, etc.)
    raw_excerpt     : str — short excerpt (max 500 chars) — never full content
    rendered_category: str — suggested memory category
    rendered_key    : str — suggested fact key
    rendered_value  : str — suggested fact value (what ORACLE thinks this means)
    confidence      : str — 'high' / 'medium' / 'low'
    """

    VALID_STATUSES = ("PENDING_HUMAN_APPROVAL", "APPROVED", "REJECTED", "CORRECTED")
    VALID_CONFIDENCE = ("high", "medium", "low")

    def __init__(
        self,
        source: str,
        source_ref: str,
        raw_excerpt: str,
        rendered_category: str,
        rendered_key: str,
        rendered_value: str,
        confidence: str = "medium",
    ):
        if confidence not in self.VALID_CONFIDENCE:
            raise ValueError(f"confidence must be one of {self.VALID_CONFIDENCE}")

        # Truncate excerpt — never store large raw content
        excerpt = str(raw_excerpt)[:500]

        self.id = str(uuid.uuid4())
        self.source = str(source)
        self.source_ref = str(source_ref)
        self.raw_excerpt = excerpt
        self.rendered_category = str(rendered_category)
        self.rendered_key = str(rendered_key)
        self.rendered_value = str(rendered_value)
        self.confidence = confidence
        self.status = "PENDING_HUMAN_APPROVAL"
        self.submitted_at = datetime.now().isoformat()
        self.decided_at = None
        self.correction = None

        # Sensitive check runs on excerpt + rendered fields
        combined = " ".join([excerpt, rendered_key, rendered_value])
        self.sensitive_flag = _check_sensitive(combined)

    def to_dict(self) -> dict:
        return {
            "id":                 self.id,
            "source":             self.source,
            "source_ref":         self.source_ref,
            "raw_excerpt":        self.raw_excerpt,
            "rendered_category":  self.rendered_category,
            "rendered_key":       self.rendered_key,
            "rendered_value":     self.rendered_value,
            "confidence":         self.confidence,
            "status":             self.status,
            "submitted_at":       self.submitted_at,
            "decided_at":         self.decided_at,
            "correction":         self.correction,
            "sensitive_flag":     self.sensitive_flag,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "CandidateEvent":
        """Reconstruct from a stored dict (does not re-run sensitive check)."""
        obj = object.__new__(cls)
        obj.id =                 d["id"]
        obj.source =             d["source"]
        obj.source_ref =         d["source_ref"]
        obj.raw_excerpt =        d["raw_excerpt"]
        obj.rendered_category =  d["rendered_category"]
        obj.rendered_key =       d["rendered_key"]
        obj.rendered_value =     d["rendered_value"]
        obj.confidence =         d["confidence"]
        obj.status =             d["status"]
        obj.submitted_at =       d["submitted_at"]
        obj.decided_at =         d.get("decided_at")
        obj.correction =         d.get("correction")
        obj.sensitive_flag =     d.get("sensitive_flag", False)
        return obj

    def __repr__(self):
        return (f"CandidateEvent(id={self.id[:8]}... source={self.source} "
                f"status={self.status} sensitive={self.sensitive_flag})")


# ── ApprovalGate ──────────────────────────────────────────────────────────────

class ApprovalGate:
    """
    The mandatory gate between external data and the ORACLE memory ledger.

    Usage
    -----
    gate = ApprovalGate()
    ids = gate.submit(candidates)       # write to pending store
    gate.list_pending()                 # Noah reviews
    gate.approve("some-uuid")           # writes to memory
    gate.reject("some-uuid")            # never written to memory
    gate.correct("some-uuid", "fixed value")  # Noah's correction → memory

    All writes to memory.upsert_fact() flow through this class.
    No connector may import or call memory.upsert_fact() directly.
    """

    def __init__(self):
        PENDING_DIR.mkdir(parents=True, exist_ok=True)

    # ── Internal helpers ──────────────────────────────────────────────────────

    def _batch_path(self, batch_id: str) -> Path:
        return PENDING_DIR / f"{batch_id}.json"

    def _load_batch(self, batch_id: str) -> dict:
        p = self._batch_path(batch_id)
        if not p.exists():
            raise FileNotFoundError(f"Batch not found: {batch_id}")
        return json.loads(p.read_text(encoding="utf-8"))

    def _save_batch(self, batch: dict) -> None:
        p = self._batch_path(batch["batch_id"])
        p.write_text(json.dumps(batch, indent=2, ensure_ascii=False), encoding="utf-8")

    def _all_batches(self) -> list[dict]:
        batches = []
        for f in sorted(PENDING_DIR.glob("*.json")):
            try:
                batches.append(json.loads(f.read_text(encoding="utf-8")))
            except Exception:
                continue
        return batches

    def _find_candidate(self, candidate_id: str) -> tuple[dict, dict]:
        """Return (batch, candidate_dict) for a given candidate UUID."""
        for batch in self._all_batches():
            for c in batch.get("candidates", []):
                if c["id"] == candidate_id:
                    return batch, c
        raise KeyError(f"Candidate not found: {candidate_id}")

    def _write_to_memory(self, candidate: dict) -> None:
        """
        The ONLY place where external data reaches memory.upsert_fact().
        Sensitive candidates are blocked here as a final guard.
        """
        if candidate.get("sensitive_flag"):
            raise PermissionError(
                f"Candidate {candidate['id'][:8]} is flagged sensitive. "
                f"It cannot be written to memory under any circumstances."
            )
        from memory import upsert_fact
        value = candidate.get("correction") or candidate["rendered_value"]
        upsert_fact(candidate["rendered_category"], candidate["rendered_key"], value)

    # ── Public API ────────────────────────────────────────────────────────────

    def submit(self, candidates: list) -> list[str]:
        """
        Accept a list of CandidateEvents (or dicts), persist to pending store.
        Returns list of candidate IDs submitted.

        Sensitive candidates are accepted into the pending store (so Noah can
        see them) but are permanently blocked from memory writes.
        """
        if not candidates:
            return []

        batch_id = (
            datetime.now().strftime("%Y-%m-%d_%H%M%S")
            + "_" + str(uuid.uuid4())[:8]
        )
        source = candidates[0].source if hasattr(candidates[0], "source") else candidates[0].get("source", "unknown")

        batch = {
            "batch_id":     batch_id,
            "source":       source,
            "submitted_at": datetime.now().isoformat(),
            "candidates":   [
                c.to_dict() if hasattr(c, "to_dict") else c
                for c in candidates
            ],
        }
        self._save_batch(batch)
        return [c["id"] for c in batch["candidates"]]

    def list_pending(self) -> list[dict]:
        """
        Return all candidates with status PENDING_HUMAN_APPROVAL.
        Sensitive candidates are clearly flagged.
        """
        pending = []
        for batch in self._all_batches():
            for c in batch.get("candidates", []):
                if c["status"] == "PENDING_HUMAN_APPROVAL":
                    pending.append(c)
        return pending

    def approve(self, candidate_id: str) -> str:
        """
        Approve a candidate. Writes rendered_value to memory.upsert_fact().
        Raises PermissionError if candidate is sensitive.
        Returns the memory key written.
        """
        batch, candidate = self._find_candidate(candidate_id)

        if candidate["status"] != "PENDING_HUMAN_APPROVAL":
            raise ValueError(f"Candidate {candidate_id[:8]} is already {candidate['status']}.")

        self._write_to_memory(candidate)

        candidate["status"] = "APPROVED"
        candidate["decided_at"] = datetime.now().isoformat()
        self._save_batch(batch)
        return f"{candidate['rendered_category']}/{candidate['rendered_key']}"

    def reject(self, candidate_id: str) -> None:
        """
        Reject a candidate. Never written to memory. Status set to REJECTED.
        """
        batch, candidate = self._find_candidate(candidate_id)

        if candidate["status"] != "PENDING_HUMAN_APPROVAL":
            raise ValueError(f"Candidate {candidate_id[:8]} is already {candidate['status']}.")

        candidate["status"] = "REJECTED"
        candidate["decided_at"] = datetime.now().isoformat()
        self._save_batch(batch)

    def correct(self, candidate_id: str, corrected_value: str) -> str:
        """
        Noah corrects ORACLE's rendered value before approving.
        Writes the corrected value (not the original) to memory.
        Raises PermissionError if candidate is sensitive.
        Returns the memory key written.
        """
        if _check_sensitive(corrected_value):
            raise PermissionError(
                "Corrected value contains sensitive data. Cannot write to memory."
            )

        batch, candidate = self._find_candidate(candidate_id)

        if candidate["status"] != "PENDING_HUMAN_APPROVAL":
            raise ValueError(f"Candidate {candidate_id[:8]} is already {candidate['status']}.")

        candidate["correction"] = corrected_value
        self._write_to_memory(candidate)

        candidate["status"] = "CORRECTED"
        candidate["decided_at"] = datetime.now().isoformat()
        self._save_batch(batch)
        return f"{candidate['rendered_category']}/{candidate['rendered_key']}"

    def purge_old_pending(self, days: int = 30) -> int:
        """
        Remove candidates that have been pending for longer than `days` days
        without a decision. Never removes APPROVED or CORRECTED candidates.
        Returns count of candidates purged.
        """
        from datetime import timezone
        cutoff = datetime.now().isoformat()[:10]  # today's date string
        purged = 0

        for batch in self._all_batches():
            changed = False
            for c in batch.get("candidates", []):
                if c["status"] != "PENDING_HUMAN_APPROVAL":
                    continue
                submitted = c.get("submitted_at", "")[:10]
                try:
                    age = (
                        datetime.fromisoformat(cutoff) -
                        datetime.fromisoformat(submitted)
                    ).days
                except Exception:
                    continue
                if age >= days:
                    c["status"] = "REJECTED"
                    c["decided_at"] = datetime.now().isoformat()
                    c["correction"] = f"[auto-purged after {days} days]"
                    purged += 1
                    changed = True
            if changed:
                self._save_batch(batch)

        return purged

    def summary(self) -> str:
        """Return a human-readable summary of pending candidate counts."""
        counts = {"PENDING_HUMAN_APPROVAL": 0, "APPROVED": 0, "REJECTED": 0, "CORRECTED": 0, "SENSITIVE": 0}
        for batch in self._all_batches():
            for c in batch.get("candidates", []):
                status = c.get("status", "PENDING_HUMAN_APPROVAL")
                counts[status] = counts.get(status, 0) + 1
                if c.get("sensitive_flag"):
                    counts["SENSITIVE"] += 1
        lines = ["--- Integration Gate Summary ---"]
        lines.append(f"  Pending approval : {counts['PENDING_HUMAN_APPROVAL']}")
        lines.append(f"  Approved         : {counts['APPROVED']}")
        lines.append(f"  Rejected         : {counts['REJECTED']}")
        lines.append(f"  Corrected        : {counts['CORRECTED']}")
        if counts["SENSITIVE"]:
            lines.append(f"  Sensitive (blocked): {counts['SENSITIVE']}")
        return "\n".join(lines)
