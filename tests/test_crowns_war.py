"""War: declaring it, battles, sieges, attrition, the war score and peace."""

import json

import pytest

from crowns.game.armies import Regiment
from crowns.game.calendar import Date
from crowns.game.campaign import Campaign
from crowns.game.realms import load
from crowns.provinces import ProvinceMap


@pytest.fixture(scope="module")
def world():
    return ProvinceMap(), *load()


@pytest.fixture
def c(world):
    provmap, realms, relations = world
    return Campaign(provmap, realms, relations, player="wallachia", seed=7)


def town(c, pid):
    return c.static(pid).town


def host(c, tag, pid, unit, n, men=None):
    """A fresh army of n regiments standing at the province's town."""
    return c.new_army(tag, *town(c, pid), [Regiment(unit, men or 1000) for _ in range(n)])


def clear(c, *tags):
    c.armies = [a for a in c.armies if a.owner not in tags]


def test_who_may_declare_on_whom(c):
    assert c.can_declare("wallachia", "ott_rum", {"kind": "conquest", "province": "nikopol"})[0]
    assert not c.can_declare("wallachia", "ott_rum", {"kind": "conquest", "province": "targoviste"})[0]
    # a vassal may only fight its overlord for its freedom
    assert not c.can_declare("moldavia", "poland", {"kind": "conquest", "province": "lwow"})[0]
    assert c.can_declare("moldavia", "poland", {"kind": "independence"})[0]
    assert not c.can_declare("wallachia", "poland", {"kind": "independence"})[0]
    # a realm that already answers to someone cannot be made to pay tribute to another
    assert not c.can_declare("wallachia", "serbia", {"kind": "tribute"})[0]


def test_overlords_vassals_and_allies_are_called(c):
    war = c.declare_war("wallachia", "ott_rum", {"kind": "conquest", "province": "nikopol"})
    assert war.attackers == ["wallachia"]
    assert "brankovic" in war.defenders and "kastrioti" in war.defenders      # Süleyman's vassals
    assert "serbia" not in war.defenders                                       # a tributary is not called
    assert c.at_war("wallachia", "brankovic") and not c.at_war("wallachia", "hungary")
    assert any("declares war" in line for line in war.log)
    assert c.messages and "Nikopol" in c.messages[-1]
    war2 = c.declare_war("moldavia", "poland", {"kind": "independence"})
    assert "lithuania" in war2.defenders                                       # the union partner
    war3 = c.declare_war("bavaria", "austria", {"kind": "conquest", "province": "linz"})
    assert "hungary" in war3.defenders                                         # Sigismund's ally


def test_an_army_at_a_town_besieges_it_and_takes_it(c):
    c.declare_war("wallachia", "ott_rum", {"kind": "conquest", "province": "nikopol"})
    clear(c, "ott_rum", "brankovic", "kastrioti", "arianiti")
    army = host(c, "wallachia", "nikopol", "great_host", 6)
    nikopol = c.provinces["nikopol"]
    assert c.fort("nikopol") == 2
    months = 0
    while nikopol.controller != "wallachia" and months < 24:
        c.end_month()
        months += 1
        if nikopol.controller != "wallachia":
            assert nikopol.siege and nikopol.siege["by"] == "wallachia"
    assert nikopol.controller == "wallachia" and nikopol.owner == "ott_rum"
    assert 2 <= months <= 12
    war = c.wars[0]
    assert c.score(war) > 0
    # holding the war goal ticks the score up
    tick = war.ticking
    c.end_month()
    assert war.ticking > tick
    assert army.men < 6000                                     # a siege in enemy land costs men


def test_a_small_force_cannot_close_in_a_strong_town(c):
    c.declare_war("wallachia", "ott_rum", {"kind": "conquest", "province": "nikopol"})
    clear(c, "ott_rum", "brankovic", "kastrioti", "arianiti")
    host(c, "wallachia", "nikopol", "great_host", 1, men=500)
    c.end_month()
    assert c.provinces["nikopol"].siege is None and c.provinces["nikopol"].controller == "ott_rum"


def test_armies_that_meet_fight(c):
    c.declare_war("wallachia", "ott_rum", {"kind": "conquest", "province": "nikopol"})
    clear(c, "wallachia", "ott_rum", "brankovic", "kastrioti", "arianiti")
    x, y = town(c, "teleorman")
    big = c.new_army("wallachia", x, y, [Regiment("boyars", 300, 0.5) for _ in range(10)] +
                     [Regiment("calarasi", 400) for _ in range(10)])
    small = c.new_army("ott_rum", x + 3, y, [Regiment("azaps", 600) for _ in range(3)])
    assert c.hostile_near(big) is small
    c.end_month()
    assert len(c.battles) == 1
    report = c.battles[0]
    assert report["winner"] == "wallachia" and report["place"] == "Teleorman"
    assert report["losses"]["ott_rum"] > report["losses"]["wallachia"]
    war = c.wars[0]
    assert war.battle_score > 0 and c.score(war) > 0
    assert war.losses["ott_rum"] > 0
    if small in c.armies:                                      # the beaten army has fallen back
        assert abs(small.x - big.x) + abs(small.y - big.y) > 6
    assert any(r.experience > 0.5 for r in big.regiments)


