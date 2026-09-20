import tomllib
from pathlib import Path


# anchored to this file, not the cwd: the GitHub Action does not start in the repo root
CONFIG_PATH = Path(__file__).parent / "config.toml"

ROLE_KEYWORDS: list[str]
SENIORITY_BLOCK: list[str]
FEEDS: list[dict[str, str]]
MAX_PER_FEED: int
TITLE_POINTS: dict[str, int]
LOCATION_POINTS: dict[str, int]
SKILL_KEYWORDS: list[str]
SKILL_POINT: int
SKILL_CAP: int


def reload() -> None:
    """Read CONFIG_PATH into the constants. The dashboard calls this after it saves a profile."""
    global ROLE_KEYWORDS, SENIORITY_BLOCK, FEEDS, MAX_PER_FEED
    global TITLE_POINTS, LOCATION_POINTS, SKILL_KEYWORDS, SKILL_POINT, SKILL_CAP
    with open(CONFIG_PATH, "rb") as f:
        raw = tomllib.load(f)
    ROLE_KEYWORDS = raw["discovery"]["role_keywords"]
    SENIORITY_BLOCK = raw["discovery"]["seniority_block"]
    FEEDS = raw["discovery"]["feeds"]
    MAX_PER_FEED = raw["discovery"].get("max_per_feed", 25)
    # scoring weights: dicts keep TOML order, so "first match wins" is the file order
    scoring = raw["scoring"]
    TITLE_POINTS = scoring["title"]
    LOCATION_POINTS = scoring["location"]
    SKILL_KEYWORDS = scoring["skills"]
    SKILL_POINT = scoring.get("skill_point", 5)
    SKILL_CAP = scoring.get("skill_cap", 25)


reload()
