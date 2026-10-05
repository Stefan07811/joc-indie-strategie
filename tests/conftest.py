import pytest

from legendele.game import Game, GameData


@pytest.fixture(scope="session")
def data():
    return GameData.load()


@pytest.fixture
def game(data):
    return Game.new(data, "voievodat")
