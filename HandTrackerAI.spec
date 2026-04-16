# -*- mode: python ; coding: utf-8 -*-
from pathlib import Path

from PyInstaller.utils.hooks import collect_data_files, collect_dynamic_libs


project_root = Path(SPECPATH)

datas = [
    (
        str(project_root / "src" / "handtracker_ai" / "pngfortutor"),
        "handtracker_ai/pngfortutor",
    ),
]
datas += collect_data_files("mediapipe")
datas += collect_data_files("customtkinter")

binaries = []
binaries += collect_dynamic_libs("cv2")

hiddenimports = [
    "cv2",
    "PIL._tkinter_finder",
    "pyautogui._pyautogui_osx",
]

analysis = Analysis(
    ["run_handtracker_ai.py"],
    pathex=[str(project_root / "src")],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(analysis.pure)

exe = EXE(
    pyz,
    analysis.scripts,
    [],
    name="HandTrackerAI-bin",
    exclude_binaries=True,
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    analysis.binaries,
    analysis.zipfiles,
    analysis.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="HandTrackerAI",
)

app = BUNDLE(
    coll,
    name="HandTrackerAI.app",
    icon=str(project_root / "assets" / "HandTrackerAI.icns"),
    bundle_identifier="com.handtracker.ai",
    info_plist={
        "CFBundleName": "HandTrackerAI",
        "CFBundleDisplayName": "HandTrackerAI",
        "CFBundleShortVersionString": "1.0.0",
        "CFBundleVersion": "1.0.0",
        "NSCameraUsageDescription": "HandTrackerAI uses the camera to detect hand gestures.",
        "NSAppleEventsUsageDescription": "HandTrackerAI uses system automation to control macOS actions.",
    },
)
