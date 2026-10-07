"""Render the same soldiers and towns in three looks, so that we can choose one.

    xvfb-run -a -s "-screen 0 1600x900x24" python tools/style_demo/style_demo.py OUT_DIR
"""

import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

import numpy as np  # noqa: E402
from panda3d.core import (AntialiasAttrib, CullFaceAttrib, NodePath, Shader, Vec3,  # noqa: E402
                          loadPrcFileData)

loadPrcFileData("", "window-type offscreen\nwin-size 1600 900\naudio-library-name null\nsync-video 0\n"
                    "framebuffer-multisample 1\nmultisamples 4\ntextures-power-2 none")
from direct.showbase.ShowBase import ShowBase  # noqa: E402

from crowns.render import models as m  # noqa: E402
from crowns.render.atmosphere import SUN, Sky, Sun  # noqa: E402
from crowns.render.figures import geom_node  # noqa: E402
from crowns.render.post import PostProcess  # noqa: E402

HERE = Path(__file__).resolve().parent
STYLES = ["A  Miniaturi pictate (figurine de colecție, contur de cerneală)",
          "B  Pictură realistă (lumină naturală, fără contur)",
          "C  Manuscris iluminat (culori plate, cerneală groasă, hârtie)"]
WALLACHIA = (0.886, 0.698, 0.204)
WALLACHIA_2 = (0.20, 0.32, 0.62)
OTTOMAN = (0.21, 0.48, 0.36)
HUNGARY = (0.77, 0.31, 0.25)


TOWN = (14.0, 92.0)


def ground_height(x, y):
    """A gentle land with a flat-topped hill for the town."""
    r = math.hypot(x - TOWN[0], y - TOWN[1])
    t = min(1.0, max(0.0, (r - 42) / 45))
    hill = 9.0 * (1 - t * t * (3 - 2 * t))
    return hill + 1.0 * math.sin(x * 0.03) * math.cos(y * 0.025) * min(1.0, r / 60)


class Demo(ShowBase):
    def __init__(self):
        super().__init__()
        self.render.setAntialias(AntialiasAttrib.MMultisample)
        self.setBackgroundColor(0.79, 0.82, 0.82)
        self.post = PostProcess(self)
        self.camLens.setFov(38)
        self.camLens.setNearFar(0.3, 6000)
        self.shader = Shader.load(Shader.SL_GLSL, str(HERE / "demo.vert"), str(HERE / "demo.frag"))
        self.root = self.render.attachNewNode("demo")
        self.root.setShader(self.shader)
        self.root.setShaderInputs(sun_dir=SUN, outline=0.0, haze=Vec3(0.79, 0.82, 0.82), fog=1 / 1600.0, style=0.0,
                                  ground=0.0)
        self.sun = Sun(self.render, SUN, size=4096, back=600.0)
        self.root.setLight(self.sun.root)
        self.sky = Sky(self.camera, self.render, SUN)
        self.inks = []
        self.models = {}
        self._ground()

    def _ground(self):
        n, cell = 160, 5.0
        xs = np.arange(n + 1) * cell - n * cell / 2
        ys = np.arange(n + 1) * cell - n * cell / 2 + 60
        h = np.array([[ground_height(x, y) for x in xs] for y in ys])
        X, Y = np.meshgrid(xs, ys)
        P = np.dstack([X, Y, h])
        a, b, c, d = P[:-1, :-1], P[:-1, 1:], P[1:, 1:], P[1:, :-1]
        tris = np.concatenate([np.stack([a, b, c], axis=2).reshape(-1, 3, 3),
                               np.stack([a, c, d], axis=2).reshape(-1, 3, 3)])
        cols = np.tile(np.array([0.50, 0.57, 0.30, 1.0]), (len(tris), 1))
        g = self.root.attachNewNode(geom_node("ground", tris, cols))
        g.setShaderInput("ground", 1.0)

    def model(self, key, build):
        if key not in self.models:
            part = build()
            verts, colors = part.arrays()
            self.models[key] = (geom_node(key, verts, colors), geom_node(key + "-ink", verts, colors, smooth=True))
        return self.models[key]

    def place(self, key, build, x, y, heading=0.0, scale=1.0, ink=0.035):
        body, ink_geom = self.model(key, build)
        node = self.root.attachNewNode(key)
        node.setPos(x, y, ground_height(x, y))
        node.setH(heading)
        node.setScale(scale)
        node.attachNewNode(body)
        outline = node.attachNewNode(ink_geom)
        outline.setShaderInput("outline", ink)
        outline.setAttrib(CullFaceAttrib.make(CullFaceAttrib.MCullCounterClockwise), 1)
        outline.hide(self.sun.light.getCameraMask())
        self.inks.append((outline, ink))
        return node

    def set_style(self, k):
        self.root.setShaderInput("style", float(k))
        for node, ink in self.inks:
            if k == 1:
                node.hide()
            else:
                node.show()
                node.setShaderInput("outline", ink * (1.9 if k == 2 else 1.0))
        self.post.set_grade(0.6 if k == 1 else 1.0)

    def shot(self, path, pos, look, span):
        self.camera.setPos(*pos)
        self.camera.lookAt(*look)
        self.sun.follow(look[0], look[1], look[2], span)
        for _ in range(3):
            self.graphicsEngine.renderFrame()
        self.win.saveScreenshot(str(path))


