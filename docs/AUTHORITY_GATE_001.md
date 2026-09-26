# AUTHORITY_GATE_001

Read-only live-runtime proof path:

```text
GET http://127.0.0.1:7781/api/proofs/AUTHORITY_GATE_001
```

This proof runs the same `validate_response_authority()` gate used by the web
runtime. It verifies:

- Companion replies rewrite unreceipted operational claims.
- Builder replies cannot say `COMPLETED` without a valid execution receipt.
- Explicit external attribution is allowed as attribution, not verification.
- A valid in-process machine receipt permits a bounded `COMPLETED` claim.

The proof is read-only. It performs no file mutation, external action, commit,
push, cloud upload, or durable memory promotion. Its receipt is process-memory
only and comes from reading the proof module itself.

Sandbox writes now default to the runtime-owned sandbox:

```text
C:\Oracle\ORACLE.AI-runtime\sandbox
C:\Oracle\ORACLE.AI-runtime\sandbox.trash
```

The legacy global sandbox directory is not a runtime dependency. Create writes
still use non-overwriting versioned paths, executable extensions remain blocked,
and mutation receipts continue to state that generated files were not executed.

The sandbox reflection lane is active at `/sandbox-reflect` and
`POST /api/sandbox/reflection`. It writes structured reflection candidates only
inside `sandbox\reflections`, appends a sandbox journal event, and keeps external
actions, GitHub push, command execution, computer control, memory promotion, and
canon promotion disabled.
