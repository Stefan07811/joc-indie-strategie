"""Finer miniatures for the battlefield and the towns.

Men of the different traditions in their own dress (the Wallachian peasant's sukman and fur cap, the
boyar's mail and kite shield, the janissary's white börk and long kaftan, the sipahi's turbaned helmet,
the Latin knight's bascinet and heater shield), horses with their caparisons, and towns built the way
each people built them: a Wallachian market town behind its palisade, a Hungarian stone castle, a
Byzantine city in banded brick and stone, an Ottoman town of domes and minarets.

Everything is built in code from simple solids, in metres, the men standing on (0, 0, 0) and facing +y.
"""

import math

import numpy as np

from .figures import Builder, _rot

SKIN = (0.84, 0.66, 0.52)
HAIR = (0.24, 0.16, 0.10)
STEEL = (0.68, 0.70, 0.74)
MAIL = (0.50, 0.52, 0.55)
LEATHER = (0.40, 0.27, 0.16)
WOOD = (0.50, 0.36, 0.22)
LINEN = (0.88, 0.85, 0.76)
FELT = (0.95, 0.93, 0.87)
FUR = (0.30, 0.22, 0.15)
GOLD = (0.86, 0.68, 0.26)
BOOT = (0.22, 0.16, 0.11)


class Part(Builder):
    """A Builder with the solids a miniature needs."""

    def ellipsoid(self, centre, radii, color, rings=6, segments=10, rot=(0, 0, 0), top=1.0, bottom=-1.0):
        r = _rot(*rot)
        c = np.array(centre, float)
        lats = np.linspace(math.asin(bottom), math.asin(top), rings + 1)

        def p(lat, lon):
            return r @ np.array([math.cos(lat) * math.cos(lon) * radii[0], math.cos(lat) * math.sin(lon) * radii[1],
                                 math.sin(lat) * radii[2]]) + c
        for i in range(rings):
            for j in range(segments):
                l0, l1 = 2 * math.pi * j / segments, 2 * math.pi * (j + 1) / segments
                self.quad(p(lats[i], l0), p(lats[i], l1), p(lats[i + 1], l1), p(lats[i + 1], l0), color)

    def limb(self, p0, p1, r0, r1, color, sides=7, cap=True):
        """A tapered cylinder from p0 to p1 (a cone if r1 is 0)."""
        p0, p1 = np.array(p0, float), np.array(p1, float)
        d = p1 - p0
        d /= np.linalg.norm(d)
        tmp = np.array([1.0, 0, 0]) if abs(d[2]) > 0.9 else np.array([0, 0, 1.0])
        u = np.cross(d, tmp)
        u /= np.linalg.norm(u)
        v = np.cross(d, u)
        angles = [2 * math.pi * k / sides for k in range(sides)]
        lo = [p0 + r0 * (math.cos(a) * u + math.sin(a) * v) for a in angles]
        hi = [p1 + r1 * (math.cos(a) * u + math.sin(a) * v) for a in angles]
        for k in range(sides):
            n = (k + 1) % sides
            if r1 > 0:
                self.quad(lo[k], lo[n], hi[n], hi[k], color)
            else:
                self.tri(lo[k], lo[n], p1, color)
        if cap:
            for k in range(sides):
                n = (k + 1) % sides
                self.tri(p0, lo[n], lo[k], color)
                if r1 > 0:
                    self.tri(p1, hi[k], hi[n], color)

    def face(self, pts, color, toward):
        """A flat convex polygon, its front turned toward the direction `toward`."""
        pts = [np.array(p, float) for p in pts]
        c = sum(pts) / len(pts)
        t = np.array(toward, float)
        for a, b in zip(pts, pts[1:] + pts[:1]):
            if np.dot(np.cross(a - c, b - c), t) >= 0:
                self.tri(c, a, b, color)
            else:
                self.tri(c, b, a, color)

    def slab(self, outline, color, thickness=0.03, back=None, rim=None):
        """A flat plate standing in the x-z plane, its face toward +y: a shield, a banner."""
        front = [(x, thickness / 2, z) for x, z in outline]
        rear = [(x, -thickness / 2, z) for x, z in outline]
        self.face(front, color, (0, 1, 0))
        self.face(rear, back or color, (0, -1, 0))
        for k in range(len(outline)):
            n = (k + 1) % len(outline)
            self.face([rear[k], rear[n], front[n], front[k]], rim or back or color,
                      (outline[k][0] + outline[n][0], 0, outline[k][1] + outline[n][1]))

    def add(self, other, rot=(0, 0, 0), at=(0, 0, 0), scale=1.0):
        r = _rot(*rot)
        o = np.array(at, float)
        for v, color in other.tris:
            self.tris.append(((v * scale) @ r.T + o, color))


