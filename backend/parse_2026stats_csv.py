"""
Parse a local Torvik-derived CSV (e.g. C:\\Users\\brend\\Downloads\\2026stats.csv)
and generate **new** KenPom-style CSVs for a given season, without touching your
existing files:

  - INT _ KenPom _ Summary (Pre-Tournament)_YYYY.csv
  - INT _ KenPom _ Offense_YYYY.csv
  - INT _ KenPom _ Defense_YYYY.csv

Rules:
- Row 1 is the header.
- Starting at row 2, keep only the EVEN data rows (2, 4, 6, ... in Excel;
  that is, keep every other row and skip the "rank" rows).
- Make sure we output all columns used by data_loader.get_team_stats:
  Summary: Season, TeamName, Seed, AdjEM, AdjOE, AdjDE, AdjTempo
  Offense: Season, TeamName, eFGPct, TOPct, ORPct, FTRate
  Defense: Season, TeamName, eFGPct, TOPct, ORPct, FTRate

Usage (from backend directory):

  python parse_2026stats_csv.py --input \"C:\\Users\\brend\\Downloads\\2026stats.csv\" --season 2026

You can adjust the COLUMN_MAP below if your header names differ.
"""

import argparse
import csv
import re
from pathlib import Path
from typing import Dict, List

TEAMDATA_DIR = Path(__file__).resolve().parent / "teamdata"

# Map our logical fields to column names in 2026stats.csv.
# Adjust these strings if your CSV headers are slightly different.
COLUMN_MAP: Dict[str, str] = {
    "TeamName": "Team",   # team name text
    "AdjOE": "AdjOE",     # adjusted offensive efficiency
    "AdjDE": "AdjDE",     # adjusted defensive efficiency
    "AdjTempo": "AdjT",   # adjusted tempo (use the tempo column you care about)
    "eFGPct": "Efg%",     # offensive effective FG%
    "EFGD": "EfgD%",      # defensive eFG%
    "TOR": "TOR",         # offensive turnover rate
    "TORD": "TORD",       # defensive turnover rate
    "ORB": "ORB",         # offensive offensive-rebound rate
    "DRB": "DRB",         # defensive rebounding rate
    "FTR": "FTR",         # offensive free-throw rate
    "FTRD": "FTRD",       # defensive free-throw rate
}


def _num(s: str) -> float:
    """Parse the first numeric token out of a cell."""
    if s is None:
        return 0.0
    text = str(s).strip()
    if not text:
        return 0.0
    # Some cells may have "12.3\n4" – take the first token.
    text = text.replace("\n", " ").split()[0]
    text = re.sub(r"[^\d.\-]", "", text)
    try:
        return float(text)
    except ValueError:
        return 0.0


def _pct(s: str) -> float:
    """Normalize a value that might be 0–1 or 0–100 into 0–100."""
    x = _num(s)
    if 0.0 <= x <= 1.0:
        return x * 100.0
    return x


