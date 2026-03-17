# Where to Get Data for This Year’s Bracket

The app needs two things: **bracket structure** (who plays whom) and **team stats** (efficiency, tempo, four factors). Here’s where to get them and what format the app expects.

---

## 1. Bracket structure: `gamedata/{year}.json`

**What it is:** The 68 teams, seeds, regions, and Round of 64 matchups. The app uses this to build `data/bracket_2025.json` and know which teams need stats.

**Where to get it:**

- **NCAA.com** – When the bracket is announced (Selection Sunday), the official bracket is published. You can manually build `gamedata/2026.json` (or whatever year) by listing each region’s eight first-round games. Format: same structure as existing `gamedata/2025.json`: `{"year": 2026, "regions": [[[game1, game2, ...]], ...], "finalfour": [...]}`. Each game is `[{ "seed": 1, "team": "Duke" }, { "seed": 16, "team": "Play-in Winner" }]` (no scores for a prediction bracket).
- **Copy and edit a prior year** – Duplicate `gamedata/2025.json`, change `year`, then replace team names and seeds with this year’s field. Play-in games can be represented as a single slot (e.g. “16a” vs “16b” or the actual team names once you pick one).

---

## 2. Team stats: KenPom-style CSVs in `teamdata/`

The model uses **adjusted efficiency margin (AdjEM), adjusted offense (AdjOE), adjusted defense (AdjDE), tempo, and four factors** (eFG%, TO%, OR%, FTR on offense and defense). The loader expects three CSVs with specific column names.

### Required files (in `backend/teamdata/`)

| File | Purpose |
|------|--------|
| `INT _ KenPom _ Summary (Pre-Tournament).csv` | Seeds, AdjEM, AdjOE, AdjDE, AdjTempo |
| `INT _ KenPom _ Offense.csv` | Offensive four factors (eFG%, TO%, OR%, FTR) |
| `INT _ KenPom _ Defense.csv` | Opponent four factors (defensive side) |

### Required columns

**Summary (Pre-Tournament):**

- `Season` (e.g. 2026)
- `TeamName` (must match team names in your bracket JSON)
- `Seed` (1–16, only for tournament teams in that season’s field; others can be blank or 16)
- `AdjEM`, `AdjOE`, `AdjDE`, `AdjTempo`

**Offense:**

- `Season`, `TeamName`
- `eFGPct`, `TOPct`, `ORPct`, `FTRate` (as percentages, e.g. 52.5; the loader normalizes to 0–1 where needed)

**Defense:**

- `Season`, `TeamName`
- `eFGPct`, `TOPct`, `ORPct`, `FTRate` (opponent rates; same column names)

Team names must be consistent across all three CSVs and your bracket JSON (e.g. "North Carolina" vs "UNC"). The repo’s `data_loader.py` uses a `TEAM_NAME_ALIASES` map for common variants (UConn → Connecticut, etc.); you can extend that if your source uses different names.

---

## 3. Where to get the stats (this year’s numbers)

### KenPom (paid) – **exact format**

- **Site:** [kenpom.com](https://kenpom.com)
- **Subscription:** Paid; includes pre-tournament ratings and tables.
- **What to export:** Pre-tournament summary (for Seed, AdjEM, AdjOE, AdjDE, AdjTempo) and the offense/defense tables (for four factors). Export or copy into CSV with the column names above. KenPom’s export or “table to CSV” browser tools often use similar names (e.g. Adj EM, Adj OE, Adj DE, Adj T); rename columns to match if needed (e.g. `Adj EM` → `AdjEM`, `Adj OE` → `AdjOE`).

### Bart Torvik / T-Rank (free) – **scraper included**

- **Site:** [barttorvik.com](https://barttorvik.com)
- **Scraper:** From the `backend` directory run:
  ```bash
  pip install playwright && playwright install chromium
  python scrape_barttorvik.py --year 2026
  ```
  This loads the homepage “T-Rank and Tempo-Free Stats” table (for the year you pass), scrapes ADJOE, ADJDE, ADJ T., EFG%, TOR, ORB, FTR, EFGD%, TORD, DRB, FTRD, and writes the three KenPom-style CSVs into `teamdata/`. **Seed is set to 16 for all teams** (Torvik doesn’t list seeds); update the Summary CSV with real seeds from the NCAA bracket before building your bracket if you want seed-accurate predictions.

### Other sources

- **Sports Reference / College Basketball Reference:** Has pace, ORtg/DRtg, and some four-factor style stats. You’d need to map to AdjOE/AdjDE/AdjEM and the four-factor names the app expects.
- **NCAA.org stats:** More basic; less aligned with “adjusted” efficiency. Possible but would require more custom mapping.

---

## 4. After you have the data

1. Put the three CSVs in `backend/teamdata/` with the exact filenames above (or adjust `data_loader.py` to point at different names).
2. Put this year’s bracket in `backend/gamedata/{year}.json` (e.g. `2026.json`).
3. From `backend/` run:

   ```bash
   python build_2025_bracket.py
   ```

   If your bracket file is for a different year, either rename it to match what `build_2025_bracket.py` expects (currently `gamedata/2025.json`) or change that script’s `GAMEDATA_DIR` / year and output paths (e.g. `bracket_2026.json`, `teams_2026.json`) and ensure `main.py` and the model load the same files.

4. Restart the backend so it uses the new `data/bracket_*.json` and `data/teams_*.json`.

The app currently loads `bracket_2025.json` and `teams_2025.json` (see `main.py`). For a different year, put that year’s bracket in `gamedata/{year}.json`, edit `build_2025_bracket.py` to use that year and write `bracket_{year}.json` / `teams_{year}.json`, run it, then set `BRACKET_PATH` and `TEAMS_PATH` in `main.py` (and `model.py` if needed) to the new filenames.

Once the bracket JSON and KenPom-style CSVs are in place, the app can use this year’s bracket and stats for predictions.
