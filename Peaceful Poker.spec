"""PyInstaller one-folder build for Peaceful Poker."""

from pathlib import Path

ROOT = Path(SPEC).resolve().parent
RESOURCE_DIR = ROOT / "src" / "poker_trainer" / "resources"
RESOURCE_FILES = [
    RESOURCE_DIR / "dark.qss",
    RESOURCE_DIR / "default_settings.json",
    RESOURCE_DIR / "light.qss",
    RESOURCE_DIR / "peaceful_poker.ico",
    RESOURCE_DIR / "peaceful_poker.png",
    RESOURCE_DIR / "peaceful_poker.svg",
    RESOURCE_DIR / "recommendation_thresholds.json",
]

a = Analysis(
    [str(ROOT / "src" / "poker_trainer" / "__main__.py")],
    pathex=[str(ROOT / "src")],
    binaries=[],
    datas=[(str(path), "poker_trainer/resources") for path in RESOURCE_FILES],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["pytest", "mypy", "ruff", "tests"],
    noarchive=False,
    optimize=1,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="Peaceful Poker",
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
    icon=str(RESOURCE_DIR / "peaceful_poker.ico"),
    version=str(ROOT / "packaging" / "windows_version_info.txt"),
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="Peaceful Poker",
)
