"""Bringing in the painted pictures: seamless ground, plants cut from their magenta, arms."""

import numpy as np
from PIL import Image, ImageDraw

import tools.import_art as imp


def test_a_plant_loses_its_magenta(tmp_path, monkeypatch):
    img = Image.new("RGB", (400, 400), (255, 0, 255))
    ImageDraw.Draw(img).ellipse((100, 50, 300, 350), fill=(40, 120, 40))
    out = np.asarray(imp.key_magenta(img, height=200))
    assert out.shape[0] == 200 and out.shape[2] == 4
    assert out[0, 0, 3] < 30 and out[100, out.shape[1] // 2, 3] > 240        # corner clear, middle solid
    solid = out[out[..., 3] > 200]
    assert (solid[:, 0].astype(int) - solid[:, 1]).max() < 60                 # no pink left on the leaves


def test_ground_tiles_without_a_seam():
    rng = np.random.default_rng(0)
    a = (rng.random((256, 256, 3)) * 255).astype(np.uint8)
    a[:, :128] = 30
    a[:, 128:] = 220                                                           # a hard seam at the edges
    out = np.asarray(imp.seamless(Image.fromarray(a), size=256)).astype(int)
    assert abs(out[:, 0].mean() - out[:, -1].mean()) < 40                    # left edge meets the right


def test_the_import_sorts_the_pictures(tmp_path, monkeypatch):
    incoming = tmp_path / "in"
    incoming.mkdir()
    Image.new("RGB", (64, 64), (90, 130, 60)).save(incoming / "ground_meadow.png")
    tree = Image.new("RGB", (64, 64), (255, 0, 255))
    ImageDraw.Draw(tree).rectangle((20, 10, 44, 60), fill=(60, 90, 40))
    tree.save(incoming / "tree_oak.png")
    Image.new("RGB", (64, 64), (200, 30, 30)).save(incoming / "arms_hungary.png")
    Image.new("RGB", (64, 64)).save(incoming / "holiday.png")
    monkeypatch.setattr(imp, "OUT", tmp_path / "art")
    monkeypatch.setattr(imp, "ROOT", tmp_path)
    made = {str(p) for p in imp.main(incoming)}
    assert made == {"art/ground/meadow.jpg", "art/plants/tree_oak.png", "art/arms/hungary.png"}
    assert imp.main(incoming) == []                                            # nothing new: nothing made
