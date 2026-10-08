# Rendered Reality Truth Replicator

Internal runtime shorthand: **ORACLE Witness Runtime**.

> ORACLE is internal shorthand only. No claim of ownership over Oracle.AI as a
> domain, brand, company, public mark, or legal entity.

A local continuity and witness runtime that routes human signal, AI outputs,
thread passes, source fragments, claims, build reports, and rendered artifacts
through **provenance and approval** before anything becomes canon.

**Core rule:** Write from truth. Do not manufacture truth.
**Core compression:** Replicate the book from the person's lived pattern, not
from AI invention.

## The gate (v0.1 — what's built)

The receipt is the gate. Built first, before vectors or connectors.

- `receipts/receipt.py` — `Receipt`, the 7-rung `CanonStatus` ladder,
  `Authorship`, `ApprovalStatus`, Return-from-Dark validation, the
  `assert_machine_observed` guard, and `ReceiptStore`.
- `witness_logs/witness.py` — `Witness` (the primary role): `observe_event`,
  `record_testimony`, `mark_not_observed`, `create_return_from_dark_record`,
  `generate_witness_statement`.
- `truthwriter/constraints.py` — `preview_candidate` / `render_draft` /
  `promote_to_canon`. Only `promote_to_canon` requires a receipt **and** approval.
- `pattern_buffer/buffer.py` — stores only Noah-approved canon.
- `safety.py` + `HOLES.md` + `PUBLIC_SAFE_LANGUAGE.md` — required holes and
  public-safe language, enforced by tests.

## Canon ladder

`external_thread_pass_signal → candidate_idea → draft_architecture →
claimed_build → runtime_ingested_record → witness_verified_record →
noah_approved_canon`

No promotion to canon without a receipt and Noah.Physical approval.

## NOT built (by design)

Live Drive connector, cross-AI import connectors, Latent Canon Engine,
autonomous loop, relational/person-like agent, vector scores in output. See
`HOLES.md`.

## Tests

```
python -m pytest rendered_reality/tests -q
```

Witness first. Provenance always. Truthwriter constrained. Noah.Physical approves canon.
