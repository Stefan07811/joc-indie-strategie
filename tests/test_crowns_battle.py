"""Tactical battles: deployment, missiles, charges and flanks, morale, the outcome in the campaign."""

import math

import pytest

from crowns.game.armies import Army, Regiment
from crowns.game.battle import DEPLOY_DEPTH, FIELD_H, Battle, Unit, conclude, tactical
from crowns.game.campaign import Campaign
from crowns.game.realms import load
from crowns.game.rules import UNITS
from crowns.provinces import ProvinceMap

VLACH = [("boyars", 300)] * 2 + [("calarasi", 400)] * 3 + [("vlach_archers", 500)] * 2 + [("great_host", 1000)] * 3
OTTOMAN = [("sipahis", 400)] * 3 + [("akinjis", 500)] * 2 + [("azaps", 600)] * 3 + [("janissaries", 300)]


def army(tag, units, times=1):
    return Army(tag, tag, f"Army of {tag}", 0, 0, [Regiment(u, n, 0.2) for u, n in units * times])


def test_the_armies_deploy_at_their_edges():
    b = Battle(army("wallachia", VLACH), army("ott_rum", OTTOMAN), UNITS, "hills", seed=1)
    assert len(b.side_units(0)) == len(VLACH) and len(b.side_units(1)) == len(OTTOMAN)
    assert all(u.y < DEPLOY_DEPTH for u in b.side_units(0))
    assert all(u.y > FIELD_H - DEPLOY_DEPTH for u in b.side_units(1))
    assert sum(u.general for u in b.units) == 2
    u = b.side_units(0)[0]
    assert b.place_unit(u, 600, 200) and (u.x, u.y) == (600, 200)
    assert not b.place_unit(u, 600, 900)                   # not in no man's land
    b.begin()
    assert not b.place_unit(u, 500, 200)                   # not once the battle has begun


def test_a_battle_is_fought_to_the_end():
    b = Battle(army("wallachia", VLACH), army("ott_rum", OTTOMAN), UNITS, "plains", seed=3)
    winner = b.run(dt=1.0)
    assert winner in (0, 1) and b.time < 1800
    assert any("flees" in line for line in b.log)
    loser = 1 - winner
    assert not b.side_units(loser)
    for side in (0, 1):
        assert sum(b.survivors(side).values()) < sum(u.start_men for u in b.units if u.side == side)


def test_numbers_tell():
    big = Battle(army("wallachia", VLACH, 3), army("ott_rum", OTTOMAN), UNITS, "plains", seed=2)
    assert big.run(dt=1.0) == 0


def test_the_same_seed_fights_the_same_battle():
    a = Battle(army("wallachia", VLACH), army("ott_rum", OTTOMAN), UNITS, "plains", seed=5)
    b = Battle(army("wallachia", VLACH), army("ott_rum", OTTOMAN), UNITS, "plains", seed=5)
    assert a.run() == b.run() and a.survivors(0) == b.survivors(0)


def test_archers_shoot_what_comes_near():
    b = Battle(army("wallachia", [("vlach_archers", 500)]), army("ott_rum", [("azaps", 600)]), UNITS, "plains", 1)
    archers, foe = b.units
    archers.x, archers.y, foe.x, foe.y = 1200, 600, 1200, 760
    b.begin()
    for _ in range(20):
        b.step(1.0)
    assert archers.ammo < 30 and foe.men < 600


def _duel(attacker_angle):
    """Knights hitting spearmen from a given side: 0 the front, pi the rear."""
    b = Battle(army("hungary", [("knights", 300)]), army("serbia", [("spearmen", 600)]), UNITS, "plains", 1)
    knights, spears = b.units
    spears.x, spears.y, spears.facing = 1200, 800, 0.0          # facing +y
    knights.x = spears.x + math.sin(attacker_angle) * 200
    knights.y = spears.y + math.cos(attacker_angle) * 200
    knights.facing = attacker_angle + math.pi
    b.begin()
    b.attack(knights, spears)
    for _ in range(120):
        b.step(0.5)
    return 600 - spears.men


def test_a_blow_in_the_rear_hurts_more_than_in_the_front():
    assert _duel(math.pi) > _duel(0.0)


@pytest.fixture(scope="module")
def world():
    return ProvinceMap(), *load()


def test_the_outcome_returns_to_the_campaign(world):
    provmap, realms, relations = world
    c = Campaign(provmap, realms, relations, player="wallachia", seed=1)
    war = c.declare_war("wallachia", "ott_rum", {"kind": "conquest", "province": "nikopol"})
    x, y = c.static("teleorman").town
    ours = c.new_army("wallachia", x, y, [Regiment(u, n) for u, n in VLACH * 2])
    theirs = c.new_army("ott_rum", x + 2, y, [Regiment(u, n) for u, n in OTTOMAN])
    c.appoint_commanders()
    before = (ours.men, theirs.men)
    b = tactical(c, ours, theirs, seed=4)
    assert b.place == "Teleorman"
    b.run(dt=1.0)
    report = conclude(c, b, ours, theirs)
    assert report["place"] == "Teleorman"
    assert ours.men < before[0]
    assert theirs not in c.armies or theirs.men < before[1]
    assert war.battle_score != 0 and war.losses


def test_formations_change_the_block_and_who_may_take_them():
    b = Battle(army("hungary", [("knights", 300), ("spearmen", 600), ("crossbowmen", 500)]),
               army("serbia", [("spearmen", 600)]), UNITS, "plains", 1)
    by = {u.unit: u for u in b.side_units(0)}
    knights, spears, bows = by["knights"], by["spearmen"], by["crossbowmen"]
    line = spears.frontage
    assert b.set_formation(spears, "deep") and spears.frontage < line and spears.depth > 12
    assert not b.set_formation(spears, "wedge")            # wedges are for horse
    assert b.set_formation(knights, "wedge") and knights.armour < knights.defence
    assert b.set_formation(bows, "loose") and "square" not in bows.formations()
    assert b.set_formation(spears, "square") and spears.speed(False) < bows.speed(False)


def test_a_square_has_no_flank():
    def rear_blow(formation):
        b = Battle(army("hungary", [("knights", 300)]), army("serbia", [("spearmen", 600)]), UNITS, "plains", 1)
        knights, spears = b.units
        spears.x, spears.y, spears.facing = 1200, 800, 0.0
        knights.x, knights.y = 1200, 800 - 30                # behind the spearmen
        b.set_formation(spears, formation)
        return b._strength(knights, spears)
    assert rear_blow("square") < rear_blow("line") / 1.5


def test_running_tires_and_rest_restores():
    b = Battle(army("wallachia", [("great_host", 1000)]), army("ott_rum", [("azaps", 600)]), UNITS, "plains", 1)
    host, _ = b.units
    b.begin()
    host.run = True
    b.move(host, host.x + 600, host.y)
    for _ in range(60):
        b._act(host, 1.0)
    tired = host.stamina
    assert tired < 60
    b.halt(host)
    for _ in range(30):
        b._act(host, 1.0)
    assert host.stamina > tired


def test_free_regiments_close_with_what_comes_near_and_held_ones_stand():
    for stance, expect in (("free", True), ("hold", False)):
        b = Battle(army("wallachia", [("great_host", 1000)]), army("ott_rum", [("azaps", 600)]), UNITS, "plains", 1)
        host, foe = b.units
        foe.x, foe.y = host.x, host.y + 60
        b.begin()
        b.set_stance(host, stance)
        b.captains(0)
        assert (host.order is not None) == expect
