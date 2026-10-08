"""The painted pictures (made with Gemini and brought in by tools/import_art.py): ground textures, plants
and the realms' arms. Every one of them is optional: without it the game paints its own."""

from pathlib import Path

from panda3d.core import Filename, SamplerState, Texture, TexturePool

ART = Path(__file__).resolve().parent.parent / "assets" / "art"
GROUNDS = ("meadow", "steppe", "dirt", "mud", "rock", "forest")
TREES = ("tree_oak", "tree_beech", "tree_pine", "tree_poplar", "tree_willow")
BUSHES = ("bush_1", "bush_2", "grass_tuft")
ARMS = {"wallachia": "wallachia", "moldavia": "moldavia", "hungary": "hungary", "serbia": "serbia",
        "byzantium": "byzantium", "venice": "venice", "genoa": "genoa", "bosnia": "bosnia", "poland": "poland",
        "lithuania": "lithuania", "knights": "knights"}


def path(kind, name):
    ext = ".jpg" if kind == "ground" else ".png"
    p = ART / kind / f"{name}{ext}"
    return p if p.exists() else None


def texture(p, repeat=False):
    """A texture from a file, mipmapped and filtered; None if there is no file."""
    if p is None:
        return None
    tex = TexturePool.loadTexture(Filename.fromOsSpecific(str(p)))
    if tex is None:
        return None
    tex.setMinfilter(SamplerState.FT_linear_mipmap_linear)
    tex.setMagfilter(SamplerState.FT_linear)
    tex.setAnisotropicDegree(4)
    if repeat:
        tex.setWrapU(SamplerState.WM_repeat)
        tex.setWrapV(SamplerState.WM_repeat)
    else:
        tex.setWrapU(SamplerState.WM_clamp)
        tex.setWrapV(SamplerState.WM_clamp)
    return tex


def ground(name):
    return texture(path("ground", name), repeat=True)


def plant(name):
    return texture(path("plants", name))


def arms_of(tag):
    """The arms painted for a realm (the Ottomans share theirs), or None."""
    name = "ottoman" if tag.startswith("ott_") else ARMS.get(tag)
    return texture(path("arms", name)) if name else None


def blank():
    """A 1x1 white texture, for samplers that must be bound to something."""
    tex = Texture("blank")
    tex.setup2dTexture(1, 1, Texture.T_unsigned_byte, Texture.F_rgba8)
    tex.setRamImage(bytes([255, 255, 255, 255]))
    return tex
