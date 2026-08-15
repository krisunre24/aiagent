import json
from pathlib import Path

import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score, classification_report

from analyze import load_all_results, clean, extract_diff_lines


def build_features(df: pd.DataFrame) -> pd.DataFrame:
    """Turn raw benchmark rows into a feature table for a simple classifier.
    Kept deliberately small and interpretable rather than maximizing accuracy --
    the point here is showing the relationship, not squeezing out performance."""
    df = df.copy()
    df["diff_lines"] = df["diff_stat"].apply(extract_diff_lines)
    df["prompt_length"] = df["task_id"].str.len()  # proxy; real prompt text isn't stored per-row
    df["is_feature_task"] = df["task_id"].str.startswith("add_").astype(int)
    df["is_mutant_task"] = df["task_id"].str.startswith("mutant_").astype(int)

    features = df[[
        "num_tool_calls",
        "num_iterations",
        "diff_lines",
        "duration_seconds",
        "is_feature_task",
        "is_mutant_task",
    ]].fillna(0)
    target = df["passed"].astype(int)
    return features, target


if __name__ == "__main__":
    df = load_all_results()
    df_clean = clean(df)

    X, y = build_features(df_clean)
    print(f"Training on {len(X)} runs, {y.sum()} passed ({y.mean():.1%})")
    print()

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.25, random_state=42, stratify=y
    )

    model = LogisticRegression(max_iter=1000)
    model.fit(X_train, y_train)

    y_pred = model.predict(X_test)
    acc = accuracy_score(y_test, y_pred)

    print(f"Test accuracy: {acc:.1%}")
    print()
    print("Classification report:")
    print(classification_report(y_test, y_pred, target_names=["Failed", "Passed"]))
    print()

    print("Feature coefficients (positive = associated with passing):")
    for name, coef in zip(X.columns, model.coef_[0]):
        print(f"  {name}: {coef:+.3f}")

    # Baseline: what accuracy would a "always predict majority class" model get?
    baseline_acc = max(y_test.mean(), 1 - y_test.mean())
    print()
    print(f"Baseline (always predict majority class): {baseline_acc:.1%}")
    print(f"Model improvement over baseline: {acc - baseline_acc:+.1%}")
