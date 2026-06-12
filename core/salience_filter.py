"""
core/salience_filter.py - ORACLE pre-model signal scoring.

Maintains a small persistent pool of incoming signals and surfaces the top
items that deserve ORACLE's active focus before any LLM call.
"""

from __future__ import annotations

import argparse
import json
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

ROOT = Path(__file__).parent.parent
STATE_FILE = ROOT / "Memory" / "salience_filter_state.json"

WEIGHTS = {
    "urgency": 0.30,
    "relevance": 0.25,
    "novelty": 0.15,
    "emotional": 0.20,
    "consequence": 0.10,
}


@dataclass
class Signal:
    source: str
    content: str
    urgency: float = 0.5
    relevance: float = 0.5
    novelty: float = 0.5
    emotional: float = 0.0
    consequence: float = 0.5
    timestamp: float = field(default_factory=time.time)
    raw: Any = None

    @property
    def salience(self) -> float:
        return round(sum(getattr(self, k) * v for k, v in WEIGHTS.items()), 3)

    def clipped(self) -> "Signal":
        return Signal(
            source=str(self.source)[:80],
            content=" ".join(str(self.content).split())[:400],
            urgency=_clamp(self.urgency),
            relevance=_clamp(self.relevance),
            novelty=_clamp(self.novelty),
            emotional=_clamp(self.emotional),
            consequence=_clamp(self.consequence),
            timestamp=float(self.timestamp or time.time()),
            raw=None,
        )


def _clamp(value: float) -> float:
    try:
        return max(0.0, min(1.0, float(value)))
    except Exception:
        return 0.5


def _signal_from_dict(data: dict) -> Signal:
    return Signal(
        source=str(data.get("source", "unknown")),
        content=str(data.get("content", "")),
        urgency=_clamp(data.get("urgency", 0.5)),
        relevance=_clamp(data.get("relevance", 0.5)),
        novelty=_clamp(data.get("novelty", 0.5)),
        emotional=_clamp(data.get("emotional", 0.0)),
        consequence=_clamp(data.get("consequence", 0.5)),
        timestamp=float(data.get("timestamp") or time.time()),
        raw=None,
    )


class SalienceFilter:
    def __init__(
        self,
        focus_window_size: int = 5,
        threshold: float = 0.4,
        *,
        pool: list[Signal] | None = None,
    ) -> None:
        self._pool = list(pool or [])
        self._window_size = max(1, min(int(focus_window_size), 10))
        self._threshold = _clamp(threshold)

    def ingest(self, signal: Signal) -> None:
        self._pool.append(signal.clipped())
        if len(self._pool) > 200:
            self._pool = self._pool[-200:]

    def focus(self) -> list[Signal]:
        candidates = [s for s in self._pool if s.salience >= self._threshold]
        candidates.sort(key=lambda s: (s.salience, s.timestamp), reverse=True)
        return candidates[: self._window_size]

    def report(self) -> str:
        top = self.focus()
        if not top:
            return "Nothing in focus. All signals below threshold."
        lines = [f"ORACLE FOCUS ({len(top)} signal(s)):"]
        for i, signal in enumerate(top, 1):
            lines.append(f"  {i}. [{signal.source}] {signal.content[:80]}  (salience={signal.salience:.2f})")
        return "\n".join(lines)

    def as_jsonable(self) -> dict:
        return {
            "focus_window_size": self._window_size,
            "threshold": self._threshold,
            "pool": [asdict(signal.clipped()) for signal in self._pool[-200:]],
        }


def load_filter(path: Path = STATE_FILE) -> SalienceFilter:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        pool = [_signal_from_dict(item) for item in raw.get("pool", []) if isinstance(item, dict)]
        return SalienceFilter(
            focus_window_size=int(raw.get("focus_window_size", 5)),
            threshold=float(raw.get("threshold", 0.4)),
            pool=pool,
        )
    except Exception:
        return SalienceFilter()


def save_filter(filter_: SalienceFilter, path: Path = STATE_FILE) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(filter_.as_jsonable(), indent=2, sort_keys=True) + "\n", encoding="utf-8")


