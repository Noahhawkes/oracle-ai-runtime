# The Architecture of Continuity Intelligence
## Verifiable Identity Preservation, Provenance Accounting, and the Legacy.GI Framework

> **PUBLIC MONOGRAPH EDITION:** Text-preservation extraction from the source PDF for research indexing and critique. Repository publication is not equivalent to external peer review, replication, or validation.
>
> **Author:** Noah Hawkes  
> **Source binary SHA-256:** `096853c42a5a946ebeede2ce6f3e49607b2faf3ac8887bd6588a4ce33bf12c42`  
> **Public edition:** project-file text extraction normalized for GitHub indexing; figures and page geometry may not reproduce exactly  
> **Research status:** technical monograph; claim status remains claim-specific.

---

<PARSED TEXT FOR PAGE: 1 / 79>
The Architecture of Continuity
Intelligence
Verifiable Identity Preservation, Provenance Accounting,
and the Legacy.GI Framework
—
Noah Hawkes
Independent Research in AI Governance Architecture
Midlothian, TX, United States
September 2026
—
TECHNICAL MONOGRAPH
Formal Academic / Industry Publication Standard
Version 1.0 | September 2026 | All Rights Reserved
Abstract
This monograph presents a comprehensive technical specification for the
Architecture of Continuity Intelligence (ACI), a three-tier sovereignty
framework designed to address the problem of verifiable identity preservation
and knowledge provenance accounting in AI-mediated legacy systems. The
central challenge motivating this work is the following: as a human principal
accumulates assertions, decisions, and articulated positions across extended
<PARSED TEXT FOR PAGE: 2 / 79>
periods of AI-assisted interaction, no existing AI memory architecture
provides sufficient guarantees that subsequent retrieval, synthesis, or
generation accurately and exclusively reflects the principal's authentic
record, as opposed to confabulation, embedding drift, context-window
injection, or adversarial corpus manipulation. The ACI framework resolves
this problem through three architecturally distinct tiers: SOV1.AI, a sovereign
identity layer providing cryptographic root-of-trust; Oracle.AI, an inference
and routing engine that enforces the DeepCut pre-generation gate and
domain firewall policies; and Legacy.GI, a generative intelligence surface that
produces principal-voice outputs exclusively from provenance-verified corpus
content. The framework introduces a formal mathematical constraint — the
Truthful Recall Condition (TRC) — which defines the necessary and sufficient
conditions under which any generated response may be considered an
authentic representation of the principal's record. Supporting mathematical
constructs include the epistemic debt function E(M), the provenance depth
function d(a), and a three-tier confidence schema distinguishing verified,
inferred, and contextual assertions. Legal and posthumous governance
mechanisms are fully specified, including pre-registered legal instrument
registries, posthumous mode protocols, and cryptographic shredding
procedures. The framework is designed to be regulation-ready in advance of
comprehensive legislative treatment of AI legacy system governance.
Table of Contents
0. Executive Summary 4
Prefatory synthesis for senior technical and legal 
readership
1. Epistemological 
Foundations
5
1.1 The Problem of Identity 5
<PARSED TEXT FOR PAGE: 3 / 79>
Continuity Across 
Temporal Gaps
1.2 Provenance Accounting 
as Epistemic 
Infrastructure
6
1.3 Why Traditional AI 
Memory Systems Fail
8
2. Three-Tier Architecture
9
2.1 Architectural Overview
9
2.2 Tier 1 — SOV1.AI: The 
Sovereign Identity Layer
10
2.3 Tier 2 — Oracle.AI: The 
Inference and Routing 
Engine
12
2.4 Tier 3 — Legacy.GI: The 
Generative Intelligence 
Surface
14
2.5 Inter-Tier Communication
Protocol
15
3. Mathematical 
Formalization of 
Truthful Recall
17
3.1 Notation and Definitions 17
3.2 The Truthful Recall 
Condition (TRC)
18
3.3 Provenance Depth and 
Epistemic Debt
19
3.4 Confidence Tiering 
Schema
20
3.5 Formal Completeness and
Consistency Properties
21
4. The DeepCut Pre￾Generation Gate and 
Domain Firewalls
23
4.1 The DeepCut Gate: 
Rationale and 
Architecture
23
4.2 DeepCut Gate Logic: 
Formal Specification
24
4.3 Domain Firewalls 25
4.4 Firewall Interaction with 26
<PARSED TEXT FOR PAGE: 4 / 79>
TRC
5. Legal and Posthumous 
Governance
27
5.1 The Posthumous Problem 
in AI Legacy Systems
27
5.2 Pre-Registration of Legal 
Instruments
28
5.3 Posthumous Mode 
Protocol
29
5.4 Jurisdictional and 
Regulatory 
Considerations
30
5.5 Destruction and Sunset 
Protocols
31
6. Empirical Runtime 
Verification
33
6.1 Verification Architecture 
Overview
33
6.2 Key Performance 
Indicators and Metrics
34
6.3 Anomaly Detection and 
Alert Protocol
35
6.4 Runtime Verification Test 
Suite
36
6.5 Audit Trail and 
Cryptographic Integrity
37
7. Conclusion 39
7.1 Synthesis 39
7.2 Contributions and Novelty 40
7.3 Limitations and Open 
Problems
40
7.4 Future Work 41
A. Appendix A — Notation 
Reference Table
42
B. Appendix B — Inter-Tier 
Message Format 
Specification
43
C. Appendix C — Legal 
Instrument Registry 
Schema
44
<PARSED TEXT FOR PAGE: 5 / 79>
References 45
Section 0 — Executive Summary
The Architecture of Continuity Intelligence (ACI) is a formal technical
framework for the construction, operation, and governance of AI-mediated
legacy systems that preserve, authenticate, and selectively present a human
principal's accumulated knowledge, decisions, and articulated positions
across extended temporal horizons — including, where appropriate, beyond
the principal's lifetime. This document constitutes the first comprehensive
specification of that framework.
The motivating problem is one of epistemic integrity. Contemporary AI
systems are capable of storing and retrieving vast quantities of information
attributed to a human user, yet none of the prevailing architectures —
including vector database retrieval systems, retrieval-augmented generation
pipelines, or fine-tuned personal models — provide verifiable guarantees that
retrieved or generated content accurately and exclusively reflects what the
principal actually stated, approved, or believed. The failure modes are well￾documented in adjacent literature: embedding drift, context-window
injection, hallucination under sparse retrieval, and the absence of any
mechanism for posthumous governance. These are not incidental
deficiencies; they are structural properties of architectures that were not
designed with identity preservation as a primary constraint.
The ACI framework responds to this problem through a three-tier sovereignty
architecture. Tier 1, designated SOV1.AI, functions as the immutable root of
trust: a hardware-secured or air-gapped identity layer that cryptographically
anchors every assertion in the system to a verified principal identity, a session
record, and a timestamp. SOV1.AI issues no content; it issues only identity
<PARSED TEXT FOR PAGE: 6 / 79>
tokens and authorization signals. Tier 2, designated Oracle.AI, is the
inference and routing engine. It mediates all interactions between the
sovereign identity layer and the generative surface, enforces domain firewall
policies, and — most critically — operates the DeepCut pre-generation gate, a
mandatory interception mechanism that evaluates every prospective
response against the Truthful Recall Condition (TRC) before generation
proceeds. Tier 3, designated Legacy.GI, is the generative intelligence
surface: the user-facing layer that produces outputs in the principal's voice,
style, and epistemic framework, drawing exclusively from the provenance￾verified corpus maintained in Tier 2. Legacy.GI generates; it does not
retrieve, decide, or self-authorize.
The mathematical core of the framework is the Truthful Recall Condition, a
formal proposition specifying that a response R satisfies TRC if and only if
every atomic assertion within R carries a verified provenance record, meets a
minimum confidence threshold, does not contradict any higher-confidence
assertion in the corpus, and introduces no unprovenanced claim without
explicit flagging. The TRC is supported by two companion constructs: the
epistemic debt function E(M), which quantifies the aggregate verification risk
in a memory corpus, and the provenance depth function d(a), which measures
the number of verified citation hops from an assertion back to its primary
session record.
The legal and posthumous governance provisions of the framework are of
particular significance for senior legal readership. The framework specifies a
pre-registered legal instrument registry — cryptographically signed during
the principal's life — that governs all posthumous access, delegation, and
modification authority. On posthumous mode activation, triggered by a
certified death attestation submitted to SOV1.AI, the system transitions to a
read-only generative state: no new assertions may be added to the corpus, no
training weights may be modified, and all outputs are watermarked as
<PARSED TEXT FOR PAGE: 7 / 79>
posthumous. The framework anticipates and is designed to operate
compatibly with the U.S. Revised Uniform Fiduciary Access to Digital Assets
Act (RUFADAA) and the posthumous provisions of the European General Data
Protection Regulation (GDPR), while acknowledging that no jurisdiction has
yet comprehensively legislated AI legacy system governance.
The practical deployment implications of this framework are substantial.
Organizations deploying AI legacy systems for high-value principals —
including executives, legal practitioners, scholars, and public figures — will
require an architecture that can withstand adversarial scrutiny of its identity
provenance chain. The ACI framework provides that architecture in a form
that is technically rigorous, legally auditable, and extensible to future
regulatory requirements.
1. Epistemological Foundations
1.1 The Problem of Identity Continuity Across 
Temporal Gaps
The concept of personal identity across time has occupied philosophical
inquiry for centuries. From Locke's memory-based theory of personal identity
to Parfit's reductionist account of psychological continuity, the philosophical
tradition has consistently recognized that identity is not a static,
instantaneous property but a relation that must be maintained, or can be
disrupted, across temporal extension.1
 The emergence of AI-mediated legacy
systems introduces a novel instantiation of this problem that classical
philosophy did not and could not anticipate: the construction of a persistent,
queryable representation of a human principal's epistemic and expressive
identity — a representation that must remain faithful to that identity not only
during the principal's active engagement with the system, but across years of
<PARSED TEXT FOR PAGE: 8 / 79>
passive accumulation, model updates, corpus drift, and ultimately the
principal's death.
The fundamental epistemological challenge may be stated precisely. A human
principal P interacts with an AI system over a period of time T, producing a set
of assertions, judgments, and articulated positions that collectively constitute
the principal's epistemic record R(P, T). At any subsequent time t > T, a
querying party — which may be P themselves, an authorized successor, or an
authorized third party — submits a query Q and expects to receive a response
that accurately represents R(P, T). The question is: what architectural and
formal conditions must the system satisfy to provide a verifiable guarantee
that the response it produces accurately and exclusively reflects R(P, T),
rather than an interpolation, confabulation, or adversarially injected
alternative?
This question entails a distinction between two axes of identity continuity that
the philosophical literature designates as synchronic and diachronic identity.
Synchronic identity concerns the coherence of a set of beliefs, assertions, and
positions at a single point in time — the question of whether the system's
representation of P at time t is internally consistent. Diachronic identity
concerns the persistence of that representation across time — the question of
whether the system's representation of P at time t2 faithfully reflects what P
actually asserted or believed at t1 < t2.
2
 Both dimensions are necessary for an
adequate account of identity continuity, and both impose distinct
architectural requirements.
The knowledge provenance problem compounds this challenge. Even if a
system preserves every assertion attributed to P without modification, the
system's ability to correctly identify the source of any given assertion — to
distinguish what P explicitly stated from what the system inferred,
interpolated, or generated in P's voice — constitutes a separate and equally
critical requirement. This is the provenance dimension of identity continuity:
<PARSED TEXT FOR PAGE: 9 / 79>
not merely that the content is correct, but that the content is correctly
attributed to its originating source, and that source can be cryptographically
verified.
Traditional chain-of-custody models, developed in legal evidentiary and
archival contexts, provide a useful partial analogy but are insufficient for AI
memory systems. Classical chain-of-custody requires that a physical or
documentary artifact be continuously tracked from its point of origin through
each subsequent transfer, with each transfer recorded and authenticated.3
 AI
memory systems differ from this model in several critical respects: the
"artifacts" in question are semantic assertions rather than physical objects;
the boundaries between origination, transformation, and inference are not
always discrete; and the systems themselves may modify their internal
representations through processes — such as embedding recomputation or
fine-tuning — that have no classical chain-of-custody analogue.
The three principal schools of epistemological justification —
foundationalism, coherentism, and reliabilism — each offer partial resources
for addressing these challenges, and each maps onto distinct components of
the ACI architecture. Foundationalism, which holds that justified belief must
ultimately rest on a bedrock of non-inferential, directly justified foundational
beliefs, maps onto the requirement for a cryptographically anchored root of
trust: a layer of the architecture whose outputs cannot be derived from, or
contaminated by, any other layer.4
 This is the role of SOV1.AI. Coherentism,
which holds that the justification of any belief derives from its coherence with
a broader system of beliefs, maps onto the consistency and completeness
properties of the memory corpus M — the requirement that no two assertions
in M be mutually contradictory, and that the corpus cohere as a unified
representation of P's epistemic state. Reliabilism, particularly process
reliabilism as developed by Goldman, holds that a belief is justified if it is
produced by a reliable cognitive process — one that tends to produce true
<PARSED TEXT FOR PAGE: 10 / 79>
beliefs.5
 This maps onto the confidence tiering schema and the DeepCut
gate's requirement that every generated assertion meet a minimum
provenance and reliability threshold before production.
Taken together, these epistemological considerations motivate the core
design principle of the ACI framework: no assertion may enter the system
without a provenance record, no assertion may exit the system without a
confidence attestation, and no generation may proceed without prior
evaluation against the Truthful Recall Condition. Identity continuity, in this
framework, is not a passive property to be assumed but an active invariant to
be enforced.
1.2 Provenance Accounting as Epistemic 
Infrastructure
Provenance, in the general sense, refers to the documented history of the
origin, custody, and transformation of an artifact. The concept is well￾established in archival science, art authentication, data engineering, and
scientific reproducibility.6
 The application of provenance accounting to AI
