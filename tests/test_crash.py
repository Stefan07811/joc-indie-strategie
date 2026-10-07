"""A crash leaves a report in the player's folder and a message, never a silent exit."""

import sys

import pygame
import pytest

from legendele import crash


def boom():
    raise RuntimeError("the dragon ate the treasury")


def test_a_crash_is_written_down(app_with_campaign):
    app = app_with_campaign
    try:
        boom()
    except RuntimeError as exc:
        path = crash.write(exc, app)
    text = path.read_text(encoding="utf-8")
    assert "RuntimeError: the dragon ate the treasury" in text and "in boom" in text
    assert "Campaign: zmei, Spring 1400" in text and "Screen: Campaign" in text


def test_the_log_stays_small(player_home, monkeypatch):
    monkeypatch.setattr(crash, "MAX_BYTES", 3000)
    for _ in range(10):
        try:
            boom()
        except RuntimeError as exc:
            path = crash.write(exc)
    text = path.read_text(encoding="utf-8")
    assert len(text) <= 3000 and text.rstrip().endswith("the dragon ate the treasury")


def test_the_player_is_told(player_home, monkeypatch):
    shown = []
    monkeypatch.setattr(crash, "headless", lambda: False)
    monkeypatch.setattr(pygame.display, "message_box", lambda title, message, **kw: shown.append(message))
    try:
        boom()
    except RuntimeError as exc:
        path = crash.handle(exc)
    assert shown and str(path) in shown[0] and "the dragon ate the treasury" in shown[0]


def test_the_game_does_not_die_silently(player_home, monkeypatch):
    from legendele import __main__ as entry
    from legendele.ui import app as app_module
    shown = []
    monkeypatch.setattr(crash, "headless", lambda: False)
    monkeypatch.setattr(pygame.display, "message_box", lambda title, message, **kw: shown.append(message))
    monkeypatch.setattr(app_module.App, "run", lambda self: boom())
    monkeypatch.setattr(sys, "argv", ["legendele"])
    with pytest.raises(SystemExit) as stop:
        entry.main()
    assert stop.value.code == 1 and shown
    assert "the dragon ate the treasury" in crash.log_path().read_text(encoding="utf-8")


@pytest.fixture
def app_with_campaign(data, player_home):
    from legendele.ui.app import App
    app = App(data)
    app.settings["tutorial"] = False
    app.start_campaign("zmei", seed=1)
    return app


def test_no_window_when_no_one_can_click_it(player_home, monkeypatch):
    monkeypatch.setattr(pygame.display, "message_box", lambda *a, **kw: pytest.fail("would block the build"))
    try:
        boom()
    except RuntimeError as exc:
        assert crash.handle(exc).exists()
