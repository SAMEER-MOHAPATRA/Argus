"""
scoring.py — ranks stored jobs. Shared by the dashboard and the daily digest.

Weights come from [scoring] in config.toml. Freshness stays in code:
everyone wants new postings first.
"""

from datetime import datetime, timezone

import store
# ponytail: module globals are the scoring seam — tests reassign them (see tests.py)
from config import LOCATION_POINTS, SKILL_CAP, SKILL_KEYWORDS, SKILL_POINT, TITLE_POINTS


def score_job(job: dict) -> int:
    """Points = title match + location match + capped skills + freshness, capped at 100."""
    title = job.get("title", "").lower()
    haystack = title + " " + job.get("summary", "").lower() + " " + job.get("location", "").lower()
    pts = 0
    for kw, p in TITLE_POINTS.items():
        if kw in title:
            pts += p
            break
    for kw, p in LOCATION_POINTS.items():
        if kw in haystack:
            pts += p
            break
    pts += min(SKILL_CAP, sum(SKILL_POINT for kw in SKILL_KEYWORDS if kw in haystack))
    # freshness dominates: apply fast while postings are new
    age = datetime.now(timezone.utc) - store.parse_date(job.get("published", ""), store.UTC_FMT)
    if age.days <= 1:
        pts += 50
    elif age.days <= 3:
        pts += 40
    elif age.days <= 7:
        pts += 25
    elif age.days <= 14:
        pts += 10
    return min(pts, 100)


def rank(jobs: list[dict]) -> list[dict]:
    """Set `_score` on each job and return a new list, best first; ties stay newest-first."""
    for j in jobs:
        j["_score"] = score_job(j)
    newest_first = sorted(jobs, key=lambda j: j.get("published", ""), reverse=True)
    return sorted(newest_first, key=lambda j: -j["_score"])
