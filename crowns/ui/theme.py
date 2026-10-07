"""The look of the windows: parchment, ink and gold, like the map they lie on."""

from pathlib import Path

import numpy as np
from direct.gui import DirectGuiGlobals as DGG
from direct.gui.DirectGui import DirectButton, DirectFrame, DirectLabel
from panda3d.core import SamplerState, TextNode, Texture, TransparencyAttrib

FONTS = Path(__file__).resolve().parent.parent / "assets" / "fonts"
INK = (0.20, 0.13, 0.07, 1)
FADED = (0.45, 0.37, 0.28, 1)
RUBRIC = (0.62, 0.14, 0.08, 1)
GOLD = (0.62, 0.45, 0.12, 1)
PAPER = (0.95, 0.90, 0.78, 1)
SHADOW = (0.0, 0.0, 0.0, 0.35)


class Theme:
    def __init__(self, loader):
        self.text = loader.loadFont(str(FONTS / "EBGaramond.ttf"))
        self.italic = loader.loadFont(str(FONTS / "EBGaramond-Italic.ttf"))
        self.title = loader.loadFont(str(FONTS / "Cinzel.ttf"))
        for f in (self.text, self.italic, self.title):
            f.setPixelsPerUnit(72)
        self.paper = _parchment(512, 512, seed=1)
        self.button_up = _parchment(256, 64, seed=2, tone=0.93)
        self.button_hover = _parchment(256, 64, seed=2, tone=1.0)
        self.button_down = _parchment(256, 64, seed=2, tone=0.82)
        self.click = None          # a sound for the buttons, if the game has sound

    # --- pieces ---------------------------------------------------------------------------------

    def panel(self, parent, left, right, bottom, top, alpha=0.96):
        """A sheet of parchment with a double ink rule round it."""
        frame = DirectFrame(parent=parent, frameSize=(left, right, bottom, top), frameTexture=self.paper,
                            frameColor=(1, 1, 1, alpha), state=DGG.NORMAL)
        frame.setTransparency(TransparencyAttrib.M_alpha)
        DirectFrame(parent=frame, frameSize=(left + 0.006, right + 0.006, bottom - 0.008, top - 0.008),
                    frameColor=SHADOW).setBin("background", 0)
        for inset, width in ((0.008, 0.004), (0.017, 0.0016)):
            self.rule(frame, left + inset, right - inset, top - inset, width)
            self.rule(frame, left + inset, right - inset, bottom + inset, width)
            self.rule(frame, left + inset, left + inset, bottom + inset, width, vertical=(bottom + inset, top - inset))
            self.rule(frame, right - inset, right - inset, bottom + inset, width,
                      vertical=(bottom + inset, top - inset))
        return frame

    def rule(self, parent, x0, x1, y, width, vertical=None, color=INK):
        if vertical:
            y0, y1 = vertical
            return DirectFrame(parent=parent, frameSize=(x0 - width / 2, x0 + width / 2, y0, y1), frameColor=color)
        return DirectFrame(parent=parent, frameSize=(x0, x1, y - width / 2, y + width / 2), frameColor=color)

    def label(self, parent, text, x, y, scale=0.04, color=INK, font=None, align=TextNode.ALeft, wrap=None):
        lab = DirectLabel(parent=parent, text=text, pos=(x, 0, y), scale=scale, text_fg=color,
                          text_font=font or self.text, text_align=align, frameColor=(0, 0, 0, 0),
                          text_wordwrap=wrap)
        return lab

    def heading(self, parent, text, x, y, scale=0.055, align=TextNode.ALeft, color=INK):
        return self.label(parent, text, x, y, scale, color, self.title, align)

    def button(self, parent, text, x, y, command, args=(), width=0.5, scale=0.036, enabled=True, align="center"):
        """A parchment button `width` wide (in screen units) whose left edge is at x (or centred on x)."""
        h = 0.034 / scale
        half = width / scale / 2
        left = x if align == "left" else x - width / 2
        b = DirectButton(parent=parent, text=text, text_font=self.text, text_fg=INK if enabled else FADED,
                         text_scale=1.0, text_pos=(0, -0.3), scale=scale, pos=(left + width / 2, 0, y),
                         frameSize=(-half, half, -h * 0.55, h * 0.75),
                         frameTexture=(self.button_up, self.button_down, self.button_hover, self.button_up),
                         frameColor=(1, 1, 1, 1) if enabled else (1, 1, 1, 0.55), relief=DGG.FLAT,
                         command=command, extraArgs=list(args), pressEffect=0,
                         state=DGG.NORMAL if enabled else DGG.DISABLED, clickSound=self.click, rolloverSound=None)
        b.setTransparency(TransparencyAttrib.M_alpha)
        if enabled:
            self.rule(b, -half, half, -h * 0.55, 0.06)
        return b


def _parchment(w, h, seed=0, tone=0.97):
    """A parchment texture: warm paper with soft blotches and fibres, darker towards the edges."""
    rng = np.random.default_rng(seed)
    y, x = np.mgrid[0:h, 0:w] / max(w, h)
    noise = np.zeros((h, w))
    for scale, amp in ((4, 0.5), (9, 0.3), (23, 0.15), (61, 0.08)):
        grid = rng.random((int(scale * h / max(w, h)) + 2, scale + 2))
        gy = np.linspace(0, grid.shape[0] - 1.001, h)
        gx = np.linspace(0, grid.shape[1] - 1.001, w)
        y0, x0 = gy.astype(int), gx.astype(int)
        fy, fx = (gy - y0)[:, None], (gx - x0)[None, :]
        fy, fx = fy * fy * (3 - 2 * fy), fx * fx * (3 - 2 * fx)
        a = grid[y0][:, x0]
        b = grid[y0][:, x0 + 1]
        c = grid[y0 + 1][:, x0]
        d = grid[y0 + 1][:, x0 + 1]
        noise += amp * ((a * (1 - fx) + b * fx) * (1 - fy) + (c * (1 - fx) + d * fx) * fy)
    noise /= 1.03
    yy, xx = np.mgrid[0:h, 0:w]
    edge = np.minimum(np.minimum(xx, w - 1 - xx) / w, np.minimum(yy, h - 1 - yy) / h)
    vignette = np.clip(edge * 9, 0, 1) ** 0.6
    base = np.array([0.95, 0.89, 0.75]) * tone
    rgb = base[None, None, :] * (0.88 + 0.16 * noise[..., None]) * (0.86 + 0.14 * vignette[..., None])
    rgba = np.concatenate([np.clip(rgb, 0, 1), np.ones((h, w, 1))], axis=2)
    img = (rgba * 255).astype(np.uint8)
    tex = Texture("parchment")
    tex.setup2dTexture(w, h, Texture.T_unsigned_byte, Texture.F_rgba8)
    tex.setRamImageAs(np.ascontiguousarray(np.flipud(img)).tobytes(), "RGBA")
    tex.setMinfilter(SamplerState.FT_linear)
    tex.setMagfilter(SamplerState.FT_linear)
    return tex
