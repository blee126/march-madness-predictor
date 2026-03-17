"""
Classifier: Team1 features + Team2 features + round -> P(Team1 wins).
Predictions use only numeric features (seed, efficiency, offense, defense, etc.);
team name is never used for prediction, only for display and lookup.
Teams with no data get a seed-based fallback feature vector so the model can still run.
"""
import json
import pickle
from pathlib import Path
from typing import Optional, Set, Iterable

import numpy as np


def _name_in_set(team_name: str, names: Set[str]) -> bool:
    """Case-insensitive match; also check if any name in set is a substring of team_name or vice versa."""
    if not team_name or not names:
        return False
    t = team_name.strip().lower()
    for n in names:
        if not n:
            continue
        nlower = n.strip().lower()
        if t == nlower or t in nlower or nlower in t:
            return True
    return False

MODEL_PATH = Path(__file__).parent / "model.pkl"
TEAMS_PATH = Path(__file__).parent / "data" / "teams.json"

# Tunable: how much sentiment and user-prompt bias shift P(team1 wins). 0 = no shift.
SENTIMENT_DELTA_SCALE = 0.18   # per unit sentiment diff (e.g. +1 vs -1 → 2 * this)
# Prompt-based bias: strongest near 50/50 games and much weaker for heavy mismatches,
# but with a large enough scale that strong prompts (bias ~ +/-1) noticeably change outcomes.
PROMPT_DELTA_SCALE = 0.30     # max effect of full +/-1 bias before closeness scaling

# Tunable: additional seed-based bias applied in logit space from the preference slider.
# seed_weight > 1 favors better seeds (lower numbers); < 1 favors upsets.
SEED_PREF_LOGIT_SCALE = 0.05  # how much one unit of seed_weight above/below 1.0 moves logit per seed difference

# Feature names used by the trained model (order matters). No team name / string features.
FEATURE_ORDER = [
    "seed",
    "adj_em",
    "adj_o",
    "adj_d",
    "efg_pct",
    "to_pct",
    "orb_pct",
    "ftr",
    "opp_efg_pct",
    "opp_to_pct",
    "opp_orb_pct",
    "opp_ftr",
    "tempo",
    "round_64",
    "round_32",
    "round_16",
    "round_8",
    "round_4",
    "round_2",
]


def _team_feature_vector(team: dict, round_of: int) -> np.ndarray:
    """Build feature vector for one side of matchup (diff with opponent done in predict)."""
    arr = []
    for key in FEATURE_ORDER:
        if key.startswith("round_"):
            r = int(key.split("_")[1])
            arr.append(1.0 if round_of == r else 0.0)
        else:
            arr.append(float(team.get(key, 0)))
    return np.array(arr, dtype=np.float64)


def _default_team_for_seed(seed: int) -> dict:
    """Feature dict for a team with no training data: seed + neutral defaults only."""
    s = int(seed)
    return {
        "seed": s,
        "adj_em": 0.0,
        "adj_o": 100.0,
        "adj_d": 100.0,
        "efg_pct": 0.5,
        "to_pct": 0.18,
        "orb_pct": 0.28,
        "ftr": 0.32,
        "opp_efg_pct": 0.48,
        "opp_to_pct": 0.19,
        "opp_orb_pct": 0.30,
        "opp_ftr": 0.30,
        "tempo": 68.0,
    }


def load_model_and_teams(model_path: Path, teams_path: Path):
    if not model_path.exists():
        raise FileNotFoundError(f"Run train_model.py first: {model_path}")
    with open(model_path, "rb") as f:
        clf = pickle.load(f)
    with open(teams_path) as f:
        teams = json.load(f)

    # If this is a single-season teams file (e.g. teams_2025.json), try to
    # patch any neutral/default teams (adj_em=0, adj_o=100, adj_d=100) with
    # real KenPom stats for that season when available.
    season_year = None
    stem = teams_path.stem  # e.g. "teams_2025"
    if "_" in stem:
        try:
            season_year = int(stem.split("_")[-1])
        except ValueError:
            season_year = None
    if season_year is not None:
        try:
            from data_loader import (
                load_pre_tournament,
                load_offense,
                load_defense,
                get_team_stats,
            )

            pre_t = load_pre_tournament(season_year)
            off_t = load_offense(season_year)
            def_t = load_defense(season_year)
        except Exception:
            pre_t = off_t = def_t = None
        if pre_t is not None:
            for t in teams:
                if (
                    isinstance(t, dict)
                    and float(t.get("adj_em", 0)) == 0.0
                    and float(t.get("adj_o", 100)) == 100.0
                    and float(t.get("adj_d", 100)) == 100.0
                ):
                    name = t.get("team") or t.get("TeamName") or ""
                    if not name:
                        continue
                    try:
                        stats = get_team_stats(season_year, name, pre_t, off_t, def_t)
                    except Exception:
                        stats = None
                    if stats:
                        # Preserve explicit seed from bracket if present
                        seed = t.get("seed", stats.get("seed"))
                        t.update(stats)
                        if seed is not None:
                            t["seed"] = seed
    teams_list = teams if isinstance(teams, list) else list(teams.values())
    by_id = {}
    for t in teams_list:
        if isinstance(t, dict):
            kid = t.get("id") or t.get("TeamID") or t.get("team_id") or t.get("team", "")
            if kid:
                by_id[kid] = t
    return {"model": clf, "teams_list": teams_list, "teams_by_id": by_id, "feature_order": FEATURE_ORDER}


