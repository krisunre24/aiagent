import subprocess
import sys


def verify(task_dir: str) -> bool:
    result = subprocess.run(
        ["python3", "tests.py"],
        cwd=task_dir,
        capture_output=True,
        text=True,
        timeout=30,
    )
    return result.returncode == 0


if __name__ == "__main__":
    task_dir = sys.argv[1]
    success = verify(task_dir)
    print("PASS" if success else "FAIL")
    sys.exit(0 if success else 1)
