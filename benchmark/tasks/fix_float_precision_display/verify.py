import subprocess
import sys


def verify(task_dir: str) -> bool:
    result = subprocess.run(
        ["python3", "main.py", "10 / 3"],
        cwd=task_dir,
        capture_output=True,
        text=True,
        timeout=15,
    )
    if result.returncode != 0:
        return False
    # The raw unrounded value should no longer appear in the output
    if "3.3333333333333335" in result.stdout:
        return False
    # And a sane, rounded value should be present
    if "3.333" not in result.stdout:
        return False
    return True


if __name__ == "__main__":
    task_dir = sys.argv[1]
    success = verify(task_dir)
    print("PASS" if success else "FAIL")
    sys.exit(0 if success else 1)
