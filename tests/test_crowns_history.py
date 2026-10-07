"""History: the events of the age, each realm's missions, and the great decisions."""

import json

import pytest

from crowns.game.calendar import Date
from crowns.game.campaign import Campaign
from crowns.game.history import EVENT, cede
from crowns.game.missions import MISSIONS, missions_of
from crowns.game.realms import load
from crowns.provinces import ProvinceMap


@pytest.fixture(scope="module")
def world():
    return ProvinceMap(), *load()


@pytest.fixture
def c(world):
    provmap, realms, relations = world
    return Campaign(provmap, realms, relations, player="wallachia", seed=4)


def run_until(c, date):
    while c.date < date:
        c.end_month()


def test_timur_takes_smyrna_leaves_and_dies(c):
    assert c.overlord["karaman"] == ("timurids", "vassal")
    assert any(a.name == "The Host of Timur" for a in c.armies)
    run_until(c, Date(1403, 3))
    assert c.provinces["smyrna"].owner == "aydin"
    assert "smyrna" in c.fired
    run_until(c, Date(1403, 9))
    assert "timur_leaves" in c.fired and "bayezid" in c.fired
    assert not any(a.name == "The Host of Timur" for a in c.armies)
    assert c.overlord["karaman"] is None and c.overlord["ott_meh"] is None
    assert c.overlord["trebizond"] == ("timurids", "vassal")       # the east stays Timur's for now
    run_until(c, Date(1405, 3))
    assert "timur_dies" in c.fired
    assert c.ruler("timurids").name != "Timur" and c.overlord["trebizond"] is None
    assert c.budget("timurids").beyond < 8000
    assert any("Timur" in text for _, text in c.history)


def test_the_player_chooses_and_the_ai_weighs(world):
    provmap, realms, relations = world
    c = Campaign(provmap, realms, relations, player="ott_rum", seed=1)
    run_until(c, Date(1403, 2))
    offers = [p for p in c.pending if p["event"] == "gallipoli"]
    assert offers and "Thessaloniki" in offers[0]["text"]
    choice = c.choose(offers[0], 0)
    assert choice.label == "Sign the treaty"
    assert c.provinces["thessaloniki"].owner == "byzantium"
    assert c.truce_with("ott_rum", "venice")
    # with Süleyman left to the AI, the treaty is (most likely) signed by itself
    signed = 0
    for seed in range(6):
        ai = Campaign(provmap, realms, relations, player="wallachia", seed=seed)
        run_until(ai, Date(1403, 7))
        signed += ai.provinces["thessaloniki"].owner == "byzantium"
    assert signed >= 3


def test_the_sons_of_bayezid_fight(world):
    provmap, realms, relations = world
    wars = 0
    for seed in range(4):
        c = Campaign(provmap, realms, relations, player="wallachia", seed=seed)
        run_until(c, Date(1404, 1))
        wars += any(set(w.attackers + w.defenders) >= {"ott_meh", "ott_isa"} for w in c.wars) or \
            c.provinces["bursa"].owner != "ott_isa" or "ulubad" in c.fired
    assert wars >= 3


def test_a_mission_accomplished(c):
    assert [m.title for m in missions_of(c, "wallachia")][0] == "Take Back the Dobruja"
    prestige, gold = c.realms["wallachia"].prestige, c.realms["wallachia"].treasury
    cede(c, "dobruja", "wallachia")
    cede(c, "silistra", "wallachia")
    c.end_month()
    assert "wallachia.dobruja" in c.missions_done
    assert c.realms["wallachia"].prestige >= prestige + 15
    assert any("Mission accomplished: Take Back the Dobruja" in m for m in c.messages)
    view = {m["id"]: m["state"] for m in c.missions_view("wallachia")}
    assert view["wallachia.dobruja"] == "done" and view["wallachia.sultans"] == "open"
    assert c.realms["wallachia"].treasury > gold


def test_every_realm_has_missions(c):
    for tag in c.realms:
        assert missions_of(c, tag), tag
    for m in MISSIONS:
        assert m.realm in c.realms, m.id
        m.done(c, m.realm)                        # the conditions can be evaluated


def test_decisions(c):
    names = {d.id: ok for d, ok, _ in c.decisions_for("hungary")}
    assert "dragon" in names and not names["dragon"]          # not before 1408
    c.date = Date(1408, 1)
    c.realms["hungary"].prestige = 20
    ok, _ = c.take_decision("dragon", "hungary")
    assert ok and "dragon" not in {d.id for d, _, _ in c.decisions_for("hungary")}
    # one Ottoman holding Edirne and Bursa proclaims the Sultanate
    cede(c, "bursa", "ott_rum")
    ok, _ = c.take_decision("sultanate", "ott_rum")
    assert ok and c.info["ott_rum"]["name"] == "Ottoman Sultanate" and c.info["ott_rum"]["rank"] == "empire"


def test_the_plague(c):
    before = sum(p.population for p in c.provinces.values())
    EVENT["plague"].effect(c, None)
    assert sum(p.population for p in c.provinces.values()) < before
    assert c.plague_at is not None


def test_a_rising_asks_the_player(c):
    c.provinces["arges"].unrest = 9
    c.date = Date(1404, 1)
    for _ in range(80):
        c.history_month()
        if any(p["event"] == "revolt" for p in c.pending):
            break
    revolt = [p for p in c.pending if p["event"] == "revolt"]
    assert revolt and "Argeș" in revolt[0]["text"]
    c.choose(revolt[0], 1)
    assert c.provinces["arges"].unrest < 9


def test_history_is_saved(world, c):
    provmap, realms, relations = world
    run_until(c, Date(1403, 6))
    cede(c, "bursa", "ott_rum")
    c.take_decision("sultanate", "ott_rum")
    again = Campaign.from_dict(json.loads(json.dumps(c.to_dict())), provmap, realms, relations)
    assert again.fired == c.fired and again.info["ott_rum"]["name"] == "Ottoman Sultanate"
    assert realms["ott_rum"]["name"] == "Ottoman Rumelia"     # the data itself is untouched
