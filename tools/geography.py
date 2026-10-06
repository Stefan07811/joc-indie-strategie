"""The real geography behind the campaign map, in longitude and latitude.

Run it to (re)write the map's geography in legendele/data/map.json: the projection, the playable land,
the Black Sea, the provinces' positions, the rivers and the names of the lands beyond the borders.
Everything else in map.json (economy, armies, ...) is kept. Then the provinces' neighbours are
recomputed (tools/build_adjacency.py).

    python tools/geography.py
"""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

MAP_PATH = ROOT / "legendele" / "data" / "map.json"

# An equirectangular projection; 160 px per degree of longitude and 230 per degree of latitude keep
# the true proportions at the Carpathians' latitude (cos 46° ≈ 160 / 230).
PROJECTION = {"lon0": 20.0, "lat0": 48.7, "px_per_lon": 160, "px_per_lat": 230}
WIDTH, HEIGHT = 1600, 1240

# id, name, terrain, latitude, longitude, owner, extras
PROVINCES = [
    ("satmar", "Sătmar", "plains", 47.75, 22.90, None, {"garrison": ["haiduc_brigands", "haiduc_brigands"]}),
    ("maramures", "Maramureș", "forest", 47.78, 24.05, "iele", {"walls": True, "garrison": ["valve", "valve"]}),
    ("suceava", "Suceava", "forest", 47.62, 25.95, "iele", {}),
    ("iasi", "Iași", "plains", 47.15, 27.55, None, {"garrison": ["haiduc_brigands", "haiduc_marksmen"]}),
    ("crisana", "Crișana", "plains", 47.00, 21.95, "solomonari", {}),
    ("bistrita", "Bistrița", "forest", 47.12, 24.55, "iele", {}),
    ("neamt", "Neamț", "mountains", 46.98, 26.10, None, {"garrison": ["haiduc_brigands", "haiduc_brigands"]}),
    ("cluj", "Cluj", "hills", 46.78, 23.60, "solomonari", {}),
    ("apuseni", "Apuseni", "mountains", 46.42, 22.75, "solomonari", {"walls": True, "garrison": ["paznici", "ucenici"]}),
    ("mures", "Mureș", "plains", 46.55, 24.60, None, {"garrison": ["haiduc_brigands", "haiduc_brigands"]}),
    ("harghita", "Harghita", "forest", 46.40, 25.75, None, {"garrison": ["haiduc_brigands", "haiduc_marksmen"]}),
    ("bacau", "Bacău", "hills", 46.55, 26.85, None, {"garrison": ["haiduc_brigands", "haiduc_brigands"]}),
    ("barlad", "Bârlad", "plains", 46.20, 27.70, "strigoi", {}),
    ("alba", "Alba", "hills", 46.07, 23.60, None, {"garrison": ["haiduc_brigands", "haiduc_marksmen"]}),
    ("hunedoara", "Hunedoara", "hills", 45.90, 22.85, "zmei", {}),
    ("sibiu", "Sibiu", "hills", 45.82, 24.10, None, {"garrison": ["haiduc_brigands", "haiduc_marksmen"]}),
    ("banat", "Banat", "plains", 45.75, 21.30, None, {"garrison": ["haiduc_brigands", "haiduc_marksmen"]}),
    ("siret", "Siret Fens", "marsh", 45.70, 27.60, "strigoi", {}),
    ("brasov", "Brașov", "hills", 45.68, 25.60, None, {"garrison": ["haiduc_brigands", "haiduc_marksmen"]}),
    ("heart", "Heart of the Mountains", "mountains", 45.62, 24.62, None,
     {"size": 1.1, "special": "heart",
      "garrison": ["haiduc_brigands", "haiduc_brigands", "haiduc_marksmen", "haiduc_marksmen"]}),
    ("retezat", "Retezat", "mountains", 45.35, 22.90, "zmei", {"walls": True, "garrison": ["pui_de_zmeu"]}),
    ("buzau", "Buzău", "hills", 45.20, 26.70, None, {"garrison": ["haiduc_brigands", "haiduc_marksmen"]}),
    ("delta", "Danube Delta", "marsh", 45.10, 29.00, "outlaws", {}),
    ("black_marsh", "Black Marsh", "marsh", 45.05, 27.85, "strigoi",
     {"walls": True, "garrison": ["morti", "morti", "morti"]}),
    ("arges", "Argeș", "hills", 45.00, 24.75, "voievodat", {}),
    ("targoviste", "Târgoviște", "plains", 44.92, 25.45, "voievodat", {"walls": True, "garrison": ["oteni", "arcasi"]}),
    ("iron_gates", "Iron Gates", "mountains", 44.85, 22.35, "zmei", {}),
    ("vlasia", "Vlăsia Woods", "forest", 44.55, 26.15, "outlaws", {"walls": True, "garrison": ["haiduc_voinici", "flacai"]}),
    ("dobrogea", "Dobrogea", "hills", 44.40, 28.25, "outlaws", {}),
    ("craiova", "Craiova", "plains", 44.30, 23.80, "voievodat", {}),
]

