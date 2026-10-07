"""The trade roads, the crusades and the end of the chronicle."""

import pytest

from crowns.game.calendar import Date
from crowns.game.campaign import Campaign
from crowns.game.realms import load
from crowns.game.trade import ROUTES
from crowns.provinces import ProvinceMap


@pytest.fixture(scope="module")
def world():
    return ProvinceMap(), *load()


@pytest.fixture
def c(world):
    provmap, realms, relations = world
    return Campaign(provmap, realms, relations, player="wallachia", seed=4)


def test_the_roads_run_through_real_towns_and_pay(c):
    for name, (value, towns) in ROUTES.items():
        assert all(t in c.provinces for t in towns), name
    assert c.trade_income("constantinople") > c.trade_income("buda") > 0
    assert "the Danube" in c.routes_through("chilia") and "the Black Sea" in c.routes_through("chilia")
    assert c.trade_income("targoviste") == 0


def test_war_cuts_a_road(c):
    open_, flow = c.route_state("the Danube")
    before = c.trade_income("buda")
    holder_a, holder_b = c.provinces["vidin"].controller, c.provinces["nikopol"].controller
    c.provinces["nikopol"].siege = {"by": "wallachia", "progress": 0.1, "months": 1}
    cut, less = c.route_state("the Danube")
    assert cut < open_ and less < flow and c.trade_income("buda") < before


def test_venice_profits_more_in_its_own_ports(c):
    ragusa_income = c.trade_income("ragusa")
    c.provinces["ragusa"].controller = "hungary"
    c._trade_cache = None
    assert c.trade_income("ragusa") < ragusa_income


def test_the_pope_preaches_a_crusade(c):
    for tag in [t for t in c.realms if t.startswith("ott_")]:
        for w in list(c.wars):
            if tag in w.attackers + w.defenders:
                c.wars.remove(w)
    war = c.call_crusade()
    assert war is not None and c.crusade["leader"] in war.attackers
    assert c.religion(c.crusade["leader"]) == "catholic" and c.crusade["target"].startswith("ott_")
    assert c.pending and c.pending[-1]["event"] == "crusade_call"          # Wallachia is asked to join
    c.join_crusade("wallachia")
    assert "wallachia" in war.attackers


def test_the_chronicle_closes_in_1500(c):
    assert c.chronicle_closes() is None
    c.date = Date(1500, 1)
    assert c.chronicle_closes() == "time" and c.chronicle_closes() is None   # only once
    ranks = c.reckoning()
    assert ranks[0][0] >= ranks[-1][0] and any(tag == "wallachia" for _, tag in ranks)


def test_a_fallen_realm_ends_the_chronicle_for_its_player(c):
    c.realms["wallachia"].alive = False
    assert c.chronicle_closes() == "fallen"
