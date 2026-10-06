"""Package the game as a stand-alone program with PyInstaller (no Python needed to play it).

    pip install pyinstaller
    python tools/build_exe.py

On Windows this makes dist/LegendsOfTheCarpathians/LegendsOfTheCarpathians.exe (and a .zip of the folder
to hand out); on Linux or macOS the same folder with a native program. The GitHub workflow
.github/workflows/build-windows.yml runs it on Windows for every version tag.
"""

import os
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
NAME = "LegendsOfTheCarpathians"
BUILD = ROOT / "build"
DIST = ROOT / "dist"


def write_icon():
    os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
    import pygame
    from legendele.ui import icon
    pygame.display.init()
    pygame.display.set_mode((1, 1))
    BUILD.mkdir(exist_ok=True)
    path = BUILD / "icon.ico"
    path.write_bytes(icon.ico_bytes())
    return path


def main():
    import PyInstaller.__main__
    sep = os.pathsep  # PyInstaller's "source<sep>destination" for --add-data
    args = [
        str(ROOT / "tools" / "launcher.py"),
        "--name", NAME,
        "--noconfirm",
        "--clean",
        "--windowed",  # no console window behind the game
        "--icon", str(write_icon()),
        "--distpath", str(DIST),
        "--workpath", str(BUILD / "work"),
        "--specpath", str(BUILD),
        "--add-data", f"{ROOT / 'legendele' / 'data'}{sep}legendele/data",
        "--add-data", f"{ROOT / 'legendele' / 'assets'}{sep}legendele/assets",
        "--collect-submodules", "legendele",
    ]
    PyInstaller.__main__.run(args)
    archive = shutil.make_archive(str(DIST / NAME), "zip", DIST, NAME)
    print(f"Done: {DIST / NAME} and {archive}")


if __name__ == "__main__":
    main()
