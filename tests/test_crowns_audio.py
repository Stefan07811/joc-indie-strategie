"""The music and sounds are there, and the right piece plays for the realm's mood."""

import pytest

from crowns.audio import MUSIC, PLAYLISTS, SOUNDS, mood_of
from crowns.game.campaign import Campaign
from crowns.game.realms import load
from crowns.provinces import ProvinceMap


def test_every_piece_and_sound_is_a_real_ogg_file():
    names = {n for playlist in PLAYLISTS.values() for n in playlist}
    for name in names:
        path = MUSIC / f"{name}.ogg"
        assert path.read_bytes()[:4] == b"OggS" and path.stat().st_size > 500_000, name
    for name in ("click", "month", "march", "victory", "defeat", "event", "build"):
        assert (SOUNDS / f"{name}.ogg").read_bytes()[:4] == b"OggS", name


@pytest.fixture(scope="module")
def c():
    provmap = ProvinceMap()
    realms, relations = load()
    return Campaign(provmap, realms, relations, player=None)


def test_the_mood_follows_the_realm(c):
    assert mood_of(c) == "choose"
    c.player = "wallachia"
    assert mood_of(c) == "vlach"
    c.player = "ott_rum"
    assert mood_of(c) == "east"
    c.player = "venice"
    assert mood_of(c) == "west"
    c.declare_war("venice", "zeta", {"kind": "conquest", "province": "antivari"})
    assert mood_of(c) == "war"
