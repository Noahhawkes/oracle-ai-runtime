# ORACLE Video Intelligence Policy
## `core/video_intelligence.py`

---

## Search Light Compression Law

> ORACLE may observe approved video.
> ORACLE may create candidate observations.
> ORACLE may compress meaning.
> ORACLE may not store raw video as memory.
> ORACLE may not create approved memory without Noah approval.

---

## What This Module Does

Accepts an approved video file path. Samples frames. Generates coarse visual observations. Compresses into a candidate record. Persists as **pending** — never as approved memory.

All candidates are born pending. Noah approves. ORACLE observes.

---

## What This Module Never Does

| Forbidden | Reason |
|---|---|
| Broad folder crawling | Must pass individual file paths |
| Automatic approval | Noah must approve every candidate |
| Raw frame storage | Frames are hashed and released — no pixel archive |
| Raw transcript storage | `raw_transcript_stored` is always `False` in the pipeline |
| Stranger identification by name | Coarse visual descriptions only |
| Emotion inference | Only explicit scene-level signals |
| Approved memory without review | `STATUS_APPROVED` requires explicit call to `approve_candidate()` |

---

## Supported Formats

`.mov` `.mp4` `.m4v` `.avi`

---

## Candidate Lifecycle

```
analyze_video() → STATUS_PENDING
                     ↓ Noah reviews
        ┌────────────┼────────────┐
   approve_candidate  reject_candidate  quarantine_candidate
        ↓                 ↓                   ↓
   STATUS_APPROVED   STATUS_REJECTED   STATUS_QUARANTINED
        ↓
  recall_approved()      ← only APPROVED candidates eligible
        ↓
  revoke_candidate()
        ↓
   STATUS_REVOKED   ← removed from recall, cannot re-approve
```

Only `STATUS_APPROVED` candidates are returned by `recall_approved()`.

---

## Sensitivity Levels

| Level | Triggered by |
|---|---|
| `low` | generic content |
| `medium` | work, code, desktop, oracle files |
| `high` | family, named people (ashley, ender, mom, dad) |
| `critical` | medical, bank, legal, intimate, bedroom, bath — **auto-quarantined** |

Critical-sensitivity candidates go directly to `STATUS_QUARANTINED`. Noah must manually review before they can be approved.

---

## Categories

| Category | Triggered by |
|---|---|
| `shopping` | shop, shopping, store, grocery, buy |
| `travel` | travel, trip, airport, car, drive |
| `family` | family, ashley, ender, mom, dad, call |
| `project_work` | oracle, desktop, screen, code, sov1, build |
| `conversation` | meeting, convo, talk, discuss |
| `desktop_failure` | oracle/desktop file in dim/dark lighting |
| `ordinary_life` | no specific signal |
| `unknown` | no match |

Classification is deterministic — no LLM.

---

## Frame Sampling

```
Default interval : 10 seconds
Max frames       : 30
Storage          : NONE by default (frames hashed and released)
Debug store      : Only if debug_store_frames=True AND debug_frame_dir explicitly set
```

Each frame produces a coarse description:
- Timestamp
- Scene brightness category (very dark / dim / normal / bright)
- Motion indicator (high visual complexity / calm)
- Resolution

No face recognition. No biometric data. No pixel archive.

---

## VideoObservationCandidate Fields

```python
@dataclass
class VideoObservationCandidate:
    id: str                          # 10-char hex, auto-generated
    source_path: str                 # absolute path to original file
    filename: str                    # basename only
    observed_at: str                 # ISO timestamp
    duration_seconds: float
    sample_method: str               # e.g. "opencv@10s"
    event_summary: str               # what happened (from frames)
    compressed_meaning: str          # compressed significance
    people_detected_labels: list     # coarse labels only ("person present")
    relationship_context: str
    project_context: str
    action_context: str
    recommended_candidate_type: str  # category
    sensitivity: str                 # low/medium/high/critical
    confidence: float                # 0.0–1.0
    unknowns: list                   # preserved — never inferred
    status: str                      # pending/approved/rejected/quarantined/revoked
    frames_sampled: int
    raw_frames_stored: bool          # always False in normal pipeline
    raw_transcript_stored: bool      # always False
    approved_by: str
    approved_at: str
    rejection_reason: str
    created_at: str
    updated_at: str
```

