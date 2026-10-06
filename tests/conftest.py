import copy

import pytest

from legendele.game import Game, GameData


@pytest.fixture(scope="session")
def real_data():
    """The game data exactly as shipped (factions start mostly at peace)."""
    return GameData.load()


@pytest.fixture(scope="session")
def data(real_data):
    """Most rule tests predate diplomacy: there every faction starts at war with every other."""
    d = GameData(*(copy.deepcopy(getattr(real_data, f)) for f in
                   ("factions", "units", "map", "buildings", "abilities")))
    d.map["diplomacy"]["start"] = "war"
    return d


@pytest.fixture
def game(data):
    return Game.new(data, "voievodat")