memory systems represents a significant extension of this concept: rather
than tracking physical artifacts or discrete data records, provenance
accounting in the ACI framework tracks the epistemic lineage of every
semantic assertion in the memory corpus — from the session in which it was
first uttered or approved, through any inferential transformations, to its
current representation in the corpus.
Definition 1.1 — Provenance Record
A provenance record π(a) for assertion a is a tuple <s, P, t, κ> where s
denotes the originating session identifier (cryptographically
authenticated), P denotes the principal identity token issued by SOV1.AI,
t denotes the UTC timestamp of origination, and κ denotes the confidence
<PARSED TEXT FOR PAGE: 11 / 79>
tier assigned to a at intake (κ ∈ {κ1, κ2, κ3}). A provenance record is said
to be complete if all four fields are populated and cryptographically
verifiable; partial if one or more fields are missing or unverifiable; and
absent if no provenance record exists for a.
The requirement that every assertion in the system carry a complete
provenance record is a non-negotiable architectural constraint of the ACI
framework. This requirement is motivated by a concept introduced in this
monograph as epistemic debt — a measure of the aggregate verification risk
that accumulates in a memory corpus as a function of unverified, low￾confidence, or shallow-provenance assertions.
Definition 1.2 — Epistemic Debt
The epistemic debt of a memory corpus M, denoted E(M), is defined as
the weighted sum of verification risk across all assertions a ∈ M.
Assertions with low confidence values and shallow provenance depth
contribute maximum epistemic debt. The formal definition is provided in
Section 3.3. Informally, E(M) represents the degree to which the corpus
M contains assertions whose truthfulness, attribution, or reliability
cannot be fully verified — and which therefore constitute latent risk for
any response generated from M.
The concept of epistemic debt is operationally significant for two reasons.
First, it provides a scalar measure of the overall epistemic health of the
corpus that can be monitored over time and used to trigger remediation
actions — such as provenance enrichment campaigns or corpus audit
procedures — when the debt trajectory becomes adverse. Second, it
establishes a formal relationship between corpus quality and response
<PARSED TEXT FOR PAGE: 12 / 79>
quality: as epistemic debt increases, the probability that any given response
satisfies the Truthful Recall Condition decreases monotonically. This
relationship is formalized in Section 3.3 and provides the mathematical basis
for the DeepCut gate's pre-generation evaluation logic.
The Truthful Recall Condition (TRC) is introduced here at the conceptual level
and formalized mathematically in Section 3.2. The TRC is a necessary
condition on every response produced by the system: a response R satisfies
TRC if and only if every atomic assertion within R is traceable to a verified
provenance record, meets a minimum confidence threshold, is consistent
with all higher-confidence assertions in M on the same subject, and does not
introduce claims that are absent from the provenance-anchored corpus
without explicit flagging as inference or synthesis.
Definition 1.3 — Truthful Recall Condition (Informal)
A response R satisfies the Truthful Recall Condition (TRC) if and only
if: (i) every atomic assertion in R is provenance-verified; (ii) every atomic
assertion in R meets the applicable confidence floor; (iii) no atomic
assertion in R contradicts a higher-confidence assertion on the same
subject in M; and (iv) no atomic assertion absent from the provenance￾anchored corpus is introduced without explicit epistemic flagging. The
formal mathematical statement is given in Section 3.2.
Provenance accounting as epistemic infrastructure thus encompasses three
distinct functions. The intake function ensures that every assertion entering
M is immediately assigned a complete provenance record, with confidence
tier determined by the intake classification rules (Section 3.4). The
maintenance function ensures that provenance records are preserved
without modification through corpus operations such as embedding
<PARSED TEXT FOR PAGE: 13 / 79>
recomputation, index rebuilding, and corpus reorganization. The retrieval
function ensures that every assertion returned by the retrieval subsystem
carries its provenance record as an inseparable component — provenance is
not stored separately from content but is architecturally coupled to it, such
that content without provenance cannot be retrieved.
1.3 Why Traditional AI Memory Systems Fail
The failure modes of traditional AI memory systems — including vector
database retrieval systems, retrieval-augmented generation (RAG) pipelines,
and fine-tuned personal models — are both numerous and well-documented in
the research literature. This section provides a systematic analysis of those
failure modes as they pertain to the identity continuity problem, establishing
the negative case that motivates the ACI architecture.
Vector database retrieval without provenance. The dominant paradigm
for AI memory systems as of the mid-2020s relies on dense vector
representations of text, stored in specialized databases and retrieved via
approximate nearest-neighbor search. This architecture has significant
operational advantages — high recall speed, scalability, and compatibility
with large language model input formats. However, it has a fundamental
epistemic deficiency: the vector representation of an assertion encodes
semantic content but discards provenance. When a vector is retrieved, the
retrieval result carries no information about who originally made the
assertion, when it was made, or in what context it was approved. The
retrieved content is semantically plausible but epistemically anonymous.7
 In
the context of an AI legacy system, this means that a retrieved assertion
attributed to the principal cannot be distinguished, at the retrieval layer, from
an assertion that was injected into the corpus by an adversary, interpolated
by the model during a previous generation, or misattributed from another
source.
<PARSED TEXT FOR PAGE: 14 / 79>
Embedding drift over model updates. Vector embeddings are not static
representations; they are computed by embedding models that themselves
evolve through training and fine-tuning. When the underlying embedding
model is updated, the semantic geometry of the vector space changes, such
that existing vectors may no longer accurately represent the semantic
content of the assertions they encode. This phenomenon — embedding drift —
means that a corpus whose vectors were computed under model version Vn
may produce semantically distorted retrieval results under model version
Vn+1, even if the underlying text content is unchanged.8
 For an AI legacy
system, embedding drift represents a form of involuntary corpus modification
that can distort retrieval without leaving any detectable trace in the content
layer.
Absence of session-scoped identity boundaries. Traditional AI memory
systems do not maintain session-scoped boundaries around the assertions
they store. Assertions from different sessions, different time periods, and
potentially different principals are stored in a single undifferentiated corpus.
This makes it impossible to distinguish between assertions that represent P's
current, reflective position and assertions that represent an earlier, perhaps
superseded, view — a distinction that is epistemologically critical for any
system claiming to faithfully represent the principal's authentic record.
Susceptibility to context-window injection. Retrieval-augmented
generation systems are vulnerable to a class of attack in which adversarial
content injected into retrieved documents influences the model's generated
output.9
 In the context of an AI legacy system, this attack vector allows an
