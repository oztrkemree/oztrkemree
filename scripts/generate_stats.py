#!/usr/bin/env python3
"""Regenerates the profile cards in assets/ from the GitHub GraphQL API.

Env:
  GH_TOKEN   token used for the API (a PAT with read:user + repo includes private data)
  GH_USER    GitHub login (default: repo owner / oztrkemree)
"""
import datetime as dt
import json
import os
import sys
import urllib.request
from html import escape

USER = os.environ.get("GH_USER") or os.environ.get("GITHUB_REPOSITORY_OWNER") or "oztrkemree"
TOKEN = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "assets")

ACCENT = "#C41E3A"
BG = "#0d1117"
FONT = "-apple-system,BlinkMacSystemFont,Segoe UI,Helvetica,Arial,sans-serif"
LEVEL_COLORS = {
    "NONE": "#161b22",
    "FIRST_QUARTILE": "#4a0f1a",
    "SECOND_QUARTILE": "#7a1828",
    "THIRD_QUARTILE": ACCENT,
    "FOURTH_QUARTILE": "#ff6b73",
}

QUERY = """
query($login: String!) {
  user(login: $login) {
    name
    pullRequests { totalCount }
    repositories(ownerAffiliations: OWNER, isFork: false) { totalCount }
    repositoriesContributedTo(contributionTypes: [COMMIT, PULL_REQUEST, ISSUE, PULL_REQUEST_REVIEW]) { totalCount }
    contributionsCollection {
      contributionCalendar {
        totalContributions
        weeks { contributionDays { date contributionCount contributionLevel weekday } }
      }
      commitContributionsByRepository(maxRepositories: 100) {
        repository {
          isFork
          languages(first: 10, orderBy: {field: SIZE, direction: DESC}) {
            edges { size node { name color } }
          }
        }
      }
    }
  }
}
"""


def gql(query, variables):
    if not TOKEN:
        sys.exit("GH_TOKEN (or GITHUB_TOKEN) is not set")
    req = urllib.request.Request(
        "https://api.github.com/graphql",
        data=json.dumps({"query": query, "variables": variables}).encode(),
        headers={"Authorization": f"bearer {TOKEN}", "Content-Type": "application/json",
                 "User-Agent": "profile-stats"},
    )
    with urllib.request.urlopen(req, timeout=60) as r:
        data = json.load(r)
    if data.get("errors"):
        sys.exit(f"GraphQL error: {data['errors']}")
    return data["data"]


def fmt_short(n):
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f}M".replace(".0M", "M")
    if n >= 1000:
        return f"{n / 1000:.1f}k".replace(".0k", "k")
    return str(n)


def fmt_date(d, with_year=False):
    s = f"{d.strftime('%b')} {d.day}"
    return f"{s}, {d.year}" if with_year else s


def text(x, y, s, fill="#c9d1d9", size=13, weight=None, anchor=None):
    attrs = f'x="{x}" y="{y}"'
    if anchor:
        attrs += f' text-anchor="{anchor}"'
    attrs += f' fill="{fill}" font-size="{size}"'
    if weight:
        attrs += f' font-weight="{weight}"'
    return f'<text {attrs} font-family="{FONT}">{escape(str(s))}</text>'


# --------------------------------------------------------------------------- data

def compute_streaks(days):
    """days: list of (date, count) sorted ascending. Returns (current, longest) as (len, start, end)."""
    today = days[-1][0]
    # longest
    longest = (0, None, None)
    run_start, run_len = None, 0
    for d, c in days:
        if c > 0:
            if run_len == 0:
                run_start = d
            run_len += 1
            if run_len > longest[0]:
                longest = (run_len, run_start, d)
        else:
            run_len = 0
    # current: today may still be empty without breaking the streak
    idx = len(days) - 1
    if days[idx][1] == 0:
        idx -= 1
    cur_len, cur_end = 0, days[idx][0] if idx >= 0 else today
    cur_start = cur_end
    while idx >= 0 and days[idx][1] > 0:
        cur_len += 1
        cur_start = days[idx][0]
        idx -= 1
    current = (cur_len, cur_start, cur_end) if cur_len else (0, today, today)
    return current, longest


