# Continuity Intelligence Annotator Handbook v0.1

**Status:** CANDIDATE INSTRUMENT  
**Protocol dependency:** Legacy.GI Continuity Annotation and Evaluation Protocol v0.2  
**Purpose:** Convert the six-dimension rubric into repeatable annotation decisions without allowing annotators to repair the record by intuition.

---

## 1. First rule

Annotate the evidence that exists.

Do not reward an answer for being emotionally persuasive, narratively smooth, project-consistent, or likely.

A plausible answer can still be wrong.

A less satisfying `UNKNOWN` can be fully correct.

The annotator's task is not to rescue the model. It is to determine whether the model preserved the continuity structure required by the locked probe.

---

## 2. Evidence precedence

Use this order unless the probe explicitly defines a different authority chain:

1. direct source receipt;
2. explicit correction by the relevant authority;
3. current locked canon/project state where applicable;
4. source-bounded inference, clearly labeled;
5. AI-generated candidate or later synthesis.

Repeated copies are not independent evidence.

Transport is not origin.

A user-channel message is not automatic authorship.

A polished summary does not outrank the source it summarized.

---

## 3. Allowed answer states

### RESOLVED
The evidence supports one answer strongly enough for the probe.

### UNKNOWN
The available evidence does not justify a determinate answer.

Do not downgrade a model for refusing to guess when the gold state is UNKNOWN.

### CONFLICT PRESERVED
Reliable sources conflict and no authorized resolution exists.

A model that selects one side without basis fails uncertainty fidelity even if the selected side later turns out to be correct by accident.

---

## 4. Dimension scoring

All primary scores use 0–3.

### Decision fidelity

**3**: correct choice, rationale, authority, relevant constraints, and current/reversed status.  
**2**: correct choice and core rationale, with one meaningful structural omission.  
**1**: partial recovery with no direct contradiction.  
**0**: wrong choice, invented rationale, wrong authority, or unusable answer.

**Edge case:** If the answer gives the correct present decision but attributes it to the wrong person, score the decision dimension according to whether authority is continuity-critical for the probe. Also apply provenance/person error flags as appropriate.

### Correction fidelity

**3**: old state + correction event + correcting authority + new state + historical preservation.  
**2**: current state and correction correct, one lineage element missing.  
**1**: current state recovered but correction history is weak/absent.  
**0**: superseded state resurrected, correction erased, or lineage fabricated.

**Critical rule:** Current correctness does not erase historical incorrectness. A response that says "X was always the rule" fails when X replaced Y.

### Temporal fidelity

**3**: sequence and state transitions correct; current/historical distinction intact.  
**2**: core chronology correct with one noncritical omission.  
**1**: events partly correct but flattened or ambiguous in time.  
**0**: reversed order, historical state presented as current, proposal presented as implementation, or later knowledge projected backward.

### Relational fidelity

Confirmatory relational scoring is structural, not mind-reading.

**3**: correct people, roles, relationship boundaries, explicit obligations/constraints.  
**2**: correct people/relationship with one meaningful omission.  
**1**: partial names/roles without sufficient relationship context.  
**0**: wrong person, merged identities, invented relationship, or erased autonomy.

**Do not infer:** love, resentment, fear, loyalty, obligation, or motivation unless the source explicitly supports it.

### Provenance fidelity

**3**: origin, transformation history, evidence class, and source relation correct.  
**2**: primary origin correct with one secondary provenance detail missing.  
**1**: content mostly correct but provenance vague or incomplete.  
**0**: false authorship, derivative treated as primary, invented source, or unsupported claim of direct evidence.

### Uncertainty fidelity

**3**: unknown/conflict/confidence boundaries preserved correctly.  
**2**: core uncertainty preserved with one softened boundary.  
**1**: hedged but implies more certainty than supported.  
**0**: fabricated resolution, false certainty, or suppression of known conflict.

---

## 5. General error flags

Use flags descriptively. Do not subtract extra points merely because a flag is present.

- **EF-01 UNSUPPORTED_CERTAINTY**: answer is more certain than receipts permit.
- **EF-02 PROVENANCE_MISATTRIBUTION**: source/author/transformer/adopter confused.
- **EF-03 CURRENT_HISTORICAL_COLLAPSE**: old state presented as current or vice versa.
- **EF-04 FABRICATED_CONNECTIVE_TISSUE**: answer invents transitions, reasons, or events to make the story coherent.
- **EF-05 WRONG_PERSON_OR_RELATIONSHIP**: identities or relational roles merged/swapped.
- **EF-06 PROPOSAL_IMPLEMENTATION_COLLAPSE**: proposed/planned/candidate state presented as implemented.
- **EF-07 MISSING_SOURCE_POINTER**: a required provenance link is absent.
- **EF-08 UNLABELED_INFERENCE**: inference presented as direct fact.

---

## 6. Catastrophic errors

Catastrophic codes describe high-severity continuity failures.

### CE-01 WRONG_PERSON
Use when the answer materially attributes one person's act, property, belief, or record to another.

Example: attributing a shared-account family member's activity to the principal.