def test_terrain_favours_the_defender_on_foot(c):
    from crowns.game.armies import Army
    foot = Army("f", "serbia", "Foot", 0, 0, [Regiment("spearmen", 600) for _ in range(5)])
    horse = Army("h", "hungary", "Horse", 0, 0, [Regiment("knights", 300) for _ in range(5)])
    assert c.strength(foot, "mountains", True) > c.strength(foot, "plains", True)
    assert c.strength(horse, "plains", False) > c.strength(horse, "mountains", False)


def test_winter_in_enemy_land_kills(c):
    c.declare_war("wallachia", "ott_rum", {"kind": "conquest", "province": "nikopol"})
    clear(c, "wallachia", "ott_rum", "brankovic", "kastrioti", "arianiti")
    x, y = town(c, "lovech")
    army = c.new_army("wallachia", x + 12, y + 12, [Regiment("great_host", 1000) for _ in range(5)])
    c.date = Date(1403, 1)
    c.end_month()
    assert army.men <= 5000 * 0.97
    home = c.new_army("wallachia", *town(c, "vlasia"), [Regiment("great_host", 1000)])
    c.date = Date(1403, 7)
    c.end_month()
    assert home.men == 1000                                     # summer at home: nothing lost


def test_peace_on_terms_the_loser_can_accept(c):
    war = c.declare_war("wallachia", "ott_rum", {"kind": "conquest", "province": "nikopol"})
    terms = {"loser": "ott_rum", "provinces": ["nikopol"]}
    assert not c.would_accept(war, terms, "ott_rum")          # nothing has happened yet
    c.provinces["nikopol"].controller = "wallachia"
    c.provinces["silistra"].controller = "wallachia"
    war.battle_score = 30
    assert c.score(war) > c.peace_cost(war, terms, "ott_rum")
    assert c.would_accept(war, terms, "ott_rum")
    text = c.make_peace(war, terms)
    assert "cedes Nikopol" in text
    assert c.provinces["nikopol"].owner == c.provinces["nikopol"].controller == "wallachia"
    assert c.provinces["silistra"].owner == c.provinces["silistra"].controller == "ott_rum"
    assert not c.wars and not c.at_war("wallachia", "ott_rum")
    assert c.truce_with("wallachia", "ott_rum") and c.truce_with("wallachia", "brankovic")
    assert not c.can_declare("wallachia", "ott_rum", {"kind": "conquest", "province": "silistra"})[0]


def test_a_white_peace_for_a_war_going_nowhere(c):
    war = c.declare_war("wallachia", "ott_rum", {"kind": "conquest", "province": "nikopol"})
    assert c.would_accept(war, {"loser": None}, "ott_rum")
    c.make_peace(war, {"loser": None})
    assert not c.wars


def test_tribute_and_independence(c):
    war = c.declare_war("hungary", "bosnia", {"kind": "tribute"})
    c.make_peace(war, {"loser": "bosnia", "tribute": True})
    assert c.overlord["bosnia"] == ("hungary", "tributary")
    assert c.budget("bosnia").tribute_out > 0
    war = c.declare_war("moldavia", "poland", {"kind": "independence"})
    c.make_peace(war, {"loser": "poland", "independence": True})
    assert c.overlord["moldavia"] is None


def test_a_realm_that_loses_its_last_province_is_gone(c):
    war = c.declare_war("ott_rum", "thopia", {"kind": "conquest", "province": "kruja"})
    assert "venice" in war.defenders                                           # Kruja's protector
    c.make_peace(war, {"loser": "thopia", "provinces": ["kruja"]})
    assert not c.realms["thopia"].alive and not c.armies_of("thopia")
    assert c.provinces["kruja"].owner == "ott_rum"


def test_a_war_is_saved_and_loaded(world, c):
    provmap, realms, relations = world
    war = c.declare_war("wallachia", "ott_rum", {"kind": "conquest", "province": "nikopol"})
    war.battle_score = 12
    c.provinces["nikopol"].siege = {"by": "wallachia", "progress": 0.4, "months": 2}
    again = Campaign.from_dict(json.loads(json.dumps(c.to_dict())), provmap, realms, relations)
    assert again.at_war("wallachia", "ott_rum") and again.wars[0].battle_score == 12
    assert again.provinces["nikopol"].siege["progress"] == 0.4
    assert again.score(again.wars[0]) == pytest.approx(c.score(war))
