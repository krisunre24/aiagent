import json
from pathlib import Path

import pandas as pd
from scipy import stats

RESULTS_DIR = Path(__file__).parent / "results"


def load_all_results() -> pd.DataFrame:
    """Load every benchmark result file into one DataFrame, tagging each row
    with its source file so we can filter/group by experiment later."""
    rows = []
    for path in sorted(RESULTS_DIR.glob("*.json")):
        with open(path) as f:
            data = json.load(f)
        for r in data:
            r = dict(r)
            r["source_file"] = path.name
            rows.append(r)
    return pd.DataFrame(rows)


def clean(df: pd.DataFrame, max_duration: float = 150.0) -> pd.DataFrame:
    """Filter out API errors and hung/outlier-duration runs -- the same
    filtering logic used manually throughout the project, now centralized."""
    return df[(df["outcome"] != "api_error") & (df["duration_seconds"] <= max_duration)].copy()


def two_proportion_test(passed_a: int, total_a: int, passed_b: int, total_b: int, label_a: str, label_b: str) -> None:
    """Fisher's exact test on two independent pass/fail proportions.
    Chosen over a z-test because sample sizes here are small (n<30 per group),
    where Fisher's exact is the more appropriate, less approximate test."""
    table = [
        [passed_a, total_a - passed_a],
        [passed_b, total_b - passed_b],
    ]
    odds_ratio, p_value = stats.fisher_exact(table)

    rate_a = passed_a / total_a
    rate_b = passed_b / total_b

    print(f"{label_a}: {passed_a}/{total_a} ({rate_a:.1%})")
    print(f"{label_b}: {passed_b}/{total_b} ({rate_b:.1%})")
    print(f"Fisher's exact test p-value: {p_value:.4f}")
    if p_value < 0.05:
        print("-> Statistically significant at alpha=0.05")
    else:
        print("-> NOT statistically significant at alpha=0.05 -- could plausibly be noise at this sample size")


if __name__ == "__main__":
    df = load_all_results()
    df_clean = clean(df)

    print(f"Loaded {len(df)} total rows across {df['source_file'].nunique()} result files")
    print(f"{len(df_clean)} rows remain after filtering api_error and >150s outlier runs")
    print()

    # The key open question from the README: is the prompt-specificity
    # finding (39% vs 28%) a real effect, or noise at this sample size?
    generic = df_clean[df_clean["source_file"] == "mutant_tasks.json"]
    specific = df_clean[df_clean["source_file"] == "mutant_tasks_specific_prompt.json"]

    print("=== Prompt specificity on mutant tasks ===")
    two_proportion_test(
        passed_a=int(generic["passed"].sum()),
        total_a=len(generic),
        passed_b=int(specific["passed"].sum()),
        total_b=len(specific),
        label_a="Generic prompt",
        label_b="Specific prompt",
    )
    print()

    # The main finding: bugfix vs feature-addition, across the 5-task suite
    TASK_TYPE = {
        "fix_division_by_zero": "bugfix",
        "fix_operator_precedence": "bugfix",
        "fix_float_precision_display": "bugfix",
        "add_modulo_operator": "feature",
        "add_power_operator": "feature",
    }
    five_task = df_clean[df_clean["task_id"].isin(TASK_TYPE.keys())].copy()
    five_task["task_type"] = five_task["task_id"].map(TASK_TYPE)

    bugfix = five_task[five_task["task_type"] == "bugfix"]
    feature = five_task[five_task["task_type"] == "feature"]

    print("=== Bug-fix vs feature-addition (hand-written 5-task suite) ===")
    two_proportion_test(
        passed_a=int(bugfix["passed"].sum()),
        total_a=len(bugfix),
        passed_b=int(feature["passed"].sum()),
        total_b=len(feature),
        label_a="Bug-fix tasks",
        label_b="Feature-addition tasks",
    )
