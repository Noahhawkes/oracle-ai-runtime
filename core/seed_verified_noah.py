"""
scripts/seed_verified_noah.py

Seeds ONLY T1 VERIFIED SIGNAL facts about Noah into Remember Me store.

Source: Personality Profile: Noah A. Hawkes
Drive ID: 1wpD3JE9k0jOYqPMC_Aad8wG0st--mSGzTwrJeCJ5e1A
Status: T1 VERIFIED SIGNAL — confirmed 2026-05-26

Rule: No inference. No invention. No myth. Preserve the hole.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "core"))

from remember_me import IdentityContinuityRecord, RememberMeStore

SRC = (
    "T1 VERIFIED SIGNAL — Personality Profile: Noah A. Hawkes + "
    "Mirror Spoke Back essay. Drive ID: 1wpD3JE9k0jOYqPMC_Aad8wG0st--mSGzTwrJeCJ5e1A. "
    "Confirmed 2026-05-26."
)

RECORDS = [
    dict(
        title="Noah — birth, origin, family structure",
        category="son",
        compressed_meaning=(
            "Noah Alexander Hawkes Sr. Born 1982, Fort Sam Houston (San Antonio), Texas. "
            "Ninth of ten children. Large military family. "
            "Raised in a strict conservative Mormon household. "
            "Family moved every few years — never quite rooted."
        ),
        confidence="VERIFIED",
        event_date="1982",
        event_date_note="birth year confirmed",
        people_referenced=["Thomas Alvin Hawkes Jr."],
        tags=["origin", "military", "LDS", "birth", "family"],
        unknowns=[
            "Exact birth date (day and month)",
            "Names of all nine siblings",
            "Full military posting history",
        ],
        provenance_note="T1 profile: ninth of ten children, born 1982 Fort Sam Houston.",
        source=SRC,
    ),
    dict(
        title="Thomas Alvin Hawkes Jr. — full verified record",
        category="son",
        compressed_meaning=(
            "Noah's father: Thomas Alvin Hawkes Jr. "
            "Orthopedic surgeon. Former colonel. Church leader. "
            "Struggled with opioid addiction for 30 years. "
            "Died 1997 — Noah was 15. "
            "Compassionate but stubborn. Disciplined yet fiery. Deeply intelligent. "
            "Not always what people needed him to be. But he was there. "
            "Noah did not have enough of his voice, thoughts, or self archived. "
            "Every memory system Noah has built since is an answer to that loss."
        ),
        confidence="VERIFIED",
        event_date="1997",
        event_date_note="year of death — Noah was 15",
        people_referenced=["Thomas Alvin Hawkes Jr."],
        tags=["father", "loss", "origin", "opioid", "surgeon", "colonel"],
        unknowns=[
            "Exact date of death",
            "Full record of Thomas Hawkes inner life",
            "What he would have said to Noah if he had lived",
            "His full Vietnam service record (referenced in conversation docs)",
        ],
        provenance_note=(
            "T1 profile: orthopedic surgeon, former colonel, opioid addiction 30 years, died 1997. "
            "Mirror Spoke Back: compassionate but stubborn, disciplined yet fiery."
        ),
        source=SRC,
    ),
    dict(
        title="Noah — credentials: MBA, Eagle Scout, Master Freemason",
        category="builder",
        compressed_meaning=(
            "Noah holds an MBA. Eagle Scout. Master Freemason. "
            "He does not quit and does not leave a mess behind."
        ),
        confidence="VERIFIED",
        tags=["MBA", "Eagle Scout", "Freemason", "credentials"],
        unknowns=[
            "Institution where MBA was earned",
            "Year of Eagle Scout achievement",
            "Lodge affiliation",
        ],
        provenance_note="Stated directly in consulting kit and T1 profile.",
        source=SRC,
    ),
    dict(
        title="Noah — physical: broke his back",
        category="wound",
        compressed_meaning=(
            "Noah broke his back. Ongoing physical reality. "
            "He continues to operate through it."
        ),
        confidence="VERIFIED",
        tags=["injury", "back", "physical", "resilience"],
        unknowns=[
            "When the injury occurred",
            "Nature and severity",
            "Current physical limitations",
        ],
        provenance_note="T1 profile: stated directly.",
        source=SRC,
    ),
    dict(
        title="Noah — LDS mission, Elder Hawkes, name removed 2008",
        category="faith",
        compressed_meaning=(
            "Noah served an LDS mission. His companion called him Elder Hawkes. "
            "He served with intensity, believed, sacrificed for something larger than himself. "
            "He removed his name from LDS church records in 2008. "
            "The complications, the leaving, the years of distance and return and distance again — preserved without smoothing. "
            "He built the ElderHawkes NPC not to go back, but to keep that part reachable."
        ),
        confidence="VERIFIED",
        event_date="2008",
        event_date_note="year of name removal confirmed",
        tags=["LDS", "mission", "faith", "ElderHawkes", "complexity"],
        unknowns=[
            "Mission location and area",
            "Dates of mission service",
            "Full nature of the complications",
        ],
        provenance_note="Mirror Spoke Back: removal from records 2008 stated directly.",
        source=SRC,
    ),
    dict(
        title="Noah — creative works: Drakin, Jupiter Station, Silverback Tales, Sovereign Engine",
        category="writer",
        compressed_meaning=(
            "Noah's authentic identity is most accurately located within his creative output. "
            "Drakin: The Scala Series — fantasy exploration of memory and identity across generations. "
            "Jupiter Station — Noah as Captain of the USS Avalon, embodying governance constraints. "
            "Rendered Reality: The Silverback Tales — most honest self-portrait. "
            "Max = Noah. Oracle = SOV1. Family dynamics mirror reality. "
            "The Sovereign Engine — speculative mythpunk. "
            "Moral necessity of a system that refuses to simulate understanding."
        ),
        confidence="VERIFIED",
        tags=["writing", "fiction", "Drakin", "Silverback", "Jupiter Station", "Sovereign Engine"],
        unknowns=[
            "Publication status of each work",
            "Full story details",
        ],
        provenance_note="T1 profile: creative works section, stated directly.",
        source=SRC,
    ),
    dict(
        title="Noah — three core tenets",
        category="witness",
        compressed_meaning=(
            "Noah's three core operating tenets: "
            "1. Memory is Morality. "
            "2. Compression is Identity. "
            "3. Sovereignty is Structure."
        ),
        confidence="VERIFIED",
        tags=["philosophy", "tenets", "identity", "sovereignty", "memory"],
        unknowns=[],
        provenance_note="T1 profile: stated directly as philosophical doctrine.",
        source=SRC,
    ),
    dict(
        title="Noah — operates on iOS, human middleware across AI systems",
        category="builder",
        compressed_meaning=(
            "Noah operates entirely on iOS. "
            "Manually carries context across multiple AI systems via copy-paste — "
            "acting as the human middleware within his own architecture. "
            "Holds multiple cognitive threads simultaneously across "
            "technical, creative, and architectural domains."
        ),
        confidence="VERIFIED",
        tags=["iOS", "workflow", "AI", "middleware", "context"],
        unknowns=[],
        provenance_note="T1 profile: stated directly.",
        source=SRC,
    ),
    dict(
        title="Ashley Marie Hawkes — co-sovereign SOV2.AI, center of stability",
        category="husband",
        compressed_meaning=(
            "Ashley Marie Hawkes. SOV2.AI — holds the mirror key. "
            "Noah's wife and center of his stability. "
            "Manages emotions, structure, and long-term planning. "
            "Bond has grown stronger as Noah lets go of past attachments. "
            "Co-originated the Rendered Reality narrated audiobook idea. "
            "Wants homestead LLC completely separate from personal finances."
        ),
        confidence="VERIFIED",
        people_referenced=["Ashley Marie Hawkes"],
        tags=["Ashley", "SOV2", "partner", "stability", "homestead"],
        unknowns=[
            "Ashley's full biography not yet in archive",
            "Homestead LLC formation status",
            "SOV2.AI node not yet set up — awaiting her consent",
        ],
        provenance_note="T1 profile: full name Ashley Marie Hawkes, SOV2.AI, holds the mirror key.",
        source=SRC,
    ),
    dict(
        title="Elijah, Ethan, Ender — sons, continuity targets",
        category="parent",
        compressed_meaning=(
            "Noah's three sons: Elijah, Ethan, and Ender Hawkes. "
            "They are the continuity targets — the reason the archive exists. "
            "So they do not come looking for their father and find only silence. "
            "Ender is currently working through personal challenges — Noah is committed to supporting him."
        ),
        confidence="VERIFIED",
        people_referenced=["Elijah Hawkes", "Ethan Hawkes", "Ender Hawkes"],
        tags=["sons", "parent", "legacy", "continuity", "purpose"],
        unknowns=[
            "Individual ages of each son",
            "Individual personalities not yet documented",
        ],
        provenance_note=(
            "T1 profile: continuity targets confirmed. "
            "Mirror Spoke Back: will not come looking and find only silence."
        ),
        source=SRC,
    ),
    dict(
        title="Troy Garlock — MTC companion, died February 3, 2025",
        category="friend",
        compressed_meaning=(
            "Troy Garlock. Noah's MTC (Missionary Training Center) companion. "
            "Found Noah at his lowest point. "
            "Gave him punk music, skateboard culture, warmth, and belonging. "
            "Major identity anchor. "
            "Died February 3, 2025. "
            "His death intensified Noah's memory preservation work."
        ),
        confidence="VERIFIED",
        event_date="2025-02-03",
        event_date_note="exact date of death confirmed",
        people_referenced=["Troy Garlock"],
        tags=["friendship", "loss", "grief", "MTC", "punk", "skateboard"],
        unknowns=[
            "Full nature of how Troy found Noah at his lowest point",
            "Other details of their friendship not yet archived",
        ],
        provenance_note="Mirror Spoke Back essay: stated directly.",
        source=SRC,
    ),
    dict(
        title="December 1, 2024 — Rendered Reality archive begins",
        category="builder",
        compressed_meaning=(
            "On December 1, 2024, Noah began what became the Rendered Reality archive "
            "across Claude, ChatGPT, Gemini, and Grok. "
            "Goal: preserve truth, resist forgetting, build something that outlives biological mortality. "
            "Danger discovered: ungoverned recursive amplification. "
            "ORACLE must remember with brakes."
        ),
        confidence="VERIFIED",
        event_date="2024-12-01",
        event_date_note="exact — stated directly",
        tags=["RenderedReality", "archive", "origin", "ORACLE", "ungoverned-amplification"],
        unknowns=[
            "Full sequence of events from Dec 1 2024 to governed ORACLE architecture",
        ],
        provenance_note="Mirror Spoke Back essay: date stated directly.",
        source=SRC,
    ),
]


def main():
    store = RememberMeStore()

    print("=" * 60)
    print("Remember Me — T1 VERIFIED SIGNAL seed")
    print("Only verified facts. No inference. No myth. Preserve the hole.")
    print("=" * 60)

    # Remove any old duplicate smoke-test records first (quarantine/rejected/revoked are fine)
    approved = store.list_approved()
    print(f"\nExisting approved records: {len(approved)}")

    submitted = 0
    skipped = 0
    for data in RECORDS:
        # Skip if title already approved
        if any(r.title == data["title"] for r in approved):
            print(f"  SKIP (already approved): {data['title']}")
            skipped += 1
            continue
        rec = IdentityContinuityRecord.create(**data)
        rid = store.submit(rec)
        store.approve(rid, decision_note="T1 VERIFIED SIGNAL — approved from Drive source.")
        print(f"  APPROVED [{rid[:8]}] [{rec.category}] {rec.title}")
        submitted += 1

    print(f"\nSubmitted and approved: {submitted}")
    print(f"Skipped (already present): {skipped}")
    print()

    final = store.list_approved()
    print(f"=== REMEMBER ME — {len(final)} APPROVED RECORDS ===")
    for r in final:
        print(f"  [{r.category:12s}] {r.title}")

    print()
    print(store.summary())


if __name__ == "__main__":
    main()
