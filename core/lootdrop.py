"""
core/lootdrop.py — ORACLE LootDrop: Momentum Recognition System

LootDrop is not gamification.
LootDrop is ORACLE recognizing meaningful progress, compressing it into
elevated memory, and rewarding momentum.

Architecture:
  Milestone/Decision → award() → reveal (console/overlay) → memory DB

Tiers: Common → Uncommon → Rare → Epic → Legendary → Mythic

Each tier has its own reveal language, pacing, and memory priority.
Mythic tier has full metadata, elevated naming, dramatic pacing,
animation and sound hooks, and highest memory priority in all recaps.

No new pip packages required. Stdlib only (time, json, datetime).
Memory stored via existing memory.upsert_fact().
"""

import time
from datetime import datetime
from pathlib import Path

# ── Tier Definitions ─────────────────────────────────────────────────────────
# Each tier is a dict. Do not hardcode tier-specific behavior outside this map.
# Add new tiers here — callers use TIERS[name], not string literals.

TIERS = {
    "common": {
        "rank":              0,
        "label":             "Common",
        "symbol":            "[ + ]",
        "memory_priority":   1,
        "memory_category":   "lootdrop",
        "elevated_naming":   False,
        "dramatic_pacing":   False,
        "animation_hook":    False,
        "sound_hook":        False,
        "reward_language":   [
            "Progress logged.",
            "Small win recorded.",
            "Momentum noted.",
            "Step complete.",
        ],
    },
    "uncommon": {
        "rank":              1,
        "label":             "Uncommon",
        "symbol":            "[++]",
        "memory_priority":   2,
        "memory_category":   "lootdrop",
        "elevated_naming":   False,
        "dramatic_pacing":   False,
        "animation_hook":    False,
        "sound_hook":        False,
        "reward_language":   [
            "Solid progress. Logged.",
            "That counts. Building momentum.",
            "Habit reinforced. System learning.",
            "Good move. Recorded.",
        ],
    },
    "rare": {
        "rank":              2,
        "label":             "Rare",
        "symbol":            "[***]",
        "memory_priority":   3,
        "memory_category":   "lootdrop",
        "elevated_naming":   False,
        "dramatic_pacing":   True,
        "animation_hook":    False,
        "sound_hook":        False,
        "reward_language":   [
            "Milestone reached.",
            "Module shipped. This one matters.",
            "Rare drop. This goes in the record.",
            "That was real work. Logged with priority.",
        ],
    },
    "epic": {
        "rank":              3,
        "label":             "Epic",
        "symbol":            "[EPIC]",
        "memory_priority":   4,
        "memory_category":   "lootdrop",
        "elevated_naming":   True,
        "dramatic_pacing":   True,
        "animation_hook":    True,
        "sound_hook":        False,
        "reward_language":   [
            "EPIC DROP. System working end-to-end.",
            "This is what progress looks like.",
            "Major decision locked in. ORACLE remembers this.",
            "End-to-end. That is rare. Logged as Epic.",
        ],
    },
    "legendary": {
        "rank":              4,
        "label":             "Legendary",
        "symbol":            "[ LEGENDARY ]",
        "memory_priority":   5,
        "memory_category":   "lootdrop",
        "elevated_naming":   True,
        "dramatic_pacing":   True,
        "animation_hook":    True,
        "sound_hook":        True,
        "reward_language":   [
            "LEGENDARY. This milestone changes the trajectory.",
            "You just crossed a threshold most people never reach.",
            "This is the kind of moment ORACLE was built to remember.",
            "A full product milestone. Legendary status confirmed.",
        ],
    },
    "mythic": {
        "rank":              5,
        "label":             "Mythic",
        "symbol":            "[ ** MYTHIC ** ]",
        "memory_priority":   10,          # Highest — always first in recaps
        "memory_category":   "lootdrop_mythic",
        "elevated_naming":   True,
        "dramatic_pacing":   True,
        "animation_hook":    True,        # Overlay can attach animation here
        "sound_hook":        True,        # OS notification hook
        "reward_language":   [
            "MYTHIC DROP.",
            "This is a category-defining moment.",
            "ORACLE has witnessed something that changes how you operate.",
            "This goes at the top of every recap. Always.",
            "The system remembers this. So will you.",
        ],
    },
}

# Ordered list for iteration / validation
TIER_NAMES = ["common", "uncommon", "rare", "epic", "legendary", "mythic"]


def _validate_tier(tier: str) -> str:
    """Normalise and validate tier name. Raises ValueError if invalid."""
    t = tier.strip().lower()
    if t not in TIERS:
        raise ValueError(
            f"Unknown LootDrop tier: '{tier}'. "
            f"Valid tiers: {', '.join(TIER_NAMES)}"
        )
    return t