def armies(demo):
    rng = np.random.default_rng(3)
    coats = [(0.62, 0.52, 0.38), (0.70, 0.62, 0.48), (0.55, 0.45, 0.34)]
    # Wallachian levy spearmen in fur caps, with round shields in the prince's colours
    for k, coat in enumerate(coats):
        demo.model(f"levy{k}", lambda coat=coat, k=k: m.man(coat, WALLACHIA, head="fur" if k != 1 else "cap",
                                                            shield_kind="round",
                                                            shield_colors=(WALLACHIA, WALLACHIA_2)))
    for r in range(4):
        for f in range(7):
            k = int(rng.integers(3))
            demo.place(f"levy{k}", None, -16 + f * 1.05 + rng.uniform(-0.1, 0.1), -4 - r * 1.3, heading=0)
    # Wallachian archers in front
    demo.model("archer", lambda: m.man((0.40, 0.42, 0.30), WALLACHIA, head="fur", weapon="bow"))
    for f in range(6):
        demo.place("archer", None, -15 + f * 1.4, 1.5, heading=rng.uniform(-8, 8))
    # boyar horsemen: mail, spangenhelm, kite shields, caparisons in the prince's colours
    demo.model("boyar", lambda: m.rider(m.horse((0.42, 0.28, 0.18), WALLACHIA, WALLACHIA_2),
                                        m.man(WALLACHIA_2, WALLACHIA, head="spangen", body="mail", weapon="lance",
                                              seated=True, shield_kind="kite", shield_colors=(WALLACHIA, WALLACHIA_2))))
    for f in range(3):
        demo.place("boyar", None, -2 + f * 1.6, -3 - (f % 2) * 0.6, heading=-4)
    # Hungarian knights: bascinets, heater shields, red and silver
    demo.model("knight", lambda: m.rider(m.horse((0.86, 0.84, 0.80), HUNGARY, (0.92, 0.92, 0.9)),
                                         m.man((0.92, 0.92, 0.90), HUNGARY, head="bascinet", body="mail",
                                               weapon="lance", seated=True, shield_kind="heater",
                                               shield_colors=(HUNGARY, (0.93, 0.93, 0.9)))))
    for f in range(2):
        demo.place("knight", None, 3.6 + f * 1.7, -2.5, heading=6)
    # janissaries: white börk, long blue kaftans, bows
    for k, coat in enumerate([(0.22, 0.30, 0.55), (0.62, 0.18, 0.16)]):
        demo.model(f"jan{k}", lambda coat=coat: m.man(coat, (0.85, 0.75, 0.4), head="bork", body="kaftan",
                                                      weapon="bow", beard=True))
    for r in range(3):
        for f in range(6):
            demo.place(f"jan{(r + f) % 2 if r == 0 else 0}", None, -14 + f * 1.15, 14 + r * 1.3, heading=180)
    # sipahis: turbaned helmets, round red shields, lances, horses in green
    demo.model("sipahi", lambda: m.rider(m.horse((0.66, 0.50, 0.34), OTTOMAN, (0.9, 0.8, 0.4)),
                                         m.man((0.70, 0.18, 0.15), OTTOMAN, head="turban", body="mail",
                                               weapon="lance", seated=True, shield_kind="round",
                                               shield_colors=((0.72, 0.16, 0.14), (0.9, 0.8, 0.4)))))
    for f in range(3):
        demo.place("sipahi", None, -1 + f * 1.7, 16 + (f % 2) * 0.7, heading=175)


