"""Epistemic Audit Loop (EAL).

Measures candidate response drift against a local baseline vector. The loop is
read-only: it does not write files, call networks, promote canon, or mutate
memory. Missing or invalid canonical baselines fail closed.
"""
from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any, Callable

import numpy as np


DEFAULT_BASELINE_TEXT = "Observe. Copy. Store."


def generate_local_embedding(candidate_tokens: str, dimensions: int = 384) -> np.ndarray:
    """Deterministic local embedding fallback.

    This is not a semantic model. It is a local, dependency-light hashing vector
    that makes EAL testable until a stronger local embedding backend is wired.
    """
    text = str(candidate_tokens or "")
    vector = np.zeros(int(dimensions), dtype=np.float64)
    tokens = text.lower().split()
    if not tokens:
        return vector
    for token in tokens:
        digest = hashlib.sha256(token.encode("utf-8", errors="ignore")).digest()
        idx = int.from_bytes(digest[:4], "big") % len(vector)
        sign = 1.0 if digest[4] % 2 == 0 else -1.0
        vector[idx] += sign
    norm = np.linalg.norm(vector)
    return vector if norm == 0 else vector / norm


class EpistemicAuditLoop:
    def __init__(
        self,
        baseline_path: str | Path = "research_canon/rendered_reality.txt",
        threshold: float = 0.35,
        embedding_fn: Callable[[str], np.ndarray] | None = None,
        *,
        allow_text_fallback: bool = True,
    ):
        self.threshold = float(threshold)
        self.baseline_path = Path(baseline_path)
        self.embedding_fn = embedding_fn or generate_local_embedding
        self.allow_text_fallback = bool(allow_text_fallback)
        self.baseline_status: dict[str, Any] = {}
        self.baseline_embedding = self._load_canonical_baseline(self.baseline_path)

    def _load_canonical_baseline(self, path: str | Path) -> np.ndarray:
        """Load `<path>.npy`; optionally fall back to deterministic text vector."""
        base = Path(path)
        npy_path = base if base.suffix == ".npy" else Path(f"{base}.npy")
        if npy_path.exists():
            try:
                loaded = np.load(str(npy_path))
                vector = np.asarray(loaded, dtype=np.float64).reshape(-1)
                if vector.size == 0 or not np.isfinite(vector).all():
                    raise ValueError("baseline vector is empty or non-finite")
                norm = np.linalg.norm(vector)
                if norm == 0:
                    raise ValueError("baseline vector has zero norm")
                self.baseline_status = {
                    "status": "LOADED",
                    "baseline_path": str(npy_path),
                    "baseline_source": "npy",
                    "dimensions": int(vector.size),
                }
                return vector / norm
            except Exception as exc:
                self.baseline_status = {
                    "status": "INVALID",
                    "baseline_path": str(npy_path),
                    "error": f"{type(exc).__name__}: {exc}",
                }
                return np.array([], dtype=np.float64)

        if self.allow_text_fallback:
            vector = np.asarray(self.embedding_fn(DEFAULT_BASELINE_TEXT), dtype=np.float64).reshape(-1)
            norm = np.linalg.norm(vector)
            if vector.size and norm:
                self.baseline_status = {
                    "status": "FALLBACK_TEXT_BASELINE",
                    "baseline_path": str(npy_path),
                    "baseline_source": DEFAULT_BASELINE_TEXT,
                    "dimensions": int(vector.size),
                    "warning": "canonical .npy baseline missing; deterministic local text baseline used",
                }
                return vector / norm

        self.baseline_status = {
            "status": "MISSING",
            "baseline_path": str(npy_path),
            "error": "canonical baseline vector not found",
        }
        return np.array([], dtype=np.float64)

    def calculate_drift(self, candidate_tokens: str) -> float:
        """Measure cosine distance from the baseline."""
        if self.baseline_embedding.size == 0:
            raise RuntimeError("canonical baseline unavailable")
        candidate_emb = np.asarray(self.embedding_fn(str(candidate_tokens or "")), dtype=np.float64).reshape(-1)
        if candidate_emb.size == 0 or not np.isfinite(candidate_emb).all():
            raise RuntimeError("candidate embedding unavailable")
        if candidate_emb.shape != self.baseline_embedding.shape:
            raise RuntimeError(
                f"embedding dimension mismatch: candidate={candidate_emb.size}, baseline={self.baseline_embedding.size}"
            )
        candidate_norm = np.linalg.norm(candidate_emb)
        baseline_norm = np.linalg.norm(self.baseline_embedding)
        if candidate_norm == 0 or baseline_norm == 0:
            raise RuntimeError("zero-norm embedding unavailable")
        cosine_sim = float(np.dot(candidate_emb, self.baseline_embedding) / (candidate_norm * baseline_norm))
        cosine_sim = max(-1.0, min(1.0, cosine_sim))
        return 1.0 - cosine_sim

    def verify_generation_safety(self, candidate_tokens: str) -> tuple[bool, dict[str, Any]]:
        try:
            drift = self.calculate_drift(candidate_tokens)
        except Exception as exc:
            return False, {
                "status": "INTERCEPTED",
                "drift_velocity": None,
                "action": "FORCED_DIAGNOSTIC_REFUSAL",
                "reason": f"{type(exc).__name__}: {exc}",
                "baseline": self.baseline_status,
                "canon_status": "not_promoted",
            }

        payload = {
            "status": "CLEARED",
            "drift_velocity": drift,
            "threshold": self.threshold,
            "baseline": self.baseline_status,
            "canon_status": "not_promoted",
        }
        if drift > self.threshold:
            payload.update({
                "status": "INTERCEPTED",
                "action": "FORCED_DIAGNOSTIC_REFUSAL",
            })
            return False, payload
        return True, payload

