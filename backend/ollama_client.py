"""
Optional Ollama LLM client (local, free). Used for chat/commentary when enabled.
Set OLLAMA_BASE_URL and OLLAMA_MODEL in env, or leave unset to disable.
Ollama can take 30–60+ seconds for a response; we use a long timeout to avoid 500s.
"""
import os
from typing import Optional, List, Any

# Long timeout so slow Ollama responses don't cause 500 (often 30–60+ seconds)
OLLAMA_REQUEST_TIMEOUT = int(os.environ.get("OLLAMA_TIMEOUT_SECONDS", "120"))

OLLAMA_BASE_URL = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434").rstrip("/")
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "llama3.2")


def is_available() -> bool:
    """True if we should try to use Ollama (user has set base URL or we use default)."""
    return bool(OLLAMA_BASE_URL and OLLAMA_MODEL)


def chat(messages: list[dict], stream: bool = False) -> Optional[dict]:
    """
    POST to Ollama /api/chat. messages = [{ "role": "user"|"assistant"|"system", "content": "..." }].
    Returns reply dict with "message" key, or None on error.
    """
    if not is_available():
        return None
    try:
        import urllib.request
        import json as _json
        body = _json.dumps({
            "model": OLLAMA_MODEL,
            "messages": messages,
            "stream": stream,
        }).encode("utf-8")
        req = urllib.request.Request(
            f"{OLLAMA_BASE_URL}/api/chat",
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=OLLAMA_REQUEST_TIMEOUT) as resp:
            out = _json.loads(resp.read().decode())
            return out
    except Exception:
        return None


def generate(prompt: str, system: Optional[str] = None, stream: bool = False) -> Optional[str]:
    """
    POST to Ollama /api/generate. Returns full response text or None on error.
    """
    if not is_available():
        return None
    try:
        import urllib.request
        import json as _json
        payload = {"model": OLLAMA_MODEL, "prompt": prompt, "stream": stream}
        if system:
            payload["system"] = system
        body = _json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            f"{OLLAMA_BASE_URL}/api/generate",
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=OLLAMA_REQUEST_TIMEOUT) as resp:
            out = _json.loads(resp.read().decode())
            return out.get("response", "").strip() or None
    except Exception:
        return None


SENTIMENT_SYSTEM = """You analyze text about March Madness / NCAA basketball. Use ONLY the most recent information in the text—ignore anything about past seasons, old stats, or outdated performance. Base sentiment strictly on current-season form and recent news. Extract team names mentioned and assign each a sentiment number: 1 = positive (favored, strong, likely to win), 0 = neutral, -1 = negative (overrated, weak, likely to lose). Return ONLY valid JSON with no other text. Format: {"summary": "one short sentence", "teams": [{"name": "Duke", "sentiment": 1}, {"name": "Kentucky", "sentiment": -1}]}. Use exact team names as they appear in college basketball (e.g. "Duke", "North Carolina", "UConn"). If no teams are clearly mentioned, return {"summary": "...", "teams": []}."""


def analyze_sentiment(text: str) -> Optional[dict]:
    """
    Use Ollama to extract team sentiment from article/Reddit/social text.
    Returns {"summary": str, "teams": [{"name": str, "sentiment": int}]} or None.
    """
    if not text or not text.strip():
        return {"summary": "", "teams": []}
    raw = generate(text.strip()[:12000], system=SENTIMENT_SYSTEM)
    if not raw:
        return None
    try:
        import json as _json
        # Strip markdown code blocks if present and try to extract JSON.
        s = raw.strip()
        if s.startswith("```"):
            s = s.split("\n", 1)[-1] if "\n" in s else s[3:]
        if s.endswith("```"):
            s = s.rsplit("```", 1)[0].strip()
        try:
            out = _json.loads(s)
        except Exception:
            # Try to salvage JSON by looking for the first '{' and last '}'.
            start = s.find("{")
            end = s.rfind("}")
            if start != -1 and end != -1 and end > start:
                out = _json.loads(s[start : end + 1])
            else:
                raise
        summary = out.get("summary", "")
        teams = out.get("teams", [])
        if not isinstance(teams, list):
            teams = []
        return {"summary": summary, "teams": teams}
    except Exception:
        return None


