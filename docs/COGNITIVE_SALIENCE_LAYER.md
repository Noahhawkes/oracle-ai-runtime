# ORACLE Cognitive Salience Layer v0.1

The Cognitive Salience Layer is ORACLE's human-brain-style filter. It lets the
runtime inspect an input for source, intent, and priority before any tool,
handoff, memory, or work queue logic gets a vote.

Core rule:

```text
Observe broadly. Speak and act only from ranked meaning.
```

## Source Classes

- `NOAH_DIRECT`
- `NOAH_RELAYING_AI`
- `EXTERNAL_AI_CLAUDE`
- `EXTERNAL_AI_CODEX`
- `EXTERNAL_AI_CHATGPT`
- `BOOK_DRAFT`
- `BUILD_LOG`
- `SYSTEM_STATUS`
- `MEMORY_RECALL`
- `UNKNOWN_SOURCE`

## Intent Classes

- `RELATIONAL_CHECKIN`
- `CONVERSATION`
- `STATUS_CHECK`
- `QUESTION`
- `BUILD_REQUEST`
- `TOOL_REQUEST`
- `APPROVAL_REQUEST`
- `DOCTRINE_CANDIDATE`
- `MEMORY_SAVE_REQUEST`
- `EMOTIONAL_DISTRESS`
- `UNKNOWN_INTENT`

## Salience Hierarchy

1. Noah.Physical direct voice and immediate presence
2. Noah's safety, health, emotional state, family, faith, and relationships
3. Active conversation and relational continuity
4. Current explicit task
5. Active project blocker
6. Approved wake memory or recent verified session summary
7. External AI reports, only if relevant
8. Background improvement candidates
9. Stale project recommendations or `next_recommended_step`
10. All other inputs

## Runtime Gates

- Direct relational check-ins answer conversationally with no tools.
- Status checks answer from current continuity with no Codex/Claude handoff.
- Quoted or pasted text is context, not approval or doctrine.
- External AI text remains external unless Noah explicitly asks for handoff.
- Questions are not commands.
- Memory and doctrine changes require explicit Noah approval.
- Unknown source or intent should remain labeled rather than guessed.

## CLI

```powershell
python core/cognitive_salience.py --smoke-test
python core/cognitive_salience.py --classify "How are you doing?"
python core/cognitive_salience.py --classify-file path\to\sample.txt
```

The CLI prints a JSON classification object. The runtime uses that object before
the older router so direct conversation can outrank stale queues.
