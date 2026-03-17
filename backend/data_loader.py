"""
Load March Madness game outcomes and team stats; build (X, y) for training.
Game JSONs: backend/gamedata/{year}.json (2002..2025).
Team CSVs: backend/teamdata/ (KenPom Pre-Tournament, Offense, Defense).
"""
import json
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd

GAMEDATA_DIR = Path(__file__).parent / "gamedata"
TEAMDATA_DIR = Path(__file__).parent / "teamdata"

# Map game JSON team names to CSV TeamName when they differ
TEAM_NAME_ALIASES = {
    "UConn": "Connecticut",
    "Ole Miss": "Mississippi",
    "UNC": "North Carolina",
    "UNC Wilmington": "UNC Wilmington",  # same in CSV
    "North Carolina State": "NC State",
    "NC State": "NC State",
    "St. John's": "St. John's",
    "Saint Mary's": "Saint Mary's",
    "St. Mary's": "Saint Mary's",
    "Texas A&M": "Texas A&M",
    "Ohio St.": "Ohio St.",
    "Michigan St.": "Michigan St.",
    "Michigan State": "Michigan St.",
    "Mississippi St.": "Mississippi St.",
    "Mississippi State": "Mississippi St.",
    "Kent St.": "Kent St.",
    "BYU": "BYU",
    "VCU": "VCU",
    "UAB": "UAB",
    "LIU": "LIU Brooklyn",
    "USC": "USC",
    "Southern California": "USC",
    "UNC-Wilmington": "UNC Wilmington",
    "Central Connecticut State": "Central Connecticut",
    "Illinois-Chicago": "UIC",
    "Hawai'i": "Hawaii",
    "Loyola Chicago": "Loyola Chicago",
    "Loyola (IL)": "Loyola Chicago",
    "Ohio St.": "Ohio State",
    "Michigan St.": "Michigan State",
    "Iowa St.": "Iowa State",
    "North Dakota St.": "North Dakota State",
    "Kennesaw St.": "Kennesaw State",
    "Wright St.": "Wright State",
    "Utah St.": "Utah State",
    "Queens (N.C.)": "Queens",
}


def normalize_team_name(name: str) -> str:
    """Return CSV-style name for lookups."""
    s = name.strip()
    return TEAM_NAME_ALIASES.get(s, s)


def load_pre_tournament(season: Optional[int] = None) -> pd.DataFrame:
    if season == 2026:
        path = TEAMDATA_DIR / "INT _ KenPom _ Summary (Pre-Tournament)_2026.csv"
    else:
        path = TEAMDATA_DIR / "INT _ KenPom _ Summary (Pre-Tournament).csv"
    if not path.exists():
        raise FileNotFoundError(path)
    df = pd.read_csv(path)
    df["Season"] = df["Season"].astype(int)
    return df


def load_offense(season: Optional[int] = None) -> pd.DataFrame:
    if season == 2026:
        path = TEAMDATA_DIR / "INT _ KenPom _ Offense_2026.csv"
    else:
        path = TEAMDATA_DIR / "INT _ KenPom _ Offense.csv"
    if not path.exists():
        return pd.DataFrame()
    df = pd.read_csv(path)
    df["Season"] = df["Season"].astype(int)
    return df


def load_defense(season: Optional[int] = None) -> pd.DataFrame:
    if season == 2026:
        path = TEAMDATA_DIR / "INT _ KenPom _ Defense_2026.csv"
    else:
        path = TEAMDATA_DIR / "INT _ KenPom _ Defense.csv"
    if not path.exists():
        return pd.DataFrame()
    df = pd.read_csv(path)
    df["Season"] = df["Season"].astype(int)
    return df


