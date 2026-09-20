# ADR-0002: Distribute Argus as a template repository; personal data lives in a private copy

**Status:** Accepted  
**Date:** 2026-09-20  
**Deciders:** User + agent

## Context

Argus must be usable by anyone: a new user edits one file and no code. Two constraints
came out of the grilling (2026-09-20):

1. No personal job-search data in the public upstream repo. This includes `config.toml`
   (role keywords, feeds, scoring weights) and the Action's outputs (`jobs_found.csv`
   artifact, daily issue comment).
2. The daily GitHub Action is a feature for every user, not a private cron.

Today `config.toml` is committed and holds the author's DA/BA India profile. The Action
(`.github/workflows/discover.yml`) checks out the repo and reads that file. A fork of a
public repo is always public on GitHub, so the fork model fails constraint 1.

## Decision

- Mark the upstream repo as a **GitHub template repository**. A user clicks
  "Use this template", chooses **private**, edits `config.toml`, commits. The Action runs
  in their copy with no further setup for config.
- Upstream `config.toml` becomes a **neutral example profile**: generic role keywords,
  source feeds that need no location, and documented scoring weights. It must run
  green as shipped, so a new user sees output before editing anything.
- The author uses the same path: a private copy holds the personal `config.toml`.
  Upstream improvements reach the copy with `git pull upstream main`; conflicts are
  confined to `config.toml`.
- One file, one layout. No `config.example.toml`, no gitignored `config.local.toml`,
  no config in Actions secrets.

## Consequences

**Positive:**
- Zero Python or YAML change to satisfy constraint 1. Config and outputs are private
  because the copy is private.
- "Edit one file" holds literally: `config.toml` is the whole user surface.
- Later config work (ADR-0003+, scoring weights) needs no split-file logic.

**Negative:**
- The author maintains two repos and pulls upstream by hand.
- Upstream git history still contains the author's earlier `config.toml`. Accepted:
  the data is job-search keywords, not credentials. Rewrite history only if that
  judgement changes.
- Template copies have no fork link on GitHub; the user adds the `upstream` remote once.

## Alternatives considered

- **Fork with committed personal config** — rejected. Forks of public repos are public.
- **Committed `config.example.toml` + gitignored `config.toml`** — rejected. The Action
  loses its config unless the user commits it (defeats gitignore) or the workflow
  injects it from a secret (new YAML, new Python, edits through the secrets UI with no
  diff or history). Outputs would still land in a public repo.
- **Config in an Actions secret, written to disk at run time** — rejected for the same
  output-leak reason and the 48 KB secret limit. Two config paths to document.