# The playable land: the lands of the present-day Romanian borders, simplified (lon, lat).
LAND = [
    (22.89, 48.00), (23.50, 47.98), (24.10, 47.95), (24.90, 47.73), (25.30, 47.90), (26.20, 48.00), (26.62, 48.26),
    (27.20, 48.00), (27.60, 47.60), (28.00, 47.10), (28.10, 46.60), (28.20, 46.00), (28.15, 45.50), (28.20, 45.45),
    (28.75, 45.30), (29.40, 45.45), (29.72, 45.40), (29.68, 45.20), (29.60, 44.85), (29.00, 44.55), (28.65, 44.17),
    (28.58, 43.74), (27.95, 43.98), (27.27, 44.12), (26.64, 44.05), (25.97, 43.86), (25.37, 43.62), (24.87, 43.70),
    (24.50, 43.72), (23.40, 43.80), (22.94, 43.98), (22.60, 44.20), (22.69, 44.55), (22.40, 44.70), (21.66, 44.72),
    (21.38, 44.82), (21.36, 45.00), (21.00, 45.30), (20.66, 45.50), (20.26, 45.85), (20.70, 46.15), (21.20, 46.40),
    (21.65, 46.90), (21.97, 47.40), (22.30, 47.75),
]

# The Black Sea, east of the coast (lon, lat).
SEA = [
    (30.30, 46.05), (29.75, 45.45), (29.72, 45.40), (29.68, 45.20), (29.60, 44.85), (29.00, 44.55), (28.65, 44.17),
    (28.58, 43.74), (28.60, 43.10), (30.30, 43.10),
]

RIVERS = {
    "Danube": [(20.00, 44.80), (20.80, 44.72), (21.38, 44.82), (21.66, 44.72), (22.40, 44.72), (22.66, 44.63),
               (22.69, 44.24), (22.94, 43.99), (23.40, 43.83), (24.50, 43.77), (24.87, 43.75), (25.37, 43.65),
               (25.97, 43.88), (26.64, 44.08), (27.33, 44.20), (27.95, 44.68), (27.97, 45.27), (28.05, 45.43),
               (28.47, 45.27), (28.80, 45.18), (29.25, 45.18), (29.68, 45.16)],
    "Mureș": [(25.55, 46.90), (25.35, 46.92), (24.70, 46.78), (24.56, 46.54), (24.10, 46.48), (23.57, 46.07),
              (22.90, 45.88), (21.69, 46.09), (21.32, 46.18), (20.60, 46.22), (20.00, 46.25)],
    "Olt": [(25.85, 46.60), (25.80, 46.36), (25.79, 45.86), (25.40, 45.85), (24.97, 45.84), (24.30, 45.73),
            (24.30, 45.60), (24.37, 45.10), (24.37, 44.43), (24.60, 44.00), (24.87, 43.75)],
    "Siret": [(26.00, 48.30), (26.05, 47.95), (26.30, 47.60), (26.92, 46.92), (26.95, 46.56), (27.10, 46.00),
              (27.40, 45.60), (28.00, 45.45)],
    "Prut": [(26.65, 48.40), (27.20, 48.00), (27.60, 47.60), (28.00, 47.10), (28.10, 46.60), (28.20, 46.00),
             (28.15, 45.50), (28.20, 45.45)],
    "Jiu": [(23.30, 45.40), (23.27, 45.04), (23.50, 44.70), (23.80, 44.32), (23.90, 43.80)],
    "Argeș": [(24.60, 45.40), (24.68, 45.14), (24.87, 44.86), (25.40, 44.50), (26.00, 44.20), (26.64, 44.08)],
    "Someș": [(24.30, 47.20), (23.88, 47.14), (23.60, 47.30), (22.88, 47.79), (22.50, 48.00), (22.30, 48.40)],
    "Criș": [(22.90, 46.90), (22.30, 47.00), (21.93, 47.06), (21.30, 46.95), (20.60, 46.80), (20.00, 46.75)],
    "Bistrița": [(25.10, 47.50), (25.36, 47.35), (26.09, 46.91), (26.50, 46.70), (26.95, 46.56)],
    "Ialomița": [(25.45, 45.30), (25.55, 44.85), (26.00, 44.65), (26.60, 44.60), (27.30, 44.62), (27.90, 44.68)],
    "Timiș": [(22.20, 45.30), (21.80, 45.60), (21.23, 45.75), (20.80, 45.50), (20.40, 45.20)],
}