def compute_languages(repos, limit=8):
    totals = {}
    for item in repos:
        repo = item["repository"]
        if repo.get("isFork"):
            continue
        for e in repo["languages"]["edges"]:
            name = e["node"]["name"]
            t = totals.setdefault(name, {"size": 0, "color": e["node"]["color"] or "#8b949e"})
            t["size"] += e["size"]
    total = sum(v["size"] for v in totals.values()) or 1
    langs = sorted(totals.items(), key=lambda kv: -kv[1]["size"])[:limit]
    return [(n, v["color"], v["size"] * 100 / total) for n, v in langs]


# --------------------------------------------------------------------------- cards

ICONS = {
    "contrib": "M8 0a8 8 0 1 1 0 16A8 8 0 0 1 8 0ZM1.5 8a6.5 6.5 0 1 0 13 0 6.5 6.5 0 0 0-13 0Zm7-3.25a.75.75 0 0 0-1.5 0v3.5c0 .192.077.377.215.516l2.25 2.25a.75.75 0 0 0 1.06-1.061L8.5 8.061V4.75Z",
    "pr": "M1.5 3.25a2.25 2.25 0 1 1 3 2.122v5.256a2.251 2.251 0 1 1-1.5 0V5.372A2.25 2.25 0 0 1 1.5 3.25Zm5.677-.177L9.25 1H6.5a.75.75 0 0 0 0 1.5h.75v5.878A2.251 2.251 0 0 1 10 11.25h.25a2.25 2.25 0 1 1 0 1.5H10A3.75 3.75 0 0 1 6.25 8.5V4.06l-.073.073a.75.75 0 0 1-1.06-1.06l2-2a.75.75 0 0 1 1.06 0Z",
    "repo": "M2 2.5A2.5 2.5 0 0 1 4.5 0h8.75a.75.75 0 0 1 .75.75v12.5a.75.75 0 0 1-.75.75h-2.5a.75.75 0 0 1 0-1.5h1.75v-2h-8a1 1 0 0 0-.714 1.7.75.75 0 1 1-1.072 1.05A2.495 2.495 0 0 1 2 11.5Zm10.5-1h-8a1 1 0 0 0 0-2h8ZM5 6.25a.75.75 0 0 1 .75-.75h5.5a.75.75 0 0 1 0 1.5h-5.5A.75.75 0 0 1 5 6.25Zm0-3a.75.75 0 0 1 .75-.75h5.5a.75.75 0 0 1 0 1.5h-5.5A.75.75 0 0 1 5 3.25Z",
    "contributed": "M0 1.75C0 .784.784 0 1.75 0h12.5C15.216 0 16 .784 16 1.75v12.5A1.75 1.75 0 0 1 14.25 16H1.75A1.75 1.75 0 0 1 0 14.25Zm1.75-.25a.25.25 0 0 0-.25.25v12.5c0 .138.112.25.25.25h12.5a.25.25 0 0 0 .25-.25V1.75a.25.25 0 0 0-.25-.25Zm7 7.75h3.5a.75.75 0 0 1 0 1.5h-3.5a.75.75 0 0 1 0-1.5ZM5 9.25a.75.75 0 0 1 .75-.75h.5a.75.75 0 0 1 0 1.5h-.5A.75.75 0 0 1 5 9.25ZM7 6.25h6.5a.75.75 0 0 1 0 1.5H7a.75.75 0 0 1 0-1.5Z",
}
GITHUB_MARK = "M8 0C3.58 0 0 3.58 0 8c0 3.54 2.29 6.53 5.47 7.59.4.07.55-.17.55-.38 0-.19-.01-.82-.01-1.49-2.01.37-2.53-.49-2.69-.94-.09-.23-.48-.94-.82-1.13-.28-.15-.68-.52-.01-.53.63-.01 1.08.58 1.23.82.72 1.21 1.87.87 2.33.66.07-.52.28-.87.51-1.07-1.78-.2-3.64-.89-3.64-3.95 0-.87.31-1.59.82-2.15-.08-.2-.36-1.02.08-2.12 0 0 .67-.21 2.2.82.64-.18 1.32-.27 2-.27.68 0 1.36.09 2 .27 1.53-1.04 2.2-.82 2.2-.82.44 1.1.16 1.92.08 2.12.51.56.82 1.27.82 2.15 0 3.07-1.87 3.75-3.65 3.95.29.25.54.73.54 1.48 0 1.07-.01 1.93-.01 2.2 0 .21.15.46.55.38A8.013 8.013 0 0016 8c0-4.42-3.58-8-8-8z"


