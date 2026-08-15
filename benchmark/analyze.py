import matplotlib
matplotlib.use("Agg")  # no display needed, just save files
import matplotlib.pyplot as plt
import re

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

def plot_pass_rate_by_model_task(df: pd.DataFrame, out_path: Path) -> None:
    """Grouped bar chart: pass rate per model, per task, for the 5-task hand-written suite."""
    TASK_TYPE = {
        "fix_division_by_zero": "bugfix",
        "fix_operator_precedence": "bugfix",
        "fix_float_precision_display": "bugfix",
        "add_modulo_operator": "feature",
        "add_power_operator": "feature",
    }
    subset = df[df["task_id"].isin(TASK_TYPE.keys())].copy()
    grouped = subset.groupby(["model", "task_id"])["passed"].mean().unstack() * 100

    ax = grouped.T.plot(kind="bar", figsize=(10, 5))
    ax.set_ylabel("Pass rate (%)")
    ax.set_xlabel("Task")
    ax.set_title("Pass rate by model and task")
    ax.legend(title="Model", bbox_to_anchor=(1.02, 1), loc="upper left")
    ax.set_ylim(0, 105)
    plt.xticks(rotation=30, ha="right")
    plt.tight_layout()
    plt.savefig(out_path, dpi=150)
    plt.close()
    print(f"Saved {out_path}")


def extract_diff_lines(diff_stat) -> int:
    """Pull total changed lines (insertions + deletions) out of a git diff --stat string.
    Older result files predate the git_diff tool and have no diff_stat at all,
    which pandas loads as NaN (a float) rather than an empty string -- handle both."""
    if not isinstance(diff_stat, str) or not diff_stat:
        return 0
    match = re.search(r"(\d+) insertion", diff_stat)
    insertions = int(match.group(1)) if match else 0
    match = re.search(r"(\d+) deletion", diff_stat)
    deletions = int(match.group(1)) if match else 0
    return insertions + deletions

def plot_diff_size_vs_outcome(df: pd.DataFrame, out_path: Path) -> None:
    """Box plot: does the size of the agent's code change differ between passed and failed runs?"""
    subset = df[df["diff_stat"].apply(lambda x: isinstance(x, str) and len(x) > 0)].copy()
    subset["diff_lines"] = subset["diff_stat"].apply(extract_diff_lines)
    subset["outcome_label"] = subset["passed"].map({True: "Passed", False: "Failed"})

    fig, ax = plt.subplots(figsize=(6, 5))
    subset.boxplot(column="diff_lines", by="outcome_label", ax=ax)
    ax.set_ylabel("Lines changed (insertions + deletions)")
    ax.set_xlabel("")
    ax.set_title("Change size vs. outcome (runs with a real code change only)")
    plt.suptitle("")
    plt.tight_layout()
    plt.savefig(out_path, dpi=150)
    plt.close()
    print(f"Saved {out_path}")


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

    charts_dir = Path(__file__).parent / "charts"
    charts_dir.mkdir(exist_ok=True)
    plot_pass_rate_by_model_task(df_clean, charts_dir / "pass_rate_by_model_task.png")
    plot_diff_size_vs_outcome(df_clean, charts_dir / "diff_size_vs_outcome.png")
