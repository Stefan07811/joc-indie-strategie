"""Campaigns saved by earlier versions of the game still load and play on.

tests/saves/ holds one save made by each milestone since the map took its real geography (made with
that version's own code, 14 seasons into an AI war). If a change breaks them, either make the loading
code fill in what is missing, or (when old saves cannot be kept) say so in the README.
"""

import shutil
from pathlib import Path

import pytest

from legendele import profile
from legendele.game.save import load_game, summary, read_save

SAVES = sorted((Path(__file__).parent / "saves").glob("*.json"))


@pytest.mark.parametrize("path", SAVES, ids=[p.stem for p in SAVES])
def test_old_save_plays_on(real_data, path):
    game = load_game(real_data, path)
    assert set(game.turn_order) <= set(game.factions) and game.player in game.factions
    assert summary(read_save(path))["player"] == game.player
    for _ in range(4):
        if game.over:
            break
        game.end_turn()


@pytest.mark.parametrize("path", SAVES, ids=[p.stem for p in SAVES])
def test_old_save_in_the_game_screens(real_data, path, player_home):
    from legendele.ui.app import App, Campaign
    profile.save_path("slot1").parent.mkdir(parents=True, exist_ok=True)
    shutil.copy(path, profile.save_path("slot1"))
    app = App(real_data)
    app.settings["battles"] = "auto"
    app.load_slot("slot1")
    c = app.scene
    assert isinstance(c, Campaign)
    for opener in (c.open_diplomacy, c.open_traditions, c.open_legends, c.open_foreign, None):
        c.dialog = None
        if opener:
            opener()
        app.present(c.draw)
    c.dialog = None
    if not c.game.over:
        c.select_next_army()
        app.present(c.draw)
        c.end_turn()
        c.summary = None
        app.present(c.draw)
