#!/usr/bin/env python3
"""Scrape today's home heating-oil price from justoil.com and update history.json.

Pure standard library (urllib, re, json, zoneinfo) so GitHub Actions needs no
`pip install`. Run twice a day from the workflow; the result feeds a TRMNL
private plugin via Polling of history.json.

Usage:
    python3 scrape.py --scheduled   # only records during the 4am / 10pm ET slots
    python3 scrape.py --force       # record right now into the nearest slot
"""

import argparse
import json
import re
import sys
import urllib.request
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

URL = "https://justoil.com/"
HISTORY = Path(__file__).resolve().parent / "history.json"
TZ = ZoneInfo("America/New_York")  # "Eastern" — handles EST/EDT automatically
MAX_POINTS = 120  # ~2 months at two points/day
USER_AGENT = "Mozilla/5.0 (OilTracker; +https://github.com)"

# Chart geometry (precomputed here so the Liquid template stays trivial).
CHART_W, CHART_H = 760, 230
PAD_L, PAD_R, PAD_T, PAD_B = 8, 8, 14, 14


def fetch_price() -> float:
    req = urllib.request.Request(URL, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=30) as resp:
        html = resp.read().decode("utf-8", "replace")
    m = re.search(r"\$\s*([0-9]+(?:\.[0-9]{1,2})?)\s*Per\s*Gallon", html, re.I)
    if not m:
        raise SystemExit("Could not find '$X.XX Per Gallon' on justoil.com — markup may have changed.")
    return round(float(m.group(1)), 2)


def slot_for(now: datetime):
    """Map the current Eastern hour to a recording slot, or None if not a slot."""
    h = now.hour
    if 3 <= h <= 6:
        return "AM"  # 4am check (allow a little drift for delayed Actions runs)
    if h >= 21 or h <= 0:
        return "PM"  # 10pm check
    return None


def load_history() -> dict:
    if HISTORY.exists():
        return json.loads(HISTORY.read_text())
    return {"unit": "gallon", "currency": "USD", "source": URL, "history": []}


def build_chart(points: list) -> dict:
    """Precompute an SVG polyline (and dot for the latest point) from price history."""
    prices = [p["p"] for p in points]
    n = len(prices)
    inner_w = CHART_W - PAD_L - PAD_R
    inner_h = CHART_H - PAD_T - PAD_B
    lo, hi = min(prices), max(prices)
    span = hi - lo

    def x_of(i):
        return PAD_L + (inner_w / 2 if n == 1 else inner_w * i / (n - 1))

    def y_of(p):
        if span == 0:
            return PAD_T + inner_h / 2
        return PAD_T + (1 - (p - lo) / span) * inner_h

    coords = [(round(x_of(i), 1), round(y_of(p), 1)) for i, p in enumerate(prices)]
    line = " ".join(f"{x},{y}" for x, y in coords)
    # Closed area under the line (for an optional light fill on the e-ink chart).
    area = f"{coords[0][0]},{PAD_T + inner_h} {line} {coords[-1][0]},{PAD_T + inner_h}"
    last_x, last_y = coords[-1]
    return {
        "w": CHART_W,
        "h": CHART_H,
        "points": line,
        "area_points": area,
        "last_x": last_x,
        "last_y": last_y,
        "min": round(lo, 2),
        "max": round(hi, 2),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--scheduled", action="store_true", help="only record during the 4am/10pm ET slots")
    ap.add_argument("--force", action="store_true", help="record now into the nearest slot")
    args = ap.parse_args()

    now = datetime.now(TZ)
    slot = slot_for(now)
    if args.scheduled and slot is None:
        print(f"{now:%Y-%m-%d %H:%M %Z}: not a 4am/10pm slot — skipping.")
        return
    if slot is None:  # --force outside a window: pick by time of day
        slot = "AM" if now.hour < 13 else "PM"

    price = fetch_price()
    data = load_history()
    hist = data["history"]

    date_str = now.strftime("%Y-%m-%d")
    key = f"{date_str}:{slot}"

    # Idempotent: one record per (date, slot). Re-runs just refresh that record.
    existing = next((p for p in hist if p["key"] == key), None)
    if existing:
        existing.update(p=price, ts=now.isoformat(timespec="minutes"))
        print(f"Updated existing record {key} -> ${price:.2f}")
    else:
        hist.append({"key": key, "d": date_str, "slot": slot,
                     "ts": now.isoformat(timespec="minutes"), "p": price})
        print(f"Recorded {key} -> ${price:.2f}")

    hist.sort(key=lambda p: p["ts"])
    del hist[:-MAX_POINTS]

    prev = hist[-2]["p"] if len(hist) >= 2 else price
    change = round(price - prev, 2)

    data.update(
        price=price,
        prev_price=prev,
        change=change,
        change_pct=round((change / prev * 100) if prev else 0, 1),
        direction="up" if change > 0 else "down" if change < 0 else "flat",
        change_str=("+" if change > 0 else "") + f"{change:.2f}",
        unit="gallon",
        currency="USD",
        source=URL,
        updated_at=now.strftime("%b %-d, %-I:%M %p %Z"),
        updated_iso=now.isoformat(timespec="minutes"),
        low=min(p["p"] for p in hist),
        high=max(p["p"] for p in hist),
        count=len(hist),
        chart=build_chart(hist),
        history=hist,
    )

    HISTORY.write_text(json.dumps(data, indent=2) + "\n")
    print(f"Wrote {HISTORY} ({len(hist)} points).")


if __name__ == "__main__":
    main()
