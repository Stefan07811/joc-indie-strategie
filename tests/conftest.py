import copy
import dataclasses
import os

import pytest

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

from legendele.game import Game, GameData


@pytest.fixture(scope="session")
def real_data():
    """The game data exactly as shipped (factions start mostly at peace)."""
    return GameData.load()


@pytest.fixture(scope="session")
def data(real_data):
    """Most rule tests predate diplomacy: there every faction starts at war with every other."""
    d = GameData(**{f.name: copy.deepcopy(getattr(real_data, f.name)) for f in dataclasses.fields(GameData)})
    d.map["diplomacy"]["start"] = "war"
    return d


@pytest.fixture
def game(data):
    return Game.new(data, "voievodat")


@pytest.fixture(autouse=True)
def player_home(tmp_path, monkeypatch):
    """Settings and saves go to a temporary folder, never to the real ~/.legendele."""
    monkeypatch.setenv("LEGENDELE_HOME", str(tmp_path / "home"))
    return tmp_path / "home"
