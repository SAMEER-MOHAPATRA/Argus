# Argus

Paste your CV. Argus reads it, watches the job feeds that fit, ranks every match, and shows the best ones on a local page. No account, no API key, nothing leaves your computer.

Named for Argus Panoptes, the hundred-eyed watchman.

## Quick start

1. **Install Python 3.11+** from [python.org](https://www.python.org/downloads/). Tick *Add python.exe to PATH*.
2. **Download this repo** (Code → Download ZIP) and unzip it.
3. **Double-click `Argus.bat`.** The first run sets itself up; a browser tab opens.
4. **Paste your CV** into the box and press **Start watching**.

Argus picks your job titles, skills and country from the CV, fetches postings from LinkedIn, Naukri and the remote boards, and lists them by score. The page refreshes itself when the first batch is in. Every later double-click on `Argus.bat` fetches again and opens the page.

**Better titles.** Open *Better titles? Ask any chatbot first* on the page, copy the prompt, paste it with your CV into ChatGPT, Claude or Gemini, and paste the five-line answer into the box instead of the CV. Argus reads both shapes. **Edit** on the page changes any answer later.

## What you get

- **One ranked table** — every open job from the last 21 days, best first. **Apply** opens the posting; **✓ Applied** records it and greys the row.
- **Sources** — WeWorkRemotely, Himalayas, Remotive, plus LinkedIn and Naukri through Google News search feeds. Add any RSS feed in `config.toml`.
- **Score** = freshness (posted ≤1 day 50 · ≤3 days 40 · ≤7 days 25 · ≤14 days 10) + first matching title keyword + first matching location keyword + 5 per skill found, capped at 25.

## Tune by hand

Press **Edit** on the page, or edit `config.toml`. It is the only file you touch:

- `role_keywords` — a job is kept when its title or description contains one
- `seniority_block` — a job is dropped when its title contains one
- `[[discovery.feeds]]` — any RSS feed. The parser reads the company from the title for `weworkremotely.com`, `linkedin.com`, and `naukri.com` URLs; other feeds use the plain title.
- `[scoring]` — how matches rank

## Command line

```bat
.venv\Scripts\python.exe dashboard.py          # serve at localhost:8765
.venv\Scripts\python.exe discover.py --days 7  # fetch without the page
.venv\Scripts\python.exe discover.py --check   # feed health, no writes
.venv\Scripts\python.exe tests.py              # the test suite
```

One dependency: `feedparser`.

## Optional: run it on GitHub instead

Argus can also run every morning in GitHub Actions and post the ranked table to an issue in your own repo, so you get it on your phone with no computer switched on.

1. **[Use this template](../../generate)** → create a **private** repo.
2. **Actions → Set up profile → Run workflow.** Type the five answers (the chatbot prompt in [docs/profile-prompt.md](docs/profile-prompt.md) produces them).
3. Open the pinned **Job digest** issue. It fills in a few minutes and updates every morning.

If GitHub asks you to enable workflows on the new repo, click **Enable**. To keep the local page and the Action in step, `git pull` before you double-click `Argus.bat`.

**Updating.** Once: `git remote add upstream https://github.com/<upstream-owner>/Argus`. Then `git pull upstream master`. Conflicts stay inside `config.toml`.

Design notes: `CONTEXT.md`, `docs/adr/`, `docs/explained/`.
