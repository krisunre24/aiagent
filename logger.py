import json
import os
import time
from datetime import datetime, timezone


LOGS_DIR = "logs"


def start_run(task_id: str, model: str, user_prompt: str) -> dict:
    """Call this once at the start of a run. Returns a run record you'll keep updating."""
    return {
        "task_id": task_id,
        "model": model,
        "user_prompt": user_prompt,
        "tool_calls": [],
        "prompt_tokens_total": 0,
        "completion_tokens_total": 0,
        "num_iterations": 0,
        "success": None,
        "final_response": None,
        "error": None,
        "start_time": time.time(),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


def record_iteration(run: dict, prompt_tokens: int, completion_tokens: int, tool_call_names: list[str]) -> None:
    run["num_iterations"] += 1
    run["prompt_tokens_total"] += prompt_tokens
    run["completion_tokens_total"] += completion_tokens
    run["tool_calls"].extend(tool_call_names)


def finish_run(run: dict, success: bool | None, final_response: str | None = None, error: str | None = None) -> None:
    run["success"] = success
    run["final_response"] = final_response
    run["error"] = error
    run["duration_seconds"] = round(time.time() - run["start_time"], 2)
    del run["start_time"]  # not JSON-friendly-relevant, we already computed duration

    os.makedirs(LOGS_DIR, exist_ok=True)
    filename = f"{run['task_id']}_{int(time.time())}.json"
    path = os.path.join(LOGS_DIR, filename)
    with open(path, "w") as f:
        json.dump(run, f, indent=2)

    print(f"[logged run to {path}]")
