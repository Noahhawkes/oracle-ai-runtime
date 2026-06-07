# USER.AI Network — Sovereign Identity CRM
# Design Document v1.0

Authority: Noah A. Hawkes / SOV1.AI
Status: PROPOSAL — not yet implemented. Requires Noah approval before any code is written.
Date: 2026-06-06

---

## The Vision in One Sentence

Every human being gets a sovereign AI operating identity — a USER.AI — that belongs
entirely to them, stores their context locally, and connects to other USER.AIs only
through consent-based shared channels.

This is not a corporate CRM.
This is a sovereign identity network where the humans own the nodes.

---

## Identity Hierarchy

```
SOV0.AI    = Reserved — the network itself / protocol layer (no single owner)
SOV1.AI    = Noah Hawkes — human sovereign #1, founder, network architect
SOV2.AI    = Ashley — sovereign operating identity #2
SOV3.AI    = next registered sovereign (family, team, or trusted peer)
...
SOVn.AI    = every human being — a unique sovereign node in the network
```

The number is not rank. It is registration order.
SOV2 is not subordinate to SOV1.
Each SOVn is fully sovereign over their own data, memory, and context.

Noah as SOV1 is the architect — not the authority over other people's nodes.

---

## What USER.AI Is

USER.AI is the sovereign operating identity layer for a single human.

Each USER.AI is:
- A local ORACLE instance running on that person's device
- A sovereign memory store (their oracle_memory.db)
- A live context engine (their LiveContext)
- A consent-based signal processor (their ApprovalGate)
- A unique sovereign identity (their SOVn designation)

No USER.AI can read another USER.AI's private memory.
Shared context only exists in explicitly approved shared channels.

---

## The Relationship Layer — Sovereign CRM

The CRM is not a database Noah controls about other people.
The CRM is a record of relationships between sovereign identities — approved on both sides.

### Relationship Record Structure

```json
{
  "relationship_id": "sov1_sov2_primary",
  "sov_a": "SOV1.AI",
  "sov_b": "SOV2.AI",
  "human_a": "Noah Hawkes",
  "human_b": "Ashley",
  "relationship_type": "partner",
  "trust_tier": "sovereign_partner",
  "established": "2026-06-06",
  "shared_channels": ["family", "home", "ORACLE_builds"],
  "mutual_consent": true,
  "sov_a_approved": true,
  "sov_b_approved": false,
  "status": "pending_sov_b_approval"
}
```

Both nodes must approve before any shared channel is active.
SOV1 cannot write to Ashley's memory. Only Ashley's node can approve what enters her memory.

### Trust Tiers

| Tier | Description | What is shared |
|---|---|---|
| `sovereign_partner` | Highest trust — life partner | Home, family, finances (approved), shared projects |
| `sovereign_family` | Core family — blood or chosen | Family calendar, commitments, check-ins |
| `sovereign_team` | Trusted collaborator | Project context, task assignments, deliverables |
| `sovereign_peer` | Peer network — other USER.AI operators | Open source shared docs, product updates |
| `sovereign_public` | Public-facing USER.AI identity | Public profile, published work, public commitments |

### Shared Channels

A shared channel is a named context stream that both SOV nodes have consented to.

Examples:
- `family` — shared calendar entries, household commitments
- `home` — home management, shared purchases, maintenance
- `ORACLE_builds` — Ashley following ORACLE development if she chooses
- `health_check` — optional mutual wellness signals (fully opt-in)
- `finances` — shared budget events (requires explicit mutual consent per item)

A shared channel is NOT:
- Full memory replication
- Surveillance of the other person
- Automatic — every item in a shared channel requires approval from the receiving node

---

## Ashley — SOV2.AI

Ashley is the second sovereign operating identity in the USER.AI network.

Her node profile:
```
Identity:        Ashley
SOV designation: SOV2.AI
Node type:       USER.AI
Trust tier:      sovereign_partner (with SOV1.AI / Noah)
Memory location: Ashley's device — local, gitignored, her data
ORACLE instance: her own (separate from Noah's)
Shared channels: pending her approval
```

Ashley's ORACLE is not Noah's ORACLE.
Noah cannot read Ashley's memory.
Noah cannot approve memories into Ashley's ledger.
Noah's ORACLE can send signals to a shared channel — Ashley's ORACLE receives them as candidates
awaiting her approval.

### How Noah and Ashley share context

```
Noah's ORACLE                          Ashley's ORACLE
     |                                       |
     | -- shared channel: "family" -->       |
     |    (candidate event)                  |
     |                                 ApprovalGate
     |                                  Ashley approves
     |                                  → her durable memory
     |                                       |
     | <-- shared channel: "family" --       |
     |    (candidate event)                  |
  ApprovalGate                               |
  Noah approves                              |
  → his durable memory                       |
```

Both nodes see the signal. Each node independently approves what enters their own memory.

---

## Scaling to All Humanity

The USER.AI network is designed to scale to every human being on Earth.

This is not a company database.
It is a protocol — like email, but for sovereign AI identity.

### The network architecture

