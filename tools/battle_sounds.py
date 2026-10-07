"""The sounds of a battle, made from noise and a little arithmetic: steel on steel, a flight of arrows, the
drumming of a charge, the war horn. Written to crowns/assets/sounds as Ogg.

    python tools/battle_sounds.py
"""

import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from music import RATE, SOUNDS, hall, write_ogg  # noqa: E402


def _t(seconds):
    return np.arange(int(seconds * RATE)) / RATE


def _bandpass(x, lo, hi):
    spec = np.fft.rfft(x)
    f = np.fft.rfftfreq(len(x), 1 / RATE)
    spec[(f < lo) | (f > hi)] = 0
    return np.fft.irfft(spec, len(x))


def _stereo(mono, pan=0.0):
    left, right = np.sqrt(0.5 - pan / 2), np.sqrt(0.5 + pan / 2)
    return np.stack([mono * left, mono * right], axis=1)


def _place(out, sound, at, pan=0.0, gain=1.0):
    i = int(at * RATE)
    n = min(len(sound), len(out) - i)
    if n > 0:
        out[i:i + n] += _stereo(sound[:n] * gain, pan)


def _norm(x, peak=0.8):
    return x / max(1e-9, np.abs(x).max()) * peak


def ring(rng, length=0.35):
    """One blow of steel: a few inharmonic partials ringing down fast."""
    t = _t(length)
    base = rng.uniform(1400, 3200)
    s = sum(np.sin(2 * np.pi * base * k * t + rng.uniform(0, 6)) * np.exp(-t * rng.uniform(18, 40)) / k
            for k in (1.0, 1.47, 2.09, 2.73))
    hit = rng.normal(0, 1, len(t)) * np.exp(-t * 120)
    return s * 0.6 + _bandpass(hit, 800, 9000) * 0.5


def thud(rng, length=0.25):
    t = _t(length)
    return np.sin(2 * np.pi * rng.uniform(70, 130) * t) * np.exp(-t * 30) + \
        _bandpass(rng.normal(0, 1, len(t)), 100, 900) * np.exp(-t * 40) * 0.6


def clash(rng, seconds=4.0):
    """The melee: blows on all sides, shields struck, the roar of men under it. Loops."""
    out = np.zeros((int(seconds * RATE), 2))
    for _ in range(int(seconds * 9)):
        _place(out, ring(rng), rng.uniform(0, seconds - 0.4), rng.uniform(-0.8, 0.8), rng.uniform(0.15, 0.6))
    for _ in range(int(seconds * 6)):
        _place(out, thud(rng), rng.uniform(0, seconds - 0.3), rng.uniform(-0.8, 0.8), rng.uniform(0.2, 0.5))
    t = _t(seconds)
    roar = _bandpass(rng.normal(0, 1, len(t)), 250, 1400)
    roar *= 0.6 + 0.4 * np.sin(2 * np.pi * 0.7 * t) ** 2
    out += _stereo(_norm(roar, 0.18))
    # make the loop seamless: fold the tail over the head
    fade = int(0.3 * RATE)
    w = np.linspace(0, 1, fade)[:, None]
    out[:fade] = out[:fade] * w + out[-fade:] * (1 - w)
    return _norm(out[:-fade], 0.7)


def arrows(rng, seconds=2.2):
    """A volley: the hiss of many arrows passing, then their fall."""
    out = np.zeros((int(seconds * RATE), 2))
    for _ in range(28):
        length = rng.uniform(0.35, 0.7)
        t = _t(length)
        env = np.sin(np.pi * t / length) ** 2
        f0 = rng.uniform(2500, 5000)
        hiss = _bandpass(rng.normal(0, 1, len(t)), f0 * 0.7, f0 * 1.4) * env
        _place(out, hiss, rng.uniform(0.0, 0.7), rng.uniform(-0.9, 0.9), rng.uniform(0.15, 0.35))
    for _ in range(18):
        t = _t(0.12)
        tick = _bandpass(rng.normal(0, 1, len(t)), 600, 4000) * np.exp(-t * 60)
        _place(out, tick, rng.uniform(1.0, 1.9), rng.uniform(-0.9, 0.9), rng.uniform(0.1, 0.3))
    return _norm(out, 0.6)


def charge(rng, seconds=4.0):
    """Horses at the gallop, coming on: hooves in threes, the ground drumming, harness jingling."""
    out = np.zeros((int(seconds * RATE), 2))
    for horse in range(14):
        pan = rng.uniform(-0.9, 0.9)
        stride = rng.uniform(0.36, 0.44)
        t0 = rng.uniform(0, stride)
        while t0 < seconds - 0.2:
            for k, gap in enumerate((0.0, 0.07, 0.15)):
                at = t0 + gap + rng.normal(0, 0.006)
                gain = (0.25 + 0.75 * at / seconds) * rng.uniform(0.5, 1.0)
                _place(out, thud(rng, 0.18), at, pan, gain * 0.5)
            t0 += stride
    for _ in range(40):
        t = _t(0.08)
        jingle = np.sin(2 * np.pi * rng.uniform(3000, 6000) * t) * np.exp(-t * 50)
        _place(out, jingle, rng.uniform(0, seconds - 0.1), rng.uniform(-0.9, 0.9), 0.05)
    return _norm(out, 0.75)


def horn(rng, seconds=2.6):
    """The war horn that opens the battle: a long call and a falling note."""
    t = _t(seconds)
    f = np.where(t < 1.6, 196.0, 196.0 * 2 ** (-2 / 12))
    f = f * (1 + 0.004 * np.sin(2 * np.pi * 5 * t))
    phase = 2 * np.pi * np.cumsum(f) / RATE
    tone = sum(np.sin(phase * k) / k ** 1.3 for k in range(1, 9))
    env = np.minimum(1, t / 0.15) * np.minimum(1, (seconds - t) / 0.5)
    env *= np.where(np.abs(t - 1.6) < 0.05, 0.4, 1.0)
    mono = _bandpass(tone * env, 80, 2400)
    return hall(_stereo(_norm(mono, 0.7)), seconds=2.0, wet=0.3)


def main():
    rng = np.random.default_rng(1402)
    for name, make in (("clash", clash), ("arrows", arrows), ("charge", charge), ("horn", horn)):
        write_ogg(make(rng), SOUNDS / f"{name}.ogg")


if __name__ == "__main__":
    main()
