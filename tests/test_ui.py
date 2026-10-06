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
    assert game.besieging(pajura)  # Sibiu has an Outlaw garrison

    click(app, (10, 10), button=3)
    assert app.scene.selected_army is None


def press(app, key):
    app.scene.handle(pygame.event.Event(pygame.KEYDOWN, key=key))
    app.scene.draw(app.screen)


def close_reports(app):
    """Read every pop-up; envoys are politely sent away."""
    while app.scene.reports:
        is_offer = type(app.scene.reports[0]).__name__ == "Proposal"
        press(app, pygame.K_n if is_offer else pygame.K_RETURN)


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


def test_manage_a_province_build_and_recruit(app):
    app.start_campaign("voievodat", seed=7)
    app.scene.draw(app.screen)
    game = app.scene.game
    craiova = game.provinces["craiova"]
    click(app, (craiova.x, craiova.y - 40))
    assert app.scene.panel.manage_rect is not None
    click(app, app.scene.panel.manage_rect.center)
    dialog = app.scene.dialog
    assert dialog is not None and dialog.pid == "craiova"

    from legendele.ui.province_dialog import BOX

    def rows(right):
        return [r for r, _ in dialog.actions if (r.x > BOX.centerx) == right and r.height > 24]

    click(app, rows(right=False)[0].center)  # the first building on offer: Farmsteads
    assert craiova.construction == {"building": "farm", "turns_left": 1}
    click(app, rows(right=True)[0].center)  # the first regiment on offer
    assert len(craiova.recruits) == 1
    gold = game.treasury["voievodat"].gold
    training = [r for r, _ in dialog.actions if r.height == 24]
    click(app, training[0].center)  # cancel it again
    assert not craiova.recruits and game.treasury["voievodat"].gold > gold
    press(app, pygame.K_ESCAPE)
    assert app.scene.dialog is None


def test_m_key_opens_only_our_own_provinces(app):
    app.start_campaign("iele", seed=8)
    app.scene.selected_province = "retezat"
    press(app, pygame.K_m)
    assert app.scene.dialog is None
    app.scene.selected_province = "maramures"
    press(app, pygame.K_m)
    assert app.scene.dialog is not None


def test_merge_button(app):
    app.start_campaign("voievodat", seed=9)
    game = app.scene.game
    vlad = next(a for a in game.armies_of("voievodat") if a.province == "targoviste")
    radu = next(a for a in game.armies_of("voievodat") if a.province == "craiova")
    radu.province = "targoviste"
    app.scene.selected_army = vlad.id
    app.scene.draw(app.screen)
    click(app, app.scene.panel.merge_rect.center)
    assert radu.id not in game.armies


def test_winter_map_draws(app):
    app.start_campaign("strigoi", seed=10)
    app.scene.game.round = 3
    app.scene.draw(app.screen)


def test_abduct_button_and_report(app):
    app.start_campaign("zmei", seed=4)
    game = app.scene.game
    army = game.add_army("zmei", "arges", "Cinderjaw", ["pui_de_zmeu"])
    app.scene.selected_army = army.id
    app.scene.draw(app.screen)
    assert app.scene.panel.abduct_rect is not None
    click(app, app.scene.panel.abduct_rect.center)
    assert app.scene.reports and type(app.scene.reports[0]).__name__ == "Abduction"
    close_reports(app)
    if army.id in game.armies:
        app.scene.selected_army = army.id
        app.scene.draw(app.screen)
        assert app.scene.panel.abduct_rect is None  # on cooldown


def test_hidden_fae_are_not_drawn(app):
    app.start_campaign("voievodat", seed=1)
    app.scene.draw(app.screen)
    game = app.scene.game
    drawn = {aid for _, aid in app.scene.map.army_rects}
    fae = next(a for a in game.armies_of("iele") if a.province == "maramures")
    assert fae.id not in drawn
    assert all(aid in drawn for aid in (a.id for a in game.armies_of("voievodat")))


def test_rebellion_shows_a_report_and_order_in_the_panel(app):
    app.start_campaign("voievodat", seed=1)
    game = app.scene.game
    p = game.provinces["arges"]
    p.captured_round, p.garrison = 0, []
    rebels = game.add_army("haiduci", "arges", "Pintea", ["haiduc_brigands"])
    from legendele.game import Rebellion
    app.scene._report([Rebellion("arges", "voievodat")])
    app.scene.draw(app.screen)
    close_reports(app)
    app.scene.selected_province = "arges"
    app.scene.draw(app.screen)
    assert rebels.id in game.armies


def start_peaceful(app, real_data, faction, seed):
    """Start a campaign with the shipped data (the other UI tests use the total-war variant)."""
    shared = app.data
    app.data = real_data
    try:
        app.start_campaign(faction, seed=seed)
    finally:
        app.data = shared


def test_diplomacy_window(app, real_data):
    start_peaceful(app, real_data, "voievodat", 3)
    game = app.scene.game
    press(app, pygame.K_d)
    dialog = app.scene.dialog
    assert dialog is not None
    labels = [label for _, label, _ in dialog.actions]
    assert labels.count("Declare war") == 3 and labels.count("Propose alliance") == 3
    war_on_zmei = [r for r, label, _ in dialog.actions if label == "Declare war"][0]  # rows follow factions.json
    click(app, war_on_zmei.center)
    assert game.at_war("voievodat", "zmei")
    assert any(label.startswith("Peace + ") for _, label, _ in app.scene.dialog.actions)
    press(app, pygame.K_ESCAPE)
    assert app.scene.dialog is None
    assert app.scene.reports and type(app.scene.reports[0]).__name__ == "DiplomacyChange"


def test_envoys_wait_for_an_answer(app, real_data):
    from legendele.game import diplomacy
    from legendele.ui.reports import ACCEPT_RECT
    start_peaceful(app, real_data, "voievodat", 3)
    game = app.scene.game
    game.declare_war("zmei", "voievodat")
    game.propose("peace", "zmei", "voievodat")
    app.scene._report(game.events)
    while type(app.scene.reports[0]).__name__ != "Proposal":
        app.scene.reports.pop(0)
    press(app, pygame.K_RETURN)  # Enter does not dismiss envoys
    assert type(app.scene.reports[0]).__name__ == "Proposal"
    click(app, ACCEPT_RECT.center)
    assert diplomacy.relation(game, "voievodat", "zmei") == "peace" and not game.proposals
