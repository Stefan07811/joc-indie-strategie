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
    assert pajura.moves_left == 0  # marching into foreign land ends the turn's march
    assert game.besieging(pajura)  # Sibiu has a Haiduc garrison

    click(app, (10, 10), button=3)
    assert app.scene.selected_army is None


def press(app, key):
    app.scene.handle(pygame.event.Event(pygame.KEYDOWN, key=key))
    app.scene.draw(app.screen)


def close_reports(app):
    while app.scene.reports:
        press(app, pygame.K_RETURN)


def test_end_turn_button_and_key(app):
    app.start_campaign("iele", seed=1)
    app.scene.draw(app.screen)
    click(app, app.scene.panel.end_turn_rect.center)
    assert app.scene.game.date == "Summer 1400"
    close_reports(app)
    press(app, pygame.K_RETURN)
    assert app.scene.game.date == "Autumn 1400"


def test_attacking_shows_a_battle_report(app):
    app.start_campaign("voievodat", seed=2)
    app.scene.draw(app.screen)
    game = app.scene.game
    vlad = next(a for a in game.armies_of("voievodat") if a.province == "targoviste")
    click(app, next(r for r, aid in app.scene.map.army_rects if aid == vlad.id).center)
    marsh = game.provinces["black_marsh"]
    app.scene.hovered = "black_marsh"
    app.scene.draw(app.screen)  # with the battle forecast in the panel
    click(app, (marsh.x + 40, marsh.y - 40))
    assert app.scene.reports and type(app.scene.reports[0]).__name__ == "Battle"
    date = game.date
    press(app, pygame.K_RETURN)  # Enter closes the report instead of ending the turn
    assert game.date == date


def test_siege_then_assault_button(app):
    app.start_campaign("voievodat", seed=4)
    app.scene.draw(app.screen)
    game = app.scene.game
    for fid in game.ai:
        game.ai[fid].take_turn = lambda game: None
    vlad = next(a for a in game.armies_of("voievodat") if a.province == "targoviste")
    game.move_army(vlad.id, "buzau")
    app.scene.end_turn()
    close_reports(app)
    app.scene.selected_army = vlad.id
    app.scene.draw(app.screen)
    assert app.scene.panel.assault_rect is not None
    click(app, app.scene.panel.assault_rect.center)
    assert app.scene.reports and app.scene.reports[0].result.kind == "assault"


def test_game_over_offers_the_main_menu(app):
    app.start_campaign("zmei", seed=5)
    game = app.scene.game
    for p in game.provinces.values():
        if p.owner is None:
            p.garrison = []
    game.provinces["heart"].owner = "zmei"
    for p in list(game.provinces.values())[:14]:
        p.owner = "zmei"
    game._check_end()
    app.scene._report(game.events)
    close_reports(app)
    assert game.over
    click(app, app.scene.menu_rect.center)
    assert not isinstance(app.scene, Campaign)


def test_cannot_move_enemy_armies(app):
    app.start_campaign("voievodat")
    app.scene.draw(app.screen)
    game = app.scene.game
    enemy = next(a for a in game.armies_of("strigoi") if a.province == "black_marsh")
    click(app, next(r for r, aid in app.scene.map.army_rects if aid == enemy.id).center)
    buzau = game.provinces["buzau"]
    click(app, (buzau.x, buzau.y - 30))
    assert enemy.province == "black_marsh"


def test_every_faction_plays_a_few_turns(app):
    for fid in ("voievodat", "zmei", "iele", "strigoi"):
        app.start_campaign(fid, seed=6)
        for _ in range(6):
            app.scene.select_next_army()
            app.scene.draw(app.screen)
            press(app, pygame.K_RETURN)
            close_reports(app)
