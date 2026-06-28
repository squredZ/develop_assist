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
    ("agent.yaml", "."),
    ("prompts/module_generation.md", "prompts"),
    ("prompts/feature_update.md", "prompts"),
]

# Collect entire features directory
features_datas = []
features_root = Path("fixtures/features")
if features_root.is_dir():
    for f in features_root.rglob("*"):
        if f.is_file():
            rel_parent = f.parent.relative_to("fixtures")
            features_datas.append((str(f), str(Path("fixtures") / rel_parent)))
datas.extend(features_datas)

# Hidden imports
hiddenimports = [
    "hilog_agent.server",
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
    pathex=[".", "src"],
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
    console=True,       # Show console window for debugging
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,           # Add icon path here for a custom icon
)
