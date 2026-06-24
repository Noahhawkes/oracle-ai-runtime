import pytest

from rendered_reality import (
    Witness, Receipt, ReceiptError, assert_machine_observed,
    OBS_RETURN_FROM_DARK,
)


def test_return_from_dark_is_not_machine_observed():
    w = Witness()
    r = w.create_return_from_dark_record(
        event_label="1.4 mile no-phone walk with Ashley",
        reporter="Noah.Physical",
        testimony="Walked 1.4 miles with Ashley, no phone.",
    )
    assert r.machine_observed is False
    assert r.observation_status == OBS_RETURN_FROM_DARK
    assert r.testimony_source == "Noah.Physical"
    assert any("machine observation" in h.lower() for h in r.holes)


def test_assert_machine_observed_fails_for_return_from_dark():
    w = Witness()
    r = w.create_return_from_dark_record(
        event_label="walk", reporter="Noah.Physical", testimony="...")
    with pytest.raises(ReceiptError):
        assert_machine_observed(r)


def test_return_from_dark_cannot_be_forced_machine_observed():
    with pytest.raises(ReceiptError):
        Receipt(source="s", submitting_system="x", submitted_by="Noah.Physical",
                testimony_source="Noah.Physical",
                observation_status=OBS_RETURN_FROM_DARK, machine_observed=True)
