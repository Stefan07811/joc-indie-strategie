"""Drives the real pygame screens without a display (SDL dummy driver)."""

import os

import pytest

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
pygame = pytest.importorskip("pygame")

from legendele.ui.app import App, Campaign  # noqa: E402


def click(app, pos, button=1):
    app.scene.handle(pygame.event.Event(pygame.MOUSEBUTTONDOWN, pos=pos, button=button))
    app.scene.draw(app.screen)


@pytest.fixture(scope="module")
def app(data):
    return App(data)


def test_choose_faction_then_march(app):
    app.scene = app.scene.__class__(app)  # fresh faction screen
    app.scene.draw(app.screen)
    zmei_card = next(rect for rect, fid in app.scene.cards if fid == "zmei")
    click(app, zmei_card.center)
    assert isinstance(app.scene, Campaign) and app.scene.game.player == "zmei"

    game = app.scene.game
    pajura = next(a for a in game.armies_of("zmei") if a.province == "retezat")
    banner = next(rect for rect, aid in app.scene.map.army_rects if aid == pajura.id)
    click(app, banner.center)
    assert app.scene.selected_army == pajura.id

    sibiu = game.provinces["sibiu"]
    click(app, (sibiu.x, sibiu.y - 30))
    assert pajura.province == "sibiu"
    assert pajura.moves_left == 2  # hills cost 2 for the Zmei

    click(app, (10, 10), button=3)
    assert app.scene.selected_army is None


def test_end_turn_button_and_key(app):
    app.start_campaign("iele")
    click(app, app.scene.panel.end_turn_rect.center)
    assert app.scene.game.date == "Summer 1400"
    app.scene.handle(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_RETURN))
    assert app.scene.game.date == "Autumn 1400"


def test_cannot_move_enemy_armies(app):
    app.start_campaign("voievodat")
    app.scene.draw(app.screen)
    game = app.scene.game
    enemy = next(a for a in game.armies_of("strigoi") if a.province == "black_marsh")
    click(app, next(r for r, aid in app.scene.map.army_rects if aid == enemy.id).center)
    buzau = game.provinces["buzau"]
    click(app, (buzau.x, buzau.y - 30))
    assert enemy.province == "black_marsh"


def test_every_faction_screen_draws(app):
    for fid in ("voievodat", "zmei", "iele", "strigoi"):
        app.start_campaign(fid)
        app.scene.select_next_army()
        app.scene.draw(app.screen)
