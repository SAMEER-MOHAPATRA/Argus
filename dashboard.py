"""
dashboard.py — the local page: paste a CV, watch the jobs come in.

Serve-only: every visit renders fresh from the store, so there is no
dashboard.html artifact to go stale. Discovery runs as a background
subprocess so a fresh process reads the new config.toml.

Usage:
    python dashboard.py      # opens http://localhost:8765/
"""

import json
import socket
import subprocess
import sys
import threading
import tomllib
import webbrowser
from datetime import datetime
from html import escape
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote

import config
import cv
import scoring
import setup
import store
from scoring import rank

HERE = Path(__file__).parent
PORT = 8765
WINDOW_DAYS = 21
REFRESH_DAYS = 7  # how far back a background fetch looks

# the route is shared by the emitted JS and the Handler below — rename in one place
APPLIED_ROUTE = "/applied/"

_TEMPLATE = (HERE / "page.html").read_text(encoding="utf-8")

# scoring imports these by value, so a new profile must be copied over
_WEIGHTS = ("TITLE_POINTS", "LOCATION_POINTS", "SKILL_KEYWORDS", "SKILL_POINT", "SKILL_CAP")


# ─── Profile ─────────────────────────────────────────────────────────────


def current_profile() -> dict | None:
    """The five answers behind config.toml, or None while the shipped example is in place."""
    try:
        text = config.CONFIG_PATH.read_text(encoding="utf-8")
    except FileNotFoundError:
        return None
    if not setup.is_profile(text):
        return None
    return setup.read_profile(tomllib.loads(text))


def save_profile(fields: dict, refresh: bool = True) -> None:
    """Write config.toml, apply the new weights in-process, forget unseen jobs, fetch."""
    text = setup.build_config(**fields)  # ValueError when there is no title
    config.CONFIG_PATH.write_text(text, encoding="utf-8")
    config.reload()
    for name in _WEIGHTS:
        setattr(scoring, name, getattr(config, name))
    store.clear_new()  # the old profile's matches would score against the new one
    if refresh:
        start_refresh()


# ─── Background refresh ──────────────────────────────────────────────────

_refresh = {"running": False, "error": None}
_refresh_lock = threading.Lock()


def _run_discovery() -> None:
    try:
        r = subprocess.run(
            [sys.executable, str(HERE / "discover.py"), "--days", str(REFRESH_DAYS)],
            cwd=HERE, capture_output=True, text=True, timeout=900,
        )
        lines = r.stderr.strip().splitlines()
        _refresh["error"] = None if r.returncode == 0 else (lines[-1] if lines else "discovery failed")
    except Exception as e:  # noqa: BLE001 — surfaced on the page, never crashes the server
        _refresh["error"] = str(e)
    finally:
        _refresh["running"] = False


def start_refresh() -> bool:
    """Run discover.py in the background. False when a run is already going."""
    with _refresh_lock:
        if _refresh["running"]:
            return False
        _refresh["running"] = True
    threading.Thread(target=_run_discovery, daemon=True).start()
    return True


# ─── Page ────────────────────────────────────────────────────────────────


def _score_pill(score: int) -> str:
    tier = "hi" if score >= 70 else "mid" if score >= 40 else "lo"
    return f"<span class='score {tier}'>{score}</span>"


def _table(ranked_jobs: list[dict], profile: dict | None) -> str:
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
            f"<td class='num'>{_score_pill(j['_score'])}</td>"
            f"<td class='title'>{escape(j.get('title', ''))}</td>"
            f"<td>{escape(j.get('company', ''))}</td>"
            f"<td class='muted'>{escape(j.get('location', ''))}</td>"
            f"<td class='muted'>{escape(j.get('source', ''))}</td>"
            f"<td class='muted'>{store.age_label(j.get('published', ''))}</td>"
            f"<td class='act'>{act}</td></tr>"
        )
    if rows:
        return (
            "<table><thead><tr><th class='num'>Score</th><th>Role</th><th>Company</th>"
            "<th>Location</th><th>Source</th><th>Posted</th><th></th></tr></thead>"
            f"<tbody>{''.join(rows)}</tbody></table>"
        )
    if profile is None:
        msg = "Paste your CV above to start."
    elif _refresh["running"]:
        msg = "Fetching jobs… the page refreshes itself when the first batch is in."
    else:
        msg = f"No matches in the last {WINDOW_DAYS} days. Widen the titles with Edit, or press Refresh."
    return f"<p class='empty'>{msg}</p>"


