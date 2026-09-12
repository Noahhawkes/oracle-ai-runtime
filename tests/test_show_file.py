"""Smoke tests for governed /show-file (core/show_file.py)."""
from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "core"))
os.environ.setdefault("ORACLE_SKIP_SERVER_BOOT", "1")

import show_file as sf  # noqa: E402


def test_module_smoke_runner_passes():
    assert sf.run_smoke_tests() == 0


def test_reads_repo_file():
    r = sf.read_repo_file("core/show_file.py")
    assert r["ok"] is True and "governed read-only file display" in r["text"]


def test_refuses_secret():
    assert sf.read_repo_file(".env")["ok"] is False


def test_refuses_outside_root_and_traversal():
    assert sf.read_repo_file("C:\\Users\\noahh\\x.txt")["ok"] is False
    assert sf.read_repo_file("../escape.txt")["ok"] is False


def test_missing_file_reported():
    assert sf.read_repo_file("book/dad/nope.md")["ok"] is False


def test_size_cap():
    big = sf.read_repo_file("core/show_file.py", max_bytes=1)
    assert big["ok"] is False and "too large" in big["reason"]


def test_format_show_ok_and_error():
    assert sf.format_show("core/show_file.py").startswith("FILE: ")
    assert sf.format_show(".env").startswith("[show-file] refused")
