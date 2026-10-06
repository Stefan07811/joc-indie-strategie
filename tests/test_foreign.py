"""The powers beyond the border: raids, tribute and mercenaries."""

import pytest

from legendele.game import Game, Plundered, Raid, foreign
from legendele.game.save import from_dict, to_dict


@pytest.fixture
def quiet(data):
    game = Game.new(data, "voievodat", seed=3)
    for ai in game.ai.values():
        ai.take_turn = lambda game: None
    return game


def test_the_powers_and_their_borders(quiet):
    assert set(foreign.powers(quiet)) == {"hungary", "poland", "ottomans", "tatars"}
    assert "craiova" in foreign.borders(quiet, "ottomans")
    assert "satmar" in foreign.borders(quiet, "hungary")
    assert "ottomans" in foreign.neighbours_of(quiet, "voievodat")
    assert "poland" not in foreign.neighbours_of(quiet, "voievodat")


def test_a_raid_plunders_and_goes_home(quiet):
    game = quiet
    p = game.provinces["craiova"]
    p.garrison = []
    for a in game.armies_in("craiova"):
        del game.armies[a.id]
    p.buildings = ["farm"]
    gold = game.treasury["voievodat"].gold
    army = foreign.start_raid(game, "ottomans")
    assert any(isinstance(e, Raid) for e in game.events)
    assert army.faction == "ottomans"
    plundered = [e for e in game.events if isinstance(e, Plundered)]
    if plundered:
        assert game.treasury["voievodat"].gold < gold and p.owner == "voievodat"  # looted, not taken
        assert any(m[0] == "Plundered" for m in p.mods)
    for _ in range(foreign.RAID_SEASONS + 2):
        game.end_turn()
    assert army.id not in game.armies  # gone home (or beaten)


def test_tribute_keeps_the_raiders_away_while_it_is_paid(quiet):
    game = quiet
    foreign.start_tribute(game, "voievodat", "ottomans")
    for pid in foreign.borders(game, "ottomans"):
        if game.provinces[pid].owner != "voievodat":
            game.provinces[pid].owner = "voievodat"
    assert foreign.start_raid(game, "ottomans") is None
    gold = game.treasury["voievodat"].gold
    foreign.season(game)
    assert game.treasury["voievodat"].gold == gold - foreign.tribute_cost(game, "ottomans")
    game.treasury["voievodat"].gold = 0
    foreign.season(game)
    assert not foreign.pays(game, "voievodat", "ottomans")  # no gold, no tribute


def test_mercenaries_are_sold_to_neighbours(data):
    game = Game.new(data, "iele", seed=1)
    offers = foreign.mercenaries(game, "iele", "poland")
    assert offers and offers[0][0] == "winged_hussars"
    game.treasury["iele"].gold = 1000
    foreign.hire(game, "iele", "poland", "winged_hussars")
    assert any("winged_hussars" in p.recruits for p in game.provinces_of("iele"))
    assert foreign.mercenaries(game, "iele", "ottomans") == []
    with pytest.raises(ValueError):
        foreign.hire(game, "iele", "ottomans", "janissaries")


def test_raids_and_tribute_are_saved(quiet):
    game = quiet
    foreign.start_tribute(game, "voievodat", "tatars")
    game.raided["hungary"] = {"voievodat": 2}
    army = game.add_army("hungary", "craiova", "Count Paul", ["black_army"])
    game.raids[army.id] = {"victim": "voievodat", "plunders": 1, "seasons": 2}
    loaded = from_dict(game.data, to_dict(game))
    assert loaded.tribute == {"voievodat": ["tatars"]} and loaded.raided == game.raided
    assert loaded.raids == game.raids
