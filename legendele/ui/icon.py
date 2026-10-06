"""The game's icon, drawn in code: the Heart of the Mountains, a red gem over snowy peaks, on a gold seal.

Used for the window and, saved as an .ico, for the Windows executable (tools/build_exe.py)."""

import io
import struct

import pygame

from . import theme

SIZES = (16, 32, 48, 64, 128, 256)


def draw(size=256):
    s = pygame.Surface((256, 256), pygame.SRCALPHA)
    pygame.draw.circle(s, theme.INK, (128, 128), 126)
    pygame.draw.circle(s, (206, 160, 72), (128, 128), 118)
    pygame.draw.circle(s, (58, 44, 32), (128, 128), 102)
    peaks = [(28, 190), (82, 96), (112, 140), (150, 70), (228, 190)]
    pygame.draw.polygon(s, (120, 116, 112), peaks)
    for top, left, right in (((82, 96), (64, 128), (100, 124)), ((150, 70), (124, 116), (176, 112))):
        pygame.draw.polygon(s, (240, 240, 236), [left, top, right])  # snow
    pygame.draw.polygon(s, theme.INK, peaks, 4)
    gem = [(128, 132), (152, 158), (128, 200), (104, 158)]
    pygame.draw.polygon(s, (204, 36, 40), gem)
    pygame.draw.polygon(s, (250, 120, 110), [(128, 132), (140, 158), (128, 158), (116, 158)])
    pygame.draw.polygon(s, theme.INK, gem, 4)
    pygame.draw.circle(s, (54, 40, 28), (128, 128), 102, 3)
    return s if size == 256 else pygame.transform.smoothscale(s, (size, size))


def ico_bytes(sizes=SIZES):
    """A Windows .ico holding one PNG per size (supported since Windows Vista)."""
    pngs = []
    for size in sizes:
        buf = io.BytesIO()
        pygame.image.save(draw(size), buf, "icon.png")
        pngs.append((size, buf.getvalue()))
    header = struct.pack("<HHH", 0, 1, len(pngs))
    offset = 6 + 16 * len(pngs)
    entries, data = b"", b""
    for size, png in pngs:
        dim = 0 if size >= 256 else size
        entries += struct.pack("<BBBBHHII", dim, dim, 0, 0, 1, 32, len(png), offset + len(data))
        data += png
    return header + entries + data