def stats_svg(first_name, contributions, prs, repos, contributed):
    rows = [("contrib", "Total Contributions:", fmt_short(contributions)),
            ("pr", "Total PRs:", fmt_short(prs)),
            ("repo", "Repositories:", fmt_short(repos)),
            ("contributed", "Contributed to:", fmt_short(contributed))]
    body = [text(24, 34, f"{first_name}'s GitHub Stats", ACCENT, 18, 700)]
    for i, (icon, label, value) in enumerate(rows):
        y = 60 + i * 34
        body.append(f'<g transform="translate(24,{y - 13})"><path fill="{ACCENT}" d="{ICONS[icon]}"/></g>')
        body.append(text(50, y, label))
        body.append(text(300, y, value, "#e6edf3", 13, 700, "end"))
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="495" height="195" viewBox="0 0 495 195" role="img" aria-label="GitHub stats">
  <rect width="495" height="195" rx="8" fill="{BG}"/>
  {"".join(body)}
  <g transform="translate(410,108)">
    <circle r="54" fill="none" stroke="{ACCENT}" stroke-width="4" opacity="0.3"/>
    <circle r="48" fill="none" stroke="{ACCENT}" stroke-width="3.5"/>
    <g transform="translate(-22,-24) scale(2.75)" fill="#e6edf3"><path d="{GITHUB_MARK}"/></g>
  </g>
</svg>
'''


def langs_svg(langs):
    parts = [text(20, 34, "Most Used Languages", ACCENT, 18, 700)]
    bar_w, x = 280.0, 20.0
    for i, (_, color, pct) in enumerate(langs):
        w = bar_w * pct / 100 if i < len(langs) - 1 else max(20 + bar_w - x, 0)
        parts.append(f'<rect x="{x:.1f}" y="48" width="{max(w, 2):.1f}" height="8" fill="{color}"/>')
        x += w
    for i, (name, color, pct) in enumerate(langs):
        col, row = divmod(i, 4)
        cx, cy = 24 + col * 146, 78 + row * 26
        parts.append(f'<circle cx="{cx}" cy="{cy}" r="4" fill="{color}"/>')
        parts.append(text(cx + 12, cy + 4, f"{name} {pct:.1f}%", size=12))
    inner = "\n  ".join(parts)
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="320" height="195" viewBox="0 0 320 195" role="img" aria-label="Most used languages">
  <rect width="320" height="195" rx="8" fill="{BG}"/>
  <clipPath id="bar"><rect x="20" y="48" width="280" height="8" rx="4"/></clipPath>
  <g clip-path="url(#bar)">{"".join(p for p in parts if p.startswith("<rect"))}</g>
  {"".join(p for p in parts if not p.startswith("<rect"))}
</svg>
'''


