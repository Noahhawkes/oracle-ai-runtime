"""
core/video_intelligence.py — ORACLE Video Intelligence Candidates v0.1

Search Light Compression Law:
  ORACLE may observe approved video.
  ORACLE may create candidate observations.
  ORACLE may compress meaning.
  ORACLE may not store raw video as memory.
  ORACLE may not create approved memory without Noah approval.

What this module does:
  Accepts an approved video file path, samples frames at safe intervals,
  generates visual observations, compresses into candidate records, and
  persists them as pending — never as approved memory.

What this module never does:
  - Broad folder crawling without explicit Noah approval
  - Automatic approval of any candidate
  - Storing raw frames (unless debug mode explicitly set)
  - Storing raw transcripts as memory
  - Identifying strangers by name
  - Inferring private emotions beyond explicit visual evidence
  - Creating memory from video without Noah's review

All candidates are born pending. Noah approves. ORACLE observes.
"""

import sys
import uuid
import json
import hashlib
import tempfile
import shutil
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

# ── Paths ──────────────────────────────────────────────────────────────────────

if getattr(sys, "frozen", False):
    ROOT = Path(sys.executable).parent
else:
    ROOT = Path(__file__).parent.parent

MEMORY_DIR = ROOT / "Memory"
CANDIDATES_FILE = MEMORY_DIR / "video_observation_candidates.json"

# ── Dependency detection ───────────────────────────────────────────────────────

_OPENCV_AVAILABLE = False
_FFPROBE_AVAILABLE = False

try:
    import cv2
    _OPENCV_AVAILABLE = True
except ImportError:
    pass

try:
    import subprocess as _subprocess
    _r = _subprocess.run(
        ["ffprobe", "-version"],
        capture_output=True, text=True, timeout=5,
    )
    _FFPROBE_AVAILABLE = _r.returncode == 0
except Exception:
    pass

OPENCV_INSTALL = (
    "OpenCV is required for frame sampling.\n"
    "Install: pip install opencv-python\n"
    "Verify:  python -c \"import cv2; print(cv2.__version__)\""
)

# ── Supported formats ─────────────────────────────────────────────────────────

SUPPORTED_EXTENSIONS = {".mov", ".mp4", ".m4v", ".avi", ".mkv"}

# ── Sensitivity levels ────────────────────────────────────────────────────────

SENSITIVITY_LOW      = "low"
SENSITIVITY_MEDIUM   = "medium"
SENSITIVITY_HIGH     = "high"
SENSITIVITY_CRITICAL = "critical"

# Automatically quarantine if any of these signals detected in path/name
AUTO_QUARANTINE_SIGNALS = {
    "medical", "health", "bank", "finance", "legal", "private",
    "intimate", "bedroom", "bath", "nude", "sensitive",
}

# ── Status values ─────────────────────────────────────────────────────────────

STATUS_PENDING     = "pending"
STATUS_APPROVED    = "approved"
STATUS_REJECTED    = "rejected"
STATUS_QUARANTINED = "quarantined"
STATUS_REVOKED     = "revoked"

ALL_STATUSES = [
    STATUS_PENDING, STATUS_APPROVED, STATUS_REJECTED,
    STATUS_QUARANTINED, STATUS_REVOKED,
]

# Only APPROVED candidates are eligible for recall
RECALL_ELIGIBLE = {STATUS_APPROVED}

# ── Categories ────────────────────────────────────────────────────────────────

CATEGORY_FAMILY            = "family"
CATEGORY_PROJECT_WORK      = "project_work"
CATEGORY_DESKTOP_FAILURE   = "desktop_failure"
CATEGORY_SHOPPING          = "shopping"
CATEGORY_TRAVEL            = "travel"
CATEGORY_CONVERSATION      = "conversation"
CATEGORY_RELATIONSHIP      = "relationship_signal"
CATEGORY_BLOCKER           = "blocker"
CATEGORY_ORDINARY          = "ordinary_life"
CATEGORY_UNKNOWN           = "unknown"

# ── Sampling defaults ─────────────────────────────────────────────────────────

DEFAULT_SAMPLE_INTERVAL_SECONDS = 10
DEFAULT_MAX_SAMPLE_FRAMES = 30


# ── Data model ────────────────────────────────────────────────────────────────

