"""Title screen, save/load slots, settings, pause menu and sound."""

import pygame
import pytest

from legendele import profile
from legendele.ui.app import App, Campaign, FactionSelect, event_sound
from legendele.ui.audio import EFFECTS, MODES, synth_effect, synth_music
from legendele.ui.menus import MainMenu, PauseMenu, SettingsScreen, SlotScreen


@pytest.fixture
def app(real_data, player_home):
    app = App(real_data)
    app.settings["battles"] = "auto"
    app.settings["tutorial"] = False
    return app


def click(app, pos):
    app.scene.handle(pygame.event.Event(pygame.MOUSEBUTTONDOWN, pos=pos, button=1))
    app.scene.draw(app.screen)


def press(app, key):
    app.scene.handle(pygame.event.Event(pygame.KEYDOWN, key=key))
    app.scene.draw(app.screen)


def button(scene, label):
    return next(rect for rect, text in scene.buttons if text == label).center


def test_title_screen_without_saves(app):
    assert isinstance(app.scene, MainMenu)
    app.scene.draw(app.screen)
    assert [label for _, label in app.scene.buttons] == ["New Campaign", "Load Game", "Settings", "Quit"]
    click(app, button(app.scene, "New Campaign"))
    assert isinstance(app.scene, FactionSelect)
    click(app, app.scene.back_rect.center)
    assert isinstance(app.scene, MainMenu)
    click(app, button(app.scene, "Quit"))
    assert not app.running


def test_autosave_then_continue(app, player_home):
    app.start_campaign("iele", seed=3)
    app.scene.end_turn()
    assert profile.save_path(profile.AUTOSAVE).exists()
    assert str(profile.save_path(profile.AUTOSAVE)).startswith(str(player_home))
    date = app.scene.game.date
    app.main_menu()
    app.scene.draw(app.screen)
    assert app.scene.buttons[0][1] == "Continue"
    click(app, button(app.scene, "Continue"))
    assert isinstance(app.scene, Campaign) and app.scene.game.date == date and app.scene.game.player == "iele"


def test_pause_menu_save_and_load(app):
    app.start_campaign("zmei", seed=4)
    campaign = app.scene
    press(app, pygame.K_ESCAPE)  # nothing selected: Esc pauses
    assert isinstance(campaign.pause, PauseMenu)
    click(app, button(campaign.pause, "Save Game"))
    assert isinstance(app.scene, SlotScreen) and app.scene.mode == "save"
    click(app, app.scene.rows[1][0].center)  # Slot 2
    assert profile.slot_info("slot2")["player"] == "zmei"
    press(app, pygame.K_ESCAPE)
    assert app.scene is campaign
    click(app, button(campaign.pause, "Resume"))
    assert campaign.pause is None
    campaign.game.end_turn()
    press(app, pygame.K_ESCAPE)
    click(app, button(campaign.pause, "Load Game"))
    slot2 = next(rect for rect, slot in app.scene.rows if slot == "slot2")
    click(app, slot2.center)
    assert isinstance(app.scene, Campaign) and app.scene is not campaign
    assert app.scene.game.date == "Spring 1400"


def test_settings_are_remembered(app):
    app.scene = SettingsScreen(app, back=app.scene)
    app.scene.draw(app.screen)
    click(app, app.scene.controls["music-"].center)
    click(app, app.scene.controls["sound+"].center)
    assert profile.load_settings()["music"] == pytest.approx(0.3)
    assert profile.load_settings()["sound"] == pytest.approx(0.8)
    press(app, pygame.K_ESCAPE)
    assert isinstance(app.scene, MainMenu)


def test_broken_saves_do_not_crash_the_menu(app):
    path = profile.save_path("slot3")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("not a save", encoding="utf-8")
    assert "error" in profile.slot_info("slot3")
    app.scene = SlotScreen(app, "load", back=app.scene)
    app.scene.draw(app.screen)
    click(app, next(rect for rect, slot in app.scene.rows if slot == "slot3").center)
    assert isinstance(app.scene, SlotScreen)


def test_every_sound_and_theme_can_be_made():
    for name in EFFECTS:
        assert len(synth_effect(name)) > 100
    raw = synth_music("zmei", seconds=2.0)
    assert len(raw) == 2 * 2 * 22050  # 16-bit mono
    assert set(MODES) >= {"menu", "voievodat", "zmei", "iele", "strigoi"}


def test_audio_plays_without_crashing(app):
    app.audio.play("battle")
    app.audio.music("menu")
    app.audio.update()


def test_events_make_the_right_sounds(real_data):
    from legendele.game import Battle, DiplomacyChange, Game, Victory
    game = Game.new(real_data, "voievodat", seed=1)
    assert event_sound(game, [Victory("voievodat", "conquest")]) == "victory"
    assert event_sound(game, [Victory("zmei", "legend")]) == "defeat"
    assert event_sound(game, [DiplomacyChange("war", "zmei", "voievodat")]) == "alarm"
    assert event_sound(game, [DiplomacyChange("peace", "zmei", "voievodat")]) == "peace"
    assert event_sound(game, []) is None
    assert Battle  # imported for completeness
