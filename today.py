#!/usr/bin/env python3

import os
import json
import datetime
from zoneinfo import ZoneInfo
import requests

IST = ZoneInfo("Asia/Kolkata")


def now_ist_string():
    return datetime.datetime.now(IST).strftime("%Y-%m-%d %I:%M %p IST")

USERNAME = os.environ.get("GH_USERNAME", "Silver595")
DISPLAY_NAME = "Akash"
ALIAS = "aka silver"
LOCATION = "Pune, India"
CACHE_PATH = "cache/stats.json"

CONTACTS = [
    ("email",     "akashpurjalkar@gmail.com"),
    ("github",    "github.com/Silver595"),
    ("linkedin",  ""),          # e.g. "linkedin.com/in/yourhandle"
    ("portfolio", "akashpurjalkar.online"),
    ("project",   ""),          # optional — e.g. a flagship project URL
]

GITHUB_API = "https://api.github.com/graphql"
TOKEN = os.environ.get("ACCESS_TOKEN")
HEADERS = {"Authorization": f"bearer {TOKEN}"} if TOKEN else {}


# ---------------------------------------------------------------------------
QUERY = """
query($login: String!) {
  user(login: $login) {
    followers { totalCount }
    repositories(first: 100, ownerAffiliations: OWNER, isFork: false, privacy: PUBLIC) {
      totalCount
      nodes {
        name
        stargazers { totalCount }
        forkCount
        primaryLanguage { name }
      }
    }
    contributionsCollection {
      totalCommitContributions
      restrictedContributionsCount
      contributionCalendar {
        totalContributions
      }
    }
    pullRequests(first: 1) { totalCount }
    issues(first: 1) { totalCount }
  }
}
"""


def fetch_stats():
    """Query GitHub's GraphQL API for live stats. Falls back to cached
    values on any failure so the workflow never breaks the README —
    but the SVG will visibly say 'cached' instead of silently pretending
    to be live, so a broken token is obvious at a glance."""
    if not TOKEN:
        print("::warning::No ACCESS_TOKEN set — falling back to cache.")
        stats = load_cache()
        stats["source"] = "cached (no token)"
        return stats

    try:
        resp = requests.post(
            GITHUB_API,
            json={"query": QUERY, "variables": {"login": USERNAME}},
            headers=HEADERS,
            timeout=15,
        )
        resp.raise_for_status()
        payload = resp.json()

        if "errors" in payload:
            raise RuntimeError(payload["errors"])

        data = payload["data"]["user"]

        repos = data["repositories"]["nodes"]
        total_stars = sum(r["stargazers"]["totalCount"] for r in repos)
        total_forks = sum(r["forkCount"] for r in repos)

        lang_counts = {}
        for r in repos:
            lang = r["primaryLanguage"]["name"] if r["primaryLanguage"] else None
            if lang:
                lang_counts[lang] = lang_counts.get(lang, 0) + 1
        # NOTE: item 4 — no hard cap here anymore. All languages found are
        # kept, sorted by frequency; render_svg() decides how many fit.
        top_langs = sorted(lang_counts.items(), key=lambda kv: -kv[1])

        contrib = data["contributionsCollection"]
        total_commits = (
            contrib["totalCommitContributions"]
            + contrib["restrictedContributionsCount"]
        )

        stats = {
            "repos": data["repositories"]["totalCount"],
            "followers": data["followers"]["totalCount"],
            "stars": total_stars,
            "forks": total_forks,
            "commits": total_commits,
            "contributions_last_year": contrib["contributionCalendar"]["totalContributions"],
            "top_langs": top_langs,
            "updated": now_ist_string(),
            "source": "live",
        }
        save_cache(stats)
        return stats

    except Exception as e:
        print(f"::error::Live fetch failed ({e}) — falling back to cache.")
        stats = load_cache()
        stats["source"] = f"cached (fetch failed)"
        return stats


def load_cache():
    if os.path.exists(CACHE_PATH):
        with open(CACHE_PATH) as f:
            return json.load(f)
    # first-ever run, no cache yet — safe zeroed defaults
    return {
        "repos": 0, "followers": 0, "stars": 0, "forks": 0,
        "commits": 0, "contributions_last_year": 0, "top_langs": [],
        "updated": "never",
    }