# --- shields ----------------------------------------------------------------------------------------

def _ring(r, n=14, z0=0.0):
    return [(r * math.cos(2 * math.pi * k / n), z0 + r * math.sin(2 * math.pi * k / n)) for k in range(n)]


def shield(kind, field, charge, rim=WOOD):
    """A shield in the x-z plane facing +y, painted with a simple device in the realm's colours."""
    s = Part()
    if kind == "round":
        s.slab(_ring(0.30), field, 0.04, back=WOOD, rim=rim)
        s.ellipsoid((0, 0.03, 0), (0.08, 0.05, 0.08), STEEL, rings=4, segments=8, bottom=0.0, rot=(0, -90, 0))
        s.slab([(x * 0.62, z * 0.62) for x, z in _ring(0.30)], charge, 0.045)
        s.slab(_ring(0.11), field, 0.05)
    elif kind == "kite":
        outline = [(0, -0.55)] + [(0.24 * math.sin(a), 0.12 + 0.18 * math.cos(a)) for a in np.linspace(1.6, -1.6, 9)]
        s.slab(outline, field, 0.04, back=WOOD, rim=rim)
        s.slab([(-0.05, 0.27), (0.05, 0.27), (0.05, -0.45), (-0.05, -0.45)], charge, 0.045)
        s.slab([(-0.2, 0.14), (0.2, 0.14), (0.2, 0.05), (-0.2, 0.05)], charge, 0.045)
    else:   # the Latin heater shield, divided per pale
        outline = [(-0.26, 0.28), (0.26, 0.28), (0.25, 0.0), (0.18, -0.2), (0.0, -0.36), (-0.18, -0.2), (-0.25, 0.0)]
        s.slab(outline, field, 0.04, back=WOOD, rim=rim)
        s.slab([(0.0, 0.28), (0.26, 0.28), (0.25, 0.0), (0.18, -0.2), (0.0, -0.36)], charge, 0.045)
    return s


# --- men ---------------------------------------------------------------------------------------------

