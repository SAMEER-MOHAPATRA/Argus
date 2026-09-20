"""
discover.py — pulls jobs from the RSS feeds in config.toml.
Adds new listings to jobs_found.csv; skips anything already seen. Writes the
digest (logs/digest.md, the ranked issue body) and the run comment
(logs/last_run_summary.txt, only when there is news).

Usage:
    python discover.py
    python discover.py --days 14
    python discover.py --days 7 --verbose
    python discover.py --check   # feed health check, no writes
"""

import argparse
import hashlib
import logging
import re
import socket
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from html import unescape
from pathlib import Path
from urllib.parse import urlparse

# pyrefly: ignore [missing-import]
import feedparser

import store
from config import FEEDS, MAX_PER_FEED, ROLE_KEYWORDS, SENIORITY_BLOCK
from scoring import rank

# ─── Configuration ───────────────────────────────────────────────────────

DEFAULT_DAYS = 7

# ponytail: 8s socket timeout prevents feedparser from hanging on dead hosts
socket.setdefaulttimeout(8)

_ROOT = Path(__file__).resolve().parent.parent  # the repo root: logs/ sits beside config.toml
SUMMARY_PATH = _ROOT / "logs" / "last_run_summary.txt"   # the issue comment
DIGEST_PATH = _ROOT / "logs" / "digest.md"                # the issue body

log = logging.getLogger("discover")


# ─── Logging ─────────────────────────────────────────────────────────────


def setup_logging(verbose: bool = False) -> None:
    # Windows cp1252 console fix lives in store.py (imported by all scripts)
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(asctime)s | %(levelname)-7s | %(message)s",
        stream=sys.stdout,
        force=True,
    )


# ─── CSV Utilities ───────────────────────────────────────────────────────


def load_seen_ids() -> set[str]:
    seen: set[str] = set()
    for row in store.load_jobs():
        seen.update(filter(None, [row.get("id"), row.get("link")]))
    log.info("Loaded %d seen IDs from store", len(seen))
    return seen


# ─── Feed Fetching ───────────────────────────────────────────────────────


def fetch_feed(url: str) -> feedparser.FeedParserDict:
    """Fetch and parse an RSS feed. No retries: the daily run is the retry."""
    feed = feedparser.parse(url)
    # ponytail: bozo=1 with entries is fine (Himalayas does this)
    if feed.bozo and not feed.entries:
        log.warning(
            "Feed fetch failed for %s: %s",
            url, getattr(feed, "bozo_exception", "unknown error"),
        )
    return feed


# ─── Entry Parsing ───────────────────────────────────────────────────────


def parse_published(entry) -> datetime:
    """Extract publication date from an RSS entry."""
    for field in ("published_parsed", "updated_parsed", "created_parsed"):
        t = getattr(entry, field, None)
        if t:
            try:
                return datetime(*t[:6], tzinfo=timezone.utc)
            except (ValueError, TypeError) as exc:
                log.debug("Failed to parse date field '%s': %s", field, exc)
    log.debug(
        "No valid date found for entry '%s', using current time",
        getattr(entry, "title", "unknown"),
    )
    return datetime.now(timezone.utc)


def extract_job_id(url: str) -> str:
    """Generate a stable unique ID from a job URL."""
    parsed = urlparse(url)
    path = parsed.path.rstrip("/")
    tail = path.split("/")[-1] if path else ""
    slug = re.sub(r"[^a-zA-Z0-9_-]", "", tail)

    if len(slug) < 4:
        # ponytail: short slugs risk collisions — hash instead
        slug = hashlib.md5(url.encode()).hexdigest()[:12]

    return slug


def extract_location(entry, feed_url: str) -> str:
    """Extract location from an RSS entry; remote-only boards default to Remote."""
    loc = getattr(entry, "location", None)
    if loc and str(loc).strip():
        return str(loc).strip()

    tags = getattr(entry, "tags", [])
    for tag in tags:
        term = getattr(tag, "term", "")
        if term and any(
            kw in term.lower()
            for kw in ("remote", "usa", "europe", "worldwide", "india")
        ):
            return term

    if any(host in feed_url for host in ("weworkremotely.com", "himalayas.app")):
        return "Remote"

    return "Not specified"


