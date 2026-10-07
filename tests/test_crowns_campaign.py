"""The campaign's month: money, buildings, troops, people, and saving it all."""

import json

import pytest

from crowns.game import rules
from crowns.game.calendar import Date
from crowns.game.campaign import Campaign
from crowns.game.realms import load
from crowns.provinces import ProvinceMap


@pytest.fixture(scope="module")
def world():
    return ProvinceMap(), *load()


@pytest.fixture
def campaign(world):
    provmap, realms, relations = world
    return Campaign(provmap, realms, relations, player="wallachia")


def test_every_realm_starts_solvent_with_an_army(campaign):
    for tag in campaign.realms:
        b = campaign.budget(tag)
        assert b.income > 0 and b.balance >= 0, tag
        assert campaign.armies_of(tag), tag
        assert campaign.realms[tag].treasury > 0 and campaign.realms[tag].manpower > 0
    # the great powers are richer than the small lords
    assert campaign.budget("hungary").income > 5 * campaign.budget("wallachia").income
    assert campaign.budget("wallachia").income > campaign.budget("kastrioti").income
    # Timur's host stands in western Anatolia, the largest army on the map
    timur = campaign.armies_of("timurids")[0]
    assert campaign.provmap.at(timur.x, timur.y).id == "kutahya"
    assert timur.men == max(a.men for a in campaign.armies)


def test_armies_are_raised_in_their_realms_tradition(campaign):
    assert {r.type.tradition for r in campaign.armies_of("wallachia")[0].regiments} == {"vlach"}
    assert {r.type.tradition for r in campaign.armies_of("ott_rum")[0].regiments} == {"ottoman"}
    assert {r.type.tradition for r in campaign.armies_of("horde")[0].regiments} == {"steppe"}
    assert all(u.tradition == "vlach" for u in campaign.units_for("moldavia"))


def test_tribute_flows_to_the_overlord(campaign):
    moldavia = campaign.budget("moldavia")
    assert moldavia.tribute_out > 0                                       # Moldavia is Poland's vassal
    assert campaign.budget("poland").tribute_in >= moldavia.tribute_out - 1e-6
    assert campaign.budget("wallachia").tribute_out == 0


def test_a_month_pays_taxes_and_troops(campaign):
    before = campaign.realms["wallachia"].treasury
    balance = campaign.budget("wallachia").balance
    campaign.end_month()
    assert campaign.date == Date(1402, 10)
    assert campaign.realms["wallachia"].treasury == pytest.approx(before + balance, rel=1e-6)


def test_building_takes_money_and_months(campaign):
    pid = "targoviste"
    p = campaign.provinces[pid]
    cost = rules.BUILDINGS["market"].costs[0]
    campaign.realms["wallachia"].treasury = 10_000
    assert campaign.build(pid, "market")
    assert campaign.realms["wallachia"].treasury == 10_000 - cost
    assert not campaign.can_build(pid, "fields")[0]        # one work at a time
    income = campaign.income(pid)[2]
    for _ in range(rules.BUILDINGS["market"].months[0]):
        campaign.end_month()
    assert p.buildings == {"market": 1} and p.works is None
    assert campaign.income(pid)[2] > income
    assert any("Market" in m for m in campaign.messages)


def test_what_cannot_be_built(campaign):
    campaign.realms["wallachia"].treasury = 100_000
    assert campaign.can_build("targoviste", "harbour") == (False, "Needs a coast.")
    assert campaign.can_build("targoviste", "mine")[0] is False          # wax, not metal
    assert campaign.can_build("arges", "mine")[0] is True                 # the salt of Ocnele Mari
    campaign.realms["wallachia"].treasury = 10
    assert campaign.can_build("arges", "mine")[1].startswith("Costs")
    # a village holds only so many buildings
    p = campaign.provinces["teleorman"]
    p.buildings = {"fields": 1, "church": 1, "castle": 1}
    campaign.realms["wallachia"].treasury = 100_000
    assert campaign.can_build("teleorman", "walls")[0] is False
    assert campaign.can_build("teleorman", "fields")[0] is True          # improving costs no room


def test_mosques_in_muslim_realms(campaign):
    assert campaign.building_name("edirne", "church", 1) == "Mosque"
    assert campaign.building_name("targoviste", "church", 2) == "Monastery"


def test_recruits_join_the_army_next_month(campaign):
    w = campaign.realms["wallachia"]
    w.treasury = 50_000
    army = campaign.army_at_town("wallachia", "targoviste")
    assert army is not None
    men = army.men
    assert campaign.can_recruit("targoviste", "boyars")[0] is False      # boyar horse needs a keep
    assert campaign.recruit("targoviste", "calarasi")
    assert not campaign.recruit("targoviste", "calarasi")                 # one muster a month without a castle
    assert not campaign.can_recruit("targoviste", "knights")[0]           # not a Wallachian troop
    manpower = w.manpower
    campaign.end_month()
    assert army.men == men + rules.UNITS["calarasi"].men
    assert w.manpower > manpower - 1                                       # the pool refills slowly


def test_an_empty_treasury_makes_soldiers_desert(campaign):
    campaign.realms["wallachia"].treasury = -10_000
    men = sum(a.men for a in campaign.armies_of("wallachia"))
    campaign.end_month()
    assert sum(a.men for a in campaign.armies_of("wallachia")) < men
    assert any("desert" in m for m in campaign.messages)


def test_the_people_grow_in_peace(campaign):
    pop = campaign.provinces["targoviste"].population
    for _ in range(12):
        campaign.end_month()
    assert pop < campaign.provinces["targoviste"].population < pop * 1.02


def test_unrest_where_faith_differs(campaign):
    # the Orthodox Bulgarians under the Ottoman emir grumble; the Turks of Edirne do not
    assert campaign.unrest_target("tarnovo") > campaign.unrest_target("edirne")


def test_saving_and_loading(world, campaign):
    provmap, realms, relations = world
    campaign.build("targoviste", "fields")
    campaign.recruit("targoviste", "great_host")
    nav_army = campaign.armies_of("wallachia")[0]
    from crowns.game.navigation import Route
    nav_army.route = Route([(nav_army.x, nav_army.y), (nav_army.x + 20, nav_army.y + 5)], [0, 30])
    campaign.end_month()
    data = json.loads(json.dumps(campaign.to_dict()))
    again = Campaign.from_dict(data, provmap, realms, relations)
    assert again.date == campaign.date and again.player == "wallachia"
    assert again.provinces["targoviste"] == campaign.provinces["targoviste"]
    assert again.realms["wallachia"] == campaign.realms["wallachia"]
    assert [a.men for a in again.armies] == [a.men for a in campaign.armies]
    for a in (campaign, again):
        a.end_month()
    assert again.realms["wallachia"].treasury == pytest.approx(campaign.realms["wallachia"].treasury)
    assert again.rng.random() == campaign.rng.random()


def test_splitting_and_joining_armies(campaign):
    army = campaign.armies_of("wallachia")[0]
    men, count = army.men, len(campaign.armies)
    new = campaign.split_army(army)
    assert new is not None and army.men + new.men == men and len(campaign.armies) == count + 1
    assert campaign.merge_armies(army) == 1
    assert army.men == men and len(campaign.armies) == count
    lone = campaign.new_army("wallachia", 100, 100, [army.regiments[0]])
    assert campaign.split_army(lone) is None
