"""core/show_file.py — governed read-only file display for the ORACLE chat.

Lets Noah pull his own words (e.g. book/dad/manuscript.md) straight onto the
screen — deterministic, no model call, no narrative smoothing, exact bytes.

Governed:
  - Path is resolved and must sit INSIDE the runtime root (no traversal/escape).
  - Secret/credential paths are refused (never displayed).
  - Size-capped so a huge file can't be dumped into chat.
  - Read-only: never writes, moves, deletes, or modifies anything.
"""

from __future__ import annotations

from pathlib import Path

RUNTIME_ROOT = Path(__file__).resolve().parent.parent
MAX_BYTES = 200_000


def _contained(path: str) -> Path | None:
    try:
        p = Path(path)
        rp = (p if p.is_absolute() else (RUNTIME_ROOT / p)).resolve()
        rp.relative_to(RUNTIME_ROOT.resolve())
        return rp
    except Exception:
        return None


def _secret(path: str) -> str | None:
    try:
        from intake_pipeline import secret_risk_for
        return secret_risk_for(path)
    except Exception:
        name = path.lower().replace("/", "\\").rsplit("\\", 1)[-1]
        if name == ".env" or name.startswith(".env.") or name.endswith((".pem", ".key")):
            return "secret"
        return None


def read_repo_file(path: str, *, max_bytes: int = MAX_BYTES) -> dict:
    raw = (path or "").strip().strip('"').strip("'")
    if not raw:
        return {"ok": False, "reason": "usage: /show-file <path-inside-repo>"}
    rp = _contained(raw)
    if rp is None:
        return {"ok": False, "reason": f"refused: path is outside the runtime root or invalid: {raw}"}
    if _secret(str(rp)):
        return {"ok": False, "reason": "refused: target is a secret/credential path — never displayed"}
    if not rp.exists() or not rp.is_file():
        return {"ok": False, "reason": f"file not found: {raw}"}
    size = rp.stat().st_size
    if size > max_bytes:
        return {"ok": False, "reason": f"file too large to display in chat ({size} bytes > {max_bytes}); open it directly"}
    try:
        text = rp.read_text(encoding="utf-8", errors="replace")
    except Exception as exc:
        return {"ok": False, "reason": f"read failed: {type(exc).__name__}: {exc}"}
    return {"ok": True, "path": str(rp.relative_to(RUNTIME_ROOT.resolve())), "size": size, "text": text}


def format_show(path: str) -> str:
    r = read_repo_file(path)
    if not r["ok"]:
        return f"[show-file] {r['reason']}"
    return (
        f"FILE: {r['path']} ({r['size']} bytes) — exact contents, no model, no smoothing:\n\n"
        f"{r['text']}"
    )


def run_smoke_tests() -> int:
    import tempfile
    failures = 0

    def check(label, cond):
        nonlocal failures
        print(f"  [{'PASS' if cond else 'FAIL'}] {label}")
        if not cond:
            failures += 1

    # A real repo file (the manuscript) should display if present; else use this module.
    target = "book/dad/manuscript.md"
    if not (RUNTIME_ROOT / target).exists():
        target = "core/show_file.py"
    r = read_repo_file(target)
    check("repo file displays", r["ok"] and len(r["text"]) > 0)

    check(".env refused", read_repo_file(".env")["ok"] is False)
    check("outside-root refused", read_repo_file("C:\\Users\\noahh\\x.txt")["ok"] is False)
    check("traversal refused", read_repo_file("../escape.txt")["ok"] is False)
    check("missing file reported", read_repo_file("book/dad/does_not_exist.md")["ok"] is False)
    check("empty usage", read_repo_file("")["ok"] is False)

    big = read_repo_file(target, max_bytes=1)
    check("size cap enforced", big["ok"] is False and "too large" in big["reason"])

    print(f"\n{'ALL PASS' if failures == 0 else str(failures) + ' FAILURES'}")
    return 0 if failures == 0 else 1


if __name__ == "__main__":
    import sys
    if "--smoke-test" in sys.argv:
        raise SystemExit(run_smoke_tests())
    print(format_show("book/dad/manuscript.md"))
