# Argus

Watches job feeds every morning, ranks the matches, and posts the best ones to an issue in your own GitHub repo. No server, no account, no code.

Named for Argus Panoptes, the hundred-eyed watchman.

## Quick start — three clicks

1. **[Use this template](../../generate)** → create a **private** repo. Private keeps your job search off the public internet.
2. In your new repo: **Actions → Set up profile → Run workflow**. Type the job titles you want, pick your country, list your skills. Submit.
3. Open the pinned **Job digest** issue. It fills in a few minutes and updates every morning: best matches first, each one a link.

If GitHub asks you to enable workflows on the new repo, click **Enable**.

Have a CV? Paste it into any chatbot with [this prompt](docs/profile-prompt.md) and it returns the form answers.

## What you get

- **Job digest issue** — a table of every open job from the last 7 days, ranked by score. Rewritten daily. A short comment (and so a notification) only on days with new jobs or feed errors.
- **Sources** — WeWorkRemotely, Himalayas, Remotive, plus LinkedIn and Naukri through Google News search feeds. Add any RSS feed.
- **Local dashboard** (optional) — the same ranking with one-click Apply and mark-applied, in your browser.

## Tune by hand

Run **Set up profile** again with new answers, or edit `config.toml` in your repo. It is the only file you touch:

- `role_keywords` — a job is kept when its title or description contains one
- `seniority_block` — a job is dropped when its title contains one
- `[[discovery.feeds]]` — any RSS feed. The parser reads the company from the title for `weworkremotely.com`, `linkedin.com`, and `naukri.com` URLs; other feeds use the plain title.
- `[scoring]` — how matches rank

**Score** = freshness (posted ≤1 day 50 · ≤3 days 40 · ≤7 days 25 · ≤14 days 10) + first matching title keyword + first matching location keyword + 5 per skill found, capped at 25.

## Local dashboard

```bash
git pull                       # bring the Action's results down
pip install -r requirements.txt
python dashboard.py            # serve at localhost:8765
python discover.py --days 7    # or run discovery locally
python discover.py --check     # feed health, no writes
```

Python 3.11+. One dependency: `feedparser`.

## Updating

Once: `git remote add upstream https://github.com/<upstream-owner>/Argus`. Then `git pull upstream master`. Conflicts stay inside `config.toml`.

Design notes: `CONTEXT.md`, `docs/adr/`, `docs/explained/`.
