"""Drives the real pygame screens without a display (SDL dummy driver)."""

import os

import pytest

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
pygame = pytest.importorskip("pygame")

from legendele.ui.app import App, Campaign, FactionSelect  # noqa: E402


def click(app, pos, button=1):
    app.scene.handle(pygame.event.Event(pygame.MOUSEBUTTONDOWN, pos=pos, button=button))
    app.scene.draw(app.screen)


def on_map(app, x, y):
    """Bring a world point into view; returns where it is on the screen."""
    app.scene.map.center_on(x, y)
    app.scene.draw(app.screen)
    return app.scene.map.to_screen((x, y))


def banner(app, army_id):
    """Where an army's standard is on the screen (brought into view)."""
    app.scene.draw(app.screen)
    rect = next(r for r, aid in app.scene.map.army_rects if aid == army_id)
    return on_map(app, *rect.center)


@pytest.fixture(scope="module")
def app(data):
    app = App(data)
    app.settings["battles"] = "auto"
    app.settings["tutorial"] = False  # these tests are about the campaign screens
    return app


def test_choose_faction_then_march(app):
    app.scene = FactionSelect(app)
    app.scene.draw(app.screen)
    zmei_card = next(rect for rect, fid in app.scene.cards if fid == "zmei")
    click(app, zmei_card.center)
    assert isinstance(app.scene, Campaign) and app.scene.game.player == "zmei"

    game = app.scene.game
    pajura = next(a for a in game.armies_of("zmei") if a.province == "retezat")
    click(app, banner(app, pajura.id))
    assert app.scene.selected_army == pajura.id

    sibiu = game.provinces["sibiu"]
    click(app, on_map(app, sibiu.x, sibiu.y - 30))
    assert pajura.province == "sibiu"
    assert pajura.moves_left == 0  # marching into foreign land ends the turn's march
    assert game.besieging(pajura)  # Sibiu has an Outlaw garrison

    click(app, (10, 10), button=3)
    assert app.scene.selected_army is None


def press(app, key):
    app.scene.handle(pygame.event.Event(pygame.KEYDOWN, key=key))
    app.scene.draw(app.screen)


ANSWER = {"Proposal": pygame.K_n, "Tale": pygame.K_1}  # envoys are sent away, tales get the first answer


def close_reports(app):
    """Read every pop-up, then the season's news."""
    while app.scene.reports:
        press(app, ANSWER.get(type(app.scene.reports[0]).__name__, pygame.K_RETURN))
    if app.scene.summary:
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
    click(app, banner(app, vlad.id))
    retezat = game.provinces["retezat"]
    app.scene.hovered = "retezat"
    app.scene.draw(app.screen)  # with the battle forecast in the panel
    click(app, on_map(app, retezat.x + 40, retezat.y - 40))
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
    for p in list(game.provinces.values())[:game.victory_rules["conquest_provinces"]]:
        p.owner = "zmei"
    game._check_end()
    app.scene._report(game.events)
    close_reports(app)
    assert game.over
    ending = app.scene.ending
    assert ending is not None  # the chronicle of the war opens by itself
    press(app, pygame.K_ESCAPE)  # ...and closes to look at the map
    assert app.scene.ending is None
    click(app, app.scene.chronicle_rect.center)  # it can be opened again
    assert app.scene.ending is not None
    press(app, pygame.K_ESCAPE)
    click(app, app.scene.menu_rect.center)
    assert not isinstance(app.scene, Campaign)


def test_cannot_move_enemy_armies(app):
    app.start_campaign("voievodat")
    app.scene.draw(app.screen)
    game = app.scene.game
    enemy = next(a for a in game.armies_of("strigoi") if a.province == "black_marsh")
    click(app, banner(app, enemy.id))
    buzau = game.provinces["buzau"]
    click(app, on_map(app, buzau.x, buzau.y - 30))
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
    click(app, on_map(app, craiova.x, craiova.y - 40))
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