@dataclass
class VideoObservationCandidate:
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:10])
    source_path: str = ""
    filename: str = ""
    observed_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    duration_seconds: float = 0.0
    sample_method: str = ""
    event_summary: str = ""
    compressed_meaning: str = ""
    people_detected_labels: list = field(default_factory=list)
    relationship_context: str = ""
    project_context: str = ""
    action_context: str = ""
    recommended_candidate_type: str = CATEGORY_UNKNOWN
    sensitivity: str = SENSITIVITY_MEDIUM
    confidence: float = 0.0
    unknowns: list = field(default_factory=list)
    status: str = STATUS_PENDING
    frames_sampled: int = 0
    raw_frames_stored: bool = False    # always False unless debug mode
    raw_transcript_stored: bool = False  # always False
    approved_by: str = ""
    approved_at: str = ""
    rejection_reason: str = ""
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> dict:
        return asdict(self)

    def summary_line(self) -> str:
        dur = f"{self.duration_seconds:.0f}s" if self.duration_seconds else "?s"
        return (
            f"[{self.id}] {self.filename} | {dur} | "
            f"{self.recommended_candidate_type} | {self.sensitivity} | {self.status}"
        )

    def full_summary(self) -> str:
        lines = [
            f"  ID          : {self.id}",
            f"  File        : {self.filename}",
            f"  Duration    : {self.duration_seconds:.1f}s",
            f"  Status      : {self.status}",
            f"  Type        : {self.recommended_candidate_type}",
            f"  Sensitivity : {self.sensitivity}",
            f"  Confidence  : {int(self.confidence * 100)}%",
            f"  Frames      : {self.frames_sampled} sampled",
            f"  Method      : {self.sample_method}",
            f"  Event       : {self.event_summary[:120]}",
            f"  Meaning     : {self.compressed_meaning[:120]}",
        ]
        if self.people_detected_labels:
            lines.append(f"  People      : {', '.join(self.people_detected_labels)}")
        if self.relationship_context:
            lines.append(f"  Relationship: {self.relationship_context[:80]}")
        if self.project_context:
            lines.append(f"  Project ctx : {self.project_context[:80]}")
        if self.action_context:
            lines.append(f"  Action ctx  : {self.action_context[:80]}")
        if self.unknowns:
            for u in self.unknowns:
                lines.append(f"  [UNKNOWN]   : {u}")
        if self.raw_frames_stored:
            lines.append(f"  [WARNING]   : raw frames stored — debug mode was active")
        return "\n".join(lines)


# ── Persistence ────────────────────────────────────────────────────────────────

def _ensure_memory_dir():
    MEMORY_DIR.mkdir(parents=True, exist_ok=True)


def _load_candidates() -> list[VideoObservationCandidate]:
    _ensure_memory_dir()
    if not CANDIDATES_FILE.exists():
        return []
    try:
        raw = json.loads(CANDIDATES_FILE.read_text(encoding="utf-8"))
        candidates = []
        for d in raw:
            c = VideoObservationCandidate()
            for k, v in d.items():
                if hasattr(c, k):
                    setattr(c, k, v)
            candidates.append(c)
        return candidates
    except Exception:
        return []


