"""Settings kept between games, saved games in slots, the rotating autosave, and the difficulty."""

import os
import time

import pytest

from crowns import settings as st
from crowns.game.campaign import Campaign
from crowns.game.realms import load
from crowns.provinces import ProvinceMap
from crowns.ui.menu import step


@pytest.fixture
def home(tmp_path, monkeypatch):
    monkeypatch.setenv("CROWNS_HOME", str(tmp_path))
    return tmp_path


def test_settings_are_kept(home):
    s = st.Settings.load()
    assert s.quality == "high" and s.size is None
    step(s, "music", -1)
    step(s, "resolution", 1)
    step(s, "fullscreen", 1)
    step(s, "difficulty", 1)
    s.save()
    again = st.Settings.load()
    assert again.music == 0.5 and again.resolution == "1280x720" and again.size == (1280, 720)
    assert again.fullscreen and again.difficulty == "hard"


def test_a_broken_settings_file_is_forgiven(home):
    (home / "settings.json").write_text("{not json", encoding="utf-8")
    assert st.Settings.load() == st.Settings()


def test_saves_newest_first_and_autosaves_take_turns(home):
    st.write_save("first", {"player": "wallachia", "date": [1402, 9]})
    later = time.time() + 5
    path = st.write_save("second", {"player": "hungary", "date": [1403, 1]})
    os.utime(path, (later, later))
    names = [name for name, _, _ in st.list_saves()]
    assert names == ["second", "first"]
    assert st.list_saves()[0][2]["realm"] == "hungary"
    seen = []
    for k in range(4):
        name = st.autosave_name()
        seen.append(name)
        p = st.write_save(name, {"player": "wallachia", "date": [1403 + k, 1]})
        os.utime(p, (later + 10 + k, later + 10 + k))
    assert seen[:3] == ["autosave_1", "autosave_2", "autosave_3"] and seen[3] == "autosave_1"


def test_difficulty_moves_the_purses():
    provmap = ProvinceMap()
    realms, relations = load()
    incomes = {}
    for level in ("easy", "normal", "hard"):
        c = Campaign(provmap, realms, relations, player="wallachia", seed=1)
        c.difficulty = level
        incomes[level] = (c.budget("wallachia").tax, c.budget("hungary").tax)
    assert incomes["easy"][0] > incomes["normal"][0] > incomes["hard"][0]
    assert incomes["easy"][1] < incomes["normal"][1] < incomes["hard"][1]
