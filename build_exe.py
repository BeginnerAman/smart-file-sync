"""
build_exe.py — High-Performance One-Click EXE Builder for Smart File Sync v3.0
=============================================================================
Run: python build_exe.py
Supports high-speed UV package resolver & PyInstaller builder.
"""
import os, sys, shutil, subprocess
from pathlib import Path

# Ensure UTF-8 output encoding on Windows consoles
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

def run(cmd, **kw):
    print(f"  $ {' '.join(cmd)}")
    return subprocess.run(cmd, **kw)

def main():
    print("=" * 60)
    print("  Smart File Sync v3.0 -- High-Speed EXE Builder")
    print("=" * 60)

    has_uv = shutil.which("uv") is not None
    if has_uv:
        print("\n[*] [UV Detected] Using ultra-fast UV package manager!")
    else:
        print("\n[*] UV not found in PATH, falling back to standard pip/python.")

    packages = ["PySide6", "psutil", "pyinstaller"]
    for pkg in packages:
        print(f"\n[*] Checking {pkg}...")
        r = run([sys.executable, "-c", f"import {pkg.lower().replace('-','')}"],
                capture_output=True)
        if r.returncode != 0:
            print(f"    Installing {pkg}...")
            if has_uv:
                run(["uv", "pip", "install", "--python", sys.executable, pkg])
            else:
                run([sys.executable, "-m", "pip", "install", pkg])
        else:
            print(f"    [OK] Already installed")

    script_dir = Path(__file__).parent
    app_script = script_dir / "app.py"
    if not app_script.exists():
        print(f"\n[ERROR] app.py not found at {app_script}")
        if sys.stdin.isatty(): input("Press Enter..."); 
        return

    print("\n[*] Building Optimized EXE...")
    pyinstaller_bin = [sys.executable, "-m", "PyInstaller"]

    ico_file = script_dir / "app_icon.ico"
    assets_src = script_dir / "smart_sync" / "assets"
    
    cmd = pyinstaller_bin + [
        "--onefile", "--windowed",
        "--name", "SmartFileSync",
        "--clean", "--noconfirm",
        "--icon", str(ico_file),
        "--add-data", f"{assets_src};smart_sync/assets",
        "--exclude-module", "PySide6.QtNetwork",
        "--exclude-module", "PySide6.QtQml",
        "--exclude-module", "PySide6.QtQuick",
        "--exclude-module", "PySide6.QtWebEngineCore",
        "--exclude-module", "PySide6.QtWebEngineWidgets",
        "--exclude-module", "PySide6.QtMultimedia",
        "--exclude-module", "PySide6.QtMultimediaWidgets",
        "--exclude-module", "PySide6.QtPdf",
        "--exclude-module", "PySide6.QtPdfWidgets",
        "--exclude-module", "PySide6.Qt3DCore",
        "--exclude-module", "PySide6.QtCharts",
        "--exclude-module", "PySide6.QtPositioning",
        "--exclude-module", "PySide6.QtSensors",
        "--exclude-module", "PySide6.QtSerialPort",
        "--exclude-module", "PySide6.QtSpatialAudio",
        "--exclude-module", "PySide6.QtSql",
        "--exclude-module", "PySide6.QtTest",
        "--exclude-module", "PySide6.QtXml",
        str(app_script)
    ]
    r = run(cmd, cwd=str(script_dir))
    if r.returncode != 0:
        print("\n[ERROR] Build failed!")
        if sys.stdin.isatty(): input("Press Enter..."); 
        return

    exe_src = script_dir / "dist" / "SmartFileSync.exe"
    if exe_src.exists():
        print(f"\n[SUCCESS] EXE created at:\n   {exe_src}")
    else:
        print(f"\n[WARNING] EXE not found at {exe_src}")

    print("\n" + "=" * 60)
    print("  Done! SmartFileSync.exe is ready in dist/ folder.")
    print("=" * 60)
    if sys.stdin.isatty(): input("\nPress Enter to exit...")

if __name__ == "__main__":
    main()