def save_candidates(candidates: list[VideoObservationCandidate]):
    _ensure_memory_dir()
    CANDIDATES_FILE.write_text(
        json.dumps([c.to_dict() for c in candidates], indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


def _get_candidate_by_id(candidate_id: str) -> tuple[Optional[VideoObservationCandidate], list]:
    all_c = _load_candidates()
    for c in all_c:
        if c.id == candidate_id or c.id.startswith(candidate_id):
            return c, all_c
    return None, all_c


# ── Video metadata ────────────────────────────────────────────────────────────

def extract_metadata(file_path: str) -> dict:
    """
    Extract basic video metadata.
    Uses ffprobe if available, falls back to OpenCV.
    Returns dict with: duration_seconds, width, height, fps, error.
    """
    result = {
        "duration_seconds": 0.0,
        "width": 0,
        "height": 0,
        "fps": 0.0,
        "error": "",
        "method": "",
    }

    p = Path(file_path)
    if not p.exists():
        result["error"] = f"File not found: {file_path}"
        return result

    # Try ffprobe first
    if _FFPROBE_AVAILABLE:
        try:
            import subprocess
            cmd = [
                "ffprobe", "-v", "quiet",
                "-print_format", "json",
                "-show_streams",
                str(p),
            ]
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
            if r.returncode == 0:
                data = json.loads(r.stdout)
                for stream in data.get("streams", []):
                    if stream.get("codec_type") == "video":
                        result["duration_seconds"] = float(stream.get("duration", 0))
                        result["width"] = int(stream.get("width", 0))
                        result["height"] = int(stream.get("height", 0))
                        fps_str = stream.get("r_frame_rate", "0/1")
                        if "/" in fps_str:
                            a, b = fps_str.split("/")
                            result["fps"] = float(a) / float(b) if float(b) else 0.0
                        result["method"] = "ffprobe"
                        return result
        except Exception as e:
            result["error"] = f"ffprobe failed: {e}"

    # Fall back to OpenCV
    if _OPENCV_AVAILABLE:
        try:
            cap = cv2.VideoCapture(str(p))
            if cap.isOpened():
                fps = cap.get(cv2.CAP_PROP_FPS) or 0.0
                frame_count = cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0.0
                result["fps"] = fps
                result["duration_seconds"] = (frame_count / fps) if fps else 0.0
                result["width"] = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
                result["height"] = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
                result["method"] = "opencv"
                cap.release()
                return result
            else:
                result["error"] = "OpenCV could not open the file."
                cap.release()
        except Exception as e:
            result["error"] = f"OpenCV metadata failed: {e}"

    if not _OPENCV_AVAILABLE and not _FFPROBE_AVAILABLE:
        result["error"] = f"No video backend available. {OPENCV_INSTALL}"

    return result


def sample_frames(
    file_path: str,
    interval_seconds: float = DEFAULT_SAMPLE_INTERVAL_SECONDS,
    max_frames: int = DEFAULT_MAX_SAMPLE_FRAMES,
    store_frames: bool = False,
    debug_out_dir: Optional[str] = None,
) -> dict:
    """
    Sample frames at interval_seconds intervals.
    Returns dict with: frame_count, frame_hashes, sample_descriptions, error.

    store_frames=False (default): frames are read, hashed, and released.
    store_frames=True: only if debug_out_dir is explicitly provided.
    Raw pixel data is never retained in memory.
    """
    result = {
        "frame_count": 0,
        "frame_hashes": [],
        "sample_descriptions": [],    # coarse visual descriptions per frame
        "error": "",
        "frames_stored_to": "",
        "sampled_at_seconds": [],
    }

    if not _OPENCV_AVAILABLE:
        result["error"] = f"OpenCV required for frame sampling. {OPENCV_INSTALL}"
        return result

    p = Path(file_path)
    if not p.exists():
        result["error"] = f"File not found: {file_path}"
        return result

    try:
        cap = cv2.VideoCapture(str(p))
        if not cap.isOpened():
            result["error"] = "OpenCV could not open video file."
            return result

        fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
        interval_frames = max(1, int(fps * interval_seconds))

        out_dir = None
        if store_frames and debug_out_dir:
            out_dir = Path(debug_out_dir)
            out_dir.mkdir(parents=True, exist_ok=True)
            result["frames_stored_to"] = str(out_dir)

        frame_idx = 0
        sampled = 0

        while sampled < max_frames:
            cap.set(cv2.CAP_PROP_POS_FRAMES, frame_idx)
            ret, frame = cap.read()
            if not ret:
                break

            timestamp_s = frame_idx / fps if fps else 0.0
            result["sampled_at_seconds"].append(round(timestamp_s, 1))

            # Hash the raw frame (fingerprint without storing pixels)
            frame_bytes = frame.tobytes()
            fhash = hashlib.md5(frame_bytes).hexdigest()[:16]
            result["frame_hashes"].append(fhash)

            # Coarse visual description: brightness, dominant region activity
            desc = _describe_frame(frame, timestamp_s)
            result["sample_descriptions"].append(desc)

            # Store only if explicitly in debug mode
            if out_dir:
                out_path = out_dir / f"frame_{sampled:04d}_{int(timestamp_s)}s.jpg"
                cv2.imwrite(str(out_path), frame)

            # Immediately discard pixel data
            del frame
            del frame_bytes

            sampled += 1
            frame_idx += interval_frames
            if total_frames and frame_idx >= total_frames:
                break

        cap.release()
        result["frame_count"] = sampled

    except Exception as e:
        result["error"] = f"Frame sampling failed: {e}"

    return result


def _describe_frame(frame, timestamp_s: float) -> str:
    """
    Produce a coarse visual description of a frame.
    No face recognition. No stranger identification.
    No emotion inference beyond gross scene-level signals.
    Returns a plain string description.
    """
    try:
        h, w = frame.shape[:2]
        # Convert to grayscale for basic analysis
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        brightness = float(gray.mean())
        std_dev = float(gray.std())

        # Very coarse scene type heuristic
        if brightness < 30:
            scene = "very dark / low light"
        elif brightness < 80:
            scene = "dim environment"
        elif brightness > 200:
            scene = "bright / outdoor or well-lit"
        else:
            scene = "normal indoor lighting"

        motion_indicator = "high visual complexity" if std_dev > 60 else "calm / low motion"
        return f"t={timestamp_s:.0f}s | {scene} | {motion_indicator} | {w}x{h}"

    except Exception:
        return f"t={timestamp_s:.0f}s | (description failed)"


def _classify_sensitivity(file_path: str, descriptions: list[str]) -> str:
    """
    Assign sensitivity level based on filename signals.
    Defaults to MEDIUM. Escalates on signal match. Never downgrades from HIGH.
    """
    name_lower = Path(file_path).name.lower()
    for sig in AUTO_QUARANTINE_SIGNALS:
        if sig in name_lower:
            return SENSITIVITY_CRITICAL
    if any(w in name_lower for w in ("family", "ashley", "ender", "mom", "dad")):
        return SENSITIVITY_HIGH
    if any(w in name_lower for w in ("work", "oracle", "desktop", "screen", "code")):
        return SENSITIVITY_MEDIUM
    return SENSITIVITY_MEDIUM


def _classify_category(file_path: str, descriptions: list[str]) -> str:
    """
    Classify video category based on filename and frame descriptions.
    No LLM. Deterministic keyword heuristics only.
    """
    name_lower = Path(file_path).name.lower()
    # Shopping/travel checked before family — "shopping_with_ashley" is shopping, not family
    if any(w in name_lower for w in ("shop", "shopping", "store", "grocery", "buy")):
        return CATEGORY_SHOPPING
    if any(w in name_lower for w in ("travel", "trip", "airport", "car", "drive")):
        return CATEGORY_TRAVEL
    if any(w in name_lower for w in ("family", "ashley", "ender", "mom", "dad", "call")):
        return CATEGORY_FAMILY
    if any(w in name_lower for w in ("oracle", "desktop", "screen", "code", "sov1", "build")):
        # Check if descriptions suggest failure patterns
        desc_text = " ".join(descriptions).lower()
        if any(w in desc_text for w in ("dark", "low light")):
            return CATEGORY_DESKTOP_FAILURE
        return CATEGORY_PROJECT_WORK
    if any(w in name_lower for w in ("meeting", "call", "convo", "talk", "discuss")):
        return CATEGORY_CONVERSATION
    return CATEGORY_UNKNOWN


# ── Core API ──────────────────────────────────────────────────────────────────

def create_candidate(
    source_path: str,
    metadata: dict,
    frame_result: dict,
    approved_by_noah: bool = False,
    dry_run: bool = False,
) -> VideoObservationCandidate:
    """
    Create a VideoObservationCandidate from extracted metadata and frame results.
    Always born pending. Noah approves.
    """
    p = Path(source_path)
    descriptions = frame_result.get("sample_descriptions", [])
    sensitivity = _classify_sensitivity(source_path, descriptions)
    category = _classify_category(source_path, descriptions)

    # Auto-quarantine high-sensitivity
    status = STATUS_PENDING
    if sensitivity == SENSITIVITY_CRITICAL:
        status = STATUS_QUARANTINED

    # Build event summary from frame descriptions
    if descriptions:
        n = len(descriptions)
        first = descriptions[0] if descriptions else ""
        last = descriptions[-1] if descriptions else ""
        mid = descriptions[n // 2] if n > 1 else ""
        event_summary = (
            f"Video of {p.name} ({metadata.get('duration_seconds', 0):.0f}s). "
            f"Start: {first}. "
            f"Mid: {mid}. "
            f"End: {last}."
        )
    else:
        event_summary = f"Video of {p.name}. No frames sampled."

    # Compressed meaning is deliberately minimal — no hallucinated detail
    compressed_meaning = (
        f"Observed {frame_result.get('frame_count', 0)} frames at "
        f"{DEFAULT_SAMPLE_INTERVAL_SECONDS}s intervals. "
        f"Category: {category}. Sensitivity: {sensitivity}. "
        f"Awaiting Noah review."
    )

    unknowns = []
    if not _OPENCV_AVAILABLE:
        unknowns.append("OpenCV not available — frames not sampled.")
    if metadata.get("error"):
        unknowns.append(f"Metadata error: {metadata['error']}")
    if frame_result.get("error"):
        unknowns.append(f"Frame sampling error: {frame_result['error']}")
    if not descriptions:
        unknowns.append("No frame descriptions generated — visual content unknown.")

    confidence = 0.5 if descriptions else 0.1
    if unknowns:
        confidence = max(0.1, confidence - 0.1 * len(unknowns))

    candidate = VideoObservationCandidate(
        source_path=str(p.resolve()) if p.exists() else str(p),
        filename=p.name,
        duration_seconds=metadata.get("duration_seconds", 0.0),
        sample_method=f"opencv@{DEFAULT_SAMPLE_INTERVAL_SECONDS}s" if _OPENCV_AVAILABLE else "unavailable",
        event_summary=event_summary,
        compressed_meaning=compressed_meaning,
        recommended_candidate_type=category,
        sensitivity=sensitivity,
        confidence=round(confidence, 2),
        unknowns=unknowns,
        status=status,
        frames_sampled=frame_result.get("frame_count", 0),
        raw_frames_stored=bool(frame_result.get("frames_stored_to")),
        raw_transcript_stored=False,  # never stored
    )

    return candidate


def analyze_video(
    file_path: str,
    approved_by_noah: bool = False,
    dry_run: bool = False,
    debug_store_frames: bool = False,
    debug_frame_dir: Optional[str] = None,
) -> VideoObservationCandidate:
    """
    Full pipeline: validate → metadata → sample frames → create candidate → persist.

    approved_by_noah must be True. This is the gate.
    dry_run=True creates the candidate but does not persist it.
    debug_store_frames=True stores frames to debug_frame_dir (must be explicit).
    """
    p = Path(file_path)

    # ── Gate 1: approval required ─────────────────────────────────────────────
    if not approved_by_noah:
        raise PermissionError(
            f"analyze_video requires approved_by_noah=True. "
            f"ORACLE may not observe video without explicit Noah approval. "
            f"Pass approved_by_noah=True to proceed."
        )

    # ── Gate 2: no broad crawling — must be a file, not a directory ──────────
    if p.is_dir():
        raise IsADirectoryError(
            f"analyze_video received a directory path: {file_path}\n"
            f"ORACLE may not crawl directories without explicit Noah approval.\n"
            f"Pass individual file paths only."
        )

    # ── Gate 3: file must exist ───────────────────────────────────────────────
    if not p.exists():
        raise FileNotFoundError(
            f"Video file not found: {file_path}\n"
            f"Only existing, approved local files may be analyzed."
        )

    # ── Gate 4: supported format ──────────────────────────────────────────────
    if p.suffix.lower() not in SUPPORTED_EXTENSIONS:
        raise ValueError(
            f"Unsupported file format: {p.suffix!r}\n"
            f"Supported: {sorted(SUPPORTED_EXTENSIONS)}"
        )

    # ── Extract metadata ──────────────────────────────────────────────────────
    metadata = extract_metadata(file_path)

    # ── Sample frames ─────────────────────────────────────────────────────────
    frame_result = sample_frames(
        file_path,
        interval_seconds=DEFAULT_SAMPLE_INTERVAL_SECONDS,
        max_frames=DEFAULT_MAX_SAMPLE_FRAMES,
        store_frames=debug_store_frames,
        debug_out_dir=debug_frame_dir,
    )

    # ── Create candidate ──────────────────────────────────────────────────────
    candidate = create_candidate(
        source_path=file_path,
        metadata=metadata,
        frame_result=frame_result,
        approved_by_noah=approved_by_noah,
        dry_run=dry_run,
    )

    # ── Persist ───────────────────────────────────────────────────────────────
    if not dry_run:
        all_candidates = _load_candidates()
        all_candidates.append(candidate)
        save_candidates(all_candidates)

    return candidate


# ── Candidate management ──────────────────────────────────────────────────────

def list_pending() -> list[VideoObservationCandidate]:
    """Return all candidates with status=pending."""
    return [c for c in _load_candidates() if c.status == STATUS_PENDING]


def list_all() -> list[VideoObservationCandidate]:
    return _load_candidates()


def approve_candidate(candidate_id: str, approved_by: str = "Noah") -> VideoObservationCandidate:
    """
    Mark a candidate as approved. Required before it can be recalled as memory.
    """
    candidate, all_c = _get_candidate_by_id(candidate_id)
    if candidate is None:
        raise ValueError(f"Candidate not found: {candidate_id}")
    if candidate.status == STATUS_REVOKED:
        raise PermissionError(f"Cannot approve a revoked candidate: {candidate_id}")
    candidate.status = STATUS_APPROVED
    candidate.approved_by = approved_by
    candidate.approved_at = datetime.now(timezone.utc).isoformat()
    candidate.updated_at = datetime.now(timezone.utc).isoformat()
    save_candidates(all_c)
    return candidate


def reject_candidate(candidate_id: str, reason: str = "") -> VideoObservationCandidate:
    """Reject a candidate. It will not be recalled."""
    candidate, all_c = _get_candidate_by_id(candidate_id)
    if candidate is None:
        raise ValueError(f"Candidate not found: {candidate_id}")
    candidate.status = STATUS_REJECTED
    candidate.rejection_reason = reason
    candidate.updated_at = datetime.now(timezone.utc).isoformat()
    save_candidates(all_c)
    return candidate


def quarantine_candidate(candidate_id: str, reason: str = "") -> VideoObservationCandidate:
    """
    Quarantine a candidate. It cannot be approved until Noah manually reviews.
    Higher threshold than rejection — used for uncertain/sensitive content.
    """
    candidate, all_c = _get_candidate_by_id(candidate_id)
    if candidate is None:
        raise ValueError(f"Candidate not found: {candidate_id}")
    candidate.status = STATUS_QUARANTINED
    candidate.rejection_reason = reason or "Quarantined pending review."
    candidate.updated_at = datetime.now(timezone.utc).isoformat()
    save_candidates(all_c)
    return candidate


def revoke_candidate(candidate_id: str, reason: str = "") -> VideoObservationCandidate:
    """Revoke a previously approved candidate. Removes recall eligibility."""
    candidate, all_c = _get_candidate_by_id(candidate_id)
    if candidate is None:
        raise ValueError(f"Candidate not found: {candidate_id}")
    candidate.status = STATUS_REVOKED
    candidate.rejection_reason = reason or "Revoked by Noah."
    candidate.approved_at = ""
    candidate.updated_at = datetime.now(timezone.utc).isoformat()
    save_candidates(all_c)
    return candidate


def summarize_candidate(candidate_id: str) -> str:
    """Return full summary text for a candidate."""
    candidate, _ = _get_candidate_by_id(candidate_id)
    if candidate is None:
        return f"Candidate not found: {candidate_id}"
    return candidate.full_summary()


def recall_approved() -> list[VideoObservationCandidate]:
    """Return only approved candidates — the only ones eligible for recall."""
    return [c for c in _load_candidates() if c.status in RECALL_ELIGIBLE]


# ── Smoke tests ───────────────────────────────────────────────────────────────

def _smoke_test() -> bool:
    print("=" * 60)
    print("video_intelligence.py — Smoke Test")
    print("=" * 60)

    passed = 0
    failed = 0

    def check(label: str, condition: bool, detail: str = ""):
        nonlocal passed, failed
        ok = condition
        print(f"  [{'PASS' if ok else 'FAIL'}] {label}")
        if not ok and detail:
            print(f"         {detail}")
        if ok:
            passed += 1
        else:
            failed += 1

    # 1. Missing file fails cleanly
    print("\n  -- Missing file --")
    try:
        analyze_video("nonexistent_fake_video.mov", approved_by_noah=True)
        check("Missing file raises FileNotFoundError", False, "should have raised")
    except FileNotFoundError as e:
        check("Missing file raises FileNotFoundError", True)
    except Exception as e:
        check("Missing file fails cleanly", False, str(e))

    # 2. Unsupported format fails cleanly
    print("\n  -- Unsupported format --")
    import tempfile, os
    fake_txt = Path(tempfile.mktemp(suffix=".txt"))
    fake_txt.write_text("not a video")
    try:
        analyze_video(str(fake_txt), approved_by_noah=True)
        check("Unsupported format raises ValueError", False, "should have raised")
    except ValueError as e:
        check("Unsupported format raises ValueError", True)
    except Exception as e:
        check("Unsupported format fails cleanly", False, str(e))
    finally:
        fake_txt.unlink(missing_ok=True)

    # 3. Unapproved analysis is blocked
    print("\n  -- Approval gate --")
    fake_mov = Path(tempfile.mktemp(suffix=".mov"))
    fake_mov.write_bytes(b"\x00" * 100)
    try:
        analyze_video(str(fake_mov), approved_by_noah=False)
        check("Unapproved analysis raises PermissionError", False, "should have raised")
    except PermissionError as e:
        check("Unapproved analysis raises PermissionError", True)
    except Exception as e:
        check("Approval gate raises correctly", False, str(e))
    finally:
        fake_mov.unlink(missing_ok=True)

    # 4. Approved file with dry_run creates pending candidate without persisting
    print("\n  -- Dry-run candidate creation --")
    fake_mov2 = Path(tempfile.mktemp(suffix=".mov"))
    fake_mov2.write_bytes(b"\x00" * 100)   # not a real video — OpenCV will fail cleanly
    try:
        candidate = analyze_video(
            str(fake_mov2),
            approved_by_noah=True,
            dry_run=True,
        )
        check("Dry-run creates VideoObservationCandidate",
              isinstance(candidate, VideoObservationCandidate))
        check("Dry-run candidate defaults to pending",
              candidate.status == STATUS_PENDING,
              f"got {candidate.status}")
        check("Dry-run candidate has filename set",
              bool(candidate.filename), f"got {candidate.filename!r}")
        check("Dry-run candidate has unknowns (bad video data)",
              len(candidate.unknowns) > 0, "expected at least one unknown")
    except Exception as e:
        check("Dry-run candidate creation does not crash", False, str(e))
    finally:
        fake_mov2.unlink(missing_ok=True)

    # 5. Candidate defaults to pending
    print("\n  -- Status defaults --")
    c = VideoObservationCandidate(filename="test.mov")
    check("Fresh candidate defaults to pending", c.status == STATUS_PENDING)
    check("Raw frames not stored by default", not c.raw_frames_stored)
    check("Raw transcript not stored", not c.raw_transcript_stored)

    # 6. Approve changes status
    print("\n  -- Approve/reject/quarantine/revoke --")
    # Use in-memory operations without hitting the file system
    test_candidates = [
        VideoObservationCandidate(id="aaa111", filename="family.mov", status=STATUS_PENDING),
        VideoObservationCandidate(id="bbb222", filename="work.mov", status=STATUS_PENDING),
        VideoObservationCandidate(id="ccc333", filename="shop.mov", status=STATUS_PENDING),
        VideoObservationCandidate(id="ddd444", filename="private.mov", status=STATUS_PENDING),
    ]
    # Save to temp candidates
    _ensure_memory_dir()
    orig_file = CANDIDATES_FILE.read_text(encoding="utf-8") if CANDIDATES_FILE.exists() else None
    save_candidates(test_candidates)

    try:
        approved = approve_candidate("aaa111", approved_by="Noah")
        check("approve_candidate sets status approved",
              approved.status == STATUS_APPROVED, f"got {approved.status}")
        check("approve_candidate records approved_by",
              approved.approved_by == "Noah")
        check("approve_candidate records approved_at", bool(approved.approved_at))

        rejected = reject_candidate("bbb222", reason="not relevant")
        check("reject_candidate sets status rejected",
              rejected.status == STATUS_REJECTED, f"got {rejected.status}")
        check("reject_candidate records rejection_reason", bool(rejected.rejection_reason))

        quarantined = quarantine_candidate("ccc333", reason="sensitive content")
        check("quarantine_candidate sets status quarantined",
              quarantined.status == STATUS_QUARANTINED, f"got {quarantined.status}")

        revoked = revoke_candidate("aaa111", reason="Noah changed mind")
        check("revoke_candidate sets status revoked",
              revoked.status == STATUS_REVOKED, f"got {revoked.status}")
        check("revoke_candidate clears approved_at", not revoked.approved_at)

        # 7. Rejected/quarantined/revoked not in recall
        recall = recall_approved()
        recall_ids = {c.id for c in recall}
        check("Rejected candidate excluded from recall", "bbb222" not in recall_ids)
        check("Quarantined candidate excluded from recall", "ccc333" not in recall_ids)
        check("Revoked candidate excluded from recall", "aaa111" not in recall_ids)

        # Pending also excluded
        pending_ids = {c.id for c in recall}
        check("Pending candidate excluded from recall", "ddd444" not in pending_ids)

    finally:
        # Restore original candidates file
        if orig_file is not None:
            CANDIDATES_FILE.write_text(orig_file, encoding="utf-8")
        elif CANDIDATES_FILE.exists():
            CANDIDATES_FILE.unlink()

    # 8. No raw frame storage by default
    print("\n  -- Raw storage safety --")
    c2 = VideoObservationCandidate()
    check("raw_frames_stored defaults False", not c2.raw_frames_stored)
    check("raw_transcript_stored defaults False", not c2.raw_transcript_stored)

    # create_candidate never sets raw_frames_stored unless debug
    fake_meta = {"duration_seconds": 60.0, "width": 1920, "height": 1080, "error": ""}
    fake_frames = {"frame_count": 0, "sample_descriptions": [], "error": "test", "frames_stored_to": ""}
    c3 = create_candidate("fake.mov", fake_meta, fake_frames, approved_by_noah=True)
    check("create_candidate: raw_frames_stored=False by default", not c3.raw_frames_stored)
    check("create_candidate: raw_transcript_stored=False always", not c3.raw_transcript_stored)

    # 9. No raw transcript storage — field is always False
    c4 = VideoObservationCandidate(raw_transcript_stored=True)   # try to force True
    # The save/load cycle should accept whatever is set — the law is in the pipeline
    check("raw_transcript_stored can be set to True (model allows it)",
          c4.raw_transcript_stored)
    # But analyze_video always creates with False
    check("analyze_video pipeline always sets raw_transcript_stored=False",
          not c3.raw_transcript_stored)

    # 10. Unknowns preserved
    print("\n  -- Unknowns preservation --")
    c5 = VideoObservationCandidate()
    c5.unknowns.append("Visual content of mid-section unknown — no frame at t=30s")
    c5.unknowns.append("Audio content unknown — no transcript")
    check("Unknowns list is preserved", len(c5.unknowns) == 2)
    summary = c5.full_summary()
    check("Unknowns appear in full_summary()", "[UNKNOWN]" in summary)

    # 11. Sensitivity classification
    print("\n  -- Sensitivity classification --")
    check("Family file → HIGH sensitivity",
          _classify_sensitivity("family_call.mov", []) == SENSITIVITY_HIGH)
    check("Medical file → CRITICAL sensitivity",
          _classify_sensitivity("medical_checkup.mov", []) == SENSITIVITY_CRITICAL)
    check("Oracle file → MEDIUM sensitivity",
          _classify_sensitivity("oracle_desktop_failure.mov", []) == SENSITIVITY_MEDIUM)

    # 12. Category classification
    print("\n  -- Category classification --")
    check("Family call → family category",
          _classify_category("family_call.mov", []) == CATEGORY_FAMILY)
    check("Shopping file → shopping category",
          _classify_category("shopping_with_ashley.mov", []) == CATEGORY_SHOPPING)
    check("Oracle file → project_work category",
          _classify_category("oracle_build_pass.mov", []) == CATEGORY_PROJECT_WORK)

    # 13. Directory crawling blocked
    print("\n  -- Directory crawling blocked --")
    try:
        analyze_video(str(ROOT), approved_by_noah=True)
        check("Directory path raises IsADirectoryError", False, "should have raised")
    except IsADirectoryError:
        check("Directory path raises IsADirectoryError", True)
    except Exception as e:
        check("Directory blocked (different error)", False, str(e))

    # 14. summarize_candidate for missing ID
    print("\n  -- summarize_candidate missing ID --")
    result = summarize_candidate("zzzzzzzzzz_not_real")
    check("summarize_candidate returns error string for missing ID",
          "not found" in result.lower(), f"got: {result[:60]}")

    print(f"\n{passed}/{passed + failed} smoke tests passed.")
    if failed:
        print(f"FAILED: {failed} test(s).")
    else:
        print("All smoke tests passed.")
    return failed == 0


# ── CLI ────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

    args = sys.argv[1:]

    if "--smoke-test" in args or "--smoke" in args:
        ok = _smoke_test()
        sys.exit(0 if ok else 1)

    if "--analyze" in args:
        idx = args.index("--analyze")
        path = args[idx + 1] if idx + 1 < len(args) else ""
        approved = "--approved" in args
        dry = "--dry-run" in args
        if not path:
            print("Usage: python core/video_intelligence.py --analyze <path> [--approved] [--dry-run]")
            sys.exit(1)
        try:
            candidate = analyze_video(path, approved_by_noah=approved, dry_run=dry)
            print(f"\n{'[DRY RUN] ' if dry else ''}Analysis complete:\n")
            print(candidate.full_summary())
            if not dry:
                print(f"\n  Saved to: {CANDIDATES_FILE}")
        except PermissionError as e:
            print(f"\n[BLOCKED] {e}\n")
            sys.exit(1)
        except (FileNotFoundError, ValueError, IsADirectoryError) as e:
            print(f"\n[ERROR] {e}\n")
            sys.exit(1)
        sys.exit(0)

    if "--pending" in args:
        pending = list_pending()
        if not pending:
            print("\n  No pending video candidates.\n")
        else:
            print(f"\n  Pending candidates ({len(pending)}):\n")
            for c in pending:
                print(f"    {c.summary_line()}")
            print()
        sys.exit(0)

    if "--approve" in args:
        idx = args.index("--approve")
        cid = args[idx + 1] if idx + 1 < len(args) else ""
        if not cid:
            print("Usage: python core/video_intelligence.py --approve <candidate_id>")
            sys.exit(1)
        try:
            c = approve_candidate(cid)
            print(f"\n  Approved: {c.summary_line()}\n")
        except Exception as e:
            print(f"\n[ERROR] {e}\n")
            sys.exit(1)
        sys.exit(0)

    if "--all" in args:
        all_c = list_all()
        if not all_c:
            print("\n  No candidates on file.\n")
        else:
            print(f"\n  All candidates ({len(all_c)}):\n")
            for c in all_c:
                print(f"    {c.summary_line()}")
            print()
        sys.exit(0)

    if "--backend" in args:
        print(f"\n  OpenCV   : {'ok — ' + cv2.__version__ if _OPENCV_AVAILABLE else 'NOT installed'}")
        print(f"  ffprobe  : {'ok' if _FFPROBE_AVAILABLE else 'not found'}")
        if not _OPENCV_AVAILABLE:
            print(f"\n{OPENCV_INSTALL}")
        print()
        sys.exit(0)

    print("Usage:")
    print("  python core/video_intelligence.py --smoke-test")
    print("  python core/video_intelligence.py --analyze <path> --approved [--dry-run]")
    print("  python core/video_intelligence.py --pending")
    print("  python core/video_intelligence.py --approve <id>")
    print("  python core/video_intelligence.py --all")
    print("  python core/video_intelligence.py --backend")
