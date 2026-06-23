# -*- mode: python ; coding: utf-8 -*-
"""Spec do PyInstaller — executável de JANELA (GUI, sem console).

Build:  pyinstaller --noconfirm --clean monitor-gui.spec
Saída:  dist/monitor-diarios-gui  (ou dist/monitor-diarios-gui.exe no Windows)
"""
from PyInstaller.utils.hooks import collect_all

datas, binaries, hiddenimports = [], [], []

for _pkg in ("anthropic",):
    _d, _b, _h = collect_all(_pkg)
    datas += _d
    binaries += _b
    hiddenimports += _h

hiddenimports += [
    "src.services.capture.comunica",
    "src.services.capture.jusbrasil",
    "src.services.capture.mock",
    "src.services.intelligence.claude",
    "src.services.intelligence.gemini",
    "src.services.intelligence.openai",
    "src.services.intelligence.mock",
    "src.services.agenda.google_calendar",
    "src.services.agenda.mock",
    "src.services.notifications.webhook",
    "src.services.notifications.telegram",
    "src.services.notifications.email",
    "src.services.notifications.mock",
    "src.services.persistence.sqlite_store",
    "src.services.persistence.memory",
    "src.services.manual.repository",
]

a = Analysis(
    ["gui_run.py"],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["tests", "pytest"],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="monitor-diarios-gui",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
