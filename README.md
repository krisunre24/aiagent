# Scout

A small, sandboxed AI coding agent — point it at a directory and a task, and it reads files, edits code, runs tests, and reports back, using nothing but a free LLM API and four hand-written tool functions.

## What is this?

Scout is a command-line agent, similar in spirit to Claude Code or Cursor's agent mode, built from scratch on top of the OpenRouter API. Give it a task in plain English — "fix the bug where addition and multiplication are evaluated in the wrong order" — and it decides for itself which of four tools to call (list files, read a file, write a file, run a Python file), executes them in a loop, and keeps going until it has a final answer, all while being strictly confined to one working directory.

## Why I built it

I use agentic coding tools daily, but "the model decides what to call, and then we call it" always felt a bit like magic from the outside. Building one myself — writing the JSON tool schemas by hand, wiring up the request/response loop, and watching the model actually choose `get_file_content` before `write_file` on its own — made the whole idea click in a way that using someone else's agent never did. Testing it by intentionally breaking a small calculator app's operator precedence, then asking Scout to fix it with zero hints, and watching it read the code, spot the bug, patch it, and verify the fix by running the tests itself, was the first time an "AI agent" felt like a system I understood rather than a black box I trusted.

## 🚀 Quick Start

### 1. Set up your environment

```bash
uv venv
source .venv/bin/activate
uv add openai==2.44.0 python-dotenv==1.1.0
```

### 2. Add your OpenRouter API key

Get a free key at [openrouter.ai](https://openrouter.ai/keys), then create a `.env` file in the project root:
OPENROUTER_API_KEY='your_key_here'

`.env` is already git-ignored — never commit your key.

### 3. Run it

```bash
uv run main.py "list the files in the calculator directory"
```

## 📖 Usage

```bash
uv run main.py "<your task here>" [--verbose]
```

- `--verbose` — prints the user prompt, token counts for each request, and the full result of every tool call the agent makes

### What Scout can do, within its sandboxed working directory

| Tool | What it does |
|---|---|
| `get_files_info` | List files and subdirectories, with sizes |
| `get_file_content` | Read a file's contents (truncated past 10,000 characters) |
| `write_file` | Create or overwrite a file |
| `run_python_file` | Execute a Python file with optional arguments, 30-second timeout |

### Example: autonomous bug fix

```bash
uv run main.py "fix the bug: 3 + 7 * 2 shouldn't be 20" --verbose
```

User prompt: fix the bug: 3 + 7 * 2 shouldn't be 20
Calling function: get_files_info
Calling function: get_file_content
Calling function: get_files_info
Calling function: get_file_content
Calling function: write_file
Calling function: run_python_file
Final response:
I've fixed the bug in the calculator. The issue was in the precedence
dictionary in pkg/calculator.py, where the "+" operator had a precedence
value of 3 instead of 1. I corrected it and verified the fix by running
several test expressions — 3 + 7 * 2 now correctly returns 17.

## 🔒 Safety

Every tool call is validated against the working directory before it runs — Scout can't read, write, or execute anything outside the sandbox, no matter how it's asked. It's still an agent that can execute arbitrary Python within that sandbox, so treat the working directory the same way you'd treat any other code you let an unattended script run against.

## 📊 Benchmark: does prompt engineering actually help?

I built a small evaluation harness to test Scout against a suite of coding tasks, across multiple runs, and measured whether a stricter system prompt actually improved task completion — rather than assuming it did.

**Result**: the effect depended entirely on task difficulty. No change on tasks the model already solved reliably, no change on a task it consistently couldn't solve, and a modest reliability gain (88% → 100%) at the cost of ~30% more time on the one task in between.

Full write-up, methodology, and raw results: [`benchmark/README.md`](./benchmark/README.md)
