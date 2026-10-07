"""The new game's map data: geography, provinces as drawn, the overlays' lookups."""

import sys
from pathlib import Path

import numpy as np
import pytest

from crowns import geo
from crowns.mapdata import blur, smoothstep
from crowns.provinces import ProvinceMap

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))
from history_1402 import PROVINCES, REALM_COLORS, REALM_NAMES  # noqa: E402


@pytest.fixture(scope="module")
def provmap():
    return ProvinceMap()


def test_projection_round_trip():
    for lon, lat in ((12.5, 45.4), (28.97, 41.01), (44.0, 34.0)):
        x, y = geo.to_map(lon, lat)
        assert 0 <= x <= geo.WIDTH and 0 <= y <= geo.HEIGHT
        assert geo.to_lonlat(x, y) == pytest.approx((lon, lat))


def test_every_province_is_on_the_map(provmap):
    assert len(provmap.provinces) == len(PROVINCES) >= 300
    for pid, name, lon, lat, owner, culture, religion in PROVINCES:
        p = provmap.provinces[pid]
        assert p.area > 0 and p.owner == owner and p.name == name
        assert owner in REALM_COLORS and owner in REALM_NAMES


def test_neighbours_are_mutual(provmap):
    for p in provmap.provinces.values():
        for n in p.neighbors:
            assert p.id in provmap.provinces[n].neighbors, (p.id, n)


def test_towns_lie_in_their_provinces(provmap):
    """Every main town is inside its own province (or within a pixel or two, at a coast)."""
    wrong = []
    for p in provmap.provinces.values():
        x, y = p.town
        found = {getattr(provmap.at(x + dx, y + dy), "id", None) for dx in (-2, 0, 2) for dy in (-2, 0, 2)}
        if p.id not in found:
            wrong.append(p.id)
    assert not wrong


def test_history_on_the_map(provmap):
    assert provmap.at(*geo.to_map(28.97, 41.01)).owner == "byzantium"   # Constantinople
    assert provmap.at(*geo.to_map(29.06, 40.18)).owner == "ott_isa"     # Bursa
    assert provmap.at(*geo.to_map(25.45, 44.93)).owner == "wallachia"   # Târgoviște
    assert provmap.at(*geo.to_map(30.0, 43.0)) is None                    # the Black Sea
    assert "fagaras" in provmap.provinces["arges"].neighbors


def test_lookup_table(provmap):
    table = provmap.lookup({"buda": 3.0, "rome": 7.0})
    assert table[provmap.provinces["buda"].index] == 3.0 and table[provmap.provinces["sofia"].index] == 0


def test_blur_keeps_the_mean_and_smoothstep():
    rng = np.random.default_rng(1)
    a = rng.random((40, 50)).astype(np.float32)
    b = blur(a, 3)
    assert b.shape == a.shape and abs(b.mean() - a.mean()) < 0.02 and b.std() < a.std()
    assert smoothstep(0, 1, np.array([-1.0, 0.5, 2.0])).tolist() == [0.0, 0.5, 1.0]


def test_realm_labels_stand_in_the_largest_piece(provmap):
    from crowns.render.political import realm_blocks
    blocks = realm_blocks(provmap, {p.id: p.owner for p in provmap.provinces.values()})
    x, y, length, angle, area = blocks["wallachia"]
    assert provmap.at(x, y).owner == "wallachia" and -40 <= angle <= 40 and length > 0


def test_the_realms_of_1402(provmap):
    from crowns.game.realms import load
    from crowns.render.political import realm_blocks
    realms, relations = load()
    owners = {p.owner for p in provmap.provinces.values()}
    assert set(realms) == owners
    for tag, r in realms.items():
        assert provmap.provinces[r["capital"]].owner == tag
        assert r["rank"] in ("empire", "kingdom", "duchy", "county")
        assert r["ruler"]["name"] and r["situation"] and r["notable"]
        if r["overlord"]:
            assert r["overlord"]["tag"] in realms and r["overlord"]["tag"] != tag
    assert realms["wallachia"]["ruler"]["name"] == "Mircea the Elder"
    assert realms["moldavia"]["overlord"] == {"tag": "poland", "kind": "vassal"}
    for rel in relations:
        assert all(t in realms for t in rel["tags"])
    # the realm's name is written over the land that holds its capital
    owner_of = {p.id: p.owner for p in provmap.provinces.values()}
    capitals = {t: r["capital"] for t, r in realms.items()}
    x, y, *_ = realm_blocks(provmap, owner_of, capitals)["venice"]
    assert provmap.at(x, y) is not None and provmap.at(x, y).id in ("venice", "istria")