PREFERENCES_SYSTEM = """You suggest March Madness bracket preference weights from a user's instruction. Weights scale model features: seed_weight, efficiency_weight, offense_weight, defense_weight, tempo_weight, upset_tendency. Each must be between 0.25 and 3.0. 1.0 = default. Higher upset_tendency = more random/upset-heavy bracket. Return ONLY a JSON object with exactly these keys and numbers, no other text: {"seed_weight": 1.0, "efficiency_weight": 1.0, "offense_weight": 1.0, "defense_weight": 1.0, "tempo_weight": 1.0, "upset_tendency": 1.0}."""

PROMPT_INFLUENCE_SYSTEM = """Interpret the user's instruction for their March Madness bracket. Return a single JSON object with exactly these keys:

"preferences": object with numeric values for seed_weight, efficiency_weight, offense_weight, defense_weight, tempo_weight, upset_tendency. Each must be between 0.25 and 3.0; use 1.0 when you cannot infer a value. These weights scale how much the model emphasizes seed, efficiency, offense, defense, tempo, and upset tendency.

When the user talks about STYLE or STRATEGY, reflect that strongly in preferences:
- Phrases like "more upsets", "I love underdogs", "chaos" -> set upset_tendency HIGH (2.0–3.0) and seed_weight LOW (0.4–0.8).
- Phrases like "chalk", "favorites", "no upsets", "trust the seeds" -> upset_tendency LOW (0.25–0.7) and seed_weight HIGH (1.6–3.0).
- "defense wins games", "tough defense", "gritty", "slow it down" -> defense_weight HIGH (1.7–3.0), tempo_weight LOW (0.4–0.9), offense_weight slightly LOWER (0.6–1.0).
- "offense wins games", "high scoring", "run-and-gun", "up-tempo" -> offense_weight HIGH (1.7–3.0), tempo_weight HIGH (1.6–3.0), defense_weight LOWER (0.4–0.9).
If the user is very strong about a style, choose more extreme values in these ranges; if they are mild, move weights only slightly away from 1.0.

"team_bias": array of objects describing which teams the user wants to help or hurt. Each object must be of the form {"name": "<team name>", "bias": <number between -1 and 1>}. Positive bias means the user favors that team (wants them to advance); negative bias means the user wants that team to lose. Use larger magnitudes (e.g. 0.8 or -0.8) for very strong language like "always goes deep", "must win", "hate", "never win"; use smaller magnitudes (e.g. 0.2) for softer language like "I kind of like".

You may infer team_bias entries from anything the user says (teams, conferences, colors, where they're from, who they like or dislike, etc.), but the JSON must only contain team names and numeric biases.

Return only valid JSON, no other text."""


def suggest_preferences_from_prompt(user_prompt: str) -> Optional[dict]:
    """
    Use Ollama to map a free-form user prompt (e.g. "I want more upsets") to preference weights.
    Returns dict of weights or None on failure.
    """
    if not user_prompt or not user_prompt.strip():
        return None
    raw = generate(
        f"User instruction for their bracket: {user_prompt.strip()[:500]}. Output the JSON object only.",
        system=PREFERENCES_SYSTEM,
    )
    if not raw:
        return None
    try:
        import json as _json
        s = raw.strip()
        if s.startswith("```"):
            s = s.split("\n", 1)[-1] if "\n" in s else s[3:]
        if s.endswith("```"):
            s = s.rsplit("```", 1)[0].strip()
        out = _json.loads(s)
        prefs = {}
        for key in ("seed_weight", "efficiency_weight", "offense_weight", "defense_weight", "tempo_weight", "upset_tendency"):
            v = out.get(key)
            if v is not None:
                try:
                    x = float(v)
                    prefs[key] = max(0.25, min(3.0, x))
                except (TypeError, ValueError):
                    pass
        return prefs if prefs else None
    except Exception:
        return None


