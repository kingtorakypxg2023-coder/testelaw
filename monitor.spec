# -*- mode: python ; coding: utf-8 -*-
"""Spec do PyInstaller — gera um executável único (onefile) do Monitor.

Build:  pyinstaller --noconfirm --clean monitor.spec
Saída:  dist/monitor-diarios  (ou dist/monitor-diarios.exe no Windows)
"""
from PyInstaller.utils.hooks import collect_all

datas, binaries, hiddenimports = [], [], []

# SDK de IA padrão (Anthropic) — inclui metadados para funcionar empacotado.
for _pkg in ("anthropic",):
    _d, _b, _h = collect_all(_pkg)
    datas += _d
    binaries += _b
    hiddenimports += _h

# Provedores carregados de forma preguiçosa pelas factories.
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
    ["run.py"],
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
    name="monitor-diarios",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
