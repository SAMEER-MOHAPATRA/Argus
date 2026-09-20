# ADR-0003: All user preference lives in config.toml; feed shape is chosen by URL host

**Status:** Accepted  
**Date:** 2026-09-20  
**Deciders:** User + agent

## Context

`dashboard.py` held the author's scoring profile as module constants (`TITLE_POINTS`,
`LOCATION_POINTS`, `SKILL_KEYWORDS`) with a comment "from resume". `config.toml` held the
other half of the same preference (`role_keywords`). A new user had to edit Python to rank
jobs for their role, which breaks "edit one file, no code" (ADR-0002).

`discover.py` also dispatched the title parser on the feed **label prefix** (`linkedin`,
`naukri`, `wwr`). A user who relabelled a feed lost company extraction with no warning.

## Decision

1. Add a `[scoring]` table to `config.toml`: `[scoring.title]` and `[scoring.location]` as
   keyword→points tables (TOML order is match priority), `skills`, `skill_point`,
   `skill_cap`. `config.py` exports them; `dashboard.py` imports them.
2. Freshness buckets stay in `score_job`. Everyone wants new postings first; this is not a
   preference.
3. `parse_title` and `extract_location` take the **feed URL** and match on host
   (`linkedin.com`, `naukri.com`, `weworkremotely.com`, `himalayas.app`). The label is
   display only. No `parser =` key per feed: the URL already says which site it is.
4. Test seam for weights: `tests.py` reassigns the `dashboard` module globals, the same
   pattern `store.CSV_PATH` already uses (ADR-0001 amendment). Tests pin their own weights
   so a retune of `config.toml` cannot break them.
5. The dashboard legend no longer spells out the weights; it points at `config.toml`.

## Consequences

**Positive:** one file is the whole user surface. Relabelling a feed is safe. Tests are
independent of the shipped profile. `config.py` has two callers again, so it stays.

**Negative:** `config.toml` is longer. A feed from a new site with a company-in-title
shape needs a code change to add a host branch — same as before, now documented.

## Alternatives considered

- **Separate `profile.toml`** — rejected. Two files to explain; ADR-0002 already decided
  one file.
- **Explicit `parser = "linkedin"` per feed** — rejected. Redundant with the URL, one more
  key to document, and silent when omitted.
- **Freshness in config** — rejected. No user asked for stale-first ranking.
