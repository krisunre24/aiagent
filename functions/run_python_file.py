import os
import subprocess


def run_python_file(
    working_directory: str, file_path: str, args: list[str] | None = None
) -> str:
    try:
        working_dir_abs = os.path.abspath(working_directory)
        target_file = os.path.normpath(os.path.join(working_dir_abs, file_path))

        valid_target = os.path.commonpath([working_dir_abs, target_file]) == working_dir_abs
        if not valid_target:
            return f'Error: Cannot execute "{file_path}" as it is outside the permitted working directory'

        if not os.path.isfile(target_file):
            return f'Error: "{file_path}" does not exist or is not a regular file'

        if not file_path.endswith(".py"):
            return f'Error: "{file_path}" is not a Python file'

        command = ["python", target_file]
        if args:
            command.extend(args)

        completed_process = subprocess.run(
            command,
            cwd=working_dir_abs,
            capture_output=True,
            text=True,
            timeout=30,
        )

        output_parts = []
        if completed_process.stdout:
            output_parts.append(f"STDOUT: {completed_process.stdout}")
        if completed_process.stderr:
            output_parts.append(f"STDERR: {completed_process.stderr}")
        if completed_process.returncode != 0:
            output_parts.append(f"Process exited with code {completed_process.returncode}")
        if not output_parts:
            return "No output produced"

        return "\n".join(output_parts)
    except Exception as e:
        return f"Error: executing Python file: {e}"

schema_run_python_file = {
    "type": "function",
    "function": {
        "name": "run_python_file",
        "description": "Executes a Python file with optional command-line arguments, relative to the working directory, with a 30-second timeout",
        "parameters": {
            "type": "object",
            "properties": {
                "file_path": {
                    "type": "string",
                    "description": "Path to the Python file to execute, relative to the working directory",
                },
                "args": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Optional list of command-line arguments to pass to the script",
                },
            },
            "required": ["file_path"],
        },
    },
}