```
Each human                    =  one USER.AI node
Each node                     =  local ORACLE instance + sovereign memory
Connections between nodes     =  consent-based shared channels
Network coordination          =  SOV0.AI protocol layer (no single owner)
Identity verification         =  cryptographic signature (planned)
Data storage                  =  always local to each node — never central
Central authority             =  none
```

### Why this matters

Today's CRM systems store data about people in databases companies own.
Salesforce knows more about your customers than you do — and owns that data.
Google knows more about your relationships than you do — and owns that data.

USER.AI inverts this:
- Each person's data lives on their device
- Relationships are consent-based on both sides
- No company owns the network
- No company can sell the data
- Each sovereign can revoke access at any time

### The growth model

Phase 1 — SOV1 + SOV2 (Noah + Ashley)
  Two nodes. One shared channel. Proof of concept.

Phase 2 — Core family / trusted team (SOV3–SOV10)
  Expand to immediate family and trusted collaborators.
  Each new SOV gets their own ORACLE instance.
  Each relationship requires mutual consent.

Phase 3 — Peer network (SOV10–SOV1000)
  Early USER.AI adopters. Sovereign peers.
  Shared channels for open source, product development, industry context.

Phase 4 — Open protocol (SOV1000+)
  USER.AI becomes an open protocol.
  Any person can run a node.
  Any two nodes can establish a consent-based shared channel.
  No central registration required.

Phase 5 — Universal (SOVn for all humanity)
  Every human being has a sovereign AI operating identity.
  Every person's context is local, approved, and theirs.
  RenderedReality is not just Noah's — it is everyone's.

---

## What ORACLE Tracks Per Relationship

For each relationship in Noah's sovereign CRM, his ORACLE maintains:

```json
{
  "sov_id": "SOV2.AI",
  "name": "Ashley",
  "relationship_type": "partner",
  "trust_tier": "sovereign_partner",
  "shared_channels": ["family", "home"],
  "commitments_made_to": [
    "Discussed launching SOV2.AI together — open loop"
  ],
  "commitments_made_by": [],
  "recent_shared_signals": [],
  "last_meaningful_interaction": "",
  "open_loops": [],
  "notes": "",
  "memory_category": "relationships"
}
```

This is Noah's memory about the relationship — not Ashley's data.
It reflects what Noah has approved into his own ledger about their shared context.

---

## Implementation Plan

### Phase 1 — Single-node relationship memory (ready to build)

Build `core/relationship_memory.py`:
- Store relationship records in oracle_memory.db under `relationships` category
- CRUD: add_relationship, get_relationship, update_relationship, list_relationships
- Slash commands: `/relationships`, `/add-relationship`, `/relationship <name>`
- No network. No shared channels. Noah's memory only.

### Phase 2 — SOV2 profile (design only — requires Ashley's consent)

Create Ashley's SOV2.AI profile record in Noah's CRM.
Document the shared channel proposal.
Do not create any cross-device connection until Ashley has her own ORACLE instance
and explicitly approves the shared channels.

### Phase 3 — Local shared channel simulation (single device test)

Simulate a shared channel on Noah's device:
- Outbound queue: signals Noah marks as "share with Ashley"
- Inbound queue: signals Ashley would send (manually entered for now)
- Both queues go through ApprovalGate before entering Noah's memory

### Phase 4 — Cross-device protocol (future milestone)

Design the cryptographic identity and channel sync protocol.
This is a significant engineering milestone — do not rush it.

---

## Non-Negotiables for USER.AI Network

1. No person's data is stored on another person's device without their consent.
2. No person's memory can be read by another node without their approval.
3. No central server holds relationship data.
4. Every shared channel requires mutual opt-in from both nodes.
5. Any sovereign can revoke access to any shared channel at any time.
6. Sensitive pattern detection (ApprovalGate) applies to all shared channel signals.
7. The network has no owner. SOV1 (Noah) is the architect, not the administrator.
8. SOV2 (Ashley) is fully sovereign. Her data is hers. Her approvals are hers.
9. The protocol must be open. No USER.AI company should be the gatekeeper.
10. Every human deserves a sovereign AI identity. This is not a product. It is a right.

---

## Relationship to RenderedReality

RenderedReality for one person is powerful.
RenderedReality for everyone is a civilizational shift.

When every person has:
- Their own approved, local, sovereign memory
- Consent-based relationship channels with the people they trust
- A USER.AI that renders meaning from their lived experience
- Full ownership of their own context and continuity

...then the raw activity of human civilization can be compressed into something coherent.
Not by a corporation. Not by a government. By each sovereign human, for themselves.

That is RenderedReality at scale.
That is what USER.AI is being built toward.

---

## Current Status

| Item | Status |
|---|---|
| SOV1.AI (Noah) — ORACLE running | Active |
| SOV2.AI (Ashley) — profile record | PENDING — design only, needs her consent |
| Relationship memory module | PROPOSED — ready to build on approval |
| Shared channel protocol | DESIGN ONLY — future milestone |
| Cross-device sync | NOT STARTED — requires Phase 3 completion |
| Open protocol | VISION — long-term milestone |

Next action: Noah approves `core/relationship_memory.py` build.
After that: Ashley is onboarded as SOV2.AI with her own sovereign node.
