"""Rulers and their houses: ageing, death, succession, marriages, children, captains."""

import json

import pytest

from crowns.game.campaign import Campaign
from crowns.game.calendar import Date
from crowns.game.realms import load
from crowns.provinces import ProvinceMap


@pytest.fixture(scope="module")
def world():
    return ProvinceMap(), *load()


@pytest.fixture
def c(world):
    provmap, realms, relations = world
    return Campaign(provmap, realms, relations, player="wallachia", seed=9)


def test_the_rulers_of_1402(c):
    mircea = c.ruler("wallachia")
    assert mircea.name == "Mircea the Elder" and c.age(mircea) == 47 and mircea.dynasty == "Basarab"
    assert "strategist" in mircea.traits and c.skill(mircea, "martial") >= 7
    heir = c.heir_of("wallachia")
    assert heir.name == "Mihail" and heir.father == mircea.id
    assert c.ruler("poland").spouse and c.people[c.ruler("poland").spouse].name == "Anna of Celje"
    # Sigismund is the same man in Buda and as heir to his brother in Prague
    assert c.heir_of("bohemia") is c.ruler("hungary")
    assert c.heir_of("hungary") is c.ruler("austria")
    assert c.ruler("thopia").female and c.heir_of("thopia") is None
    assert c.heir_of("venice") is None                       # the Doge is elected


def test_a_son_succeeds_his_father(c):
    c.dies(c.ruler("wallachia"))
    assert c.ruler("wallachia").name == "Mihail"
    assert c.people[c.rulers["wallachia"]].court == "wallachia"
    assert any("Mircea the Elder" in m and "Mihail now reigns" in m for m in c.messages)
    assert c.history and "Mircea" in c.history[-1][1]


def test_a_brother_who_reigns_elsewhere_joins_the_realms(c):
    c.dies(c.ruler("bohemia"))
    assert c.ruler("bohemia") is c.ruler("hungary")
    assert c.overlord["bohemia"] == ("hungary", "union")


def test_when_the_line_fails_a_cousin_or_a_new_house_rises(c):
    houses = set()
    for _ in range(12):
        unrest = c.provinces["kruja"].unrest
        old = c.ruler("thopia")
        c.dies(old)
        new = c.ruler("thopia")
        assert new is not old and new.dynasty
        if new.dynasty != old.dynasty:
            assert c.provinces["kruja"].unrest >= unrest + 4
        houses.add(new.dynasty == old.dynasty)
    assert houses == {True, False}


def test_republics_elect_and_the_church_chooses(c):
    doge = c.ruler("venice")
    c.dies(doge)
    assert c.ruler("venice") is not doge and c.age(c.ruler("venice")) >= 50
    pope = c.ruler("papal")
    c.dies(pope)
    assert c.ruler("papal").dynasty is None
    name, number = c.ruler("papal").name.split()
    assert number in ("VIII", "XIII", "VI", "V", "IV", "III", "XI", "VII", "VIII")
    council = c.ruler("ragusa")
    for _ in range(600):
        c.people_month()
    assert c.ruler("ragusa") is council and council.alive


def test_children_are_born_and_people_die(c):
    alive = sum(p.alive for p in c.people.values())
    born = len(c.people)
    for _ in range(120):
        c.date = c.date.next()
        c.people_month()
    assert len(c.people) > born + 20                         # children (and spouses) in ten years
    assert sum(not p.alive for p in c.people.values()) > 5
    assert any(p.spouse and c.people[p.spouse].court == p.court for p in c.people.values() if p.alive)
    assert all(c.ruler(t) is not None and c.ruler(t).alive for t in c.realms)
    assert alive > 0


def test_a_marriage_between_houses(c):
    heir = c.heir_of("wallachia")
    bride = c.add_person("Jelena", 1388, True, "serbia", "Lazarević")
    ok, _ = c.marriage_answer(heir.id, bride.id)
    assert ok
    before = c.opinion("wallachia", "serbia")
    c.propose_marriage(heir.id, bride.id)
    assert heir.spouse == bride.id and bride.court == "wallachia"
    assert c.opinion("wallachia", "serbia") > before
    sultan_kin = c.add_person("Hatice", 1388, True, "ott_rum", "Osman")
    groom = c.add_person("Radu", 1384, False, "wallachia", "Basarab")
    assert not c.marriage_answer(groom.id, sultan_kin.id)[0]  # not across faiths


def test_every_army_has_a_captain_and_good_ones_fight_better(c):
    assert all(c.commander_of(a) is not None for a in c.armies)
    army = c.armies_of("wallachia")[0]
    cmd = c.commander_of(army)
    cmd.martial, cmd.traits = 10, []
    strong = c.strength(army, "plains", False)
    cmd.martial = 1
    assert c.strength(army, "plains", False) < strong


def test_a_good_steward_raises_more(c):
    ruler = c.ruler("wallachia")
    ruler.stewardship, ruler.traits = 9, []
    rich = c.budget("wallachia").tax
    ruler.stewardship = 2
    assert c.budget("wallachia").tax < rich


def test_people_are_saved(world, c):
    provmap, realms, relations = world
    for _ in range(12):
        c.end_month()
    again = Campaign.from_dict(json.loads(json.dumps(c.to_dict())), provmap, realms, relations)
    assert again.ruler("wallachia").name == c.ruler("wallachia").name
    assert len(again.people) == len(c.people)
    assert [a.commander for a in again.armies] == [a.commander for a in c.armies]
    assert again.date == Date(1403, 9)