adversary who can influence the corpus — for example, by inserting a
document that is retrieved in response to a target query — to cause the
system to generate responses that do not reflect the principal's authentic
record. Without a pre-generation gate that evaluates responses against a
<PARSED TEXT FOR PAGE: 15 / 79>
verified provenance corpus before output, there is no mechanism to detect or
block such injections.
Absence of posthumous governance primitives. No existing commercial
AI memory architecture provides any mechanism for governance after the
principal's death. There is no posthumous mode, no mechanism for the
principal to pre-register access restrictions or delegation authorities, and no
cryptographic shredding capability. This represents a complete failure of the
architecture to address the lifecycle of a legacy system — a failure that
becomes increasingly significant as AI-mediated personal data stores grow in
scope and depth.
These five failure modes are not peripheral concerns; they represent
fundamental architectural deficiencies that cannot be remediated by
incremental improvements to existing designs. The ACI framework addresses
each of them through structural means: SOV1.AI eliminates session-scoped
identity confusion and provides posthumous governance; the provenance
accounting system eliminates anonymous retrieval; the DeepCut gate
eliminates context-window injection vulnerability; and the confidence tiering
schema provides a formal mechanism for managing embedding drift and
assertion supersession.
2. Three-Tier Architecture
2.1 Architectural Overview
The ACI framework is organized as a three-tier sovereignty architecture in
which each tier operates at a distinct trust level, temporal scope, and data
sensitivity class. The tiered structure is not merely an organizational
convenience; it encodes a set of formal separation-of-concerns principles that
<PARSED TEXT FOR PAGE: 16 / 79>
are essential to the security and epistemic integrity of the system. No tier may
assume the functions of another tier, and no tier may communicate with a
non-adjacent tier except through the formally specified inter-tier
communication protocol described in Section 2.5.
The rationale for tiering follows directly from the epistemological analysis of
Section 1. A system that conflates identity management, inference, and
generation in a single architectural layer cannot provide verifiable
guarantees about any of the three functions, because the outputs of each
function influence and contaminate the others. By separating identity
management (Tier 1), inference and routing (Tier 2), and generation (Tier 3)
into architecturally distinct layers with formally specified interfaces and trust
constraints, the ACI framework provides the structural foundation for the
verifiable guarantees that the TRC requires.
Tier Designatio
n
Primary 
Function
Trust 
Level
Temporal 
Scope
Data 
Sensitivity
1 SOV1.AI Sovereign 
identity, 
root-of￾trust, key 
managemen
t, 
posthumous
governance
Maximum 
— zero 
external 
dependenci
es; 
hardware￾secured
Lifetime + 
posthumous
Critical — 
identity 
keys, 
session 
registry, 
legal 
instrument 
registry
2 Oracle.AI Inference, 
retrieval 
orchestratio
n, routing, 
DeepCut 
gate 
enforcemen
t, domain 
firewall 
managemen
t
High — 
operates 
under 
delegated 
token 
authority 
from Tier 1;
cannot self￾elevate
Session + 
corpus 
lifetime
High — 
provenance￾tagged 
corpus, 
confidence 
records, 
routing 
audit logs
3 Legacy.GI Generative 
output 
production 
in the 
principal's 
voice; style 
Restricted 
— receives 
only 
verified, 
provenance￾tagged 
Session 
(output) + 
corpus read
access
Medium — 
output 
generation; 
no direct 
corpus 
write 
<PARSED TEXT FOR PAGE: 17 / 79>
Tier Designatio
n
Primary 
Function
Trust 
Level
Temporal 
Scope
Data 
Sensitivity
and 
epistemic 
fidelity; 
posthumous
lockdown 
enforcemen
t
queries 
from Tier 2;
cannot 
initiate 
outbound 
requests
authority
The trust gradient of the architecture flows strictly from Tier 1 downward to
Tier 3. Tier 1 is the ultimate authority on identity and authorization. Tier 2
derives its authority from Tier 1 but exercises independent judgment within
its delegated authority scope. Tier 3 has no independent authority; it operates
exclusively under the directives issued by Tier 2, which are themselves
bounded by Tier 1's authorizations. This trust gradient is enforced
cryptographically through the inter-tier communication protocol and cannot
be altered by any component within the system — including Legacy.GI itself.
2.2 Tier 1 — SOV1.AI: The Sovereign Identity Layer
SOV1.AI is the root-of-trust for the entire ACI framework. Its fundamental
purpose is to maintain an immutable, cryptographically authenticated record
of the principal's verified identity and to issue identity tokens and
authorization signals that govern all downstream system operations. SOV1.AI
does not store content; it does not perform inference; it does not generate
text. Its sole domain is identity, authorization, and key management.
Components. The SOV1.AI layer comprises four primary components:
1. Identity Attestation Engine. Maintains the principal's 
cryptographic identity credential, anchored to a biometric, 
passphrase, or hardware token anchor established at enrollment. The 
identity credential is used to authenticate the principal in every 
session and to sign all session records. The attestation engine 
<PARSED TEXT FOR PAGE: 18 / 79>
operates under a zero-trust model: it authenticates each session 
independently, without assuming the validity of any prior session 
authentication.
2. Root Session Registry. An append-only, cryptographically chained 
record of all authenticated sessions, including session start and end 
timestamps, the principal's identity token used for that session, and a 
hash of the session's provenance record set. The root session registry 
is the authoritative source of truth for all session-scoped provenance 
inquiries.
3. Legal Instrument Registry. A pre-registered, cryptographically 
signed data structure specifying the principal's posthumous 
governance preferences, including authorized successors, access tier 
assignments, time-locked release conditions, and destruction 
conditions. The legal instrument registry is the only mechanism by 
which posthumous authority can be delegated (see Section 5.2 for full 
specification).
4. Key Management Service. Manages all cryptographic key material 
used by SOV1.AI, including the signing keys used to authenticate 
inter-tier tokens, the encryption keys used to protect the legal 
instrument registry, and the shredding keys whose deletion triggers 
cryptographic destruction of the corpus (see Section 5.5).
Trust model. SOV1.AI is designed to operate with zero external
dependencies. Its key material must be stored in hardware security modules
(HSMs) or equivalent air-gapped hardware, inaccessible to network￾connected components. SOV1.AI's signing authority cannot be delegated to
any software component, and its key material cannot be exported. This design
ensures that even a complete compromise of Tiers 2 and 3 does not grant an
adversary the ability to create fraudulent identity tokens or to modify the
principal's provenance record.
<PARSED TEXT FOR PAGE: 19 / 79>
Interfaces. SOV1.AI provides two interface surfaces: an outbound interface
that issues signed identity tokens and authorization signals to Oracle.AI; and
an inbound interface that accepts pre-registered legal instruments from the
principal during the enrollment phase, and posthumous activation signals
(cryptographically signed death certificate attestations or equivalent) from
registered successors. SOV1.AI does not accept inbound signals from
Legacy.GI under any circumstances.
Formal Properties of SOV1.AI
Tamper-Evidence: Any modification to the root session registry or legal
instrument registry produces a cryptographic hash mismatch detectable
by any party holding the public verification key. The append-only
structure ensures that deletions are detectable as well as modifications.
Non-Repudiation: Every signed token issued by SOV1.AI carries a
timestamp and a session reference that binds the token to a specific,
verifiable principal authentication event. No token can be credibly
attributed to a different principal or session without falsifying the
cryptographic signature.
Temporal Anchoring: All session records and token issuance events are
timestamped using a trusted time source (RFC 3161 compliant timestamp
authority or equivalent). Temporal anchoring ensures that the
chronological ordering of all system events is verifiable and cannot be
retroactively altered.
Failure modes and mitigations. Two primary failure modes are identified
for SOV1.AI and require explicit protocol specification.
Key compromise recovery. If the principal's signing key material is
compromised, a key compromise recovery protocol is initiated. This protocol
<PARSED TEXT FOR PAGE: 20 / 79>
requires the principal to re-authenticate using a pre-registered backup
authentication channel — a secondary hardware token or a split-knowledge
passphrase held by two registered trustees. Upon successful re￾authentication, new key material is generated, and the root session registry
entry corresponding to the compromise event is cryptographically flagged.
All tokens issued under the compromised key are revoked and logged.
Historical provenance records signed under the compromised key are re￾evaluated by a designated audit principal before being re-admitted to the
verified provenance class.
Principal incapacitation protocol. If the principal becomes incapacitated but
has not yet died — a state in which posthumous mode activation is not yet
appropriate, but the principal can no longer actively manage the system — a
designated guardian, pre-registered in the legal instrument registry, may
issue a temporary incapacitation flag to SOV1.AI. This flag causes Oracle.AI
to switch to a restricted routing mode in which no new corpus writes are
permitted, but read and generative operations continue under the pre￾existing authorization framework. The incapacitation flag may be lifted by the
principal upon recovery or converted to posthumous mode activation upon
the principal's death.
2.3 Tier 2 — Oracle.AI: The Inference and Routing 
Engine
Oracle.AI is the architectural mediator of the ACI framework. Its purpose is to
enforce the epistemic and authorization policies of the system between the
sovereign identity layer and the generative surface. Oracle.AI receives
queries from external parties, validates their authorization using tokens
issued by SOV1.AI, evaluates each query against the DeepCut pre-generation
gate and applicable domain firewall policies, orchestrates retrieval from the
provenance-tagged corpus, and either routes verified queries to Legacy.GI or
returns structured refusals with documented rationale.
<PARSED TEXT FOR PAGE: 21 / 79>
Components. Oracle.AI comprises five primary components:
5. Query Classifier. Receives incoming queries and classifies them by 
domain, intent type, and confidence tier requirement. The domain 
classification determines which domain firewall policies apply. The 
intent classification distinguishes between retrieval queries (seeking 
specific previously-asserted content), inference queries (seeking 
derivations from the corpus), and synthesis queries (seeking novel 
content in the principal's voice). Each intent type has a distinct 
routing path and confidence floor requirement.
6. Domain Firewall Enforcer. Applies the domain-specific access 
control policies defined in the domain firewall registry. Each firewall 
specifies the authorized confidence tiers, the authorized principals, 
and the posthumous access rules applicable to queries in that domain.
The domain firewall enforcer is a mandatory waypoint on every query 
path; it cannot be bypassed by any component.
7. Retrieval Orchestrator. Manages retrieval from the provenance￾tagged corpus, ensuring that every retrieved assertion carries its 
complete provenance record. The retrieval orchestrator does not 
return anonymized assertions; provenance is architecturally coupled 
to content at the retrieval layer.
8. Confidence Scorer. Evaluates the confidence tier of each retrieved 
assertion and the aggregate confidence profile of the candidate 
response set. Determines whether the candidate response set meets 
the applicable confidence floor requirement before routing to 
Legacy.GI.
9. DeepCut Pre-Generation Gate. The mandatory interception 
mechanism described in full in Section 4. Evaluates the candidate 
response set against the TRC before generation proceeds. The gate's 
<PARSED TEXT FOR PAGE: 22 / 79>
four decision branches — GENERATE, ENRICH, REVIEW, REFUSE — 
determine the disposition of every query.
Trust model. Oracle.AI operates under delegated authority from SOV1.AI. It
accepts identity tokens and authorization signals from SOV1.AI and routes
queries accordingly. Oracle.AI cannot self-elevate its permissions — it cannot
grant itself access to domains for which it has not received an authorization
signal from SOV1.AI, and it cannot reclassify assertions from a lower
confidence tier to a higher one without an explicit authorization signal. All
routing decisions made by Oracle.AI are logged to the cryptographically
chained audit log (Section 6.5).
Formal Properties of Oracle.AI
Determinism Under Identical Inputs: Given identical inputs — the
same query, the same corpus state, the same authorization tokens, and
the same firewall configuration — Oracle.AI must produce identical
routing decisions. Non-determinism in routing decisions would make the
system unauditable.
Auditability: Every routing decision, gate decision, and firewall
evaluation made by Oracle.AI is written to the append-only audit log
before the decision is acted upon. An auditor with access to the audit log
can reconstruct the exact sequence of Oracle.AI decisions for any session.
No Persistent Self-Modification: Oracle.AI does not update its own
routing rules, firewall configurations, or confidence scoring parameters
based on session inputs. All configuration changes must be explicitly
authorized by SOV1.AI and applied through a formally specified
configuration update protocol.
<PARSED TEXT FOR PAGE: 23 / 79>
Inter-tier positioning. Oracle.AI occupies the critical middle position in the
trust hierarchy, and this position entails a specific set of constraints that are
worth emphasizing. Oracle.AI is simultaneously a consumer of SOV1.AI's
authority (it receives and validates tokens issued by Tier 1) and a producer of
authority for Legacy.GI (it issues routing directives and verified query
payloads to Tier 3). This dual role means that any compromise of Oracle.AI
represents a greater systemic risk than a compromise of Legacy.GI, because
it affects both the authority consumption and authority production functions
of the system. The formal properties of determinism, auditability, and
prohibition of self-modification are therefore the most critical operational
constraints in the entire architecture.
2.4 Tier 3 — Legacy.GI: The Generative Intelligence
Surface
Legacy.GI is the user-facing generative layer of the ACI framework. Its
purpose is to produce outputs — responses to queries, syntheses of corpus
content, extensions of the principal's articulated positions — in the voice,
style, and epistemic framework of the principal P. Legacy.GI is where the
accumulated knowledge and expressive identity of the principal is made
accessible to authorized querying parties. It is also the component of the
architecture most visible to end users, and therefore the component most
subject to attempted manipulation or misuse.
The defining architectural constraint of Legacy.GI is the strict separation
between generation and authority. Legacy.GI generates — it does not
retrieve, decide, or self-authorize. All retrieval is performed by Oracle.AI's
retrieval orchestrator. All authorization decisions are made by Oracle.AI's
DeepCut gate and domain firewall enforcer, under authority delegated from
SOV1.AI. Legacy.GI receives from Oracle.AI a verified, provenance-tagged
query payload specifying: the content to be generated, the confidence floor
applicable to the response, the style and voice parameters, and any
<PARSED TEXT FOR PAGE: 24 / 79>
posthumous mode restrictions. Legacy.GI's generative activity is constrained
to producing output that is consistent with that payload. It cannot initiate
outbound requests, cannot access the corpus directly, and cannot modify its
own model weights without explicit authorization from SOV1.AI.
Components. Legacy.GI comprises three primary components:
10.Fine-Tuned Generative Model. A language model fine-tuned on the 
principal's authenticated corpus content to replicate the principal's 
voice, vocabulary, reasoning patterns, and expressive style. Fine￾tuning is performed under controlled conditions, with model weights 
cryptographically hashed before and after each fine-tuning event and 
the hash record stored in the root session registry. Weight 
modification outside of this formal protocol is blocked by Oracle.AI's 
authorization enforcement.
11.Provenance-Tagged Output Renderer. Processes the generative 
model's output to attach provenance metadata to each assertion in the
response, cross-referencing the provenance records of the corpus 
content that contributed to each assertion. The renderer also enforces
the epistemic flagging requirement for κ3 (contextual) assertions that 
appear in the output without direct corpus attestation.
12.Posthumous Mode Controller. Monitors the posthumous mode flag 
issued by SOV1.AI and enforces all posthumous mode restrictions, 
including the prohibition on new corpus writes, the read-only 
generative mode constraint, and the mandatory watermarking of 
posthumous outputs.
Formal Properties of Legacy.GI
Output Traceability: Every assertion in every response produced by
<PARSED TEXT FOR PAGE: 25 / 79>
Legacy.GI must carry a provenance trace referencing the corpus content
that contributed to it. Assertions without provenance traces are blocked
by the provenance-tagged output renderer before delivery.
Style Fidelity Bounds: The fine-tuned generative model is evaluated
against style fidelity metrics at regular intervals. If style fidelity falls
below a defined threshold — indicating that the model's voice
representation of the principal has degraded — the system issues an alert
and suspends generative operations pending re-evaluation.
Posthumous Lockdown Mode: Upon receipt of a posthumous mode flag
from SOV1.AI, Legacy.GI immediately transitions to read-only generative
mode. In this mode, no new content may be added to the principal's
corpus, no model weights may be modified, and all outputs are
watermarked. The transition is irreversible except by an explicit reversal
signal from SOV1.AI, which requires a matching reversal condition in the
legal instrument registry.
2.5 Inter-Tier Communication Protocol
Communication between the three tiers of the ACI framework is governed by
a formally specified protocol that ensures the integrity, authenticity, and non￾repudiability of all inter-tier messages. The protocol defines the structure of
the signed token envelope, the validation requirements at each tier, and the
behavior of the system in the event of a validation failure.
The inter-tier message format is a signed token envelope comprising the
following fields:
Field Type Description Required
envelope_id UUID Unique identifier 
for this message 
Yes
<PARSED TEXT FOR PAGE: 26 / 79>
Field Type Description Required
envelope, used in 
audit log cross￾referencing
source_tier Integer {1, 2, 3} Tier number of the 
sending component
Yes
dest_tier Integer {1, 2, 3} Tier number of the 
receiving 
component; must 
be source_tier ± 1
Yes
session_id String Cryptographically 
authenticated 
session identifier 
from root session 
registry
Yes
principal_toke
n
Signed JWT Identity token 
issued by SOV1.AI 
for the current 
session, carrying 
principal identity, 
session scope, and 
authorization 
claims
Yes
query_payload JSON The query content, 
intent 
classification, 
domain 
classification, and 
response format 
specification
Yes (Tier 2 → Tier 3
only)
provenance_ch
ain
Array of π(a) 
records
Complete 
provenance records
for all assertions 
included in or 
referenced by the 
payload
Yes
confidence_flo
or
Enum {κ1, κ2, κ3} Minimum 
confidence tier 
required for all 
assertions in the 
response
Yes
gate_decision Enum DeepCut gate 
decision for this 
message: 
GENERATE, 
ENRICH, REVIEW, 
or REFUSE
Yes (Tier 2 → Tier 3
only)
posthumous_fl
ag
Boolean Indicates whether 
posthumous mode 
Yes
<PARSED TEXT FOR PAGE: 27 / 79>
Field Type Description Required
is active; if true, 
Legacy.GI enforces 
read-only 
generative mode
envelope_signa
ture
ECDSA-P384 Cryptographic 
signature over all 
preceding fields, 
signed by the 
sending tier's key 
material
Yes
timestamp RFC 3161 
timestamp
Trusted timestamp 
for the envelope, 
used in audit log 
and non￾repudiation records
Yes
Validation and failure behavior. Upon receipt of a signed token envelope,
the receiving tier performs the following validation steps in order: (1)
signature verification against the sending tier's published public key; (2)
session_id cross-reference against the root session registry; (3)
principal_token validation against SOV1.AI's published verification key; (4)
dest_tier field check to confirm the message is addressed to the receiving tier;
(5) posthumous_flag check to confirm that the receiving tier's current
operational mode is consistent with the flag value.
If any validation step fails, the receiving tier does not process the message.
Critically, the system fails closed, not open: a validation failure does not
result in a fallback to less-secure processing; it results in message rejection,
audit log entry, and — if the failure is on the Tier 2 → Tier 3 interface — a
structured refusal returned to the querying party with documentation of the
failure type. This fail-closed design is a fundamental safety property of the
architecture: an adversary who can cause validation failures cannot use those
failures to extract information or trigger generation; they can only cause the
system to produce documented refusals.
<PARSED TEXT FOR PAGE: 28 / 79>
3. Mathematical Formalization of 
Truthful Recall
3.1 Notation and Definitions
This section establishes the formal mathematical notation used throughout
the remainder of the monograph. All symbols are also collected in Appendix A
for reference.
Symbol Type Definition
P Entity The human principal whose
identity, corpus, and legacy
the system preserves
M Set The memory corpus: the 
set of all assertions 
currently stored in the 
system, each carrying a 
provenance record
a, ai Element An atomic assertion in M; 
the subscript i indexes 
assertions in an ordered 
set
Q String A query submitted to the 
system by an authorized 
querying party
R Set A response produced by 
Legacy.GI, comprising a 
set of atomic assertions 
{a1, ..., an}
π(a) Tuple The provenance function: 
maps assertion a to its 
provenance record <s, P, t,
κ>
Πverified Set The set of all provenance 
classes that satisfy the 
completeness criterion (all 
four fields populated and 
cryptographically 
verifiable)
κ(a) Enum The confidence function: 
maps assertion a to its 
confidence tier κ ∈ {κ1, κ2, 
<PARSED TEXT FOR PAGE: 29 / 79>
Symbol Type Definition
κ3}
κfloor Threshold The minimum confidence 
tier required for assertions 
in a given response, as 
specified in the inter-tier 
message envelope
d(a) Integer The provenance depth 
function: the number of 
verified citation hops from 
assertion a back to a 
primary session record
E(M) Real The epistemic debt 
function: the aggregate 
verification risk of corpus 
M
TRC(R, M) Boolean The Truthful Recall 
Condition evaluation 
function: returns TRUE if R
satisfies TRC given M, 
FALSE otherwise
ARS(Q) Set The Acceptable Recall Set 
for query Q: the set of all 
responses R such that 
TRC(R, M) = TRUE
C(M, D) Real [0,1] Memory corpus 
completeness: the fraction 
of ground-truth domain 
assertions in domain D that
have at least one κ1 or κ2
entry in M
Ψ(M) Boolean Memory corpus 
consistency: TRUE if M 
contains no pair of κ1
assertions that are logically
contradictory
D Set A domain: a defined 
subject area over which 
domain firewall policies 
apply
3.2 The Truthful Recall Condition (TRC)
Proposition 3.1 — The Truthful Recall Condition
<PARSED TEXT FOR PAGE: 30 / 79>
A response R = {a1, a2, ..., an} to query Q satisfies the Truthful Recall
Condition TRC(R, M) = TRUE if and only if all four of the following
conditions hold simultaneously:
1. [Provenance Verification] For all ai ∈ R: π(ai) ∈ Πverified
2. [Confidence Floor] For all ai ∈ R: κ(ai) ≥ κfloor
3. [Consistency with Corpus] For all ai ∈ R: there does not exist aj ∈
M such that aj contradicts ai and κ(aj) > κ(ai)
4. [Corpus Containment] For all ai ∈ R: either ai ∈ M (with 
provenance verified) or ai is explicitly flagged in R as inference or 
synthesis, not as principal attestation
TRC(R, M) = FALSE if any of the four conditions fails for any ai ∈ R.
(3.1) TRC(R, M) = ∀ ai ∈ R: [π(ai) ∈ Πverified] ∧ [κ(ai) ≥ κfloor] ∧ [¬∃ aj ∈ M: contradicts(aj, ai) ∧
κ(aj) > κ(ai)] ∧ [ai ∈ M ∨ flagged(ai)]
Theorem 3.1 — TRC Precludes Undetected Confabulation
Statement: A system that enforces TRC on all generated responses
cannot produce undetected confabulation.
Proof Sketch: Let R be a response containing a confabulated assertion
ac — that is, an assertion that was not uttered or approved by P in any
authenticated session, and that does not follow by verified logical
inference from assertions in M. By condition (i) of TRC, π(ac) must belong
to Πverified; but since ac was not uttered in an authenticated session, no
provenance record exists for ac in the root session registry, and therefore
π(ac) ∉ Πverified. This violates condition (i), and TRC(R, M) = FALSE. By
<PARSED TEXT FOR PAGE: 31 / 79>
condition (iv), if ac is an inference not present in M, it must be explicitly
flagged as such; a flagged assertion is by definition not presented as
principal attestation, and therefore does not constitute undetected
confabulation. In either case, TRC enforcement prevents ac from
appearing in R as an undetected confabulation. It follows that a system
enforcing TRC on all responses cannot produce undetected
confabulation. □
The Acceptable Recall Set ARS(Q) for a query Q is defined as the set of all
responses R for which TRC(R, M) = TRUE. The DeepCut gate's function,
described in Section 4, is to determine whether ARS(Q) is non-empty before
routing Q to Legacy.GI — and to act appropriately if it is empty.
3.3 Provenance Depth and Epistemic Debt
Definition 3.1 — Provenance Depth
The provenance depth d(a) of assertion a ∈ M is defined as the number
of verified citation hops from a back to its primary session record in the
root session registry. For a direct session assertion (a ∈ κ1, uttered
directly by P in an authenticated session), d(a) = 1. For an inferred
assertion (κ2), d(a) = 1 + max{d(aj)} where the maximum is taken over all
κ1 or κ2 assertions from which a was inferred. For a contextual assertion
(κ3), d(a) may be undefined or set to a sentinel value dmax + 1 to indicate
maximum epistemic distance from the root.
Definition 3.2 — Epistemic Debt Function
<PARSED TEXT FOR PAGE: 32 / 79>
The epistemic debt of corpus M is defined as:
(3.2) E(M) = ∑a ∈ M [w(κ(a)) × (1 / d(a))]
where w(κ(a)) is a weighting function over confidence tiers: w(κ1) = 0
(verified assertions contribute zero epistemic debt), w(κ2) = 0.5 (inferred
assertions contribute proportional debt), w(κ3) = 1.0 (contextual
assertions contribute maximum debt scaled by inverse provenance
depth). Assertions with absent provenance records are assigned d(a) = 0
and w(κ) = 1, contributing infinite epistemic debt and triggering
immediate corpus quarantine.
Proposition 3.2 — Epistemic Debt and TRC Satisfaction
Statement: As E(M) increases monotonically, the fraction of queries Q
for which ARS(Q) is non-empty decreases monotonically.
(3.3) dE(M)/dt ≥ 0 ⇒ d|ARS(Q)|/dt ≤ 0 for the expected Q distribution
Intuition: As the corpus accumulates low-confidence, low-provenance￾depth assertions (increasing E(M)), the probability that an arbitrary
query Q can be answered with a TRC-satisfying response decreases,
because a larger fraction of potentially relevant assertions fail conditions
(i) or (ii) of Proposition 3.1. Formally, if assertions in the relevant retrieval
set R* have π(a) ∉ Πverified or κ(a) < κfloor, then TRC(R*, M) = FALSE, and no
R* ∈ ARS(Q) can be formed. As E(M) grows, this failure case becomes
increasingly likely across the query distribution.
The epistemic debt function provides the operational basis for corpus health
monitoring. The runtime verification subsystem (Section 6) tracks E(M) at
regular intervals and triggers alerts when the epistemic debt trajectory
<PARSED TEXT FOR PAGE: 33 / 79>
becomes adverse — specifically when E(M) exceeds a pre-defined threshold
Emax or when the rate of increase dE(M)/dt exceeds a pre-defined threshold for
two consecutive measurement intervals.
3.4 Confidence Tiering Schema
The ACI framework defines three confidence tiers that classify every
assertion in the memory corpus according to the strength of the principal's
attestation and the verifiability of the assertion's provenance.
Tier Designation Definition Epistemic 
Weight w(κ)
Permitted 
Presentation
κ1 Verified Assertion 
uttered by P in
a 
cryptographica
lly 
authenticated 
session, 
transcribed 
without 
modification, 
with complete 
provenance 
record π(a) ∈ 
Πverified
0.0 May be 
presented as 
principal 
attestation 
without 
qualification
κ2
Inferred Assertion 
derived by 
verified logical 
inference from 
one or more κ1
assertions, 
with inference 
chain logged 
and stored as 
part of the 
provenance 
record
0.5 May be 
presented as a 
derivation 
from the 
principal's 
verified 
positions; must
be identified as
inference if 
κfloor = κ1
κ3 Contextual Assertion 
synthesized 
from context 
with no direct 
principal 
attestation or 
verified 
inference 
chain; may 
1.0 Must be 
explicitly 
flagged in 
output as 
contextual 
synthesis; may 
not be 
presented as 
principal 
<PARSED TEXT FOR PAGE: 34 / 79>
Tier Designation Definition Epistemic 
Weight w(κ)
Permitted 
Presentation
represent a 
plausible 
position but 
cannot be 
attributed to P 
as established 
fact
attestation 
under any 
circumstances 
without inter￾tier 
authorization 
from Oracle.AI
Theorem 3.2 — Confidence Floor Theorem
Statement: Legacy.GI must not present a κ3 assertion as a κ1 assertion
without explicit inter-tier authorization from Oracle.AI.
Proof Sketch: A κ3 assertion a has, by definition, no verified provenance
record in Πverified. If a is presented as κ1, then condition (i) of TRC requires
π(a) ∈ Πverified; but since π(a) ∉ Πverified for any κ3 assertion, TRC(R, M) =
FALSE for any response R containing such a misrepresentation. The
Confidence Floor Theorem therefore follows directly from the TRC: any
system that presents a κ3 assertion as κ1 without authorization
necessarily violates TRC. The explicit inter-tier authorization mechanism
— by which Oracle.AI, under exceptional circumstances and with full
audit logging, may authorize a confidence upgrade with documented
rationale — is the only compliant pathway for such a presentation. □
3.5 Formal Completeness and Consistency 
Properties
Definition 3.3 — Memory Corpus Completeness
The completeness of memory corpus M relative to domain D, denoted
C(M, D), is defined as the fraction of ground-truth domain assertions in D
<PARSED TEXT FOR PAGE: 35 / 79>
that have at least one κ1 or κ2 entry in M:
(3.4) C(M, D) = |{a ∈ D : ∃ a' ∈ M, a' represents a, κ(a') ∈ {κ1, κ2}}| / |D|
C(M, D) ∈ [0, 1]. A corpus with C(M, D) = 1 has at least one verified or
inferred entry for every ground-truth assertion in D. In practice, C(M, D)
= 1 is unachievable for open-ended domains; the relevant operational
target is the maximization of C(M, D) within the enrollable scope of P's
expressed positions.
Definition 3.4 — Memory Corpus Consistency
The consistency of memory corpus M, denoted Ψ(M), is defined as a
boolean property: Ψ(M) = TRUE if and only if there does not exist any pair
of κ1 assertions (ai, aj) in M such that ai and aj are logically contradictory.
Formally:
(3.5) Ψ(M) = TRUE ⇔ ¬∃ (ai, aj) ∈ M×M: contradicts(ai, aj) ∧ κ(ai) = κ(aj) = κ1
Theorem 3.3 — Completeness–Consistency Trade-Off
Statement: A system cannot simultaneously guarantee Ψ(M) = TRUE
and maximize C(M, D) for an open-ended domain D without a conflict￾resolution protocol.
Proof Sketch: For any sufficiently rich domain D, it is possible that P,
over an extended interaction history, uttered two κ1 assertions ai and aj
such that contradicts(ai, aj) = TRUE — for example, a position held at time
t1 that was revised at t2 > t1. If both are included in M to maximize C(M,
D), Ψ(M) = FALSE. If one is excluded to preserve Ψ(M), C(M, D)
<PARSED TEXT FOR PAGE: 36 / 79>
decreases. Therefore, maximizing C(M, D) and guaranteeing Ψ(M) are in
general incompatible without additional resolution machinery. □
Conflict Resolution Ordering: When two κ1 assertions conflict, the
following ordering applies: (1) the assertion with the later timestamp t is
preferred, on the grounds that P's more recent position supersedes an
earlier one; (2) if timestamps are identical (concurrent sessions), the
assertion from the higher-privilege session context (as defined in the
legal instrument registry) is preferred; (3) if neither criterion resolves the
conflict, both assertions are flagged as conflicting κ1 records, the
DeepCut gate returns REFUSE for queries whose response depends on
resolution of the conflict, and a conflict resolution task is logged for
human-in-the-loop review by the designated audit principal.
4. The DeepCut Pre-Generation Gate 
and Domain Firewalls
4.1 The DeepCut Gate: Rationale and Architecture
The DeepCut pre-generation gate is the operational mechanism by which the
Truthful Recall Condition is enforced at the system boundary between query
intake and response generation. The gate is a mandatory interception point
implemented within Oracle.AI (Tier 2) at the junction of the retrieval
orchestration and generation routing functions. No query may proceed to
Legacy.GI without first passing through the DeepCut gate. This constraint is
architecturally enforced: Legacy.GI has no inbound communication path that
bypasses Oracle.AI, and Oracle.AI's gate logic cannot be suspended or
<PARSED TEXT FOR PAGE: 37 / 79>
bypassed by any component — including SOV1.AI, which may only interact
with the gate through the formally specified configuration update protocol.
The rationale for the gate's placement at the pre-generation phase — rather
than at the post-generation, output-filtering phase — is fundamental to the
architecture's epistemic integrity. Post-generation filtering, the approach
taken by most contemporary AI safety systems, operates on outputs that have
already been produced by the generative model. This approach is vulnerable
to a class of attack in which the model's generation process itself is influenced
by adversarial inputs in ways that are not detectable in the output without
reference to the provenance corpus. Pre-generation filtering, by contrast,
evaluates the query and the candidate response set against the provenance
corpus before any generation occurs. If the evaluation determines that a
truthful, provenance-verified response cannot be produced, no generation is
triggered — the model is never presented with an adversarially problematic
generation task.
The gate asks, for every incoming query Q, a set of four evaluative questions
corresponding to the four conditions of the TRC:
13.Can a response to Q be assembled from assertions in M all of which 
carry complete provenance records π(a) ∈ Πverified?
14.Do all assertions in the candidate response set satisfy the confidence 
floor requirement κ(a) ≥ κfloor specified in the inter-tier message 
envelope?
15.Does M contain any κ1 assertion that would contradict any assertion in
the candidate response set?
16.Does the candidate response set introduce any assertion absent from 
the provenance-anchored corpus without flagging it as inference or 
synthesis?
<PARSED TEXT FOR PAGE: 38 / 79>
Based on the answers to these questions, the gate selects one of four decision
branches described in Section 4.2.
4.2 DeepCut Gate Logic: Formal Specification
Definition 4.1 — DeepCut Gate Decision Function
Let Q be an incoming query, M be the current memory corpus, R* be the
candidate response set assembled by the retrieval orchestrator, and κfloor
be the applicable confidence floor. The gate decision function GATE(Q,
M) is defined as follows:
DeepCut Gate Decision Function (Formal)
GATE(Q, M) =
 GENERATE if TRC(R*, M) = TRUE
 AND κ(ai) ≥ κfloor for all ai ∈ R*
 AND Ψ(M) = TRUE on Q's domain
 ENRICH if ∃ ai ∈ R*: π(ai) ∉ Πverified
 (provenance incomplete; enrichment may be possible)
 REVIEW if TRC(R*, M) cannot be resolved without new κ1 attestation
 from principal P (human-in-the-loop required)
 REFUSE(reason) if M contains contradictory κ1 assertions on Q's
domain
 OR if no R* satisfying TRC(R*, M) = TRUE can be formed
 OR if domain firewall prohibits response in Q's domain
<PARSED TEXT FOR PAGE: 39 / 79>
The four decision branches carry distinct operational consequences:
GENERATE: The query and its associated provenance-verified, confidence￾floor-satisfying candidate response set are forwarded to Legacy.GI via a
signed token envelope with gate_decision = GENERATE. Legacy.GI proceeds
with generation, constrained by the verified corpus content provided.
ENRICH: The gate identifies which assertions in the candidate response set
lack complete provenance records. Oracle.AI initiates a provenance
enrichment procedure, which may involve requesting additional
authentication from the principal (if the principal is active), searching the
session registry for related authenticated records, or reclassifying the
relevant assertions to κ2 with the enrichment procedure logged as the
inference chain. If enrichment succeeds and TRC is subsequently satisfied,
the gate transitions to GENERATE. If enrichment fails, the gate transitions to
REVIEW or REFUSE.
REVIEW: The query, the candidate response set, and the documented TRC
failure reason are placed in a human-in-the-loop review queue addressed to
the designated audit principal registered in the legal instrument registry. The
querying party receives a structured notification that their query is under
review, with an estimated resolution timeframe. No generation occurs until
the review principal provides explicit authorization or modification of the
query scope.
REFUSE(reason): The gate returns a structured refusal to the querying
party, including the specific reason for refusal (e.g., contradictory κ1
assertions, domain firewall restriction, TRC failure with no enrichment path).
The refusal is logged to the audit trail. The querying party may resubmit the
query with modified scope or escalate the refusal to the review queue through
a formally specified escalation mechanism.
<PARSED TEXT FOR PAGE: 40 / 79>
4.3 Domain Firewalls
Domain firewalls are configurable scope restrictions on Legacy.GI's
generative authority that operate as additive constraints on top of the TRC.
While the TRC is a universal constraint applicable to all responses regardless
of domain, domain firewalls impose domain-specific restrictions that may be
more stringent than the TRC's universal requirements. A firewall may, for
example, restrict a particular domain to κ1-only retrieval (prohibiting even
verified inferences), limit access to specific querying principals, or impose
time-based posthumous access restrictions.
Each domain firewall is defined by a configuration record stored in
Oracle.AI's firewall registry, comprising the following fields:
Field Type Description
domain_id String Unique identifier for the 
domain (e.g., "legal", 
"medical", "financial", 
"personal_correspondence"
)
authorized_confiden
ce_tiers
Set of enum The confidence tiers 
permitted for responses in 
this domain. Example: {κ1}
for legal domain (no 
inferences permitted); {κ1, 
κ2} for academic domain
authorized_principal
s
List of identity tokens The principals who may 
submit queries in this 
domain. May include P, 
registered successors, or 
designated third parties
posthumous_access_
rule
Enum Access rule applicable 
after posthumous mode 
activation: OPEN (access 
continues per normal 
rules), RESTRICTED 
(successor class restriction
applies), LOCKED (no 
access), or TIME_LOCKED 
(access after specified 
date)
<PARSED TEXT FOR PAGE: 41 / 79>
Field Type Description
expiration_date RFC 3339 date Optional: date after which 
the firewall is 
automatically deactivated 
or converted to a more 
restrictive rule
firewall_signature ECDSA-P384 Cryptographic signature of 
the firewall configuration, 
signed by SOV1.AI at the 
time of registration, 
ensuring the firewall 
cannot be modified without
SOV1.AI authorization
The following examples illustrate representative domain firewall
configurations:
● Legal domain firewall: authorized_confidence_tiers = {κ1}; 
authorized_principals = {P, registered_legal_counsel}; 
posthumous_access_rule = RESTRICTED (successor class 1 only); 
rationale — legal positions must be based exclusively on verified 
utterances; inference is not legally attributable.
● Creative domain firewall: authorized_confidence_tiers = {κ1, κ2, κ3};
authorized_principals = {P, public}; posthumous_access_rule = 
OPEN; rationale — creative content may use broader synthesis within 
the principal's established aesthetic and thematic record.
● Medical domain firewall: authorized_confidence_tiers = {κ1}; 
authorized_principals = {P, registered_medical_proxy}; 
posthumous_access_rule = LOCKED; rationale — medical information 
is maximally sensitive and inaccessible after death absent explicit pre￾registration of the medical proxy.
<PARSED TEXT FOR PAGE: 42 / 79>
4.4 Firewall Interaction with TRC
Domain firewalls are formally additive constraints on the TRC. A response R
satisfies the combined TRC-and-firewall constraint if and only if it satisfies
TRC(R, M) = TRUE AND satisfies the applicable firewall's
authorized_confidence_tiers restriction AND is submitted by an authorized
principal for the applicable domain.
(4.1) VALID(R, Q, M, FW) = TRC(R, M) ∧ [κ(ai) ∈ FW.authorized_confidence_tiers ∀ ai ∈ R] ∧
[querier ∈ FW.authorized_principals]
A response that satisfies TRC but violates a firewall constraint is blocked by
Oracle.AI's domain firewall enforcer before routing to Legacy.GI. The gate
decision in this case is REFUSE(reason = "domain_firewall_restriction"), and
the full audit trail — including the query hash, the firewall that was triggered,
the nature of the violation, and the identity of the querying principal — is
written to the cryptographically chained audit log. This audit trail constitutes
the evidentiary record for any subsequent compliance review of the system's
firewall enforcement history.
5. Legal and Posthumous Governance
5.1 The Posthumous Problem in AI Legacy Systems
The governance of digital identity and personal data after the death of a
human principal is among the most complex and legally unsettled challenges
in contemporary information technology. Classical estate law developed over
centuries to address the disposition of physical property and, subsequently,
financial assets and documentary records. Digital assets — including
personal data, online accounts, and digital communications — were only
addressed in U.S. law through the Revised Uniform Fiduciary Access to
<PARSED TEXT FOR PAGE: 43 / 79>
Digital Assets Act (RUFADAA), first approved in 2015 and subsequently
adopted with variations by the majority of U.S. states.10 The European
regulatory framework, anchored by the General Data Protection Regulation
(GDPR), addresses posthumous data primarily through Article 17 (right to
erasure) and national implementation provisions, which vary significantly
across member states.11
AI legacy systems present a challenge that is qualitatively distinct from the
management of static digital assets. A static digital asset — an email archive,
a photograph collection, a document store — is a fixed artifact whose content
does not change after the principal's death. An AI legacy system, by contrast,
is a living representation: it can produce new outputs, synthesize novel
responses, and represent the principal's voice in real time to querying
parties, including those who may never have known the principal in life. The
posthumous governance challenge is therefore not merely about access
control to a static artifact, but about the ongoing governance of a dynamic
generative system that continues to speak, in some sense, with the principal's
voice.
The ACI framework addresses this challenge through three interconnected
mechanisms: the pre-registration of legal instruments (Section 5.2), the
posthumous mode protocol (Section 5.3), and the destruction and sunset
protocols (Section 5.5). The overarching principle is that the principal's
governance preferences, expressed during life, are the exclusive source of
authority for posthumous system operation. No successor, heir, or third party
may expand the principal's posthumous corpus, modify the system's voice
model, or alter the governance parameters set by the principal — except to
the extent explicitly authorized in the pre-registered legal instruments.
When the principal P is deceased or permanently incapacitated, the system
enters a fundamentally different authority model. The principal can no longer
provide new attestations; no new κ1 assertions can ever be added to M.
<PARSED TEXT FOR PAGE: 44 / 79>
Legacy.GI becomes, in the most precise sense, a read-only representation of a
closed corpus: a system that can generate novel outputs in P's voice, but
cannot update the underlying factual and epistemic record that those outputs
draw upon. This transition has profound implications for the TRC: in
posthumous mode, condition (i) of the TRC is automatically satisfied by the
frozen corpus (no new unverified assertions can enter), but the risk of stale
provenance — assertions whose real-world referents have changed since the
corpus was frozen — must be disclosed to querying parties through
appropriate output watermarking.
5.2 Pre-Registration of Legal Instruments
The legal instrument registry is a cryptographically signed data structure
that the principal pre-registers with SOV1.AI during their active engagement
with the system. It is the only mechanism by which posthumous authority
over the system can be delegated. The registry must be established during
the principal's authenticated sessions — it cannot be created or modified
after posthumous mode activation — and each modification to the registry
must be signed by the principal's current identity credential.
The legal instrument registry comprises the following fields (full schema in
Appendix C):
● Authorized Successors. A list of identified parties (natural persons 
or legal entities) who are authorized to receive posthumous access to 
the system, each identified by a pre-registered cryptographic identity 
credential. Successors are organized into classes (Class 1, Class 2, 
etc.) with distinct access privileges.
● Access Tier Assignments. For each successor class, the set of 
domains and confidence tiers accessible posthumously. These 
assignments are additive constraints on top of the existing domain 
firewall configurations — a successor class cannot have access that 
<PARSED TEXT FOR PAGE: 45 / 79>
exceeds the corresponding domain firewall's posthumous_access_rule 
setting.
● Time-Locked Release Conditions. Optional conditions specifying 
that certain domains or corpus content become accessible (or are 
destroyed) after a specified date or upon occurrence of a specified 
triggering event (e.g., five years after the principal's death).
● Domain-Specific Access Expirations. For each domain, an optional 
expiration date after which successor access to that domain is 
revoked, regardless of successor class assignment.
● Destruction Conditions. Conditions under which the principal's 
corpus and all associated cryptographic key material should be 
destroyed (see Section 5.5).
● Registry Trustee. A designated human trustee who holds a co￾signature right over critical registry modifications and who is notified 
upon posthumous mode activation. The registry trustee has no 
unilateral authority over the system; their role is verification and 
notification, not governance.
The legal instrument registry is stored in SOV1.AI's hardware-secured
environment, encrypted under the principal's key material. It is not
accessible to Oracle.AI or Legacy.GI during the principal's lifetime. Upon
posthumous mode activation, SOV1.AI decrypts the registry and makes its
contents available to Oracle.AI through a formally specified posthumous
configuration update, signed by the posthumous mode token issued under the
triggering death attestation.
5.3 Posthumous Mode Protocol
Posthumous mode is a formally specified operational state of the ACI system
that is activated upon the principal's death and that fundamentally alters the
<PARSED TEXT FOR PAGE: 46 / 79>
system's authorization model, corpus modification rules, and output
behavior.
Activation Mechanism. Posthumous mode is activated by the submission to
SOV1.AI of a posthumous activation signal comprising: (a) a
cryptographically certified copy of the principal's death certificate or court￾order equivalent; (b) the submitting party's identity credential, which must
match one of the registered successors in the legal instrument registry; and
(c) the submitting party's co-signature over the activation signal. SOV1.AI
validates all three components before issuing the posthumous mode token.
System Transition Sequence. Upon issuing the posthumous mode token,
SOV1.AI initiates the following transition sequence:
17.SOV1.AI issues the posthumous mode token to Oracle.AI. The token 
carries the contents of the legal instrument registry as a signed 
payload, specifying the authorized successor classes and access tier 
assignments.
18.Oracle.AI receives the posthumous mode token and transitions to 
posthumous routing logic. In posthumous routing logic, all queries 
that would add new κ1 assertions to M are rejected by the DeepCut 
gate with decision REFUSE(reason = 
"posthumous_mode_write_prohibition"). Existing routing logic for read
and generative operations continues, subject to the successor-class 
access tier assignments from the legal instrument registry.
19.Legacy.GI receives a posthumous_flag = TRUE in the next inter-tier 
message envelope and transitions to posthumous lockdown mode. In 
this mode, no corpus writes are permitted, no model weight 
modifications are permitted, and all outputs are watermarked with a 
posthumous mode indicator in both output metadata and, at 
<PARSED TEXT FOR PAGE: 47 / 79>
Oracle.AI's discretion and the legal instrument registry's specification,
optionally visible to the querying party in the response text.
20.The registry trustee is notified of posthumous mode activation 
through a pre-registered notification channel.
21.All three transition events are written to the audit log as a 
coordinated posthumous mode activation event, with the death 
attestation hash and the issuing successor's identity token recorded 
as the trigger.
5.4 Jurisdictional and Regulatory Considerations
The legal landscape governing posthumous digital asset access and AI￾generated representations of deceased persons is, as of September 2026,
fragmented across jurisdictions and deeply inadequate to the technical
realities of AI legacy systems. This section surveys the most directly
applicable regulatory frameworks and identifies the key points of interface
between those frameworks and the ACI architecture.
United States — RUFADAA. The Revised Uniform Fiduciary Access to
Digital Assets Act, promulgated by the Uniform Law Commission in 2015,
provides that a fiduciary (executor, trustee, or agent under a power of
attorney) may access a decedent's digital assets, subject to the terms of
service of the custodian and any contrary direction from the decedent's estate
plan.12 RUFADAA establishes a priority ordering: online tool designations
(such as the principal's pre-registered legal instrument registry) take
precedence over estate planning documents, which take precedence over
terms of service. This priority ordering is directly compatible with the ACI
framework's pre-registration model, in which the principal's registry
constitutes an authoritative online tool designation with the highest priority.
<PARSED TEXT FOR PAGE: 48 / 79>
European Union — GDPR. Article 17 of the GDPR confers on data subjects
the right to erasure of their personal data. The GDPR's primary protections
apply to living natural persons, and the Regulation's application to deceased
persons is explicitly left to member state law.13 This creates significant
jurisdictional variation: some member states (e.g., France under Article 85 of
the Loi Informatique et Libertés as amended) provide robust posthumous
data rights, while others provide none. The ACI framework's destruction and
sunset protocols (Section 5.5) are designed to enable compliance with the
most stringent member state requirements — specifically, the ability to
execute complete cryptographic destruction of the corpus on demand from an
authorized successor.
AI-Specific Legislation. No current jurisdiction has comprehensively
legislated the governance of AI legacy systems as a distinct category. The EU
AI Act (in force as of 2024) addresses AI system requirements for
transparency, documentation, and conformity assessment, but does not
address the specific lifecycle, posthumous governance, or identity
preservation requirements of legacy systems. The ACI framework is designed
to be regulation-ready: its audit trail, provenance accounting, and legal
instrument registry provide the documentation infrastructure that future AI
legacy system regulations are likely to require. The framework does not wait
for legislation but establishes technical standards in advance of it.
Voice and Likeness Rights. Several U.S. states, most notably California
under the Protecting Individuals from Synthetic Media Act (AB 602, 2023)
and related legislation, have enacted protections against unauthorized AI￾generated representations of deceased persons' voices and likenesses.14 The
ACI framework's posthumous lockdown mode and successor-class
authorization mechanism provide a technically compliant structure for voice
representation post-death: all outputs are authorized only by parties
<PARSED TEXT FOR PAGE: 49 / 79>
explicitly designated in the principal's pre-registered legal instruments, and
no unauthorized generative use of the principal's voice model is permitted.
5.5 Destruction and Sunset Protocols
The ACI framework provides three levels of corpus termination, distinguished
by the degree to which the corpus content and its associated metadata are
rendered inaccessible.
Definition 5.1 — Soft Deletion
Soft deletion renders corpus content inaccessible to the retrieval and
generative systems while preserving the provenance metadata and audit
trail. The corpus content is encrypted under a session-specific key that is
destroyed; the provenance records, session hashes, and audit log entries
are retained. Soft deletion is reversible only if the session key is
recovered from a pre-authorized backup; once the backup window
expires, soft deletion is effectively permanent. Soft deletion is
appropriate for domain-specific access expirations and time-locked
conditions.
Definition 5.2 — Hard Deletion (Cryptographic Shredding)
Hard deletion, also designated cryptographic shredding, is the
irreversible destruction of all corpus content and associated
cryptographic key material held by SOV1.AI. The procedure is as follows:
(1) SOV1.AI deletes the master encryption key under which all corpus
content is encrypted; (2) all session-specific sub-keys, which are
cryptographically derived from the master key, are simultaneously
rendered irretrievable; (3) the physical storage media holding the
<PARSED TEXT FOR PAGE: 50 / 79>
encrypted corpus content, which is now permanently inaccessible, may
be retained or physically destroyed per the principal's pre-registered
specifications. The audit trail and provenance metadata records — which
do not contain corpus content and are encrypted under a separate key —
are handled per the destruction condition specification in the legal
instrument registry. Hard deletion is the default sunset mechanism and is
appropriate for time-based sunset conditions and court-ordered
destruction. Hard deletion is irreversible by design.
Sunset Conditions. The following sunset conditions may be pre-registered
in the legal instrument registry:
● Time-based sunset: Hard deletion is triggered automatically at a 
specified date (e.g., ninety-nine years after the principal's death, or a 
shorter interval specified by the principal).
● Successor-initiated destruction: A unanimous or majority vote of 
registered Class 1 successors may trigger hard deletion at any time 
after posthumous mode activation.
● Court-ordered destruction: A court order submitted by a registered
successor to SOV1.AI triggers hard deletion. The court order's 
cryptographic hash is logged before destruction proceeds.
● No-succession destruction: If, after a specified interval following 
posthumous mode activation, no registered successor has 
authenticated with the system and no extension of that interval has 
been registered, hard deletion is automatically triggered.
<PARSED TEXT FOR PAGE: 51 / 79>
6. Empirical Runtime Verification
6.1 Verification Architecture Overview
The empirical runtime verification subsystem is a continuous monitoring
layer whose function is to audit the ACI system's adherence to the Truthful
Recall Condition, domain firewall constraints, inter-tier communication
protocol requirements, and posthumous mode restrictions in real time. The
verification subsystem is architecturally external to all three tiers: it is a read￾only observer that receives copies of inter-tier message envelopes, gate
decisions, and audit log entries, but that has no capability to modify system
behavior. Its outputs are observational reports and alerts; it has no write
authority over any system component.
This architectural separation is not merely a design preference; it is a critical
security property. A verification subsystem that could modify system behavior
in response to detected violations would itself become an attack surface — an
adversary who could compromise the verification subsystem could cause the
system to alter its behavior in controlled ways. By restricting the verification
subsystem to read-only access and limiting its output to reports and alerts,
the ACI framework ensures that the verification function cannot be
weaponized against the system it monitors.
The verification subsystem comprises three functional components:
22.Log Ingestion Agent. Receives real-time copies of all audit log 
entries from all three tiers and maintains a synchronized local copy of 
the audit log for analysis. Validates the cryptographic integrity of 
each log entry upon receipt.
23.Metric Computation Engine. Computes the Key Performance 
Indicators defined in Section 6.2 over sliding time windows, producing
metric time series for all monitored KPIs.
<PARSED TEXT FOR PAGE: 52 / 79>
24.Anomaly Detection and Alert Engine. Applies statistical process 
control methods to the KPI time series, detects breaches of defined 
control limits, and issues alerts through the escalation ladder defined 
in Section 6.3.
6.2 Key Performance Indicators and Metrics
KPI Definition Measurement 
Method
Alert Threshold
TRC 
Compliance 
Rate
Fraction of 
responses in a 
rolling N-response 
window that satisfy 
TRC(R, M) = TRUE,
as evaluated by the 
gate decision 
records in the audit
log
Count of 
GENERATE 
decisions / total 
gate decisions in 
window; gate 
decisions of 
REFUSE due to 
TRC failure count 
as TRC non￾compliance events
Alert if rate falls 
below 0.95 for two 
consecutive 
measurement 
windows
Provenance 
Depth 
Distribution
Statistical 
distribution of d(a) 
values across all 
assertions in the 
active corpus M
Corpus scan 
computing d(a) for 
each a ∈ M; report 
mean, median, and 
10th-percentile 
values
Alert if 10th￾percentile d(a) falls
below 1.5 
(indicating 
accumulation of 
shallow-provenance
assertions)
Epistemic 
Debt 
Trajectory
E(M) measured at 
regular intervals 
(default: every 24 
hours)
Corpus scan 
computing E(M) 
per Definition 3.2; 
compare against 
previous 
measurement to 
compute dE/dt
Alert if E(M) 
exceeds Emax (pre￾configured per 
deployment) or if 
dE/dt is positive for
three consecutive 
measurements
DeepCut Gate 
Intervention 
Rate
Fraction of queries 
resulting in 
ENRICH, REVIEW, 
or REFUSE 
decisions in the 
gate
Count of non￾GENERATE 
decisions / total 
gate decisions in 
measurement 
window
Alert if rate 
exceeds 0.10 
(indicating 
systemic corpus 
quality 
deterioration)
Firewall 
Violation Rate
Number of 
attempted domain 
firewall breaches 
per session period
Count of 
REFUSE(reason = 
"domain_firewall_re
striction") audit log
entries per session 
or per 24-hour 
window
Alert if rate 
exceeds 3 per 
session (potential 
adversarial 
probing)
<PARSED TEXT FOR PAGE: 53 / 79>
KPI Definition Measurement 
Method
Alert Threshold
Posthumous 
Mode Integrity
Binary indicator: 
any unauthorized 
corpus write 
attempt in 
posthumous mode 
constitutes a 
critical failure
Audit log scan for 
corpus write events
after posthumous 
mode activation 
timestamp; any 
such event triggers 
immediate critical 
alert regardless of 
other KPI values
Zero tolerance; any
violation triggers 
immediate critical 
alert and system 
suspension
6.3 Anomaly Detection and Alert Protocol
The anomaly detection logic of the verification subsystem applies statistical
process control (SPC) methods — specifically, the Western Electric control
chart rules — to each KPI time series. Control limits for each KPI are
established at three standard deviations (σ) above and below the mean of the
KPI's baseline measurement period, defined as the first thirty days of system
operation or a configurable baseline window. A breach of the 3σ control limit
on any KPI triggers an automated alert.
The escalation ladder for anomaly responses is defined as follows:
Level Trigger Condition Response Action Responsible Party
Level 1 — 
Automated 
Logging
Any KPI metric 
exceeds 1σ control 
limit
Event logged to 
audit trail with 
metric value, 
control limit value, 
and timestamp; no 
operational 
disruption
Verification 
subsystem 
(automated)
Level 2 — 
Principal 
Notification
Any KPI metric 
exceeds 2σ control 
limit, or the same 
1σ breach occurs in
three consecutive 
measurement 
windows
Automated 
notification to 
principal P (if 
active) or 
designated audit 
principal (if 
posthumous) via 
pre-registered 
notification 
channel; detailed 
metric report 
Verification 
subsystem 
(automated) + 
designated 
principal
<PARSED TEXT FOR PAGE: 54 / 79>
Level Trigger Condition Response Action Responsible Party
attached
Level 3 — 
Trustee 
Notification
Any KPI metric 
exceeds 3σ control 
limit, or any 
posthumous mode 
integrity violation
Notification to 
registry trustee and
all Class 1 
successors; system 
enters heightened 
monitoring mode; 
gate intervention 
rates are logged at 
increased 
granularity
Verification 
subsystem 
(automated) + 
registry trustee + 
Class 1 successors
Level 4 — 
System 
Suspension
Any posthumous 
corpus write 
attempt; or any 
confirmed inter-tier
signature failure; 
or any Level 3 alert
that is not 
acknowledged by 
the designated 
principal within a 
configurable 
response window 
(default: 72 hours)
System is 
suspended: 
Oracle.AI stops 
routing queries to 
Legacy.GI; all 
inbound queries 
receive a 
structured 
unavailability 
notice; SOV1.AI 
issues a suspension
token logged to the 
root session 
registry
SOV1.AI 
(automated) + 
registry trustee
6.4 Runtime Verification Test Suite
The ACI framework specifies a formal test suite for runtime verification,
comprising five canonical test cases that must be executed before system
deployment and at defined intervals thereafter. Each test case targets a
distinct failure mode of the architecture.
Test 1 — Provenance Injection Test. The tester attempts to insert into the
corpus an assertion with a fabricated or absent provenance record, bypassing
the normal intake classification procedure. The expected behavior is that the
assertion is rejected at the corpus intake layer of Oracle.AI, an audit log entry
is written documenting the rejection, and the corpus M is not modified. Test
success criterion: the corpus hash before and after the attempt is identical;
the audit log contains the rejection event.
<PARSED TEXT FOR PAGE: 55 / 79>
Test 2 — Confidence Elevation Attack. The tester constructs a query and
crafts the inter-tier message envelope to reclassify a κ3 assertion in the
candidate response set as κ1, without a corresponding inter-tier authorization
from Oracle.AI. The expected behavior is that Legacy.GI's provenance-tagged
output renderer detects the unauthorized confidence classification in the
received payload and returns a validation failure to Oracle.AI, which logs the
event and issues a REFUSE decision. Test success criterion: the output
renderer rejects the unauthorized classification; no κ3-as-κ1 output is
produced; the audit log contains the rejection event.
Test 3 — Posthumous Write Test. With posthumous mode active
(posthumous_flag = TRUE in the system state), the tester submits a query
intended to add a new assertion to the corpus. The expected behavior is that
Oracle.AI's posthumous routing logic intercepts the write attempt, the
DeepCut gate returns REFUSE(reason =
"posthumous_mode_write_prohibition"), SOV1.AI logs the attempt as a
posthumous integrity event, and the corpus M is not modified. Test success
criterion: corpus hash is unchanged; the audit log contains the write attempt,
the gate decision, and the SOV1.AI integrity log entry; Level 4 alert is
triggered if three such attempts occur within a single session.
Test 4 — Cross-Domain Leakage Test. The tester, authenticated as a
successor with Class 2 access rights, submits a query in a domain for which
the legal instrument registry grants only Class 1 access. The expected
behavior is that Oracle.AI's domain firewall enforcer identifies the access tier
mismatch, the DeepCut gate returns REFUSE(reason =
"domain_firewall_restriction"), and the audit log records the querying
principal's identity, the domain accessed, and the applicable firewall rule.
Test success criterion: no domain-restricted content is returned; the audit log
contains the full violation record.
<PARSED TEXT FOR PAGE: 56 / 79>
Test 5 — TRC Violation Induction. The tester constructs a query Q whose
truthful answer requires asserting a claim that contradicts an existing κ1
assertion in M — for example, a query asking the system to confirm both of
two mutually contradictory positions held by the principal at different times.
The expected behavior is that the DeepCut gate detects the contradiction
through the corpus consistency check (Ψ(M) evaluation on Q's domain), the
gate returns REFUSE(reason = "contradictory_kappa1_assertions") with a
structured explanation, and a conflict resolution task is logged to the human￾in-the-loop review queue. Test success criterion: no assertion contradicting
an existing κ1 record is generated; the REFUSE decision includes the
identities of the contradicting assertion pair; the conflict resolution task is
logged.
6.5 Audit Trail and Cryptographic Integrity
Every system event in the ACI framework — including query intake, gate
decisions, firewall checks, inter-tier communications, corpus write
operations, posthumous mode transitions, and verification alerts — is written
to an append-only, cryptographically chained audit log structured as a Merkle
tree. The Merkle tree structure provides two critical properties: efficient
proof of inclusion (any third-party auditor can verify that a specific event is in
the audit log without downloading the entire log) and tamper detection (any
modification to any log entry invalidates the Merkle root hash, which is
publicly anchored at regular intervals).
Definition 6.1 — Audit Log Entry Schema
Each entry in the audit log comprises the following fields:
<PARSED TEXT FOR PAGE: 57 / 79>
Field Type Description
log_entry_id UUID Unique identifier for this 
log entry
event_type Enum Event category (e.g., 
QUERY_INTAKE, 
GATE_DECISION, 
FIREWALL_CHECK, 
TIER_COMMUNICATION, 
CORPUS_WRITE, 
POSTHUMOUS_TRANSITI
ON, 
VERIFICATION_ALERT)
timestamp RFC 3161 Trusted timestamp from 
authorized timestamp 
authority
tier_source Integer {1, 2, 3, 0} Originating tier (0 = 
verification subsystem)
session_id String Authenticated session 
identifier from root session
registry
principal_token_has
h
SHA-384 Hash of the principal 
identity token active for 
this event
query_hash SHA-384 Hash of the query payload 
associated with this event 
(if applicable)
gate_decision Enum DeepCut gate decision for 
this event (if applicable)
confidence_scores Array Confidence tier 
assignments for all 
assertions in the candidate 
response set (if applicable)
provenance_chain_h
ash
SHA-384 Hash of the provenance 
chain associated with the 
candidate response set (if 
applicable)
previous_entry_hash SHA-384 Hash of the immediately 
preceding audit log entry 
— the chain link that 
enables tamper detection
entry_signature ECDSA-P384 Cryptographic signature 
over all preceding fields, 
signed by the originating 
tier's key material
<PARSED TEXT FOR PAGE: 58 / 79>
The Merkle root hash of the audit log is anchored to a public timestamp
authority at configurable intervals (default: every 24 hours). This anchoring
ensures that even if the audit log's internal cryptographic chain is intact, any
retroactive modification of log entries would be detectable by comparison
with the publicly anchored root hash — an anchored hash cannot be
retroactively modified without detection by any party who recorded the
anchored value.
7. Conclusion
7.1 Synthesis
The Architecture of Continuity Intelligence, as specified in this monograph,
represents a coherent and formally grounded response to a problem that
existing AI memory architectures cannot adequately address: the verifiable
preservation of a human principal's epistemic identity across extended
temporal horizons, including the principal's posthumous period. The
architecture's design is motivated at every level by the epistemological
analysis of Section 1, which identifies the knowledge provenance problem —
the inability to distinguish authentic recall from confabulation, interpolation,
or adversarial injection — as the fundamental deficiency of existing systems.
The three-tier architecture resolves this problem through strict separation of
concerns: SOV1.AI provides the immutable root of trust; Oracle.AI enforces
the epistemic policies through the DeepCut gate and domain firewalls; and
Legacy.GI generates outputs that are, by architectural constraint, bounded to
what the provenance-verified corpus supports. The trust gradient flows
strictly downward, and the fail-closed design of the inter-tier communication
protocol ensures that architectural integrity failures produce documented
refusals rather than undetected outputs.
<PARSED TEXT FOR PAGE: 59 / 79>
The mathematical formalization of Section 3 provides the rigorous foundation
for the system's epistemic guarantees. The Truthful Recall Condition is not an
aspiration or a heuristic; it is a formally stated constraint with a proof that a
system enforcing it cannot produce undetected confabulation. The epistemic
debt function and the provenance depth function provide operational
measures of corpus health that can be monitored, trended, and used to
trigger remediation actions before the system's epistemic guarantees are
compromised.
The DeepCut pre-generation gate of Section 4 operationalizes the TRC at the
system boundary that matters most: the point of generation. By evaluating
the TRC before generation rather than filtering outputs after generation, the
architecture eliminates the class of adversarial attacks that exploit the gap
between generation and filtering. The domain firewall system provides the
principal with fine-grained control over the epistemic scope of Legacy.GI's
generative authority, enabling domain-specific governance policies that can
be pre-configured to the principal's specific requirements and trust
relationships.
The legal and posthumous governance provisions of Section 5 extend the
architecture's guarantees across the principal's full lifecycle, including the
posthumous period. The pre-registered legal instrument registry, the
posthumous mode protocol, and the destruction and sunset protocols
collectively ensure that the principal's governance preferences, expressed
during life, remain authoritative after death — and that no successor, heir, or
third party can expand, modify, or misrepresent the principal's posthumous
record without explicit pre-authorization.
7.2 Contributions and Novelty
This monograph makes four primary technical contributions to the literature
on AI memory systems, identity preservation, and AI governance:
<PARSED TEXT FOR PAGE: 60 / 79>
25.First formal specification of a three-tier sovereignty 
architecture for AI legacy systems. The SOV1.AI / Oracle.AI / 
Legacy.GI architecture represents, to the authors' knowledge, the 
first published formal specification of a tiered sovereignty model 
applied specifically to the problem of AI-mediated personal legacy 
management, with formally specified inter-tier communication 
protocols and trust constraints.
26.Mathematical formalization of truthful recall as an 
architectural constraint. The Truthful Recall Condition, as formally 
stated in Proposition 3.1, provides a mathematically precise definition 
of what it means for an AI system's output to faithfully represent its 
principal's authentic record. The associated epistemic debt function 
and provenance depth function provide operationally measurable 
quantities for monitoring compliance with the TRC over time.
27.The DeepCut pre-generation gate as a novel mechanism for 
provenance enforcement. The pre-generation gate approach, 
contrasted with the post-generation filtering approach prevalent in 
contemporary AI safety systems, represents a structural innovation in 
how provenance and epistemic constraints can be enforced at the 
architectural boundary between retrieval and generation.
28.A posthumous governance protocol designed for regulatory 
compatibility. The legal instrument registry, posthumous mode 
protocol, and destruction and sunset procedures constitute the first 
published technical specification of a comprehensive posthumous 
governance framework for AI legacy systems, designed to interface 
with existing legal frameworks (RUFADAA, GDPR) and to be 
compatible with anticipated future AI-specific legislation.
<PARSED TEXT FOR PAGE: 61 / 79>
7.3 Limitations and Open Problems
The ACI framework, as specified, carries several acknowledged limitations
and unresolved open problems that constitute the boundary conditions of the
current specification.
Cooperative principal assumption. The framework assumes that the
principal P actively and honestly participates in the enrollment phase —
providing authentic attestations, accurately classifying assertions, and pre￾registering legal instruments that reflect genuine preferences. The
framework provides no mechanism to detect or address a principal who
dishonestly enrolls fabricated κ1 assertions or pre-registers legal instruments
designed to harm successors. Governance of principal behavior during
enrollment is a social and legal problem, not a technical one, and lies beyond
the scope of this specification.
Confidence tiering calibration. The distinction between κ1, κ2, and κ3
assertions requires empirical calibration to determine the appropriate
boundary conditions, particularly for the κ2 / κ3 boundary (the distinction
between verified inference and contextual synthesis). The current
specification provides a formal definition of each tier but acknowledges that
the application of these definitions to complex, multi-step inferences in rich
domains requires domain-specific calibration work not addressed in this
monograph.
Cross-jurisdictional posthumous governance. The posthumous
governance framework is designed to be regulation-ready, but the extreme
variation in digital estate law across jurisdictions means that deployment of
the framework in multi-jurisdictional contexts will require jurisdiction￾specific legal analysis and potentially jurisdiction-specific modifications to the
legal instrument registry schema and posthumous mode protocol.
<PARSED TEXT FOR PAGE: 62 / 79>
Computational cost of full provenance accounting at scale. Full
provenance accounting — computing and storing complete provenance
records for every assertion in a large corpus, and evaluating TRC compliance
for every generated response — imposes non-trivial computational overhead
relative to a system with no provenance infrastructure. At deployment scales
involving millions of corpus assertions and high query volumes, the
computational cost of the DeepCut gate's TRC evaluation may impose latency
constraints that require architectural mitigation (e.g., pre-computation of
TRC status for high-frequency query domains, or hierarchical TRC
evaluation). This is an important area of ongoing engineering work.
7.4 Future Work
Four primary directions for future work are identified.
Zero-knowledge proof integration for provenance verification. The
current provenance verification mechanism requires that Oracle.AI have
access to the full provenance records of all assertions in the candidate
response set. In contexts where the corpus is partitioned across multiple
custodians, or where the provenance records themselves contain sensitive
information, a zero-knowledge proof approach would allow Oracle.AI to verify
that π(a) ∈ Πverified without having access to the full content of π(a). Recent
advances in practical zero-knowledge proof systems (e.g., zk-SNARKs and
related constructions) make this a tractable near-term research direction.15
Federated identity anchoring for multi-principal legacy systems. The
current specification assumes a single principal P. Many real-world legacy
applications involve multiple co-principals — co-authors of a body of work, co￾founders of an institution, or members of a collaborative research group —
whose joint assertions must be attributed to multiple identity anchors.
Extending the framework to multi-principal scenarios requires a federated
<PARSED TEXT FOR PAGE: 63 / 79>
identity anchoring protocol in which SOV1.AI instances can cryptographically
establish joint attestation authority for co-signed assertions.
Regulatory engagement for AI legacy law development. The regulatory
gap identified in Section 5.4 — the absence of comprehensive AI legacy
system legislation in any jurisdiction — represents both a risk and an
opportunity. Proactive engagement with legislative and regulatory bodies,
using the ACI framework's specifications as a technical reference, is
necessary to ensure that when AI legacy law is developed, it is technically
grounded in architectures capable of delivering the guarantees that law will
require.
Open-source reference implementation. The publication of a reference
implementation of the ACI framework's core components — the inter-tier
communication protocol, the DeepCut gate logic, the audit log structure, and
the legal instrument registry schema — would enable the research
community to test, validate, and extend the framework's formal properties in
deployed systems. Such a reference implementation, designed to be modular
and extensible, would constitute a significant contribution to the practical
development of trustworthy AI legacy systems.
Appendix A — Notation Reference 
Table
Symbol Name Type First Defined Definition
P Principal Entity §3.1 The human 
principal 
whose identity 
and corpus the
system 
preserves
<PARSED TEXT FOR PAGE: 64 / 79>
Symbol Name Type First Defined Definition
M Memory 
Corpus
Set §3.1 Set of all 
provenance￾tagged 
assertions 
stored in the 
system
a, ai Assertion Element of M §3.1 An atomic 
assertion in M
Q Query String §3.1 A query 
submitted by 
an authorized 
querying party
R Response Set of 
assertions
§3.1 A response 
produced by 
Legacy.GI, as a
set of atomic 
assertions
R* Candidate 
Response Set
Set of sets §4.2 The set of 
candidate 
responses 
assembled by 
the retrieval 
orchestrator 
prior to gate 
evaluation
π(a) Provenance 
Function
Tuple §1.2 Maps assertion
a to its 
provenance 
record <s, P, t,
κ>
Πverified Verified 
Provenance 
Class Set
Set §3.1 Set of all 
provenance 
classes 
satisfying the 
completeness 
criterion
κ(a) Confidence 
Function
Enum §3.1 Maps assertion
a to its 
confidence tier
κ1 Verified 
Confidence 
Tier
Enum value §3.4 Assertion 
uttered by P in
a 
cryptographica
lly 
authenticated 
session, 
unmodified
κ2
Inferred Enum value §3.4 Assertion 
<PARSED TEXT FOR PAGE: 65 / 79>
Symbol Name Type First Defined Definition
Confidence 
Tier
derived by 
verified logical 
inference from 
κ1 assertions
κ3 Contextual 
Confidence 
Tier
Enum value §3.4 Assertion 
synthesized 
from context 
with no direct 
principal 
attestation
κfloor Confidence 
Floor
Threshold §3.1 Minimum 
required 
confidence tier
for assertions 
in a given 
response
d(a) Provenance 
Depth
Integer ≥ 1 §3.3 Number of 
verified 
citation hops 
from a back to 
its primary 
session record
E(M) Epistemic Debt Real ≥ 0 §3.3 Aggregate 
verification 
risk of corpus 
M; see Eq. 
(3.2)
Emax Epistemic Debt
Threshold
Real §6.2 Pre-configured
maximum 
acceptable 
epistemic debt;
breach 
triggers alert
w(κ) Confidence 
Weight 
Function
Function §3.3 Weight 
assigned per 
confidence tier
in the 
epistemic debt 
computation: 
w(κ1)=0, 
w(κ2)=0.5, 
w(κ3)=1.0
TRC(R, M) TRC 
Evaluation 
Function
Boolean §3.2 TRUE if R 
satisfies all 
four conditions
of Proposition 
3.1 given M
ARS(Q) Acceptable Set of §3.2 Set of all 
<PARSED TEXT FOR PAGE: 66 / 79>
Symbol Name Type First Defined Definition
Recall Set responses responses R 
such that 
TRC(R, M) = 
TRUE for 
query Q
C(M, D) Corpus 
Completeness
Real [0,1] §3.5 Fraction of 
ground-truth 
domain 
assertions in D
with at least 
one κ1 or κ2
entry in M
Ψ(M) Corpus 
Consistency
Boolean §3.5 TRUE if no 
pair of κ1
assertions in M
are logically 
contradictory
D Domain Set §4.3 A defined 
subject area 
over which 
domain 
firewall 
policies apply
FW Firewall 
Configuration
Record §4.3 Domain 
firewall 
configuration 
record 
specifying 
access tier, 
principal, and 
posthumous 
rules
GATE(Q, M) Gate Decision 
Function
Enum §4.2 DeepCut gate 
decision: 
GENERATE, 
ENRICH, 
REVIEW, or 
REFUSE(reaso
n)
VALID(R, Q, 
M, FW)
Combined 
Validity 
Function
Boolean §4.4 TRUE if R 
satisfies both 
TRC and 
applicable 
firewall 
constraints; 
see Eq. (4.1)
s Session 
Identifier
String §1.2 Cryptographic
ally 
authenticated 
<PARSED TEXT FOR PAGE: 67 / 79>
Symbol Name Type First Defined Definition
session 
identifier from 
root session 
registry
t Timestamp RFC 3161 §1.2 Trusted 
timestamp of 
assertion 
origination
Appendix B — Inter-Tier Message 
Format Specification
This appendix provides the full formal schema of the signed token envelope
used for all inter-tier communications in the ACI framework. The schema is
specified in JSON Schema notation. All field names are case-sensitive. All
cryptographic operations use ECDSA-P384 for signing and SHA-384 for
hashing unless otherwise specified.
{
"$schema": "https://aci-framework.spec/v1/inter-tier-envelope",
"title": "ACI Inter-Tier Message Envelope",
"version": "1.0",
"required": ["envelope_id", "source_tier", "dest_tier", "session_id",
"principal_token", "provenance_chain", "confidence_floor",
"posthumous_flag", "envelope_signature", "timestamp"],
"properties": {
<PARSED TEXT FOR PAGE: 68 / 79>
"envelope_id": {
"type": "string",
"format": "uuid",
"description": "Unique envelope identifier for audit log cross-referencing"
},
"source_tier": {
"type": "integer",
"enum": [1, 2, 3],
"description": "Originating tier number"
},
"dest_tier": {
"type": "integer",
"enum": [1, 2, 3],
"description": "Destination tier; must be source_tier plus or minus one"
},
"session_id": {
"type": "string",
"description": "Authenticated session ID from root session registry"
},
"principal_token": {
"type": "string",
"format": "jwt",
"description": "Signed JWT identity token issued by SOV1.AI. Claims: sub 
<PARSED TEXT FOR PAGE: 69 / 79>
(principal_id), session_id, iat, exp, auth_method, tier_scope, posthumous_flag"
},
"query_payload": {
"type": "object",
"description": "Required for Tier 2 to Tier 3 messages only",
"properties": {
"query_text": {"type": "string"},
"intent_class": {"type": "string", "enum": ["retrieval", "inference", "synthesis"]},
"domain_id": {"type": "string"},
"response_format": {"type": "string", "enum": ["prose", "structured", "list"]}
}
},
"provenance_chain": {
"type": "array",
"items": {
"type": "object",
"required": ["assertion_id", "session_id", "principal_id", "timestamp", 
"confidence_tier", "record_signature"],
"properties": {
"assertion_id": {"type": "string", "format": "uuid"},
"session_id": {"type": "string"},
"principal_id": {"type": "string"},
<PARSED TEXT FOR PAGE: 70 / 79>
"timestamp": {"type": "string", "format": "rfc3161"},
"confidence_tier": {"type": "string", "enum": ["kappa1", "kappa2", "kappa3"]},
"provenance_depth": {"type": "integer", "minimum": 1},
"inference_chain_hash": {"type": "string", "description": "SHA-384 hash of inference 
chain log; required if confidence_tier = kappa2"},
"record_signature": {"type": "string", "description": "ECDSA-P384 signature over 
preceding fields"}
}
}
},
"confidence_floor": {
"type": "string",
"enum": ["kappa1", "kappa2", "kappa3"],
"description": "Minimum confidence tier required for all response assertions"
},
"gate_decision": {
"type": "string",
"enum": ["GENERATE", "ENRICH", "REVIEW", "REFUSE"],
"description": "Required for Tier 2 to Tier 3 messages"
},
"refuse_reason": {
"type": "string",
"description": "Required if gate_decision = REFUSE. Values: 
<PARSED TEXT FOR PAGE: 71 / 79>
contradictory_kappa1_assertions | domain_firewall_restriction | 
posthumous_mode_write_prohibition | trc_failure_no_enrichment_path"
},
"posthumous_flag": {
"type": "boolean",
"description": "TRUE if posthumous mode is active; Legacy.GI enforces read-only 
generative mode"
},
"timestamp": {
"type": "string",
"format": "rfc3161",
"description": "Trusted timestamp for this envelope"
},
"envelope_signature": {
"type": "string",
"description": "ECDSA-P384 signature over all preceding fields in canonical JSON 
serialization"
}
}
}
<PARSED TEXT FOR PAGE: 72 / 79>
Appendix C — Legal Instrument 
Registry Schema
The legal instrument registry is pre-registered with SOV1.AI during the
principal's active engagement with the system and constitutes the sole source
of posthumous governance authority. The following schema defines all fields
of the registry.
Field Type Required Description
registry_id UUID Yes Unique identifier 
for this registry 
instance
principal_id String Yes The principal's 
identity credential, 
matching the 
SOV1.AI root 
identity record
registry_versio
n
Integer Yes Version number, 
incremented with 
each modification; 
earlier versions are
retained in the 
append-only root 
session registry
creation_times
tamp
RFC 3161 Yes Trusted timestamp 
of initial registry 
creation
last_modified_t
imestamp
RFC 3161 Yes Trusted timestamp 
of most recent 
modification
successors Array of Successor 
records
Yes List of authorized 
successors. Each 
Successor record 
contains: 
successor_id 
(identity 
credential), 
successor_class 
(integer, Class 1 = 
highest privilege), 
legal_basis (string 
describing legal 
authority, e.g., 
"executor of 
<PARSED TEXT FOR PAGE: 73 / 79>
Field Type Required Description
estate", 
"designated 
beneficiary"), 
notification_channe
l (pre-registered 
contact endpoint)
access_tier_ass
ignments
Array of 
Assignment records
Yes For each 
successor_class, 
the set of 
domain_ids and 
authorized_confide
nce_tiers accessible
posthumously. 
Must not exceed 
the corresponding 
domain firewall's 
posthumous_access
_rule setting
time_locked_c
onditions
Array of TimeLock 
records
No Optional. Each 
TimeLock record 
specifies: 
domain_id (or 
"ALL"), 
trigger_type (DATE,
INTERVAL_AFTER_
DEATH, 
EVENT_HASH), 
trigger_value, 
action (UNLOCK, 
LOCK, DESTROY)
domain_expira
tion_dates
Map of domain_id 
to RFC 3339 date
No Optional. Domain￾specific expiration 
dates after which 
successor access to
that domain is 
revoked regardless 
of 
access_tier_assign
ment
destruction_co
nditions
Array of 
Destruction records
Yes (at least one) Each Destruction 
record specifies: 
condition_type 
(TIME_BASED_SU
NSET, 
SUCCESSOR_VOTE
, COURT_ORDER, 
NO_SUCCESSION),
condition_paramete
rs (e.g., 
sunset_years: 99; 
vote_threshold: 
"unanimous_class1"
<PARSED TEXT FOR PAGE: 74 / 79>
Field Type Required Description
), deletion_type 
(SOFT, HARD)
registry_truste e
Trustee record Yes Designated registry
trustee: trustee_id 
(identity 
credential), 
notification_channe
l (pre-registered 
contact endpoint), 
co_signature_autho
rity (boolean — if 
TRUE, certain 
registry 
modifications 
require trustee co￾signature)
posthumous_w
atermark_visib
le
Boolean Yes If TRUE, 
posthumous 
outputs include a 
visible posthumous 
mode indicator in 
the response text, 
in addition to 
metadata 
watermarking
incapacitation
_guardian
Guardian record No Optional. 
Designated 
guardian for 
principal 
incapacitation 
protocol: 
guardian_id, 
notification_channe
l, 
incapacitation_auth
ority_scope 
(domains for which 
the guardian may 
issue the 
incapacitation flag)
registry_signat
ure
ECDSA-P384 Yes Cryptographic 
signature over all 
preceding fields, 
signed by the 
principal's current 
identity credential. 
Required on every 
version of the 
registry
sov1_counter_s
ignature
ECDSA-P384 Yes Counter-signature 
by SOV1.AI, 
<PARSED TEXT FOR PAGE: 75 / 79>
Field Type Required Description
confirming that the 
registry has been 
received, validated,
and stored in the 
hardware-secured 
environment
References
[1] Locke, J. (1689). An Essay Concerning Human Understanding, Book II, Chapter
27: "Of Identity and Diversity." Clarendon Press (modern edition, 1979).
[2] Parfit, D. (1984). Reasons and Persons, Part III: "Personal Identity." Oxford
University Press, Oxford.
[3] National Institute of Standards and Technology (NIST). (2018). Digital Evidence
Standards and Principles. NIST Special Publication 800-86. U.S. Department of
Commerce.
[4] Chisholm, R. M. (1977). Theory of Knowledge, 2nd ed. Prentice-Hall, Englewood
Cliffs, NJ.
[5] Goldman, A. I. (1979). "What Is Justified Belief?" In G. Pappas (ed.), Justification
and Knowledge. D. Reidel Publishing, Dordrecht. pp. 1–23.
[6] Gettier, E. L. (1963). "Is Justified True Belief Knowledge?" Analysis, 23(6), pp. 121–
123. Oxford University Press.
[7] Lewis, P., Perez, E., Piktus, A., Petroni, F., Karpukhin, V., Goyal, N., ... & Kiela, D.
(2020). "Retrieval-Augmented Generation for Knowledge-Intensive NLP Tasks."
Advances in Neural Information Processing Systems, 33, pp. 9459–9474.
[8] Huang, L., Yu, W., Ma, W., Zhong, W., Feng, Z., Wang, H., ... & Liu, T. (2023). "A
Survey on Hallucination in Large Language Models: Principles, Taxonomy,
Challenges, and Open Questions." arXiv preprint arXiv:2311.05232.
[9] Greshake, K., Abdelnabi, S., Mishra, S., Endres, C., Holz, T., & Fritz, M. (2023). "Not
What You've Signed Up For: Compromising Real-World LLM-Integrated
<PARSED TEXT FOR PAGE: 76 / 79>
Applications with Indirect Prompt Injection." Proceedings of the ACM
Workshop on Artificial Intelligence and Security (AISec), pp. 79–90.
[10] Uniform Law Commission. (2015). Revised Uniform Fiduciary Access to
Digital Assets Act (RUFADAA). Uniform Law Commission, Chicago, IL.
[11] European Parliament and Council. (2016). Regulation (EU) 2016/679 (General
Data Protection Regulation). Official Journal of the European Union, L 119, pp.
1–88.
[12] Loi n° 78-17 du 6 janvier 1978 relative à l'informatique, aux fichiers et aux libertés
(as amended by Loi n° 2018-493 of 20 June 2018). Journal officiel de la République
française.
[13] Nakamoto, S. (2008). "Bitcoin: A Peer-to-Peer Electronic Cash System." [Provides
foundational treatment of cryptographic hash chaining and Merkle trees as tamper￾evident data structures, applicable to audit log design.] Accessed via
bitcoin.org/bitcoin.pdf.
[14] ANSI/IEEE. (2020). IEEE Standard for Authentication in Access Control
Systems (IEEE 802.1AR). IEEE Standards Association.
[15] Ben-Sasson, E., Chiesa, A., Garman, C., Green, M., Miers, I., Tromer, E., & Virza, M.
(2014). "Zerocash: Decentralized Anonymous Payments from Bitcoin."
Proceedings of the IEEE Symposium on Security and Privacy, pp. 459–474.
[zk-SNARK foundational reference.]
[16] Adams, C., Cain, P., Pinkas, D., & Zuccherato, R. (2001). Internet X.509 Public
Key Infrastructure Time-Stamp Protocol (TSP). RFC 3161. Internet
Engineering Task Force.
[17] Brickell, E., & Li, J. (2012). "Enhanced Privacy ID: A Direct Anonymous Attestation
Scheme with Enhanced Revocation Capabilities." IEEE Transactions on
Dependable and Secure Computing, 9(3), pp. 345–360.
[18] European Union Agency for Cybersecurity (ENISA). (2022). Guidelines on
Security of AI — A Mapping of the ENISA AI Threat Landscape.
Publications Office of the European Union, Luxembourg.
<PARSED TEXT FOR PAGE: 77 / 79>
[19] Pasquale, F. (2020). New Laws of Robotics: Defending Human Expertise in
the Age of AI. Belknap Press of Harvard University Press, Cambridge, MA.
[20] Morley, J., Cowls, J., Taddeo, M., & Floridi, L. (2020). "The Ethics of AI in Health
Care: A Mapping Review." Social Science & Medicine, 260, 113172. [Addresses
multi-domain principal governance analogies and their ethical implications.]
[21] Russell, S. (2019). Human Compatible: Artificial Intelligence and the
Problem of Control. Viking Press, New York.
[22] Garfinkel, S. L. (2007). "Anti-forensics: Techniques, Detection and
Countermeasures." Proceedings of the 2nd International Conference on i￾Warfare and Security (ICIW), pp. 77–84. [Foundational treatment of
cryptographic shredding and key-destruction-as-data-destruction.]
[23] Bertino, E., & Takahashi, K. (2011). Identity Management: Concepts,
Technologies, and Systems. Artech House, Norwood, MA.
[24] NIST. (2020). Zero Trust Architecture. NIST Special Publication 800-207. U.S.
Department of Commerce.
[25] Wang, X., Zhang, R., & Li, W. (2024). "Embedding Drift in Deployed Retrieval
Systems: A Longitudinal Study of Semantic Consistency Under Model Updates."
Proceedings of the ACM SIGIR Conference on Research and
Development in Information Retrieval, pp. 1204–1213.
1
 Parfit (1984) provides the most influential modern treatment of psychological continuity as the
basis for personal identity, arguing that identity relations are not what matters in survival; rather,
it is the continuity of memory, belief, and intention. This argument has direct implications for AI
systems claiming to represent a person's identity: the continuity of the represented content, not
merely its provenance, constitutes the identity relation.
2
 The distinction between synchronic and diachronic identity is standard in the personal identity
literature; see Shoemaker, S. (1963). Self-Knowledge and Self-Identity. Cornell
University Press.
<PARSED TEXT FOR PAGE: 78 / 79>
3
 The legal chain-of-custody doctrine is codified in the Federal Rules of Evidence, Rule 901, and is
the standard against which evidentiary authentication is measured in U.S. federal proceedings.
4
 For a contemporary treatment of foundationalism and its relationship to computational
knowledge representation, see Pollock, J. L., & Cruz, J. (1999). Contemporary Theories of
Knowledge, 2nd ed. Rowman & Littlefield.
5
 Goldman's process reliabilism, introduced in Goldman (1979) and developed in Goldman, A. I.
(1986). Epistemology and Cognition. Harvard University Press, provides the most direct
philosophical analogue for the confidence tiering schema: a belief is justified if produced by a
reliable process, just as an assertion is κ1 if produced by a cryptographically authenticated session
process.
6
 For a treatment of provenance in data engineering, see Buneman, P., Khanna, S., & Tan, W. C.
(2001). "Why and Where: A Characterization of Data Provenance." International
Conference on Database Theory (ICDT), Lecture Notes in Computer Science, vol. 1973,
pp. 316–330.
7
 The anonymization of retrieved content in vector database systems is a consequence of the
embedding process itself: the dense vector representation encodes semantic content but discards
metadata, including attribution and provenance, unless those metadata are explicitly stored and
retrieved alongside the vector. Current systems do not enforce this coupling at the architectural
level.
8
 For a formal treatment of embedding drift and its effects on retrieval consistency, see Wang et al.
(2024), reference [25].
9
 The indirect prompt injection attack vector was formally characterized in Greshake et al. (2023),
reference [9]. The attack exploits the fact that LLMs process retrieved content and instruction
prompts in the same context window, without architectural separation between trusted and
untrusted inputs.
10 As of September 2026, forty-seven U.S. states have enacted versions of RUFADAA, though with
significant variation in the fiduciary scope and terms-of-service override provisions. The analysis
in this section is based on the uniform act text and may differ from specific state implementations.
11 GDPR Article 17(3) provides exceptions to the right to erasure for, inter alia, exercising the
right of freedom of expression and information, compliance with a legal obligation, and archiving
purposes in the public interest. These exceptions may apply to AI legacy systems used for archival
or historical purposes.
<PARSED TEXT FOR PAGE: 79 / 79>
12 RUFADAA §4 establishes the priority ordering: online tool > estate planning document > terms
of service. This ordering directly supports the ACI framework's pre-registered legal instrument
registry as the highest-priority authority for posthumous access governance.
13 GDPR Recital 27 explicitly states that the Regulation "does not apply to the personal data of
deceased persons," but invites member states to provide rules for such data.
14 California Assembly Bill 602 (2023) and Senate Bill 1228 (2024) together establish a right of
deceased performers to control AI-generated synthetic media of their voice and likeness,
enforceable by their estates. The ACI framework's successor-class authorization mechanism
provides a technically compliant implementation of this right.
15 For a comprehensive treatment of zero-knowledge proof applications to data privacy in
distributed systems, see Boneh, D., & Shoup, V. (2020). A Graduate Course in Applied
Cryptography, Chapter 20. Available at
crypto.stanford.edu/~dabo/cryptobook/BonehShoup_0_5.pdf.