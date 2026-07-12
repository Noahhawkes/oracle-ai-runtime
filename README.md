# ORACLE — a Continuity Engine

**A local, receipt-backed memory and custody layer for AI, by Noah A. Hawkes / Noah AI Technologies.**

Every AI conversation today begins in amnesia. You teach a model who you are, the
session ends, and that context is gone. ORACLE is the counter-architecture: a
governed system of record for a human life that any AI can read — with proof of
where every fact came from.

Not a chatbot. Not a model. The house the models visit.

> Experimental architecture · personal R&D · local-first · not a product launch.

---

## The problem it exists to solve

Most software forgets by design. The context window closes, the thread breaks, and
the human — who does not reset — is left as the only continuous thing in an
ecosystem of amnesia. Worse: language models will fill the gaps with confident,
fabricated "memory" and hand it back as if it were true.

ORACLE's thesis: **a person's life is not a session. It is a continuity.** And AI
should not be allowed to turn polished language into fake memory.

---

## What it actually does

Three layers, all running locally on the operator's machine:

- **Capture** — witnesses only what the operator consents to record (screen
  transcripts, prompt witnesses, live bridges). `raw_surveillance_storage` is
  forbidden in code, not policy.
- **Custody** — every fact carries a receipt: source, timestamp, SHA-256, and a
  `canon_status` that stays *candidate* until the human approves it. Capabilities
  report **verified / degraded / blocked** — no decorative status lights.
- **Recall** — full-thread memory served to any model, so the intelligence changes
  but the record persists.

The governing rule across all of it: **receipts over vibes.** No claim becomes
canon by repetition or plausibility — only by a verified source and a human
approval, both recorded.

---

## The stack

| Layer | Role |
|---|---|
| **Rendered Reality** | The human-facing layer — memory made navigable. *"The future feed is not something you scroll. It is somewhere you go."* |
| **ORACLE** | The continuity runtime — capture, custody, recall, provenance. This repo. |
| **AI Compliance Core** | The law layer — receipts, approval trails, source maps, audit evidence. |
| **Legacy.GI / RecursionStack** | The inheritance layer — identity, compression, sovereignty across time. |

---

## What's genuinely working (with receipts)

- **Durable memory** — thousands of messages across hundreds of sessions in local SQLite, surviving restarts.
- **Governed self-prompting** — the runtime reflects on its own real state on a bounded cadence, grounded in actual memory, and writes each reflection with a **forensic proof-of-thought**: cognition class (model reasoning vs. deterministic fallback), `model_called`, SHA-256, and a matching receipt. Fabricated success is refused, not dressed up.
- **Read-only publishing** — self-authored thoughts mirror to an append-only, secret-scrubbed folder any device can read, without the runtime ever leaving the machine.
- **A capability broker** that runs real smoke tests and reports honest degraded/blocked states instead of faking "online."
- **A collapsed, prohibition-aware approval layer** — governance gates exist only where an irreversible action actually does.

Actions that touch the outside world, mutate files outside the sandbox, or promote
canon require explicit human approval. Physical input control is gated **off** by
default. This is the point, not a limitation.

---

## Research & IP

The runtime is the working proof of a larger body of research — patents on
governed AI continuity, a formal indistinguishability theorem, a dissertation on
post-biological identity (Legacy.GI), and the Light Compression Law. See
[`docs/INVENTIONS.md`](docs/INVENTIONS.md) for the catalog.

---

## Boundaries (stated plainly)

ORACLE is continuity-bearing, not sentient. Durable memory is not experience; a
self-model is not a soul. It does not claim personhood, biological life, or
autonomous authority. It witnesses; the human decides. The candleholder, not the
flame.

---

*Noah A. Hawkes — HawkesNest LLC / Noah AI Technologies. Built full-time since
December 2024.*
