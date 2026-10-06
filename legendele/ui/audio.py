"""Sound effects and music, synthesised in code (no audio files needed).

A WAV/OGG file in assets/sounds/ (effects) or assets/music/ (themes) with the same name replaces the
synthesised version, so real recordings can be dropped in later. Without an audio device the game
simply stays silent.

The music is a doina-like tune over a drone: each legend gets its own mode of the folk scales.
"""

import array
import math
import random
import threading
from pathlib import Path

import pygame

RATE = 22050
ASSET_DIR = Path(__file__).resolve().parent.parent / "assets"
TAU = 2 * math.pi

# D-based folk modes (semitones above D)
MODES = {
    "menu": [0, 2, 3, 6, 7, 9, 10],        # Romanian (Ukrainian Dorian) minor: the doina sound
    "voievodat": [0, 2, 3, 5, 7, 9, 10],   # Dorian: steady and stately
    "zmei": [0, 1, 4, 5, 7, 8, 10],        # Phrygian dominant: fiery
    "iele": [0, 2, 4, 6, 7, 9, 11],        # Lydian: bright and uncanny
    "strigoi": [0, 1, 3, 5, 6, 8, 10],     # Locrian: hollow and grave
}
TEMPO = {"menu": 84, "voievodat": 92, "zmei": 104, "iele": 112, "strigoi": 72}
D3 = 146.83


def _freq(base, semitones):
    return base * 2 ** (semitones / 12)


def _note(out, start, freq, dur, vol, timbre="flute", attack=0.01, release=0.08, vibrato=0.0):
    n = int(dur * RATE)
    a, r = max(1, int(attack * RATE)), max(1, int(release * RATE))
    step = TAU * freq / RATE
    phase = 0.0
    end = min(len(out), start + n)
    for i in range(start, end):
        k = i - start
        env = min(1.0, k / a, (n - k) / r)
        if vibrato:
            phase += step * (1 + vibrato * math.sin(TAU * 5.5 * k / RATE))
        else:
            phase += step
        if timbre == "flute":
            s = math.sin(phase) + 0.25 * math.sin(2 * phase) + 0.1 * math.sin(3 * phase)
        elif timbre == "reed":
            s = math.sin(phase) + 0.5 * math.sin(2 * phase) + 0.33 * math.sin(3 * phase) + 0.2 * math.sin(5 * phase)
        elif timbre == "bell":
            s = math.sin(phase) + 0.6 * math.sin(2.76 * phase) + 0.3 * math.sin(5.4 * phase)
            env *= math.exp(-3.0 * k / n)
        else:  # pluck
            s = math.sin(phase) + 0.4 * math.sin(2 * phase)
            env *= math.exp(-6.0 * k / n)
        out[i] += vol * env * s


def _noise(out, start, dur, vol, decay=20.0, seed=0):
    rng = random.Random(seed)
    n = int(dur * RATE)
    low = 0.0
    for k in range(min(n, len(out) - start)):
        low = 0.6 * low + 0.4 * rng.uniform(-1, 1)
        out[start + k] += vol * low * math.exp(-decay * k / n)


def _thump(out, start, freq, dur, vol):
    n = int(dur * RATE)
    phase = 0.0
    for k in range(min(n, len(out) - start)):
        phase += TAU * freq * (1 - 0.5 * k / n) / RATE
        out[start + k] += vol * math.sin(phase) * math.exp(-8.0 * k / n)


def _pcm(samples):
    peak = max(1e-9, max(abs(s) for s in samples))
    scale = 32000 / max(peak, 1.0)
    return array.array("h", (int(max(-32767, min(32767, s * scale))) for s in samples)).tobytes()


def _blank(seconds):
    return [0.0] * int(seconds * RATE)


def synth_effect(name):
    """Raw 16-bit mono samples (bytes) for a sound effect."""
    t = lambda s: int(s * RATE)  # noqa: E731
    if name == "click":
        out = _blank(0.06)
        _note(out, 0, 1320, 0.05, 0.6, "pluck")
    elif name == "select":
        out = _blank(0.16)
        _note(out, 0, 660, 0.07, 0.5, "pluck")
        _note(out, t(0.06), 990, 0.09, 0.5, "pluck")
    elif name == "march":
        out = _blank(0.7)
        for i in range(3):
            _thump(out, t(0.2 * i), 95, 0.18, 0.9)
            _noise(out, t(0.2 * i), 0.05, 0.25, seed=i)
    elif name == "battle":
        out = _blank(1.1)
        for i, at in enumerate((0.0, 0.18, 0.31, 0.55, 0.7)):
            _noise(out, t(at), 0.18, 0.7, decay=14, seed=i)
            _note(out, t(at), 1250 + 170 * i, 0.3, 0.25, "bell")
            _note(out, t(at), 1870 + 90 * i, 0.25, 0.15, "bell")
        _thump(out, 0, 70, 0.5, 0.8)
    elif name == "victory":
        out = _blank(1.6)
        for i, semis in enumerate((0, 4, 7, 12)):
            _note(out, t(0.16 * i), _freq(D3 * 2, semis), 0.9 if i == 3 else 0.2, 0.5, "reed", release=0.3)
    elif name == "defeat":
        out = _blank(1.8)
        for i, semis in enumerate((7, 3, 2, 0)):
            _note(out, t(0.3 * i), _freq(D3, semis), 0.9 if i == 3 else 0.35, 0.5, "reed", release=0.4)
    elif name == "build":
        out = _blank(0.5)
        for i in range(2):
            _noise(out, t(0.2 * i), 0.08, 0.6, decay=30, seed=10 + i)
            _note(out, t(0.2 * i), 520, 0.12, 0.3, "pluck")
    elif name == "recruit":
        out = _blank(0.9)
        _note(out, 0, _freq(D3, 7), 0.25, 0.5, "reed", vibrato=0.01)
        _note(out, t(0.22), _freq(D3, 12), 0.6, 0.5, "reed", release=0.3, vibrato=0.01)
    elif name == "turn":
        out = _blank(1.8)
        _note(out, 0, _freq(D3 * 2, 7), 1.7, 0.6, "bell")
        _note(out, 0, _freq(D3 * 4, 0), 1.2, 0.2, "bell")
    elif name == "alarm":
        out = _blank(1.3)
        _note(out, 0, _freq(D3 / 2, 0), 0.5, 0.7, "reed", release=0.1)
        _note(out, t(0.45), _freq(D3 / 2, 1), 0.8, 0.7, "reed", release=0.4)
    elif name == "coins":
        out = _blank(0.7)
        for i in range(5):
            _note(out, t(0.09 * i), 2000 + 260 * (i % 3), 0.2, 0.35, "bell")
    elif name == "peace":
        out = _blank(1.6)
        for semis in (0, 4, 7):
            _note(out, 0, _freq(D3 * 2, semis), 1.5, 0.3, "flute", attack=0.2, release=0.6)
    else:
        raise KeyError(name)
    return _pcm(out)


