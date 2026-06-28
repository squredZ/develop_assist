# PyInstaller spec — single .exe for Windows
# Build: pyinstaller build.spec
# Output: dist/HilogAgent.exe

# -*- mode: python ; coding: utf-8 -*-

import sys
from pathlib import Path

block_cipher = None

# Collect data files
datas = [
    ("frontend/chat.html", "frontend"),
    ("prompts/module_generation.md", "prompts"),
    ("prompts/feature_update.md", "prompts"),
]

# Hidden imports
hiddenimports = [
    "uvicorn.logging",
    "uvicorn.loops",
    "uvicorn.loops.auto",
    "uvicorn.protocols",
    "uvicorn.protocols.http",
    "uvicorn.protocols.http.auto",
    "uvicorn.protocols.websockets",
    "uvicorn.protocols.websockets.auto",
    "uvicorn.lifespan",
    "uvicorn.lifespan.on",
    "fastapi",
    "starlette",
    "sse_starlette",
    "pydantic",
    "yaml",
    "openai",
    "click",
    "PyQt6",
    "PyQt6.QtWebEngineWidgets",
    "PyQt6.QtWebEngineCore",
]

a = Analysis(
    ["frontend/main.py"],
    pathex=[],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name="HilogAgent",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,       # No console window
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,           # Add icon path here for a custom icon
)
