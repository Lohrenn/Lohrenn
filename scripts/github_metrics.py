"""
Generates a self-built GitHub metrics panel: contribution stats and streaks,
a top-languages breakdown by real code volume, and a tiered achievement
system based on real thresholds — replacing three separate third-party
widgets (readme-stats, top-langs, trophy) that depend on someone else's
free server staying online.

Requires: requests, matplotlib
Env vars: GH_TOKEN (a token with read access), GH_USERNAME
"""

import os
from datetime import datetime, timedelta, timezone

import requests
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches

GH_TOKEN = os.environ["GH_TOKEN"]
GH_USERNAME = os.environ["GH_USERNAME"]

BG = "#1C1B1A"
PANEL_BG = "#211F1E"
GRID = "#3A3835"
TEXT = "#E8E6E1"
SUBTEXT = "#9C9892"
NAVY = "#6E92A8"
RUST = "#C1666B"
GOLD = "#D9A566"
SAGE = "#7FA084"
BRONZE = "#B08D57"
SILVER = "#B8B8B8"

plt.rcParams["font.family"] = "DejaVu Serif"


def gql(query, variables):
    resp = requests.post(
        "https://api.github.com/graphql",
        json={"query": query, "variables": variables},
        headers={
            "Authorization": f"bearer {GH_TOKEN}",
            "Accept": "application/vnd.github+json",
        },
        timeout=30,
    )
    resp.raise_for_status()
    payload = resp.json()
    if "errors" in payload:
        raise RuntimeError(payload["errors"])
    return payload["data"]