def save_cache(stats):
    os.makedirs(os.path.dirname(CACHE_PATH), exist_ok=True)
    with open(CACHE_PATH, "w") as f:
        json.dump(stats, f, indent=2)


# ---------------------------------------------------------------------------
# SVG rendering — our own design, not a copy of anyone else's card.
# Two themes rendered from one template so GitHub's #gh-dark/#gh-light-mode
# picture toggle can pick the right one automatically.
# ---------------------------------------------------------------------------
THEMES = {
    "dark": {
        "bg": "#0b0e14", "card_stroke": "#1c2230", "divider": "#1c2230",
        "text_primary": "#e6e9ef", "text_muted": "#7d8590", "text_dim": "#565f78",
        "accent_blue": "#7aa2f7", "accent_amber": "#e5c07b", "accent_green": "#98c379",
        "text_body": "#c8cdd8",
    },
    "light": {
        "bg": "#ffffff", "card_stroke": "#d0d7de", "divider": "#e8ecef",
        "text_primary": "#1c2230", "text_muted": "#57606a", "text_dim": "#8b949e",
        "accent_blue": "#2563eb", "accent_amber": "#b8860b", "accent_green": "#1a7f37",
        "text_body": "#24292f",
    },
}

def compute_height(stats):
    """Height depends on how many language-lines wrap and how many
    contact rows are visible (items 4 + 5 both add variable-length
    content), so the canvas is sized to fit instead of hardcoded."""
    lang_names = [name for name, _ in stats["top_langs"]] or ["—"]
    n_lang_lines = len(wrap_items(lang_names, max_per_line=6))
    n_contacts = len([1 for _, v in CONTACTS if v])

    y = 186                                          # header -> first rule
    y += 26 + (n_lang_lines - 1) * 26 + 18            # stack lines -> rule2
    y += 28 + 42 + 22 + 30                            # stats block -> rule3
    y += 28 + 32 + max(n_contacts, 1) * 30 + 4        # connect block -> rule4
    y += 28 + 60                                      # footer text + generous bottom margin
    return y


WIDTH = 1000


def wrap_items(items, max_per_line=6):
    """Split a list of language names into lines for wrapping instead of
    overflowing the card edge when the list grows (item 4)."""
    lines, current = [], []
    for i, name in enumerate(items):
        current.append(name)
        if len(current) == max_per_line:
            lines.append(current)
            current = []
    if current:
        lines.append(current)
    return lines


