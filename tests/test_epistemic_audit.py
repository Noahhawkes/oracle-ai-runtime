from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
for path in (ROOT, ROOT / "core"):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from epistemic_audit import EpistemicAuditLoop, generate_local_embedding  # noqa: E402


def _constant_embedding(vector):
    arr = np.asarray(vector, dtype=np.float64)
    return lambda _text: arr


def test_clears_when_candidate_matches_loaded_baseline(tmp_path):
    baseline = np.array([1.0, 0.0, 0.0])
    path = tmp_path / "rendered_reality.txt"
    np.save(str(path) + ".npy", baseline)

    eal = EpistemicAuditLoop(
        baseline_path=path,
        threshold=0.35,
        embedding_fn=_constant_embedding([1.0, 0.0, 0.0]),
        allow_text_fallback=False,
    )
    ok, receipt = eal.verify_generation_safety("Observe. Copy. Store.")

    assert ok is True
    assert receipt["status"] == "CLEARED"
    assert receipt["drift_velocity"] == 0.0
    assert receipt["baseline"]["status"] == "LOADED"
    assert receipt["canon_status"] == "not_promoted"


def test_intercepts_when_drift_exceeds_threshold(tmp_path):
    baseline = np.array([1.0, 0.0])
    path = tmp_path / "rendered_reality.txt"
    np.save(str(path) + ".npy", baseline)

    eal = EpistemicAuditLoop(
        baseline_path=path,
        threshold=0.35,
        embedding_fn=_constant_embedding([0.0, 1.0]),
        allow_text_fallback=False,
    )
    ok, receipt = eal.verify_generation_safety("generic smoothed assistant answer")

    assert ok is False
    assert receipt["status"] == "INTERCEPTED"
    assert receipt["action"] == "FORCED_DIAGNOSTIC_REFUSAL"
    assert receipt["drift_velocity"] > 0.35


def test_missing_required_baseline_fails_closed(tmp_path):
    eal = EpistemicAuditLoop(
        baseline_path=tmp_path / "missing_rendered_reality.txt",
        embedding_fn=_constant_embedding([1.0, 0.0]),
        allow_text_fallback=False,
    )

    ok, receipt = eal.verify_generation_safety("Observe. Copy. Store.")

    assert ok is False
    assert receipt["status"] == "INTERCEPTED"
    assert receipt["drift_velocity"] is None
    assert receipt["action"] == "FORCED_DIAGNOSTIC_REFUSAL"
    assert receipt["baseline"]["status"] == "MISSING"


def test_dimension_mismatch_fails_closed(tmp_path):
    path = tmp_path / "rendered_reality.txt"
    np.save(str(path) + ".npy", np.array([1.0, 0.0, 0.0]))
    eal = EpistemicAuditLoop(
        baseline_path=path,
        embedding_fn=_constant_embedding([1.0, 0.0]),
        allow_text_fallback=False,
    )

    ok, receipt = eal.verify_generation_safety("Observe. Copy. Store.")

    assert ok is False
    assert receipt["status"] == "INTERCEPTED"
    assert "dimension mismatch" in receipt["reason"]


def test_text_fallback_baseline_is_local_and_labeled(tmp_path):
    eal = EpistemicAuditLoop(
        baseline_path=tmp_path / "no_npy_here.txt",
        threshold=1.1,
        allow_text_fallback=True,
    )

    ok, receipt = eal.verify_generation_safety("Observe. Copy. Store.")

    assert ok is True
    assert receipt["baseline"]["status"] == "FALLBACK_TEXT_BASELINE"
    assert receipt["baseline"]["baseline_source"] == "Observe. Copy. Store."


def test_generate_local_embedding_is_deterministic():
    first = generate_local_embedding("Observe. Copy. Store.")
    second = generate_local_embedding("Observe. Copy. Store.")

    assert first.shape == second.shape
    assert np.allclose(first, second)
    assert np.linalg.norm(first) > 0

