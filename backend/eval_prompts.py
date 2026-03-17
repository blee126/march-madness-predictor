"""
Quick utility to inspect how the current LLM prompt → bias pipeline behaves.

It loads the 2025 bracket, extracts the team list, and then runs a set of
sample prompts through `prompt_to_preferences_and_teams`, printing out:

- preferences (feature weights)
- per-team bias scores (team_bias map)

Run from the backend folder:

    python eval_prompts.py

Make sure Ollama is running and OLLAMA_BASE_URL / OLLAMA_MODEL are set.
"""

from pathlib import Path
import json

from ollama_client import is_available, prompt_to_preferences_and_teams


DATA_DIR = Path(__file__).parent / "data"
BRACKET_PATH = DATA_DIR / "bracket_2026.json"


SAMPLE_PROMPTS = [
    # Style / strategy
    "more upsets",
    "no upsets, trust the seeds",
    "defense wins games",
    "offense wins games",
    "slow, grind-it-out basketball",
    "fast-paced run-and-gun, high scoring games",
    # Favorites / rooting interests
    "my favorite team is Arkansas",
    "I hate Duke",
    "I want Liberty to go deep",
    "rooting for underdogs and mid-majors",
    "I only trust Big Ten schools",
    "I want SEC schools to lose early",
    "I like blue teams",
    "I'm from Texas so favor Texas schools",
    "I don't want any 1 seed to win the championship",
    "I want Auburn to win it all",
    "no blue bloods, I want a new champion",
    "favor teams with great defense and slow tempo",
    "favor teams with elite offense and fast tempo",
    "balanced bracket, mix of chalk and upsets",
]


def load_bracket_teams() -> list[str]:
    if not BRACKET_PATH.exists():
        raise FileNotFoundError(BRACKET_PATH)
    with open(BRACKET_PATH) as f:
        bracket = json.load(f)
    from sentiment_crawl import get_bracket_team_names

    return get_bracket_team_names(bracket)


def main() -> None:
    if not is_available():
        print("Ollama not available. Set OLLAMA_BASE_URL / OLLAMA_MODEL and start ollama serve.")
        return

    teams = load_bracket_teams()
    print(f"Bracket teams ({len(teams)}): {', '.join(sorted(teams))}\n")

    for prompt in SAMPLE_PROMPTS:
        print("=" * 80)
        print(f"PROMPT: {prompt!r}")
        print("-" * 80)
        out = prompt_to_preferences_and_teams(prompt, bracket_team_names=teams)
        if out is None:
            print("  LLM call failed or returned invalid JSON.\n")
            continue
        prefs = out.get("preferences") or {}
        bias = out.get("team_bias") or {}
        print("preferences:", json.dumps(prefs, indent=2, sort_keys=True))
        # Show only teams with non-zero bias, sorted by absolute magnitude
        nonzero = [(name, float(v)) for name, v in bias.items() if abs(float(v)) > 0]
        nonzero.sort(key=lambda x: -abs(x[1]))
        if not nonzero:
            print("team_bias: (none)\n")
            continue
        print("team_bias (sorted by |bias|):")
        for name, val in nonzero:
            print(f"  {name:25s}  {val:+.3f}")
        print()


if __name__ == "__main__":
    main()

