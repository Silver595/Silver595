#!/usr/bin/env python3
"""
today.py — pulls live GitHub stats for a user and renders them into two
hand-designed SVG cards (dark_mode.svg / light_mode.svg) for use as a
GitHub profile README header.

Inspired by the automation pattern used in Andrew6rant/Andrew6rant, but
with an original script and an original card design.

Requires:
    - env var ACCESS_TOKEN: a GitHub personal access token with `repo`
      and `read:user` scopes (stored as a repo secret, injected by the
      Actions workflow).
    - env var GITHUB_ACTOR (optional): defaults to USERNAME below if unset.

Run locally:
    ACCESS_TOKEN=ghp_xxx python3 today.py
"""

import os
import json
import datetime
import requests

# ---------------------------------------------------------------------------
# Config — edit these for your own profile
# ---------------------------------------------------------------------------
USERNAME = os.environ.get("GH_USERNAME", "Silver595")
DISPLAY_NAME = "Akash"
ALIAS = "aka silver"
LOCATION = "Pune, India"
CACHE_PATH = "cache/stats.json"

GITHUB_API = "https://api.github.com/graphql"
TOKEN = os.environ.get("ACCESS_TOKEN")
HEADERS = {"Authorization": f"bearer {TOKEN}"} if TOKEN else {}

# ---------------------------------------------------------------------------
# GraphQL query — pulls repos, stars, followers, and contribution totals
# in a single round trip instead of hammering the REST API per-repo.
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
    values on any failure so the workflow never breaks the README."""
    if not TOKEN:
        print("No ACCESS_TOKEN set — falling back to cache.")
        return load_cache()

    try:
        resp = requests.post(
            GITHUB_API,
            json={"query": QUERY, "variables": {"login": USERNAME}},
            headers=HEADERS,
            timeout=15,
        )
        resp.raise_for_status()
        data = resp.json()["data"]["user"]

        repos = data["repositories"]["nodes"]
        total_stars = sum(r["stargazers"]["totalCount"] for r in repos)
        total_forks = sum(r["forkCount"] for r in repos)

        lang_counts = {}
        for r in repos:
            lang = r["primaryLanguage"]["name"] if r["primaryLanguage"] else None
            if lang:
                lang_counts[lang] = lang_counts.get(lang, 0) + 1
        top_langs = sorted(lang_counts.items(), key=lambda kv: -kv[1])[:4]

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
            "updated": datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC"),
        }
        save_cache(stats)
        return stats

    except Exception as e:
        print(f"Live fetch failed ({e}), falling back to cache.")
        return load_cache()


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

WIDTH, HEIGHT = 900, 460


def render_svg(stats, theme_name):
    t = THEMES[theme_name]
    lang_line = "   ·   ".join(f"{name}" for name, _ in stats["top_langs"]) or "—"

    svg = f'''<svg width="{WIDTH}" height="{HEIGHT}" viewBox="0 0 {WIDTH} {HEIGHT}" xmlns="http://www.w3.org/2000/svg">
  <style>
    .mono {{ font-family: 'SFMono-Regular', Consolas, 'Liberation Mono', Menlo, monospace; }}
    .name {{ font-size: 30px; fill: {t['text_primary']}; }}
    .alias {{ font-size: 18px; fill: {t['accent_blue']}; }}
    .muted {{ font-size: 15px; fill: {t['text_muted']}; }}
    .label {{ font-size: 15px; fill: {t['text_dim']}; }}
    .body {{ font-size: 16px; fill: {t['text_body']}; }}
    .statnum {{ font-size: 26px; fill: {t['accent_amber']}; }}
    .statlabel {{ font-size: 13px; fill: {t['text_dim']}; }}
    .key {{ font-size: 16px; fill: {t['accent_blue']}; }}
  </style>

  <rect x="0.5" y="0.5" width="{WIDTH-1}" height="{HEIGHT-1}" rx="12" fill="{t['bg']}" stroke="{t['card_stroke']}" stroke-width="1"/>

  <circle cx="34" cy="34" r="6" fill="#e06c75"/>
  <circle cx="56" cy="34" r="6" fill="#e5c07b"/>
  <circle cx="78" cy="34" r="6" fill="#98c379"/>
  <text x="{WIDTH-40}" y="39" text-anchor="end" class="mono muted">~/{USERNAME.lower()}</text>

  <text x="40" y="94" class="mono name">{DISPLAY_NAME}</text>
  <text x="40" y="122" class="mono alias">{ALIAS}</text>
  <text x="40" y="150" class="mono muted">{LOCATION}</text>

  <line x1="40" y1="176" x2="{WIDTH-40}" y2="176" stroke="{t['divider']}" stroke-width="1" stroke-dasharray="4 4"/>

  <text x="40" y="204" class="mono label">stack</text>
  <text x="40" y="230" class="mono body">{lang_line}</text>

  <line x1="40" y1="256" x2="{WIDTH-40}" y2="256" stroke="{t['divider']}" stroke-width="1" stroke-dasharray="4 4"/>

  <text x="40" y="284" class="mono label">live stats</text>

  <text x="40" y="326" class="mono statnum">{stats['repos']}</text>
  <text x="40" y="348" class="mono statlabel">repositories</text>

  <text x="190" y="326" class="mono statnum">{stats['stars']}</text>
  <text x="190" y="348" class="mono statlabel">stars earned</text>

  <text x="340" y="326" class="mono statnum">{stats['commits']}</text>
  <text x="340" y="348" class="mono statlabel">commits (this year)</text>

  <text x="540" y="326" class="mono statnum">{stats['followers']}</text>
  <text x="540" y="348" class="mono statlabel">followers</text>

  <text x="680" y="326" class="mono statnum">{stats['forks']}</text>
  <text x="680" y="348" class="mono statlabel">forks received</text>

  <line x1="40" y1="378" x2="{WIDTH-40}" y2="378" stroke="{t['divider']}" stroke-width="1" stroke-dasharray="4 4"/>

  <text x="40" y="406" class="mono muted">last synced {stats['updated']}</text>
  <circle cx="{WIDTH-196}" cy="401" r="5" fill="{t['accent_green']}"/>
  <text x="{WIDTH-184}" y="406" class="mono muted">auto-updates 12h</text>
</svg>'''
    return svg


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