def parse_csv(input_path: Path, season: int) -> List[dict]:
    """
    Read the Torvik-derived CSV and return a list of team rows with all fields we need.

    Row indexing:
      - Row 1 (index 0) is the header.
      - Starting at row_index = 1 (Excel row 2), we KEEP rows where (row_index % 2 == 1)
        and SKIP rows where (row_index % 2 == 0).
      That means we keep rows 2, 4, 6, ... (the stat rows) and skip rows 3, 5, 7, ...
    """
    rows: List[dict] = []
    with input_path.open(newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for idx, raw in enumerate(reader, start=1):  # idx=1 -> Excel row 2
            # Keep only even-numbered Excel rows: 2,4,6,... -> idx odd (1-based in this loop)
            if idx % 2 == 0:
                # This would be Excel row 3,5,7,... (rank rows) – skip
                continue

            def get(col_key: str) -> str:
                name = COLUMN_MAP[col_key]
                # Try exact match first, then case-insensitive fallback
                if name in raw:
                    return raw[name]
                for k in raw.keys():
                    if k.lower() == name.lower():
                        return raw[k]
                return ""

            team_name = get("TeamName").strip()
            if not team_name:
                continue

            adj_o = _num(get("AdjOE"))
            adj_d = _num(get("AdjDE"))
            adj_em = adj_o - adj_d
            adj_t = _num(get("AdjTempo"))

            efg = _pct(get("eFGPct"))
            efgd = _pct(get("EFGD"))
            tor = _pct(get("TOR"))
            tord = _pct(get("TORD"))
            orb = _pct(get("ORB"))
            drb = _pct(get("DRB"))
            ftr = _pct(get("FTR"))
            ftrd = _pct(get("FTRD"))

            rows.append(
                {
                    "Season": season,
                    "TeamName": team_name,
                    # Seed is not in this CSV; default 16 so the pipeline works.
                    # You can edit the Summary CSV later to set real seeds.
                    "Seed": 16,
                    "AdjEM": round(adj_em, 4),
                    "AdjOE": round(adj_o, 4),
                    "AdjDE": round(adj_d, 4),
                    "AdjTempo": round(adj_t, 4),
                    "eFGPct": round(efg, 4),
                    "TOPct": round(tor, 4),
                    "ORPct": round(orb, 4),
                    "FTRate": round(ftr, 4),
                    "opp_eFGPct": round(efgd, 4),
                    "opp_TOPct": round(tord, 4),
                    # Opp OR% ≈ 100 - our DRB%
                    "opp_ORPct": round(100.0 - drb, 4),
                    "opp_FTRate": round(ftrd, 4),
                }
            )
    return rows


def write_kenpom_csvs(rows: List[dict], season: int) -> None:
    TEAMDATA_DIR.mkdir(parents=True, exist_ok=True)

    suffix = f"_{season}"

    summary_path = TEAMDATA_DIR / f"INT _ KenPom _ Summary (Pre-Tournament){suffix}.csv"
    with summary_path.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["Season", "TeamName", "Seed", "AdjEM", "AdjOE", "AdjDE", "AdjTempo"])
        for r in rows:
            w.writerow(
                [
                    r["Season"],
                    r["TeamName"],
                    r["Seed"],
                    r["AdjEM"],
                    r["AdjOE"],
                    r["AdjDE"],
                    r["AdjTempo"],
                ]
            )

    offense_path = TEAMDATA_DIR / f"INT _ KenPom _ Offense{suffix}.csv"
    with offense_path.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["Season", "TeamName", "eFGPct", "TOPct", "ORPct", "FTRate"])
        for r in rows:
            w.writerow(
                [
                    r["Season"],
                    r["TeamName"],
                    r["eFGPct"],
                    r["TOPct"],
                    r["ORPct"],
                    r["FTRate"],
                ]
            )

    defense_path = TEAMDATA_DIR / f"INT _ KenPom _ Defense{suffix}.csv"
    with defense_path.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["Season", "TeamName", "eFGPct", "TOPct", "ORPct", "FTRate"])
        for r in rows:
            w.writerow(
                [
                    r["Season"],
                    r["TeamName"],
                    r["opp_eFGPct"],
                    r["opp_TOPct"],
                    r["opp_ORPct"],
                    r["opp_FTRate"],
                ]
            )


def main() -> int:
    parser = argparse.ArgumentParser(description="Parse 2026stats.csv into model-ready KenPom-style CSVs")
    parser.add_argument(
        "--input",
        type=str,
        required=True,
        help="Path to 2026stats.csv (e.g. C:\\Users\\brend\\Downloads\\2026stats.csv)",
    )
    parser.add_argument("--season", type=int, default=2026, help="Season year (default: 2026)")
    args = parser.parse_args()

    input_path = Path(args.input).expanduser()
    if not input_path.exists():
        raise SystemExit(f"Input CSV not found: {input_path}")

    season = args.season
    rows = parse_csv(input_path, season=season)
    if not rows:
        raise SystemExit("No team rows parsed; check COLUMN_MAP and CSV header names.")

    write_kenpom_csvs(rows, season=season)
    print(
        f"Wrote KenPom-style CSVs to {TEAMDATA_DIR} with suffix _{season}. "
        "Seed is 16 for all teams; edit the Summary CSV copy to set real seeds from the bracket."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