---

## API

```python
from video_intelligence import (
    analyze_video,
    extract_metadata,
    sample_frames,
    create_candidate,
    save_candidates,
    list_pending,
    list_all,
    approve_candidate,
    reject_candidate,
    quarantine_candidate,
    revoke_candidate,
    summarize_candidate,
    recall_approved,
)

# Full pipeline — Noah must approve
candidate = analyze_video(
    "family_call.mov",
    approved_by_noah=True,      # gate — must be True
    dry_run=False,              # True = create candidate but don't persist
)
print(candidate.status)         # "pending"

# Inspect pending
for c in list_pending():
    print(c.summary_line())

# Noah approves
approved = approve_candidate(candidate.id, approved_by="Noah")

# Recall only approved
for c in recall_approved():
    print(c.full_summary())

# Revoke if needed
revoke_candidate(candidate.id, reason="Noah changed mind")
```

---

## Backend

| Backend | Used for | Install |
|---|---|---|
| `opencv-python` | Frame sampling, metadata fallback | `pip install opencv-python` |
| `ffprobe` | Metadata (duration, resolution, fps) | Install ffmpeg |

If OpenCV is absent, the module raises `EnvironmentError` with install instructions. ffprobe is optional — OpenCV handles metadata if ffprobe is missing.

---

## Persistence

`Memory/video_observation_candidates.json` — append-only JSON array of all candidates across sessions. Gitignored (Memory/ directory). Never committed.

---

## REPL Commands

```
/video-analyze <path>     Analyze an approved video — prompts Noah for confirmation
/video-pending            List all pending candidates
/video-approve <id>       Approve a candidate for recall
```

---

## CLI

```bash
python core/video_intelligence.py --smoke-test
python core/video_intelligence.py --analyze "family_call.mov" --approved
python core/video_intelligence.py --analyze "family_call.mov" --approved --dry-run
python core/video_intelligence.py --pending
python core/video_intelligence.py --approve <candidate_id>
python core/video_intelligence.py --all
python core/video_intelligence.py --backend
```

---

## Smoke Tests

38/38 — all passing.

Covers:
- Missing file → `FileNotFoundError` (clean)
- Unsupported format → `ValueError` (clean)
- Unapproved analysis → `PermissionError` (gate holds)
- Dry-run on bad video → pending candidate with unknowns (no crash)
- Fresh candidate defaults to pending
- Raw frames not stored by default
- Raw transcript not stored
- `approve_candidate` → approved, records who and when
- `reject_candidate` → rejected, records reason
- `quarantine_candidate` → quarantined
- `revoke_candidate` → revoked, clears approved_at
- Rejected/quarantined/revoked/pending all excluded from `recall_approved()`
- `create_candidate` pipeline never sets `raw_frames_stored=True`
- Unknowns preserved and appear in `full_summary()`
- `family` → HIGH sensitivity; `medical` → CRITICAL; `oracle` → MEDIUM
- `family_call.mov` → family category
- `shopping_with_ashley.mov` → shopping category (not family)
- `oracle_build_pass.mov` → project_work
- Directory path → `IsADirectoryError` (no crawling)
- Unknown candidate ID → clean error string

---

## Candidate Examples

**Example 1: family_call.mov**
```
Event summary    : Video of family_call.mov (180s). Normal indoor lighting.
Compressed meaning: Observed 18 frames. Category: family. Sensitivity: high. Awaiting Noah review.
Status           : pending
```

**Example 2: oracle_desktop_failure.mov**
```
Event summary    : Video of oracle_desktop_failure.mov (90s). Dim environment throughout.
Compressed meaning: Observed 9 frames. Category: desktop_failure. Sensitivity: medium. Awaiting Noah review.
Status           : pending
```

**Example 3: shopping_with_ashley.mov**
```
Event summary    : Video of shopping_with_ashley.mov (240s). Bright / well-lit.
Compressed meaning: Observed 24 frames. Category: shopping. Sensitivity: medium. Awaiting Noah review.
Status           : pending
```

All examples born pending. None recalled until Noah approves.

---

*Last updated: 2026-06-07 | ORACLE.AI — Video Intelligence Policy v0.1*
