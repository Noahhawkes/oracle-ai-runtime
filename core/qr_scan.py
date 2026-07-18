"""Local QR image decode capability for ORACLE.

This is a read-only file capability. It does not open the camera, upload the
image, store image bytes, promote canon, or claim physical verification.
"""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import hashlib
import json
import re
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
RECEIPTS_DIR = ROOT / "Memory" / "qr_scan_receipts"
LATEST_RECEIPT = ROOT / "Memory" / "qr_scan_receipt_latest.json"

SUPPORTED_EXTENSIONS = {".png", ".jpg", ".jpeg", ".bmp", ".webp", ".tif", ".tiff"}
IMAGE_PATH_RE = re.compile(
    r"(?P<path>[A-Za-z]:\\[^\"'\r\n<>|]+\.(?:png|jpe?g|bmp|webp|tiff?))",
    re.IGNORECASE,
)


class QRScanError(ValueError):
    """Raised when a QR scan request is malformed or unsupported."""


def extract_image_path(text: str) -> str | None:
    """Return the first supported Windows image path in a user message."""
    match = IMAGE_PATH_RE.search(text or "")
    if not match:
        return None
    return match.group("path").strip().rstrip(".,;)")


def _normalize_path(path: str | Path) -> Path:
    if not path:
        raise QRScanError("image path is required")
    p = Path(str(path).strip().strip('"'))
    if not p.is_absolute():
        p = (ROOT / p).resolve()
    else:
        p = p.resolve()
    if p.suffix.lower() not in SUPPORTED_EXTENSIONS:
        raise QRScanError(
            f"unsupported image extension {p.suffix!r}; supported: "
            + ", ".join(sorted(SUPPORTED_EXTENSIONS))
        )
    if not p.exists():
        raise QRScanError(f"image file not found: {p}")
    if not p.is_file():
        raise QRScanError(f"path is not a file: {p}")
    return p


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _decode_with_opencv(path: Path) -> tuple[str, list[list[float]] | None, str | None]:
    try:
        import cv2
    except Exception as exc:  # pragma: no cover - environment dependent
        return "", None, f"OpenCV unavailable: {type(exc).__name__}: {exc}"

    img = cv2.imread(str(path))
    if img is None:
        return "", None, "OpenCV could not read the image"

    detector = cv2.QRCodeDetector()

    def attempt(name: str, arr: Any) -> tuple[str, list[list[float]] | None, str] | None:
        data, points, _straight = detector.detectAndDecode(arr)
        if data:
            pts = points.reshape(-1, 2).tolist() if points is not None else None
            return data, pts, name
        ok, infos, points_multi, _ = detector.detectAndDecodeMulti(arr)
        if ok:
            for info in infos:
                if info:
                    pts = points_multi.reshape(-1, 2).tolist() if points_multi is not None else None
                    return info, pts, f"{name}:multi"
        return None

    direct = attempt("original", img)
    if direct:
        data, pts, _name = direct
        return data, pts, None

    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    variants: list[tuple[str, Any]] = [("gray", gray)]
    variants.append(("gray_border", cv2.copyMakeBorder(gray, 80, 80, 80, 80, cv2.BORDER_CONSTANT, value=255)))
    for thresh in (100, 130, 160, 190):
        _, bw = cv2.threshold(gray, thresh, 255, cv2.THRESH_BINARY)
        variants.append((f"threshold_{thresh}", bw))

    for name, arr in variants:
        found = attempt(name, arr)
        if found:
            data, pts, _variant = found
            return data, pts, None

    return "", None, None


def scan_image_file(path: str | Path, *, write_receipt: bool = True) -> dict[str, Any]:
    """Decode a QR payload from a local image file and optionally write a receipt."""
    requested_path = str(path)
    scanned_at = datetime.now(timezone.utc).isoformat()
    try:
        final_path = _normalize_path(path)
        file_sha = _sha256(final_path)
        decoded_text, points, decode_error = _decode_with_opencv(final_path)
        decoded = bool(decoded_text)
        short = file_sha[:12]
        action_id = f"qr_scan_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')}_{short}"
        result: dict[str, Any] = {
            "ok": True,
            "operation_type": "qr_scan_image_file",
            "capability": "qr_scan",
            "capability_status": "available",
            "action_id": action_id,
            "requested_path": requested_path,
            "final_path": str(final_path),
            "sha256": file_sha,
            "scanned_at": scanned_at,
            "decoded": decoded,
            "decoded_text": decoded_text if decoded else None,
            "qr_points": points,
            "approval_required": False,
            "canon_status": "evidence_candidate",
            "promotion_status": "not_promoted",
            "external_write": False,
            "camera_used": False,
            "raw_image_stored": False,
            "holes": [],
            "boundaries": [
                "local image file read only",
                "no camera capture",
                "no external send",
                "no canon promotion",
                "no claim of physical identity/security verification",
            ],
        }
        if decode_error:
            result["holes"].append(decode_error)
        if not decoded:
            result["holes"].append(
                "QR payload not decoded from supplied image; visible QR-like pixels are not machine verification."
            )
    except QRScanError as exc:
        result = {
            "ok": False,
            "operation_type": "qr_scan_image_file",
            "capability": "qr_scan",
            "capability_status": "available",
            "requested_path": requested_path,
            "scanned_at": scanned_at,
            "decoded": False,
            "decoded_text": None,
            "approval_required": False,
            "error": str(exc),
            "holes": [str(exc)],
            "external_write": False,
            "camera_used": False,
            "raw_image_stored": False,
        }

    if write_receipt:
        RECEIPTS_DIR.mkdir(parents=True, exist_ok=True)
        action_id = result.get("action_id") or f"qr_scan_error_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')}"
        receipt_path = RECEIPTS_DIR / f"{action_id}_receipt.json"
        result["receipt_path"] = str(receipt_path)
        receipt_path.write_text(json.dumps(result, indent=2, sort_keys=True), encoding="utf-8")
        LATEST_RECEIPT.write_text(json.dumps(result, indent=2, sort_keys=True), encoding="utf-8")
    return result