def test_the_map_scrolls_and_the_minimap_jumps(app):
    app.start_campaign("voievodat", seed=1)
    view = app.scene.map
    capital = app.scene.game.provinces["targoviste"]
    assert view.view().collidepoint(capital.x, capital.y)  # the campaign opens on our capital
    view.scroll(-10000, -10000)
    assert view.camera == [0.0, 0.0]
    view.scroll(10000, 10000)
    assert view.view().bottomright == view.size
    press(app, pygame.K_HOME)
    assert view.view().collidepoint(capital.x, capital.y)

    app.scene.handle(pygame.event.Event(pygame.MOUSEBUTTONDOWN, pos=view.minimap_rect.topleft, button=1))
    app.scene.handle(pygame.event.Event(pygame.MOUSEBUTTONUP, pos=view.minimap_rect.topleft, button=1))
    assert view.camera == [0.0, 0.0]
    assert app.scene.selected_province is None  # a click on the minimap is not a click on the map

    sea = next(f for f in app.data.map["foreign"] if f["terrain"] == "sea")
    assert view.province_at(on_map(app, sea["x"], sea["y"])) is None


def test_tooltips_explain_the_panel(app):
    from legendele.ui import theme
    app.start_campaign("voievodat", seed=3)
    theme.clear_tips()
    app.scene.select_next_army()
    app.scene.draw(app.screen)
    panel = theme.PANEL_RECT
    titles = {lines[0] for rect, lines in theme._tips if panel.contains(rect)}
    assert {"Gold", "Food", "Conquest victory", "Legendary victory", "Levy Spearmen"} <= titles
    rect, lines = next((r, l) for r, l in theme._tips if l[0] == "Gold")
    assert theme.draw_tip(app.screen, rect.center, now=float("inf")) is not None


def test_the_season_news_leads_to_the_place(app):
    app.start_campaign("voievodat", seed=4)
    app.scene.end_turn()
    while app.scene.reports:
        press(app, ANSWER.get(type(app.scene.reports[0]).__name__, pygame.K_RETURN))
    summary = app.scene.summary
    assert summary is not None and summary.rows
    app.scene.draw(app.screen)
    rect, place = next((r, p) for r, p in summary.row_rects if p)
    click(app, rect.center)
    assert app.scene.summary is None and app.scene.selected_province == place
    p = app.scene.game.provinces[place]
    assert app.scene.map.view().collidepoint(p.x, p.y)

    app.settings["turn_summary"] = False
    app.scene.end_turn()
    assert app.scene.summary is None
    app.settings["turn_summary"] = True


def test_the_advisor_waits_for_each_lesson(app):
    from legendele.ui.tutorial import STEPS
    app.settings["tutorial"] = True
    app.start_campaign("voievodat", seed=8)
    c = app.scene
    tutorial = c.tutorial
    assert tutorial is not None and tutorial.index == 0
    c.draw(app.screen)
    click(app, tutorial.next_rect.center)
    assert tutorial.index == 1
    press(app, pygame.K_TAB)  # select an army: the lesson is learnt
    assert tutorial.index == 2
    army = c.game.armies[c.selected_army]
    target = next(iter(c.game.reachable(army)))
    c.game.move_army(army.id, target)
    c.draw(app.screen)
    assert tutorial.index == 3
    click(app, tutorial.skip_rect.center)
    assert c.tutorial is None and app.settings["tutorial"] is False
    assert len(STEPS) > 5


def test_a_tale_is_answered_in_its_window(app):
    from legendele.game import Tale
    from legendele.ui.reports import tale_choice_rects
    app.start_campaign("voievodat", seed=9)
    c = app.scene
    tale = Tale("harvest", "voievodat", "craiova")
    c.game.pending_events.append(tale)
    c._report([tale])
    gold = c.game.treasury["voievodat"].gold
    press(app, pygame.K_RETURN)  # a tale waits for an answer
    assert c.reports and c.reports[0] is tale
    click(app, tale_choice_rects(2)[1].center)  # sell the surplus
    assert not c.reports and c.game.treasury["voievodat"].gold == gold + 90