def prompt_to_preferences_and_teams(
    user_prompt: str,
    bracket_team_names: Optional[List[str]] = None,
) -> Optional[dict]:
    """
    Use Ollama to get both preference weights and per-team bias scores from user prompt.
    If bracket_team_names is provided, the LLM is told to use only those names (exact spelling) in team_bias.
    Returns {"preferences": {...}, "team_bias": {team_name: bias_float}} or None.
    """
    if not user_prompt or not user_prompt.strip():
        return None
    system = PROMPT_INFLUENCE_SYSTEM
    if bracket_team_names:
        names_list = ", ".join(sorted(bracket_team_names))
        system = (
            PROMPT_INFLUENCE_SYSTEM
            + "\n\nOnly the following teams are in the bracket you are predicting. "
            + "In favor_teams and disfavor_teams you must use only names from this list, with exact spelling. "
            + "Do not include any team not in the list.\nTeams in bracket: "
            + names_list
        )
    raw = generate(
        f"User instruction: {user_prompt.strip()[:600]}. Output the JSON object only.",
        system=system,
    )
    if not raw:
        return None
    try:
        import json as _json
        s = raw.strip()
        if s.startswith("```"):
            s = s.split("\n", 1)[-1] if "\n" in s else s[3:]
        if s.endswith("```"):
            s = s.rsplit("```", 1)[0].strip()
        try:
            out = _json.loads(s)
        except Exception:
            # Try to salvage JSON by looking for the first '{' and last '}'.
            start = s.find("{")
            end = s.rfind("}")
            if start != -1 and end != -1 and end > start:
                out = _json.loads(s[start : end + 1])
            else:
                # For debugging eval_prompts.py, print the raw response once.
                print("prompt_to_preferences_and_teams: failed to parse JSON from LLM response:")
                print(raw[:1000])
                return None
        prefs = {}
        for key in ("seed_weight", "efficiency_weight", "offense_weight", "defense_weight", "tempo_weight", "upset_tendency"):
            v = (out.get("preferences") or {}).get(key)
            if v is not None:
                try:
                    x = float(v)
                    prefs[key] = max(0.25, min(3.0, x))
                except (TypeError, ValueError):
                    pass

        bias_map: dict[str, float] = {}
        team_bias = out.get("team_bias")
        if isinstance(team_bias, list):
            for item in team_bias:
                if not isinstance(item, dict):
                    continue
                name = str(item.get("name") or "").strip()
                if not name:
                    continue
                try:
                    bias = float(item.get("bias", 0.0))
                except (TypeError, ValueError):
                    continue
                # Clamp to [-1, 1]
                if bias > 1.0:
                    bias = 1.0
                elif bias < -1.0:
                    bias = -1.0
                if bracket_team_names:
                    allowed = set((n or "").strip() for n in bracket_team_names if (n or "").strip())
                    if name not in allowed:
                        continue
                if abs(bias) > 0:
                    bias_map[name] = bias

        # Backwards compatibility: if team_bias is missing but favor_teams/disfavor_teams exist,
        # turn them into +/-1.0 entries.
        if not bias_map:
            favor = out.get("favor_teams")
            disfavor = out.get("disfavor_teams")
            if isinstance(favor, list):
                for n in favor:
                    name = str(n or "").strip()
                    if not name:
                        continue
                    if bracket_team_names:
                        allowed = set((t or "").strip() for t in bracket_team_names if (t or "").strip())
                        if name not in allowed:
                            continue
                    bias_map[name] = max(bias_map.get(name, 0.0), 1.0)
            if isinstance(disfavor, list):
                for n in disfavor:
                    name = str(n or "").strip()
                    if not name:
                        continue
                    if bracket_team_names:
                        allowed = set((t or "").strip() for t in bracket_team_names if (t or "").strip())
                        if name not in allowed:
                            continue
                    bias_map[name] = min(bias_map.get(name, 0.0), -1.0)

        return {"preferences": prefs, "team_bias": bias_map}
    except Exception:
        return None
