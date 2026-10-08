import json
import shutil
from pathlib import Path

import pytest

from core import continuity_lock_profile as cl
from core import ingest_engine as ie


@pytest.fixture(autouse=True)
def clean_workspace():
    if ie.WORKSPACE_DIR.exists():
        shutil.rmtree(ie.WORKSPACE_DIR)
    yield
    if ie.WORKSPACE_DIR.exists():
        shutil.rmtree(ie.WORKSPACE_DIR)


# Seed: the Quantum Entanglement Authentication candidate (speculative, deferred).
QUANTUM_SEED = {
    "title": "Quantum Entanglement Authentication Candidate",
    "summary": "Speculative physical-security layer using entanglement / Bell-violation ideas.",
    "category": "speculative_physical_security_layer",
    "source_basis": "GENERATED_SYNTHESIS from ChatGPT thread, witnessed by Noah.Physical",
    "basis_label": "GENERATED_SYNTHESIS",
    "verification_status": "UNVERIFIED_PHYSICAL_LAYER",
    "implementation_status": "DEFERRED",
    "mindcoin_salience_score": 12000,
    "boundary_warnings": [
        "This is a speculative architecture candidate. It is not implemented, not "
        "physically verified, not canon, and not evidence of operational quantum authentication."
    ],
    "open_holes": ["No quantum hardware exists", "No physical entanglement channel"],
    "required_evidence_before_activation": [
        "Physical quantum hardware (entangled photon source + detectors)",
        "Reproducible CHSH/Bell-inequality violation measurement",
    ],
}


def _minimal():
    return cl.create_continuity_lock_profile({"title": "Minimal Candidate"})


def test_1_creates_profile_json():
    r = _minimal()
    assert Path(r["profile_path"]).exists()
    on_disk = json.loads(Path(r["profile_path"]).read_text(encoding="utf-8"))
    assert on_disk["lock_id"] == r["lock_id"]


def test_2_lock_id_is_unique():
    a = cl.create_continuity_lock_profile({"title": "A"})
    b = cl.create_continuity_lock_profile({"title": "B"})
    assert a["lock_id"] != b["lock_id"]


def test_3_canon_status_defaults_false():
    assert _minimal()["canon_status"] is False


def test_4_implementation_status_defaults_deferred():
    assert _minimal()["implementation_status"] == "DEFERRED"


def test_5_verification_status_defaults_unverified():
    assert _minimal()["verification_status"] == "UNVERIFIED"


def test_6_mindcoin_financial_value_always_zero():
    r = cl.create_continuity_lock_profile({"title": "X", "mindcoin_financial_value": 999999})
    assert r["mindcoin_financial_value"] == 0
    on_disk = json.loads(Path(r["profile_path"]).read_text(encoding="utf-8"))
    assert on_disk["mindcoin_financial_value"] == 0


def test_7_mindcoin_is_non_financial_salience_metric():
    d = _minimal()["mindcoin_unit_definition"].lower()
    assert "non-financial" in d and "not money" in d


def test_8_quantum_profile_is_speculative_not_operational():
    r = cl.create_continuity_lock_profile(QUANTUM_SEED)
    assert r["implementation_status"] == "DEFERRED"
    assert r["verification_status"] == "UNVERIFIED_PHYSICAL_LAYER"
    assert r["basis_label"] == "GENERATED_SYNTHESIS"
    assert r["canon_status"] is False
    assert any("not evidence of operational quantum" in w.lower() for w in r["boundary_warnings"])


def test_9_profile_includes_open_holes():
    r = cl.create_continuity_lock_profile(QUANTUM_SEED)
    assert "open_holes" in r and len(r["open_holes"]) >= 1


def test_10_profile_includes_required_evidence_before_activation():
    r = cl.create_continuity_lock_profile(QUANTUM_SEED)
    assert "required_evidence_before_activation" in r
    assert len(r["required_evidence_before_activation"]) >= 1


def _snapshot(d: Path):
    if not d.exists():
        return {}
    return {p.name: p.read_bytes() for p in sorted(d.glob("*.json"))}


def test_11_read_function_does_not_mutate_files():
    r = _minimal()
    locks = cl._locks_dir()
    before = _snapshot(locks)
    got = cl.get_continuity_lock_profile(r["lock_id"])
    assert got is not None and got["lock_id"] == r["lock_id"]
    assert _snapshot(locks) == before


def test_12_list_function_does_not_mutate_files():
    _minimal()
    locks = cl._locks_dir()
    before = _snapshot(locks)
    items = cl.list_continuity_lock_profiles()
    assert isinstance(items, list) and len(items) >= 1
    assert _snapshot(locks) == before


def test_13_sha256_exists_for_profile_record():
    r = _minimal()
    assert isinstance(r["record_sha256"], str)
    assert len(r["record_sha256"]) == 64
    int(r["record_sha256"], 16)  # valid hex


def test_14_no_network_or_cloud_calls_in_module():
    src = Path(cl.__file__).read_text(encoding="utf-8").lower()
    for forbidden in ("import requests", "import urllib", "import http",
                      "import socket", "import aiohttp", "openai", "boto3",
                      "http://", "https://"):
        assert forbidden not in src, f"forbidden network token present: {forbidden}"