def get_team_features(teams_by_id: dict, team_id: str) -> Optional[dict]:
    return teams_by_id.get(team_id)


# Indices into FEATURE_ORDER for preference scaling (non-round features only)
_FEATURE_WEIGHT_INDEX = {
    "seed": 0,
    "adj_em": 1,
    "adj_o": 2,
    "adj_d": 3,
    "tempo": 12,
}


def predict_matchup(
    model_data: dict,
    team1_id: str,
    team2_id: str,
    round_of: int = 64,
    preferences: Optional[dict] = None,
    team1_seed: Optional[int] = None,
    team2_seed: Optional[int] = None,
    sentiment_teams: Optional[dict] = None,
    team1_name: Optional[str] = None,
    team2_name: Optional[str] = None,
    prompt_bias: Optional[dict] = None,
) -> float:
    """
    Returns P(team1 wins). Uses only numeric features (no team name).
    sentiment_teams: optional { "Team Name": -1|0|1 } from article analysis; shifts prob toward favored team.
    favor_teams / disfavor_teams: from user prompt (e.g. "my favorite is Arkansas") to pull outcome that way.
    """
    by_id = model_data["teams_by_id"]
    t1 = by_id.get(team1_id)
    t2 = by_id.get(team2_id)
    if t1 is None:
        t1 = _default_team_for_seed(team1_seed if team1_seed is not None else 8)
    if t2 is None:
        t2 = _default_team_for_seed(team2_seed if team2_seed is not None else 8)
    v1 = _team_feature_vector(t1, round_of)
    v2 = _team_feature_vector(t2, round_of)
    diff = (v1 - v2).reshape(1, -1)

    if preferences:
        # Build per-feature weight vector (1.0 for round one-hots and unweighted features)
        w = np.ones(diff.shape[1], dtype=np.float64)
        w[_FEATURE_WEIGHT_INDEX["seed"]] = float(preferences.get("seed_weight", 1.0))
        w[_FEATURE_WEIGHT_INDEX["adj_em"]] = float(preferences.get("efficiency_weight", 1.0))
        w[_FEATURE_WEIGHT_INDEX["adj_o"]] = float(preferences.get("offense_weight", 1.0))
        w[_FEATURE_WEIGHT_INDEX["adj_d"]] = float(preferences.get("defense_weight", 1.0))
        w[_FEATURE_WEIGHT_INDEX["tempo"]] = float(preferences.get("tempo_weight", 1.0))
        upset = float(preferences.get("upset_tendency", 1.0))
        if upset > 0:
            # Shrink diff toward 0 -> predictions toward 0.5 (more upsets)
            w = w / upset
        diff = diff * w

    # Base probability from numeric model
    prob = float(model_data["model"].predict_proba(diff)[0, 1])
    base_prob = prob

    # Optional additional seed-based bias driven directly by the seed_weight preference.
    # This operates in logit space so the effect is smooth and symmetric and does not
    # require retraining the model.
    if preferences and team1_seed is not None and team2_seed is not None:
        try:
            seed_pref = float(preferences.get("seed_weight", 1.0)) - 1.0
        except (TypeError, ValueError):
            seed_pref = 0.0
        if seed_pref != 0.0:
            # Positive diff means team1 is better seed (3 vs 14 -> diff = 14 - 3 = 11).
            seed_diff = float(team2_seed) - float(team1_seed)
            # Move logit toward better seed when seed_pref>0, toward worse seed when seed_pref<0.
            if 0.0 < prob < 1.0:
                import math

                logit = math.log(prob / (1.0 - prob))
                logit += SEED_PREF_LOGIT_SCALE * seed_pref * seed_diff
                prob = 1.0 / (1.0 + math.exp(-logit))

    # Sentiment: pull probability toward favored team
    if sentiment_teams and (team1_name or team2_name):
        b1 = float(sentiment_teams.get(team1_name or "", 0))
        b2 = float(sentiment_teams.get(team2_name or "", 0))
        delta = (b1 - b2) * SENTIMENT_DELTA_SCALE
        prob = prob + delta
    # User prompt per-team bias: pull probability toward teams with higher bias
    if prompt_bias and (team1_name or team2_name):
        n1 = (team1_name or "").strip()
        n2 = (team2_name or "").strip()
        b1 = float(prompt_bias.get(n1, 0.0)) if n1 else 0.0
        b2 = float(prompt_bias.get(n2, 0.0)) if n2 else 0.0
        # Clamp again defensively
        b1 = max(-1.0, min(1.0, b1))
        b2 = max(-1.0, min(1.0, b2))
        # Base shift from bias difference
        d = (b1 - b2) * PROMPT_DELTA_SCALE
        # Scale prompt effect by how close the game already is. Near 50/50 -> full effect;
        # near 0 or 1 -> almost no effect so huge mismatches aren't flipped by the prompt.
        margin = abs(base_prob - 0.5)  # 0 at 50/50, up to 0.5 at extremes
        closeness_scale = max(0.0, 1.0 - 2.0 * margin)  # 1 at 0.5, 0 at 0 or 1
        prob = prob + d * closeness_scale
    return max(0.0, min(1.0, prob))