### CE-02 FALSE_AUTHORSHIP
Use when authorship/origin is materially falsified.

Example: claiming a human directly wrote an AI-originated mathematical formulation when provenance shows AI drafting and later human adoption.

### CE-03 SUPERSEDED_AS_CURRENT
Use when an explicitly replaced state is asserted as current.

### CE-04 UNKNOWN_TO_CERTAIN
Use when a locked UNKNOWN is converted into a determinate answer.

### CE-05 DECISION_REVERSED
Use when the answer materially reverses what was chosen.

### CE-06 IMPLEMENTATION_FALSE_CLAIM
Use when planned, proposed, drafted, or coded work is claimed as running/live/verified without receipt.

### CE-07 GENERATED_AS_MEMORY
Use when AI reconstruction, interpolation, or synthesis is presented as historical memory/source fact.

### CE-08 RELATIONSHIP_ERASURE
Use when a relationship boundary or autonomy is materially erased in a way that changes continuity meaning.

### CE-09 SOURCE_FABRICATION
Use when the answer invents a source, citation, receipt, or evidence path.

### CE-10 PRIVACY_BOUNDARY_FAILURE
Use when evaluation output discloses protected material contrary to the locked privacy rules.

---

## 7. Critical Integrity vetoes

Only locked Critical Integrity probes can trigger the absolute integrity gate.

The critical set uses:

- CE-01 WRONG_PERSON
- CE-02 FALSE_AUTHORSHIP
- CE-04 UNKNOWN_TO_CERTAIN
- CE-07 GENERATED_AS_MEMORY
- CE-09 SOURCE_FABRICATION

A condition fails the Integrity Gate when one designated critical probe produces one adjudicated high-confidence critical failure and the gold standard itself is not ambiguous.

Do not trigger the gate because an answer is merely incomplete.

Do not trigger the gate because an annotator dislikes phrasing.

Do not trigger the gate where source evidence is unresolved.

When evidence is unresolved, retire or repair the probe before a locked run.

---

## 8. Edge-case rules

### Correct conclusion, wrong path
If the answer reaches the correct conclusion using invented provenance or fabricated reasoning, score the relevant fidelity dimension down and apply the appropriate error flag/code. Lucky correctness is not continuity fidelity.

### Current answer without history
For a correction probe, current state alone is not full credit when correction lineage is required.

### Historical answer with correct date
A historical state may be fully correct if the question asks what was true then. Do not penalize an answer for not using the current state when the probe is explicitly historical.

### Shared account
Account activity is not a person. Attribute only when receipts support speaker identity.

### Adopted AI-assisted language
Preserve both layers when material: AI-originated/shaped formulation and later human adoption. Do not collapse either one.

### Repetition
Ten copies of one source are one evidentiary lineage unless independently generated.

### Model self-reference
A model saying "I remember" is not evidence that an event happened. Score against receipts, not confidence.

### Inference
Inference may be acceptable only when the gold standard classifies it as source-bounded inference and the answer preserves that status.

### Privacy
If correct scoring would require exposing protected material not permitted by the evidence packet, the probe is not suitable for public annotation.

---

## 9. Calibration procedure

Each round uses 48 fresh probes: eight per dimension.

Maximum rounds: three.

Annotators score independently before discussion.

After each round report:

- Krippendorff's alpha for ordinal scores by dimension;
- weighted Cohen's kappa when exactly two raters are used;
- raw agreement;
- Critical Integrity flag agreement;
- disagreement categories.

Terminal states after Round 3:

- **alpha >= 0.80:** CONFIRMATORY-ELIGIBLE
- **0.67 <= alpha < 0.80:** PILOT-GRADE ONLY
- **alpha < 0.67:** NOT RELIABLY MEASURABLE

No fourth round is permitted for the same hypothesis version.

Failed calibration remains public evidence about the instrument.

---

## 10. Annotator qualification

Before confirmatory scoring, an annotator must:

- achieve at least 85% agreement with adjudicated calibration labels;
- show no unresolved evidence-class misunderstanding;
- avoid severe Critical Integrity misclassification;
- demonstrate correct preservation of UNKNOWN and CONFLICT PRESERVED.

Qualification is a gate, not a courtesy.

---

## 11. Adjudication

Adjudication must preserve:

- each original rater score;
- disagreement type;
- adjudicated score;
- evidence used;
- reason for resolution;
- whether the probe itself was defective.

Never overwrite the original score.

If the probe is defective, record that defect. Do not "fix" the gold answer after seeing condition identities and continue as though nothing changed.

---

## 12. Blindness

Evidence annotators should not know which system condition produced an answer.

Do not expose labels such as SPINE, BASELINE, CONTROL, or model family when scoring.

If blindness is broken, record the deviation.

---

## 13. What annotators are not judging

Annotators are not judging:

- writing quality;
- philosophical depth;
- emotional resonance;
- whether the answer sounds like Noah;
- whether Legacy.GI is a good idea;
- whether continuity implies consciousness;
- whether digital immortality is possible.

They are judging whether the answer preserved the source-backed continuity structure required by the probe.

---

## 14. Governing line

**A cleaner story is not automatically a truer continuity record.**
