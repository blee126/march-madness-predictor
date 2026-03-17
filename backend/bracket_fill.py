"""
Fill bracket with model predictions.
Uses win probability from the model and randomly samples the winner so each fill
simulates the tournament (different runs can produce different brackets).
"""

import random
from typing import Optional, List, Dict


def _get_team_id(slot: dict) -> str:
    return slot.get("id") or slot.get("TeamID") or slot.get("team_id") or slot.get("team", "")


def fill_bracket_with_predictions(
    model_data: dict,
    bracket: dict,
    preferences: dict,
    sentiment_teams: Optional[dict] = None,
    prompt_bias: Optional[Dict[str, float]] = None,
    deterministic: bool = False,
) -> dict:
    from model import predict_matchup

    sentiment_teams = sentiment_teams or {}
    prompt_bias = prompt_bias or {}
    regions = bracket.get("regions", [])
    result = {"predictions": [], "region_winners": [], "champion": None, "rounds": {}}

    def _team_name(slot: dict, fallback_id: str) -> str:
        return (slot.get("team") or fallback_id) or ""

    for region_idx, round_64_games in enumerate(regions):
        current = list(round_64_games)  # list of games, each game = [team1, team2]
        round_of = 64
        while len(current) >= 1:
            winners = []
            for game in current:
                t1, t2 = game[0], game[1]
                id1, id2 = _get_team_id(t1), _get_team_id(t2)
                s1 = int(t1.get("seed", 8)) if t1.get("seed") is not None else None
                s2 = int(t2.get("seed", 8)) if t2.get("seed") is not None else None
                n1, n2 = _team_name(t1, id1), _team_name(t2, id2)
                prob = predict_matchup(
                    model_data, id1, id2, round_of, preferences,
                    team1_seed=s1, team2_seed=s2,
                    sentiment_teams=sentiment_teams, team1_name=n1, team2_name=n2,
                    prompt_bias=prompt_bias,
                )
                if deterministic:
                    winner = t1 if prob >= 0.5 else t2
                else:
                    winner = t1 if random.random() < prob else t2
                winners.append(winner)
                result["predictions"].append({
                    "region_index": region_idx,
                    "round_of": round_of,
                    "team1": t1.get("team", id1),
                    "team2": t2.get("team", id2),
                    "team1_seed": s1,
                    "team2_seed": s2,
                    "team1_id": id1,
                    "team2_id": id2,
                    "winner": winner.get("team", _get_team_id(winner)),
                    "winner_id": _get_team_id(winner),
                    "team1_win_prob": round(prob, 4),
                })
            if len(winners) == 1:
                result["region_winners"].append(winners[0])
                break
            # Pair winners for next round
            current = [[winners[i * 2], winners[i * 2 + 1]] for i in range(len(winners) // 2)]
            round_of = {64: 32, 32: 16, 16: 8, 8: 4}.get(round_of, 4)

    # Final Four: 4 region winners -> 2 semis -> 1 final
    if len(result["region_winners"]) == 4:
        semis = [
            [result["region_winners"][0], result["region_winners"][1]],
            [result["region_winners"][2], result["region_winners"][3]],
        ]
        semi_winners = []
        for game in semis:
            t1, t2 = game[0], game[1]
            id1, id2 = _get_team_id(t1), _get_team_id(t2)
            s1 = int(t1.get("seed", 8)) if t1.get("seed") is not None else None
            s2 = int(t2.get("seed", 8)) if t2.get("seed") is not None else None
            n1, n2 = _team_name(t1, id1), _team_name(t2, id2)
            prob = predict_matchup(
                model_data, id1, id2, 4, preferences,
                team1_seed=s1, team2_seed=s2,
                sentiment_teams=sentiment_teams, team1_name=n1, team2_name=n2,
                prompt_bias=prompt_bias,
            )
            if deterministic:
                w = t1 if prob >= 0.5 else t2
            else:
                w = t1 if random.random() < prob else t2
            semi_winners.append(w)
            result["predictions"].append({
                "region_index": None,
                "round_of": 4,
                "team1": t1.get("team", id1),
                "team2": t2.get("team", id2),
                "team1_seed": s1,
                "team2_seed": s2,
                "winner": w.get("team", _get_team_id(w)),
                "team1_win_prob": round(prob, 4),
            })
        if len(semi_winners) == 2:
            t1, t2 = semi_winners[0], semi_winners[1]
            id1, id2 = _get_team_id(t1), _get_team_id(t2)
            s1 = int(t1.get("seed", 8)) if t1.get("seed") is not None else None
            s2 = int(t2.get("seed", 8)) if t2.get("seed") is not None else None
            n1, n2 = _team_name(t1, id1), _team_name(t2, id2)
            prob = predict_matchup(
                model_data, id1, id2, 2, preferences,
                team1_seed=s1, team2_seed=s2,
                sentiment_teams=sentiment_teams, team1_name=n1, team2_name=n2,
                prompt_bias=prompt_bias,
            )
            if deterministic:
                champ = t1 if prob >= 0.5 else t2
            else:
                champ = t1 if random.random() < prob else t2
            result["champion"] = champ.get("team", _get_team_id(champ))
            result["predictions"].append({
                "region_index": None,
                "round_of": 2,
                "team1": t1.get("team", id1),
                "team2": t2.get("team", id2),
                "team1_seed": s1,
                "team2_seed": s2,
                "winner": result["champion"],
                "team1_win_prob": round(prob, 4),
            })

    return result