def fetch_all():
    now = datetime.now(timezone.utc)
    start = now - timedelta(days=365)

    query = """
    query($login: String!, $from: DateTime!, $to: DateTime!) {
      user(login: $login) {
        contributionsCollection(from: $from, to: $to) {
          totalCommitContributions
          totalIssueContributions
          totalPullRequestContributions
          contributionCalendar {
            weeks { contributionDays { date contributionCount } }
          }
        }
        repositories(first: 100, ownerAffiliations: OWNER, isFork: false) {
          totalCount
          nodes {
            stargazerCount
            languages(first: 10, orderBy: {field: SIZE, direction: DESC}) {
              edges { size node { name color } }
            }
          }
        }
      }
    }
    """
    variables = {
        "login": GH_USERNAME,
        "from": start.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "to": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    data = gql(query, variables)["user"]
    return data


def compute_streaks(counts):
    longest = current = 0
    run = 0
    for c in counts:
        if c > 0:
            run += 1
            longest = max(longest, run)
        else:
            run = 0
    # current streak: count backwards from the end, allow today to be 0
    i = len(counts) - 1
    if counts[i] == 0:
        i -= 1
    while i >= 0 and counts[i] > 0:
        current += 1
        i -= 1
    return current, longest


def tier_for(value, bronze, silver, gold):
    if value >= gold:
        return "Gold", GOLD
    if value >= silver:
        return "Silver", SILVER
    if value >= bronze:
        return "Bronze", BRONZE
    return None, None


def draw_ribbon(ax, cx, cy, width, height, color, label, sublabel):
    rect = mpatches.FancyBboxPatch(
        (cx - width / 2, cy - height / 2), width, height,
        boxstyle="round,pad=0.02,rounding_size=0.04",
        linewidth=0, facecolor=color,
    )
    ax.add_patch(rect)
    ax.text(cx, cy + height * 0.12, label, ha="center", va="center",
             fontsize=10.5, fontweight="bold", color=BG)
    ax.text(cx, cy - height * 0.28, sublabel, ha="center", va="center",
             fontsize=8, color=BG)


def main():
    data = fetch_all()
    cc = data["contributionsCollection"]

    dates, counts = [], []
    for week in cc["contributionCalendar"]["weeks"]:
        for day in week["contributionDays"]:
            dates.append(day["date"])
            counts.append(day["contributionCount"])

    total_contributions = sum(counts)
    current_streak, longest_streak = compute_streaks(counts)

    repos = data["repositories"]["nodes"]
    total_repos = data["repositories"]["totalCount"]
    total_stars = sum(r["stargazerCount"] for r in repos)

    lang_totals = {}
    lang_colors = {}
    for r in repos:
        for edge in r["languages"]["edges"]:
            name = edge["node"]["name"]
            lang_totals[name] = lang_totals.get(name, 0) + edge["size"]
            lang_colors[name] = edge["node"]["color"] or NAVY

    top_langs = sorted(lang_totals.items(), key=lambda kv: kv[1], reverse=True)[:6]
    lang_total_size = sum(v for _, v in top_langs) or 1

    total_prs = cc["totalPullRequestContributions"]
    total_commits_year = cc["totalCommitContributions"]

    # --- Figure layout ---
    fig = plt.figure(figsize=(18, 7.2), dpi=150)
    fig.patch.set_facecolor(BG)

    fig.text(0.045, 0.955, "GitHub Metrics", fontsize=22, fontweight="bold", color=TEXT)
    fig.text(0.045, 0.915, "Computed directly from the GitHub API — no third-party widget dependency.",
              fontsize=11.5, color=SUBTEXT, style="italic")

    # Row 1: three stat callouts
    stat_y = 0.72
    stats = [
        (str(total_contributions), "Total Contributions", "Past 12 months"),
        (str(current_streak), "Current Streak", "days"),
        (str(longest_streak), "Longest Streak", "days"),
    ]
    for i, (big, label, sub) in enumerate(stats):
        x = 0.19 + i * 0.32
        fig.text(x, stat_y, big, fontsize=30, fontweight="bold", color=NAVY, ha="center")
        fig.text(x, stat_y - 0.055, label, fontsize=11, color=TEXT, ha="center")
        fig.text(x, stat_y - 0.09, sub, fontsize=9, color=SUBTEXT, ha="center", style="italic")

    fig.add_artist(plt.Line2D([0.36, 0.36], [0.6, 0.8], color=GRID, linewidth=1, transform=fig.transFigure))
    fig.add_artist(plt.Line2D([0.62, 0.62], [0.6, 0.8], color=GRID, linewidth=1, transform=fig.transFigure))
    fig.add_artist(plt.Line2D([0.045, 0.955], [0.585, 0.585], color=GRID, linewidth=1, transform=fig.transFigure))

    # Row 2 left: top languages horizontal bar
    ax_lang = fig.add_axes([0.045, 0.10, 0.42, 0.37])
    ax_lang.set_facecolor(PANEL_BG)
    names = [n for n, _ in reversed(top_langs)]
    sizes = [v / lang_total_size * 100 for _, v in reversed(top_langs)]
    colors = [lang_colors.get(n, NAVY) for n in names]
    ax_lang.barh(names, sizes, color=colors, height=0.6)
    for i, (name, pct) in enumerate(zip(names, sizes)):
        ax_lang.text(pct + 1, i, f"{pct:.1f}%", va="center", fontsize=8.5, color=TEXT)
    ax_lang.set_xlim(0, max(sizes) * 1.25 if sizes else 1)
    for spine in ax_lang.spines.values():
        spine.set_visible(False)
    ax_lang.tick_params(colors=TEXT, labelsize=9, length=0)
    ax_lang.set_xticks([])
    ax_lang.set_title("Top Languages by Code Volume", fontsize=12, color=TEXT, loc="left", pad=10)

    # Row 2 right: achievements
    ax_ach = fig.add_axes([0.52, 0.08, 0.44, 0.40])
    ax_ach.set_xlim(0, 1)
    ax_ach.set_ylim(0, 1)
    ax_ach.axis("off")
    ax_ach.set_title("Achievements", fontsize=12, color=TEXT, loc="left", pad=10, x=-0.03)

    achievements = [
        ("Commit Streak", total_commits_year, 10, 100, 500, "commits/yr"),
        ("Star Collector", total_stars, 1, 10, 50, "stars"),
        ("PR Contributor", total_prs, 1, 10, 25, "PRs/yr"),
        ("Repo Builder", total_repos, 1, 5, 15, "repos"),
    ]
    positions = [(0.22, 0.65), (0.72, 0.65), (0.22, 0.2), (0.72, 0.2)]
    for (label, value, b, s, g, unit), (cx, cy) in zip(achievements, positions):
        tier, color = tier_for(value, b, s, g)
        if tier is None:
            tier, color = "Locked", GRID
        draw_ribbon(ax_ach, cx, cy, 0.42, 0.3, color, f"{label}", f"{tier} · {value} {unit}")

    fig.text(0.045, 0.025, "Source: GitHub GraphQL API  ·  Regenerated daily",
              fontsize=8.5, color=SUBTEXT, style="italic")

    os.makedirs("assets", exist_ok=True)
    fig.savefig("assets/github-metrics.png", facecolor=BG)
    print("Generated assets/github-metrics.png")


if __name__ == "__main__":
    main()