def render_svg(stats, theme_name):
    t = THEMES[theme_name]
    HEIGHT = compute_height(stats)
    lang_names = [name for name, _ in stats["top_langs"]] or ["—"]
    lang_lines = wrap_items(lang_names, max_per_line=6)

    is_live = stats.get("source") == "live"
    status_color = t["accent_green"] if is_live else "#e06c75"
    status_text = "live" if is_live else stats.get("source", "cached")

    parts = [f'''<svg width="{WIDTH}" height="{HEIGHT}" viewBox="0 0 {WIDTH} {HEIGHT}" xmlns="http://www.w3.org/2000/svg">
  <style>
    .mono {{ font-family: 'SFMono-Regular', Consolas, 'Liberation Mono', Menlo, monospace; }}
    .name {{ font-size: 32px; fill: {t['text_primary']}; }}
    .alias {{ font-size: 19px; fill: {t['accent_blue']}; }}
    .muted {{ font-size: 15px; fill: {t['text_muted']}; }}
    .label {{ font-size: 15px; fill: {t['text_dim']}; }}
    .body {{ font-size: 17px; fill: {t['text_body']}; }}
    .statnum {{ font-size: 27px; fill: {t['accent_amber']}; }}
    .statlabel {{ font-size: 13px; fill: {t['text_dim']}; }}
    .key {{ font-size: 16px; fill: {t['accent_blue']}; }}
    .val {{ font-size: 16px; fill: {t['text_body']}; }}
  </style>

  <rect x="0.5" y="0.5" width="{WIDTH-1}" height="{HEIGHT-1}" rx="14" fill="{t['bg']}" stroke="{t['card_stroke']}" stroke-width="1"/>

  <circle cx="36" cy="36" r="6" fill="#e06c75"/>
  <circle cx="58" cy="36" r="6" fill="#e5c07b"/>
  <circle cx="80" cy="36" r="6" fill="#98c379"/>
  <text x="{WIDTH-44}" y="41" text-anchor="end" class="mono muted">~/{USERNAME.lower()}</text>

  <text x="44" y="100" class="mono name">{DISPLAY_NAME}</text>
  <text x="44" y="130" class="mono alias">{ALIAS}</text>
  <text x="44" y="158" class="mono muted">{LOCATION}</text>

  <line x1="44" y1="186" x2="{WIDTH-44}" y2="186" stroke="{t['divider']}" stroke-width="1" stroke-dasharray="4 4"/>

  <text x="44" y="214" class="mono label">stack</text>''']

    # --- item 4: wrapped, unlimited-length language block ---
    y = 240
    for line in lang_lines:
        parts.append(f'  <text x="44" y="{y}" class="mono body">{"   ·   ".join(line)}</text>')
        y += 26

    rule2_y = y + 18
    parts.append(f'  <line x1="44" y1="{rule2_y}" x2="{WIDTH-44}" y2="{rule2_y}" stroke="{t["divider"]}" stroke-width="1" stroke-dasharray="4 4"/>')

    stats_label_y = rule2_y + 28
    parts.append(f'  <text x="44" y="{stats_label_y}" class="mono label">live stats</text>')

    row_y = stats_label_y + 42
    row_label_y = row_y + 22
    cols = [
        (44,  stats['repos'],     "repositories"),
        (194, stats['stars'],     "stars earned"),
        (344, stats['commits'],   "commits (this yr)"),
        (554, stats['followers'], "followers"),
        (704, stats['forks'],     "forks received"),
    ]
    for x, val, label in cols:
        parts.append(f'  <text x="{x}" y="{row_y}" class="mono statnum">{val}</text>')
        parts.append(f'  <text x="{x}" y="{row_label_y}" class="mono statlabel">{label}</text>')

    rule3_y = row_label_y + 30
    parts.append(f'  <line x1="44" y1="{rule3_y}" x2="{WIDTH-44}" y2="{rule3_y}" stroke="{t["divider"]}" stroke-width="1" stroke-dasharray="4 4"/>')

    # --- item 5: contacts / links block ---
    connect_label_y = rule3_y + 28
    parts.append(f'  <text x="44" y="{connect_label_y}" class="mono label">connect</text>')

    c_y = connect_label_y + 32
    visible_contacts = [(k, v) for k, v in CONTACTS if v]
    for key, val in visible_contacts:
        parts.append(f'  <text x="44" y="{c_y}" class="mono key">{key}</text>')
        parts.append(f'  <text x="200" y="{c_y}" class="mono val">{val}</text>')
        c_y += 30

    rule4_y = c_y + 4
    parts.append(f'  <line x1="44" y1="{rule4_y}" x2="{WIDTH-44}" y2="{rule4_y}" stroke="{t["divider"]}" stroke-width="1" stroke-dasharray="4 4"/>')

    footer_y = rule4_y + 28
    parts.append(f'  <text x="44" y="{footer_y}" class="mono muted">last synced {stats["updated"]}</text>')
    parts.append(f'  <circle cx="{WIDTH-206}" cy="{footer_y-5}" r="5" fill="{status_color}"/>')
    parts.append(f'  <text x="{WIDTH-194}" y="{footer_y}" class="mono muted">{status_text}</text>')

    parts.append('</svg>')
    return "\n".join(parts)


def main():
    stats = fetch_stats()
    for theme in ("dark", "light"):
        svg = render_svg(stats, theme)
        out_path = f"{theme}_mode.svg"
        with open(out_path, "w") as f:
            f.write(svg)
        print(f"Wrote {out_path}")


if __name__ == "__main__":
    main()
