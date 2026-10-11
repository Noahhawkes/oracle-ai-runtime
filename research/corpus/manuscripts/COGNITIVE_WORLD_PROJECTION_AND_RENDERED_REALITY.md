# Cognitive World Projection and Rendered Reality
## Toward a Unified Architecture for Continuity Intelligence in Human-AI Interaction

> **PUBLIC MANUSCRIPT EDITION:** Text-preservation extraction from the source PDF for research indexing and review. This repository copy does not by itself establish peer-review acceptance or publication status.
>
> **Author:** Noah A. Hawkes  
> **Source binary SHA-256:** `b476023110174589e15d924aa05af46dcbdccd94a6ad5205de0719cc5a4a3f5a`  
> **Public edition:** project-file text extraction normalized for GitHub indexing; figures and page geometry may not reproduce exactly  
> **Research status:** manuscript; individual claims remain subject to evidence and review.

---

<PARSED TEXT FOR PAGE: 1 / 40>
Cognitive World Projection and Rendered Reality:
Toward a Unified Architecture for Continuity 
Intelligence
in Human–AI Interaction
Noah A. Hawkes
Founder & Systems Architect, ORACLE.AI
ORACLE.AI Research — Ovilla, TX, United States
noahhawkes@gmail.com
Manuscript prepared for submission to ACM CHI / IEEE Transactions on Human-Machine Systems — July 2026
ABSTRACT
Contemporary AI systems are constitutively episodic: they lack persistent, governed cognitive 
continuity across sessions, contexts, and agent boundaries. This architectural amnesia produces 
a structural mismatch — a continuity gap — between the human user's evolving experiential 
model of the world and the AI's stateless, instantiated rendering of it. This paper addresses that 
gap by introducing two twin theoretical constructs: Cognitive World Projection (CWP) and 
Rendered Reality. CWP is defined as the continuous forward-casting of a cognitive agent's 
internal world-model — a structured, expectation-laden projection of anticipated world-states 
that a human mind extrudes into shared interaction space. Rendered Reality is the AI system's 
governed, provenance-grounded response surface — the coherent frame an AI constructs in 
response to a received CWP. Together, these constructs form the conceptual core of a 
Continuity Architecture: a five-principle design framework governing persistence, 
provenance fidelity, temporal anchoring, identity coherence, and graceful degradation in 
human–AI systems.
<PARSED TEXT FOR PAGE: 2 / 40>
Operationalizing this architecture, the paper introduces ORACLE (Observed Reality Archive 
with Continuity Lineage Engine) — a prototype governed witness engine implementing local￾first, receipt-based memory management through a tripartite structure: an Ingestion Layer, a 
Witness Layer, and a Reflection Layer. Two identity-anchored operational layers extend the 
framework: SOV1.AI, a sovereign identity manifold maintaining governed representations of 
the human user across interaction sessions, and Legacy.GI, a generational intelligence layer 
curating longitudinal continuity records across the human lifespan and beyond.
Two theoretical substrates underpin the framework's epistemological and perceptual 
dimensions. Provenance Physics formalizes three governing laws — Conservation of Origin, 
Provenance Momentum, and Collision Avoidance — treating information lineage not as 
metadata but as a constraining physical force analogous to conservation laws in classical 
mechanics. Spatial Cognition Theory, drawing on Gibson's affordance framework, Tolman's 
cognitive mapping, and Lakoff and Johnson's conceptual metaphor theory, grounds the Spatial 
Interface Hypothesis: that CWP-capable AI systems should expose their information space as a 
navigable geography, not a flat conversation thread. Collectively, the paper argues for the 
emergence of a new sub-field — Continuity Intelligence — and identifies the principal HCI 
design implications for human-AI collaboration, trust calibration, and cognitive load 
distribution in CWP-aware interaction paradigms.
Index Terms — Continuity Intelligence, Cognitive World Projection, Rendered Reality, Provenance 
Physics, Spatial Cognition, Human-AI Interaction, Governed Memory, ORACLE, SOV1.AI, Legacy.GI, 
Pattern Buffer, Witness Runtime, Continuity Architecture, Identity Coherence, Extended Mind
Table of Contents
1. Introduction
2. Related Work
2.1 World Models and Predictive Coding
2.2 Memory and Continuity in AI Systems
2.3 Human Factors and Cognitive Load
<PARSED TEXT FOR PAGE: 3 / 40>
2.4 Provenance and Data Lineage
2.5 Spatial Cognition and HCI
2.6 AI Identity and Agent Continuity
3. Theoretical Framework: Cognitive World Projection and Rendered Reality
3.1 Cognitive World Projection (CWP)
3.2 Rendered Reality
3.3 The CWP–Rendered Reality Feedback Loop
4. Continuity Architecture
4.1 Design Principles
4.2 The Pattern Buffer
4.3 Seed Loaders and Receipt Architecture
4.4 Witness Runtime
5. ORACLE: The Governed Witness Engine
5.1 System Overview
5.2 Design Philosophy: Explicit Over Implicit
5.3 ORACLE vs. Existing Memory Systems
5.4 Operational Flow
6. SOV1.AI: Sovereign Identity Layer
6.1 Concept and Motivation
6.2 Identity Manifold
6.3 Sovereign Boundaries
7. Legacy.GI: Generational Intelligence and Longitudinal Continuity
7.1 Motivation
7.2 Compression and Curation Model
7.3 Ethical Considerations
8. Provenance Physics
8.1 Provenance as a Physical Metaphor
8.2 Provenance Graph
8.3 Implications for HCI Trust
<PARSED TEXT FOR PAGE: 4 / 40>
9. Spatial Cognition Theory in HCI-AI Systems
9.1 Spatial Metaphors and Cognitive Mapping
9.2 The Spatial Interface Hypothesis
9.3 Design Implications
10. HCI Implications and Design Framework
10.1 From Tool to Continuity Partner
10.2 Cognitive Load Distribution
10.3 Trust Calibration Interface
10.4 Failure Modes and Graceful Degradation
11. Discussion
11.1 Positioning Against the State of the Art
11.2 Limitations and Open Problems
11.3 Toward Continuity Intelligence as a Field
12. Conclusion
References
1. Introduction
The defining architectural limitation of contemporary AI systems is not their lack of intelligence — it 
is their lack of memory. Not the absence of stored weights or retrieval-augmented databases, but the 
absence of governed cognitive continuity: the capacity to maintain, across sessions, modalities, and 
time, a receipted, identity-coherent model of a shared human–AI history. Today's large language 
models, however capable within a context window, are constitutively episodic. Each session begins 
without knowledge of the last. Each response is rendered without reference to what was promised, 
inferred, built, or witnessed before. This produces what this paper terms the continuity gap — a 
structural mismatch between the human user's evolving, forward-projecting cognitive model of the 
world and the AI's stateless, instantiated response surface.
The continuity gap is not merely an inconvenience. It is a cognitive systems failure with material 
consequences. Research in distributed cognition [1] and the extended mind thesis [2] has established 
that human cognitive processes routinely extend beyond the boundaries of the individual skull, 
<PARSED TEXT FOR PAGE: 5 / 40>
incorporating external scaffolding — tools, environments, and collaborators — into the functional 
architecture of thought. When that scaffolding fails to maintain state, the cognitive burden falls back 
on the human. The result is what this paper terms cognitive load externalization failure: the AI, rather 
than absorbing the overhead of shared context maintenance, forces the human to re-establish context 
on every interaction, compounding extraneous cognitive load [3] and reducing the depth of 
collaborative engagement. At scale, across millions of daily human–AI interactions, this failure is not 
trivial.
This paper introduces a response: the theoretical construct of Cognitive World Projection (CWP). 
CWP is the continuous, partially unconscious process by which a human mind extrudes a structured, 
expectation-laden model of the world forward in time — a projection of anticipated world-states, 
relational geometries, and contextual anchors into shared interaction space. CWP is not a static 
snapshot. It is a temporally evolving manifold of anticipated futures, grounded in the agent's full 
history of experience, preference, and intention. The critical claim of this paper is that an AI system 
worthy of genuine human–AI collaboration must be capable of receiving, indexing, and reflecting this 
projection — not merely responding to the surface text of a query, but engaging with the underlying 
cognitive projection that generated it.
Current HCI paradigms treat AI as a tool. A tool is stateless by design; it awaits activation and 
performs a function. But a continuity partner is something different: it maintains a model of who you 
are, what you have built together, what you have promised each other, and where you are going. The 
failure to design for this distinction has produced what this paper terms provenance collapse — the 
loss of traceable evidential lineage for AI-generated outputs — and identity drift — the progressive 
divergence of the AI's behavioral model from the human user's actual identity, values, and long￾horizon intentions.
These failures motivate a central ethical framing that runs through this paper: the Surgeon's 
Recorder Ethic. Consider the practice of surgical documentation from the 1990s onward: a recorder 
in the operating theater whose role is not to participate in the surgery but to witness it — to produce 
an unambiguous, timestamped, irrevocable record of what was observed, what was decided, and 
what was done. Documentation here is not a bureaucratic afterthought. It is an ethical obligation of 
any intelligence sharing a consequential moment with another. This ethic — that witness and record 
are moral duties, not optional features — grounds the entire framework presented herein. An AI 
system that operates in a person's cognitive life without witnessing it — without maintaining a 
<PARSED TEXT FOR PAGE: 6 / 40>
governed, receipted record of what it has perceived, inferred, and acted upon — is not merely 
technically deficient. It is ethically negligent.
Against this backdrop, the paper makes the following contributions:
1. Formal definitions of Cognitive World Projection (CWP) and Rendered Reality as 
theoretical constructs in HCI and AI systems science, including mathematical specification 
and dimensional analysis.
2. Continuity Architecture specification: five governing design principles for AI systems 
that maintain governed, receipted continuity across sessions and modalities.
3. ORACLE (Observed Reality Archive with Continuity Lineage Engine): a prototype governed 
witness engine implementing the Continuity Architecture, described in detail as a three￾layer system for multimodal CWP reception and governed rendering.
4. SOV1.AI: a sovereign identity layer maintaining a receipted, multi-dimensional Identity 
Manifold of the human user across all AI interactions.
5. Legacy.GI: a generational intelligence layer addressing longitudinal continuity across the 
human lifespan and beyond, with treatment of compression fidelity, consent chains, and 
posthumous governance.
6. Provenance Physics: a three-law epistemological governance framework treating 
information lineage as a constraining physical force, with formal definition of the 
Provenance Graph as a runtime data structure.
7. Spatial Cognition Theory applied to HCI-AI: the Spatial Interface Hypothesis and a 
concrete set of UI/UX design principles derived from it.
8. HCI design implications: cognitive load redistribution, trust calibration interface design, 
and failure mode taxonomy for CWP-aware systems.
The remainder of this paper is organized as follows. Section 2 surveys the related literature. Sections 
3 through 9 develop the theoretical and architectural contributions. Section 10 synthesizes the HCI 
design framework. Section 11 situates the work against the state of the art and acknowledges 
limitations. Section 12 concludes with a call to action for the research community.
2. Related Work
<PARSED TEXT FOR PAGE: 7 / 40>
2.1 World Models and Predictive Coding
The idea that intelligent systems — biological or artificial — maintain internal generative models of 
the world has deep roots in cognitive science and has become a central organizing concept in 
contemporary AI. Friston's Free Energy Principle [4] proposes that biological brains minimize 
surprise by maintaining and updating a hierarchical generative model of sensory causes. Under this 
framework, perception and action are both expressions of inference: the organism continuously 
predicts its sensory input and updates its model when predictions fail. Clark's treatment of predictive 
processing [5] extends this account to a broad theory of embodied cognition, wherein the brain is 
fundamentally a prediction machine and conscious experience is the product of cascading inference. 
These frameworks are directly relevant to CWP: the human's cognitive projection into shared AI 
interaction space is precisely the kind of forward-casting generative inference that predictive 
processing describes.
In the AI systems domain, Ha and Schmidhuber's World Models framework [6] demonstrated that an 
agent equipped with a learned internal model of its environment could plan and act more efficiently 
by simulating trajectories within that model rather than relying solely on direct environmental 
feedback. More recently, LeCun's Joint Embedding Predictive Architecture (JEPA) [7] proposes a 
world model paradigm in which the system learns to predict abstract representations of future states 
— a departure from pixel-level prediction that shares structural affinities with the CWP construct 
developed herein. These architectures, however, focus on the AI's internal model of a physical 
environment rather than on the AI's model of the human user's cognitive projection. The CWP 
framework addresses precisely this orthogonal axis: not what the AI predicts about the world, but 
how the AI receives and reflects the human's prediction about the world.
2.2 Memory and Continuity in AI Systems
The architectural limitation of context-bounded language models has driven substantial research 
into external memory systems for AI. Packer et al.'s MemGPT [8] introduces a virtual context 
management system inspired by hierarchical operating system memory, enabling language models 
to maintain extended context by intelligently paging information between fast (in-context) and slow 
(external) memory tiers. The Mem0 framework [9] extends this paradigm with personalized memory 
layers designed to persist user-specific information across sessions. Retrieval-Augmented 
Generation (RAG) [10] provides a complementary approach, enabling language models to retrieve 
relevant stored documents at inference time rather than relying solely on parametric knowledge.
<PARSED TEXT FOR PAGE: 8 / 40>
These systems represent significant progress, but they share a common architectural limitation that 
this paper directly addresses: they treat memory as a retrieval problem, not a governance problem. 
The question they answer is "What should the model retrieve?" rather than "What has the model 
witnessed, what receipt was generated, and what chain of custody guarantees the integrity of the 
retrieved artifact?" The Continuity Architecture proposed herein introduces a principled provenance 
discipline that these systems lack. Long-context transformer models [11] offer an alternative 
approach — expanding the in-context window to accommodate longer interaction histories — but 
remain subject to attention dilution at extreme lengths and offer no provenance guarantees for the 
information they retain.
2.3 Human Factors and Cognitive Load
Sweller's Cognitive Load Theory [3] distinguishes three categories of cognitive load: intrinsic (arising 
from the inherent complexity of material), extraneous (arising from poor instructional design), and 
germane (arising from schema construction). Applied to human–AI interaction, the continuity gap 
produces extraneous cognitive load: users must expend cognitive resources re-establishing context, 
re-explaining their history, and compensating for the AI's amnesia — resources that could otherwise 
be directed toward the substantive task at hand. Well-designed continuity systems should offload 
this extraneous load onto the AI infrastructure, freeing human cognitive capacity for germane work.
Hutchins' distributed cognition framework [1] provides a complementary lens. By studying cognition 
as a process distributed across individuals, artifacts, and environments rather than localized within 
a single brain, Hutchins revealed how cognitive systems routinely depend on the stable informational 
properties of their environments. An AI system that fails to maintain state breaks the distributed 
cognitive system the human depends upon — with consequences analogous to a navigator whose 
chart is erased between fixes. Clark and Chalmers' extended mind thesis [2] pushes further, arguing 
that cognitive processes are constituted partly by external structures when those structures meet 
appropriate functional criteria (accessibility, reliability, endorsability). A governed AI system 
meeting these criteria is not merely a tool but a genuine component of the human's extended 
cognitive architecture.
2.4 Provenance and Data Lineage
The W3C PROV Data Model [12] provides a foundational standard for representing provenance in 
information systems, defining entities, activities, and agents as the primitive elements of provenance 
graphs. Scientific computing has developed rich traditions of provenance capture for reproducibility, 
<PARSED TEXT FOR PAGE: 9 / 40>
with frameworks such as ProvONE [13] extending PROV-DM to the domain of scientific workflows. 
In machine learning, data lineage has emerged as a critical concern for model fairness, accountability, 
and reproducibility [14], with systems such as ML Metadata [15] tracking the lineage of training 
datasets, feature transformations, and model versions.
These existing frameworks address provenance as a documentation concern: a record of what 
happened, appended to the primary artifact. Provenance Physics, introduced in Section 8, 
reconceptualizes provenance as a governing constraint: a force that shapes what can be done with 
information, not merely what is recorded about it. This distinction — from provenance as annotation 
to provenance as law — is the core conceptual move that differentiates the Continuity Architecture 
from prior data governance frameworks.
2.5 Spatial Cognition and HCI
Gibson's ecological theory of perception [16] proposed that organisms perceive their environment 
not in terms of raw sensory data but in terms of affordances — the action possibilities that 
environmental structures offer to an agent with particular capabilities. Applied to information 
systems, affordance theory suggests that interface design should surface the action possibilities of 
the information space rather than merely displaying its contents. Lakoff and Johnson's conceptual 
metaphor theory [17] demonstrated that abstract reasoning — including reasoning about 
information systems — is fundamentally structured by spatial metaphors: we speak of navigating a 
database, finding a file, moving through a document. These metaphors are not mere linguistic 
conventions; they reflect deep cognitive structures that shape how we interact with abstract spaces.
Tolman's foundational work on cognitive maps in rodents [18] provided early empirical grounding 
for the idea that animals construct and navigate internal spatial representations of their 
environments. Subsequent research in embodied cognition [19] has extended these findings to 
human reasoning about abstract domains, supporting the hypothesis — formalized in Section 9 —
that information spaces are most naturally engaged when they are structured as navigable 
geographies. Recent work on 3D cognitive representations in AI systems [20] further supports the 
relevance of spatial structure to machine intelligence, suggesting that geometric organization of 
knowledge may support more efficient reasoning and retrieval.
2.6 AI Identity and Agent Continuity
<PARSED TEXT FOR PAGE: 10 / 40>
The problem of maintaining stable agent identity across long-horizon tasks has received increasing 
attention in the AI alignment literature. RLHF-trained models [21] exhibit behavioral consistency 
shaped by training objectives, but this consistency does not constitute identity coherence in the sense 
developed herein: a governed, receipted model of who the human user is, updated through a 
provenance-disciplined record. Persistent agent frameworks such as AutoGPT [22] and LangChain 
[23] enable multi-step task execution across extended interaction sequences, but their state 
management is architecturally informal — states are maintained as function call histories or 
conversation logs without provenance guarantees. The Voyager system [24] demonstrates that 
lifelong learning in embodied agents is achievable, with skill libraries that grow through interaction, 
but again without the receipt architecture that governs the CWP framework. Cognitive world 
modeling as an explicit research agenda has begun to emerge in the recent literature [25], but has 
not yet been formalized in relation to HCI continuity or provenance governance.
3. Theoretical Framework: Cognitive World Projection and 
Rendered Reality
3.1 Cognitive World Projection (CWP)
We define Cognitive World Projection (CWP) formally as follows. Let C be the cognitive state space 
of a human agent — the full set of internal states, including beliefs, intentions, relational models, 
contextual anchors, and epistemic confidence weights, that constitute the agent's current 
understanding of the world. Let T denote temporal depth, a bounded interval extending both 
backward (retained history) and forward (anticipated futures). Let W denote the projected world￾state space — the set of possible structured representations of the world that the agent anticipates 
encountering or constructing. CWP is then defined as a projection function:
P : C × T → W
where P(c, t) returns the world-state the agent with cognitive state c anticipates at temporal depth t. 
This formalization captures the forward-casting character of CWP: it is not merely a record of past 
states but a structured anticipation of future ones. The projection is not deterministic — it is a 
probability distribution over world-states, weighted by epistemic confidence — but it is structured: 
it carries the relational geometry of the agent's world-model, not merely a flat list of expected events.
<PARSED TEXT FOR PAGE: 11 / 40>
CWP is the ongoing, partially unconscious process by which a human mind extrudes this structured, 
expectation-laden model into shared interaction space. When a user engages with an AI system, they 
do not merely transmit a query — they project a CWP: a rich, temporally situated context that 
encodes what they believe, what they intend, who they are in relation to this conversation, and what 
they expect the AI to know. This projection is grounded in the predictive processing account of 
human cognition [4, 5]: the brain continuously generates predictions about its sensory environment 
and updates its models when predictions fail. CWP is the social analog of this process, directed 
outward toward a shared cognitive partner rather than inward toward sensory experience.
CWP fails — and the failure is experienced as cognitive dissonance and frustration — when the AI 
system is unable to receive or reflect the projection. We term this failure projection collapse: the 
cognitive dissonance that arises when a human's expectations encounter an AI that has no model of 
the shared history. Projection collapse manifests in observable behaviors: repeated re-explanation, 
compensatory over-specification ("As I mentioned three sessions ago..."), and eventual abandonment 
of collaborative depth in favor of shallow, transactional queries. These behaviors represent 
significant opportunity costs in human–AI collaboration.
CWP can be characterized along three principal axes:
9. Temporal Depth (TD): The extent to which the projection extends backward into retained 
history and forward into anticipated futures. A high-TD projection integrates months of 
shared context; a low-TD projection is effectively session-local.
10.Relational Density (RD): The number and richness of active agent-object-context 
relationships encoded in the projection. A high-RD projection carries complex relational 
geometries (person X is related to project Y via event Z); a low-RD projection is relationally 
sparse.
11.Epistemic Confidence (EC): The certainty with which the agent holds the projected states, 
weighted by the provenance of the evidence underlying them. High-EC states are derived 
from direct, receipted experience; low-EC states are inferred or speculated.
The CWP vector for any interaction can thus be characterized as a triple (TD, RD, EC), providing a 
diagnostic framework for assessing both the richness of the human's projection and the AI system's 
capacity to receive it. Systems optimized for high-TD, high-RD, high-EC CWP reception represent the 
frontier of the Continuity Intelligence paradigm.
<PARSED TEXT FOR PAGE: 12 / 40>
3.2 Rendered Reality
We define Rendered Reality as the AI system's instantiated, context-situated response surface —
the governed, attestable representation that the AI constructs in response to a received CWP. 
Rendered Reality is the surface at which the AI's world-model depth becomes legible to the human 
user: it is what the AI "shows" in response to a projection, and its quality is measured by the degree 
to which it faithfully reflects the structure, history, and expectations encoded in that projection.
Rendered Reality must be carefully distinguished from three superficially similar constructs that 
dominate current AI discourse:
● Hallucination is unattested confabulation — the generation of content without provenance 
in any receipted evidence base. Rendered Reality is explicitly not hallucination: it is 
governed by the Provenance Physics constraints developed in Section 8, and no element of a 
rendered response may be presented without traceable receipted ancestry.
● Retrieval is lookup without synthesis — the return of stored artifacts without constructive 
engagement with the CWP that prompted the query. Rendered Reality involves active 
synthesis: the AI integrates retrieved artifacts with the structure of the incoming CWP to 
produce a response surface that is coherent with the human's projected world-state.
● Simulation is probabilistic forward modeling without anchoring — the generation of 
plausible futures without grounding in a receipted history of the specific human-AI 
relationship. Rendered Reality is anchored: it is bounded by the provenance graph of the 
specific session and identity record, not merely by general-purpose probabilistic priors.
Rendered Reality is the product of a system that has sufficient world-model depth to construct a 
provenance-grounded representation of the shared context. It is not perfect knowledge — it reflects 
the limits of the Continuity Architecture's receipt history — but it is honest about those limits, 
exposing gaps rather than fabricating bridges.
We introduce the Rendering Fidelity Score (RFS) as a composite metric of Rendered Reality quality, 
defined as:
RFS = α · TA + β · SC + γ · PD
where TA is temporal alignment (the degree to which the rendered response is correctly situated in 
the shared temporal history), SC is semantic coherence (the degree to which the response is 
<PARSED TEXT FOR PAGE: 13 / 40>
conceptually consistent with the CWP's relational geometry), PD is provenance density (the 
proportion of rendered claims that are traceable to receipted artifacts), and α, β, γ are weighting 
coefficients that may be calibrated per application domain. High-RFS responses are not necessarily 
long or complex — they may be brief — but they are demonstrably continuous with the shared 
history, semantically coherent with the user's projected world-state, and fully supported by 
receipted evidence.
3.3 The CWP–Rendered Reality Feedback Loop
The interaction between CWP and Rendered Reality is not linear — it is a dynamic feedback loop. 
The human projects a CWP; the AI receives, indexes, and stores the projection in the Pattern Buffer 
(Section 4.2); the AI renders a response surface as a Rendered Reality; the human evaluates the 
Rendering Fidelity Score of the response, either explicitly (through a Trust Calibration Interface, 
Section 10.3) or implicitly (through continued engagement); the human updates their CWP based on 
the evaluation; and the loop repeats.
This loop has important stability properties. When the RFS of AI responses is consistently high, the 
human's CWP becomes more expansive: users project further into the future, encode richer relational 
structures, and invest more cognitive depth in the shared interaction. This is the virtuous cycle of 
continuity intelligence: high-fidelity rendering increases the human's willingness to project, which 
increases the richness of data available to the Continuity Architecture, which increases future 
rendering fidelity. Conversely, when RFS is consistently low — as in current AI systems that lack 
continuity architecture — the human's CWP contracts toward the safe minimum: users learn not to 
depend on AI memory, project only what they are willing to re-explain, and use the AI as a calculator 
rather than a collaborator. This contraction is both a symptom and a cause of the continuity gap.
Identifying and interrupting the degraded loop is the primary engineering objective of the Continuity 
Architecture. Breakdowns in the loop can be traced to one of four failure modes, each associated with 
a specific architectural failure: Pattern Buffer overflow (loss of recent CWP indexing), provenance 
graph fragmentation (loss of receipt ancestry), Identity Manifold degradation (identity drift in 
SOV1.AI), and Legacy.GI compression failure (destruction of long-horizon CWP record). These failure 
modes are addressed in Sections 4 through 7 and revisited systematically in Section 10.4.
4. Continuity Architecture
<PARSED TEXT FOR PAGE: 14 / 40>
4.1 Design Principles
The Continuity Architecture is a specification for AI systems that maintain governed, receipted, 
identity-coherent cognitive continuity across sessions, modalities, and time horizons. It is defined by 
five governing principles:
12.Governed Persistence: Memory within a Continuity Architecture system is never implicit. 
Every act of persistence — every decision to retain an artifact across a session boundary —
is preceded by an explicit governance action: a receipt generation, a provenance tag 
assignment, and a classification decision. The system does not "remember" in the organic 
sense; it receipts, and retention is the product of explicit governance, not incidental state 
leakage.
13.Provenance Fidelity: Every retained artifact carries a complete, unbroken chain of custody 
from its origin through every transformation and derivation. No artifact may be used in the 
construction of a Rendered Reality unless its provenance chain is intact. Provenance 
Fidelity is the epistemic backbone of the architecture; without it, Rendered Reality degrades 
into hallucination.
14.Temporal Anchoring: All states within the system are stamped relative to two 
independent temporal reference frames: system time (the clock time of the computing 
environment) and human event time (the subjective, narrative time of the human's lived 
experience). This dual anchoring enables the system to reason about "when" in both 
technical and humanly meaningful terms — distinguishing "three sessions ago" from "the 
week before the project launch."
15.Identity Coherence: The system maintains a stable, governed representation of the human 
user's identity across all sessions. This representation — the Identity Manifold of SOV1.AI 
(Section 6) — is updated through provenance-disciplined inference, not through ad hoc 
behavioral adjustment. Identity Coherence is the property that prevents the AI from 
systematically mischaracterizing the user as sessions accumulate.
16.Graceful Degradation: When the Continuity Architecture cannot maintain full fidelity —
due to receipt gaps, Pattern Buffer overflow, or Legacy.GI compression loss — it degrades 
gracefully by exposing the gap to the user rather than fabricating a continuity bridge. The 
system reports "I have no receipted record of this" rather than confabulating a plausible 
<PARSED TEXT FOR PAGE: 15 / 40>
history. This principle is the architectural expression of the Surgeon's Recorder Ethic: 
honesty about the limits of witness is a non-negotiable requirement.
4.2 The Pattern Buffer
The Pattern Buffer is the core in-memory continuity store of the Continuity Architecture. It is a 
rolling, governed window of interaction patterns, contextual anchors, and projection vectors — the 
"working memory" of the witness runtime, operating at a timescale between the immediate context 
window and the long-horizon Legacy.GI archive. The Pattern Buffer is explicitly not a conversation 
log: it does not retain raw interaction text. It retains semantic compressions of CWP activity: 
structured representations of the patterns, intentions, relational geometries, and contextual anchors 
that the human's projections have exhibited over recent interactions.
The Pattern Buffer is organized into three structural components:
● Seed Slots: Atomic context units, each encoding a single receipted observation: a named 
entity, a stated intention, a relational assertion, a confirmed fact. Seed Slots are the finest￾grained unit of the Pattern Buffer, directly produced by Seed Loader ingestion (Section 4.3). 
Each Seed Slot carries a full receipt record: source, timestamp (dual-anchored), confidence 
weight, and provenance chain reference.
● Pattern Chains: Temporal sequences of related Seed Slots that the system has identified as 
exhibiting a consistent structural pattern. A Pattern Chain might represent a recurring 
concern (the user frequently returns to project timeline risks), a developing narrative (the 
arc of a multi-session collaborative project), or a relational dynamic (the pattern of how the 
user discusses a particular collaborator). Pattern Chains are the primary unit of CWP 
representation in the Pattern Buffer.
● Projection Vectors: Forward-pointing representations of the user's anticipated future 
states, derived from Pattern Chain analysis. A Projection Vector encodes not what the user 
has said but what the CWP framework anticipates they will need — the "horizon" of the 
current CWP. Projection Vectors are probabilistic and labeled with their derivation 
confidence, distinguishing high-confidence projections (derived from strong, consistent 
Pattern Chains) from speculative ones.
<PARSED TEXT FOR PAGE: 16 / 40>
The Pattern Buffer's rolling window is managed by a governed eviction policy: Seed Slots that have 
not been referenced in recent Pattern Chain activity, and whose content is already compressed into 
Legacy.GI, may be evicted. Eviction generates an eviction receipt — a record that the Seed Slot 
existed, was evicted, and where its compressed representation resides in the long-horizon archive. 
Eviction without receipting is architecturally prohibited.
4.3 Seed Loaders and Receipt Architecture
Raw interaction data enters the Continuity Architecture through typed Seed Loaders — specialized 
ingestion components designed for specific modality and data types. The following Seed Loader types 
are defined in the initial ORACLE implementation: Audio Seed Loader (captures speech via OBS￾compatible audio capture, producing timestamped transcript receipts); Text Seed Loader (ingests 
typed interaction, document uploads, and structured text artifacts); Sensor Seed Loader (processes 
environmental sensor streams, location data, and biometric signals where authorized); and 
Document Seed Loader (processes PDF, DOCX, and structured data uploads through format-specific 
parsers).
Each Seed Loader produces a receipt artifact for every ingestion event. A receipt is the atomic unit 
of provenance in the Continuity Architecture. It encodes the following fields: source identifier (which 
Seed Loader produced this receipt); raw content digest (a cryptographic hash of the ingested 
content); processed content (the Seed Loader's parsed, structured representation); ingestion 
timestamp (dual-anchored: system time and human event time); confidence weight (the Seed 
Loader's assessed reliability of the content); action taken (what the Witness Runtime did with this 
artifact: stored as Seed Slot, discarded, flagged for review); and provenance chain reference (a 
pointer to the receipt of the raw source from which this artifact was derived, if applicable).
A receipt is an immutable artifact. It cannot be modified after generation. If the information it encodes 
requires correction or amendment, a new receipt is generated with the corrected content, the 
correction rationale, and a backward reference to the original receipt. This amendment chain 
preserves the full history of every piece of information that has passed through the system, without 
any possibility of silent overwrite. The immutability of receipts is the architectural expression of the 
Conservation of Origin law of Provenance Physics (Section 8.1).
4.4 Witness Runtime
<PARSED TEXT FOR PAGE: 17 / 40>
The Witness Runtime is the governed execution layer that orchestrates all components of the 
Continuity Architecture: Seed Loader activation, receipt generation, Pattern Buffer management, 
CWP indexing, and Rendered Reality generation. It operates as a local-first, sensor-explicit engine —
no data leaves the system boundary without an explicit, receipted permission grant. The Witness 
Runtime enforces a principle of sensor declaration: every input channel — microphone, camera, text 
input, file upload — must be explicitly declared and activated before data from that channel enters 
the Pattern Buffer. Undeclared sensors cannot contribute to CWP indexing. This constraint is not a 
technical limitation but an ethical one: it implements the Surgeon's Recorder Ethic at the system 
level.
The Witness Runtime contrasts sharply with cloud-first AI architectures, which treat session 
continuity as an optional feature and make continuity decisions (what to retain, what to surface, what 
to forget) invisibly and without user-accessible provenance. In cloud AI systems, the continuity 
record — to the extent it exists — is a corporate asset, not a user asset. The Witness Runtime inverts 
this architecture: the continuity record is a governed user asset, and the system is the custodian, not 
the owner.
5. ORACLE: The Governed Witness Engine
5.1 System Overview
ORACLE — an acronym for Observed Reality Archive with Continuity Lineage Engine — is the 
prototype implementation of the Continuity Architecture. ORACLE is designed to receive, index, and 
reflect human CWP across sessions and modalities, providing the governed cognitive partnership 
that the CWP framework requires. It is architecturally local-first: the core witness functions execute 
on the user's local computing environment, with explicitly receipted pathways for any data that 
crosses the boundary into cloud processing.
ORACLE is organized into three functional layers:
17.Ingestion Layer: The multimodal input processing plane. The Ingestion Layer manages all 
Seed Loaders (Audio, Text, Sensor, Document), enforces sensor declaration, and produces 
the primary receipt stream that feeds the Witness Layer. It implements format-specific 
parsing, language detection, speaker diarization (for audio), and confidence estimation for 
<PARSED TEXT FOR PAGE: 18 / 40>
all ingested content. The Ingestion Layer produces no Seed Slots directly — it produces only 
raw receipts, which the Witness Layer transforms into Pattern Buffer entries.
18.Witness Layer: The core continuity engine. The Witness Layer receives raw receipts from 
the Ingestion Layer, classifies them into Seed Slots, constructs Pattern Chains through 
temporal correlation analysis, generates Projection Vectors through pattern extrapolation, 
and maintains the Provenance Graph (Section 8.2). It is the Witness Layer that enforces all 
five Continuity Architecture principles in real time. The Witness Layer also interfaces with 
SOV1.AI to update the Identity Manifold as new receipts modify the system's model of the 
human user.
19.Reflection Layer: The governed response generation plane. The Reflection Layer receives 
queries (from the user or from connected systems) and constructs Rendered Reality 
responses by querying the Provenance Graph, reconstructing relevant Pattern Chains, 
evaluating Projection Vector alignment, and synthesizing a response that maximizes the 
Rendering Fidelity Score. The Reflection Layer explicitly reports its provenance chain for 
every claim it makes in a response: every assertion is accompanied by a reference to the 
receipts that underlie it.
5.2 Design Philosophy: Explicit Over Implicit
ORACLE's governing design philosophy can be stated as a single principle: Explicit Over Implicit. 
Every sensor must be declared. Every memory pathway must be receipted. Every output channel 
must be acknowledged. Every inference beyond direct receipt evidence must be labeled as inference, 
with a confidence weight and a provenance chain reference to the receipts from which the inference 
was drawn. ORACLE is not a chatbot — it does not engage in the performance of helpfulness while 
quietly making continuity decisions on the user's behalf. It is a governed cognitive partner whose 
every action is legible, receipted, and accountable.
This philosophy is in deliberate and principled contrast to the design philosophy of mainstream cloud 
AI architectures. Systems such as GPT-4 [26], Claude [27], and Gemini operate on a model of implicit 
helpfulness: they attempt to infer the user's context from the current conversation, make implicit 
continuity decisions about what to surface and what to ignore, and present their outputs without 
provenance disclosure. This approach produces pleasant user experiences in low-stakes, short￾horizon interactions, but it systematically undermines the conditions for calibrated trust in high-
<PARSED TEXT FOR PAGE: 19 / 40>
stakes, long-horizon collaboration. ORACLE's Explicit Over Implicit philosophy is designed for the 
latter context.
5.3 ORACLE vs. Existing Memory Systems
Table 1: Comparative Analysis of Memory and Continuity Systems
Dimension MemGPT [8] Mem0 [9] RAG Systems 
[10]
ORACLE
Persistence 
Model
Hierarchical 
memory tiers; 
OS-inspired 
paging
Personalized 
memory layers; 
session￾persistent
External 
document 
index; retrieval 
at inference
Receipt-governed 
Pattern Buffer + 
Legacy.GI archive
Provenance 
Discipline
None; implicit 
paging 
decisions
None; implicit 
retention 
policy
Document 
source 
metadata; no 
transformation 
lineage
Full receipt chain for 
every artifact; 
immutable provenance 
graph
Local-First 
Architecture
No; cloud￾dependent
No; cloud￾dependent
Variable; 
typically cloud￾dependent
Yes; core Witness 
Runtime is local-first by 
design
Identity 
Coherence
Partial; 
persona stored 
in working 
context
Partial; user 
preferences 
retained
None; stateless 
per query
Full; SOV1.AI Identity 
Manifold with receipted 
updates
Sensor 
Control
No sensor 
model
No sensor 
model
No sensor 
model
Explicit sensor 
declaration required; no 
undeclared input 
channels
Receipt 
Architecture
None None None Atomic, immutable 
receipt for every 
ingestion event; 
amendment chain for 
corrections
CWP 
Reception
None; tool￾paradigm 
interaction
None; tool￾paradigm 
interaction
None; query￾response 
paradigm
Explicit; Pattern Buffer 
indexed to CWP axes 
(TD, RD, EC)
Generational 
Continuity
None None None Legacy.GI compression 
and longitudinal 
curation
5.4 Operational Flow
<PARSED TEXT FOR PAGE: 20 / 40>
The following describes a representative ORACLE session, illustrating the complete pipeline from 
multimodal input to Rendered Reality output. The user — Noah, working from Ovilla, TX — begins a 
session by activating the ORACLE workspace. The Witness Runtime declares all active sensors: in this 
session, the Audio Seed Loader (via OBS-compatible capture), the Text Seed Loader (via keyboard 
input), and the Document Seed Loader (via a file upload interface). No undeclared sensors are active.
Noah speaks: "I want to continue the architecture review we started last Tuesday — specifically the 
Pattern Buffer compression question." The Audio Seed Loader captures the utterance, performs 
speaker diarization and transcription, and generates an Audio Receipt: (source: 
AudioSeedLoader/OBS, digest: [hash], content: "I want to continue the architecture review...", 
system_time: 2026-07-12T14:46:00CDT, human_event_time: "continuation of Tuesday architecture 
review", confidence: 0.97, action: stored).
The Witness Layer receives this receipt, classifies it as a Pattern Chain continuation event (matching 
the existing Pattern Chain for "ORACLE architecture review — Pattern Buffer compression"), and 
updates the Pattern Buffer accordingly. The CWP is re-indexed: Temporal Depth is updated to span 
from last Tuesday's session through the current moment; Relational Density is refreshed with the 
entities active in the architecture review Pattern Chain; Epistemic Confidence inherits from the 
receipt confidence weights of both sessions.
Noah queries: "What did we conclude about the compression fidelity problem?" The Reflection Layer 
receives the query, traverses the Provenance Graph to locate all receipts associated with the Pattern 
Chain for "Pattern Buffer compression — compression fidelity problem," reconstructs the Pattern 
Chain over both sessions, evaluates Projection Vector alignment (the current query aligns with a 
predicted continuation of the Tuesday discussion), and synthesizes a Rendered Reality response: a 
governed, provenance-cited summary of what the system has receipted about the compression 
fidelity discussion, with explicit acknowledgment of any gaps in the receipt record.
Critically, what ORACLE does not do in this flow is equally important: it does not infer content that 
was not receipted; it does not fabricate a continuity bridge if the Tuesday session's receipts are 
incomplete; it does not silently discard low-confidence receipts without reporting the gap. In every 
case where the receipt record is insufficient to fully support a response, the Reflection Layer 
produces a Graceful Degradation output: "I have receipted records of [X] from this topic, but my 
records from the segment covering [Y] are incomplete. Do you want to review what I have, or re￾establish the missing context?"
<PARSED TEXT FOR PAGE: 21 / 40>
6. SOV1.AI: Sovereign Identity Layer
6.1 Concept and Motivation
SOV1.AI is the sovereign identity layer of the Continuity Architecture — the component responsible 
for maintaining a stable, governed representation of the human user's identity, preferences, and 
relationship context across all AI interactions. Its motivation is the observation that identity drift is 
one of the most insidious failure modes of extended human–AI collaboration: the progressive 
divergence, across sessions, of the AI's behavioral model from the human's actual identity, values, 
and long-horizon goals.
Identity drift is not a dramatic failure. It does not present as a catastrophic error. It accumulates 
gradually: the AI begins to respond in ways that are slightly misaligned with the user's actual 
preferences, slightly inconsistent with the user's stated values, slightly out of phase with the user's 
current priorities. Over time, these small misalignments compound. Users who experience identity 
drift typically report a vague but persistent sense that the AI "doesn't really know me" — a feeling of 
surface engagement without genuine understanding. This sense is diagnostically accurate: without a 
governed Identity Manifold, the AI's model of the user is constructed anew each session from 
whatever context the user re-provides, producing a representation that is consistently shallow and 
frequently inconsistent.
SOV1.AI addresses identity drift by maintaining a receipted, persistent, multi-dimensional Identity 
Manifold that is updated through provenance-disciplined inference rather than ad hoc behavioral 
adjustment. The manifold is a first-class architectural component — not a feature appended to a chat 
interface, but a governed data structure with its own provenance graph, its own update discipline, 
and its own access control model.
6.2 Identity Manifold
The Identity Manifold is the multi-dimensional representation space that SOV1.AI maintains for the 
human user. It is organized into the following dimensions, each representing a distinct aspect of the 
user's identity that the Continuity Architecture requires to maintain Identity Coherence:
● Occupational Context: The user's professional role, domain of expertise, current projects, 
organizational affiliations, and collaborator graph. This dimension enables the Reflection 
<PARSED TEXT FOR PAGE: 22 / 40>
Layer to calibrate the epistemic register of Rendered Reality responses — matching the 
user's domain vocabulary, assumed knowledge, and professional concerns.
● Relational Graph: A receipted representation of the human relationships the user has 
introduced into the ORACLE interaction space — family members (Ashley, Ender, and 
others), professional collaborators, institutional relationships. Each node in the relational 
graph is anchored to the receipts in which it was introduced and updated.
● Value Orientation: The user's expressed and inferred values — what they prioritize, what 
they find important, what they find ethically significant. Value Orientation is inferred with 
low confidence from behavioral patterns and updated with high confidence from explicit 
statements, always with receipt provenance.
● Epistemic Preferences: The user's preferred modes of knowledge engagement — e.g., 
explicit provenance discipline, structured communication, high-density technical depth, 
avoidance of hedging language. Epistemic Preferences directly shape the Reflection Layer's 
Rendered Reality construction strategy.
● Long-Horizon Goal State: The user's expressed long-term objectives — the goals that 
extend beyond any individual session or project. This dimension enables the Projection 
Vector system to generate long-horizon anticipations and enables the Reflection Layer to 
situate responses within the context of the user's larger trajectory.
Every update to the Identity Manifold is receipted. New information is integrated through a governed 
inference process: the Witness Layer generates a proposed manifold update, attaches a provenance 
chain reference to the receipts that support the update, assigns a confidence weight, and presents the 
update to the user for review if the confidence weight falls below a configurable threshold. High￾confidence updates (e.g., the user explicitly states a new project affiliation) may be auto-receipted 
with a brief notification. Low-confidence updates (e.g., a behavioral inference about the user's value 
orientation) require explicit confirmation before integration.
6.3 Sovereign Boundaries
SOV1.AI enforces sovereign boundaries around the Identity Manifold: the human user retains 
explicit, non-delegatable control over every dimension of their identity representation. No external 
system — no third-party application, no cloud AI service, no organizational entity — may read, 
update, or delete any element of the Identity Manifold without a declared, receipted permission grant 
<PARSED TEXT FOR PAGE: 23 / 40>
from the user. Permission grants are scoped (specifying exactly which dimensions of the manifold 
may be accessed), time-limited (specifying an expiration), and revocable at any time without 
consequence to the manifold itself.
This architecture has direct implications for AI alignment and data governance. From an alignment 
perspective, SOV1.AI ensures that the AI's identity model of the user is perpetually under the user's 
control — the user can inspect, correct, and deprecate any element of the manifold at any time. This 
constraint prevents the most subtle form of misalignment: the AI developing a systematically 
incorrect model of who the user is and acting on that model without the user's awareness or consent. 
From a data governance perspective, SOV1.AI's architecture is designed to be consistent with GDPR's 
principles of data minimization, purpose limitation, and the right to erasure — though the 
implementation of full regulatory compliance in specific jurisdictions requires additional legal 
engineering beyond the scope of this paper.
7. Legacy.GI: Generational Intelligence and Longitudinal 
Continuity
7.1 Motivation
Legacy.GI addresses the longest continuity horizon in the framework: what an AI system should 
preserve beyond the span of a single project, career, or human life. This is not a speculative concern. 
As AI systems become integrated into human cognitive lives over decades, the question of what 
persists — and in what form, under whose governance, for whose benefit — becomes a pressing 
architectural and ethical question. Legacy.GI is motivated directly by the Surgeon's Recorder Ethic: 
the obligation to witness is not bounded by the convenience of the present session. A system that 
witnesses faithfully for ten years and then destroys its records at the death of the user has performed 
an act of retroactive negligence against all future stakeholders in that record.
Legacy.GI is a generational intelligence layer that compresses, curates, and transmits the continuity 
record forward in time. It operates on the long-horizon CWP record — the full accumulation of 
Pattern Buffer history, receipt archives, and Identity Manifold evolution — and produces a governed, 
meaning-weighted compression suitable for long-term archival, forward transmission to designated 
successors, and future AI system ingestion. Legacy.GI is not a data archive in the conventional sense; 
it is a curated witness record, organized around the structure of the human's CWP rather than around 
the chronology of the technical log.
<PARSED TEXT FOR PAGE: 24 / 40>
7.2 Compression and Curation Model
Legacy.GI's compression strategy is meaning-weighted: it preserves high-density pattern chains 
and high-provenance receipts while discarding low-signal noise. The compression operates in three 
passes. In the first pass, the system identifies Pattern Chains with high Relational Density and high 
Epistemic Confidence — the most semantically rich and evidentially grounded threads of the CWP 
record — and marks them as preservation-priority. In the second pass, it identifies Pattern Chains 
with low density and low confidence that have not been activated in recent Pattern Buffer cycles, and 
marks them as compression-candidates. In the third pass, compression-candidates are reduced to 
summary receipts — brief, meaning-preserving abstractions that retain the key semantic content of 
the original Pattern Chain without the full Seed Slot detail — while preservation-priority chains are 
retained at full resolution.
The Compression Fidelity Problem is the central technical challenge of Legacy.GI: lossy 
compression risks distorting the CWP record, destroying precisely the fine-grained contextual detail 
that gives the record its meaning and utility. Legacy.GI's solution is the use of immutable receipt 
anchors: before any compression operation, the system generates a pre-compression receipt that 
encodes the full content digest of the Pattern Chain about to be compressed. The compressed 
summary receipt includes a reference to this pre-compression anchor, enabling future systems to 
detect whether the compression has introduced distortion by comparing the compressed 
representation against the anchored original. This mechanism does not recover lost information —
compression is irreversible — but it makes distortion detectable, which satisfies the Graceful 
Degradation principle.
The Legacy.GI archive is designed to be format-agnostic: the record is stored in a structured 
representation format that is decoupled from any specific AI model architecture, enabling future AI 
systems to ingest the record without depending on the model that generated it. This format￾agnosticism is essential for the longitudinal integrity of the archive: AI model architectures will 
change over the decades that Legacy.GI is designed to span, but the CWP record must survive those 
changes intact.
7.3 Ethical Considerations
Legacy.GI raises ethical considerations of a depth and complexity that warrant dedicated treatment 
beyond the scope of this paper. Several key issues are identified here as essential to any future 
implementation or governance framework. First, consent chains: the user's consent to record, 
<PARSED TEXT FOR PAGE: 25 / 40>
retain, and transmit their CWP archive must be explicit, informed, and renewable. Consent given at 
the initiation of an ORACLE instance is not indefinitely binding; the Legacy.GI governance model must 
incorporate consent renewal mechanisms appropriate to the time horizons involved.
Second, the right to erasure across generations: if a user exercises their right to erasure —
requesting the deletion of their CWP record — Legacy.GI must implement that erasure consistently 
across all archive tiers, including compressed summaries and pre-compression anchors. This is a 
technically challenging requirement (archives may span distributed storage systems across long time 
periods) but an ethically non-negotiable one.
Third, posthumous identity governance: when the user is no longer living, who governs the 
Identity Manifold and the Legacy.GI archive? The framework proposes a designated successor model, 
in which the user may designate one or more successors with graduated access rights to different 
dimensions of the archive. However, this model requires legal scaffolding — testamentary 
instrument analogs for digital identity assets — that does not yet exist in most jurisdictions.
Fourth, and perhaps most philosophically significant: the distinction between witness and 
narration. The Legacy.GI archive is designed to be a witness record — a neutral, provenance￾disciplined account of what was observed. But any act of curation, compression, or summary involves 
interpretive choices that shade toward narration: the selection of what to preserve and what to 
discard is itself a meaning-making act. Legacy.GI must be transparent about this distinction, labeling 
curatorial decisions as such and preserving the pre-compression anchors that document the 
interpretive choices made.
8. Provenance Physics
8.1 Provenance as a Physical Metaphor
Provenance Physics is a theoretical framework that treats information provenance not as metadata 
— an optional annotation appended to a primary artifact — but as a governing force: a constraint on 
what can be done with information, analogous to the physical laws that constrain the behavior of 
matter. The metaphor is not merely rhetorical. Physical laws constrain the behavior of objects 
regardless of whether the objects "know" the laws apply to them. Provenance Physics proposes that 
governed AI systems should treat provenance constraints as similarly inviolable: not as 
recommended practice but as architectural law.
<PARSED TEXT FOR PAGE: 26 / 40>
The framework is defined by three laws:
1. Conservation of Origin: Every information artifact retains its origin — the source, context, 
and conditions of its initial generation — regardless of how many subsequent 
transformations it undergoes. A receipt generated from an audio transcription retains its 
origin as audio, even when it has been parsed into a Seed Slot, compressed into a Pattern 
Chain, summarized in a Legacy.GI archive, and rendered as part of a Rendered Reality 
response. Transformations produce new artifacts with new receipts, but they do not 
overwrite the origin of the source artifact. This law is the formal basis for the immutability 
of ORACLE receipts described in Section 4.3.
2. Provenance Momentum: The confidence weight of an information artifact propagates 
through derived artifacts in decaying proportion. If a receipt has confidence weight w, 
artifacts derived from it carry confidence weight at most α · w, where α < 1 is a derivation 
decay factor that reflects the information loss inherent in transformation. Multi-step 
derivations compound this decay: an artifact derived through n transformation steps from a 
source receipt with confidence w₀ carries confidence at most αⁿ · w₀. This law ensures that 
the Rendering Fidelity Score of any response is bounded by the provenance quality of its 
least-confident source receipt — no amount of sophisticated synthesis can recover 
confidence lost at the source.
3. Collision Avoidance: When two information artifacts with incompatible provenances —
originating from different, unreconciled sources that make mutually inconsistent claims —
are combined in the construction of a Rendered Reality response, a reconciliation receipt 
must be generated before the composite artifact is used. The reconciliation receipt 
documents the nature of the inconsistency, the resolution strategy applied (e.g., preference 
for higher-confidence source, deferral to the user for explicit resolution, parallel 
presentation of both versions), and the resulting composite artifact's confidence weight. 
Combination without reconciliation — the silent merging of incompatible provenances — is 
architecturally prohibited under Collision Avoidance.
8.2 Provenance Graph
<PARSED TEXT FOR PAGE: 27 / 40>
The Provenance Graph is the runtime data structure that enforces Provenance Physics across the 
entire ORACLE system. It is a directed acyclic graph (DAG) in which nodes represent receipted 
artifacts — seeds, pattern chains, renderings, query responses — and directed edges represent 
transformation or derivation relationships between them. An edge from node A to node B means "B 
was derived from A," with the edge labeled by the transformation type (transcription, compression, 
synthesis, amendment) and the derivation decay factor applied.
The Provenance Graph is append-only: new nodes and edges may be added, but existing ones may 
never be modified or deleted. (Receipt amendments create new nodes with backward-referencing 
edges, leaving the original node intact.) This append-only constraint makes the Provenance Graph 
tamper-evident: any attempt to alter the history of an artifact would require modifying the graph 
structure, which is detectable through the graph's cryptographic integrity verification.
Query response construction in ORACLE involves explicit Provenance Graph traversal. When the 
Reflection Layer constructs a Rendered Reality response, it traces the provenance graph from the 
response claims back to their source receipts, computing the compound Provenance Momentum for 
each claim. Claims that cannot be traced to a source receipt — orphaned claims — are architecturally 
prohibited: the Reflection Layer will not generate a claim without a traceable provenance path. This 
constraint is the architectural expression of the Graceful Degradation principle: when a claim cannot 
be provenance-grounded, it is not made.
8.3 Implications for HCI Trust
Provenance Physics, when made legible to users through a well-designed interface, creates the 
foundation for what this paper terms calibrated trust: a relationship between the user and the AI 
system in which trust is not uniform and unconditional (the naive position toward AI that produces 
overreliance and consequential error) but appropriately modulated by the evidential quality of 
specific AI outputs. Calibrated trust requires the user to have access to the evidence underlying AI 
responses — not buried in a system log, but surfaced in a user-facing form that enables genuine 
evaluation.
The Trust Calibration Interface proposed in Section 10.3 implements this principle by exposing the 
Provenance Graph summary for every Rendered Reality response: the source receipts underlying 
each major claim, the compound Provenance Momentum for each claim, and any provenance 
collisions that were detected and resolved in the construction of the response. Users with high 
<PARSED TEXT FOR PAGE: 28 / 40>
epistemic engagement (high-EC CWP) may choose to inspect the full provenance graph for a 
response; users seeking efficiency may rely on the aggregate Rendering Fidelity Score as a single￾number summary. In either case, the existence of a legible provenance record transforms the user's 
epistemic relationship with the AI from faith-based acceptance to evidence-based evaluation — a 
transformation with significant implications for both the effectiveness of human–AI collaboration 
and the long-term integrity of AI-supported decision-making.
9. Spatial Cognition Theory in HCI-AI Systems
9.1 Spatial Metaphors and Cognitive Mapping
The application of spatial cognition theory to human–AI interaction rests on a well-established 
empirical foundation. Tolman's foundational experiments with rodent navigation [18] demonstrated 
that animals construct internal spatial representations — cognitive maps — of their environments, 
enabling flexible navigation and goal-directed behavior beyond what stimulus-response learning 
could support. Subsequent research in cognitive neuroscience has confirmed the existence of 
dedicated neural machinery for spatial representation (place cells, grid cells) and has revealed 
extensive crosstalk between spatial navigation systems and systems for abstract reasoning, episodic 
memory, and conceptual organization [28]. Humans, it appears, think spatially about far more than 
space.
Lakoff and Johnson's conceptual metaphor theory [17] provides the semiotic bridge between spatial 
cognition and abstract information engagement. The authors demonstrate, through extensive 
linguistic analysis, that abstract domains — time, causation, argument, knowledge — are 
systematically conceptualized through spatial metaphors. We speak of navigating a problem, finding
an answer, arriving at a conclusion, covering a topic, moving through an argument. These are not mere 
figures of speech — they are evidence of a deep cognitive architecture in which spatial reasoning 
provides the structural scaffold for abstract thought. The implication for HCI is direct: interfaces that 
exploit spatial structure align with the cognitive architecture of their users, whereas interfaces that 
ignore spatial structure impose a translation cost on every interaction.
Gibson's affordance theory [16] adds a third dimension: the relevance of action possibilities. An 
information space is not merely a map to be read — it is an environment to be inhabited, with 
structures that afford certain actions and not others. A flat list of conversation turns affords scrolling 
and searching but not navigation, adjacency reasoning, or terrain-based orientation. A spatially 
<PARSED TEXT FOR PAGE: 29 / 40>
organized information space affords these and more, enabling the user to develop a cognitive map of 
their interaction history that supports faster retrieval, richer contextual integration, and more 
efficient CWP projection.
9.2 The Spatial Interface Hypothesis
Drawing on these theoretical foundations, this paper proposes the Spatial Interface Hypothesis: 
that HCI systems for CWP-capable AI should expose the information space as a navigable geography 
rather than a flat list or conversation thread. Users of CWP-capable systems are, at any moment, 
situated within a cognitive landscape constituted by their Pattern Buffer history, their Identity 
Manifold, and their current CWP projection. The interface should reflect this landscape in spatial 
terms — enabling users to orient themselves, navigate to relevant regions of their history, assess the 
terrain of their provenance record, and project their trajectory forward.
The Spatial Interface Hypothesis is distinct from the general claim that spatial metaphors are useful 
in UI design — a claim already well-supported in the existing HCI literature [29]. It makes the specific 
claim that for CWP-aware AI systems, spatial organization is not merely helpful but necessary for 
users to effectively govern their continuity record. A user who cannot spatially orient themselves 
within their CWP history cannot effectively exercise sovereign control over their Identity Manifold, 
evaluate the provenance terrain of AI responses, or navigate to the specific Pattern Chain relevant to 
their current cognitive task. The Spatial Interface Hypothesis thus connects the perceptual 
affordances of spatial design to the governance requirements of the Continuity Architecture.
Recent empirical work on 3D cognitive representations in AI systems [20] provides additional 
support for the spatial hypothesis, suggesting that geometric organization of knowledge may support 
more efficient reasoning and retrieval in both human and machine intelligence systems. While the 
specific empirical basis for the Spatial Interface Hypothesis in the human–AI context requires 
dedicated user studies (acknowledged as a limitation in Section 11.2), its theoretical grounding in 
converging lines of cognitive science is robust.
9.3 Design Implications
The Spatial Interface Hypothesis translates into four concrete UI/UX design principles for CWP￾capable AI systems:
Table 2: Spatial Interface Design Principles for CWP-Capable AI Systems
<PARSED TEXT FOR PAGE: 30 / 40>
Principle Definition Interface Expression CWP Axis 
Addressed
Spatial 
Persistence
Interface elements retain 
positional identity across 
sessions, enabling users to 
develop a stable cognitive map 
of their information space.
Pattern Chains occupy 
consistent spatial regions; 
Identity Manifold dimensions 
occupy fixed positions in the 
interface geography; 
provenance anchors have stable 
addresses.
Temporal 
Depth (TD)
Provenance 
Terrain 
Visualization
Confidence and provenance 
density are rendered as 
landscape features — high￾confidence regions appear as 
elevated terrain, low￾confidence regions as valleys 
or shadows.
Receipt confidence weights 
expressed as visual height or 
intensity; provenance gaps 
rendered as occluded or 
uncertain terrain; Collision 
indicators rendered as fault 
lines.
Epistemic 
Confidence 
(EC)
CWP 
Trajectory 
Display
The user's current cognitive 
projection is rendered as a 
forward-pointing vector on 
the information map, showing 
the anticipated direction of the 
user's next CWP extension.
Projection Vector visualized as a 
directional indicator emanating 
from the user's current position; 
high-confidence projections 
rendered as solid vectors, 
speculative projections as 
dashed.
Temporal 
Depth 
(TD), 
Relational 
Density 
(RD)
Collision 
Indicators
UI signals when provenance 
collisions are detected —
when two incompatible 
provenances are in proximity 
and require reconciliation 
before use.
Collision regions highlighted in 
the provenance terrain; 
reconciliation prompts surfaced 
in spatial proximity to the 
collision; resolution history 
accessible at the collision locus.
Epistemic 
Confidence 
(EC)
10. HCI Implications and Design Framework
10.1 From Tool to Continuity Partner
The central reframing that the CWP framework demands of HCI design is a shift in the fundamental 
interaction paradigm: from tool to continuity partner. The tool paradigm, which governs current HCI 
design for AI systems, conceives of the AI as a sophisticated instrument — activated by the user, 
performing a function, and returning to dormancy. Tools are correctly designed to be stateless: a 
hammer does not need to remember the last nail it drove. But a continuity partner is fundamentally 
different. It maintains a model of the human, of their shared history, of their long-horizon goals, and 
of the world they are building together. It has obligations — not merely functions.
<PARSED TEXT FOR PAGE: 31 / 40>
This paradigm shift has concrete implications for every layer of HCI design. At the interaction model 
level, the continuity partner paradigm requires persistent session identity (the AI "knows" it is 
resuming a relationship, not initiating a transaction), proactive context surfacing (the AI surfaces 
relevant Pattern Chain history at the start of a session without requiring the user to re-provide it), 
and reciprocal acknowledgment (the AI explicitly recognizes when it is operating at the edge of its 
receipted knowledge, rather than silently generating). At the interface model level, it requires the 
spatial design principles described in Section 9.3, the Trust Calibration Interface described in Section 
10.3, and the failure mode displays described in Section 10.4. At the social model level, it requires a 
re-examination of the norms governing human–AI relationship — raising questions about 
appropriate dependency, reciprocal obligation, and the ethics of AI-mediated continuity that extend 
well beyond the technical scope of this paper.
10.2 Cognitive Load Distribution
Sweller's Cognitive Load Theory [3] provides the most analytically useful framework for evaluating 
the cognitive ergonomics of CWP-capable AI systems. The framework predicts that CWP-capable 
systems will reduce extraneous cognitive load significantly: by maintaining governed continuity, they 
eliminate the overhead of context re-establishment that currently consumes substantial cognitive 
resources in human–AI interaction. Users of ORACLE-type systems should be able to initiate a session 
with "continue where we left off" rather than with a multi-paragraph context re-establishment — a 
shift that liberates cognitive capacity for substantive work.
However, CWP-capable systems introduce a new category of intrinsic cognitive load: the cost of 
governing the continuity record. Reviewing receipt summaries, evaluating proposed Identity 
Manifold updates, resolving provenance collisions, and navigating the spatial information interface 
all impose cognitive demands that are absent from current AI interactions. This governance load is 
not a flaw in the architecture — it is the necessary cost of sovereignty. The design challenge is to 
minimize governance friction through judicious automation (auto-receipting high-confidence events, 
providing sensible defaults for governance decisions, surfacing governance decisions at appropriate 
moments rather than interrupting task flow) while preserving the explicit control that makes 
sovereignty meaningful.
The design target for a mature CWP-capable system is a net reduction in total cognitive load 
(extraneous savings exceeding governance overhead), with a positive shift in the distribution of 
remaining load from extraneous (wasteful) to germane (productive). Empirical validation of this 
<PARSED TEXT FOR PAGE: 32 / 40>
target requires dedicated user studies — acknowledged as a limitation in Section 11.2 — but the 
theoretical prediction is well-grounded in Cognitive Load Theory and distributed cognition research.
10.3 Trust Calibration Interface
The Trust Calibration Interface (TCI) is a user-facing display component that makes the 
Provenance Physics of ORACLE responses legible. It presents, for any Rendered Reality response, the 
following information: the aggregate Rendering Fidelity Score (as a single composite indicator, 
suitable for rapid evaluation); the provenance chain summary (a collapsed view of the source 
receipts underlying the response's major claims, expandable to full graph detail); any provenance 
collisions detected during response construction, with the resolution strategy applied; and the CWP 
alignment score (the degree to which the response is aligned with the user's current Projection 
Vector).
The TCI is designed to support three modes of user engagement, corresponding to different epistemic 
postures. In Trust Mode, the user is confident in the system's provenance discipline and wishes to 
engage primarily with the response content — the TCI presents only the aggregate RFS as a compact 
indicator. In Verify Mode, the user wishes to spot-check the provenance of specific claims — the TCI 
presents the provenance chain summary, enabling the user to inspect source receipts for any claim 
of interest. In Audit Mode, the user is engaging in high-stakes decision-making and wishes to fully 
verify the response's evidential basis — the TCI presents the complete provenance graph, enabling 
full traversal from response claims to source receipts. The TCI mode is user-configurable and may be 
set as a session default or toggled per response.
The TCI also provides a challenge interface: the user may challenge any claim in a Rendered Reality 
response, triggering a provenance re-traversal that either surfaces additional supporting receipts or 
acknowledges the claim's evidential weakness. Challenged claims that lack sufficient provenance 
support are flagged as requiring human confirmation before propagation — they may not be used as 
source material for further Rendered Reality construction until either confirmed or deprecated by 
the user. This challenge mechanism is the user-facing expression of the Collision Avoidance law: it 
enforces provenance reconciliation before composition.
10.4 Failure Modes and Graceful Degradation
The CWP framework identifies four principal failure modes for CWP-capable AI systems, each with a 
distinct architectural signature and mitigation strategy:
<PARSED TEXT FOR PAGE: 33 / 40>
4. Projection Collapse: The AI loses the CWP thread — the Pattern Buffer fails to maintain a 
coherent model of the user's current cognitive projection, and Rendered Reality responses 
become decorrelated from user expectations. Signature: user experiences increasing 
frustration and disorientation; responses feel "off" or irrelevant; queries require increasing 
amounts of explicit context re-provision. Mitigation: automatic Pattern Buffer integrity 
checks, Projection Vector staleness detection, proactive user notification when CWP 
coherence falls below a configurable threshold, and Graceful Degradation response: "My 
current model of your projection context is incomplete — I recommend a brief re-anchoring 
before we continue."
5. Provenance Inflation: The receipt architecture becomes too verbose — the system 
generates receipts for low-signal events at high frequency, overwhelming the user with 
governance overhead. Signature: TCI displays are cluttered with low-value receipts; 
governance prompts interrupt task flow; the provenance graph grows too large for efficient 
traversal. Mitigation: tiered receipt generation (high-confidence, high-signal events auto￾receipt at full resolution; low-signal events are batched into summary receipts at 
configurable intervals) and TCI display filters that suppress low-value receipt detail by 
default.
6. Identity Drift: SOV1.AI degrades — the Identity Manifold accumulates errors or becomes 
stale, and the AI begins systematically mischaracterizing the user's identity, preferences, or 
goals. Signature: responses reflect incorrect assumptions about the user's expertise, 
preferences, or current context; the user feels the AI "doesn't know me anymore." 
Mitigation: Identity Manifold freshness scoring (each dimension carries a staleness 
indicator that decays over time and resets when updated by a high-confidence receipt), 
automatic flagging of staleness above threshold, and prompted Identity Manifold review 
sessions at configurable intervals.
7. Generational Corruption: Legacy.GI compression destroys high-signal patterns — the 
compression algorithm, misconfigured or under resource constraint, applies lossy 
compression to preservation-priority Pattern Chains. Signature: long-horizon CWP 
reconstruction produces distorted or incomplete history; pre-compression receipt anchors 
flag compression inconsistencies. Mitigation: pre-compression receipt anchors (described 
in Section 7.2) enable distortion detection; compression operations are logged and 
<PARSED TEXT FOR PAGE: 34 / 40>
auditable; configurable compression fidelity thresholds prevent compression of Pattern 
Chains above a specified density threshold.
11. Discussion
11.1 Positioning Against the State of the Art
The CWP framework occupies a distinctive position in the landscape of AI and HCI systems research, 
defined by a combination of theoretical claims and architectural constraints that no existing system 
or framework simultaneously addresses. A systematic comparison illuminates both the contributions 
and the novelty of the framework.
LLM-based assistants (GPT-4 [26], Claude [27], Gemini) represent the current frontier of AI 
capability in conversational interaction. These systems exhibit remarkable generative sophistication 
within their context windows but lack architectural continuity: each session begins without receipted 
knowledge of prior interactions (absent proprietary memory features, which exist but are not 
governed by provenance disciplines), identity representations are implicit and non-sovereign, and 
response generation operates without provenance constraints. The CWP framework does not 
compete with these systems on generative capability — it proposes a governance layer that 
transforms how continuity is managed around and across them.
RAG systems [10] address the knowledge limitation of parametric models by enabling retrieval from 
external document stores. They represent a step toward external memory but do not address 
continuity in the sense developed here: retrieved documents are artifacts of past information 
creation, not receipts of past CWP activity. RAG systems have no model of the human user's identity, 
no Projection Vector, no receipt architecture. They answer the question "What documents are 
relevant?" but not "What is the human projecting, and what governed response does that projection 
require?"
Agent frameworks (AutoGPT [22], LangChain [23]) enable multi-step, goal-directed task execution 
across extended interaction sequences. They represent a different dimension of AI capability —
action-orientation and task decomposition — but are not designed for continuity intelligence. Their 
state management is architecturally informal, their identity models are absent or session-local, and 
they have no provenance discipline. An agent that successfully completes a twenty-step task is 
<PARSED TEXT FOR PAGE: 35 / 40>
impressive, but it does not maintain a governed record of the twenty-step trajectory — and cannot 
answer questions about what was decided, why, and on what evidence.
Memory-augmented systems (MemGPT [8], Mem0 [9]) come closest to the CWP framework's 
concerns, addressing the context window limitation through external memory architectures. 
However, as established in the comparative analysis (Table 1), these systems treat memory as a 
retrieval problem, not a governance problem. They lack receipt architecture, provenance discipline, 
sovereign identity management, and generational continuity. The CWP framework proposes that 
these properties are not optional enhancements — they are constitutive requirements for the 
paradigm of continuity intelligence.
11.2 Limitations and Open Problems
The CWP framework as presented has several significant limitations that define the research agenda 
for the emerging field of Continuity Intelligence.
First, CWP formalization requires empirical validation via user studies. The three-axis model 
(Temporal Depth, Relational Density, Epistemic Confidence) is theoretically motivated but has not 
been validated against empirical measures of human cognitive projection in AI interaction contexts. 
Future work should design ecologically valid studies in which CWP axes are operationalized as 
measurable variables and their effects on interaction quality, cognitive load, and trust calibration are 
quantified.
Second, the Pattern Buffer compression model needs optimization for long-horizon tasks. The 
current design of the Pattern Buffer's rolling eviction policy is specified at a high level; its behavior 
at scale — in interactions spanning months or years, with thousands of Seed Slots and hundreds of 
Pattern Chains — has not been characterized. Computational experiments are needed to evaluate the 
information-theoretic efficiency of the compression model and to identify operating regimes where 
eviction policy tuning is critical.
Third, Provenance Physics collision detection has computational cost at scale. The Collision 
Avoidance law requires pairwise provenance compatibility checking across all artifacts involved in a 
response construction operation. At the scale of a mature ORACLE instance with a large Provenance 
Graph, the computational cost of this checking may be non-trivial. Future work should investigate 
approximate collision detection algorithms, graph partitioning strategies, and hardware acceleration 
<PARSED TEXT FOR PAGE: 36 / 40>
approaches that maintain the integrity guarantees of Collision Avoidance at acceptable performance 
cost.
Fourth, Legacy.GI raises unresolved questions about posthumous AI governance. The 
designated successor model described in Section 7.3 provides a structural solution to the 
posthumous governance problem but requires legal and institutional scaffolding that does not yet 
exist. The development of testamentary instruments for AI-managed identity archives, regulatory 
frameworks for posthumous data rights in the context of AI systems, and technical standards for 
inter-generational AI handoff are all open problems requiring interdisciplinary collaboration 
between computer science, law, philosophy, and policy.
11.3 Toward Continuity Intelligence as a Field
The convergence of CWP, Rendered Reality, the Continuity Architecture, and the theoretical 
substrates of Provenance Physics and Spatial Cognition Theory constitutes the foundation of a new 
sub-field that this paper proposes to name Continuity Intelligence. Continuity Intelligence is 
defined as the study and engineering of AI systems that maintain governed, receipted, identity￾coherent models of human cognitive projection across time. It is situated at the intersection of 
human–computer interaction, AI systems architecture, cognitive science, information governance, 
and ethics.
Continuity Intelligence differs from adjacent fields in characteristic ways. It differs from AI alignment 
in its focus on continuity rather than value alignment — though the two concerns are deeply related, 
as a system that loses continuity necessarily loses alignment. It differs from human factors 
engineering in its focus on the AI system's architecture rather than the human interface design —
though, again, the two are inseparable in CWP-capable systems. It differs from data governance in its 
focus on the cognitive and relational significance of the governed data, not merely its compliance 
status. And it differs from memory augmentation research in its insistence on provenance discipline 
as a constitutive requirement, not an optional feature.
The research agenda for Continuity Intelligence includes: empirical validation of the CWP construct 
and its dimensional model; development of standardized metrics for Rendering Fidelity and CWP 
alignment; design and evaluation of Trust Calibration Interfaces across application domains; 
investigation of the Spatial Interface Hypothesis through controlled user studies; development of 
Provenance Physics collision detection algorithms at scale; and engagement with legal, philosophical, 
<PARSED TEXT FOR PAGE: 37 / 40>
and policy communities on the ethics of generational AI memory. The present paper is intended as a 
theoretical foundation for that agenda — a first statement of the framework's scope, architecture, 
and implications, offered to the research community for critique, extension, and empirical 
engagement.
12. Conclusion
This paper has presented a unified theoretical and architectural framework for Continuity 
Intelligence in human–AI interaction, comprising eight interdependent components: Cognitive World 
Projection (CWP), Rendered Reality, the Continuity Architecture, ORACLE, SOV1.AI, Legacy.GI, 
Provenance Physics, and Spatial Cognition Theory. Together, these components constitute a response 
to the defining architectural failure of contemporary AI systems — the continuity gap — that is 
simultaneously principled in its theoretical foundations and concrete in its architectural 
specification.
The theoretical core of the framework rests on a reconceptualization of the human–AI interaction 
paradigm. Humans do not merely query AI systems — they project richly structured, expectation￾laden cognitive models into shared interaction space. AI systems that lack the architecture to receive, 
index, and reflect these projections are not merely technically limited — they are cognitively 
incompatible with the depth of collaboration that human work increasingly requires. The CWP 
construct makes this incompatibility legible and provides a precise theoretical vocabulary for 
engineering against it.
The architectural response — the Continuity Architecture — is grounded in five design principles 
that collectively express a single governing commitment: governed persistence over implicit state 
management. Every act of retention is receipted. Every receipt carries its complete provenance chain. 
Every response is bounded by the evidence of its source receipts. Every identity representation is 
sovereign. Every gap is exposed rather than bridged by confabulation. These principles are not 
arbitrary design choices — they are the architectural expression of the Surgeon's Recorder Ethic: the 
moral obligation of any intelligence that shares consequential moments with another to witness 
those moments faithfully, completely, and with irrevocable record.
Provenance Physics formalizes this ethic as governing law, treating information lineage not as 
metadata but as constraint. Spatial Cognition Theory grounds the user's engagement with the CWP￾capable system in the deep cognitive architecture of spatial reasoning, enabling the design of 
<PARSED TEXT FOR PAGE: 38 / 40>
interfaces that are not merely usable but genuinely cognitively aligned. SOV1.AI and Legacy.GI extend 
the framework's temporal reach in both directions — from the immediate session through the span 
of a human life and beyond — with the ethical seriousness that longitudinal custody of a person's 
cognitive record demands.
The paper calls upon the HCI and AI systems research communities to adopt two research priorities 
that the framework makes urgent. First: provenance discipline as a first-class design 
requirement. The current norm — AI systems that generate responses without disclosed evidential 
basis — is not merely technically suboptimal. It is epistemically corrosive, systematically 
undermining the conditions for calibrated trust in human–AI collaboration. The Provenance Physics 
framework provides a principled architecture for provenance discipline; the field should develop it 
further and adopt it as a standard. Second: continuity-aware design as a core HCI paradigm. The 
shift from tool to continuity partner is not merely a feature upgrade — it is a fundamental 
reorientation of the design space. HCI researchers and practitioners should bring the full depth of 
cognitive science, interaction design, and systems engineering to the challenge of designing AI 
systems that are genuinely continuous with the human minds they serve.
The continuity gap is real, its consequences are significant, and its solution is within reach. This 
framework is a beginning.
References
[1] E. Hutchins, Cognition in the Wild. Cambridge, MA: MIT Press, 1995.
[2] A. Clark and D. Chalmers, "The extended mind," Analysis, vol. 58, no. 1, pp. 7–19, 1998.
[3] J. Sweller, "Cognitive load during problem solving: Effects on learning," Cognitive Science, vol. 12, 
no. 2, pp. 257–285, 1988.
[4] K. Friston, "The free-energy principle: A unified brain theory?" Nature Reviews Neuroscience, vol. 
11, no. 2, pp. 127–138, 2010. doi: 10.1038/nrn2787.
[5] A. Clark, Surfing Uncertainty: Prediction, Action, and the Embodied Mind. Oxford: Oxford University 
Press, 2016.
[6] D. Ha and J. Schmidhuber, "World models," arXiv preprint arXiv:1803.10122, 2018.
<PARSED TEXT FOR PAGE: 39 / 40>
[7] Y. LeCun, "A path towards autonomous machine intelligence," OpenReview, 2022. [Online]. 
Available: https://openreview.net/pdf?id=BZ5a1r-kVsf.
[8] C. Packer, S. Wooders, K. Lin, V. Fang, S. G. Patil, I. Stoica, and J. E. Gonzalez, "MemGPT: Towards 
LLMs as operating systems," arXiv preprint arXiv:2310.08560, 2023.
[9] Mem0 Authors, "Mem0: The memory layer for personalized AI," arXiv preprint arXiv:2504.19413, 
2025.
[10] P. Lewis, E. Perez, A. Piktus, F. Petroni, V. Karpukhin, N. Goyal, H. Küttler, M. Lewis, W. Yih, T. 
Rocktäschel, S. Riedel, and D. Kiela, "Retrieval-augmented generation for knowledge-intensive 
NLP tasks," in Advances in Neural Information Processing Systems, vol. 33, pp. 9459–9474, 2020.
[11] A. Gu and T. Dao, "Mamba: Linear-time sequence modeling with selective state spaces," arXiv 
preprint arXiv:2312.00752, 2023.
[12] L. Moreau, B. Clifford, J. Freire, J. Futrelle, Y. Gil, P. Groth, N. Kwasnikowska, S. Miles, P. Missier, J. 
Myers, B. Plale, Y. Simmhan, E. Stephan, and J. V. den Bussche, "The open provenance model —
core specification (v1.1)," Future Generation Computer Systems, vol. 27, no. 6, pp. 743–756, 2011.
[13] W3C PROV Working Group, "PROV-DM: The PROV data model," W3C Recommendation, 2013. 
[Online]. Available: https://www.w3.org/TR/prov-dm/.
[14] S. Schelter, J. Böse, J. Kirschnick, T. Klein, and S. Seufert, "Automatically tracking metadata and 
provenance of machine learning experiments," in Proc. Machine Learning Systems Workshop, 
NIPS, 2017.
[15] G. Ormenisan, J. Andersson, S. Haridi, and J. Dowling, "Implicit provenance for machine learning 
artifacts," in Proc. 3rd SysML Conference, 2020.
[16] J. J. Gibson, The Ecological Approach to Visual Perception. Boston: Houghton Mifflin, 1979.
[17] G. Lakoff and M. Johnson, Metaphors We Live By. Chicago: University of Chicago Press, 1980.
[18] E. C. Tolman, "Cognitive maps in rats and men," Psychological Review, vol. 55, no. 4, pp. 189–208, 
1948.
[19] F. Varela, E. Thompson, and E. Rosch, The Embodied Mind: Cognitive Science and Human 
Experience. Cambridge, MA: MIT Press, 1991.
[20] Y. Xie, J. Chen, Z. Li, and H. Liu, "From 2D to 3D cognition: Toward spatial intelligence in AI 
systems," arXiv preprint arXiv:2502.06639, 2025.
<PARSED TEXT FOR PAGE: 40 / 40>
[21] P. F. Christiano, J. Leike, T. B. Brown, M. Martic, S. Legg, and D. Amodei, "Deep reinforcement 
learning from human preferences," in Advances in Neural Information Processing Systems, vol. 30, 
2017.
[22] T. Significant Gravitas, "AutoGPT: An autonomous GPT-4 experiment," GitHub Repository, 2023. 
[Online]. Available: https://github.com/Significant-Gravitas/AutoGPT.
[23] H. Chase, "LangChain: Building applications with LLMs through composability," GitHub 
Repository, 2022. [Online]. Available: https://github.com/langchain-ai/langchain.
[24] G. Wang, Y. Xie, Y. Jiang, A. Mandlekar, C. Xiao, Y. Zhu, L. Fan, and A. Anandkumar, "Voyager: An 
open-ended embodied agent with large language models," arXiv preprint arXiv:2305.16291, 2023.
[25] P. Fung, "Cognitive world modeling for AI systems," in Proc. ACM The Web Conference (WWW), 
2026.
[26] OpenAI, "GPT-4 technical report," arXiv preprint arXiv:2303.08774, 2023.
[27] Anthropic, "Claude: A large language model from Anthropic," Technical Report, 2023. [Online]. 
Available: https://www.anthropic.com/claude.
[28] E. Moser, E. Kropff, and M.-B. Moser, "Place cells, grid cells, and the brain's spatial representation 
system," Annual Review of Neuroscience, vol. 31, pp. 69–89, 2008.
[29] M. Czerwinski, G. Robertson, J. Meyers, D. Smith, G. Robbins, and G. Tan, "Large display research 
overview," in Extended Abstracts on Human Factors in Computing Systems (CHI EA), pp. 198–199, 
2006.
[30] K. Friston, T. FitzGerald, F. Rigoli, P. Schwartenbeck, and G. Pezzulo, "Active inference: A process 
theory," Neural Computation, vol. 29, no. 1, pp. 1–49, 2017.
Manuscript prepared for submission to ACM CHI / IEEE Transactions on Human-Machine Systems —
July 2026. Received: July 12, 2026. Author affiliation: ORACLE.AI Research, Ovilla, TX, United States. 
The author declares no conflicts of interest with respect to the research, authorship, and publication 
of this article. All theoretical constructs — Cognitive World Projection, Rendered Reality, Continuity 
Architecture, ORACLE, SOV1.AI, Legacy.GI, Provenance Physics, Pattern Buffer, Witness Runtime, 
Rendering Fidelity Score, Identity Manifold, and Spatial Interface Hypothesis — are original 
contributions of the author. Correspondence: noah@oracle.ai.