# -*- mode: python ; coding: utf-8 -*-
# Experimental frozen build; source/wheel verification does not approve this EXE.


a = Analysis(
    ['kojakstreet_qt_launcher.py'],
    pathex=['src'],
    binaries=[],
    datas=[('aktien.txt', '.')],
    hiddenimports=['daten', 'speicher'],
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
    name='Kojak Street Pro',
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
    icon=['assets\\kojak_street.ico'],
)
