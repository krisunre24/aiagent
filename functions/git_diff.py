import os
import subprocess


def git_diff(working_directory: str) -> str:
    try:
        working_dir_abs = os.path.abspath(working_directory)

        completed_process = subprocess.run(
            ["git", "diff", "--stat"],
            cwd=working_dir_abs,
            capture_output=True,
            text=True,
            timeout=15,
        )

        if completed_process.returncode != 0:
            return f"Error: git diff failed: {completed_process.stderr}"

        output = completed_process.stdout.strip()
        if not output:
            return "No changes detected (working directory matches the initial commit)."

        return output
    except Exception as e:
        return f"Error: {e}"


schema_git_diff = {
    "type": "function",
    "function": {
        "name": "git_diff",
        "description": "Shows a summary of file changes made so far in the working directory (lines added/removed per file), useful for reviewing the size and scope of your own edits",
        "parameters": {
            "type": "object",
            "properties": {},
        },
    },
}