def _reveal(tier_key: str, metadata: dict) -> None:
    """
    Print the LootDrop reveal to the console.
    Tier-specific pacing and language applied here.
    Overlay / GUI callers can replace this by wrapping award() and
    checking metadata['animation_hook'] and metadata['sound_hook'].
    """
    cfg = TIERS[tier_key]
    symbol = cfg["symbol"]
    label = cfg["label"]
    lines = cfg["reward_language"]

    # Pick reward line (rotate by minute so it varies without randomness)
    line = lines[datetime.now().minute % len(lines)]

    if cfg["dramatic_pacing"]:
        print()
        time.sleep(0.3)
        print(f"  {symbol}")
        time.sleep(0.4)

        if cfg["elevated_naming"]:
            print(f"  {label.upper()} LOOT DROP")
        else:
            print(f"  {label} LootDrop")

        time.sleep(0.3)
        print(f"  {line}")
        time.sleep(0.2)

        # Mythic gets the full dramatic beat
        if tier_key == "mythic":
            time.sleep(0.5)
            print()
            print(f"  Project : {metadata.get('related_project', 'ORACLE.AI')}")
            print(f"  Earned  : {metadata.get('reason_earned', '')}")
            if metadata.get("significance"):
                print(f"  Signal  : {metadata['significance']}")
            if metadata.get("suggested_follow_up_action"):
                print(f"  Next    : {metadata['suggested_follow_up_action']}")
            time.sleep(0.3)
        print()

    else:
        # Common / Uncommon — clean single line
        print(f"\n  {symbol} {label}: {line}\n")


def award(
    tier: str,
    source_activity: str,
    reason_earned: str,
    related_project: str = "ORACLE.AI",
    significance: str = "",
    suggested_follow_up_action: str = "",
) -> dict:
    """
    Award a LootDrop for a meaningful moment.

    Parameters
    ----------
    tier                      : str  — one of TIER_NAMES
    source_activity           : str  — what activity triggered this drop
    reason_earned             : str  — why this tier was awarded
    related_project           : str  — which project this connects to
    significance              : str  — what this moment means (optional, Mythic especially)
    suggested_follow_up_action: str  — what to do next (optional)

    Returns
    -------
    dict — full LootDrop metadata (also written to memory DB)
    """
    tier_key = _validate_tier(tier)
    cfg = TIERS[tier_key]
    ts = datetime.now().isoformat()

    metadata = {
        "tier":                      cfg["label"],
        "tier_rank":                 cfg["rank"],
        "source_activity":           source_activity,
        "reason_earned":             reason_earned,
        "related_project":           related_project,
        "timestamp":                 ts,
        "significance":              significance,
        "suggested_follow_up_action": suggested_follow_up_action,
        "memory_priority":           cfg["memory_priority"],
        "animation_hook":            cfg["animation_hook"],
        "sound_hook":                cfg["sound_hook"],
    }

    # Reveal in console
    _reveal(tier_key, metadata)

    # Persist to memory DB
    try:
        import sys
        from pathlib import Path as _Path
        sys.path.insert(0, str(_Path(__file__).parent))
        from memory import upsert_fact

        # Key is timestamp-based so each award is a separate fact
        fact_key = f"{tier_key}_{ts[:16].replace(':', '').replace('-', '').replace('T', '_')}"
        import json as _json
        upsert_fact(cfg["memory_category"], fact_key, _json.dumps(metadata))

        # Mythic also writes a human-readable summary fact for easy recall
        if tier_key == "mythic":
            summary = (
                f"[MYTHIC] {reason_earned} | "
                f"Project: {related_project} | "
                f"Signal: {significance} | "
                f"Next: {suggested_follow_up_action}"
            )
            upsert_fact("lootdrop_mythic", f"summary_{fact_key}", summary)

    except Exception as e:
        # Memory write failure must never crash the reveal
        print(f"  [lootdrop] memory write skipped: {e}")

    return metadata


def last_drops(n: int = 5, min_tier: str = "common") -> list:
    """
    Retrieve the last N LootDrop awards from memory, filtered by minimum tier rank.

    Parameters
    ----------
    n        : int — max results to return
    min_tier : str — only return drops at this tier or above

    Returns
    -------
    list of metadata dicts, most recent first
    """
    import json as _json
    import sys
    from pathlib import Path as _Path
    sys.path.insert(0, str(_Path(__file__).parent))
    from memory import get_facts

    min_rank = TIERS[_validate_tier(min_tier)]["rank"]

    results = []
    # Collect from both lootdrop categories
    for cat in ("lootdrop", "lootdrop_mythic"):
        for fact in get_facts(cat):
            if fact["key"].startswith("summary_"):
                continue  # skip human-readable summaries (they're duplicates)
            try:
                meta = _json.loads(fact["value"])
                if meta.get("tier_rank", 0) >= min_rank:
                    results.append(meta)
            except Exception:
                continue

    # Sort by timestamp descending
    results.sort(key=lambda m: m.get("timestamp", ""), reverse=True)
    return results[:n]


def recap_summary(n: int = 5) -> str:
    """
    Return a human-readable recap of recent LootDrops for use in daily briefs
    and session summaries. Mythic drops always appear first regardless of date.
    """
    drops = last_drops(n=20, min_tier="common")

    # Mythic always first
    mythic = [d for d in drops if d.get("tier_rank", 0) == TIERS["mythic"]["rank"]]
    rest = [d for d in drops if d.get("tier_rank", 0) < TIERS["mythic"]["rank"]]

    ordered = (mythic + rest)[:n]

    if not ordered:
        return "No LootDrops recorded yet."

    lines = ["--- LootDrop Recap ---"]
    for d in ordered:
        label = d.get("tier", "?")
        project = d.get("related_project", "")
        reason = d.get("reason_earned", "")
        ts = d.get("timestamp", "")[:10]
        lines.append(f"  [{label}] {reason} ({project}) — {ts}")

    return "\n".join(lines)
