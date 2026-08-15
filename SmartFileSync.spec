# -*- mode: python ; coding: utf-8 -*-
import os

a = Analysis(
    ['C:\\Users\\Aman\\Downloads\\adv_file_sync - Copy\\app.py'],
    pathex=[],
    binaries=[],
    datas=[('C:\\Users\\Aman\\Downloads\\adv_file_sync - Copy\\smart_sync\\assets', 'smart_sync/assets')],
    hiddenimports=['watchdog', 'watchdog.observers', 'watchdog.events'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'PySide6.QtNetwork', 'PySide6.QtQml', 'PySide6.QtQuick', 'PySide6.QtWebEngineCore',
        'PySide6.QtWebEngineWidgets', 'PySide6.QtMultimedia', 'PySide6.QtMultimediaWidgets',
        'PySide6.QtPdf', 'PySide6.QtPdfWidgets', 'PySide6.Qt3DCore', 'PySide6.QtCharts',
        'PySide6.QtPositioning', 'PySide6.QtSensors', 'PySide6.QtSerialPort',
        'PySide6.QtSpatialAudio', 'PySide6.QtSql', 'PySide6.QtTest', 'PySide6.QtXml',
        'tkinter', 'unittest', 'pydoc'
    ],
    noarchive=False,
    optimize=1,
)

# ── STRIP UNUSED HEAVY DLLs (Bloat Removal) ──
excluded_binary_patterns = [
    'opengl32sw',
    'Qt6Qml',
    'Qt6Quick',
    'Qt6Pdf',
    'Qt6Network',
    'Qt6QmlModels',
    'Qt6OpenGL',
    'd3dcompiler',
    'libcrypto-3',
    'libssl-3',
]

a.binaries = [
    b for b in a.binaries
    if not any(pat.lower() in b[0].lower() for pat in excluded_binary_patterns)
]

pyz = PYZ(a.pure)

# ── 1. SINGLE-FILE STANDALONE EXE (Clean & Slim) ──
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='SmartFileSync',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=['C:\\Users\\Aman\\Downloads\\adv_file_sync - Copy\\app_icon.ico'],
)

# ── 2. PORTABLE INSTANT-LAUNCH FOLDER (Zero Extraction Delay) ──
exe_portable = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='SmartFileSync',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    icon=['C:\\Users\\Aman\\Downloads\\adv_file_sync - Copy\\app_icon.ico'],
)

coll = COLLECT(
    exe_portable,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name='SmartFileSync-Portable',
)
