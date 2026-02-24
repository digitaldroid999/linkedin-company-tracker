"""Build script: converts app_icon.svg to .ico and creates a standalone .exe with PyInstaller."""

import os
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
ASSETS = PROJECT_ROOT / "assets"
APP_ICON_SVG = ASSETS / "app_icon.svg"
APP_ICON_ICO = ASSETS / "app_icon.ico"


def svg_to_ico() -> bool:
    """Convert app_icon.svg to app_icon.ico using PyQt6 + Pillow."""
    try:
        from PIL import Image
        import io
    except ImportError:
        print("Error: Pillow is required for icon conversion. Run: pip install pillow")
        return False

    # PyQt6 needed for SVG rendering; create minimal app for plugin loading
    from PyQt6.QtWidgets import QApplication
    from PyQt6.QtGui import QIcon
    from PyQt6.QtCore import QBuffer, QIODevice

    if not APP_ICON_SVG.exists():
        print(f"Error: {APP_ICON_SVG} not found")
        return False

    app = QApplication(sys.argv[:1] if sys.argv else [])
    icon = QIcon(str(APP_ICON_SVG))
    sizes = [(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]
    images = []

    for w, h in sizes:
        pix = icon.pixmap(w, h)
        if pix.isNull():
            continue
        buf = QBuffer()
        buf.open(QIODevice.OpenModeFlag.WriteOnly)
        pix.save(buf, b"PNG")
        png_bytes = bytes(buf.data().data())
        img = Image.open(io.BytesIO(png_bytes)).convert("RGBA")
        images.append((img, (w, h)))

    if not images:
        print("Error: Could not render SVG to pixmap")
        return False

    # Save as ICO (Pillow expects list of (img, (w,h)) for multi-size)
    img = images[-1][0]  # Largest for base
    img.save(str(APP_ICON_ICO), format="ICO", sizes=[s for _, s in images])
    print(f"Created {APP_ICON_ICO}")
    return True


def build_exe() -> bool:
    """Run PyInstaller to create the executable."""
    icon_arg = f"--icon={APP_ICON_ICO}" if APP_ICON_ICO.exists() else ""

    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--onefile",           # Single exe
        "--windowed",          # No console window (GUI app)
        "--name=LinkedIn Company Tracker",
        "--hidden-import=PyQt6.QtSvg",  # For SVG icon loading
        f"--add-data={ASSETS}{os.pathsep}assets",
    ]
    if icon_arg:
        cmd.append(icon_arg)
    cmd.append(str(PROJECT_ROOT / "main.py"))

    print("Running:", " ".join(cmd))
    result = subprocess.run(cmd, cwd=PROJECT_ROOT)
    return result.returncode == 0


if __name__ == "__main__":
    if not svg_to_ico():
        sys.exit(1)
    if not build_exe():
        sys.exit(1)
    print("Build complete. Output: dist/LinkedIn Company Tracker.exe")
