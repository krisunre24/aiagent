import random
import re
import shutil
import json
import subprocess
from pathlib import Path


# Each mutator is a (pattern, replacement, description) tuple.
# Applied to pkg/calculator.py in a clean calculator copy.
MUTATIONS = [
    (r'"\+": 1,', '"+": 3,', "swap_plus_precedence"),
    (r'"-": 1,', '"-": 3,', "swap_minus_precedence"),
    (r"a \+ b", "a - b", "flip_add_to_subtract"),
    (r"a \* b", "a / b", "flip_multiply_to_divide"),
    (r">= self\.precedence\[token\]", "> self.precedence[token]", "flip_precedence_comparison"),
]


def apply_mutation(source_calculator_dir: Path, dest_dir: Path, pattern: str, replacement: str, name: str) -> bool:
    """Copy a clean calculator into dest_dir with one mutation applied.
    Returns True if the mutation pattern was found and applied, False otherwise."""
    if dest_dir.exists():
        shutil.rmtree(dest_dir)
    shutil.copytree(source_calculator_dir, dest_dir)

    calc_file = dest_dir / "pkg" / "calculator.py"
    original = calc_file.read_text()

    mutated, count = re.subn(pattern, replacement, original)
    if count == 0:
        return False

    calc_file.write_text(mutated)
    return True


def verify_mutation_breaks_tests(dest_dir: Path) -> bool:
    """A valid mutation must make the ORIGINAL test suite fail.
    If tests still pass, the mutation didn't actually break anything -- discard it."""
    result = subprocess.run(
        ["python3", "tests.py"],
        cwd=str(dest_dir),
        capture_output=True,
        text=True,
        timeout=15,
    )
    return result.returncode != 0  # True if tests now fail, as expected


def generate_mutant_tasks(source_calculator_dir: str, output_dir: str) -> list[str]:
    source = Path(source_calculator_dir)
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    created = []
    for pattern, replacement, name in MUTATIONS:
        task_dir = out / f"mutant_{name}"
        setup_dir = task_dir / "setup"

        applied = apply_mutation(source, setup_dir, pattern, replacement, name)
        if not applied:
            print(f"  SKIP {name}: pattern not found in source")
            continue

        breaks_tests = verify_mutation_breaks_tests(setup_dir)
        if not breaks_tests:
            print(f"  SKIP {name}: mutation didn't break tests, discarding")
            shutil.rmtree(task_dir)
            continue

        # Find a concrete failing example by trying the mutated main.py against a few known expressions
        example_prompt = None
        for expr in ["3 + 7 * 2", "10 - 2 * 3", "5 + 3", "6 * 2", "10 - 3 - 2"]:
            probe = subprocess.run(
                ["python3", "main.py", expr],
                cwd=str(setup_dir),
                capture_output=True,
                text=True,
                timeout=10,
            )
            if probe.returncode == 0 and '"result"' in probe.stdout:
                # confirm this differs from the correct calculator's answer
                correct = subprocess.run(
                    ["python3", "main.py", expr],
                    cwd=str(source),
                    capture_output=True,
                    text=True,
                    timeout=10,
                )
                if probe.stdout != correct.stdout:
                    import re as re_module
                    match = re_module.search(r'"result": ([-\d.]+)', probe.stdout)
                    if match:
                        example_prompt = f"Fix the bug: {expr} shouldn't be {match.group(1)}."
                        break

        task_json = task_dir / "task.json"
        generic_prompt = "The test suite is failing. Investigate and fix the bug in the calculator so all tests pass again."
        task_json.write_text(json.dumps({
            "task_id": f"mutant_{name}",
            "difficulty": "mutant",
            "prompt": generic_prompt,
            "specific_prompt": example_prompt,  # may be None if no probe expression triggered the bug
        }, indent=2) + "\n")

        verify_py = task_dir / "verify.py"
        verify_py.write_text(
            "import subprocess\nimport sys\n\n\n"
            "def verify(task_dir: str) -> bool:\n"
            "    result = subprocess.run(\n"
            '        ["python3", "tests.py"],\n'
            "        cwd=task_dir,\n"
            "        capture_output=True,\n"
            "        text=True,\n"
            "        timeout=30,\n"
            "    )\n"
            "    return result.returncode == 0\n\n\n"
            'if __name__ == "__main__":\n'
            "    task_dir = sys.argv[1]\n"
            "    success = verify(task_dir)\n"
            '    print("PASS" if success else "FAIL")\n'
            "    sys.exit(0 if success else 1)\n"
        )

        print(f"  CREATED mutant_{name}")
        created.append(f"mutant_{name}")

    return created


if __name__ == "__main__":
    print("Generating mutant tasks...")
    created = generate_mutant_tasks("calculator", "benchmark/tasks")
    print(f"\nCreated {len(created)} mutant tasks: {created}")
