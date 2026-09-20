# ADR-0006: The local page is the primary UI; a pasted CV is the setup

**Status:** Accepted  
**Date:** 2026-09-20  
**Deciders:** User + agent

## Context

ADR-0005 made the GitHub issue the UI and an Actions form the setup. A new user still had
to create a repo, find the Actions tab and type five answers. The owner's goal moved to
"paste a CV and the tool does the rest". No API key and no hosted service are acceptable.

## Decision

- **`Argus.bat` is the entry point.** It makes the venv on first run, installs the one
  dependency and starts `dashboard.py`, which opens the page.
- **The page takes pasted text.** One box accepts either a raw CV or the five-line answer
  to the prompt in `docs/profile-prompt.md`. `cv.read` parses the answer exactly when it is
  present and otherwise falls back to a dictionary extractor (`cv.extract_profile`). No
  network call. The prompt is on the page with a copy button, because a chatbot picks
  better titles than a word list can.
- **Saving a profile is one call.** `dashboard.save_profile` writes `config.toml` through
  `setup.build_config`, reloads `config`, copies the weights onto `scoring`, drops unseen
  jobs from the store and runs `discover.py` as a subprocess. The subprocess reads the new
  file; the page polls `/status` and reloads when it ends.
- **Discovery runs on paste and on each launch.** No scheduler. A launch with the shipped
  example config does not fetch, so the example never fills the store.
- **The GitHub path stays.** `setup.yml`, `discover.yml`, and the digest issue are unchanged
  and optional. The README lists them after the local quick start.

## Consequences

- `page.html` is a template filled by `.replace` tokens; the HTML, CSS and JS live in one
  file and Python stays small.
- `setup.read_profile` and `setup.is_profile` invert `build_config`, so the edit form shows
  the current answers and the page knows a first run from a returning one.
- `config.CONFIG_PATH` becomes a test seam like `store.CSV_PATH`.
- The extractor knows about 90 titles and 100 skills. A CV outside that list returns no
  title and the page says to use the prompt. Growing the lists is a data change, not code.
- `refresh.bat` and `pytest.ini` are parked in `To Delete/` (gitignored). `python tests.py`
  is the one test path.
