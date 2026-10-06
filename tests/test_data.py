import copy

import pytest

from legendele.game import DataError, GameData


def test_bundled_data_is_valid(data):
    data.validate()


def test_six_playable_factions_with_five_units_each(data):
    playable = [f for f, d in data.factions.items() if d["playable"]]
    assert sorted(playable) == ["iele", "outlaws", "solomonari", "strigoi", "voievodat", "zmei"]
    for fid in playable:
        assert sum(u["faction"] == fid and u["tier"] > 0 for u in data.units.values()) == 5
        quests = [q for q in data.quests.values() if q["faction"] == fid]
        assert len(quests) == 2 and all(data.units[q["hero"]]["tier"] == 0 for q in quests)  # heroes of legend


@pytest.mark.parametrize("breakage, message", [
    (lambda d: d.map["provinces"][0].update(terrain="lava"), "unknown terrain"),
    (lambda d: d.map["provinces"][0]["neighbors"].append("atlantis"), "unknown neighbour"),
    (lambda d: d.map["start_armies"][0]["regiments"].append("dragon"), "unknown unit"),
    (lambda d: d.factions["zmei"].update(capital="atlantis"), "unknown capital"),
])
def test_validation_catches_mistakes(data, breakage, message):
    broken = GameData(copy.deepcopy(data.factions), copy.deepcopy(data.units), copy.deepcopy(data.map), copy.deepcopy(data.buildings), copy.deepcopy(data.abilities))
    breakage(broken)
    with pytest.raises(DataError, match=message):
        broken.validate()
