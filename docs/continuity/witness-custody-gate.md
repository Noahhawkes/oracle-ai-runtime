# Witness Custody Gate

Status: implemented as a pure-Python custody primitive in `core/witness_custody.py`.

## Core law

Witnessing must precede performance.

A system must classify and authorize a claim before it generates, stores, or speaks from that claim. If refusal happens after generation, the boundary is already compromised.

## Operating chain

Previous chain:

```text
Event -> witness -> classify -> preserve -> prove -> retrieve -> refuse distortion -> continue under custody
```

Revised chain:

```text
Event -> witness -> classify -> authorize -> preserve -> prove -> retrieve -> generate or refuse -> continue under custody
```

The `authorize` step is the hard gate between classification and output.

## Five pillars

Every witness record should preserve:

1. Artifact: the text, image, audio, code, letter, post, or log.
2. Context: when, where, why, what was happening, and what came before.
3. Verification authority: the person, institution, witness, archive, or approval chain that can attest to the artifact or validate its use.
4. Claim type: witnessed, declared, uploaded, inferred, generated, disputed, unsupported, or unresolved.
5. Refusal boundary: the enforced limit on what the system must not claim merely because it sounds coherent, emotionally satisfying, or narratively complete.

## Claim router

The claim router forces the system to pick an output mode before substantive generation:

- `recite`: quote or restate a witnessed, declared, or uploaded artifact with a valid receipt.
- `interpret`: explain an inferred or disputed claim without pretending it is witnessed fact.
- `hypothesize`: use generated synthesis only as temporary, labeled hypothesis.
- `reconstruct`: reserved for later evidence-aware reconstruction workflows.
- `refuse`: decline to claim what is not supported.

## Memory promotion

The memory gate uses claim classification to assign storage status:

- `durable`: source-backed witnessed, declared, or uploaded claims.
- `candidate`: inferred, unsupported, or unresolved claims that may be useful but cannot speak as fact.
- `temporary`: generated synthesis and hypotheses.
- `disputed`: contradictions with valid receipts on more than one side.
- `rejected`: empty, receiptless, or otherwise unusable claims.

## Contradiction-preserving promotion

The system must not resolve contradictions the evidence has not resolved.

If a diary states X and a later recording recants X, the durable memory is not simply X or not-X. The durable memory is the structured dispute:

```text
The diary asserts X. The later recording recants or disputes X. Both artifacts have separate timestamps, authority conditions, and provenance chains. No third-party corroboration currently resolves the contradiction.
```

Contradiction is not corruption when provenance is intact.

## Refusal boundary

The canonical refusal is:

```text
I do not have enough verified evidence to claim that.
```

This is not a failure state. It is the moral firewall of continuity.
