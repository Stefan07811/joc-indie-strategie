"""Compose and render the game's music and sounds with real sampled instruments.

The pieces are original, written in the manner of the late Middle Ages: estampies in the church modes
for the Christian lands, a maqam piece for the Ottoman and Islamic world, a doina and hora for the
Danube, a court piece and a war march. They are played on the instruments of the GeneralUser GS
SoundFont (recorder, lute, fiddle, harp, shawm, bagpipe, ney, oud, kanun, frame drums), given the
echo of a stone hall, and written as Ogg Vorbis files to crowns/assets/music and crowns/assets/sounds.

    pip install --no-deps tinysoundfont
    python tools/music.py [--soundfont PATH]

The SoundFont (GeneralUser GS by S. Christian Collins, free to use) is downloaded once to the build
cache if no path is given. Only the rendered files are shipped with the game.
"""

import argparse
import os
import subprocess
import sys
import tempfile
import urllib.request
import wave
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
MUSIC = ROOT / "crowns" / "assets" / "music"
SOUNDS = ROOT / "crowns" / "assets" / "sounds"
SF2_URL = "https://raw.githubusercontent.com/mrbumpy409/GeneralUser-GS/main/GeneralUser-GS.sf2"
RATE = 44100

# General MIDI programs (0-based) standing in for the instruments of the age
RECORDER, PAN_FLUTE, SHAKUHACHI = 74, 75, 77
LUTE, HARP, DULCIMER = 24, 46, 15
FIDDLE, CELLO, STRINGS = 110, 42, 48
SHAWM, BAGPIPE, TRUMPET = 68, 109, 56
BELLS, CHOIR = 14, 52
DRUMS = "drums"
# percussion keys
BASS_DRUM, LOW_TOM, MID_TOM, SNARE, TAMBOURINE = 36, 41, 45, 38, 54
HIGH_BONGO, LOW_BONGO, MUTE_CONGA, OPEN_CONGA, LOW_CONGA = 60, 61, 62, 63, 64

NOTE = {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11}


def pitch(name):
    """'D5', 'F#4', 'Eb5' -> MIDI key."""
    letter, rest = name[0], name[1:]
    shift = 0
    while rest and rest[0] in "#b":
        shift += 1 if rest[0] == "#" else -1
        rest = rest[1:]
    return 12 * (int(rest) + 1) + NOTE[letter] + shift


def line(text, start=0.0, scale=1.0):
    """'D5/2 E5/1 r/1 F#5/.5' -> [(start, duration, key)], durations in beats times `scale`; and the end."""
    out, t = [], start
    for token in text.split():
        name, dur = token.split("/")
        d = float(dur) * scale
        if name != "r":
            out.append((t, d, pitch(name)))
        t += d
    return out, t


class Score:
    """Notes on channels, in beats; rendered at a tempo."""

    def __init__(self, tempo):
        self.tempo = tempo          # beats a minute
        self.parts = {}             # channel -> (program, [(start, dur, key, velocity)])

    def part(self, channel, program):
        self.parts.setdefault(channel, (program, []))
        return self.parts[channel][1]

    def add(self, channel, program, notes, velocity=90, swing=0.0, human=0.0, rng=None):
        part = self.part(channel, program)
        for start, dur, key in notes:
            v = velocity
            if rng is not None and human:
                v = int(np.clip(velocity + rng.normal(0, human), 20, 127))
                start += rng.normal(0, 0.008)
            part.append((max(0.0, start), dur, key, v))

    @property
    def length(self):
        return max((s + d for _, notes in self.parts.values() for s, d, _, _ in notes), default=0.0)


def render(score, synth, sfid, tail=4.0):
    """Play the score through the synth: a stereo float array."""
    events = []
    for channel, (program, notes) in score.parts.items():
        if program == DRUMS:
            synth.program_select(channel, sfid, 128, 0, True)
        else:
            synth.program_select(channel, sfid, 0, program)
        for start, dur, key, vel in notes:
            events.append((start, 1, channel, key, vel))
            events.append((start + dur * 0.97, 0, channel, key, 0))
    events.sort(key=lambda e: (e[0], e[1]))
    seconds_per_beat = 60.0 / score.tempo
    out, now = [], 0
    for beat, on, channel, key, vel in events:
        at = int(beat * seconds_per_beat * RATE)
        if at > now:
            out.append(np.frombuffer(synth.generate(at - now), np.float32).reshape(-1, 2).copy())
            now = at
        if on:
            synth.noteon(channel, key, vel)
        else:
            synth.noteoff(channel, key)
    out.append(np.frombuffer(synth.generate(int(tail * RATE)), np.float32).reshape(-1, 2).copy())
    synth.notes_off()
    return np.concatenate(out)


