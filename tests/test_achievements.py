"""Achievements: what a campaign earns, and how the profile remembers it."""

import pygame

from legendele import profile
from legendele.game import Game, Victory, achievements


def test_every_achievement_is_listed_once(data):
    ids = [a.id for a in achievements.every(data)]
    assert len(ids) == len(set(ids)) >= 25
    assert "win_outlaws" in ids and ids[-1] == "all_legends"


def test_campaign_deeds(data):
    game = Game.new(data, "voievodat", seed=1)
    assert achievements.campaign(game) == []
    game.stats["voievodat"] = {"won": 1}
    for p in list(game.provinces.values())[:10]:
        p.owner = "voievodat"
    earned = achievements.campaign(game)
    assert "first_blood" in earned and "realm" in earned and "warlord" not in earned
    assert "first_blood" not in achievements.campaign(game, known=earned)


def test_victories_and_all_six(data):
    game = Game.new(data, "outlaws", seed=1, options={"shuffle": True})
    game.winner = Victory("outlaws", "legend")
    earned = achievements.campaign(game)
    assert {"win_outlaws", "legend", "lots", "everyone"} <= set(earned) and "all_legends" not in earned
    others = [achievements.victory_id(f) for f in achievements.LEGENDS if f != "outlaws"]
    assert "all_legends" in achievements.campaign(game, known=others)


def test_ai_games_earn_nothing(data):
    game = Game.new(data, "zmei", seed=1)
    game.spectate = True
    game.winner = Victory("zmei", "conquest")
    assert achievements.campaign(game) == []


def test_the_profile_remembers(player_home):
    assert profile.load_achievements() == {}
    assert profile.unlock(["first_blood", "realm"]) == ["first_blood", "realm"]
    assert profile.unlock(["realm", "hero"]) == ["hero"]
    assert set(profile.load_achievements()) == {"first_blood", "realm", "hero"}


def test_earned_in_play_and_shown(data, player_home):
    from legendele.ui.app import App
    from legendele.ui.menus import AchievementsScreen
    app = App(data)
    app.settings["tutorial"] = False
    app.start_campaign("voievodat", seed=1)
    game = app.scene.game
    game.stats["voievodat"] = {"won": 1}
    app.scene.end_turn()
    assert "first_blood" in profile.load_achievements()
    assert app.toasts and app.toasts[0][0].id == "first_blood"
    app.present(app.scene.draw)  # the announcement is drawn over the map
    app.scene = AchievementsScreen(app, back=app.scene)
    app.scene.draw(app.screen)
    app.scene.handle(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_ESCAPE))
    assert not isinstance(app.scene, AchievementsScreen)
