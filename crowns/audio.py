"""Music and sounds: the pieces of tools/music.py, played by the mood of the realm, and short sounds for
what happens. If the machine has no sound, everything here quietly does nothing."""

from pathlib import Path

ASSETS = Path(__file__).resolve().parent / "assets"
MUSIC = ASSETS / "music"
SOUNDS = ASSETS / "sounds"
# what plays, by mood: the realm's tradition and whether it is at war
PLAYLISTS = {
    "choose": ["the_court", "the_danube", "the_crescent"],
    "west": ["the_danube", "the_court", "doina"],
    "vlach": ["doina", "the_danube", "the_court"],
    "east": ["the_crescent", "the_court", "the_danube"],
    "war": ["war_banners", "the_danube", "war_banners", "the_crescent"],
}
FADE = 3.0           # seconds to fade one piece into the next


def mood_of(campaign):
    tag = campaign.player
    if tag is None:
        return "choose"
    if campaign.wars_of(tag):
        return "war"
    tradition = campaign.tradition(tag)
    if tradition in ("ottoman", "steppe", "levant"):
        return "east"
    return "vlach" if tradition == "vlach" else "west"


class Audio:
    def __init__(self, base, volume=0.6):
        self.base = base
        self.volume = volume
        self.enabled = bool(base.musicManager and base.musicManager.isValid())
        self.tracks = {}
        self.sfx = {}
        self.current = None       # (name, sound)
        self.fading = []          # sounds fading out
        self.mood = None
        self.index = 0
        self.muted = False

    def _music(self, name):
        if name not in self.tracks:
            path = MUSIC / f"{name}.ogg"
            self.tracks[name] = self.base.loader.loadMusic(str(path)) if path.exists() else None
        return self.tracks[name]

    def set_mood(self, mood):
        if mood == self.mood or not self.enabled:
            return
        self.mood = mood
        self.index = 0
        self._play(PLAYLISTS[mood][0])

    def _play(self, name):
        sound = self._music(name)
        if sound is None:
            return
        if self.current is not None:
            if self.current[0] == name:
                return
            self.fading.append(self.current[1])
        sound.setVolume(0.0)
        sound.setLoop(False)
        sound.play()
        self.current = (name, sound)

    def update(self, dt):
        if not self.enabled:
            return
        target = 0.0 if self.muted else self.volume
        if self.current is not None:
            name, sound = self.current
            v = sound.getVolume()
            sound.setVolume(min(target, v + dt * target / FADE) if v < target else target)
            if sound.status() != sound.PLAYING:   # the piece is over: the next one
                playlist = PLAYLISTS[self.mood or "choose"]
                self.index = (self.index + 1) % len(playlist)
                self.current = None
                self._play(playlist[self.index])
        for sound in list(self.fading):
            v = sound.getVolume() - dt * self.volume / FADE
            if v <= 0:
                sound.stop()
                self.fading.remove(sound)
            else:
                sound.setVolume(v)

    def toggle(self):
        self.muted = not self.muted

    def play(self, name, volume=0.8):
        """A short sound: click, month, march, victory, defeat, event, build."""
        if not self.enabled or self.muted:
            return
        if name not in self.sfx:
            path = SOUNDS / f"{name}.ogg"
            self.sfx[name] = self.base.loader.loadSfx(str(path)) if path.exists() else None
        sound = self.sfx[name]
        if sound is not None:
            sound.setVolume(volume)
            sound.play()
