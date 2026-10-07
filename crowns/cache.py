"""A cache in the player's folder for maps that take seconds to compute (colour, normals, borders).

An entry is remade when the code version or any of the source files it depends on changes.
"""

import hashlib
import os
import sys
from pathlib import Path

import numpy as np

VERSION = 3  # bump to throw every cached map away


def home():
    return Path(os.environ.get("CROWNS_HOME", Path.home() / ".crowns"))


def _key(name, sources):
    h = hashlib.sha1(f"{VERSION}:{name}".encode())
    for src in sources:
        try:
            st = Path(src).stat()
            h.update(f"{Path(src).name}:{st.st_size}:{st.st_mtime_ns}".encode())
        except OSError:   # a packaged game has no source code to watch: its version stands in for it
            h.update(f"{Path(src).name}:packaged".encode())
    return h.hexdigest()[:16]


SEED = Path(__file__).resolve().parent / "cache_seed"   # maps made when the game was packaged


def cached(name, sources, make):
    """make() -> numpy array, kept in the cache until a source changes. A packaged game brings the maps
    already made (see tools/build_crowns.py), so its first start is as quick as any other."""
    folder = home() / "cache"
    path = folder / f"{name}-{_key(name, sources)}.npy"
    if path.exists():
        try:
            return np.load(path)
        except (OSError, ValueError):
            pass
    seed = SEED / f"{name}.npy"
    if getattr(sys, "frozen", False) and seed.exists():
        try:
            return np.load(seed)
        except (OSError, ValueError):
            pass
    value = make()
    try:
        folder.mkdir(parents=True, exist_ok=True)
        for old in folder.glob(f"{name}-*.npy"):
            old.unlink()
        np.save(path, value)
    except OSError:
        pass  # a read-only or full disk only costs the time to compute it again
    return value
