"""
Optional agent that crawls the web for articles about each bracket team,
runs sentiment analysis via Ollama, and returns per-team sentiment for predictions.
Uses ddgs for search (no API key); restricts to current season / recent articles only.
"""
import time
from datetime import datetime
from typing import Optional

# Max snippet length to send to Ollama per team
MAX_TEXT_PER_TEAM = 10_000
# Delay between teams to avoid rate limits (seconds)
DELAY_BETWEEN_TEAMS = 1.5
# Max search results to combine per team
MAX_SEARCH_RESULTS = 5
# DDG timelimit: "d"=day, "w"=week, "m"=month, "y"=year – use past month for most recent articles only
SEARCH_TIMELIMIT = "m"


def _season_year() -> int:
    """Tournament year for current season (e.g. 2025 for March 2025)."""
    now = datetime.utcnow()
    # Jan–Apr = this year's tournament; May–Dec = next year's tournament
    return now.year if now.month <= 4 else now.year + 1


def _search_team(team_name: str, season_year: Optional[int] = None) -> list[dict]:
    """Return list of search result dicts with 'title' and 'body' (snippets). Recent/this season only."""
    year = season_year if season_year is not None else _season_year()
    try:
        from ddgs import DDGS
        ddgs = DDGS()
        query = f"{team_name} March Madness {year} recent news"
        results = list(ddgs.text(
            query,
            max_results=MAX_SEARCH_RESULTS,
            timelimit=SEARCH_TIMELIMIT,
        ))
        return results or []
    except Exception:
        return []


def _fetch_page_text(url: str, timeout: int = 8) -> str:
    """Fetch URL and return plain text (first 8000 chars). Returns '' on failure."""
    try:
        import requests
        from bs4 import BeautifulSoup
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; rv:109.0) Gecko/20100101 Firefox/115.0"}
        r = requests.get(url, headers=headers, timeout=timeout)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "html.parser")
        for tag in soup(["script", "style", "nav", "footer", "header"]):
            tag.decompose()
        text = soup.get_text(separator=" ", strip=True)
        return (text or "")[:8000]
    except Exception:
        return ""


def _collect_text_for_team(
    team_name: str,
    use_fetch: bool = False,
    season_year: Optional[int] = None,
) -> str:
    """Search for team (this season only), optionally fetch first URL; return combined text for sentiment."""
    results = _search_team(team_name, season_year=season_year)
    parts = []
    for r in results:
        title = (r.get("title") or "").strip()
        body = (r.get("body") or "").strip()
        if title or body:
            parts.append(f"{title}\n{body}")
    if use_fetch and results and results[0].get("href"):
        url_text = _fetch_page_text(results[0]["href"])
        if url_text:
            parts.append(url_text)
    combined = "\n\n".join(parts)
    return combined[:MAX_TEXT_PER_TEAM] if combined else ""


def crawl_sentiment_for_teams(
    team_names: list[str],
    *,
    max_teams: int = 16,
    use_page_fetch: bool = False,
    season_year: Optional[int] = None,
) -> dict:
    """
    For each team (up to max_teams): search web for this season only, collect text, run Ollama sentiment.
    Returns {"summary": str, "teams": [{"name": str, "sentiment": int}]}.
    """
    from ollama_client import analyze_sentiment, is_available
    if not is_available():
        return {"summary": "Ollama not configured.", "teams": []}
    year = season_year if season_year is not None else _season_year()
    teams = list(team_names)[:max_teams]
    out_teams = []
    for i, name in enumerate(teams):
        if i > 0:
            time.sleep(DELAY_BETWEEN_TEAMS)
        text = _collect_text_for_team(name, use_fetch=use_page_fetch, season_year=year)
        sentiment = 0
        if text:
            result = analyze_sentiment(text)
            if result and result.get("teams"):
                for t in result["teams"]:
                    if (t.get("name") or "").strip().lower() == name.strip().lower():
                        try:
                            sentiment = int(t.get("sentiment", 0))
                        except (TypeError, ValueError):
                            pass
                        break
        out_teams.append({"name": name, "sentiment": max(-1, min(1, sentiment))})
    return {
        "summary": f"Crawled sentiment for {len(out_teams)} teams from recent ({year} season) web search.",
        "teams": out_teams,
    }


def get_bracket_team_names(bracket: dict) -> list[str]:
    """Extract unique team names from bracket template (regions + games)."""
    seen = set()
    names = []
    for region in bracket.get("regions", []):
        for game in region:
            for slot in game:
                if isinstance(slot, dict):
                    team = (slot.get("team") or slot.get("team_name") or "").strip()
                    if team and team not in seen:
                        seen.add(team)
                        names.append(team)
    return names
