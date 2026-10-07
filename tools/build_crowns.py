"""Package Crowns of the Balkans as a stand-alone program with PyInstaller (no Python needed to play).

    pip install pyinstaller
    python tools/build_crowns.py

On Windows this makes dist/CrownsOfTheBalkans/CrownsOfTheBalkans.exe and a .zip of the folder to hand
out; on Linux the same folder with a native program. The GitHub workflow
.github/workflows/build-crowns.yml runs it on Windows.
"""

import os
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
NAME = "CrownsOfTheBalkans"
BUILD = ROOT / "build" / "crowns"
DIST = ROOT / "dist"


def write_icon():
    """A gold crown on a red shield, in the colours of the map's realms."""
    from PIL import Image, ImageDraw
    size = 256
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle((16, 16, 240, 240), radius=40, fill=(240, 228, 196, 255), outline=(60, 38, 20, 255),
                        width=10)
    d.polygon([(48, 196), (40, 84), (88, 136), (128, 60), (168, 136), (216, 84), (208, 196)],
              fill=(196, 150, 40, 255), outline=(60, 38, 20, 255))
    d.rectangle((48, 196, 208, 214), fill=(170, 36, 26, 255), outline=(60, 38, 20, 255), width=4)
    for x in (40, 128, 216):
        d.ellipse((x - 12, (60 if x == 128 else 84) - 12, x + 12, (60 if x == 128 else 84) + 12),
                  fill=(170, 36, 26, 255), outline=(60, 38, 20, 255), width=3)
    BUILD.mkdir(parents=True, exist_ok=True)
    path = BUILD / "crowns.ico"
    img.save(path, sizes=[(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
    return path


def seed_cache():
    """Make the maps that take a minute at the first start, to ship them inside the game."""
    sys.path.insert(0, str(ROOT))
    import numpy as np
    from crowns.mapdata import Ground
    from crowns.provinces import ProvinceMap
    from crowns.render.political import _border_distance, _rounded, _spread, _upscale
    from crowns.render.world import EXAGGERATION
    folder = BUILD / "cache_seed"
    folder.mkdir(parents=True, exist_ok=True)
    g = Ground()
    fine = _spread(_rounded(_upscale(ProvinceMap().labels, 2))).astype(np.uint16)
    for name, make in (("colors", g.color_map), (f"normals-{EXAGGERATION}", lambda: g.normal_map(EXAGGERATION)),
                       ("coast", g.coast_distance), ("province-index", lambda: fine),
                       ("province-border-distance", lambda: _border_distance(fine))):
        np.save(folder / f"{name}.npy", make())
        print("seeded", name)
    return folder


def main():
    import PyInstaller.__main__
    sep = os.pathsep  # PyInstaller's "source<sep>destination" for --add-data
    seed = seed_cache()
    args = [
        str(ROOT / "tools" / "crowns_launcher.py"),
        "--name", NAME,
        "--noconfirm",
        "--clean",
        "--windowed",  # no console window behind the game
        "--icon", str(write_icon()),
        "--distpath", str(DIST),
        "--workpath", str(BUILD / "work"),
        "--specpath", str(BUILD),
        "--paths", str(ROOT),
        "--add-data", f"{ROOT / 'crowns' / 'data'}{sep}crowns/data",
        "--add-data", f"{ROOT / 'crowns' / 'assets'}{sep}crowns/assets",
        "--add-data", f"{ROOT / 'crowns' / 'render' / 'shaders'}{sep}crowns/render/shaders",
        "--add-data", f"{seed}{sep}crowns/cache_seed",
        "--collect-submodules", "crowns",
        # Panda3D's display, sound and video plugins are loaded by name at run time
        "--collect-binaries", "panda3d",
        "--collect-data", "panda3d",
        "--hidden-import", "direct.showbase.ShowBase",
        "--hidden-import", "direct.gui.DirectGui",
        "--hidden-import", "direct.gui.OnscreenText",
        "--exclude-module", "pygame",
        "--exclude-module", "legendele",
        "--exclude-module", "tkinter",
        "--exclude-module", "pytest",
    ]
    PyInstaller.__main__.run(args)
    archive = shutil.make_archive(str(DIST / NAME), "zip", DIST, NAME)
    print(f"Done: {DIST / NAME} and {archive}")


if __name__ == "__main__":
    sys.exit(main())
