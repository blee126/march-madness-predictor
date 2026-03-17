"""
Train March Madness outcome classifier on real game data (2002–2025).
Uses team stats from backend/teamdata/ and game outcomes from backend/gamedata/{year}.json.
Trains an ensemble (VotingClassifier) with optional grid search for best accuracy.
"""
import argparse
import json
import pickle
from pathlib import Path

import numpy as np
from sklearn.ensemble import (
    GradientBoostingClassifier,
    RandomForestClassifier,
    VotingClassifier,
)
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import GridSearchCV, cross_val_score, train_test_split

from data_loader import (
    FEATURE_ORDER,
    build_xy,
    load_defense,
    load_offense,
    load_pre_tournament,
)

DATA_DIR = Path(__file__).parent / "data"
TEAMS_PATH = DATA_DIR / "teams.json"
MODEL_PATH = Path(__file__).parent / "model.pkl"
GAMEDATA_DIR = Path(__file__).parent / "gamedata"


def get_training_years() -> list[int]:
    """Years 2002..2025 that have both gamedata and pre-tournament stats."""
    years = []
    for y in range(2002, 2026):
        if (GAMEDATA_DIR / f"{y}.json").exists():
            years.append(y)
    return years


def main(
    test_size: float = 0.15,
    random_state: int = 42,
    cv: int = 5,
    tune_ensemble: bool = True,
):
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    years = get_training_years()
    if not years:
        raise FileNotFoundError(f"No gamedata/*.json found in {GAMEDATA_DIR}")
    print(f"Training years: {min(years)}–{max(years)} ({len(years)} years)")

    pre_tournament = load_pre_tournament()
    offense = load_offense()
    defense = load_defense()
    X, y = build_xy(years, pre_tournament, offense, defense)
    if X.size == 0:
        raise ValueError("No training samples: check team name matching in data_loader.py")
    print(f"Training samples: {len(y)} games")

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=test_size, random_state=random_state, stratify=y
    )

    # Base estimators for ensemble
    lr = LogisticRegression(max_iter=1000, random_state=random_state, C=0.5)
    rf = RandomForestClassifier(n_estimators=150, max_depth=8, random_state=random_state, min_samples_leaf=4)
    gb = GradientBoostingClassifier(
        n_estimators=150, max_depth=4, learning_rate=0.08, random_state=random_state, min_samples_leaf=4, subsample=0.8
    )
    ensemble = VotingClassifier(
        estimators=[("lr", lr), ("rf", rf), ("gb", gb)],
        voting="soft",
        weights=[1, 1, 1],
    )

    if tune_ensemble:
        param_grid = {
            "lr__C": [0.4, 1.0],
            "rf__n_estimators": [120, 180],
            "rf__max_depth": [7, 9],
            "gb__n_estimators": [120, 180],
            "gb__max_depth": [3, 5],
            "gb__learning_rate": [0.06, 0.1],
        }
        search = GridSearchCV(
            ensemble,
            param_grid,
            cv=min(cv, 4),
            scoring="accuracy",
            n_jobs=-1,
            verbose=1,
        )
        search.fit(X_train, y_train)
        clf = search.best_estimator_
        print(f"Best params: {search.best_params_}")
    else:
        clf = ensemble
        clf.fit(X_train, y_train)

    train_acc = clf.score(X_train, y_train)
    test_acc = clf.score(X_test, y_test)
    print(f"Train accuracy: {train_acc:.4f}, Test accuracy: {test_acc:.4f}")

    # Cross-validation on full dataset for stability estimate
    cv_scores = cross_val_score(clf, X, y, cv=5, scoring="accuracy")
    print(f"CV accuracy (5-fold): {cv_scores.mean():.4f} (+/- {cv_scores.std() * 2:.4f})")

    with open(MODEL_PATH, "wb") as f:
        pickle.dump(clf, f)
    print(f"Model saved to {MODEL_PATH}")

    # Persist FEATURE_ORDER so model.py and API stay in sync
    meta = {"feature_order": FEATURE_ORDER}
    with open(Path(__file__).parent / "model_meta.json", "w") as f:
        json.dump(meta, f, indent=2)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Train March Madness model on real data")
    parser.add_argument("--no-tune", action="store_true", help="Skip grid search (faster)")
    parser.add_argument("--test-size", type=float, default=0.15)
    parser.add_argument("--cv", type=int, default=5)
    args = parser.parse_args()
    main(tune_ensemble=not args.no_tune, test_size=args.test_size, cv=args.cv)
