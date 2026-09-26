# vector_db_DO_NOT_USE

Frozen on purpose (NEW GROUND 5 + 9). Peer review flagged a stub returning a
fake similarity score (e.g. `0.851`) that could read as real and violate
Truthwriter constraints.

Until receipts and gates are proven and real embeddings exist:

- Do **not** use random or stubbed vector scores in any user-facing or
  canon-facing output.
- Do **not** call anything here "semantic search."
- Do **not** use vector results for canon decisions.
- Prefer **grep / keyword search** for v0.1.

v0.2 (only after the receipt gate is solid): a clearly-labeled local embedding
model (e.g. all-MiniLM-L6-v2), no remote embedding APIs by default, with
embedding metadata recorded in receipts.