def parse_title(title: str, feed_url: str) -> tuple[str, str]:
    """Split a feed title into (title, company).

    The feed URL picks the shape: Google News (site:linkedin.com, site:naukri.com)
    and WWR bake the employer into the title; other boards leave it out. Return an
    empty company when the title does not fit — the caller falls back to entry.author.
    """
    if "linkedin.com" in feed_url:
        # "<Company> hiring <Title> in <Location> - LinkedIn[ India]"
        head = title.split(" - LinkedIn")[0]
        company, sep, rest = head.partition(" hiring ")
        if sep and " in " in rest:
            # ponytail: last " in " is the location split — a title ending in
            # "... in Training" with no location would lose its tail
            return rest.rsplit(" in ", 1)[0].strip(), company.strip()

        # the other shape: "<Title> at <Company> — <Location> | LinkedIn Jobs"
        left = head.split(" — ")[0]
        if left != head and " at " in left:
            role, _, company = left.rpartition(" at ")
            return role.strip(), company.strip()

    elif "naukri.com" in feed_url:
        # "<Title> - <Locations> - <Company> - <N to M> years... - Naukri.com"
        parts = title.split(" - ")
        # the tail is always 3 segments (company, experience, Naukri.com) after
        # one location segment, so a title needs at least 5 to have a name left
        if len(parts) >= 5 and parts[-1].endswith("Naukri.com"):
            return " - ".join(parts[:-4]).strip(), parts[-3].strip()

    elif "weworkremotely.com" in feed_url:
        # "<Company>: <Title>"
        company, sep, rest = title.partition(": ")
        if sep:
            return rest.strip(), company.strip()

    return title, ""


# ─── Feed Processing ────────────────────────────────────────────────────


_HTML_TAG_RE = re.compile(r"<[^>]+>")


def sanitize_html(text: str) -> str:
    """Strip HTML tags and decode entities. Feed text is not trusted."""
    clean = _HTML_TAG_RE.sub(" ", text)
    clean = unescape(clean)
    return re.sub(r"\s+", " ", clean).strip()


def process_feed(
    label: str, url: str, days: int, seen: set[str],
) -> tuple[list[dict], str | None]:
    """Process a single RSS feed and return new job listings.

    seen is read-only: feeds run in parallel, so cross-feed dedup happens
    once after the join (see main).
    """
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    results: list[dict] = []

    try:
        feed = fetch_feed(url)

        if not feed.entries:
            log.info("Feed '%s' returned 0 entries", label)
            return results, None

        for entry in feed.entries[:MAX_PER_FEED]:
            pub_date = parse_published(entry)

            if pub_date < cutoff:
                continue

            link = getattr(entry, "link", "")
            if not link:
                continue

            job_id = extract_job_id(link)
            if job_id in seen or link in seen:
                continue

            # sanitize everything feed-controlled — the store holds plain text
            title, company = parse_title(
                sanitize_html(getattr(entry, "title", "")), url,
            )
            company = company or sanitize_html(getattr(entry, "author", "")) or "Unknown"
            description = sanitize_html(getattr(entry, "summary", ""))

            title_lower = title.lower()
            combined_lower = title_lower + " " + description.lower()

            # relevance: matches a role keyword and isn't too senior
            if not any(kw in combined_lower for kw in ROLE_KEYWORDS) or any(
                flag in title_lower for flag in SENIORITY_BLOCK
            ):
                continue

            results.append({
                "id":          job_id,
                "title":       title,
                "company":     company,
                "location":    extract_location(entry, url),
                "source":      label,
                "link":        link,
                "published":   pub_date.strftime(store.UTC_FMT),
                "status":      "new",
                "status_date": "",
                "summary":     description,
            })

        log.info(
            "Feed '%s': %d new jobs from %d entries",
            label, len(results), min(len(feed.entries), MAX_PER_FEED),
        )

    except Exception as exc:
        log.error("Feed '%s' failed: %s", label, exc)
        return results, str(exc)

    return results, None


# ─── Digest ──────────────────────────────────────────────────────────────


# GitHub issue bodies and comments cap at 65 KB; a fresh copy's first run can
# find hundreds of jobs, so both lists are capped
DIGEST_MAX_LINKS = 50


def write_summary(feed_stats: list[tuple], new_jobs: list[dict]) -> None:
    """Print the run result. Save the issue comment to SUMMARY_PATH only when there
    is something to say (new jobs or feed errors); remove it otherwise, so a quiet
    day sends no notification."""
    errors = [f"- {label}: {error}" for label, _, error in feed_stats if error]
    lines = [f"**{len(new_jobs)} new jobs** · {datetime.now():%Y-%m-%d}", ""]
    lines += [f"- [{j['title']} @ {j['company']}]({j['link']})" for j in new_jobs[:DIGEST_MAX_LINKS]]
    if len(new_jobs) > DIGEST_MAX_LINKS:
        lines.append(f"- …and {len(new_jobs) - DIGEST_MAX_LINKS} more in the digest above")
    if errors:
        lines += ["", "Feed errors:", *errors]
    summary = "\n".join(lines)
    print(summary)

    SUMMARY_PATH.parent.mkdir(exist_ok=True)
    if new_jobs or errors:
        SUMMARY_PATH.write_text(summary, encoding="utf-8")
    else:
        SUMMARY_PATH.unlink(missing_ok=True)


