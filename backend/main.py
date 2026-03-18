"""
March Madness Prediction API
Team1 features + Team2 features + round -> P(Team1 wins)
"""
from pathlib import Path
from fastapi import FastAPI, HTTPException, Body
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List
import json

from model import load_model_and_teams, predict_matchup

app = FastAPI(title="March Madness Prediction API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "*",  # allow all origins for deployed frontend
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

DATA_DIR = Path(__file__).parent / "data"
MODEL_PATH = Path(__file__).parent / "model.pkl"
TEAMS_PATH = DATA_DIR / "teams_2026.json"
BRACKET_PATH = DATA_DIR / "bracket_2026.json"
SENTIMENT_PATH = DATA_DIR / "sentiment_teams.json"  # precomputed from offline crawl

# Load model and team data on startup
model_data = None


@app.on_event("startup")
def startup():
    global model_data
    try:
        model_data = load_model_and_teams(MODEL_PATH, TEAMS_PATH)
    except (FileNotFoundError, Exception):
        model_data = None  # Run: python train_model.py


class PredictRequest(BaseModel):
    team1_id: str
    team2_id: str
    round_of: int = 64  # 64, 32, 16, 8, 4, 2
    preferences: Optional[dict] = None  # e.g. {"seed_weight": 1.2, "offense_weight": 1.0}


class PredictResponse(BaseModel):
    team1_win_prob: float
    team2_win_prob: float
    recommended_winner_id: str


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/teams")
def teams():
    """Return all teams with features for bracket building."""
    if model_data is None:
        raise HTTPException(status_code=503, detail="Model not loaded")
    return {"teams": model_data["teams_list"], "by_id": model_data["teams_by_id"]}


@app.get("/bracket")
def get_bracket():
    """Return the current year bracket template (regions, matchups)."""
    if not BRACKET_PATH.exists():
        raise HTTPException(status_code=404, detail="Bracket template not found")
    with open(BRACKET_PATH) as f:
        return json.load(f)


@app.post("/predict", response_model=PredictResponse)
def predict(req: PredictRequest):
    """Predict winner of a single matchup."""
    if model_data is None:
        raise HTTPException(status_code=503, detail="Model not loaded")
    prob = predict_matchup(
        model_data, req.team1_id, req.team2_id, req.round_of, req.preferences
    )
    winner = req.team1_id if prob >= 0.5 else req.team2_id
    return PredictResponse(
        team1_win_prob=round(prob, 4),
        team2_win_prob=round(1 - prob, 4),
        recommended_winner_id=winner,
    )


class FillBracketBody(BaseModel):
    preferences: Optional[dict] = None
    user_prompt: Optional[str] = None  # free-form text to influence preferences via LLM
    sentiment_teams: Optional[dict] = None  # { "Team Name": sentiment number } from article analysis
    use_precomputed_sentiment: Optional[bool] = None  # merge sentiment from data/sentiment_teams.json if true
    deterministic: Optional[bool] = None  # if true, always pick higher-prob team (no random sampling)


@app.post("/fill-bracket")
def fill_bracket(body: Optional[FillBracketBody] = Body(None)):
    """Return a full predicted bracket (all matchups resolved)."""
    if model_data is None:
        raise HTTPException(status_code=503, detail="Model not loaded")
    if not BRACKET_PATH.exists():
        raise HTTPException(status_code=404, detail="Bracket template not found")
    with open(BRACKET_PATH) as f:
        bracket = json.load(f)
    from bracket_fill import fill_bracket_with_predictions
    from ollama_client import is_available, prompt_to_preferences_and_teams
    user_prefs = dict((body.preferences if body else None) or {})
    prompt_bias = {}
    if body and body.user_prompt and body.user_prompt.strip() and is_available():
        from sentiment_crawl import get_bracket_team_names
        bracket_team_names = get_bracket_team_names(bracket)
        llm_out = prompt_to_preferences_and_teams(body.user_prompt.strip(), bracket_team_names=bracket_team_names)
        if llm_out:
            prefs = dict((llm_out.get("preferences") or {}))
            prefs.update(user_prefs)
            prompt_bias = llm_out.get("team_bias") or {}
        else:
            prefs = user_prefs
    else:
        prefs = user_prefs
    sentiment_teams = dict((body.sentiment_teams if body else None) or {})
    if body and body.use_precomputed_sentiment and SENTIMENT_PATH.exists():
        try:
            with open(SENTIMENT_PATH) as f:
                precomputed = json.load(f)
            if isinstance(precomputed, dict):
                sentiment_teams.update(precomputed)
        except (json.JSONDecodeError, OSError):
            pass
    deterministic = bool(body.deterministic) if body and body.deterministic is not None else False
    filled = fill_bracket_with_predictions(
        model_data, bracket, prefs,
        sentiment_teams=sentiment_teams,
        prompt_bias=prompt_bias,
        deterministic=deterministic,
    )
    return filled


# --- Optional Ollama LLM (local, free). Set OLLAMA_BASE_URL / OLLAMA_MODEL to enable. ---


class LLMChatBody(BaseModel):
    messages: List[dict]  # [{ "role": "user"|"assistant"|"system", "content": "..." }]


class LLMChatResponse(BaseModel):
    ok: bool
    reply: Optional[str] = None
    error: Optional[str] = None


@app.get("/llm/status")
def llm_status():
    """Whether Ollama is configured and reachable."""
    from ollama_client import is_available, OLLAMA_BASE_URL, OLLAMA_MODEL, chat
    if not is_available():
        return {"enabled": False, "message": "Ollama not configured (set OLLAMA_BASE_URL, OLLAMA_MODEL)"}
    # Quick ping: send minimal chat and see if we get a response
    r = chat([{"role": "user", "content": "Say OK"}])
    if r is None:
        return {"enabled": True, "reachable": False, "base_url": OLLAMA_BASE_URL, "model": OLLAMA_MODEL}
    return {"enabled": True, "reachable": True, "base_url": OLLAMA_BASE_URL, "model": OLLAMA_MODEL}


class SentimentBody(BaseModel):
    text: str


@app.post("/llm/sentiment")
def llm_sentiment(body: SentimentBody):
    """Analyze article/Reddit/social text for team sentiment; returns summary + teams with sentiment -1/0/1."""
    from ollama_client import is_available, analyze_sentiment
    if not is_available():
        raise HTTPException(status_code=503, detail="Ollama not configured. Set OLLAMA_BASE_URL and OLLAMA_MODEL.")
    result = analyze_sentiment(body.text or "")
    if result is None:
        raise HTTPException(status_code=503, detail="Sentiment analysis failed or timed out.")
    return result


@app.post("/llm/chat", response_model=LLMChatResponse)
def llm_chat(body: LLMChatBody):
    """Send messages to Ollama and return the assistant reply."""
    from ollama_client import is_available, chat
    if not is_available():
        raise HTTPException(status_code=503, detail="Ollama not configured. Set OLLAMA_BASE_URL and OLLAMA_MODEL.")
    out = chat(body.messages)
    if out is None:
        raise HTTPException(
            status_code=503,
            detail="Ollama request failed or timed out. Is Ollama running? Try: ollama serve. Large models can take 1–2 minutes; set OLLAMA_TIMEOUT_SECONDS=120 if needed.",
        )
    msg = (out.get("message") or {}).get("content", "")
    return LLMChatResponse(ok=True, reply=msg or None)


# Bracket scoring: 1-2-4-8-16-32 points per round
POINTS_BY_ROUND = {64: 1, 32: 2, 16: 4, 8: 8, 4: 16, 2: 32}


def _match_key(t1: str, t2: str) -> frozenset:
    return frozenset([(t1 or "").strip().lower(), (t2 or "").strip().lower()])


class ScoreBracketBody(BaseModel):
    predictions: List[dict]  # [{ round_of, team1, team2, winner }, ...]
    actual_results: List[dict]  # [{ round_of, team1, team2, winner }, ...]


@app.post("/score-bracket")
def score_bracket(body: ScoreBracketBody):
    """
    Compare predictions to actual results. Returns total score and per-round breakdown.
    Uses standard NCAA scoring: R64=1, R32=2, R16=4, R8=8, FF=16, Final=32.
    """
    actual_by_round = {}
    for g in body.actual_results:
        r = g.get("round_of")
        if r not in actual_by_round:
            actual_by_round[r] = []
        t1, t2 = g.get("team1", ""), g.get("team2", "")
        actual_by_round[r].append({
            "key": _match_key(t1, t2),
            "winner": (g.get("winner") or "").strip().lower(),
        })
    by_round = {}
    total_score = 0
    for p in body.predictions:
        r = p.get("round_of")
        pts = POINTS_BY_ROUND.get(r, 0)
        t1, t2 = p.get("team1", ""), p.get("team2", "")
        pred_winner = (p.get("winner") or "").strip().lower()
        key = _match_key(t1, t2)
        actuals = actual_by_round.get(r) or []
        match = next((a for a in actuals if a["key"] == key), None)
        if not match:
            continue
        correct = pred_winner == match["winner"]
        if r not in by_round:
            by_round[r] = {"correct": 0, "total": 0, "points_earned": 0}
        by_round[r]["total"] += 1
        if correct:
            by_round[r]["correct"] += 1
            by_round[r]["points_earned"] += pts
            total_score += pts
    max_possible = sum(POINTS_BY_ROUND.get(r, 0) * data["total"] for r, data in by_round.items())
    return {
        "total_score": total_score,
        "max_possible": max_possible,
        "by_round": by_round,
    }
