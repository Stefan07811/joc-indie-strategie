"""Diplomacy between the realms, and the AI that rules the realms the player does not."""

import time

import pytest

from crowns.game.campaign import Campaign
from crowns.game.navigation import Navigation
from crowns.game.realms import load
from crowns.mapdata import Ground
from crowns.provinces import ProvinceMap


@pytest.fixture(scope="module")
def world():
    provmap = ProvinceMap()
    nav = Navigation(Ground(), provmap)
    return provmap, nav, *load()


@pytest.fixture
def c(world):
    provmap, nav, realms, relations = world
    return Campaign(provmap, realms, relations, player="wallachia", seed=3)


def test_opinions_follow_faith_and_history(c):
    assert c.opinion("poland", "lithuania") > 50                         # the union
    assert c.opinion("ott_isa", "ott_meh") < -30                         # brothers fighting for a throne
    assert c.opinion("wallachia", "moldavia") > c.opinion("wallachia", "karaman")
    assert c.opinion("hungary", "naples") < 0                             # Ladislaus wants Sigismund's crown
    assert "ott_rum" in c.neighbours["wallachia"] and "hungary" in c.neighbours["wallachia"]


def test_alliances_need_trust(c):
    ok, why = c.ally("wallachia", "karaman")
    assert not ok and "trust" in why
    c.nudge("wallachia", "moldavia", 60)
    ok, _ = c.ally("wallachia", "moldavia")
    assert ok and c.allies_of("wallachia") == ["moldavia"]
    war = c.declare_war("hungary", "wallachia", {"kind": "conquest", "province": "fagaras"})
    assert "moldavia" in war.defenders                                    # the ally answers the call
    assert c.break_alliance("wallachia", "moldavia")


def test_a_weak_neighbour_may_bow_rather_than_fight(c):
    ok, _ = c.tribute_answer("ott_rum", "wallachia")
    assert not ok                                                          # Mircea will fight
    ok, why = c.demand_tribute("ott_rum", "kastrioti")
    assert not ok and "already answers" in why                            # already Süleyman's vassal
    ok, _ = c.demand_tribute("hungary", "frankopan")
    assert not ok                                                          # already Hungary's vassal
    c.overlord["dukagjini"] = None
    ok, why = c.demand_tribute("ott_rum", "dukagjini")
    assert ok, why
    assert c.overlord["dukagjini"] == ("ott_rum", "tributary")


def test_gifts_buy_goodwill(c):
    c.realms["wallachia"].treasury = 10_000
    before = c.opinion("wallachia", "serbia")
    assert c.send_gift("wallachia", "serbia", 2_000)
    assert c.opinion("wallachia", "serbia") > before + 5
    assert c.realms["wallachia"].treasury == 8_000
    assert not c.send_gift("wallachia", "serbia", 1_000_000)


def test_the_ai_runs_the_world_for_two_years(world):
    provmap, nav, realms, relations = world
    c = Campaign(provmap, realms, relations, player="wallachia", seed=11)
    c.attach_ai(nav)
    player_treasury = c.realms["wallachia"].treasury
    start = time.time()
    for _ in range(24):
        c.end_month()
    assert time.time() - start < 60
    # the AI builds and raises troops; the player's realm is left alone to the player
    built = sum(len(p.buildings) for p in c.provinces.values() if p.owner != "wallachia")
    assert built > 30
    assert all(not p.buildings for p in c.provinces_of("wallachia"))
    assert c.realms["wallachia"].treasury > player_treasury
    # nobody's treasury is deep in debt
    assert all(r.treasury > -5_000 for r in c.realms.values())
    for army in c.armies:
        assert army.regiments and army.men > 0
        assert provmap.at(army.x, army.y) is not None or nav.land_cell(army.x, army.y) is not None


def test_the_ai_makes_war_and_peace(world):
    provmap, nav, realms, relations = world
    c = Campaign(provmap, realms, relations, player="wallachia", seed=5)
    c.attach_ai(nav)
    wars, peaces = set(), 0
    for _ in range(72):
        before = {w.id for w in c.wars}
        c.end_month()
        wars |= {w.id for w in c.wars}
        peaces += len(before - {w.id for w in c.wars})
    assert len(wars) >= 3 and peaces >= 1


def test_peace_offered_to_the_player(world):
    provmap, nav, realms, relations = world
    c = Campaign(provmap, realms, relations, player="wallachia", seed=2)
    c.attach_ai(nav)
    war = c.declare_war("wallachia", "ott_rum", {"kind": "conquest", "province": "nikopol"})
    for pid in ("tarnovo", "nikopol", "vidin", "ruse", "silistra"):
        c.provinces[pid].controller = "wallachia"
    war.battle_score = 30
    war.start = c.date
    for _ in range(5):
        c.date = c.date.next()
    c.ai.month()
    offers = [p for p in c.proposals if p["kind"] == "peace"]
    assert offers and offers[0]["from"] == "ott_rum"
    text = c.answer(offers[0], True)
    assert text and war not in c.wars