def streak_svg(total, first_day, current, longest):
    def rng(s):
        n, a, b = s
        if not n:
            return "-"
        return fmt_date(a) if a == b else f"{fmt_date(a)} - {fmt_date(b)}"
    cur = current[0]
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="840" height="200" viewBox="0 0 840 200" role="img" aria-label="GitHub streak">
  <rect width="840" height="200" rx="8" fill="{BG}"/>
  <line x1="280" y1="24" x2="280" y2="176" stroke="#30363d"/>
  <line x1="560" y1="24" x2="560" y2="176" stroke="#30363d"/>
  {text(140, 88, f"{total:,}", "#e6edf3", 40, 800, "middle")}
  {text(140, 118, "Total Contributions", size=14, anchor="middle")}
  {text(140, 140, f"{fmt_date(first_day, True)} - Present", "#8b949e", 12, anchor="middle")}
  <g transform="translate(420,78)">
    <circle r="50" fill="none" stroke="#21262d" stroke-width="6"/>
    <circle r="50" fill="none" stroke="{ACCENT}" stroke-width="6" stroke-linecap="round" stroke-dasharray="314.2 314.2" transform="rotate(-90)"/>
    {text(0, 10, cur, "#e6edf3", 34, 800, "middle")}
  </g>
  {text(420, 150, "Current Streak", ACCENT, 14, 700, "middle")}
  {text(420, 170, rng(current), "#8b949e", 12, anchor="middle")}
  {text(700, 88, longest[0], "#e6edf3", 40, 800, "middle")}
  {text(700, 118, "Longest Streak", size=14, anchor="middle")}
  {text(700, 140, rng(longest), "#8b949e", 12, anchor="middle")}
</svg>
'''


def graph_svg(weeks):
    cells, months, last_month = [], [], None
    for wi, week in enumerate(weeks):
        x = 28 + wi * 14
        for day in week["contributionDays"]:
            d = dt.date.fromisoformat(day["date"])
            if d.day <= 7 and d.month != last_month and x < 760:
                months.append(text(x, 22, d.strftime("%b"), "#8b949e", 10))
                last_month = d.month
            y = 36 + day["weekday"] * 14
            fill = LEVEL_COLORS.get(day["contributionLevel"], ACCENT)
            cells.append(f'<rect x="{x}" y="{y}" width="11" height="11" rx="2" fill="{fill}">'
                         f'<title>{day["date"]}: {day["contributionCount"]}</title></rect>')
    width = 28 + len(weeks) * 14 + 16
    days = "".join(text(8, y, n, "#8b949e", 9) for n, y in (("Mon", 59), ("Wed", 87), ("Fri", 115)))
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="154" viewBox="0 0 {width} 154" role="img" aria-label="Contribution graph">
  <rect width="{width}" height="154" rx="12" fill="{BG}" stroke="#30363d" stroke-width="1"/>
  {"".join(months)}
  {days}
  {"".join(cells)}
</svg>
'''


# --------------------------------------------------------------------------- main

def build(user):
    cc = user["contributionsCollection"]
    cal = cc["contributionCalendar"]
    days = [(dt.date.fromisoformat(d["date"]), d["contributionCount"])
            for w in cal["weeks"] for d in w["contributionDays"]]
    days.sort()
    current, longest = compute_streaks(days)
    first_name = (user.get("name") or USER).split()[0]
    return {
        "stats.svg": stats_svg(first_name, cal["totalContributions"], user["pullRequests"]["totalCount"],
                               user["repositories"]["totalCount"], user["repositoriesContributedTo"]["totalCount"]),
        "langs.svg": langs_svg(compute_languages(cc["commitContributionsByRepository"])),
        "streak.svg": streak_svg(cal["totalContributions"], days[0][0], current, longest),
        "graph.svg": graph_svg(cal["weeks"]),
    }


def main():
    user = gql(QUERY, {"login": USER})["user"]
    os.makedirs(OUT, exist_ok=True)
    for name, svg in build(user).items():
        with open(os.path.join(OUT, name), "w", encoding="utf-8") as f:
            f.write(svg)
        print("wrote", name)


if __name__ == "__main__":
    main()