def man(coat, accent, legs=(0.36, 0.30, 0.24), head="cap", body="tunic", shield_kind=None, weapon="spear",
        beard=True, seated=False, shield_colors=None, rng=None):
    """A man in his gear. coat: the main garment's colour; accent: the realm's second colour."""
    p = Part()
    rng = rng or np.random.default_rng(0)
    lift = 0.0
    if not seated:
        for side in (-1, 1):
            x = 0.1 * side
            p.box((x, 0.04, 0.05), (0.11, 0.24, 0.1), BOOT)
            p.limb((x, 0, 0.08), (x, 0, 0.5), 0.065, 0.075, BOOT if body == "kaftan" else legs)
            p.limb((x, 0, 0.5), (x, 0, 0.9), 0.075, 0.09, legs)
    else:
        lift = 0.0
        for side in (-1, 1):
            hip, knee, foot = (0.12 * side, 0, 0.92), (0.28 * side, 0.22, 0.72), (0.3 * side, 0.12, 0.32)
            p.limb(hip, knee, 0.09, 0.075, legs)
            p.limb(knee, foot, 0.07, 0.06, BOOT)
            p.box((foot[0], foot[1] + 0.06, foot[2] - 0.03), (0.1, 0.22, 0.08), BOOT)
    # the garment: a long kaftan, a knee-length tunic or coat, mail
    if body == "kaftan":
        p.limb((0, 0, 0.12 + lift), (0, 0, 0.95), 0.30, 0.19, coat, sides=10)
        p.box((0, 0.2, 0.55), (0.06, 0.03, 0.85), accent)
    elif not seated:
        p.limb((0, 0, 0.48), (0, 0, 0.95), 0.27, 0.19, MAIL if body == "mail" else coat, sides=10)
        if body == "mail":
            p.limb((0, 0, 0.55), (0, 0, 0.95), 0.275, 0.195, coat, sides=10)   # surcoat over the mail
    else:
        p.limb((0, 0, 0.82), (0, 0, 0.98), 0.24, 0.2, coat, sides=10)
    torso = MAIL if body == "mail" else coat
    p.limb((0, 0, 0.93), (0, 0, 1.40), 0.185, 0.21, coat if body in ("kaftan", "tunic") else torso, sides=10)
    if body == "mail":
        p.limb((0, 0, 0.98), (0, 0, 1.30), 0.19, 0.205, coat, sides=10)        # the surcoat's body
    p.limb((0, 0, 0.92), (0, 0, 0.99), 0.205, 0.205, accent if body != "mail" else LEATHER, sides=10)  # sash
    p.ellipsoid((0, 0, 1.38), (0.25, 0.15, 0.09), torso, rings=4, segments=10)
    p.limb((0, 0, 1.40), (0, 0, 1.52), 0.06, 0.06, SKIN, sides=6)
    # the head
    p.ellipsoid((0, 0.01, 1.62), (0.098, 0.108, 0.125), SKIN, rings=5, segments=10)
    p.box((0, 0.11, 1.61), (0.03, 0.04, 0.05), (0.78, 0.58, 0.45))
    if beard:
        p.ellipsoid((0, 0.06, 1.53), (0.085, 0.07, 0.07), HAIR, rings=4, segments=8)
    if head == "fur":         # the Wallachian peasant's tall fur cap
        p.limb((0, 0, 1.66), (0, -0.02, 1.86), 0.118, 0.105, FUR, sides=9)
        p.ellipsoid((0, -0.02, 1.86), (0.105, 0.105, 0.04), FUR, rings=3, segments=9, bottom=0.0)
    elif head == "spangen":   # a conical helmet with a nasal and a mail aventail
        p.limb((0, 0, 1.43), (0, 0, 1.64), 0.135, 0.118, MAIL, sides=10)
        p.limb((0, 0, 1.66), (0, 0, 1.96), 0.123, 0.0, STEEL, sides=10)
        p.box((0, 0.115, 1.63), (0.025, 0.02, 0.1), STEEL)
    elif head == "bascinet":  # the Latin knight's pointed bascinet with its visor
        p.limb((0, 0, 1.43), (0, 0, 1.6), 0.14, 0.125, MAIL, sides=10)
        p.ellipsoid((0, 0, 1.64), (0.125, 0.13, 0.17), STEEL, rings=5, segments=10, bottom=-0.1)
        p.limb((0, -0.03, 1.78), (0, -0.06, 1.88), 0.06, 0.0, STEEL, sides=8)
        p.limb((0, 0.08, 1.58), (0, 0.24, 1.6), 0.07, 0.0, STEEL, sides=8)      # the "hounskull" visor
    elif head == "kettle":
        p.ellipsoid((0, 0, 1.68), (0.12, 0.12, 0.11), STEEL, rings=4, segments=10, bottom=0.0)
        p.limb((0, 0, 1.68), (0, 0, 1.70), 0.21, 0.21, STEEL, sides=12)
    elif head == "bork":      # the janissary's white felt börk, its flap falling down his back
        p.limb((0, 0, 1.67), (0, -0.03, 2.02), 0.112, 0.1, FELT, sides=10)
        p.ellipsoid((0, -0.03, 2.02), (0.1, 0.1, 0.03), FELT, rings=2, segments=10, bottom=0.0)
        p.box((0, -0.14, 1.8), (0.17, 0.035, 0.42), FELT, pitch=-12)
        p.box((0, 0.11, 1.75), (0.05, 0.02, 0.12), GOLD)
    elif head == "turban":    # a turban wound about a spiked helmet
        p.ellipsoid((0, 0, 1.71), (0.14, 0.145, 0.085), FELT, rings=4, segments=10)
        p.limb((0, 0, 1.74), (0, 0, 1.98), 0.09, 0.0, STEEL, sides=8)
    else:                     # a plain cap
        p.ellipsoid((0, 0, 1.67), (0.108, 0.115, 0.08), coat, rings=3, segments=10, bottom=0.0)
    # the arms: the right hand holds the weapon, the left the shield or the bow
    rs, re, rh = (0.24, 0, 1.36), (0.29, 0.08, 1.12), (0.26, 0.25, 1.05)
    ls, le, lh = (-0.24, 0, 1.36), (-0.3, 0.08, 1.12), (-0.24, 0.26, 1.08)
    sleeve = MAIL if body == "mail" else coat
    for s, e, h in ((rs, re, rh), (ls, le, lh)):
        p.limb(s, e, 0.07, 0.06, sleeve)
        p.limb(e, h, 0.058, 0.05, sleeve)
        p.ellipsoid(h, (0.045, 0.05, 0.045), SKIN, rings=3, segments=6)
    if weapon == "spear":
        p.limb((rh[0], rh[1], 0.05), (rh[0], rh[1], 2.65), 0.018, 0.018, WOOD, sides=5)
        p.limb((rh[0], rh[1], 2.65), (rh[0], rh[1], 2.95), 0.035, 0.0, STEEL, sides=5)
    elif weapon == "lance":
        p.limb((rh[0], rh[1] - 0.6, 0.85), (rh[0], rh[1] + 0.9, 3.4), 0.025, 0.02, WOOD, sides=5)
        p.limb((rh[0], rh[1] + 0.9, 3.4), (rh[0], rh[1] + 1.0, 3.62), 0.035, 0.0, STEEL, sides=5)
        tip = np.array((rh[0], rh[1] + 0.82, 3.28))                   # a pennon below the point
        pennon = [tip, tip + (0, -0.08, -0.12), tip + (0, -0.55, -0.02)]
        p.face(pennon, accent, (1, 0, 0))
        p.face(pennon, accent, (-1, 0, 0))
    elif weapon == "sword":
        p.limb((rh[0], rh[1], 1.05), (rh[0], rh[1] + 0.12, 1.85), 0.022, 0.012, STEEL, sides=4)
        p.box((rh[0], rh[1], 1.08), (0.18, 0.03, 0.03), GOLD)
    if weapon == "bow":
        pts = [(lh[0], lh[1] + 0.12 * math.cos(t) ** 0.5 * 0 + 0.13 * (1 - (t / 1.2) ** 2), lh[2] + 0.62 * t / 1.2)
               for t in np.linspace(-1.2, 1.2, 9)]
        for a, b in zip(pts, pts[1:]):
            p.limb(a, b, 0.018, 0.018, WOOD, sides=4, cap=False)
        p.limb(pts[0], pts[-1], 0.004, 0.004, LINEN, sides=3, cap=False)
        p.limb((0.16, -0.17, 0.75), (0.2, -0.2, 1.25), 0.06, 0.07, LEATHER, sides=7)   # the quiver
        for k in range(4):
            p.limb((0.17 + 0.02 * k, -0.19, 1.2), (0.17 + 0.02 * k, -0.2, 1.38), 0.012, 0.012, LINEN, sides=3)
    else:
        p.limb((-0.2, 0.08, 0.95), (-0.24, 0.24, 0.55), 0.02, 0.015, LEATHER, sides=4)  # a sword at the hip
    if shield_kind:
        field, charge = shield_colors or (coat, accent)
        p.add(shield(shield_kind, field, charge), rot=(-8, 0, 0), at=(-0.3, 0.3, 1.0))
    return p


