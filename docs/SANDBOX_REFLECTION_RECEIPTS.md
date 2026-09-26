# Sandbox Reflection Receipts

Status: Live

ORACLE has a governed reflection-writing lane inside the runtime sandbox:

```text
C:\Oracle\ORACLE.AI-runtime\sandbox\reflections
C:\Oracle\ORACLE.AI-runtime\sandbox\journal\oracle_journal.jsonl
```

This lane exists so ORACLE can practice the bounded executive loop:

```text
perceive -> classify -> plan -> reflect
```

## Commands

```text
/sandbox-reflect <reflection receipt text or key: value lines>
/reflection-receipt <reflection receipt text or key: value lines>
```

## API

```text
POST /api/sandbox/reflection
```

Accepted JSON:

```json
{
  "receipt": {
    "what_changed": "commit ba896c4, 94 dirty file(s)",
    "what_is_stuck": "GitHub access, STT, qr_scan, web_access, external_send, command_exec",
    "what_noah_is_trying": "give ORACLE governed executive function without unrestricted autonomy",
    "safe_next_action": "patch routing before polishing doctrine",
    "requires_approval": "state-changing actions, canon promotion, external send, computer control",
    "leave_untouched": "the live autostart server, the signed-commit policy, anything out of scope",
    "highest_value_next": "patch routing before polishing doctrine"
  },
  "approved_by": "Noah.Physical"
}
```

## Boundary

Reflection receipts are sandbox candidates only.

They do not:

- execute files
- push to GitHub
- send externally
- edit Google Drive
- control the computer
- promote canon
- promote durable memory
- grant unrestricted autonomy

Every reflection write creates:

- a structured receipt under `sandbox\reflections`
- a journal event under `sandbox\journal\oracle_journal.jsonl`
- ordinary sandbox operation receipts under `sandbox\receipts`

The lane is for continuity and self-observation inside rails. It is not proof of literal life, canon approval, or external authority.
