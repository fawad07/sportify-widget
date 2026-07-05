# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['run.py'],
    pathex=[],
    binaries=[],
    datas=[],
    hiddenimports=[],
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
    [],
    exclude_binaries=True,
    name='Sportify',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='assets/icon.icns',
)

# onedir keeps the Qt libraries as separate, replaceable shared
# libraries inside the bundle, as the LGPL expects
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='Sportify',
)

app = BUNDLE(
    coll,
    name='Sportify.app',
    icon='assets/icon.icns',
    bundle_identifier='com.fawad.sportify',
    info_plist={
        'LSUIElement': True,
        'CFBundleDisplayName': 'Sportify',
        'CFBundleShortVersionString': '1.0.2',
    },
)