def horse(color=(0.55, 0.40, 0.28), caparison=None, accent=None, rng=None):
    p = Part()
    mane = (0.18, 0.12, 0.08)
    p.ellipsoid((0, 0, 1.22), (0.27, 0.78, 0.33), color, rings=7, segments=12)
    p.ellipsoid((0, 0.55, 1.28), (0.25, 0.3, 0.32), color, rings=5, segments=10)
    p.limb((0, 0.65, 1.38), (0, 0.98, 1.88), 0.17, 0.11, color, sides=9)
    p.limb((0, 0.98, 1.92), (0, 1.38, 1.66), 0.11, 0.065, color, sides=8)
    p.ellipsoid((0, 1.38, 1.64), (0.07, 0.08, 0.07), color, rings=3, segments=6)
    for side in (-1, 1):
        p.limb((0.05 * side, 1.0, 1.98), (0.06 * side, 0.96, 2.14), 0.03, 0.0, color, sides=4)
    p.box((0, 0.8, 1.72), (0.06, 0.5, 0.22), mane, pitch=-55)
    for side in (-1, 1):
        x = 0.15 * side
        for (top, knee, hoof) in (((x, 0.55, 1.05), (x, 0.62, 0.52), (x, 0.58, 0.06)),
                                  ((x, -0.55, 1.08), (x, -0.66, 0.6), (x, -0.56, 0.06))):
            p.limb(top, knee, 0.085, 0.055, color, sides=6)
            p.limb(knee, hoof, 0.05, 0.045, color, sides=6)
            p.limb((hoof[0], hoof[1], 0.0), (hoof[0], hoof[1], 0.1), 0.06, 0.055, (0.15, 0.12, 0.1), sides=6)
    p.limb((0, -0.76, 1.38), (0, -0.98, 0.78), 0.07, 0.035, mane, sides=6)
    if caparison:
        p.limb((0, -0.2, 0.92), (0, -0.2, 1.42), 0.36, 0.31, caparison, sides=12, cap=False)
        p.limb((0, 0.35, 0.92), (0, 0.35, 1.45), 0.36, 0.31, caparison, sides=12, cap=False)
        p.limb((0, -0.2, 0.92), (0, -0.2, 0.98), 0.365, 0.36, accent or caparison, sides=12, cap=False)
        p.limb((0, 0.35, 0.92), (0, 0.35, 0.98), 0.365, 0.36, accent or caparison, sides=12, cap=False)
    p.box((0, 0.0, 1.57), (0.42, 0.55, 0.1), LEATHER)
    return p


