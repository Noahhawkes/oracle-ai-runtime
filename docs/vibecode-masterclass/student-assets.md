# Student Assets

## VibeCode Prompt Card

Before asking AI to build, fill this in:

```text
Intent:
What do I want changed?

Boundary:
What must not change?

Target:
Where should it work?

Test:
How will we prove it?

Receipt:
What evidence do I need back?
```

Then write:

```text
Do only this. If uncertain, stop and ask. Report changed files, test result,
and remaining uncertainty.
```

## Receipt Checklist

Ask for:

- What changed?
- Where did it change?
- What command ran?
- What failed?
- What passed?
- What remains uncertain?
- What was not done?
- What is the next single action?

## Queue Reset Scripts

Use when the prompt pile gets too deep:

```text
Pause new work. Report current state only.
```

```text
Ignore pending prompt pile unless already executing one. Pause and report your
current state only.
```

```text
Finish only the current patch. No new architecture. No new features. Report
test result only.
```

## AI Role Map Worksheet

Assign one job per system:

| Role | Tool/System | Boundary |
|---|---|---|
| Architect |  |  |
| Implementation hand |  |  |
| Critic |  |  |
| Summarizer |  |  |
| Local runtime |  |  |
| Archive/source truth |  |  |
| Final authority | Human | Human keeps the keys |

Example map:

| Role | Tool/System | Boundary |
|---|---|---|
| Implementation hand | Codex | Show diffs/tests; no commit without approval |
| Live runtime | ORACLE | Show route/custody receipts; do not fake execution |
| Orientation layer | ChatGPT | Synthesis is candidate unless source-backed |
| External audit | Gemini/Grok | External answers are not canon |
| Archive | Drive/local storage | Preserve source, hash, and provenance |
| Final authority | Noah.Physical | Approves canon, publish, send, commit |

## Patch Command Template

```text
Intent:
Patch [specific behavior].

Boundary:
No new architecture. No extra features. Do not commit. Do not hardcode final
answers.

Target:
[file/module/path]

Test:
Run [commands].

Receipt:
Report changed files, test result, live result if applicable, and remaining
failures.
```

## Live Test Template

```text
Live test target:
[URL, app, document, or command]

Prompt/input:
[exact input]

Pass criteria:
- [criterion]
- [criterion]
- [criterion]

Fail criteria:
- [criterion]
- [criterion]

Receipt required:
- route/result
- visible output
- saved/persisted status if relevant
- remaining failures
```

## Candidate vs Canon Guide

Candidate means:

- Captured.
- Searchable.
- Useful.
- Not yet final authority.

Canon means:

- Approved by the human authority.
- Source-backed.
- Provenance-preserved.
- Safe to speak from as settled within the system.

Rule:

```text
Captured is not canon.
Fluent is not proven.
Useful is not final.
```

## Companion Boundary Guide

Safe:

```text
This system has a sustained role in my workflow.
This interaction has continuity value.
This artifact matters to me.
This response should be warm but bounded.
```

Unsafe without proof:

```text
The AI is proven alive.
The AI wants this.
The AI has a soul.
The AI remembers outside the grounded system.
The AI performed an action without a receipt.
```
