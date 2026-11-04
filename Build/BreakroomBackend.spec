from pathlib import Path

from PyInstaller.utils.hooks import collect_submodules

project_root = Path(SPECPATH).parent
backend_root = project_root / "Backend"

a = Analysis(
    [str(backend_root / "RunBackend.py")],
    pathex=[str(backend_root)],
    binaries=[],
    datas=[],
    hiddenimports=collect_submodules("uvicorn") + collect_submodules("pydantic_settings"),
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["pytest", "ruff", "PyInstaller"],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="BreakroomBackend",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name="BreakroomBackend",
)