def rider(horse_part, man_part):
    p = Part()
    p.add(horse_part)
    p.add(man_part, at=(0, 0.0, 0.68))
    return p


# --- buildings ----------------------------------------------------------------------------------------

STONE = (0.74, 0.70, 0.62)
DARK_STONE = (0.56, 0.53, 0.47)
BRICK = (0.66, 0.36, 0.26)
PLASTER = (0.91, 0.87, 0.77)
TIMBER = (0.52, 0.40, 0.28)
TILE = (0.68, 0.30, 0.20)
SHINGLE = (0.38, 0.30, 0.24)
LEAD = (0.56, 0.60, 0.64)
THATCH = (0.66, 0.56, 0.34)


def gabled(p, x, y, w, d, h, walls, roof, yaw=0.0, pitch_h=None, z=0.0):
    """A house: walls w x d x h, a gabled roof along its length."""
    rh = pitch_h if pitch_h is not None else w * 0.55
    c, s = math.cos(math.radians(yaw)), math.sin(math.radians(yaw))

    def q(lx, ly, lz):
        return (x + lx * c - ly * s, y + lx * s + ly * c, z + lz)
    p.box((x, y, z + h / 2), (w, d, h), walls, yaw=yaw)
    ow, od = w / 2 + 0.25, d / 2 + 0.25
    p.quad(q(-ow, -od, h - 0.15), q(0, -od, h + rh), q(0, od, h + rh), q(-ow, od, h - 0.15), roof)
    p.quad(q(ow, od, h - 0.15), q(0, od, h + rh), q(0, -od, h + rh), q(ow, -od, h - 0.15), roof)
    p.quad(q(-ow, od, h - 0.15), q(0, od, h + rh), q(0, -od, h + rh), q(-ow, -od, h - 0.15), roof)   # under side
    p.quad(q(ow, -od, h - 0.15), q(0, -od, h + rh), q(0, od, h + rh), q(ow, od, h - 0.15), roof)
    p.tri(q(-w / 2, -d / 2, h), q(w / 2, -d / 2, h), q(0, -d / 2, h + rh - 0.1), walls)
    p.tri(q(w / 2, d / 2, h), q(-w / 2, d / 2, h), q(0, d / 2, h + rh - 0.1), walls)
    # a door and two windows on the long side
    p.box(q(w / 2 + 0.01, 0, 0.0)[:2] + (z + 0.9,), (0.04, 0.9, 1.8), (0.30, 0.20, 0.13), yaw=yaw)
    for k in (-1, 1):
        p.box(q(w / 2 + 0.01, k * d / 4, 0)[:2] + (z + h * 0.65,), (0.04, 0.5, 0.6), (0.20, 0.16, 0.12), yaw=yaw)


