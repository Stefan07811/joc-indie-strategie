"""Bring the pictures made with Gemini (art/incoming/, see art/GEMINI.md) into the game:

- ground_*.png  -> crowns/assets/art/ground/*.jpg   made seamless, 1024 px
- tree_*, bush_*, grass_tuft, reeds -> crowns/assets/art/plants/*.png   magenta keyed out, cropped, 512 px tall
- arms_*.png    -> crowns/assets/art/arms/*.png      512 px

    python tools/import_art.py [INCOMING_DIR]

Pictures already imported are made again only when the incoming file is newer.
"""

import sys
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
INCOMING = ROOT / "art" / "incoming"
OUT = ROOT / "crowns" / "assets" / "art"
PLANTS = ("tree_", "bush_", "grass_tuft", "reeds")


def seamless(img, size=1024, band=0.18):
    """Make a texture tile: blend each edge into the opposite one over a band, so the seams vanish."""
    a = np.asarray(img.convert("RGB").resize((size, size), Image.LANCZOS)).astype(np.float32)
    n = size
    w = int(n * band)
    t = np.linspace(0, 1, w)[:, None]
    t = t * t * (3 - 2 * t)
    out = a.copy()
    # left/right: the first w columns become a blend of themselves and what lies past the right edge
    out[:, :w] = a[:, :w] * t.T[..., None] + a[:, n - w:] * (1 - t.T[..., None])
    a = out.copy()
    out[:w, :] = a[:w, :] * t[..., None] + a[n - w:, :] * (1 - t[..., None])
    # the last w columns/rows are no longer needed to match: crop them off and scale back up
    core = out[:n - w, :n - w]
    return Image.fromarray(np.clip(core, 0, 255).astype(np.uint8)).resize((size, size), Image.LANCZOS)


def key_magenta(img, height=512):
    """Magenta background to transparency, the pink fringe taken out of the edges, cropped and scaled."""
    a = np.asarray(img.convert("RGB")).astype(np.float32) / 255
    r, g, b = a[..., 0], a[..., 1], a[..., 2]
    # how magenta a pixel is: red and blue high, green low
    magenta = np.clip(np.minimum(r, b) - g, 0, 1)
    alpha = 1 - np.clip((magenta - 0.25) / 0.35, 0, 1)
    # despill: where magenta bled into the edge, pull red and blue down towards green
    spill = np.clip(np.minimum(r, b) - g, 0, None) * (1 - alpha * 0.5)
    rgb = a.copy()
    rgb[..., 0] -= spill * (alpha < 1)
    rgb[..., 2] -= spill * (alpha < 1)
    rgba = np.dstack([np.clip(rgb, 0, 1), alpha])
    ys, xs = np.nonzero(alpha > 0.1)
    if len(ys) == 0:
        raise ValueError("nothing left once the magenta is gone")
    pad = 4
    crop = rgba[max(0, ys.min() - pad):ys.max() + pad, max(0, xs.min() - pad):xs.max() + pad]
    out = Image.fromarray((crop * 255).astype(np.uint8), "RGBA")
    k = height / out.height
    return out.resize((max(1, round(out.width * k)), height), Image.LANCZOS)


def main(incoming=INCOMING):
    incoming = Path(incoming)
    done = []
    for path in sorted(incoming.glob("*")):
        if path.suffix.lower() not in (".png", ".jpg", ".jpeg", ".webp"):
            continue
        name = path.stem.lower()
        if name.startswith("ground_"):
            target = OUT / "ground" / f"{name[7:]}.jpg"
            make = lambda img: seamless(img)                       # noqa: E731
            save = {"quality": 92}
        elif name.startswith(PLANTS):
            target = OUT / "plants" / f"{name}.png"
            make = key_magenta
            save = {}
        elif name.startswith("arms_"):
            target = OUT / "arms" / f"{name[5:]}.png"
            make = lambda img: img.convert("RGB").resize((512, 512), Image.LANCZOS)   # noqa: E731
            save = {}
        else:
            print("not mine:", path.name)
            continue
        if target.exists() and target.stat().st_mtime >= path.stat().st_mtime:
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        try:
            make(Image.open(path)).save(target, **save)
        except (OSError, ValueError) as error:
            print(f"could not use {path.name}: {error}")
            continue
        done.append(target.relative_to(ROOT))
        print("made", target.relative_to(ROOT))
    return done


if __name__ == "__main__":
    main(*sys.argv[1:])
