"""
dashboard.py — renders the job dashboard and serves it locally.

Serve-only: every visit renders fresh from the store, so there is no
dashboard.html artifact to go stale.

Usage:
    python dashboard.py      # opens http://localhost:8765/
"""

import socket
import webbrowser
from datetime import datetime
from html import escape
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import unquote

import store
from scoring import rank

PORT = 8765
WINDOW_DAYS = 21

# the route is shared by the emitted JS and the Handler below — rename in one place
APPLIED_ROUTE = "/applied/"

# one neutral palette, one accent; the table is the page
_CSS = """:root {
  --bg: #f6f7f9; --card: #ffffff; --text: #17181c; --muted: #6b7280;
  --line: #e6e8ec; --accent: #2457d6;
}
* { box-sizing: border-box; }
body {
  margin: 0 auto; padding: 2.5rem 1.5rem 4rem; max-width: 72rem;
  background: var(--bg); color: var(--text);
  font: 15px/1.5 -apple-system, "Segoe UI", system-ui, sans-serif;
}
header { display: flex; align-items: baseline; justify-content: space-between; gap: 1rem; }
h1 { margin: 0; font-size: 1.35rem; font-weight: 600; letter-spacing: -.01em; }
.muted { color: var(--muted); font-size: .85rem; }
.stats { display: flex; flex-wrap: wrap; gap: 2.5rem; margin: 1.5rem 0 1.25rem; }
.stat b { display: block; font-size: 1.75rem; font-weight: 600; line-height: 1.1; font-variant-numeric: tabular-nums; }
.stat span { font-size: .8rem; color: var(--muted); }
.card { background: var(--card); border: 1px solid var(--line); border-radius: .75rem; overflow: hidden; }
table { width: 100%; border-collapse: collapse; font-size: .9rem; }
th, td { padding: .65rem .9rem; text-align: left; border-bottom: 1px solid var(--line); vertical-align: middle; }
th {
  position: sticky; top: 0; background: var(--card); color: var(--muted);
  font-weight: 500; font-size: .72rem; text-transform: uppercase; letter-spacing: .05em;
}
tr:last-child td { border-bottom: none; }
td.num, th.num { text-align: right; font-variant-numeric: tabular-nums; }
td.num { font-weight: 600; }
td.title { font-weight: 500; }
td.act { white-space: nowrap; text-align: right; }
a.apply, button.mark {
  display: inline-block; padding: .3rem .75rem; border-radius: .5rem;
  font: 600 .8rem/1.4 inherit; cursor: pointer;
}
a.apply { background: var(--accent); color: #fff; text-decoration: none; }
a.apply:hover { filter: brightness(1.1); }
button.mark { margin-left: .35rem; border: 1px solid var(--line); background: var(--card); color: var(--text); }
button.mark:hover:enabled { border-color: var(--accent); color: var(--accent); }
button.mark:disabled { opacity: .5; cursor: default; }
tr.done td { color: var(--muted); }
tr.done td.title { text-decoration: line-through; }
.empty { margin: 0; padding: 3rem 1rem; text-align: center; color: var(--muted); }"""


def _build_html(ranked_jobs: list[dict], jobs_week: int, apps_week: int) -> str:
    # escape at the render boundary — feed data is untrusted
    rows = []
    for j in ranked_jobs:
        status = store.get_status(j)
        applied = status != "new"  # anything past 'new' is applied to
        if applied:
            act = f"<span class='muted'>{escape(status.title())}</span>"
        elif j.get("link"):
            act = (
                f"<a class='apply' href='{escape(j['link'])}' target='_blank' rel='noopener'>Apply</a>"
                f"<button class='mark' data-id='{escape(j.get('id', ''))}'>&#10003; Applied</button>"
            )
        else:
            act = "<span class='muted'>—</span>"
        rows.append(
            f"<tr{' class=done' if applied else ''}>"
            f"<td class='num'>{j['_score']}</td>"
            f"<td class='title'>{escape(j.get('title', ''))}</td>"
            f"<td>{escape(j.get('company', ''))}</td>"
            f"<td class='muted'>{escape(j.get('location', ''))}</td>"
            f"<td class='muted'>{escape(j.get('source', ''))}</td>"
            f"<td class='muted'>{store.age_label(j.get('published', ''))}</td>"
            f"<td class='act'>{act}</td></tr>"
        )
    table = (
        "<table><thead><tr><th class='num'>Score</th><th>Role</th><th>Company</th>"
        "<th>Location</th><th>Source</th><th>Posted</th><th></th></tr></thead>"
        f"<tbody>{''.join(rows)}</tbody></table>"
        if rows else
        f"<p class='empty'>No jobs in the last {WINDOW_DAYS} days. Run <code>python discover.py</code>.</p>"
    )
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Argus</title>
<style>
{_CSS}
</style>
</head>
<body>
<header>
  <h1>Argus</h1>
  <span class="muted">Updated {datetime.now():%Y-%m-%d %H:%M}</span>
</header>
<div class="stats">
  <div class="stat"><b>{len(ranked_jobs)}</b><span>Jobs · last {WINDOW_DAYS} days</span></div>
  <div class="stat"><b>{jobs_week}</b><span>New this week</span></div>
  <div class="stat"><b>{apps_week}</b><span>Applied this week</span></div>
</div>
<div class="card">{table}</div>
<script>
// one click, one write — the server is the only state, nothing cached client-side
document.querySelectorAll('button.mark').forEach(b =>
  b.addEventListener('click', async () => {{
    b.disabled = true;
    const r = await fetch('{APPLIED_ROUTE}' + encodeURIComponent(b.dataset.id),
                          {{method: 'POST'}});
    if (r.ok) location.reload();
    else {{ b.disabled = false; b.textContent = 'failed'; }}
  }})
);
</script>
</body>
</html>"""


def render() -> str:
    """Load the store and return the dashboard as an HTML string."""
    all_jobs = store.load_jobs()
    jobs = store.this_week(all_jobs, "published", store.UTC_FMT, days=WINDOW_DAYS)
    # applications come from the full store, not the window — an old posting you
    # applied to still counts
    apps = [j for j in all_jobs if store.get_status(j) != "new"]
    return _build_html(
        ranked_jobs=rank(jobs),
        jobs_week=len(store.this_week(jobs, "published", store.UTC_FMT)),
        apps_week=len(store.this_week(apps, "status_date")),
    )


# ─── Server ──────────────────────────────────────────────────────────────


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path in ("/", "/dashboard.html"):
            body = render().encode("utf-8")
        else:
            self.send_error(404)
            return
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):
        job_id = unquote(self.path.rsplit("/", 1)[-1])
        if self.path.startswith(APPLIED_ROUTE) and store.set_status(job_id, "applied"):
            self.send_response(204)
        else:
            self.send_response(404)
        self.end_headers()

    def log_message(self, format: str, *args) -> None:  # quiet console
        pass


def _already_running() -> bool:
    # ponytail: Windows SO_REUSEADDR lets a busy port re-bind without OSError,
    # so probe by connecting instead of catching a bind error.
    with socket.socket() as s:
        s.settimeout(0.3)
        return s.connect_ex(("127.0.0.1", PORT)) == 0


def serve() -> None:
    """Serve the dashboard on PORT, rendering fresh on every request."""
    url = f"http://localhost:{PORT}/"
    webbrowser.open(url)  # always open a fresh tab
    if _already_running():
        print(f"Dashboard already running at {url}")
        return
    print(f"Dashboard at {url}  (Ctrl+C to stop)")
    HTTPServer(("127.0.0.1", PORT), Handler).serve_forever()


if __name__ == "__main__":
    serve()
