# Oil Price Tracker — TRMNL plugin

A TRMNL private plugin that checks **[justoil.com](https://justoil.com/)** (Just Oil,
NY home heating oil) twice a day — **4am and 10pm Eastern** — and shows the current
price per gallon plus a chart of how it has changed over time.

No server required. [GitHub Actions](.github/workflows/scrape.yml) does the scraping
on a schedule and commits the price history to this repo; TRMNL polls
[`history.json`](history.json) and renders it with the [Liquid templates](trmnl/).

```
GitHub Actions (cron 4am/10pm ET) → scrape.py → history.json (committed) → raw URL → TRMNL polls → e-ink
```

## How it works

| File | Role |
|------|------|
| `scrape.py` | Stdlib-only scraper. Pulls `$X.XX Per Gallon`, appends one point per slot, precomputes the SVG chart, writes `history.json`. |
| `history.json` | Current price + full history. **This is the URL TRMNL polls.** |
| `.github/workflows/scrape.yml` | Runs the scraper at 4am & 10pm ET and commits the result. |
| `trmnl/full.liquid` / `trmnl/half_horizontal.liquid` | Display templates (big price + SVG line chart). |

Daylight saving is handled in `scrape.py`: the workflow fires at the UTC times that
match 4am/10pm ET in both EST and EDT, and the script only records during the actual
Eastern 4am/10pm window — so you get exactly two readings a day year-round.

## Setup

### 1. Put this on GitHub

```bash
cd OilTracker
git init && git add . && git commit -m "Oil price tracker"
gh repo create oil-tracker --public --source=. --push   # or create the repo in the UI
```

The repo must be **public** so TRMNL can fetch `history.json` without auth.

### 2. Let the workflow commit

In the repo: **Settings → Actions → General → Workflow permissions → Read and write
permissions → Save.** (The workflow already requests `contents: write`; this toggles
it on for the repo.) Then open the **Actions** tab → *Scrape oil price* → **Run
workflow** once to confirm it works (tick **force** to record immediately).

> Note: GitHub disables scheduled workflows after 60 days with no repo activity.
> Because each run commits `history.json`, the repo stays active on its own.

### 3. Create the TRMNL private plugin

1. TRMNL dashboard → **Plugins → Private Plugin → Add New**.
2. **Strategy: Polling.**
3. **Polling URL** — the raw URL of `history.json`:
   ```
   https://raw.githubusercontent.com/<your-user>/oil-tracker/main/history.json
   ```
4. Set the **refresh rate** to a few hours (the data only changes twice a day).
5. **Markup** — paste `trmnl/full.liquid` into the *Full* view and
   `trmnl/half_horizontal.liquid` into the *Half Horizontal* view (optional).
6. Save, then **Add to a playlist / mashup** on your device.

Because it's a single polling URL, the JSON fields are available at the template
root: `{{ price }}`, `{{ change_str }}`, `{{ chart.points }}`, `{{ updated_at }}`, etc.

## Local testing

```bash
python3 scrape.py --force     # scrape now, write history.json
cat history.json
```

`--force` records into the nearest slot regardless of time. The scheduled workflow
uses `--scheduled`, which only records during the 4am/10pm ET windows.

## Customizing

- **Different times:** edit the `cron:` lines in `.github/workflows/scrape.yml` and
  the `slot_for()` windows in `scrape.py`.
- **History length:** change `MAX_POINTS` in `scrape.py`.
- **Chart size/style:** `CHART_W/CHART_H/PAD_*` in `scrape.py` and the `<svg>` blocks
  in the Liquid templates.
- **If justoil.com changes its markup** and the scrape fails, update the regex in
  `fetch_price()` (currently matches `$X.XX Per Gallon`).
