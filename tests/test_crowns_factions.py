"""The great men of the realms: their discontent, what calms it, and the civil wars it brings."""

import pytest

from crowns.game.campaign import Campaign
from crowns.game.realms import load
from crowns.provinces import ProvinceMap


@pytest.fixture(scope="module")
def world():
    return ProvinceMap(), *load()


@pytest.fixture
def c(world):
    provmap, realms, relations = world
    return Campaign(provmap, realms, relations, player="wallachia", seed=2)


def test_the_quarrels_of_1402(c):
    f = c.faction("wallachia")
    assert f.name == "the Dănești boyars" and c.pretender_of("wallachia").name == "Dan"
    assert c.faction("hungary").name == "the barons' league"
    assert c.faction("venice") is None and c.faction("papal") is None     # no great men in a republic
    assert c.faction("ott_rum") is not None


def test_defeats_and_lost_lands_anger_them(c):
    calm = c.discontent_target("wallachia")
    c.note_defeat("wallachia", 2.0)
    for p in c.provinces_of("wallachia")[:3]:
        p.controller = "ott_rum"
    assert c.discontent_target("wallachia") > calm + 30


def test_gifts_calm_them_and_cost(c):
    f = c.faction("wallachia")
    f.discontent = 70
    gold = c.realms["wallachia"].treasury
    c.appease("wallachia", "privileges")
    assert f.discontent < 45 and c.realms["wallachia"].treasury < gold


def test_a_civil_war_crowns_the_pretender_or_crushes_him(world):
    provmap, realms, relations = world
    outcomes = set()
    for seed in range(30):
        c = Campaign(provmap, realms, relations, player="wallachia", seed=seed)
        c.faction("hungary").discontent = 95
        before = c.rulers["hungary"]
        changed = c.civil_war("hungary")
        outcomes.add(changed)
        assert changed == (c.rulers["hungary"] != before)
        if outcomes == {True, False}:
            break
    assert outcomes == {True, False}


def test_saved_and_loaded(c, world):
    provmap, realms, relations = world
    c.faction("wallachia").discontent = 77
    again = Campaign.from_dict(c.to_dict(), provmap, realms, relations)
    assert again.faction("wallachia").discontent == 77 and again.pretender_of("wallachia").name == "Dan"