def hall(audio, seconds=2.4, wet=0.22, seed=3):
    """The echo of a stone hall: convolution with a decaying noise impulse, block by block."""
    rng = np.random.default_rng(seed)
    n = int(seconds * RATE)
    t = np.arange(n) / RATE
    env = np.exp(-t * 6.9 / seconds) * (1 - np.exp(-t * 300))
    out = np.empty_like(audio)
    block = 1 << 16
    size = 1
    while size < block + n:
        size <<= 1
    for ch in range(2):
        ir = rng.normal(0, 1, n) * env
        ir /= np.sqrt(np.sum(ir ** 2))
        spectrum = np.fft.rfft(ir, size)
        x = audio[:, ch]
        y = np.zeros(len(x) + n)
        for i in range(0, len(x), block):
            seg = x[i:i + block]
            conv = np.fft.irfft(np.fft.rfft(seg, size) * spectrum, size)[:len(seg) + n]
            y[i:i + len(conv)] += conv
        out[:, ch] = (1 - wet) * x + wet * y[:len(x)] * 0.8
    return out


def finish(audio, fade_in=0.02, fade_out=3.0, peak=0.7):
    a = audio.copy()
    fi, fo = int(fade_in * RATE), int(fade_out * RATE)
    a[:fi] *= np.linspace(0, 1, fi)[:, None]
    if fo:
        a[-fo:] *= np.linspace(1, 0, fo)[:, None] ** 1.5
    a *= peak / max(1e-6, np.max(np.abs(a)))
    return a


def write_ogg(audio, path, quality=4):
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        wav = Path(tmp) / "out.wav"
        pcm = (np.clip(audio, -1, 1) * 32767).astype("<i2")
        with wave.open(str(wav), "wb") as w:
            w.setnchannels(2)
            w.setsampwidth(2)
            w.setframerate(RATE)
            w.writeframes(pcm.tobytes())
        subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-i", str(wav), "-c:a", "libvorbis", "-q:a",
                        str(quality), str(path)], check=True)
    print(f"wrote {path.relative_to(ROOT)} ({path.stat().st_size // 1024} KB, {len(audio) / RATE:.0f} s)")


# --- the pieces -------------------------------------------------------------------------------------

def danube(rng):
    """An estampie in D Dorian, in 6/8 (a beat is an eighth): recorder, fiddle, lute, harp, frame drum."""
    s = Score(tempo=228)
    a = "D5/2 E5/1 F5/2 G5/1  A5/3 G5/1 F5/1 E5/1  D5/2 E5/1 F5/1 G5/1 A5/1  C6/3 A5/3 " \
        "G5/2 F5/1 E5/2 F5/1  G5/2 A5/1 G5/1 F5/1 E5/1 "
    b = "A5/2 B5/1 C6/2 D6/1  C6/2 B5/1 A5/3  G5/2 A5/1 B5/1 A5/1 G5/1  A5/6 " \
        "D6/2 C6/1 B5/2 A5/1  G5/2 F5/1 E5/2 D5/1 "
    ouvert, clos = "F5/2 G5/1 A5/1 G5/1 F5/1  E5/6 ", "F5/2 E5/1 D5/1 C5/1 E5/1  D5/6 "
    tune = a + ouvert + a + clos + b + ouvert + b + clos + a + ouvert + a + clos
    # the chord under each bar of a section: D, C or the dominant A
    chords_a = "D D D C C C D D".split()
    chords_b = "A A C A D C D D".split()
    bars = (chords_a * 2) + (chords_b * 2) + (chords_a * 2)
    roots = {"D": ("D3", "A3", "D4"), "C": ("C3", "G3", "C4"), "A": ("A2", "E3", "A3")}
    t = 0.0
    for rnd in range(2):
        melody, end = line(tune, t)
        if rnd == 0:
            s.add(0, RECORDER, melody, 92, human=6, rng=rng)
        else:
            s.add(1, FIDDLE, melody, 84, human=6, rng=rng)
            up = [(st, d, k + 12) for st, d, k in melody]
            s.add(0, RECORDER, up, 66, human=5, rng=rng)
        for i, chord in enumerate(bars):
            bar = t + i * 6
            lo, fifth, hi = (pitch(n) for n in roots[chord])
            s.add(2, LUTE, [(bar, 1, lo), (bar + 1, 1, fifth), (bar + 2, 1, hi), (bar + 3, 1, fifth),
                            (bar + 4, 1, hi), (bar + 5, 1, fifth)], 62, human=8, rng=rng)
            if i % 2 == 0:
                s.add(3, HARP, [(bar, 6, lo - 12), (bar, 6, hi + 12)], 48)
            s.add(9, DRUMS, [(bar, .5, LOW_TOM), (bar + 2, .5, TAMBOURINE), (bar + 3, .5, LOW_TOM),
                             (bar + 5, .5, TAMBOURINE)], 70 if rnd else 55, human=10, rng=rng)
        s.add(4, STRINGS, [(t, end - t, pitch("D3")), (t, end - t, pitch("A3"))], 38)
        t = end
    s.add(3, HARP, [(t, 8, pitch("D3")), (t, 8, pitch("A3")), (t, 8, pitch("D4")), (t + .3, 8, pitch("F4"))], 70)
    return s


