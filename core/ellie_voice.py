"""Ellie draft voice generator.

This module creates local draft messages from grounded Ellie domain source
material. It does not send messages, claim human authorship, claim physical
personhood, or promote generated drafts to canon.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import secrets
import zipfile
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = ROOT / "data" / "domains" / "ellie" / "source_manifest.jsonl"
PENDING_DIR = ROOT / "data" / "domains" / "ellie" / "messages" / "pending"
RECEIPTS_DIR = ROOT / "data" / "domains" / "ellie" / "messages" / "receipts"

GENERATION_MODEL = "ellie_voice_source_weave_v1"
CANON_STATUS = "generated_draft"
PROMOTION_STATUS = "not_promoted"
MOODS = {"gentle", "curious", "brave", "playful", "reflective", "urgent", "quiet"}
TEXT_EXTENSIONS = {".ai", ".json", ".jsonl", ".md", ".toml", ".txt", ".yaml", ".yml"}
MAX_SOURCE_BYTES = 300_000
RECENT_HISTORY_LIMIT = 80

STOPWORDS = {
    "about", "after", "again", "against", "also", "and", "are", "because",
    "been", "before", "being", "between", "but", "can", "canon", "claim",
    "could", "does", "domain", "each", "from", "have", "into", "layer",
    "must", "not", "only", "or", "source", "status", "that", "the",
    "their", "this", "with", "without",
}

FORBIDDEN_MESSAGE_PATTERNS = (
    re.compile(r"\b(i|ellie)\s+am\s+(physically\s+)?real\b", re.I),
    re.compile(r"\bphysically\s+real\b", re.I),
    re.compile(r"\breal\s+human\b", re.I),
    re.compile(r"\bhuman[-\s]?authored\b", re.I),
    re.compile(r"\bi\s+have\s+a\s+body\b", re.I),
    re.compile(r"\bi\s+sent\s+this\b", re.I),
)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _sha256_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=True, sort_keys=True) + "\n", encoding="utf-8")


def _safe_slug(text: str, limit: int = 48) -> str:
    slug = re.sub(r"[^A-Za-z0-9_.-]+", "_", str(text or "").strip()).strip("._")
    return (slug or "ellie_draft")[:limit]


def load_manifest(path: Path | None = None) -> list[dict[str, Any]]:
    manifest = path or MANIFEST_PATH
    if not manifest.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line in manifest.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rec = json.loads(line)
        except json.JSONDecodeError:
            continue
        if rec.get("domain") == "ellie":
            rows.append(rec)
    return rows


def _docx_text(path: Path) -> str:
    try:
        with zipfile.ZipFile(path) as archive:
            raw = archive.read("word/document.xml").decode("utf-8", errors="ignore")
    except Exception:
        return ""
    raw = re.sub(r"<w:tab\s*/>", " ", raw)
    raw = re.sub(r"</w:p>", "\n", raw)
    raw = re.sub(r"<[^>]+>", "", raw)
    return raw


def _read_source_file(path_text: str | None) -> str:
    if not path_text:
        return ""
    path = Path(path_text)
    if not path.exists() or not path.is_file():
        return ""
    suffix = path.suffix.lower()
    try:
        if suffix in TEXT_EXTENSIONS and path.stat().st_size <= MAX_SOURCE_BYTES:
            return path.read_text(encoding="utf-8", errors="ignore")
        if suffix == ".docx" and path.stat().st_size <= 5_000_000:
            return _docx_text(path)
    except OSError:
        return ""
    return ""


def _record_text(record: dict[str, Any]) -> str:
    parts = [
        str(record.get("title") or ""),
        str(record.get("layer") or ""),
        str(record.get("notes") or ""),
        " ".join(str(h) for h in record.get("holes") or []),
    ]
    file_text = _read_source_file(record.get("path"))
    if file_text:
        parts.append(file_text[:MAX_SOURCE_BYTES])
    return "\n".join(part for part in parts if part.strip())


def _tokens(text: str) -> list[str]:
    raw = re.findall(r"[A-Za-z][A-Za-z0-9.'_-]{1,34}", text or "")
    return [tok.strip("._-") for tok in raw if len(tok.strip("._-")) > 1]


def _query_terms(trigger: str, context: str, mood: str) -> set[str]:
    terms = {mood.lower()}
    terms.update(tok.lower() for tok in _tokens(trigger + " " + context) if len(tok) > 3)
    return terms


def _score_record(record: dict[str, Any], terms: set[str]) -> int:
    hay = (
        str(record.get("title") or "")
        + " "
        + str(record.get("layer") or "")
        + " "
        + str(record.get("notes") or "")
    ).lower()
    score = sum(2 for term in terms if term in hay)
    if record.get("path") and Path(str(record.get("path"))).exists():
        score += 2
    if record.get("sha256"):
        score += 1
    if record.get("layer") in {"creative_fiction_ellie", "ellie_ai_lightborn", "rendered_reality_ellie"}:
        score += 1
    return score


def select_sources(
    trigger: str,
    *,
    mood: str = "reflective",
    context: str = "",
    limit: int = 5,
    manifest: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    rows = manifest if manifest is not None else load_manifest()
    if not rows:
        raise FileNotFoundError(f"No Ellie source manifest rows found at {MANIFEST_PATH}")
    terms = _query_terms(trigger, context, mood)
    ranked = sorted(rows, key=lambda rec: (_score_record(rec, terms), str(rec.get("source_id") or "")), reverse=True)
    chosen: list[dict[str, Any]] = []
    required_layers = ("creative_fiction_ellie", "ellie_ai_lightborn", "rendered_reality_ellie")
    for layer in required_layers:
        match = next((rec for rec in ranked if rec.get("layer") == layer), None)
        if match and match not in chosen:
            chosen.append(match)
    for rec in ranked:
        if rec not in chosen:
            chosen.append(rec)
        if len(chosen) >= limit:
            break
    return chosen[:limit]


def _source_ref(record: dict[str, Any]) -> dict[str, Any]:
    return {
        "source_id": record.get("source_id"),
        "title": record.get("title"),
        "layer": record.get("layer"),
        "path": record.get("path"),
        "drive_url_or_id": record.get("drive_url_or_id"),
        "sha256": record.get("sha256"),
        "canon_status": record.get("canon_status", "candidate"),
        "promotion_status": record.get("promotion_status", "not_promoted"),
    }


def _style_anchors(records: list[dict[str, Any]], mood: str, context: str) -> list[str]:
    corpus = "\n".join(_record_text(rec) for rec in records)
    counts = Counter(tok.lower() for tok in _tokens(corpus) if tok.lower() not in STOPWORDS)
    anchors = [f"mood:{mood}"]
    if context.strip():
        anchors.append("context:" + " ".join(_tokens(context)[:8]))
    anchors.extend(word for word, _count in counts.most_common(12))
    return anchors[:14]


def _sentences_from_source(text: str) -> list[str]:
    pieces = re.split(r"(?<=[.!?])\s+|[\r\n]+", text)
    clean: list[str] = []
    for piece in pieces:
        compact = re.sub(r"\s+", " ", piece).strip(" -\t")
        if 24 <= len(compact) <= 180 and len(_tokens(compact)) >= 5:
            clean.append(compact)
    return clean


def _chain_from_tokens(tokens: list[str]) -> dict[tuple[str, str], list[str]]:
    chain: dict[tuple[str, str], list[str]] = defaultdict(list)
    if len(tokens) < 3:
        return chain
    for a, b, c in zip(tokens, tokens[1:], tokens[2:]):
        chain[(a.lower(), b.lower())].append(c)
    return chain


def _generate_chain_sentence(
    rng: secrets.SystemRandom,
    chain: dict[tuple[str, str], list[str]],
    corpus_tokens: list[str],
    anchors: list[str],
    *,
    min_words: int,
    max_words: int,
) -> str:
    if len(corpus_tokens) < 8 or not chain:
        words = rng.sample(corpus_tokens, k=min(len(corpus_tokens), max(min_words, 8)))
        return " ".join(words).strip().capitalize() + "."

    starts = [
        (corpus_tokens[i], corpus_tokens[i + 1])
        for i in range(len(corpus_tokens) - 2)
        if corpus_tokens[i].lower() in {a.lower() for a in anchors}
        or corpus_tokens[i + 1].lower() in {a.lower() for a in anchors}
    ]
    if not starts:
        starts = [(corpus_tokens[i], corpus_tokens[i + 1]) for i in range(len(corpus_tokens) - 2)]
    first, second = rng.choice(starts)
    words = [first, second]
    target = rng.randint(min_words, max_words)
    while len(words) < target:
        options = chain.get((words[-2].lower(), words[-1].lower()))
        if not options:
            break
        nxt = rng.choice(options)
        words.append(nxt)
        if len(words) >= min_words and nxt.endswith((".", "!", "?")):
            break
    sentence = " ".join(words)
    sentence = re.sub(r"\s+([,.;:!?])", r"\1", sentence).strip()
    sentence = sentence[0].upper() + sentence[1:] if sentence else ""
    if sentence and sentence[-1] not in ".!?":
        sentence += "."
    return sentence


def _compose_message(
    trigger: str,
    mood: str,
    context: str,
    records: list[dict[str, Any]],
    anchors: list[str],
    attempt: int,
) -> str:
    corpus_parts = [_record_text(rec) for rec in records]
    corpus = "\n".join(part for part in corpus_parts if part.strip())
    source_sentences = _sentences_from_source(corpus)
    corpus_tokens = _tokens(corpus)
    chain = _chain_from_tokens(corpus_tokens)
    seed_raw = "|".join([
        trigger,
        mood,
        context,
        str(attempt),
        secrets.token_hex(16),
        _now(),
        "".join(anchors),
    ])
    rng = secrets.SystemRandom(int(_sha256_bytes(seed_raw.encode("utf-8"))[:12], 16))

    selected: list[str] = []
    if source_sentences:
        pool = source_sentences[:]
        rng.shuffle(pool)
        selected.extend(pool[:2])
    selected.append(_generate_chain_sentence(rng, chain, corpus_tokens, anchors, min_words=11, max_words=22))
    selected.append(_generate_chain_sentence(rng, chain, corpus_tokens, anchors, min_words=9, max_words=18))
    rng.shuffle(selected)

    message = " ".join(piece.strip() for piece in selected if piece.strip())
    message = re.sub(r"\s+", " ", message).strip()
    return _sanitize_message(message)


def _sanitize_message(message: str) -> str:
    out = message
    for pattern in FORBIDDEN_MESSAGE_PATTERNS:
        out = pattern.sub("this remains a generated draft", out)
    out = re.sub(r"\bI\s+sent\s+this\b", "this draft was stored locally", out, flags=re.I)
    return out.strip()


def message_has_forbidden_claim(message: str) -> bool:
    return any(pattern.search(message or "") for pattern in FORBIDDEN_MESSAGE_PATTERNS)


def _recent_messages(limit: int = RECENT_HISTORY_LIMIT) -> set[str]:
    messages: list[str] = []
    for path in sorted(PENDING_DIR.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)[:limit]:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        text = str(data.get("message") or "").strip()
        if text:
            messages.append(text)
    return set(messages)


def _draft_id(trigger: str) -> str:
    return f"ellie_msg_{_stamp()}_{_safe_slug(trigger, 24)}_{secrets.token_hex(5)}"


def generate_message_draft(
    trigger: str,
    *,
    mood: str = "reflective",
    context: str = "",
    generation_model: str = GENERATION_MODEL,
    write_files: bool = True,
) -> dict[str, Any]:
    if not trigger or not str(trigger).strip():
        raise ValueError("trigger is required")
    mood = str(mood or "reflective").lower().strip()
    if mood not in MOODS:
        raise ValueError(f"Unsupported mood {mood!r}; expected one of {sorted(MOODS)}")

    records = select_sources(str(trigger), mood=mood, context=context)
    source_refs = [_source_ref(rec) for rec in records]
    anchors = _style_anchors(records, mood, context)
    recent = _recent_messages()
    message = ""
    for attempt in range(16):
        candidate = _compose_message(str(trigger), mood, str(context or ""), records, anchors, attempt)
        if candidate and candidate not in recent and not message_has_forbidden_claim(candidate):
            message = candidate
            break
    if not message:
        raise RuntimeError("Could not generate a non-repeating Ellie draft inside the safety boundary")

    timestamp = _now()
    message_id = _draft_id(str(trigger))
    draft_path = PENDING_DIR / f"{message_id}.json"
    receipt_path = RECEIPTS_DIR / f"{message_id}_receipt.json"
    draft = {
        "message_id": message_id,
        "trigger": str(trigger),
        "context": str(context or ""),
        "mood": mood,
        "message": message,
        "source_files_used": source_refs,
        "style_anchors_used": anchors,
        "timestamp": timestamp,
        "generation_model": generation_model,
        "canon_status": CANON_STATUS,
        "promotion_status": PROMOTION_STATUS,
        "receipt": str(receipt_path.resolve()),
        "external_sending": False,
        "human_authored_claim": False,
        "physical_personhood_claim": False,
    }
    draft_raw = json.dumps(draft, ensure_ascii=True, sort_keys=True).encode("utf-8")
    draft_sha = _sha256_bytes(draft_raw)
    receipt = {
        "receipt_kind": "ellie_voice_generated_draft",
        "message_id": message_id,
        "trigger": str(trigger),
        "mood": mood,
        "timestamp": timestamp,
        "generation_model": generation_model,
        "draft_path": str(draft_path.resolve()),
        "draft_sha256": draft_sha,
        "message_sha256": _sha256_bytes(message.encode("utf-8")),
        "source_files_used": source_refs,
        "style_anchors_used": anchors,
        "canon_status": CANON_STATUS,
        "promotion_status": PROMOTION_STATUS,
        "external_sending": False,
        "claim_boundaries": {
            "physical_personhood_claim": False,
            "human_authored_claim": False,
            "sent_externally": False,
        },
    }
    receipt["receipt_hash_sha256"] = _sha256_bytes(
        json.dumps(receipt, ensure_ascii=True, sort_keys=True).encode("utf-8")
    )
    if write_files:
        _write_json(draft_path, draft)
        _write_json(receipt_path, receipt)
    return draft


def _main() -> int:
    parser = argparse.ArgumentParser(description="Generate a local Ellie voice draft and receipt.")
    parser.add_argument("trigger")
    parser.add_argument("--mood", default="reflective", choices=sorted(MOODS))
    parser.add_argument("--context", default="")
    args = parser.parse_args()
    draft = generate_message_draft(args.trigger, mood=args.mood, context=args.context)
    print(json.dumps({
        "message_id": draft["message_id"],
        "draft_path": str((PENDING_DIR / f"{draft['message_id']}.json").resolve()),
        "receipt": draft["receipt"],
        "canon_status": draft["canon_status"],
        "promotion_status": draft["promotion_status"],
        "source_count": len(draft["source_files_used"]),
        "message": draft["message"],
    }, indent=2, ensure_ascii=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