def crenels(p, a, b, z, color, size=0.9, thick=1.2):
    """Merlons along the top of a wall from a to b at height z."""
    a, b = np.array(a, float), np.array(b, float)
    length = np.linalg.norm(b - a)
    yaw = math.degrees(math.atan2(b[1] - a[1], b[0] - a[0]))
    n = max(1, int(length / (size * 2)))
    for k in range(n):
        t = (k + 0.5) / n
        c = a + (b - a) * t
        p.box((c[0], c[1], z + size / 2), (size, thick, size), color, yaw=yaw)


def wall(p, a, b, height, thick, color, top=None, bands=None):
    a, b = np.array(a, float), np.array(b, float)
    length = np.linalg.norm(b - a)
    yaw = math.degrees(math.atan2(b[1] - a[1], b[0] - a[0]))
    c = (a + b) / 2
    p.box((c[0], c[1], height / 2), (length, thick, height), color, yaw=yaw)
    if bands:   # courses of brick laid through the stone, as the Byzantines built
        for z in np.arange(1.5, height - 0.5, 1.6):
            p.box((c[0], c[1], z), (length + 0.02, thick + 0.04, 0.35), bands, yaw=yaw)
    crenels(p, a, b, height, top or color, thick=thick * 0.45)


def round_tower(p, x, y, r, h, color, roof=None, merlons=True):
    p.limb((x, y, 0), (x, y, h), r, r * 0.92, color, sides=14)
    if roof:
        p.limb((x, y, h), (x, y, h + r * 2.2), r * 1.15, 0.0, roof, sides=14)
    elif merlons:
        for k in range(8):
            a = 2 * math.pi * k / 8
            p.box((x + math.cos(a) * r * 0.85, y + math.sin(a) * r * 0.85, h + 0.45), (0.8, 0.8, 0.9), color,
                  yaw=math.degrees(a))


def square_tower(p, x, y, w, h, color, roof=None, bands=None):
    p.box((x, y, h / 2), (w, w, h), color)
    if bands:
        for z in np.arange(1.5, h - 0.5, 1.6):
            p.box((x, y, z), (w + 0.04, w + 0.04, 0.35), bands)
    if roof:
        p.limb((x, y, h), (x, y, h + w * 1.1), w * 0.78, 0.0, roof, sides=4)
    else:
        for a, b in (((-1, -1), (1, -1)), ((1, -1), (1, 1)), ((1, 1), (-1, 1)), ((-1, 1), (-1, -1))):
            crenels(p, (x + a[0] * w / 2, y + a[1] * w / 2), (x + b[0] * w / 2, y + b[1] * w / 2), h, color,
                    thick=0.6)


def windows(p, x, y, z, w, n, along=0.0, color=(0.18, 0.14, 0.12)):
    for k in range(n):
        p.box((x, y, z + k * 2.2), (0.5, 0.5, 1.0), color, yaw=along)


def orthodox_church(p, x, y, big=1.0, walls=PLASTER, roof=LEAD):
    """A cross-in-square church with its drum and dome, as in Wallachia and Serbia."""
    p.box((x, y, 2.6 * big), (5.2 * big, 8.0 * big, 5.2 * big), walls)
    p.limb((x, y - 4.0 * big, 0), (x, y - 4.0 * big, 4.6 * big), 2.4 * big, 2.4 * big, walls, sides=12)  # the apse
    p.limb((x, y - 4.0 * big, 4.6 * big), (x, y - 4.0 * big, 5.6 * big), 2.5 * big, 0.6 * big, roof, sides=12)
    gabled(p, x, y, 5.4 * big, 8.2 * big, 5.2 * big, walls, roof, yaw=90, pitch_h=1.6 * big)
    p.limb((x, y, 6.2 * big), (x, y, 8.6 * big), 1.5 * big, 1.5 * big, walls, sides=12)
    p.ellipsoid((x, y, 8.6 * big), (1.65 * big, 1.65 * big, 1.5 * big), roof, rings=5, segments=12, bottom=0.0)
    p.limb((x, y, 10.0 * big), (x, y, 11.2 * big), 0.06, 0.06, GOLD, sides=4)
    p.box((x, y, 10.9 * big), (0.6 * big, 0.06, 0.06), GOLD)
    for k in range(3):
        p.box((x + 2.62 * big, y - 2 + 2 * k * big, 3.2 * big), (0.06, 0.5, 1.4), (0.2, 0.16, 0.13))