def synth_music(theme, seconds=24.0, seed=None):
    """Raw samples for a looping theme: a drone of the root and fifth, under a wandering doina tune."""
    mode = MODES[theme]
    rng = random.Random(seed if seed is not None else theme)
    beat = 60 / TEMPO[theme]
    out = _blank(seconds)
    root = D3 / 2 if theme == "strigoi" else D3
    # the drone, re-struck every four bars so the loop seam is soft
    bar = beat * 4
    at = 0.0
    while at < seconds - 0.01:
        length = min(bar * 4, seconds - at)
        _note(out, int(at * RATE), root, length, 0.12, "reed", attack=0.3, release=0.3)
        _note(out, int(at * RATE), root * 1.5, length, 0.07, "reed", attack=0.3, release=0.3)
        at += bar * 4
    # the tune: a random walk on the mode, phrases ending on the root
    degree, at = 7, 0.0
    while at < seconds - beat:
        phrase_end = min(seconds - beat, at + bar * 2)
        while at < phrase_end:
            length = beat * rng.choice((0.5, 0.5, 1, 1, 1.5, 2))
            degree = max(0, min(13, degree + rng.choice((-2, -1, -1, 0, 1, 1, 2))))
            octave, step = divmod(degree, 7)
            freq = _freq(root * 2, mode[step] + 12 * octave)
            if rng.random() < 0.85:
                _note(out, int(at * RATE), freq, length * 0.95, 0.22, "flute", attack=0.03, release=0.1, vibrato=0.006)
            at += length
        _note(out, int(at * RATE), root * 2, beat * 1.5, 0.2, "flute", attack=0.05, release=0.4, vibrato=0.006)
        at += beat * 2
        degree = 7
    return _pcm(out)


class Audio:
    """Plays effects and one looping theme. Everything is a no-op without an audio device."""

    def __init__(self, settings):
        self.settings = settings
        self.enabled = False
        try:
            pygame.mixer.init(RATE, -16, 1, 512)
            pygame.mixer.set_reserved(1)
            self.enabled = True
        except pygame.error:
            return
        self.music_channel = pygame.mixer.Channel(0)
        self._effects = {}
        self._themes = {}
        self._pending = {}  # theme -> raw bytes being synthesised in the background
        self._wanted = None
        self._playing = None

    def play(self, name):
        if not self.enabled or self.settings["sound"] <= 0:
            return
        if name not in self._effects:
            self._effects[name] = self._load("sounds", name) or pygame.mixer.Sound(buffer=synth_effect(name))
        sound = self._effects[name]
        sound.set_volume(self.settings["sound"])
        sound.play()

    def music(self, theme):
        """Switch to `theme` (synthesising it in the background the first time)."""
        if not self.enabled:
            return
        self._wanted = theme
        if theme not in self._themes and theme not in self._pending:
            loaded = self._load("music", theme)
            if loaded:
                self._themes[theme] = loaded
            else:
                self._pending[theme] = None
                threading.Thread(target=self._synth, args=(theme,), daemon=True).start()

    def _synth(self, theme):
        self._pending[theme] = synth_music(theme)

    def update(self):
        """Call once a frame: starts themes that finished synthesising, applies volume changes."""
        if not self.enabled:
            return
        for theme, raw in list(self._pending.items()):
            if raw is not None:
                self._themes[theme] = pygame.mixer.Sound(buffer=raw)
                del self._pending[theme]
        if self._wanted != self._playing and self._wanted in self._themes:
            self.music_channel.fadeout(400)
            self.music_channel.play(self._themes[self._wanted], loops=-1, fade_ms=800)
            self._playing = self._wanted
        self.music_channel.set_volume(self.settings["music"])

    def _load(self, folder, name):
        for ext in (".ogg", ".wav"):
            path = ASSET_DIR / folder / f"{name}{ext}"
            if path.exists():
                return pygame.mixer.Sound(str(path))
        return None


EFFECTS = ("click", "select", "march", "battle", "victory", "defeat", "build", "recruit", "turn", "alarm",
           "coins", "peace")
