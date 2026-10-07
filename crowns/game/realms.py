"""The realms as history left them in September 1402 (tools/realms_1402.py wrote the data)."""

import json
from pathlib import Path

DATA = Path(__file__).resolve().parent.parent / "data" / "realms.json"


def load():
    """({tag: realm description}, [relations])"""
    raw = json.loads(DATA.read_text(encoding="utf-8"))
    return {r["tag"]: r for r in raw["realms"]}, raw["relations"]