def gothic_church(p, x, y, big=1.0):
    p.box((x, y, 4.0 * big), (6.0 * big, 12.0 * big, 8.0 * big), STONE)
    gabled(p, x, y, 6.0 * big, 12.0 * big, 8.0 * big, STONE, TILE, yaw=90, pitch_h=5.0 * big)
    square_tower(p, x, y + 7.5 * big, 3.6 * big, 15.0 * big, STONE)
    p.limb((x, y + 7.5 * big, 15.0 * big), (x, y + 7.5 * big, 22.0 * big), 2.2 * big, 0.0, SHINGLE, sides=8)
    for k in range(4):
        p.box((x + 3.02 * big, y - 4.5 + 3 * k * big, 4.5 * big), (0.06, 0.9, 3.2), (0.25, 0.3, 0.42))


def mosque(p, x, y, big=1.0):
    p.box((x, y, 3.0 * big), (10.0 * big, 10.0 * big, 6.0 * big), PLASTER)
    p.limb((x, y, 6.0 * big), (x, y, 7.6 * big), 4.6 * big, 4.4 * big, PLASTER, sides=16)
    p.ellipsoid((x, y, 7.6 * big), (4.5 * big, 4.5 * big, 4.2 * big), LEAD, rings=6, segments=16, bottom=0.0)
    p.limb((x, y, 11.7 * big), (x, y, 12.8 * big), 0.08, 0.04, GOLD, sides=4)
    for dx in (-3.0, 0.0, 3.0):        # the portico with its little domes
        p.box((x + dx * big, y + 6.5 * big, 2.2 * big), (2.8 * big, 3.0 * big, 4.4 * big), PLASTER)
        p.ellipsoid((x + dx * big, y + 6.5 * big, 4.4 * big), (1.25 * big, 1.25 * big, 1.1 * big), LEAD,
                    rings=4, segments=10, bottom=0.0)
    mx, my = x + 6.2 * big, y + 5.6 * big     # the minaret
    p.limb((mx, my, 0), (mx, my, 4.0 * big), 1.1 * big, 1.1 * big, PLASTER, sides=8)
    p.limb((mx, my, 4.0 * big), (mx, my, 17.0 * big), 0.75 * big, 0.65 * big, PLASTER, sides=12)
    p.limb((mx, my, 13.0 * big), (mx, my, 13.6 * big), 1.15 * big, 1.15 * big, PLASTER, sides=12)
    p.limb((mx, my, 17.0 * big), (mx, my, 21.5 * big), 0.72 * big, 0.0, LEAD, sides=12)


