# Argus — Domain Glossary

## Domain

**Discovery** — RSS feed ingestion, relevance filtering, and deduplication of job listings. Produces `Job` records. All feed-derived text is sanitized to plain text before storage (`sanitize_html`). Title shape (where the company sits) is chosen by **feed URL host**, never by the display label (ADR-0003). Entry point: `discover.py` (`--check` for feed health).

**Digest** — The body of the pinned "Job digest" issue: every open `Job` in the discovery window as a Markdown table, ranked by **Scoring**, each row a link, capped at `DIGEST_MAX_LINKS`. Discovery writes it to `logs/digest.md`; the Action rewrites the issue body each run (ADR-0005). The **run comment** (`logs/last_run_summary.txt`) lists only this run's new jobs and feed errors, and exists only when there are some — a quiet day posts nothing.

**Scoring** — `scoring.py`: `score_job` (title, location, capped skills, freshness) and `rank` (best first, ties newest-first). Shared by Dashboard and Digest.

**Setup** — The "Set up profile" Actions form (`setup.yml`). Five answers → `setup.py` writes `config.toml`, including Google News feed URLs for LinkedIn/Naukri → commit → first discovery run. The user never edits TOML (ADR-0005).

**Tracking** — Recording where each `Job` stands. A single `status` column on the job row is the state machine; the dashboard's "✓ Applied" button advances it. Applied jobs leave the Digest. No separate entry point.

**Dashboard** — Serves one ranked table and owns the write endpoint. Interface: `render() -> str` builds the page from the store; `serve()` runs it on port 8765 and renders fresh per request, so there is no `dashboard.html` artifact to go stale. `APPLIED_ROUTE` and the `Handler` that serves it live in the same module as the JS that calls it. Entry point: `dashboard.py`.

## Core entities

- **Job** — A discovered listing with fields: id, title, company, location, source, link, published, status, status_date, summary.
- **Application** — A `Job` whose status moved past `new`. Status is one of: new, applied, interview, rejected. `status_date` records the last change. There is no separate applications file.

## Architecture

- **store.py** — plain module functions (`load_jobs`, `add_jobs`, `get_status`, `set_status`, `this_week`, `age_label`) that own the CSV schema and date formats. `dashboard.py` HTML-escapes at render; `discover.py` neutralises `|` in Markdown cells.
- **config.toml + config.py** — All user preference (feeds, role keywords, seniority blocklist, `[scoring]` weights) in `config.toml`. `config.py` loads it once at import and exports typed constants. Upstream ships a neutral **example profile**; it must run green unedited. `setup.py` regenerates the whole file. Freshness buckets stay in `score_job` — they are not a preference.
- **Seams** — Module globals, reassigned by `tests.py`: `store.CSV_PATH` (persistence), `discover.SUMMARY_PATH` / `DIGEST_PATH` (digest), and the `scoring.*_POINTS` / `SKILL_*` weights. No protocols or adapters.

## Distribution

- **Template repository** — The public upstream. Users click "Use this template" and get a fresh repo with no fork link. Holds no personal data (ADR-0002).
- **Private copy** — A user's own repo made from the template. Holds their `config.toml` and the Action's outputs. Pulls upstream by hand: `git pull upstream master`.
- **Repo as store** — In the private copy the Action commits `jobs_found.csv` back after each run (`git add -f`; the file stays gitignored so the template never carries it). The repo is the single store for CI and the laptop (ADR-0004).
