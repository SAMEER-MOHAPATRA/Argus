import tomllib
from pathlib import Path


# anchored to this file, not the cwd: the GitHub Action does not start in the repo root
CONFIG_PATH = Path(__file__).parent / "config.toml"

with open(CONFIG_PATH, "rb") as f:
    _raw = tomllib.load(f)


ROLE_KEYWORDS: list[str] = _raw["discovery"]["role_keywords"]
SENIORITY_BLOCK: list[str] = _raw["discovery"]["seniority_block"]
FEEDS: list[dict[str, str]] = _raw["discovery"]["feeds"]
MAX_PER_FEED: int = _raw["discovery"].get("max_per_feed", 25)

# scoring weights: dicts keep TOML order, so "first match wins" is the file order
_scoring = _raw["scoring"]
TITLE_POINTS: dict[str, int] = _scoring["title"]
LOCATION_POINTS: dict[str, int] = _scoring["location"]
SKILL_KEYWORDS: list[str] = _scoring["skills"]
SKILL_POINT: int = _scoring.get("skill_point", 5)
SKILL_CAP: int = _scoring.get("skill_cap", 25)
