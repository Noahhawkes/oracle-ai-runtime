"""OracleMind — memory first, tools when needed, no permission theater."""
from rendered_reality import LocalMemory, OracleMind
from rendered_reality.samples import all_samples


def _mind(caps=None):
    return OracleMind(LocalMemory(all_samples()), capabilities=caps)


def test_remembers_project_from_memory():
    r = _mind().respond("what do you remember about this project?")
    assert r.kind == "memory"
    assert r.from_memory is True
    assert "holding" in r.text


def test_reports_holes_from_local_state():
    r = _mind().respond("what are the current holes?")
    assert r.kind == "memory"
    assert "machine observation" in r.text.lower()


def test_reports_state_and_approvals():
    r = _mind().respond("what is approved and pending right now?")
    assert r.kind == "memory"
    assert "pending approval" in r.text.lower()


def test_distinguishes_memory_from_action():
    m = _mind()
    assert m.classify("how does this project feel to you") == "memory"
    assert m.classify("commit this to github") == "action"


def test_unsupported_action_says_missing_capability_not_fake_permission():
    r = _mind().respond("delete the manuscript file")
    assert r.kind == "unsupported_action"
    assert r.needs_capability == "local_file_write"
    assert "cannot do that from this runtime yet" in r.text.lower()
    # no permission theater
    assert "would you like me to proceed" not in r.text.lower()
    assert r.requires_approval is False


def test_supported_readonly_action_no_approval():
    r = _mind(caps={"local_file_read"}).respond("read file notes.md")
    assert r.kind == "action"
    assert r.requires_approval is False


def test_supported_mutating_action_requests_approval():
    r = _mind(caps={"local_file_write"}).respond("delete notes.md")
    assert r.kind == "action"
    assert r.requires_approval is True
