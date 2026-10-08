"""
core/vernacular_decoder.py — ORACLE Vernacular & Conflict-Speech Decoder v0.1

Distilled from Noah's "When Did Everyone Start Talking Like That?" thread —
the night he and Ashley watched Outlast and realized the real problem wasn't the
accent, it was conflict-speed speech: people talk over each other, drop words,
use slang as punctuation, and imply half the sentence. Under almost every
reality-TV fight there is ONE plain sentence — an accusation — buried under
compression, g-dropping, and status performance.

This module renders that plain meaning back out. It never rewrites the person's
words; it only surfaces what the phrase is doing.

Doctrine (RenderedReality, applied to language):
  - Decode meaning, do not smooth or replace the speaker's voice.
  - The lexicon is Noah.Physical's authored interpretation, kept verbatim.
  - If a phrase is recognized but Noah hasn't defined it, return UNKNOWN and
    invite him to author it. An honest gap beats a confident guess.

CLI:
  python core/vernacular_decoder.py --decode "Nah cuz you was actin' funny, that's cap"
  python core/vernacular_decoder.py --eras
  python core/vernacular_decoder.py --smoke-test
"""
from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass, field


# ── Conflict-speech lexicon ──────────────────────────────────────────────────
# Authored by Noah.Physical from the Outlast conversation. `triggers` are the
# surface phrases (with common g-dropped variants); `meaning` is his plain
# reading, preserved exactly as written.
@dataclass(frozen=True)
class LexEntry:
    triggers: tuple[str, ...]
    meaning: str


CONFLICT_LEXICON: tuple[LexEntry, ...] = (
    LexEntry(("you weird", "you acting weird", "you actin weird",
              "you acting funny", "you actin funny", "acting funny", "actin funny"),
             "I think your behavior changed and I don't trust it."),
    LexEntry(("dont play with me", "don't play with me"),
             "Stop disrespecting me or testing my boundaries."),
    LexEntry(("you know what you did",),
             "I'm accusing you of something but making you defend yourself first."),
    LexEntry(("thats cap", "that's cap", "you cappin", "you capping", "cappin"),
             "You're lying."),
    LexEntry(("im not gonna do this with you", "i'm not gonna do this with you",
              "im not doing this with you"),
             "I want to exit the argument while still winning it."),
    LexEntry(("keep that same energy",),
             "Don't change your attitude now that people are watching."),
    LexEntry(("say it with your chest",),
             "Repeat that accusation directly instead of hinting."),
    LexEntry(("its giving", "it's giving"),
             "Your behavior looks like..."),
    LexEntry(("i peeped that", "peeped that"),
             "I noticed what you did."),
    LexEntry(("you doing too much", "you doin too much"),
             "You're overreacting or making a scene."),
)

# The single sentence Noah says is hiding under almost every Outlast fight.
CONFLICT_SUBTEXT = (
    "I don't trust you, I think you're selfish, and I'm trying to make the "
    "group see it before you make me look bad."
)

# Terms Noah named but did NOT define. Recognized, but meaning stays UNKNOWN
# until he authors it — on purpose. Never invent a definition.
UNDEFINED_TERMS: tuple[str, ...] = ("no cap", "rizz", "bro is cooked", "cooked", "sus")

# Generational drift — same human emotions, different codebook.
ERAS: tuple[tuple[str, str, tuple[str, ...]], ...] = (
    ("1940s", "formal, structured public register",
     ("Now wait just a minute.", "I do not care for your tone.",
      "You're out of line.", "That's no way to speak to someone.")),
    ("1960s", "counterculture loosening",
     ("groovy", "far out", "don't trust anyone over thirty")),
    ("1990s", "MTV / mall-era slang",
     ("talk to the hand", "my bad", "phat", "all that")),
    ("2020s", "TikTok / rap / group-chat compression",
     ("it's giving", "no cap", "rizz", "bro is cooked", "you doing too much")),
)


def _normalize(text: str) -> str:
    """Lowercase, straighten + drop apostrophes (don't->dont, actin'->actin),
    turn punctuation into spaces, collapse whitespace."""
    text = text.lower().replace("’", "'").replace("`", "'")
    text = text.replace("'", "")
    text = re.sub(r"[^a-z0-9 ]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


@dataclass
class DecodeResult:
    original: str
    matches: list[tuple[str, str]] = field(default_factory=list)   # (surface, meaning)
    undefined: list[str] = field(default_factory=list)             # recognized, UNKNOWN
    subtext: str | None = None

    @property
    def is_conflict(self) -> bool:
        return bool(self.matches)


def decode(text: str) -> DecodeResult:
    """Surface the plain meaning under conflict/slang speech."""
    norm = _normalize(text)
    result = DecodeResult(original=text)

    for entry in CONFLICT_LEXICON:
        for trigger in entry.triggers:
            if _normalize(trigger) in norm:
                result.matches.append((trigger, entry.meaning))
                break  # one hit per concept is enough

    for term in UNDEFINED_TERMS:
        if _normalize(term) in norm:
            result.undefined.append(term)

    if result.matches:
        result.subtext = CONFLICT_SUBTEXT
    return result


def render(result: DecodeResult) -> str:
    """Human-readable decode report."""
    lines = [f'INPUT: "{result.original.strip()}"', ""]
    if result.matches:
        lines.append("PLAIN MEANING:")
        for surface, meaning in result.matches:
            lines.append(f'  "{surface}" -> {meaning}')
    else:
        lines.append("PLAIN MEANING: UNKNOWN (no catalogued conflict phrase found)")

    if result.undefined:
        lines.append("")
        lines.append("RECOGNIZED BUT UNDEFINED (Noah hasn't authored these yet):")
        for term in result.undefined:
            lines.append(f'  "{term}" -> UNKNOWN')

    if result.subtext:
        lines += ["", f"SUBTEXT: {result.subtext}"]
    return "\n".join(lines)


def render_eras() -> str:
    lines = ["GENERATIONAL DRIFT — same emotion, different codebook", ""]
    for era, register, samples in ERAS:
        lines.append(f"[{era}] {register}")
        for s in samples:
            lines.append(f'    "{s}"')
        lines.append("")
    return "\n".join(lines).rstrip()


def _smoke_test() -> int:
    r = decode("Nah cuz you was actin' funny, but now that's cap")
    assert r.is_conflict, "should detect conflict speech"
    meanings = [m for _, m in r.matches]
    assert "I think your behavior changed and I don't trust it." in meanings
    assert "You're lying." in meanings
    assert r.subtext == CONFLICT_SUBTEXT

    r2 = decode("the weather is nice today")
    assert not r2.is_conflict, "neutral speech is not a fight"

    r3 = decode("bro is cooked, no cap")
    assert "no cap" in r3.undefined and "bro is cooked" in r3.undefined

    print("vernacular_decoder smoke test: PASS")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="ORACLE Vernacular & Conflict-Speech Decoder")
    parser.add_argument("--decode", metavar="TEXT", help="decode a line of conflict/slang speech")
    parser.add_argument("--eras", action="store_true", help="show generational drift table")
    parser.add_argument("--smoke-test", action="store_true", help="run self-check")
    args = parser.parse_args(argv)

    if args.smoke_test:
        return _smoke_test()
    if args.eras:
        print(render_eras())
        return 0
    if args.decode:
        print(render(decode(args.decode)))
        return 0
    parser.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
