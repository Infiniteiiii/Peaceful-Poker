"""PyInstaller one-folder build for Peaceful Poker."""

from pathlib import Path

from PyInstaller.utils.hooks import collect_data_files

ROOT = Path(SPEC).resolve().parent
RESOURCE_DIR = ROOT / "src" / "poker_trainer" / "resources"
RESOURCE_FILES = collect_data_files("poker_trainer", includes=["resources/*"])
if not RESOURCE_FILES:
    raise RuntimeError(f"No application resources were collected from {RESOURCE_DIR}.")

a = Analysis(
    [str(ROOT / "src" / "poker_trainer" / "__main__.py")],
    pathex=[str(ROOT / "src")],
    binaries=[],
    datas=RESOURCE_FILES,
    hiddenimports=["PySide6.QtCore", "PySide6.QtGui", "PySide6.QtWidgets"],
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
