"""Rendered Reality Truth Replicator — ORACLE Witness Runtime (internal shorthand).

ORACLE is internal shorthand only. No claim of ownership over Oracle.AI as a
domain, brand, company, public mark, or legal entity.

Witness first. Provenance always. Truthwriter constrained. Noah.Physical approves canon.
"""
from .receipts.receipt import (  # noqa: F401
    Receipt, ReceiptStore, ReceiptError,
    CanonStatus, CANON_LADDER, ApprovalStatus, Authorship,
    classify_authorship, assert_machine_observed,
    OBS_MACHINE, OBS_RETURN_FROM_DARK, OBS_POST_EVENT_TESTIMONY,
)
from .witness_logs.witness import Witness  # noqa: F401
from .truthwriter.constraints import Truthwriter, TruthwriterError  # noqa: F401
from .pattern_buffer.buffer import PatternBuffer  # noqa: F401
from .safety import REQUIRED_HOLES, UNSAFE_PUBLIC_TERMS, PUBLIC_SAFE_DESCRIPTION  # noqa: F401
from .memory.local_memory import LocalMemory  # noqa: F401
from .memory.context_state import ContextState  # noqa: F401
from .memory.retrieval import keyword_search  # noqa: F401
from .witness_logs.session_memory import SessionMemory, SessionEvent  # noqa: F401
from .provenance_graph.query import ProvenanceQuery  # noqa: F401
from .mind import OracleMind, MindResponse, MUTATING_CAPS  # noqa: F401

__all__ = [
    "Receipt", "ReceiptStore", "ReceiptError", "CanonStatus", "CANON_LADDER",
    "ApprovalStatus", "Authorship", "classify_authorship", "assert_machine_observed",
    "OBS_MACHINE", "OBS_RETURN_FROM_DARK", "OBS_POST_EVENT_TESTIMONY",
    "Witness", "Truthwriter", "TruthwriterError", "PatternBuffer",
    "REQUIRED_HOLES", "UNSAFE_PUBLIC_TERMS", "PUBLIC_SAFE_DESCRIPTION",
    "LocalMemory", "ContextState", "keyword_search", "SessionMemory", "SessionEvent",
    "ProvenanceQuery", "OracleMind", "MindResponse", "MUTATING_CAPS",
]
