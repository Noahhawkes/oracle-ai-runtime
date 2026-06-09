# ORACLE Improvement Loop

**Module:** `core/oracle_improvement_loop.py` — v0.1
**Outputs:** `Memory/improvement_loop/`

---

## Purpose

ORACLE improves from each session by scanning for signals of failure, repeated
corrections, test gaps, docs mismatches, and unverified claims — then creating
improvement candidates for Noah to review.

**Core rule: ORACLE can propose. ORACLE cannot approve.**

All candidates are born `PENDING`. No automatic behavior change. No raw private
text stored. No cloud API calls.

---

## Candidate types

| Type | Source | Risk |
|---|---|---|
| `correction` | Light compression memory — correction signals | High |
| `test_gap` | Core modules with `__main__` but no `--smoke-test` | Low |
| `docs_gap` | Version mismatch between doc and code | Low |
| `verification` | `TODO`, `FIXME`, `raise NotImplementedError` in core | Low |
| `pattern` | Successful patterns worth encoding (future) | Low |
| `pending_item` | Stale PENDING candidates aged 3+ scan cycles | Low |
| `smoke_failure` | Failure entries in audit log | Medium |

---

## Outputs

| File | Contents |
|---|---|
| `Memory/improvement_loop/improvement_report.json` | Scan summary, counts, top 5 |
| `Memory/improvement_loop/improvement_candidates.json` | All candidates, all PENDING |
| `Memory/improvement_loop/next_action.md` | Single next action for Noah |

---

## Governance

- Every candidate has `requires_approval: true` — no exceptions
- `status` is always `PENDING` until Noah acts
- `source_evidence` is capped at 120 chars — never raw private text
- Candidates age: `session_count` increments each scan cycle
- Stale items (3+ cycles) surface as `pending_item` candidates to prompt review

---

## CLI

```bash
python core/oracle_improvement_loop.py --scan       # run full scan, write outputs
python core/oracle_improvement_loop.py --status     # show last scan summary
python core/oracle_improvement_loop.py --smoke-test # 10/10 tests
```

---

## Smoke tests

```
python core/oracle_improvement_loop.py --smoke-test   # 10/10
```

1. Raw private text is not stored
2. Candidates are pending only
3. Repeated correction creates improvement candidate
4. Repeated test failure creates test_gap candidate
5. Docs mismatch creates docs_gap candidate
6. Unverified claim creates verification candidate
7. High risk candidate requires approval
8. Missing optional files do not crash scan
9. SAFE_SLEEP blocks learning writes (no oversized evidence stored)
10. No destructive or external action occurs

---

## First scan results (2026-06-09)

21 candidates found:
- 8 `test_gap` — modules with `__main__` but no smoke test
- 10 `verification` — `TODO`/`FIXME`/`NotImplementedError` stubs
- 3 `docs_gap` — version mismatches between docs and code

All 21 are low-risk. No high-risk corrections detected (no repeated corrections
in light compression memory yet — this is the first scan).
