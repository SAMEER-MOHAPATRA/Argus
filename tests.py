"""Checks on the Argus persistence, discovery, and dashboard seams.

Run: python tests.py
"""

import tempfile
import tomllib
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

import discover
import scoring
import setup
import store
from dashboard import APPLIED_ROUTE, _build_html, render
from scoring import rank, score_job

# the module-global path is the persistence seam: point it at a tmp dir
_tmp = Path(tempfile.mkdtemp())
store.CSV_PATH = _tmp / "jobs.csv"
discover.SUMMARY_PATH = _tmp / "summary.txt"
discover.DIGEST_PATH = _tmp / "digest.md"

# same seam for scoring: pin the weights so the asserts below survive any
# retune of config.toml
scoring.TITLE_POINTS = {"data analyst": 30, "business analyst": 20}
scoring.LOCATION_POINTS = {"remote": 20, "india": 10}
scoring.SKILL_KEYWORDS = ["sql", "python", "power bi", "tableau", "excel", "etl"]
scoring.SKILL_POINT, scoring.SKILL_CAP = 5, 25

LINKEDIN = "https://news.google.com/rss/search?q=site%3Alinkedin.com%2Fjobs+%22x%22"
NAUKRI = "https://news.google.com/rss/search?q=site%3Anaukri.com+%22x%22"
WWR = "https://weworkremotely.com/remote-jobs.rss"
HIMALAYAS = "https://himalayas.app/jobs/rss"


def job_at(days_ago: int, **kw) -> dict:
    published = (datetime.now(timezone.utc) - timedelta(days=days_ago)).strftime(store.UTC_FMT)
    return {"title": "", "summary": "", "location": "", "published": published, **kw}


def full_job(job_id: str, days_ago: int, title: str = "") -> dict:
    return {**job_at(days_ago, title=title), "id": job_id, "company": "", "source": "",
            "link": f"https://example.com/{job_id}", "status": "new"}


