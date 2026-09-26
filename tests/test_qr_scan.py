import sys
from pathlib import Path

import cv2

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "core"))

import qr_scan  # noqa: E402


def _write_test_qr(path: Path, payload: str) -> None:
    encoder = cv2.QRCodeEncoder_create(cv2.QRCodeEncoder_Params())
    image = encoder.encode(payload)
    image = cv2.resize(image, None, fx=20, fy=20, interpolation=cv2.INTER_NEAREST)
    image = cv2.copyMakeBorder(image, 80, 80, 80, 80, cv2.BORDER_CONSTANT, value=255)
    assert cv2.imwrite(str(path), image)


def test_qr_scan_decodes_local_image_and_writes_receipt(tmp_path, monkeypatch):
    monkeypatch.setattr(qr_scan, "RECEIPTS_DIR", tmp_path / "receipts")
    monkeypatch.setattr(qr_scan, "LATEST_RECEIPT", tmp_path / "qr_scan_receipt_latest.json")
    image_path = tmp_path / "sov1_qr.png"
    _write_test_qr(image_path, "https://sov1.ai/")

    result = qr_scan.scan_image_file(image_path, write_receipt=True)

    assert result["ok"] is True
    assert result["decoded"] is True
    assert result["decoded_text"] == "https://sov1.ai/"
    assert result["capability"] == "qr_scan"
    assert result["approval_required"] is False
    assert result["camera_used"] is False
    assert result["raw_image_stored"] is False
    assert Path(result["receipt_path"]).exists()
    assert (tmp_path / "qr_scan_receipt_latest.json").exists()


def test_extract_image_path_from_chat_text():
    path = r"C:\Users\noahh\OneDrive\Pictures\Camera Roll\2026\06\20260627_035946049_iOS.jpg"
    text = f"please scan this QR tattoo image {path}"

    assert qr_scan.extract_image_path(text) == path


def test_qr_scan_missing_file_is_available_but_not_decoded(tmp_path, monkeypatch):
    monkeypatch.setattr(qr_scan, "RECEIPTS_DIR", tmp_path / "receipts")
    monkeypatch.setattr(qr_scan, "LATEST_RECEIPT", tmp_path / "qr_scan_receipt_latest.json")

    result = qr_scan.scan_image_file(tmp_path / "missing.jpg", write_receipt=True)

    assert result["ok"] is False
    assert result["capability_status"] == "available"
    assert result["decoded"] is False
    assert "not found" in result["error"]
    assert Path(result["receipt_path"]).exists()
