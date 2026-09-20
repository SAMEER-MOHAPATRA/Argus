# Graph Report - Argus  (2026-09-20)

## Corpus Check
- cluster-only mode — file stats not available

## Summary
- 97 nodes · 158 edges · 7 communities (6 shown, 1 thin omitted)
- Extraction: 97% EXTRACTED · 3% INFERRED · 0% AMBIGUOUS · INFERRED: 5 edges (avg confidence: 0.85)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `2fcf6bee`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- argus/dashboard.py
- argus/discover.py
- argus/store.py
- Handler
- cv.py
- setup.py
- reload

## God Nodes (most connected - your core abstractions)
1. `rank()` - 8 edges
2. `process_feed()` - 8 edges
3. `Handler` - 7 edges
4. `_build_html()` - 7 edges
5. `test_suite()` - 7 edges
6. `main()` - 7 edges
7. `start_refresh()` - 6 edges
8. `render()` - 5 edges
9. `clear_new()` - 5 edges
10. `load_jobs()` - 5 edges

## Surprising Connections (you probably didn't know these)
- `test_suite()` --calls--> `_build_html()`  [INFERRED]
  tests/tests.py → argus/dashboard.py
- `test_suite()` --calls--> `render()`  [INFERRED]
  tests/tests.py → argus/dashboard.py
- `test_suite()` --calls--> `rank()`  [INFERRED]
  tests/tests.py → argus/scoring.py
- `test_suite()` --calls--> `score_job()`  [INFERRED]
  tests/tests.py → argus/scoring.py
- `main()` --calls--> `rank()`  [EXTRACTED]
  argus/discover.py → argus/scoring.py

## Import Cycles
- None detected.

## Communities (7 total, 1 thin omitted)

### Community 0 - "argus/dashboard.py"
Cohesion: 0.16
Nodes (20): _already_running(), _build_html(), current_profile(), dashboard.py — the local page: paste a CV, watch the jobs come in. Serve-only:…, One sentence for the current profile; the most wanted title is bold., The five answers behind config.toml, or None while the shipped example is in…, render(), _score_bar() (+12 more)

### Community 1 - "argus/discover.py"
Cohesion: 0.15
Nodes (21): _cell(), check_feeds(), extract_job_id(), extract_location(), fetch_feed(), load_seen_ids(), main(), parse_published() (+13 more)

### Community 2 - "argus/store.py"
Cohesion: 0.24
Nodes (14): add_jobs(), age_label(), clear_new(), get_status(), _load(), load_jobs(), parse_date(), datetime (+6 more)

### Community 3 - "Handler"
Cohesion: 0.23
Nodes (7): Handler, Write config.toml, apply the new weights in-process, forget unseen jobs, fetch., Run discover.py in the background. False when a run is already going., _run_discovery(), save_profile(), start_refresh(), BaseHTTPRequestHandler

### Community 4 - "cv.py"
Cohesion: 0.29
Nodes (10): _count(), extract_profile(), _list(), parse_answers(), _ranked(), cv.py — turns pasted text into the five setup answers. Two shapes go through…, The five-line answer, with any chatbot chatter around it. None if no `titles:`…, Guess the five answers from a CV. Titles and skills by frequency; country by… (+2 more)

### Community 5 - "setup.py"
Cohesion: 0.22
Nodes (10): build_config(), _clean(), is_profile(), _news_feed(), setup.py — writes config.toml from a few answers. Backs the "Set up profile"…, True when config.toml was written from answers, not the shipped example., The five answers behind a parsed config.toml — the inverse of build_config., Google News RSS scoped to one job site — the only way to get LinkedIn/Naukri as… (+2 more)

## Knowledge Gaps
- **1 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `rank()` connect `argus/dashboard.py` to `argus/discover.py`?**
  _High betweenness centrality (0.162) - this node is a cross-community bridge._
- **Why does `Handler` connect `Handler` to `argus/dashboard.py`?**
  _High betweenness centrality (0.069) - this node is a cross-community bridge._
- **Why does `main()` connect `argus/discover.py` to `argus/dashboard.py`?**
  _High betweenness centrality (0.028) - this node is a cross-community bridge._
- **Are the 4 inferred relationships involving `test_suite()` (e.g. with `_build_html()` and `render()`) actually correct?**
  _`test_suite()` has 4 INFERRED edges - model-reasoned connections that need verification._