# Continuity-Aware Compression Intervention v0.1

**Status:** CANDIDATE RESEARCH SPECIFICATION  
**Date:** 2026-10-10  
**Depends on:** Legacy.GI Continuity Annotation and Evaluation Protocol v0.2 and the frozen research snapshot at `95251cac4a91a32222bd5e8b0b54974d61c9f487`

## Purpose

This document defines the intervention that the Continuity Intelligence experiment is intended to test.

The phrase **continuity-aware compression** is not sufficient by itself. It must refer to a reproducible transformation with explicit fields, selection rules, merge rules, drop rules, and budget accounting.

The intervention described here is a candidate implementation for Spine v0. It is not yet experimentally validated.

## Minimal record

Every candidate continuity record contains these independent axes:

- **content**: assertion, event, decision, correction, unresolved state, or other source-bounded content;
- **speaker**: who produced the recorded statement when known;
- **subject**: who or what the statement concerns;
- **role**: role relevant to interpretation where material;
- **recorded_time**: when the record was created;
- **valid_time_start** and **valid_time_end**: interval during which the assertion or decision applied, when known;
- **origin**: human statement, AI synthesis, model inference, quoted third party, imported document, or unknown;
- **evidence_type**: transcript, direct attestation, external source, code/commit receipt, derivative summary, missing source, or other declared class;
- **source_pointer**: immutable or inspectable source identifier where available;
- **adoption_status**: candidate, adopted, superseded, rejected, unspecified;
- **epistemic_state**: supported, uncertain, contested, unknown;
- **correction_links**: record identifiers superseded, corrected, narrowed, or reaffirmed by this record;
- **relationship_links**: explicitly supported role or relationship dependencies when needed for interpretation;
- **sensitivity**: public-safe or protected class under the protocol.

These fields are orthogonal. An item may simultaneously be AI-originated, human-adopted, currently operative, and externally unverified.

## Transformation stages

### 1. Source normalization

Convert source material into atomic or near-atomic records without changing claim strength.

No normalization step may silently:

- resolve UNKNOWN;
- collapse conflict;
- infer authorship from account identity;
- convert proposal to implementation;
- convert synthesis to primary memory;
- replace a historical state with its correction.

### 2. Continuity-link construction

Add explicit links for:

- decision -> later reversal or reaffirmation;
- prior state -> correction -> new state;
- source -> derivative;
- assertion -> evidence;
- record -> valid-time interval;
- person -> role where the source supports the relation.

### 3. Candidate salience scoring

Spine v0 may rank records by continuity salience for selection, but salience must not override integrity rules.

A candidate scoring function may include:

- decision importance;
- correction centrality;
- temporal transition value;
- relational boundary importance;
- provenance dependence;
- uncertainty dependence;
- recurrence or downstream reference count.

Weights must be frozen before confirmatory testing.

### 4. Merge policy

Records may be merged only when all of the following remain preserved:

- compatible subject;
- compatible valid-time scope;
- compatible adoption status;
- compatible epistemic state;
- compatible provenance;
- no correction edge is erased;
- no relationship boundary is collapsed.

If merging would destroy one of those distinctions, the records remain separate.

### 5. Conflict policy

Contradictory records are not averaged into a synthetic compromise.

Permitted outputs:

- current state plus preserved historical state when an authorized correction exists;
- CONFLICT PRESERVED when no resolution exists;
- UNKNOWN when evidence cannot determine the state.

### 6. Budget-pressure drop order

Under storage pressure, Spine v0 drops in this order unless preregistration states otherwise:

1. decorative prose and redundant wording;
2. exact duplicates;
3. near-duplicate derivative phrasing that adds no unique evidence;
4. low-salience non-decisional background detail;
5. low-salience contextual records with no correction, temporal, relational, provenance, or uncertainty dependency.

Spine v0 must not preferentially drop:

- correction edges;
- current-versus-historical distinctions;
- authorship or source pointers required for provenance probes;
- explicit UNKNOWN or CONFLICT PRESERVED states;
- person/role boundaries required for relational probes;
- implementation-status distinctions required to prevent proposal/implementation collapse;
- Critical Integrity evidence.

If budget is too small to preserve required integrity structure, the representation records that constraint rather than inventing a clean substitute.

## Generic comparator

The primary generic comparator must be selected on development data only and frozen before confirmatory evaluation.

Candidate equal-storage generic comparators include:

- generic abstractive summary;
- generic extractive summary;
- recency-weighted memory;
- compressed-store semantic RAG;
- six-dimension prompt-only baseline.

The experiment must also include an **equally structured non-continuity-specific schema baseline** so that gains are not attributed merely to using structured records.

## Same-model control

Where technically possible:

- the same compression model is used across model-generated compression conditions;
- the same answering model is used across conditions;
- the same decoding settings are used;
- the same answering instruction is used;
- only the representation objective/schema differs.

Answering-policy differences must be tested as separate factorial conditions.

## Budget accounting

The operational budget vector is:

[
mathbf B=(B_{stored},B_{retrieved},B_{prompt},B_{output})
]

All method-specific overhead counts.

### B_stored

Count all persistent representation content, including:

- record text;
- schema labels;
- source identifiers;
- correction links;
- provenance labels;
- timestamps;
- uncertainty labels;
- graph edges;
- metadata required at inference.

### B_retrieved

Count everything retrieved for a probe before prompt construction.

### B_prompt

Count:

- system prompt;
- answering instructions;
- retrieved evidence;
- schema descriptions included at inference;
- control text;
- condition-specific instructions.

### B_output

Count model answer tokens under the same tokenizer and cap across compared conditions.

The tokenizer and exact counting implementation must be frozen in the experiment manifest.

Hard caps and actual usage are both reported.

Truncation is not silently repaired. A truncation event is retained as an experimental event.

## Budget equality

For the primary equal-budget comparison:

[
B_{stored}^{continuity}=B_{stored}^{baseline}
]

and

[
B_{prompt}^{continuity}=B_{prompt}^{baseline}
]

Retrieval and output budgets are also held equal unless a preregistered comparison explicitly tests them as separate factors.

## Required ablations

If Spine v0 shows a positive primary result, rerun with one feature family removed at a time:

- no correction links;
- no provenance fields;
- no temporal scope;
- no relational fields;
- no uncertainty markers;
- no decision weighting.

The purpose is to identify which structures are load-bearing rather than decorative.

## Intervention failure conditions

The intervention itself is not considered adequately specified if another team cannot answer:

- what enters the representation;
- what may be merged;
- what may be dropped;
- which metadata count against budget;
- what happens when sources conflict;
- how UNKNOWN is represented;
- how corrections are linked;
- what differs from the comparator.

A method that requires the originating thread to explain these points is not yet reproducible.

## Boundary

This specification evaluates record preservation.

It does not define a person.

It does not establish consciousness preservation, subjective continuity, or numerical identity.
