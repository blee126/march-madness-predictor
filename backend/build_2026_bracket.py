"""
Build bracket_2026.json and teams_2026.json from gamedata/2026.json and 2026 teamdata CSVs.
Uses INT _ KenPom _ Summary (Pre-Tournament)_2026.csv, Offense_2026.csv, Defense_2026.csv.
Run from backend: python build_2026_bracket.py
"""
import json
from pathlib import Path

from data_loader import (
    load_pre_tournament,
    load_offense,
    load_defense,
    get_team_stats,
)

DATA_DIR = Path(__file__).parent / "data"
GAMEDATA_DIR = Path(__file__).parent / "gamedata"
REGION_NAMES = ["East", "West", "South", "Midwest"]
SEASON = 2026


def team_to_id(region: str, seed: int, team: str) -> str:
    """Sanitize for id: replace spaces/special with underscore."""
    safe = team.replace(" ", "_").replace(".", "").replace("'", "").replace("(", "").replace(")", "")
    return f"{region}_{seed}_{safe}"


def main():
    with open(GAMEDATA_DIR / "2026.json") as f:
        data = json.load(f)
    regions_data = data["regions"]
    pt = load_pre_tournament(SEASON)
    ox = load_offense(SEASON)
    dx = load_defense(SEASON)

    bracket_regions = []
    all_teams = []

    for region_idx, region in enumerate(regions_data):
        round_64 = region[0]
        region_name = REGION_NAMES[region_idx]
        games = []
        for game in round_64:
            t1, t2 = game[0], game[1]
            team1_name, team2_name = t1["team"], t2["team"]
            seed1, seed2 = int(t1["seed"]), int(t2["seed"])
            id1 = team_to_id(region_name, seed1, team1_name)
            id2 = team_to_id(region_name, seed2, team2_name)
            games.append([
                {"id": id1, "team": team1_name, "seed": seed1},
                {"id": id2, "team": team2_name, "seed": seed2},
            ])
            for (name, seed) in [(team1_name, seed1), (team2_name, seed2)]:
                tid = team_to_id(region_name, seed, name)
                if any(t["id"] == tid for t in all_teams):
                    continue
                stats = get_team_stats(SEASON, name, pt, ox, dx)
                if stats:
                    s = dict(stats)
                    s["seed"] = int(seed)
                    all_teams.append({
                        "id": tid,
                        "team": name,
                        "region": region_name,
                        **s,
                    })
                else:
                    all_teams.append({
                        "id": tid,
                        "team": name,
                        "seed": seed,
                        "region": region_name,
                        "adj_em": 0,
                        "adj_o": 100,
                        "adj_d": 100,
                        "efg_pct": 0.5,
                        "to_pct": 0.18,
                        "orb_pct": 0.28,
                        "ftr": 0.32,
                        "opp_efg_pct": 0.48,
                        "opp_to_pct": 0.19,
                        "opp_orb_pct": 0.30,
                        "opp_ftr": 0.30,
                        "tempo": 68,
                    })
        bracket_regions.append(games)

    bracket = {"regions": bracket_regions, "finalfour": [[], []]}
    with open(DATA_DIR / "bracket_2026.json", "w") as f:
        json.dump(bracket, f, indent=2)
    print(f"Wrote {DATA_DIR / 'bracket_2026.json'}")

    with open(DATA_DIR / "teams_2026.json", "w") as f:
        json.dump(all_teams, f, indent=2)
    print(f"Wrote {DATA_DIR / 'teams_2026.json'} with {len(all_teams)} teams")


if __name__ == "__main__":
    main()
