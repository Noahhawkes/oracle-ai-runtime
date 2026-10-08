"""Local memory layer — recall, state, provenance from local records only."""
from rendered_reality import (
    LocalMemory, ContextState, ProvenanceQuery, Authorship, ApprovalStatus,
)
from rendered_reality.samples import all_samples


def _mem():
    return LocalMemory(all_samples())


def test_project_summary_from_local_records():
    m = _mem()
    s = m.project_summary()
    assert "holding" in s
    assert "4 record" in s  # 4 sample records


def test_remember_about_finds_topic():
    m = _mem()
    hits = m.remember_about("stories vessel cargo")
    assert hits, "should recall the Noah note about stories"
    assert any("stories" in (h.record.content or "").lower() for h in hits)


def test_holes_include_return_from_dark():
    m = _mem()
    holes = m.holes()
    assert any("machine observation" in h.lower() for _, h in holes)


def test_cite_returns_receipt_reference():
    m = _mem()
    r = m.all()[0]
    c = m.cite(r)
    assert r.receipt_id in c and "author=" in c


def test_context_state_counts_match():
    m = _mem()
    cs = ContextState.from_memory(m)
    assert cs.total == 4
    assert cs.canon == 0  # nothing approved to canon yet


def test_provenance_separates_authors():
    m = _mem()
    pq = ProvenanceQuery(m.all())
    assert len(pq.by_author(Authorship.AI_AUTHORED)) >= 1  # the pasted Claude thread
    assert Authorship.NOAH_AUTHORED.value in pq.authorship_breakdown()
