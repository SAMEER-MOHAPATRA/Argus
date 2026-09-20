# ADR-0005: The digest issue is the UI; an Actions form is the setup

**Status:** Accepted  
**Date:** 2026-09-20  
**Deciders:** User + agent

## Context

After ADR-0002..0004 a new user still had to: understand GitHub templates, hand-edit TOML,
write Google News RSS query strings for LinkedIn/Naukri, and install Python to see a ranked
view. The TOML and RSS steps stop most people. The user's goal is "anyone can use it", and
asked whether to build a hosted website instead.

## Decision

- **Setup is a form.** `setup.yml` is a `workflow_dispatch` workflow with five inputs
  (titles, country, remote, skills, locations). GitHub renders it as a form in the Actions
  tab. It runs `setup.py`, which writes `config.toml` — including the Google News feed
  URLs — commits, and starts discovery. Inputs pass through `env`, never inline in `run`.
- **The digest issue is the UI.** Each run rewrites the body of one pinned "Job digest"
  issue with a Markdown table of every open job in the window, ranked by score, each a link.
  Per-feed counts sit in a collapsed `<details>`. A comment (which sends a notification) is
  posted only when there are new jobs or feed errors; `write_summary` removes the comment
  file on quiet days and the workflow checks for it.
- **Scoring is shared.** `score_job` and `rank` move from `dashboard.py` to `scoring.py`,
  imported by both `dashboard.py` and `discover.py`. This reverses the "rejected for now" in
  ADR-0004: the issue now needs the ranking, and one small module is cheaper than two orders.
- **The dashboard is one table.** Company, location and relative age are columns. The
  feed-count panel, recent-applications panel and score legend are removed; three stat
  tiles remain. Neutral palette, one accent.
- **CV → profile is a prompt**, `docs/profile-prompt.md`, not code. An LLM extracts titles
  and skills well; a regex parser does not.
- **No hosted website.** It needs a server, per-user storage of CVs (personal data), an LLM
  API, and one IP querying Google News for every user. The template path is the free demand
  test for that product.

## Consequences

**Positive:** setup is three clicks and no file editing. The daily view works on a phone
through the GitHub app. Python is optional. The target is now "anyone with a GitHub account".

**Negative:** editing an issue body sends no notification, so the comment stays as the
nudge. Applied-tracking still needs the local dashboard; a checkbox flow in the issue is
deferred. `setup.py` emits TOML by string formatting (`json.dumps` for strings and arrays),
which is valid TOML but must be re-checked if the config schema changes.

## Alternatives considered

- **GitHub Pages dashboard** — rejected. Pages on a private repo needs a paid plan, and the
  private repo is where the profile lives.
- **Hosted website with CV upload** — deferred, see above.
- **Regex CV parser in `setup.py`** — rejected. Poor titles and locations; the prompt is free.
