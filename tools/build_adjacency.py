"""Recompute each province's "neighbors" in legendele/data/map.json from the drawn map shapes.

Run after moving or adding provinces:  python tools/build_adjacency.py
"""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from legendele.mapshape import adjacency, build_grid, components  # noqa: E402

MAP_PATH = ROOT / "legendele" / "data" / "map.json"


def main():
    data = json.loads(MAP_PATH.read_text(encoding="utf-8"))
    grid = build_grid(data["provinces"], data["width"], data["height"])
    adj = adjacency(grid)
    for p in data["provinces"]:
        pieces = components(grid, p["id"])
        if pieces != 1:
            print(f"warning: {p['id']} is split into {pieces} pieces")
        p["neighbors"] = sorted(adj.get(p["id"], ()))
        print(f"{p['id']:12} -> {', '.join(p['neighbors'])}")

    # Keep one province per line so the file stays easy to edit by hand.
    text = json.dumps(data, ensure_ascii=False, indent=2)
    for key in ("provinces", "start_armies"):
        compact = ",\n    ".join(json.dumps(item, ensure_ascii=False) for item in data[key])
        start = text.index(f'"{key}": [')
        end = _matching_bracket(text, text.index("[", start))
        text = text[:start] + f'"{key}": [\n    {compact}\n  ]' + text[end + 1:]
    compact = ",\n    ".join(
        f"{json.dumps(k)}: {json.dumps(v, ensure_ascii=False)}" for k, v in data["terrain"].items()
    )
    start = text.index('"terrain": {')
    end = text.index('\n  },', start)
    text = text[:start] + f'"terrain": {{\n    {compact}\n  }},' + text[end + 5:]
    MAP_PATH.write_text(text + "\n", encoding="utf-8")


def _matching_bracket(text, open_index):
    depth = 0
    for i in range(open_index, len(text)):
        if text[i] == "[":
            depth += 1
        elif text[i] == "]":
            depth -= 1
            if depth == 0:
                return i
    raise ValueError("unbalanced brackets")


if __name__ == "__main__":
    main()
