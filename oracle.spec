# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec for ORACLE.AI
# Bundles config.yaml and the tools package into a single console EXE.
# Runtime data (Memory/, Logs/, Users/, .env) stays outside the EXE
# next to oracle.exe so it persists between runs.

from PyInstaller.utils.hooks import collect_data_files
import os

ROOT = os.path.abspath(".")

a = Analysis(
    [os.path.join(ROOT, "core", "oracle.py")],
    pathex=[
        os.path.join(ROOT, "core"),
        ROOT,
    ],
    binaries=[],
    datas=[
        # Bundle config so the exe can read it from inside
        (os.path.join(ROOT, "config.yaml"), "."),
    ],
    hiddenimports=[
        "tools.definitions",
        "tools.executor",
        "yaml",
        "anthropic",
        "dotenv",
        "docx",
        "pypdf",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="oracle",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,          # Keep console — Oracle is a terminal app
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