def get_team_stats(
    season: int,
    team_name: str,
    pre_tournament: pd.DataFrame,
    offense: pd.DataFrame,
    defense: pd.DataFrame,
) -> Optional[dict]:
    """Look up stats for one team in one season. Returns dict with keys matching FEATURE_ORDER."""
    name = normalize_team_name(team_name)
    pt = pre_tournament[(pre_tournament["Season"] == season) & (pre_tournament["TeamName"] == name)]
    if pt.empty:
        # Try without alias (e.g. Connecticut already in CSV as Connecticut)
        pt = pre_tournament[(pre_tournament["Season"] == season) & (pre_tournament["TeamName"] == team_name.strip())]
    if pt.empty:
        return None
    row = pt.iloc[0]
    seed = row.get("Seed", 16)
    if pd.isna(seed) or seed == "":
        seed = 16
    seed = int(seed)

    out = {
        "seed": float(seed),
        "adj_em": float(row.get("AdjEM", 0)),
        "adj_o": float(row.get("AdjOE", 0)),
        "adj_d": float(row.get("AdjDE", 100)),
        "tempo": float(row.get("AdjTempo", 68)),
        "efg_pct": 0.5,
        "to_pct": 0.18,
        "orb_pct": 0.28,
        "ftr": 0.32,
        "opp_efg_pct": 0.48,
        "opp_to_pct": 0.19,
        "opp_orb_pct": 0.30,
        "opp_ftr": 0.30,
    }
    ox = offense[(offense["Season"] == season) & (offense["TeamName"] == name)]
    if ox.empty:
        ox = offense[(offense["Season"] == season) & (offense["TeamName"] == team_name.strip())]
    if not ox.empty:
        r = ox.iloc[0]
        efg = float(r.get("eFGPct", 50))
        out["efg_pct"] = efg / 100.0 if efg > 1 else efg
        out["to_pct"] = float(r.get("TOPct", 18)) / 100.0 if r.get("TOPct") is not None else 0.18
        out["orb_pct"] = float(r.get("ORPct", 28)) / 100.0 if r.get("ORPct") is not None else 0.28
        ftr = float(r.get("FTRate", 32))
        out["ftr"] = ftr / 100.0 if ftr > 1 else ftr

    dx = defense[(defense["Season"] == season) & (defense["TeamName"] == name)]
    if dx.empty:
        dx = defense[(defense["Season"] == season) & (defense["TeamName"] == team_name.strip())]
    if not dx.empty:
        r = dx.iloc[0]
        oefg = float(r.get("eFGPct", 48))
        out["opp_efg_pct"] = oefg / 100.0 if oefg > 1 else oefg
        out["opp_to_pct"] = float(r.get("TOPct", 19)) / 100.0 if r.get("TOPct") is not None else 0.19
        out["opp_orb_pct"] = float(r.get("ORPct", 30)) / 100.0 if r.get("ORPct") is not None else 0.30
        oft = float(r.get("FTRate", 30))
        out["opp_ftr"] = oft / 100.0 if oft > 1 else oft
    return out


def iter_games(years: list[int]):
    """Yield (year, round_of, team1_dict, team2_dict) for each game in region + finalfour."""
    for year in years:
        path = GAMEDATA_DIR / f"{year}.json"
        if not path.exists():
            continue
        with open(path) as f:
            data = json.load(f)
        regions = data.get("regions", [])
        for region in regions:
            for round_idx, round_games in enumerate(region):
                round_of = [64, 32, 16, 8][round_idx]
                for game in round_games:
                    if len(game) != 2:
                        continue
                    t1, t2 = game[0], game[1]
                    yield year, round_of, t1, t2
        ff = data.get("finalfour", [])
        for round_idx, round_games in enumerate(ff):
            round_of = 4 if round_idx == 0 else 2
            for game in round_games:
                if len(game) != 2:
                    continue
                t1, t2 = game[0], game[1]
                yield year, round_of, t1, t2


FEATURE_ORDER = [
    "seed", "adj_em", "adj_o", "adj_d",
    "efg_pct", "to_pct", "orb_pct", "ftr",
    "opp_efg_pct", "opp_to_pct", "opp_orb_pct", "opp_ftr",
    "tempo",
    "round_64", "round_32", "round_16", "round_8", "round_4", "round_2",
]


def team_to_vector(t: dict, round_of: int) -> np.ndarray:
    arr = []
    for key in FEATURE_ORDER:
        if key.startswith("round_"):
            r = int(key.split("_")[1])
            arr.append(1.0 if round_of == r else 0.0)
        else:
            arr.append(float(t.get(key, 0)))
    return np.array(arr, dtype=np.float64)


def build_xy(
    years: list[int],
    pre_tournament: pd.DataFrame,
    offense: pd.DataFrame,
    defense: pd.DataFrame,
) -> tuple[np.ndarray, np.ndarray]:
    """Build (X, y) from game outcomes. X = feature diff (team1 - team2), y = 1 if team1 wins."""
    X_list, y_list = [], []
    for year, round_of, t1, t2 in iter_games(years):
        s1 = get_team_stats(year, t1["team"], pre_tournament, offense, defense)
        s2 = get_team_stats(year, t2["team"], pre_tournament, offense, defense)
        if s1 is None or s2 is None:
            continue
        score1, score2 = int(t1.get("score", 0)), int(t2.get("score", 0))
        winner_first = 1 if score1 > score2 else 0
        v1 = team_to_vector(s1, round_of)
        v2 = team_to_vector(s2, round_of)
        diff = v1 - v2
        X_list.append(diff)
        y_list.append(winner_first)
    if not X_list:
        return np.array([]).reshape(0, len(FEATURE_ORDER)), np.array([])
    return np.vstack(X_list), np.array(y_list, dtype=np.int64)
