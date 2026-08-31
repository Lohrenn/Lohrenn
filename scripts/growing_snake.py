"""
Generates a GitHub-contribution "growing snake" animation.

Unlike the standard eating-snake tools, the snake here genuinely gets longer
every time it passes over a day with real contributions, and stays the same
length when it passes over an empty day — exactly like the classic Snake game.

Requires: requests, pillow
Env vars: GH_TOKEN (a token with read access), GH_USERNAME
"""

import os
import requests
from collections import deque
from PIL import Image, ImageDraw, ImageFont

GH_TOKEN = os.environ["GH_TOKEN"]
GH_USERNAME = os.environ["GH_USERNAME"]

CELL = 14          # size of each contribution square, in px
GAP = 3             # gap between squares
MARGIN_X = 20
MARGIN_Y = 20
COUNTER_HEIGHT = 30
BG_COLOR = (13, 17, 23)        # GitHub dark background (#0D1117)
EMPTY_COLOR = (22, 27, 34)     # color for a cell after the snake eats it
HEAD_COLOR = (0, 217, 255)     # #00D9FF — brand cyan
TAIL_COLOR = (247, 37, 133)    # #F72585 — brand pink
FRAME_DURATION_MS = 55
END_HOLD_FRAMES = 20           # extra frames pausing on the final, longest state


def fetch_contribution_calendar():
    query = """
    query($login: String!) {
      user(login: $login) {
        contributionsCollection {
          contributionCalendar {
            weeks {
              contributionDays {
                date
                contributionCount
                color
              }
            }
          }
        }
      }
    }
    """
    resp = requests.post(
        "https://api.github.com/graphql",
        json={"query": query, "variables": {"login": GH_USERNAME}},
        headers={
            "Authorization": f"bearer {GH_TOKEN}",
            "Accept": "application/vnd.github+json",
        },
        timeout=30,
    )
    resp.raise_for_status()
    data = resp.json()
    return data["data"]["user"]["contributionsCollection"]["contributionCalendar"]["weeks"]


def hex_to_rgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def lerp_color(c1, c2, t):
    return tuple(int(c1[i] + (c2[i] - c1[i]) * t) for i in range(3))


def build_path(weeks):
    """Boustrophedon path: down column 0, up column 1, down column 2, etc."""
    path = []
    for w_idx, week in enumerate(weeks):
        days = week["contributionDays"]
        indices = range(len(days)) if w_idx % 2 == 0 else reversed(range(len(days)))
        for d_idx in indices:
            path.append((w_idx, d_idx))
    return path


def main():
    weeks = fetch_contribution_calendar()
    grid_colors = {}
    grid_counts = {}
    for w_idx, week in enumerate(weeks):
        for d_idx, day in enumerate(week["contributionDays"]):
            grid_colors[(w_idx, d_idx)] = hex_to_rgb(day["color"])
            grid_counts[(w_idx, d_idx)] = day["contributionCount"]

    path = build_path(weeks)
    n_weeks = len(weeks)
    n_days = 7

    img_w = MARGIN_X * 2 + n_weeks * (CELL + GAP)
    img_h = MARGIN_Y * 2 + n_days * (CELL + GAP) + COUNTER_HEIGHT

    try:
        font = ImageFont.truetype("DejaVuSans-Bold.ttf", 16)
    except Exception:
        font = ImageFont.load_default()

    body = deque()
    eaten = set()
    frames = []

    for step, (w_idx, d_idx) in enumerate(path):
        count = grid_counts.get((w_idx, d_idx), 0)
        body.append((w_idx, d_idx))
        if count == 0 and len(body) > 1:
            body.popleft()
        eaten.add((w_idx, d_idx))

        frame = Image.new("RGB", (img_w, img_h), BG_COLOR)
        draw = ImageDraw.Draw(frame)

        # draw the grid
        for w in range(n_weeks):
            for d in range(n_days):
                if (w, d) not in grid_colors:
                    continue
                x0 = MARGIN_X + w * (CELL + GAP)
                y0 = MARGIN_Y + d * (CELL + GAP)
                color = EMPTY_COLOR if (w, d) in eaten else grid_colors[(w, d)]
                draw.rounded_rectangle(
                    [x0, y0, x0 + CELL, y0 + CELL], radius=3, fill=color
                )

        # draw the snake body, gradient tail -> head
        body_list = list(body)
        n = len(body_list)
        for i, (w, d) in enumerate(body_list):
            t = i / max(n - 1, 1)
            color = lerp_color(TAIL_COLOR, HEAD_COLOR, t)
            x0 = MARGIN_X + w * (CELL + GAP)
            y0 = MARGIN_Y + d * (CELL + GAP)
            draw.rounded_rectangle(
                [x0, y0, x0 + CELL, y0 + CELL], radius=3, fill=color
            )

        # live length counter
        draw.text(
            (MARGIN_X, img_h - COUNTER_HEIGHT + 4),
            f"Snake length: {n}",
            fill=(201, 209, 217),
            font=font,
        )

        frames.append(frame)

    # hold on the final, longest frame before the gif loops
    frames.extend([frames[-1]] * END_HOLD_FRAMES)

    os.makedirs("assets", exist_ok=True)
    frames[0].save(
        "assets/growing-snake.gif",
        save_all=True,
        append_images=frames[1:],
        duration=FRAME_DURATION_MS,
        loop=0,
        optimize=True,
    )
    print(f"Generated assets/growing-snake.gif with {len(frames)} frames.")


if __name__ == "__main__":
    main()