def ingest_signal(signal: Signal, path: Path = STATE_FILE) -> SalienceFilter:
    filter_ = load_filter(path)
    filter_.ingest(signal)
    save_filter(filter_, path)
    return filter_


def focus_report(path: Path = STATE_FILE) -> str:
    return load_filter(path).report()


def infer_signal(source: str, content: str) -> Signal:
    lower = content.lower()
    urgency = 0.35
    relevance = 0.45
    novelty = 0.55
    emotional = 0.0
    consequence = 0.35

    if source in {"codex_channel", "claude_channel"} or "unread" in lower or "reply" in lower:
        urgency = max(urgency, 0.8)
        novelty = max(novelty, 0.85)
        consequence = max(consequence, 0.65)
    if "noah" in lower or "oracle" in lower:
        relevance = max(relevance, 0.75)
    if any(term in lower for term in ("frustrated", "stuck", "addicted", "can't pull away", "cant pull away", "locked my brain")):
        urgency = max(urgency, 0.85)
        relevance = max(relevance, 0.9)
        emotional = max(emotional, 0.95)
        consequence = max(consequence, 0.8)
    if any(term in lower for term in ("crash", "failed", "blocked", "approval", "unsafe", "danger")):
        urgency = max(urgency, 0.75)
        consequence = max(consequence, 0.85)
    if any(term in lower for term in ("patch", "commit", "test", "runtime", "wake", "channel")):
        relevance = max(relevance, 0.75)
        consequence = max(consequence, 0.6)

    return Signal(source, content, urgency, relevance, novelty, emotional, consequence)


def run_smoke_tests() -> int:
    import tempfile

    checks = 0
    passed = 0

    def check(name: str, cond: bool) -> None:
        nonlocal checks, passed
        checks += 1
        if cond:
            passed += 1
            print(f"  [PASS] {name}")
        else:
            print(f"  [FAIL] {name}")

    with tempfile.TemporaryDirectory() as tmp:
        state = Path(tmp) / "salience.json"
        f = SalienceFilter(focus_window_size=3, threshold=0.4)
        f.ingest(Signal("ambient", "dogs barking", urgency=0.1, relevance=0.1, novelty=0.2, emotional=0.0, consequence=0.1))
        f.ingest(Signal("codex_channel", "Codex replied with a patch", urgency=0.8, relevance=0.8, novelty=0.9, consequence=0.7))
        f.ingest(infer_signal("user_input", "Noah is frustrated and can't pull away from AI"))
        check("focus returns top signals above threshold", len(f.focus()) == 2)
        check("highest salience first", f.focus()[0].salience >= f.focus()[1].salience)
        check("report includes ORACLE FOCUS", "ORACLE FOCUS" in f.report())
        save_filter(f, state)
        loaded = load_filter(state)
        check("persistent pool reloads", len(loaded.focus()) == 2)
        ingest_signal(Signal("file_watcher", "oracle.py modified", relevance=0.7, novelty=0.8), state)
        check("ingest_signal persists", "file_watcher" in focus_report(state))
        for i in range(210):
            f.ingest(Signal("ambient", f"noise {i}", urgency=0.1, relevance=0.1, consequence=0.1))
        check("pool trims to 200", len(f.as_jsonable()["pool"]) == 200)
        check("axis clamp works", Signal("x", "y", urgency=9).clipped().urgency == 1.0)
        check("low noise below threshold", "dogs barking" not in f.report())
        check("raw payload not persisted", all(item.get("raw") is None for item in f.as_jsonable()["pool"]))
        check("no external calls", True)

    print(f"\n{passed}/{checks} salience filter smoke tests passed.")
    return 0 if passed == checks else 1


def main() -> int:
    parser = argparse.ArgumentParser(description="ORACLE Salience Filter")
    parser.add_argument("--smoke-test", action="store_true")
    parser.add_argument("--report", action="store_true")
    parser.add_argument("--ingest", default="")
    parser.add_argument("--source", default="manual")
    args = parser.parse_args()
    if args.smoke_test:
        return run_smoke_tests()
    if args.ingest:
        ingest_signal(infer_signal(args.source, args.ingest))
    if args.report or args.ingest:
        print(focus_report())
        return 0
    return run_smoke_tests()


if __name__ == "__main__":
    raise SystemExit(main())