def _cell(text: str) -> str:
    # a pipe or newline in feed text would break the Markdown table
    return text.replace("|", "/").replace("\n", " ").strip()


def write_digest(ranked: list[dict], feed_stats: list[tuple], days: int, new_count: int) -> None:
    """Save the issue body to DIGEST_PATH: every open job in the window, best first."""
    lines = [
        f"Updated {datetime.now(timezone.utc):{store.UTC_FMT}} · **{new_count} new today** · "
        f"{len(ranked)} job{'s' if len(ranked) != 1 else ''} in the last {days} days",
        "",
    ]
    if ranked:
        lines += ["| Score | Role | Company | Location | Posted |", "|--:|---|---|---|---|"]
        for j in ranked[:DIGEST_MAX_LINKS]:
            lines.append(
                f"| {j['_score']} | [{_cell(j.get('title', ''))}]({j.get('link', '')}) | "
                f"{_cell(j.get('company', ''))} | {_cell(j.get('location', ''))} | "
                f"{store.age_label(j.get('published', ''))} |"
            )
        if len(ranked) > DIGEST_MAX_LINKS:
            lines += ["", f"…and {len(ranked) - DIGEST_MAX_LINKS} more in `jobs_found.csv`."]
    else:
        lines.append("_No jobs in the window yet. Check the feed list below._")

    lines += ["", "<details><summary>Feeds</summary>", "", "| Feed | New |", "|---|--:|"]
    for label, found, error in feed_stats:
        lines.append(f"| {_cell(label)} | {'error: ' + _cell(error) if error else found} |")
    lines += ["", "</details>", ""]

    DIGEST_PATH.parent.mkdir(exist_ok=True)
    DIGEST_PATH.write_text("\n".join(lines), encoding="utf-8")
    log.debug("Digest written to %s", DIGEST_PATH)


# ─── Main ────────────────────────────────────────────────────────────────


def check_feeds() -> None:
    """Print feed health without touching the store."""
    for f in FEEDS:
        feed = fetch_feed(f["url"])
        sample = feed.entries[0].title[:60] if feed.entries else "N/A"
        print(f"{f['label']:30s} | {len(feed.entries):>3} entries | bozo={feed.bozo} | {sample}")


def main(days: int, verbose: bool = False) -> None:
    setup_logging(verbose)
    log.info("Starting job discovery (window: %d days)", days)
    seen = load_seen_ids()
    all_jobs: list[dict] = []
    feed_stats: list[tuple] = []

    # threads, not processes: feed work is socket wait. map keeps FEEDS order.
    with ThreadPoolExecutor(max_workers=8) as pool:
        per_feed = list(pool.map(
            lambda f: process_feed(f["label"], f["url"], days, seen), FEEDS,
        ))

    # dedup once, in FEEDS order — same result as the old sequential run
    for f, (jobs, error) in zip(FEEDS, per_feed):
        kept = []
        for job in jobs:
            if job["id"] in seen or job["link"] in seen:
                continue
            seen.update([job["id"], job["link"]])
            kept.append(job)
        all_jobs.extend(kept)
        feed_stats.append((f["label"], len(kept), error))

    all_jobs.sort(key=lambda x: x["published"], reverse=True)

    if all_jobs:
        store.add_jobs(all_jobs)
        log.info("Added %d new jobs", len(all_jobs))

    write_summary(feed_stats, all_jobs)
    # the digest shows the whole window, not just this run, so a reader who
    # missed a day still sees the best open matches first
    window = [
        j for j in store.this_week(store.load_jobs(), "published", store.UTC_FMT, days=days)
        if store.get_status(j) == "new"
    ]
    write_digest(rank(window), feed_stats, days, new_count=len(all_jobs))
    log.info("Job discovery complete")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Job discovery via RSS feeds in config.toml")
    parser.add_argument("--days", type=int, default=DEFAULT_DAYS)
    parser.add_argument("--verbose", "-v", action="store_true", help="Enable debug logging")
    parser.add_argument("--check", action="store_true", help="Feed health check, no writes")
    args = parser.parse_args()
    if args.check:
        check_feeds()
    else:
        main(days=args.days, verbose=args.verbose)