# The mountain chains drawn on the map (lon, lat), with their half-width in pixels. Only the
# picture follows them; the rules use each province's own terrain.
RANGES = {
    "Eastern Carpathians": (84, [(22.60, 48.90), (23.50, 48.30), (24.20, 47.90), (24.90, 47.65), (25.50, 47.35),
                                 (25.85, 46.95), (26.05, 46.50), (26.15, 46.00), (26.25, 45.65), (26.10, 45.45)]),
    "Harghita": (40, [(25.05, 47.10), (25.40, 46.80), (25.65, 46.40), (25.80, 46.10)]),
    "Southern Carpathians": (76, [(26.10, 45.45), (25.70, 45.42), (25.40, 45.42), (24.80, 45.58), (24.30, 45.52),
                                  (23.80, 45.40), (23.40, 45.35), (22.90, 45.33), (22.45, 45.30), (22.05, 45.05),
                                  (21.85, 44.75), (22.15, 44.55)]),
    "Apuseni": (62, [(22.30, 46.95), (22.70, 46.60), (23.15, 46.32), (23.30, 46.05)]),
    "Poiana Ruscă": (30, [(22.30, 45.72), (22.70, 45.65)]),
}

# The lands beyond the borders, named on the map only.
FOREIGN = [
    ("Kingdom of Hungary", 21.30, 48.35, "plains"),
    ("Serbian Despotate", 21.20, 44.10, "hills"),
    ("Lands of the Sultan", 25.40, 43.48, "plains"),
    ("The Wild Fields", 29.00, 48.20, "plains"),
    ("Kingdom of Poland", 24.60, 48.45, "forest"),
    ("Black Sea", 29.40, 43.75, "sea"),
]


def project(lon, lat):
    return (round((lon - PROJECTION["lon0"]) * PROJECTION["px_per_lon"]),
            round((PROJECTION["lat0"] - lat) * PROJECTION["px_per_lat"]))


def main():
    data = json.loads(MAP_PATH.read_text(encoding="utf-8"))
    data["width"], data["height"] = WIDTH, HEIGHT
    data["victory"]["conquest_provinces"] = round(len(PROVINCES) * 0.7)
    data["projection"] = PROJECTION
    data["land"] = [list(project(*p)) for p in LAND]
    data["sea"] = [list(project(*p)) for p in SEA]
    provinces = []
    for pid, name, terrain, lat, lon, owner, extras in PROVINCES:
        x, y = project(lon, lat)
        provinces.append({"id": pid, "name": name, "terrain": terrain, "x": x, "y": y, "owner": owner, **extras})
    data["provinces"] = provinces
    data["rivers"] = [{"name": n, "points": [list(project(*p)) for p in pts]} for n, pts in RIVERS.items()]
    data["ranges"] = [{"name": n, "width": w, "points": [list(project(*p)) for p in pts]}
                      for n, (w, pts) in RANGES.items()]
    data["foreign"] = [{"name": n, "x": project(lon, lat)[0], "y": project(lon, lat)[1], "terrain": t}
                       for n, lon, lat, t in FOREIGN]
    order = ["name", "width", "height", "projection", "start_year", "army_moves", "victory", "economy", "order",
             "diplomacy", "seasons", "terrain", "provinces", "land", "sea", "rivers", "ranges", "foreign", "start_armies"]
    data = {k: data[k] for k in order if k in data}
    MAP_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    from tools.build_adjacency import main as build_adjacency
    build_adjacency()


if __name__ == "__main__":
    main()