def crescent(rng):
    """In maqam Hijaz on D, 4/4 (a beat is an eighth), the maqsum rhythm: ney, oud, kanun, darbuka."""
    s = Score(tempo=184)
    a = "D5/2 Eb5/1 F#5/1 G5/2 A5/2  Bb5/1 A5/1 G5/1 F#5/1 G5/4  F#5/1 G5/1 A5/2 G5/1 F#5/1 Eb5/2  D5/6 r/2 " \
        "A5/2 Bb5/1 C6/1 D6/2 C6/2  Bb5/1 A5/1 G5/2 A5/4  G5/1 F#5/1 Eb5/2 F#5/1 G5/1 F#5/1 Eb5/1  D5/8 "
    b = "G4/2 A4/1 Bb4/1 A4/2 G4/2  F#4/1 G4/1 A4/2 Bb4/2 A4/2  G4/2 F#4/1 Eb4/1 D4/4  r/8 " \
        "Bb4/2 C5/1 D5/1 C5/2 Bb4/2  A4/1 Bb4/1 C5/2 Bb4/1 A4/1 G4/2  A4/1 G4/1 F#4/1 Eb4/1 F#4/2 G4/2  D4/8 "
    answer = "D5/.5 Eb5/.5 F#5/.5 G5/.5 A5/.5 G5/.5 F#5/.5 Eb5/.5  D5/.5 Eb5/.5 F#5/.5 Eb5/.5 D5/2 "
    t = 0.0
    # an opening taqsim: the ney alone over the drone, free and slow
    taqsim, t1 = line("A4/3 Bb4/1 A4/2 G4/2  F#4/1 G4/1 A4/4 r/2  D5/4 Eb5/1 D5/1 C5/1 Bb4/1  A4/6 G4/1 F#4/1 "
                      "Eb4/2 F#4/2 G4/2 F#4/1 Eb4/1  D4/8 r/4", 0.0, 1.6)
    s.add(0, SHAKUHACHI, taqsim, 86, human=8, rng=rng)
    s.add(4, STRINGS, [(0, t1, pitch("D3")), (0, t1, pitch("A3"))], 42)
    t = t1
    for rnd in range(3):
        mel_a, end_a = line(a, t)
        s.add(0, SHAKUHACHI, mel_a, 92, human=7, rng=rng)
        if rnd > 0:
            s.add(2, LUTE, [(st, d, k - 12) for st, d, k in mel_a], 70, human=6, rng=rng)
        mel_b, end_b = line(b, end_a)
        s.add(3 if rnd != 1 else 0, DULCIMER if rnd != 1 else SHAKUHACHI, mel_b, 80, human=6, rng=rng)
        resp, _ = line(answer, end_a + 24)
        s.add(3, DULCIMER, resp, 72, human=6, rng=rng)
        end = end_b
        for bar in np.arange(t, end, 8):
            dum, tek = (LOW_CONGA, HIGH_BONGO) if rnd else (LOW_BONGO, HIGH_BONGO)
            s.add(9, DRUMS, [(bar, .5, dum), (bar + 1, .5, tek), (bar + 3, .5, tek), (bar + 4, .5, dum),
                             (bar + 6, .5, tek)], 78, human=10, rng=rng)
            if rnd == 2:
                s.add(9, DRUMS, [(bar + i * .5, .25, TAMBOURINE) for i in range(16)], 40, human=8, rng=rng)
            s.add(5, LUTE, [(bar, 1, pitch("D3")), (bar + 2, 1, pitch("A2")), (bar + 4, 1, pitch("D3")),
                            (bar + 6, 1, pitch("A2"))], 60, human=8, rng=rng)
        s.add(4, STRINGS, [(t, end - t, pitch("D3")), (t, end - t, pitch("A3"))], 40)
        t = end
    s.add(0, SHAKUHACHI, [(t, 10, pitch("D5"))], 80)
    s.add(4, STRINGS, [(t, 10, pitch("D3")), (t, 10, pitch("A3"))], 40)
    return s