def _status_text() -> str:
    if _refresh["running"]:
        return "Fetching jobs…"
    if _refresh["error"]:
        return f"Last fetch failed: {_refresh['error']}"
    try:
        when = datetime.fromtimestamp(store.CSV_PATH.stat().st_mtime)
    except FileNotFoundError:
        return "No jobs fetched yet"
    return f"Updated {when:%Y-%m-%d %H:%M}"


def _build_html(ranked_jobs: list[dict], jobs_week: int, apps_week: int) -> str:
    profile = current_profile()
    p = profile or {"titles": [], "country": "US", "remote": True, "skills": [], "locations": []}
    chips = "".join(
        f"<span class='chip{' top' if i == 0 else ''}'>{escape(t)}</span>" for i, t in enumerate(p["titles"])
    )
    meta = [setup.COUNTRIES.get(p["country"], p["country"])]
    if p["remote"]:
        meta.append("remote OK")
    if p["locations"]:
        meta.append(", ".join(p["locations"]).title())
    meta.append(f"{len(p['skills'])} skills · {len(config.FEEDS)} feeds")
    options = "".join(
        f"<option value='{code}'{' selected' if code == p['country'] else ''}>{escape(name)}</option>"
        for code, name in setup.COUNTRIES.items()
    )
    tokens = {
        "MODE": "watching" if profile else "onboarding",
        "REFRESHING": "1" if _refresh["running"] else "0",
        "REFRESH_DISABLED": "disabled" if _refresh["running"] or not profile else "",
        "STATUS": escape(_status_text()),
        "HERO_OPEN": "" if profile else "open",
        "PROMPT": escape(cv.PROMPT.strip()),
        "TITLE_CHIPS": chips,
        "META": escape(" · ".join(meta)),
        "TITLES": escape(", ".join(p["titles"])),
        "SKILLS": escape(", ".join(p["skills"])),
        "LOCATIONS": escape(", ".join(p["locations"])),
        "COUNTRY_OPTIONS": options,
        "REMOTE_CHECKED": "checked" if p["remote"] else "",
        "N_OPEN": str(len(ranked_jobs)),
        "N_WEEK": str(jobs_week),
        "N_APPLIED": str(apps_week),
        "WINDOW_DAYS": str(WINDOW_DAYS),
        "TABLE": _table(ranked_jobs, profile),
        "APPLIED_ROUTE": APPLIED_ROUTE,
    }
    html = _TEMPLATE
    for key, value in tokens.items():
        html = html.replace("{{" + key + "}}", value)
    return html


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
    def _send(self, code: int, body: bytes, ctype: str) -> None:
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path in ("/", "/dashboard.html"):
            self._send(200, render().encode("utf-8"), "text/html; charset=utf-8")
        elif self.path == "/status":
            body = {"refreshing": _refresh["running"], "error": _refresh["error"]}
            self._send(200, json.dumps(body).encode("utf-8"), "application/json")
        else:
            self.send_error(404)

    def _json_body(self) -> dict:
        n = int(self.headers.get("Content-Length") or 0)
        return json.loads(self.rfile.read(n) or b"{}") if n else {}

    def do_POST(self):
        if self.path.startswith(APPLIED_ROUTE):
            job_id = unquote(self.path.rsplit("/", 1)[-1])
            self.send_response(204 if store.set_status(job_id, "applied") else 404)
            self.end_headers()
        elif self.path == "/profile":
            try:
                body = self._json_body()
                pasted = bool(body.get("text"))
                fields = cv.read(body["text"]) if pasted else body.get("fields") or {}
                save_profile(fields)
            except (ValueError, KeyError, TypeError) as e:
                msg = (
                    "No job title found in that text. Use the chatbot prompt below and paste its answer."
                    if pasted else str(e) or "Invalid profile."
                )
                self._send(422, msg.encode("utf-8"), "text/plain; charset=utf-8")
                return
            self.send_response(204)
            self.end_headers()
        elif self.path == "/refresh":
            start_refresh()
            self.send_response(204)
            self.end_headers()
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
    if current_profile():
        start_refresh()  # each launch fetches; the example profile never pollutes the store
    print(f"Dashboard at {url}  (Ctrl+C to stop)")
    ThreadingHTTPServer(("127.0.0.1", PORT), Handler).serve_forever()


if __name__ == "__main__":
    serve()
