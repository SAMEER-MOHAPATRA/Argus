# ADR-0004: The daily Action commits jobs_found.csv back and posts a linked digest

**Status:** Accepted; digest format and the scoring split superseded by ADR-0005  
**Date:** 2026-09-20  
**Deciders:** User + agent

## Context

The workflow had four defects:

1. `jobs_found.csv` was gitignored and never restored, so `load_seen_ids()` started empty
   every run. Every job in the window was "new" every day.
2. The issue comment was a per-feed count plus one "Top match", which was the newest job,
   not the best. Nothing in the email was clickable.
3. `cron: '0 0 * * *'` sits on GitHub's most loaded minute. GitHub also disables scheduled
   workflows after 60 days with no repository activity.
4. `ISSUE_NUMBER` was a repository variable; when unset the step exited 0 silently.

The user runs the Action as the primary discovery and the laptop as the dashboard.

## Decision

- **Repo as store.** After discovery the Action runs `git add -f jobs_found.csv` and
  commits if changed. The file stays in `.gitignore` so a `git add -A` in the public
  template can never pick up personal data; `-f` tracks it in the private copy, and once
  tracked git follows it normally. `permissions: contents: write`.
- **Digest with links.** `write_summary` emits the run comment: `- [title @ company](link)`
  per new job this run, newest first, plus feed errors, capped at `DIGEST_MAX_LINKS = 50`
  (a fresh copy's first run can find hundreds; the comment limit is 65 KB). ADR-0005 later
  split the ranked table and the per-feed counts out into the issue body (`write_digest`).
- **Self-creating issue.** The Action searches for an open issue titled "Job digest" and
  creates it on first run. No repository variable.
- **Cron `17 3 * * *`** (08:47 IST). `concurrency: discover` so a manual run cannot race
  the scheduled push.
- The artifact upload is removed; the commit replaces it.

## Consequences

**Positive:** dedup works across days. The digest is actionable. `git pull` feeds the
local dashboard. The daily commit is repository activity, so the schedule stays enabled
(reasonable assumption from GitHub's wording; not verified against a 60-day gap).

**Negative:** one commit per day of noise. If the user also edits `jobs_found.csv`
locally (mark Applied) and CI appends rows, a `git pull` can conflict; both sides append
to the same file, so most days merge clean. Resolve by keeping both sides.

## Alternatives considered

- **`actions/cache`** — rejected. Opaque, evicts after 7 idle days, and the laptop still
  needs an artifact download.
- **Stateless with a better summary** — rejected. Daily repeats of the same jobs.
- **Score the digest with `dashboard.score_job`** — rejected here, reversed by ADR-0005.
  Discovery and Dashboard met only at `store.py`, so importing one into the other added
  coupling. ADR-0005 then needed the same ranking in the issue and moved scoring into
  `scoring.py`, which both now import.