def court(rng):
    """A slow piece for times of peace, in G, 3/4 (a beat is a quarter): harp, recorder, cello."""
    s = Score(tempo=66)
    a = "B4/2 A4/1  G4/2 D5/1  C5/1 B4/1 A4/1  B4/3  D5/2 E5/1  D5/2 B4/1  C5/1 B4/1 A4/1  G4/3 "
    b = "E5/2 D5/1  C5/2 B4/1  A4/1 B4/1 C5/1  D5/3  G5/2 F5/1  E5/2 D5/1  C5/1 A4/1 B4/1  G4/3 "
    harmony = {"G": ("G2", "D3", "G3", "B3"), "C": ("C3", "G3", "C4", "E4"), "D": ("D3", "A3", "D4", "F#4"),
               "Am": ("A2", "E3", "A3", "C4"), "F": ("F2", "C3", "F3", "A3"), "Em": ("E3", "B3", "E4", "G4")}
    plan_a = "G G Am G G G D G".split()
    plan_b = "C C Am D G C D G".split()
    t = 0.0
    for rnd in range(3):
        for text, plan in ((a, plan_a), (b, plan_b)):
            mel, end = line(text, t)
            if rnd == 1:
                s.add(1, FIDDLE, mel, 72, human=5, rng=rng)
            else:
                s.add(0, RECORDER, mel, 80, human=5, rng=rng)
            for i, chord in enumerate(plan):
                bar = t + i * 3
                notes = [pitch(n) for n in harmony[chord]]
                s.add(2, HARP, [(bar + j * .5, .5, notes[k]) for j, k in enumerate((0, 1, 2, 3, 2, 1))], 64,
                      human=7, rng=rng)
            s.add(3, CELLO, [(t, 12, pitch("G2")), (t + 12, 12, pitch("D2" if text is a else "C2"))], 46)
            t = end
    s.add(2, HARP, [(t + i * .25, 4, pitch(n)) for i, n in enumerate(("G2", "D3", "G3", "B3", "D4", "G4"))], 70)
    return s


