# -*- mode: python ; coding: utf-8 -*-
#
# PyInstaller spec for Schemedit.
# Build:  pyinstaller schemedit.spec
#
import sys

block_cipher = None

a = Analysis(
    ['main.py'],
    pathex=['.'],
    binaries=[],
    datas=[],
    hiddenimports=[
        # PyQt6 OpenGL support — not always auto-detected
        'PyQt6.QtOpenGLWidgets',
        'PyQt6.QtOpenGL',
        'PyQt6.sip',
        # moderngl / glm are C extensions; list explicitly so PyInstaller
        # includes them even if the import graph doesn't reach them statically
        'moderngl',
        'moderngl.mgl',
        'glm',
        # numpy (transitive via litemapy → nbtlib, and our own mesh_builder)
        'numpy',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    # Cut down size by skipping large unused Qt modules
    excludes=[
        'PyQt6.QtWebEngineWidgets',
        'PyQt6.QtWebEngine',
        'PyQt6.QtBluetooth',
        'PyQt6.QtNfc',
        'PyQt6.QtSql',
        'PyQt6.QtTest',
        'PyQt6.QtXml',
        'tkinter',
        'matplotlib',
        'scipy',
    ],
    noarchive=False,
    cipher=block_cipher,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='Schemedit',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    # Hide the console window on Windows / macOS
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

# macOS: also produce a proper .app bundle
if sys.platform == 'darwin':
    app = BUNDLE(
        exe,
        name='Schemedit.app',
        bundle_identifier='io.github.bigocb.schemedit',
        info_plist={
            'NSHighResolutionCapable': True,
            'LSMinimumSystemVersion': '11.0',
        },
    )
