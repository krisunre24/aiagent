import os
import subprocess


def run_linter(working_directory: str, file_path: str = ".") -> str:
    try:
        working_dir_abs = os.path.abspath(working_directory)
        target = os.path.normpath(os.path.join(working_dir_abs, file_path))

        valid_target = os.path.commonpath([working_dir_abs, target]) == working_dir_abs
        if not valid_target:
            return f'Error: Cannot lint "{file_path}" as it is outside the permitted working directory'

        completed_process = subprocess.run(
            ["ruff", "check", target, "--output-format=concise"],
            capture_output=True,
            text=True,
            timeout=30,
        )

        output = completed_process.stdout.strip()
        if not output:
            return "No lint issues found."

        num_issues = len(output.splitlines())
        return f"Found {num_issues} lint issue(s):\n{output}"
    except FileNotFoundError:
        return "Error: ruff is not installed. Install it with 'pip install ruff' or 'uv add ruff'."
    except Exception as e:
        return f"Error: {e}"


schema_run_linter = {
    "type": "function",
    "function": {
        "name": "run_linter",
        "description": "Runs a Python linter (ruff) against a file or directory, relative to the working directory, and reports any code quality issues found",
        "parameters": {
            "type": "object",
            "properties": {
                "file_path": {
                    "type": "string",
                    "description": "Path to the file or directory to lint, relative to the working directory (defaults to the whole working directory)",
                },
            },
        },
    },
}