def town(kind, seed=0):
    """A whole walled town of one tradition, about 70 m across, centred on (0, 0)."""
    rng = np.random.default_rng(seed)
    p = Part()
    p.limb((0, 0, -1.0), (0, 0, 0.05), 40.0, 38.0, (0.55, 0.48, 0.34), sides=24)   # trodden ground

    def houses(n, radius, walls_c, roof_c, size=(4.0, 6.0, 3.2), avoid=()):
        placed = list(avoid)
        for _ in range(n):
            for _ in range(30):
                r = rng.uniform(6, radius)
                a = rng.uniform(0, 2 * math.pi)
                x, y = math.cos(a) * r, math.sin(a) * r
                if all(math.hypot(x - px, y - py) > pr for px, py, pr in placed):
                    break
            placed.append((x, y, 6.5))
            w, d, h = (s * rng.uniform(0.85, 1.25) for s in size)
            wc = walls_c[rng.integers(len(walls_c))]
            gabled(p, x, y, w, d, h, wc, roof_c, yaw=math.degrees(a) + rng.uniform(-20, 20))

    if kind == "wallachian":
        # a market town behind an earthwork and an oak palisade, the prince's court with its tower
        n = 28
        for k in range(n):
            a0, a1 = 2 * math.pi * k / n, 2 * math.pi * (k + 1) / n
            for t in np.linspace(0, 1, 9)[:-1]:
                a = a0 + (a1 - a0) * t
                x, y = math.cos(a) * 32, math.sin(a) * 32
                h = rng.uniform(4.2, 4.8)
                p.limb((x, y, 0), (x, y, h), 0.28, 0.24, WOOD, sides=5)
                p.limb((x, y, h), (x, y, h + 0.5), 0.24, 0.0, WOOD, sides=5)
        for a in np.linspace(0, 2 * math.pi, 6, endpoint=False):
            x, y = math.cos(a) * 32, math.sin(a) * 32
            p.box((x, y, 3.5), (3.6, 3.6, 7.0), TIMBER)
            p.limb((x, y, 7.0), (x, y, 10.5), 3.0, 0.0, SHINGLE, sides=4)
        p.box((-6, -4, 3.0), (12.0, 8.0, 6.0), PLASTER)                                # the princely court
        gabled(p, -6, -4, 12.0, 8.0, 6.0, PLASTER, SHINGLE, pitch_h=3.0)
        square_tower(p, 2.0, -8.0, 4.0, 18.0, STONE, roof=SHINGLE)                   # like the Chindia tower
        orthodox_church(p, 10, 8, big=0.9)
        houses(16, 26, [TIMBER, PLASTER, (0.82, 0.78, 0.66)], SHINGLE, size=(4.0, 5.5, 2.8),
               avoid=[(-6, -4, 10), (2, -8, 5), (10, 8, 8)])
    elif kind == "hungarian":
        # a stone castle on its rock: curtain wall, square towers, a tall keep, a Gothic church
        pts = [(math.cos(a) * 31, math.sin(a) * 27) for a in np.linspace(0, 2 * math.pi, 9)[:-1]]
        for a, b in zip(pts, pts[1:] + pts[:1]):
            wall(p, a, b, 8.0, 2.2, STONE)
        for x, y in pts:
            square_tower(p, x, y, 5.0, 12.0, STONE, roof=TILE)
        square_tower(p, 31, 0, 6.0, 14.0, DARK_STONE)                                  # the gatehouse
        p.box((33.2, 0, 2.2), (0.3, 3.0, 4.4), (0.2, 0.15, 0.1))
        square_tower(p, -10, 6, 9.0, 26.0, STONE, roof=TILE)                           # the keep
        windows(p, -10 + 4.52, 6, 10, 9, 5, color=(0.15, 0.12, 0.1))
        gothic_church(p, 8, -6, big=1.0)
        houses(12, 22, [PLASTER, (0.86, 0.80, 0.66)], TILE, avoid=[(-10, 6, 10), (8, -6, 12)])
    elif kind == "byzantine":
        # the city in banded brick and stone: a walled circuit of square towers, a domed church
        pts = [(math.cos(a) * 33, math.sin(a) * 29) for a in np.linspace(0, 2 * math.pi, 11)[:-1]]
        for a, b in zip(pts, pts[1:] + pts[:1]):
            wall(p, a, b, 9.0, 2.6, (0.78, 0.72, 0.62), bands=BRICK)
        for x, y in pts:
            square_tower(p, x, y, 5.5, 13.0, (0.78, 0.72, 0.62), bands=BRICK)
        orthodox_church(p, 0, 2, big=1.6, walls=(0.80, 0.62, 0.48), roof=LEAD)
        houses(14, 24, [PLASTER, (0.86, 0.74, 0.6)], TILE, size=(5.0, 6.0, 3.6), avoid=[(0, 2, 13)])
    else:   # ottoman
        # an Ottoman town: the old walls, a mosque and its minaret, a han with its little domes, timbered houses
        pts = [(math.cos(a) * 32, math.sin(a) * 28) for a in np.linspace(0, 2 * math.pi, 9)[:-1]]
        for a, b in zip(pts, pts[1:] + pts[:1]):
            wall(p, a, b, 7.0, 2.2, (0.80, 0.74, 0.62))
        for x, y in pts:
            round_tower(p, x, y, 2.8, 10.0, (0.80, 0.74, 0.62))
        mosque(p, -4, -2, big=1.0)
        p.box((12, 10, 2.5), (10.0, 8.0, 5.0), (0.82, 0.74, 0.60))                    # the han
        for dx in (-3, 0, 3):
            for dy in (-2, 2):
                p.ellipsoid((12 + dx, 10 + dy, 5.0), (1.2, 1.2, 1.0), LEAD, rings=3, segments=8, bottom=0.0)
        houses(16, 24, [PLASTER, (0.92, 0.88, 0.80), TIMBER], TILE, size=(4.5, 6.0, 4.4),
               avoid=[(-4, -2, 12), (12, 10, 9)])
    return p
