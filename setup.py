"""
setup.py — writes config.toml from a few answers.

Backs the "Set up profile" form in the Actions tab, so a new user never edits
TOML or builds a Google News URL by hand. Works from the command line too:

    python setup.py --titles "data analyst, business analyst" --country IN \
                    --skills "sql, python" --locations "Pune" --remote true
"""

import argparse
import json
import re
from pathlib import Path
from urllib.parse import quote_plus

CONFIG_PATH = Path(__file__).parent / "config.toml"

# ISO code -> name used as a location keyword. Google News accepts any code
# with an English edition (hl=en-XX&gl=XX&ceid=XX:en); this list only feeds
# the form's dropdown and the location score.
COUNTRIES = {
    "US": "United States", "GB": "United Kingdom", "CA": "Canada", "AU": "Australia",
    "IN": "India", "SG": "Singapore", "IE": "Ireland", "NZ": "New Zealand",
    "DE": "Germany", "NL": "Netherlands", "AE": "United Arab Emirates", "ZA": "South Africa",
}

REMOTE_BOARDS = [
    ("WWR | All", "https://weworkremotely.com/remote-jobs.rss"),
    ("Himalayas | Remote", "https://himalayas.app/jobs/rss"),
    # .com is Cloudflare-walled; the .io mirror serves the general feed
    ("Remotive | Remote", "https://remotive.io/remote-jobs/feed"),
]

SENIORITY_BLOCK = [
    "senior", "staff", "lead", "manager", "director",
    "sr.", "head of", "principal", "vp ", "vice president",
]


def _news_feed(site: str, title: str, country: str) -> str:
    """Google News RSS scoped to one job site — the only way to get LinkedIn/Naukri as a feed."""
    q = quote_plus(f'site:{site} "{title}"')
    return f"https://news.google.com/rss/search?q={q}&hl=en-{country}&gl={country}&ceid={country}:en"


def _clean(items: list[str]) -> list[str]:
    return [s.strip().lower() for s in items if s.strip()]


def build_config(
    titles: list[str], country: str, skills: list[str], remote: bool, locations: list[str],
) -> str:
    """Return the text of a complete config.toml."""
    titles, skills, locations = _clean(titles), _clean(skills), _clean(locations)
    if not titles:
        raise ValueError("at least one job title is required")
    country = country.upper()

    # "product manager" as a title must survive the "manager" block
    block = [b for b in SENIORITY_BLOCK if not any(b in t for t in titles)]

    feeds = list(REMOTE_BOARDS) if remote else []
    for t in titles:
        feeds.append((f"LinkedIn | {t.title()}", _news_feed("linkedin.com/jobs", t, country)))
        if country == "IN":
            feeds.append((f"Naukri | {t.title()}", _news_feed("naukri.com", t, country)))

    # first title is the top pick; the rest tie
    title_points = {t: 30 if i == 0 else 25 for i, t in enumerate(titles)}
    location_points = {"remote": 20} if remote else {}
    for loc in locations + [COUNTRIES.get(country, "").lower()]:
        if loc:
            location_points.setdefault(loc, 10)

    # ponytail: json.dumps emits valid TOML strings and arrays — no tomli_w dependency
    def table(d: dict) -> str:
        return "\n".join(f"{json.dumps(k)} = {v}" for k, v in d.items())

    feed_blocks = "\n".join(
        f"[[discovery.feeds]]\nlabel = {json.dumps(label)}\nurl = {json.dumps(url)}\n"
        for label, url in feeds
    )
    return f"""# Argus configuration — written by setup.py ("Set up profile" in Actions).
# You can edit it by hand at any time. See README "Tune by hand".

[discovery]
max_per_feed = 25
# a job is kept when its title or description contains one of these
role_keywords = {json.dumps(titles)}
# a job is dropped when its title contains one of these
seniority_block = {json.dumps(block)}

{feed_blocks}
[scoring]
# +skill_point per skill found, capped at skill_cap
skills = {json.dumps(skills)}
skill_point = 5
skill_cap = 25

# first title keyword that matches wins
[scoring.title]
{table(title_points)}

# first location keyword that matches wins
[scoring.location]
{table(location_points)}
"""


def is_profile(config_text: str) -> bool:
    """True when config.toml was written from answers, not the shipped example."""
    return "written by setup.py" in config_text[:200]


def read_profile(cfg: dict) -> dict:
    """The five answers behind a parsed config.toml — the inverse of build_config."""
    d, s = cfg["discovery"], cfg["scoring"]
    urls = [f["url"] for f in d["feeds"]]
    codes = [m.group(1) for u in urls for m in [re.search(r"[?&]gl=([A-Z]{2})", u)] if m]
    country = codes[0] if codes else "US"
    boards = {url for _, url in REMOTE_BOARDS}
    skip = {"remote", COUNTRIES.get(country, "").lower()}
    return {
        "titles": list(d["role_keywords"]),
        "country": country,
        "remote": any(u in boards for u in urls),
        "skills": list(s["skills"]),
        "locations": [k for k in s["location"] if k not in skip],
    }


if __name__ == "__main__":
    p = argparse.ArgumentParser(description="Write config.toml from a few answers")
    p.add_argument("--titles", required=True, help="comma-separated job titles")
    p.add_argument("--country", default="US", help="ISO code, e.g. US, GB, IN")
    p.add_argument("--skills", default="", help="comma-separated")
    p.add_argument("--locations", default="", help="comma-separated cities or regions")
    p.add_argument("--remote", default="true", help="true/false: include remote-only boards")
    a = p.parse_args()
    CONFIG_PATH.write_text(
        build_config(
            a.titles.split(","), a.country, a.skills.split(","),
            a.remote.strip().lower() == "true", a.locations.split(","),
        ),
        encoding="utf-8",
    )
    print(f"Wrote {CONFIG_PATH}")
