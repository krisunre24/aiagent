import subprocess
import sys


def verify(task_dir: str) -> bool:
    result = subprocess.run(
        ["python3", "main.py", "5 / 0"],
        cwd=task_dir,
        capture_output=True,
        text=True,
        timeout=15,
    )
    # Should not crash (non-zero exit or traceback), and should mention "Error"
    if result.returncode != 0:
        return False
    if "Traceback" in result.stderr:
        return False
    if "Error" not in result.stdout:
        return False
    return True


if __name__ == "__main__":
    task_dir = sys.argv[1]
    success = verify(task_dir)
    print("PASS" if success else "FAIL")
    sys.exit(0 if success else 1)
