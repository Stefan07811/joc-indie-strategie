"""What the campaign's panels show (worked out without graphics)."""

import pytest

from crowns.game.campaign import Campaign
from crowns.game.realms import load
from crowns.provinces import ProvinceMap
from crowns.ui import model


@pytest.fixture(scope="module")
def world():
    return ProvinceMap(), *load()


@pytest.fixture
def c(world):
    provmap, realms, relations = world
    return Campaign(provmap, realms, relations, player="wallachia")


def test_the_top_bar(c):
    t = model.top_bar(c)
    assert t["realm"] == "Principality of Wallachia" and t["date"] == "September 1402"
    assert t["ruler"].startswith("Voivode Mircea the Elder, aged 47")
    assert t["balance"].startswith("+")


def test_the_budget_adds_up(c):
    lines, balance = model.budget_lines(c, "wallachia")
    assert sum(amount for _, amount in lines) == pytest.approx(balance)
    names = [n for n, _ in model.budget_lines(c, "mamluks")[0]]
    assert "Lands beyond the map" in names


def test_a_province_of_ours(c):
    v = model.province_view(c, "targoviste")
    assert v["name"] == "Târgoviște" and v["mine"] and v["owner"] == "Principality of Wallachia"
    assert any("people" in line for line in v["lines"])
    kinds = {row["kind"]: row for row in v["build"]}
    assert kinds["harbour"]["ok"] is False and kinds["harbour"]["why"] == "Needs a coast."
    assert kinds["fields"]["ok"] is True and "300 ducats" in kinds["fields"]["label"]
    units = {row["unit"]: row for row in v["recruit"]}
    assert units["calarasi"]["ok"] and not units["boyars"]["ok"]
    c.build("targoviste", "market")
    c.recruit("targoviste", "great_host")
    v = model.province_view(c, "targoviste")
    assert "Building: Market" in v["works"] and "Mustering: The Great Host" in v["works"]


def test_a_province_of_others_offers_no_building(c):
    v = model.province_view(c, "edirne")
    assert not v["mine"] and not v["build"] and not v["recruit"]
    c.provinces["edirne"].siege = {"by": "wallachia", "progress": 0.5, "months": 3}
    assert model.province_view(c, "edirne")["siege"].startswith("Besieged by Wallachia: 50%")


def test_an_army(c):
    army = c.armies_of("wallachia")[0]
    v = model.army_view(c, army)
    assert v["mine"] and v["men"] == f"{army.men:,} men"
    assert any("The Great Host" in row for row in v["rows"])


def test_a_foreign_realm_and_what_we_can_do(c):
    v = model.realm_view(c, "ott_rum", "wallachia")
    assert v["name"] == "Ottoman Rumelia" and "Süleyman" in v["ruler"]
    wars = [a for a in v["actions"] if a["do"] == "war"]
    assert wars and all(a["ok"] for a in wars)
    assert any("Nikopol" in a["label"] for a in wars)
    v = model.realm_view(c, "poland", "moldavia")
    assert [a["label"] for a in v["actions"] if a["do"] == "war"] == ["War for independence"]


def test_a_war_and_its_peace_offers(c):
    war = c.declare_war("wallachia", "ott_rum", {"kind": "conquest", "province": "nikopol"})
    c.provinces["nikopol"].controller = "wallachia"
    v = model.realm_view(c, "ott_rum", "wallachia")
    assert v["wars"] and v["wars"][0]["name"] == c.war_name(war)
    labels = [o["label"] for o in v["wars"][0]["offers"]]
    assert "Offer a white peace" in labels and "Demand Nikopol" in labels
    assert "At war with you" in v["relation"]


def test_every_realm_can_be_chosen(c):
    tags = model.playable(c)
    assert len(tags) == len(c.realms) and tags[0] in ("byzantium", "horde", "mamluks", "timurids")


def test_the_court(c):
    v = model.court_view(c, "wallachia")
    assert v["ruler"].startswith("Voivode: Mircea the Elder (47)") and "strategist" in v["ruler"]
    assert v["heir"].startswith("Heir: Mihail")
    assert model.court_view(c, "venice")["heir"] == "Heir: chosen by election"
    army = c.armies_of("wallachia")[0]
    assert model.army_view(c, army)["commander"].startswith("Led by ")


def test_marriages_can_be_proposed(c):
    c.add_person("Jelena", 1385, True, "serbia", "Lazarević")
    offers = model.marriage_offers(c, "wallachia", "serbia")
    assert offers and offers[0]["ok"] and "Mihail" in offers[0]["label"] and "Jelena" in offers[0]["label"]
    labels = [a["label"] for a in model.realm_view(c, "serbia", "wallachia")["actions"]]
    assert any(label.startswith("Marry Mihail") for label in labels)