def war_banners(rng):
    """A war march in A Mixolydian, 4/4 (a beat is a quarter): shawm, bagpipe, trumpet, drums."""
    s = Score(tempo=104)
    a = "A4/1 A4/.5 B4/.5 C#5/1 A4/1  E5/1.5 D5/.5 C#5/1 B4/1  A4/1 B4/.5 C#5/.5 D5/1 E5/1  F#5/1 E5/1 D5/1 E5/1 " \
        "G5/1.5 F#5/.5 E5/1 D5/1  C#5/1 D5/.5 E5/.5 B4/2 "
    ouvert, clos = "A4/1 G4/1 B4/1 C#5/1  E5/4 ", "A4/1 C#5/1 B4/1 G4/1  A4/4 "
    b = "E5/1 E5/1 F#5/1 G5/1  A5/2 G5/1 F#5/1  E5/1 D5/1 C#5/1 B4/1  C#5/2 A4/2 " \
        "D5/1 E5/1 F#5/1 D5/1  E5/1 C#5/1 A4/1 B4/1 "
    tune = a + ouvert + a + clos + b + ouvert + b + clos
    fanfare = "A4/.5 A4/.5 E5/1 A4/.5 C#5/.5 E5/2 r/0  A5/3 r/1"
    t = 0.0
    call, t = line(fanfare, t)
    s.add(6, TRUMPET, call, 96)
    s.add(9, DRUMS, [(i * .25, .25, SNARE) for i in range(16)], 60)
    for rnd in range(2):
        mel, end = line(tune, t)
        s.add(0, SHAWM, mel, 96, human=6, rng=rng)
        if rnd == 1:
            s.add(1, BAGPIPE, mel, 78, human=4, rng=rng)
            s.add(6, TRUMPET, [(st, d, k - 12) for st, d, k in mel[::4]], 60)
        for bar in np.arange(t, end, 4):
            s.add(9, DRUMS, [(bar, .5, BASS_DRUM), (bar + 2, .5, BASS_DRUM), (bar + 1, .5, LOW_TOM),
                             (bar + 3, .25, SNARE), (bar + 3.25, .25, SNARE), (bar + 3.5, .25, SNARE),
                             (bar + 3.75, .25, SNARE)], 82, human=10, rng=rng)
        s.add(4, STRINGS, [(t, end - t, pitch("A2")), (t, end - t, pitch("E3"))], 44)
        s.add(5, CELLO, [(bar, 2, pitch("A2")) for bar in np.arange(t, end, 4)], 54)
        t = end
    s.add(0, SHAWM, [(t, 4, pitch("A4"))], 96)
    s.add(6, TRUMPET, [(t, 4, pitch("A4")), (t, 4, pitch("E5"))], 90)
    s.add(9, DRUMS, [(t, 1, BASS_DRUM)], 100)
    return s


def doina(rng):
    """A doina, the long free lament of the Romanian lands, then a hora: pan flute, fiddle, lute, drum.
    Mode: A with a sharp fourth (D#) and sixth (F#)."""
    s = Score(tempo=60)
    lament = ("E5/3 F#5/.25 E5/.25 D#5/.5 E5/.5 F#5/1 E5/2  D#5/.5 C5/.5 B4/1 A4/4 r/1 "
              "B4/.5 C5/.5 D#5/1 E5/2 F#5/.5 G5/.5 F#5/1 E5/3  D#5/.5 E5/.5 C5/1 B4/1 A4/4 r/1 "
              "A5/2 G5/.5 F#5/.5 E5/2 F#5/.25 G5/.25 F#5/1 E5/1 D#5/1  E5/4 r/.5 "
              "C5/.5 B4/.5 A4/1 B4/.5 C5/.5 D#5/1 C5/.5 B4/.5 A4/5 r/2")
    mel, t = line(lament, 0.0)
    s.add(0, PAN_FLUTE, mel, 88, human=6, rng=rng)
    s.add(4, STRINGS, [(0, t, pitch("A2")), (0, t, pitch("E3"))], 42)
    s.add(1, FIDDLE, [(0, t, pitch("A3"))], 34)
    # the hora: twice as fast; a beat is an eighth at 240
    hora = Score(tempo=240)
    tune = ("E5/1 E5/1 F#5/1 E5/1  D#5/1 C5/1 B4/1 C5/1  D#5/1 E5/1 F#5/1 G5/1  F#5/2 E5/2 "
            "E5/1 D#5/1 C5/1 B4/1  C5/1 D#5/1 E5/1 D#5/1  C5/1 B4/1 A4/1 B4/1  A4/4 ")
    tune2 = ("A5/1 A5/1 G5/1 F#5/1  G5/1 F#5/1 E5/2  F#5/1 E5/1 D#5/1 E5/1  C5/2 B4/2 "
             "C5/1 D#5/1 E5/1 F#5/1  G5/1 F#5/1 E5/1 D#5/1  C5/1 B4/1 C5/1 D#5/1  E5/4 ")
    th = t * 4 + 2
    for rnd in range(3):
        for text in (tune, tune, tune2, tune2):
            m, end = line(text, th)
            hora.add(1, FIDDLE, m, 90, human=6, rng=rng)
            if rnd:
                hora.add(0, PAN_FLUTE, [(st, d, k + 12) for st, d, k in m], 60, human=5, rng=rng)
            for bar in np.arange(th, end, 4):
                root = pitch("A2")
                hora.add(2, LUTE, [(bar, 1, root), (bar + 1, 1, root + 12 + 4 - 1), (bar + 2, 1, root + 7),
                                   (bar + 3, 1, root + 12 + 4 - 1)], 64, human=8, rng=rng)
                hora.add(9, DRUMS, [(bar, .5, LOW_TOM), (bar + 1, .5, TAMBOURINE), (bar + 2, .5, LOW_TOM),
                                    (bar + 3, .5, TAMBOURINE)], 72, human=10, rng=rng)
            th = end
    hora.add(1, FIDDLE, [(th, 6, pitch("A4"))], 90)
    hora.add(2, LUTE, [(th, 6, pitch("A2")), (th, 6, pitch("E3")), (th, 6, pitch("A3"))], 70)
    # fold the hora into the doina's score (its beats are a quarter as long)
    for channel, (program, notes) in hora.parts.items():
        part = s.part(channel if channel != 0 else 6, program)
        part.extend((st / 4, d / 4, k, v) for st, d, k, v in notes)
    return s