def test_suite() -> None:
    now = datetime.now(timezone.utc)
    JOB = {
        "id": "j1", "title": "Data Analyst", "company": "Acme", "location": "Remote",
        "source": "Test", "link": "https://example.com/j1",
        "published": now.strftime(store.UTC_FMT),
        "status": "new", "status_date": "", "summary": "sql",
    }

    # missing file loads as empty; add_jobs appends and round-trips
    assert store.load_jobs() == []
    store.add_jobs([JOB])
    store.add_jobs([{**JOB, "id": "j2"}])
    jobs = store.load_jobs()
    assert [j["id"] for j in jobs] == ["j1", "j2"]
    assert jobs[0]["title"] == "Data Analyst"

    # set_status: unknown id and unknown status are no-ops; a known pair stamps the date
    assert store.set_status("nope", "applied") is False
    assert store.set_status("j1", "hired") is False
    assert store.set_status("j1", "applied") is True
    j1 = next(j for j in store.load_jobs() if j["id"] == "j1")
    assert j1["status"] == "applied"
    assert j1["status_date"] == now.strftime(store.DATE_FMT)
    # untouched rows keep 'new'; a blank column reads as 'new' too
    assert store.get_status(next(j for j in store.load_jobs() if j["id"] == "j2")) == "new"
    assert store.get_status({}) == "new" and store.get_status({"status": " Applied "}) == "applied"

    # this_week keeps recent rows; garbage dates sort as oldest-possible
    rows = [
        {"d": (now - timedelta(days=1)).strftime(store.DATE_FMT)},
        {"d": (now - timedelta(days=10)).strftime(store.DATE_FMT)},
        {"d": "garbage"},
    ]
    assert store.this_week(rows, "d") == [rows[0]]
    assert store.parse_date("garbage", store.DATE_FMT) == datetime.min.replace(tzinfo=timezone.utc)

    # sanitize_html strips tags, decodes entities, collapses whitespace
    assert discover.sanitize_html("<p>Data &amp;  Analyst</p>") == "Data & Analyst"
    assert discover.sanitize_html("<br/>Remote\n\n  (EU)") == "Remote (EU)"
    assert discover.sanitize_html("") == ""

    # --- parse_title: the feed URL picks the title shape, the label is display only ---
    assert discover.parse_title(
        "Wipro hiring BUSINESS ANALYST L4 in Pune Division, Maharashtra, India - LinkedIn India",
        LINKEDIN,
    ) == ("BUSINESS ANALYST L4", "Wipro")
    assert discover.parse_title(
        "Optum hiring Data Analyst - Remote in Eden Prairie, MN - LinkedIn", LINKEDIN,
    ) == ("Data Analyst - Remote", "Optum")
    # LinkedIn's other shape: "<Title> at <Company> — <Location> | LinkedIn Jobs"
    assert discover.parse_title(
        "Analytics Engineer at Dojo — London, England, United Kingdom | LinkedIn Jobs - LinkedIn",
        LINKEDIN,
    ) == ("Analytics Engineer", "Dojo")
    assert discover.parse_title(
        "Data Analyst - Business (Remote) at Quik Hire Staffing — Philippines | LinkedIn Jobs - LinkedIn",
        LINKEDIN,
    ) == ("Data Analyst - Business (Remote)", "Quik Hire Staffing")
    assert discover.parse_title(
        "Support Engineer - Level 2 - Bengaluru - Virtusa - 0 to 1 years of experience - Naukri.com",
        NAUKRI,
    ) == ("Support Engineer - Level 2", "Virtusa")
    assert discover.parse_title(
        "DCX: Home-Based Marketing Data Analyst", WWR,
    ) == ("Home-Based Marketing Data Analyst", "DCX")
    # a title that does not fit its feed's shape is returned untouched, with no company
    assert discover.parse_title("Data Analyst", HIMALAYAS) == ("Data Analyst", "")
    assert discover.parse_title("Data Analyst", LINKEDIN) == ("Data Analyst", "")
    assert discover.parse_title("Analyst - Naukri.com", NAUKRI) == ("Analyst - Naukri.com", "")
    assert discover.parse_title(
        "Data Analyst - Lenskart - 0 to 5 years of experience - Naukri.com", NAUKRI,
    ) == ("Data Analyst - Lenskart - 0 to 5 years of experience - Naukri.com", "")

    # --- extract_location: remote-only boards default to Remote, by URL not label ---
    bare = SimpleNamespace()
    assert discover.extract_location(bare, WWR) == "Remote"
    assert discover.extract_location(bare, HIMALAYAS) == "Remote"
    assert discover.extract_location(bare, LINKEDIN) == "Not specified"
    assert discover.extract_location(SimpleNamespace(location=" Pune "), WWR) == "Pune"

    # --- write_summary: the comment lists every new job as a link, plus feed errors ---
    discover.write_summary(
        [("Feed A", 1, None), ("Feed B", 0, "boom")],
        [{"title": "Data Analyst", "company": "Acme", "link": "https://example.com/j1"}],
    )
    summary = discover.SUMMARY_PATH.read_text(encoding="utf-8")
    assert "Feed B" in summary and "boom" in summary
    assert "- [Data Analyst @ Acme](https://example.com/j1)" in summary
    assert "```" not in summary  # per-feed counts moved to the digest body
    # a quiet run (no new jobs, no errors) posts no comment: the file is removed
    discover.write_summary([("Feed A", 0, None)], [])
    assert not discover.SUMMARY_PATH.exists()

    # --- write_digest: the issue body is a score-ranked table with links ---
    discover.write_digest(
        [
            {**job_at(0, title="Data | Analyst", company="Acme", location="Remote",
                      link="https://example.com/j1", source="Feed A"), "_score": 90},
            {**job_at(2, title="Business Analyst", company="Globex", location="Pune",
                      link="https://example.com/j2", source="Feed A"), "_score": 40},
        ],
        [("Feed A", 2, None)],
        days=7,
        new_count=2,
    )
    digest = discover.DIGEST_PATH.read_text(encoding="utf-8")
    assert "| 90 | [Data / Analyst](https://example.com/j1) | Acme | Remote | today |" in digest
    assert digest.index("example.com/j1") < digest.index("example.com/j2")
    assert "2 new today" in digest and "2 jobs in the last 7 days" in digest
    assert "<details>" in digest and "Feed A" in digest

    # --- age_label: relative posting age for the digest and dashboard ---
    assert store.age_label(job_at(0)["published"]) == "today"
    assert store.age_label(job_at(1)["published"]) == "1d"
    assert store.age_label(job_at(6)["published"]) == "6d"
    assert store.age_label("garbage") == ""

    # --- setup.build_config: the Actions form writes a valid config.toml ---
    cfg = tomllib.loads(setup.build_config(
        titles=["Data Analyst", "Business Analyst"], country="IN",
        skills=["SQL", "Python"], remote=True, locations=["Pune"],
    ))
    assert cfg["discovery"]["role_keywords"] == ["data analyst", "business analyst"]
    urls = [f["url"] for f in cfg["discovery"]["feeds"]]
    assert "https://weworkremotely.com/remote-jobs.rss" in urls
    assert any("site%3Alinkedin.com%2Fjobs+%22data+analyst%22" in u and "gl=IN" in u for u in urls)
    assert any("site%3Anaukri.com+%22business+analyst%22" in u for u in urls)
    assert cfg["scoring"]["title"] == {"data analyst": 30, "business analyst": 25}
    assert cfg["scoring"]["location"] == {"remote": 20, "pune": 10, "india": 10}
    assert cfg["scoring"]["skills"] == ["sql", "python"]
    # US, on-site only: no remote boards, no Naukri
    cfg = tomllib.loads(setup.build_config(["Nurse"], "US", [], remote=False, locations=[]))
    urls = [f["url"] for f in cfg["discovery"]["feeds"]]
    assert len(urls) == 1 and "linkedin" in urls[0] and "gl=US" in urls[0]
    assert cfg["scoring"]["location"] == {"united states": 10}
    # a quote in a title must not break the TOML
    tomllib.loads(setup.build_config(['Analyst "II"'], "GB", [], False, []))
    # blank titles would make role_keywords empty and drop every job — refuse
    try:
        setup.build_config([" ", ""], "US", [], True, [])
        assert False, "empty titles accepted"
    except ValueError:
        pass

    JOBS = [
        {
            "id": "evil1",
            "title": "<script>alert(1)</script> Data Analyst",
            "source": "RemoteOK",
            "published": "2026-07-01 10:00 UTC",
            "link": "https://example.com/job/evil1",
            "status": "new",
            "_score": 90,
        },
        {
            "id": "done1",
            "title": "Business Analyst",
            "company": "Globex",
            "source": "WWR",
            "published": "2026-06-20 10:00 UTC",
            "status_date": "2026-06-21",
            "link": "https://example.com/job/done1",
            "status": "applied",
            "_score": 40,
        },
    ]

    html = _build_html(ranked_jobs=JOBS, jobs_week=1, apps_week=0)

    # untrusted feed title must be escaped, never raw
    assert "<script>alert(1)</script>" not in html
    assert "&lt;script&gt;" in html

    # pending job gets an Apply link + inline mark button; applied job gets neither
    assert "href='https://example.com/job/evil1'" in html  # Apply links straight to the posting
    assert "<button class='mark' data-id='evil1'>" in html
    assert "data-id='done1'" not in html
    assert "<span class='muted'>Applied</span>" in html
    assert "class=done" in html

    # the mark button POSTs to APPLIED_ROUTE; the old localStorage flow is gone
    assert f"'{APPLIED_ROUTE}'" in html
    assert "localStorage" not in html and "confirm(" not in html

    # one table: company is a column; the feed and recent-applications panels are gone
    assert "<td>Globex</td>" in html
    assert "Jobs by Feed" not in html and "Recent Applications" not in html

    # --- score_job: freshness buckets, title/location match, skill cap ---
    assert score_job(job_at(0)) == 50
    assert score_job(job_at(2)) == 40
    assert score_job(job_at(5)) == 25
    assert score_job(job_at(10)) == 10
    assert score_job(job_at(20)) == 0
    assert score_job(job_at(20, title="Senior Data Analyst")) == 30
    assert score_job(job_at(20, title="Business Analyst")) == 20
    assert score_job(job_at(20, location="Remote")) == 20
    assert score_job(job_at(20, location="Pune")) == 0  # no location keyword
    assert score_job(job_at(20, summary="sql python power bi tableau excel etl")) == 25  # 6 skills capped

    # --- rank / render: higher score first, ties stay newest-first ---
    window = [full_job("lo_old", 18), full_job("hi", 20, title="Data Analyst"), full_job("lo_new", 16)]
    assert [j["id"] for j in rank(window)] == ["hi", "lo_new", "lo_old"]
    assert all("_score" in j for j in window)
    store.add_jobs(window)
    page = render()
    assert page.index("data-id='hi'") < page.index("data-id='lo_new'") < page.index("data-id='lo_old'")

    print("OK: tests passed")


if __name__ == "__main__":
    test_suite()