def label(path, text, size=(800, 450)):
    from PIL import Image, ImageDraw, ImageFont
    img = Image.open(path).convert("RGB").resize(size, Image.LANCZOS)
    draw = ImageDraw.Draw(img)
    font = ImageFont.truetype(str(ROOT / "crowns/assets/fonts/EBGaramond.ttf"), 24)
    w = draw.textlength(text, font=font)
    draw.rectangle((0, 0, w + 24, 40), fill=(244, 236, 214))
    draw.text((12, 6), text, fill=(60, 40, 20), font=font)
    return img


def sheet(images, cols, out):
    from PIL import Image
    w, h = images[0].size
    rows = math.ceil(len(images) / cols)
    s = Image.new("RGB", (cols * w + (cols + 1) * 8, rows * h + (rows + 1) * 8), (90, 70, 50))
    for k, img in enumerate(images):
        s.paste(img, (8 + (k % cols) * (w + 8), 8 + (k // cols) * (h + 8)))
    s.save(out)


def main(out):
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    demo = Demo()
    armies(demo)
    demo.place("town-hungarian", lambda: m.town("hungarian"), *TOWN, heading=10, ink=0.12)
    close, wide = [], []
    for k in range(3):
        demo.set_style(k)
        demo.shot(out / f"close_{k}.png", (9, 7.5, 3.6), (-6, -3.5, 1.0), 60)
        demo.shot(out / f"wide_{k}.png", (-6, -34, 9), (6, 40, 9), 240)
        close.append(label(out / f"close_{k}.png", STYLES[k]))
        wide.append(label(out / f"wide_{k}.png", STYLES[k]))
        print("style", k, "done")
    sheet(close, 1, out / "soldati_variante.png")
    sheet(wide, 1, out / "scena_variante.png")
    # the four kinds of town, each alone on the hill, in the first look
    demo.set_style(0)
    demo.root.find("**/town-hungarian").hide()
    for node in demo.root.getChildren():
        if node.getName() not in ("ground",):
            node.hide()
    towns = []
    names = {"wallachian": "Târg valah cu palisadă și curte domnească", "hungarian": "Cetate ungurească de piatră",
             "byzantine": "Oraș bizantin, ziduri cu brâie de cărămidă", "ottoman": "Oraș otoman cu geamie și han"}
    for kind in ("wallachian", "hungarian", "byzantine", "ottoman"):
        node = demo.place(f"town-{kind}", lambda kind=kind: m.town(kind), *TOWN, heading=10, ink=0.12)
        demo.shot(out / f"town_{kind}.png", (TOWN[0] + 62, TOWN[1] - 66, 52), (TOWN[0], TOWN[1], 10), 160)
        towns.append(label(out / f"town_{kind}.png", names[kind]))
        node.hide()
    sheet(towns, 2, out / "orase_variante.png")
    print("ok")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "style_demo_out")