PIECES = {"the_danube": danube, "the_crescent": crescent, "the_court": court, "war_banners": war_banners,
          "doina": doina}


# --- sounds --------------------------------------------------------------------------------------

def sounds():
    """Short sounds for the game: (name, score, tail seconds)."""
    out = []
    s = Score(120)
    s.add(0, LUTE, [(0, .5, pitch("D4")), (0.04, .5, pitch("A4"))], 70)
    out.append(("click", s, 0.6))
    s = Score(60)
    s.add(0, BELLS, [(0, 3, pitch("D5")), (0.6, 3, pitch("A4"))], 80)
    out.append(("month", s, 2.5))
    s = Score(120)
    s.add(9, DRUMS, [(i * .25, .25, SNARE) for i in range(8)] + [(2, .5, BASS_DRUM)], 80)
    out.append(("march", s, 1.0))
    s = Score(120)
    s.add(6, TRUMPET, line("D5/.5 D5/.5 A5/1 F#5/.5 A5/2", 0)[0], 100)
    s.add(9, DRUMS, [(0, .5, BASS_DRUM), (2, .5, BASS_DRUM)], 90)
    out.append(("victory", s, 1.5))
    s = Score(70)
    s.add(6, CELLO, line("D3/1 C3/1 A2/2", 0)[0], 90)
    s.add(9, DRUMS, [(0, 1, LOW_TOM), (2, 1, LOW_TOM)], 80)
    out.append(("defeat", s, 1.5))
    s = Score(100)
    s.add(0, CHOIR, [(0, 3, pitch(n)) for n in ("D4", "A4", "D5", "F#5")], 70)
    out.append(("event", s, 2.0))
    s = Score(120)
    s.add(9, DRUMS, [(i * .5, .25, k) for i, k in enumerate((MID_TOM, LOW_TOM, MID_TOM, LOW_TOM))], 75)
    out.append(("build", s, 0.8))
    return out


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--soundfont", help="path to GeneralUser-GS.sf2 (downloaded if omitted)")
    parser.add_argument("--only", nargs="*", help="just these pieces")
    args = parser.parse_args(argv)
    import tinysoundfont
    sf2 = Path(args.soundfont) if args.soundfont else \
        Path(os.environ.get("CROWNS_HOME", Path.home() / ".crowns")) / "build" / "GeneralUser-GS.sf2"
    if not sf2.exists():
        sf2.parent.mkdir(parents=True, exist_ok=True)
        print("downloading the SoundFont…")
        urllib.request.urlretrieve(SF2_URL, sf2)
    rng = np.random.default_rng(1402)
    synth = tinysoundfont.Synth(samplerate=RATE)
    sfid = synth.sfload(str(sf2))
    for name, compose in PIECES.items():
        if args.only and name not in args.only:
            continue
        audio = render(compose(rng), synth, sfid)
        write_ogg(finish(hall(audio)), MUSIC / f"{name}.ogg", quality=4)
    if not args.only or "sounds" in args.only:
        for name, score, tail in sounds():
            audio = render(score, synth, sfid, tail=tail)
            write_ogg(finish(hall(audio, seconds=1.2, wet=0.15), fade_out=0.3, peak=0.65), SOUNDS / f"{name}.ogg")


if __name__ == "__main__":
    sys.exit(main())
