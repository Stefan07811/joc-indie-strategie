"""Recompute each province's "neighbors" in legendele/data/map.json from the drawn map shapes.

Run after moving or adding provinces:  python tools/build_adjacency.py
"""

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from legendele.mapshape import adjacency, components, map_grid  # noqa: E402

MAP_PATH = ROOT / "legendele" / "data" / "map.json"


def main():
    data = json.loads(MAP_PATH.read_text(encoding="utf-8"))
    grid = map_grid(data)
    adj = adjacency(grid)
    for p in data["provinces"]:
        pieces = components(grid, p["id"])
        if pieces != 1:
            print(f"warning: {p['id']} is split into {pieces} pieces")
        p["neighbors"] = sorted(adj.get(p["id"], ()))
        print(f"{p['id']:12} -> {', '.join(p['neighbors'])}")
    by_id = {p["id"]: p for p in data["provinces"]}
    for p in data["provinces"]:
        p["roads"] = sorted(n for n in p["neighbors"] if has_road(p, by_id[n]))
        p["crossings"] = {n: river for n in p["neighbors"]
                          if (river := river_between(p, by_id[n], data.get("rivers", [])))}

    # Keep one province per line so the file stays easy to edit by hand.
    text = json.dumps(data, ensure_ascii=False, indent=2)
    for key in ("provinces", "rivers", "ranges", "foreign", "start_armies"):
        if key not in data:
            continue
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
    # Tiny objects such as {"food": 1.0} and short lists also go on one line.
    text = re.sub(r"\{\n\s+([^{}\[\]\n]+)\n\s+\}", r"{\1}", text)
    while True:
        compacted = re.sub(r"\[\n\s+([^{}\[\]]+?)\n\s+\]",
                           lambda m: "[" + ", ".join(x.strip() for x in m.group(1).split(",\n")) + "]", text)
        if compacted == text:
            break
        text = compacted
    MAP_PATH.write_text(text + "\n", encoding="utf-8")


def has_road(a, b):
    """Roads join neighbours, except over the high peaks (only passes lead to the Heart)."""
    if "mountains" in (a["terrain"], b["terrain"]):
        return "heart" in (a.get("special"), b.get("special"))
    return True


def _crosses(p1, p2, q1, q2):
    def side(a, b, c):
        return (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])
    return side(p1, p2, q1) * side(p1, p2, q2) < 0 and side(q1, q2, p1) * side(q1, q2, p2) < 0


def river_between(a, b, rivers):
    """The river an army must cross between two neighbours' centres, if any (the widest first)."""
    line = ((a["x"], a["y"]), (b["x"], b["y"]))
    for river in sorted(rivers, key=lambda r: r["name"] != "Danube"):
        pts = river["points"]
        if any(_crosses(*line, pts[i], pts[i + 1]) for i in range(len(pts) - 1)):
            return river["name"]
    return None


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
