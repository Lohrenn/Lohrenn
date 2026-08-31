"""
Generates a full-year GitHub contribution activity panel in an editorial,
data-journalism style (muted tones, serif type, annotated peaks, a real
headline and source line) rather than a glossy neon dashboard look.

Requires: requests, matplotlib
Env vars: GH_TOKEN (a token with read access), GH_USERNAME
"""

import os
from datetime import datetime, timedelta, timezone

import requests
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.dates as mdates

GH_TOKEN = os.environ["GH_TOKEN"]
GH_USERNAME = os.environ["GH_USERNAME"]

# --- Editorial palette: muted, print-like, no neon/glow ---
BG = "#1C1B1A"          # warm charcoal, not pure black
PANEL_BG = "#211F1E"
GRID = "#3A3835"
TEXT = "#E8E6E1"        # warm off-white
SUBTEXT = "#9C9892"
NAVY = "#6E92A8"
RUST = "#C1666B"
GOLD = "#D9A566"
SAGE = "#7FA084"

plt.rcParams["font.family"] = "DejaVu Serif"


def fetch_year_of_contributions():
    now = datetime.now(timezone.utc)
    start = now - timedelta(days=365)

    query = """
    query($login: String!, $from: DateTime!, $to: DateTime!) {
      user(login: $login) {
        contributionsCollection(from: $from, to: $to) {
          totalCommitContributions
          totalIssueContributions
          totalPullRequestContributions
          totalPullRequestReviewContributions
          contributionCalendar {
            weeks {
              contributionDays {
                date
                contributionCount
              }
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
    return payload["data"]["user"]["contributionsCollection"]


def rolling_average(values, window=7):
    out = []
    for i in range(len(values)):
        lo = max(0, i - window + 1)
        chunk = values[lo:i + 1]
        out.append(sum(chunk) / len(chunk))
    return out


def style_axes(ax, y_grid_only=True):
    ax.set_facecolor(PANEL_BG)
    for spine in ax.spines.values():
        spine.set_visible(False)
    ax.tick_params(colors=SUBTEXT, labelsize=8.5, length=0)
    if y_grid_only:
        ax.grid(True, axis="y", color=GRID, linewidth=0.7)
        ax.grid(False, axis="x")
    else:
        ax.grid(True, color=GRID, linewidth=0.7)
    ax.set_axisbelow(True)


def main():
    data = fetch_year_of_contributions()

    dates, counts = [], []
    for week in data["contributionCalendar"]["weeks"]:
        for day in week["contributionDays"]:
            dates.append(datetime.strptime(day["date"], "%Y-%m-%d"))
            counts.append(day["contributionCount"])

    total = sum(counts)
    peak_idx = max(range(len(counts)), key=lambda i: counts[i])
    peak_date, peak_count = dates[peak_idx], counts[peak_idx]
    avg = total / len(counts) if counts else 0

    fig = plt.figure(figsize=(18, 6.5), dpi=150)
    fig.patch.set_facecolor(BG)

    # --- Headline + dek, like a real published chart ---
    fig.text(0.045, 0.94, "A Year of Building", fontsize=22, fontweight="bold", color=TEXT)
    fig.text(
        0.045, 0.885,
        f"{total} contributions over the past 12 months, averaging {avg:.1f} per day.",
        fontsize=12, color=SUBTEXT, style="italic",
    )

    gs = fig.add_gridspec(1, 3, left=0.045, right=0.97, top=0.78, bottom=0.16, wspace=0.22)
    ax1 = fig.add_subplot(gs[0, 0])
    ax2 = fig.add_subplot(gs[0, 1])
    ax3 = fig.add_subplot(gs[0, 2])

    # --- Line chart: smoothed trend, annotated peak ---
    smoothed = rolling_average(counts, window=7)
    ax1.plot(dates, smoothed, color=NAVY, linewidth=1.8)
    ax1.axhline(avg, color=SUBTEXT, linewidth=0.8, linestyle=(0, (4, 3)))
    ax1.annotate(
        f"Busiest day\n{peak_date.strftime('%b %-d')} · {peak_count} contributions",
        xy=(peak_date, smoothed[peak_idx]),
        xytext=(0.5, 0.92), textcoords="axes fraction",
        fontsize=8.5, color=RUST, ha="center",
        arrowprops=dict(arrowstyle="-", color=RUST, linewidth=0.8,
                         connectionstyle="arc3,rad=-0.2"),
    )
    ax1.xaxis.set_major_locator(mdates.MonthLocator(interval=2))
    ax1.xaxis.set_major_formatter(mdates.DateFormatter("%b"))
    ax1.set_title("7-Day Rolling Trend", fontsize=12, color=TEXT, loc="left", pad=12)
    style_axes(ax1)

    # --- Bar chart: daily volume, peak highlighted ---
    bar_colors = [RUST if i == peak_idx else GOLD for i in range(len(counts))]
    ax2.bar(dates, counts, color=bar_colors, width=1.0, linewidth=0)
    ax2.xaxis.set_major_locator(mdates.MonthLocator(interval=2))
    ax2.xaxis.set_major_formatter(mdates.DateFormatter("%b"))
    ax2.set_title("Daily Contribution Volume", fontsize=12, color=TEXT, loc="left", pad=12)
    style_axes(ax2)

    # --- Donut chart: contribution type breakdown, editorial labeling ---
    labels_values = [
        ("Commits", data["totalCommitContributions"], NAVY),
        ("Issues", data["totalIssueContributions"], SAGE),
        ("Pull Requests", data["totalPullRequestContributions"], GOLD),
        ("PR Reviews", data["totalPullRequestReviewContributions"], RUST),
    ]
    labels_values = [(l, v, c) for l, v, c in labels_values if v > 0]
    ax3.set_facecolor(PANEL_BG)
    if labels_values:
        labels = [l for l, v, c in labels_values]
        values = [v for l, v, c in labels_values]
        colors = [c for l, v, c in labels_values]
        wedges, texts, autotexts = ax3.pie(
            values,
            labels=labels,
            colors=colors,
            autopct="%1.0f%%",
            pctdistance=0.78,
            startangle=90,
            wedgeprops=dict(width=0.42, edgecolor=BG, linewidth=2),
            textprops={"color": TEXT, "fontsize": 9},
        )
        for at in autotexts:
            at.set_color(BG)
            at.set_fontsize(8.5)
            at.set_fontweight("bold")
    else:
        ax3.text(0.5, 0.5, "No contributions yet", color=SUBTEXT, ha="center", va="center")
    ax3.set_title("Contribution Type Breakdown", fontsize=12, color=TEXT, loc="left", pad=12)

    # --- Source line, like a real chart footer ---
    fig.text(0.045, 0.045, "Source: GitHub GraphQL API  ·  Regenerated daily",
              fontsize=8.5, color=SUBTEXT, style="italic")

    os.makedirs("assets", exist_ok=True)
    fig.savefig("assets/activity-charts.png", facecolor=BG)
    print("Generated assets/activity-charts.png")


if __name__ == "__main__":
    main()
