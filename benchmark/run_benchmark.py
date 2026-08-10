import json
import os
import shutil
import subprocess
import tempfile
import time
from pathlib import Path

# Resolve paths relative to this file, so it works no matter where you run it from
SCRIPT_DIR = Path(__file__).parent.resolve()
PROJECT_ROOT = SCRIPT_DIR.parent
TASKS_DIR = SCRIPT_DIR / "tasks"
RESULTS_DIR = SCRIPT_DIR / "results"

MODELS = [
    "openai/gpt-oss-20b:free",
    "nvidia/nemotron-3-nano-30b-a3b:free",
    # add more specific ":free" model IDs here once you find ones that
    # reliably support tool calling on OpenRouter, e.g.:
    # "openai/gpt-oss-20b:free",
]
RUNS_PER_TASK = 3


def load_tasks() -> list[dict]:
    tasks = []
    for task_dir in sorted(TASKS_DIR.iterdir()):
        if not task_dir.is_dir():
            continue
        task_json = task_dir / "task.json"
        if not task_json.exists():
            continue
        with open(task_json) as f:
            meta = json.load(f)
        meta["task_dir"] = str(task_dir)
        tasks.append(meta)
    return tasks


def run_single(task: dict, model: str, run_index: int) -> dict:
    with tempfile.TemporaryDirectory() as tmp:
        setup_src = Path(task["task_dir"]) / "setup"
        work_dir = Path(tmp) / "calculator"
        shutil.copytree(setup_src, work_dir)

        env = os.environ.copy()
        env["AGENT_WORKING_DIR"] = str(work_dir)

        logs_before = set((PROJECT_ROOT / "logs").glob("*.json")) if (PROJECT_ROOT / "logs").exists() else set()

        start = time.time()
        try:
            agent_result = subprocess.run(
                ["uv", "run", "main.py", task["prompt"], "--model", model],
                cwd=str(PROJECT_ROOT),
                env=env,
                capture_output=True,
                text=True,
                timeout=120,
            )
            agent_stdout = agent_result.stdout
            agent_timed_out = False
        except subprocess.TimeoutExpired as e:
            agent_stdout = (e.stdout or "") + "\n[TIMED OUT]"
            agent_timed_out = True

        agent_result_returncode = agent_result.returncode if not agent_timed_out else None
        duration = time.time() - start

        # Find the log file this run just wrote, to pull tool_calls/iterations
        logs_after = set((PROJECT_ROOT / "logs").glob("*.json")) if (PROJECT_ROOT / "logs").exists() else set()
        new_logs = logs_after - logs_before
        num_tool_calls = 0
        num_iterations = 0
        tool_call_names = []
        if new_logs:
            newest_log = max(new_logs, key=lambda p: p.stat().st_mtime)
            with open(newest_log) as f:
                agent_log = json.load(f)
            tool_call_names = agent_log.get("tool_calls", [])
            num_tool_calls = len(tool_call_names)
            num_iterations = agent_log.get("num_iterations", 0)

        verify_script = Path(task["task_dir"]) / "verify.py"
        verify_result = subprocess.run(
            ["python3", str(verify_script), str(work_dir)],
            capture_output=True,
            text=True,
        )
        passed = (not agent_timed_out) and verify_result.returncode == 0

        if agent_result_returncode == 2:
            outcome = "api_error"
        elif passed:
            outcome = "passed"
        elif num_tool_calls == 0:
            outcome = "no_attempt"
        elif "write_file" not in tool_call_names:
            outcome = "diagnosed_but_not_executed"
        else:
            outcome = "attempted_but_failed"

        return {
            "task_id": task["task_id"],
            "difficulty": task.get("difficulty", "unknown"),
            "model": model,
            "run_index": run_index,
            "passed": passed,
            "outcome": outcome,
            "timed_out": agent_timed_out,
            "num_tool_calls": num_tool_calls,
            "num_iterations": num_iterations,
            "tool_calls": tool_call_names,
            "duration_seconds": round(duration, 2),
            "agent_stdout_tail": agent_stdout[-2000:],
        }


def main():
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    tasks = load_tasks()

    if not tasks:
        print(f"No tasks found in {TASKS_DIR}")
        return

    all_results = []

    for task in tasks:
        for model in MODELS:
            for run_index in range(RUNS_PER_TASK):
                print(f"Running {task['task_id']} | {model} | run {run_index + 1}/{RUNS_PER_TASK}")
                result = run_single(task, model, run_index)
                all_results.append(result)
                status = "PASS" if result["passed"] else "FAIL"
                print(f"  -> {status} ({result['duration_seconds']}s)")

    out_path = RESULTS_DIR / f"benchmark_{int(time.time())}.json"
    with open(out_path, "w") as f:
        json.dump(all_results, f, indent=2)

    print(f"\nSaved {len(all_results)} results to {out_path}")


if __name__ == "__main__":
    main()
