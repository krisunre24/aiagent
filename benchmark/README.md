# Scout Benchmark: Does a Stricter System Prompt Actually Help?

A controlled experiment testing whether an explicit "you MUST call write_file"
instruction improves an LLM coding agent's task completion rate — and whether
that effect (if any) holds across different kinds of coding tasks.

## TL;DR

A stricter system prompt had **no measurable effect on tasks the model could
already reliably solve, and no effect on a task it consistently failed** — its
only measurable impact was a small reliability gain (88% → 100% pass rate) on
one borderline-difficulty task, at the cost of ~30% more time per run. An
earlier single-task version of this experiment suggested the stricter prompt
*halved* the pass rate; that result did not replicate once a second task was
added as a control, and turned out to be specific to one task rather than a
general effect of the prompt.

## Background

While testing Scout on a bug-fix task, I noticed a failure mode: the model
would correctly diagnose a bug and even describe a correct fix in its final
response — without ever calling `write_file` to actually persist it. I called
this `diagnosed_but_not_executed` in the benchmark harness. The obvious fix
seemed to be telling the model, explicitly, that it must call `write_file` or
the task isn't complete. Rather than assume that helped, I measured it — and
the first version of that measurement turned out to be misleading, for
reasons explained below.

## Method

**Tasks** (increasing difficulty, verified by running the app's own tests or
checking real command output — not by inspecting the model's response text):

| Task | Type | Description |
|---|---|---|
| `fix_division_by_zero` | easy | Dividing by zero crashes with a traceback instead of a clean error |
| `fix_operator_precedence` | medium | `+` has an incorrectly high precedence value, breaking order of operations |
| `add_modulo_operator` | hard | The `%` operator isn't supported at all — requires adding a new operator, not fixing an existing one |

**Model**: `openai/gpt-oss-20b:free`, pinned explicitly (not routed through
`openrouter/free`) to eliminate model-selection variance as a confound —
OpenRouter's free router silently picks a different underlying model per
request, which would otherwise be indistinguishable from a real prompt effect.

**Conditions**: identical tasks and model, only the system prompt changed.
- *Before*: a minimal prompt listing available operations.
- *After*: the same prompt, plus an explicit instruction that `write_file`
  must be called to complete the task, and that describing a fix without
  executing it doesn't count as done.

**n = 8 runs per task per condition** (48 total runs), since LLM outputs are
non-deterministic even at `temperature=0` with tool calling involved.

## Results

| Task | Before (pass rate / mean duration) | After (pass rate / mean duration) |
|---|---|---|
| `fix_division_by_zero` | 100% (8/8) / 23.6s | 100% (8/8) / 14.8s |
| `fix_operator_precedence` | 88% (7/8) / 66.3s | 100% (8/8) / 85.9s |
| `add_modulo_operator` | 0% (0/8) / 15.6s | 0% (0/8) / 28.3s |

## Interpretation

The stricter prompt's effect depends entirely on task difficulty:

- **Tasks the model already solves reliably** (`fix_division_by_zero`) were
  unaffected — no ceiling left to raise.
- **Tasks the model fundamentally cannot do** (`add_modulo_operator`) were
  also unaffected. On this task the model consistently investigated just
  enough to see the codebase exists (2 tool calls, ~100 completion tokens),
  then produced an empty final response — 8/8 times, before *and* after the
  prompt change, with near-identical behavior. Telling the model more
  forcefully to finish the job doesn't help when it doesn't seem to know
  *what* the job requires in the first place — this looks like an open-ended
  feature-addition task exceeding the model's ability to plan a multi-step
  change, not a compliance problem the prompt could fix.
- **The one task where the prompt mattered** (`fix_operator_precedence`) sits
  in between: hard enough to fail sometimes, easy enough to be solvable. Here
  the stricter prompt raised pass rate from 88% to 100%, but cost ~30% more
  time per run — plausibly because the added verification instructions led
  to more careful (and slower) checking before finishing.

**An earlier, single-task version of this experiment** (testing only
`fix_operator_precedence` in isolation, n=8 per condition) showed pass rate
dropping from 100% to 50% after the same prompt change — the opposite
direction of the result above. That run turned out to be an outlier: a
follow-up run on the same single task, same model, same prompts, produced
88% → 100%, consistent with the three-task result here. This is the reason
the benchmark now runs multiple tasks and treats single-task results as
provisional until they replicate — a stark reminder that n=8 on one task
isn't enough to trust a single measurement, especially with free-tier model
inference that has its own variance independent of anything being tested.

## Multi-model comparison

Expanded the task suite to 5 tasks (3 bug-fixes, 2 feature-additions) and ran
both through 2 models with clean, usable data (`google/gemma-4-31b-it:free`
was dropped entirely in an earlier round — every request to it failed with a
429 from Google AI Studio's shared free pool, unrelated to this benchmark).

| Model | Task | Type | Pass Rate |
|---|---|---|---|
| `gpt-oss-20b` | fix_division_by_zero | bugfix | 5/5 (100%) |
| `gpt-oss-20b` | fix_operator_precedence | bugfix | 4/5 (80%) |
| `gpt-oss-20b` | fix_float_precision_display | bugfix | 0/5 (0%) |
| `gpt-oss-20b` | add_modulo_operator | feature | 0/5 (0%) |
| `gpt-oss-20b` | add_power_operator | feature | 0/5 (0%) |
| `nemotron-3-nano` | fix_division_by_zero | bugfix | 5/5 (100%) |
| `nemotron-3-nano` | fix_operator_precedence | bugfix | 4/5 (80%) |
| `nemotron-3-nano` | fix_float_precision_display | bugfix | 2/5 (40%) |
| `nemotron-3-nano` | add_modulo_operator | feature | 2/5 (40%) |
| `nemotron-3-nano` | add_power_operator | feature | 3/5 (60%) |

**Aggregate, both models combined, n=50:**

| Task type | Pass rate |
|---|---|
| Bug-fix | 67% (20/30) |
| Feature-addition | 25% (5/20) |

**Findings:**

- The bug-fix vs. feature-addition gap held up and strengthened with more
  data: 67% vs 25% pooled across both models and all 5 tasks, up from the
  earlier 3-task, single-model observation. This is now the most robust
  finding in this benchmark.
- The size of the gap between the two models varies by task rather than
  being uniform — `nemotron-3-nano` clearly outperformed `gpt-oss-20b` on
  `fix_float_precision_display` (40% vs 0%) and both feature tasks, while
  the two were roughly tied or `gpt-oss-20b` slightly ahead on the other two
  bug-fix tasks. Neither model is straightforwardly "better" across the
  board — the honest summary is that `nemotron-3-nano` has a wider range of
  tasks it can handle at all, not that it's more accurate on tasks both
  models attempt.
- `fix_float_precision_display` (0% for `gpt-oss-20b`, 40% for
  `nemotron-3-nano`) turned out to be harder than expected for a task
  classified "easy" — floating-point display formatting appears to be a
  genuine blind spot for both models, worth investigating further as its own
  category rather than assuming difficulty labels transfer cleanly.

## Measuring code quality

Added two tools beyond the original four: `run_linter` (runs `ruff` against
the working directory) and `git_diff` (shows the size/scope of the agent's
own changes so far). Each benchmark trial's working directory is now
initialized as its own isolated git repo with a committed baseline before
the agent runs, so `git diff --stat` always reflects only the agent's
changes for that trial.

**Finding: when this agent writes code, it writes small, focused changes.**
Across 12 runs where the agent actually called `write_file` (excluding the
much larger number of runs where it gave up or only described a fix without
executing it), diffs ranged from 2 to 9 lines, and 11 of 12 (92%) passed
verification. The one failure was not a bloated or careless edit — it was a
normally-sized 5-line change that simply didn't produce a correct fix.

This reframes where the agent's real bottleneck is. It isn't "the agent
makes messy, over-broad changes that break things" — the changes it commits
to are almost always small and appropriately scoped. The bottleneck is
upstream: whether the agent decides to act at all. This is consistent with,
and cross-validates, the `diagnosed_but_not_executed` finding from the
prompt experiment above — of the 44 clean runs analyzed here, 32 made no
file change whatsoever (correctly reflected as an empty `git diff`), most of
them cases where the agent investigated the code but stopped short of
writing the fix.

**A known limitation surfaced during this work**: compiled `.pyc` files in
`pkg/__pycache__/` were committed as part of each task's baseline and show
up as noise in every diff (e.g. `calculator.cpython-313.pyc | Bin 3412 ->
3479 bytes`). This doesn't affect the line-count analysis above, but a
cleaner setup would `.gitignore` `__pycache__/` inside each task's baseline
commit.

**Infrastructure note**: getting reliable process-group timeouts for a
`uv run` subprocess (which spawns its own child processes) took several
iterations — a naive `subprocess.run(timeout=...)` did not reliably kill the
full process tree, occasionally allowing a run to hang for hours instead of
the intended 120-second cap. The fix was switching to `Popen` with
`start_new_session=True` and explicitly `SIGKILL`-ing the process group on
timeout, with a secondary bounded wait on output capture in case pipes stay
open after the kill. One outlier (666s) still occurred in the final run
and was excluded from analysis rather than silently kept — a reminder that
subprocess timeout handling on systems with nested process trees is harder
to get fully right than it looks, even after fixing it once.

## Does the agent generalize beyond hand-picked tasks?

All tasks so far were hand-written by me. That raises an obvious question:
was the agent actually good at "bug-fixing" as a general capability, or just
good at the specific five bugs I happened to write tasks for?

To test this, I wrote a small mutation engine (`benchmark/mutate.py`) that
takes the known-correct calculator and applies small, targeted mutations to
`pkg/calculator.py` — swapping an operator, flipping a comparison — and
automatically discards any mutation that doesn't actually break the existing
test suite. This produces genuinely novel bugs with zero hand-authored task
logic, verified the same way as every other task: does the original test
suite pass again after the agent's fix.

Five mutations survived verification (one was discarded — a mutation that
only broke indentation, producing a `SyntaxError` rather than a logic bug,
which tests something fundamentally different and was excluded).

**First pass, using a generic prompt** ("the test suite is failing,
investigate and fix it"), n=25 clean runs across both models:

| Prompt type | Pass rate |
|---|---|
| Generic ("tests are failing, fix it") | 28% (7/25) |

This was a large, concerning drop from the 67% pooled pass rate on the
hand-written bug-fix tasks. Before concluding the agent simply can't handle
novel bugs, I checked for a confound: my hand-written tasks all gave a
concrete failing example in the prompt (e.g. "3 + 7 * 2 shouldn't be 20"),
while the auto-generated mutant tasks used a generic, example-free prompt.
That's a real, uncontrolled difference between the two task sets.

**Second pass**: extended the mutator to auto-derive a concrete example for
each mutation (by probing the mutated code against a handful of test
expressions until one produced a wrong, non-crashing result), then re-ran
the same five mutant bugs with that specific prompt instead:

| Prompt type | Pass rate |
|---|---|
| Generic ("tests are failing, fix it") | 28% (7/25) |
| Specific (concrete failing example given) | 39% (11/28) |

**Conclusion**: prompt specificity is a real, measurable factor — an
11-point improvement from giving a concrete example instead of a vague
description — but it does not close the gap to the hand-written tasks'
67%. Even with a comparably concrete prompt, genuinely novel bugs (bugs the
task set wasn't specifically built and tuned around) are meaningfully
harder for this agent than the hand-picked set suggested. The honest
takeaway: the earlier 67% figure likely overstates general bug-fixing
capability, and a fair benchmark of an agent should include
mutation-generated or otherwise unseen tasks, not just hand-curated ones —
hand-curated tasks alone can look reassuringly high without actually
measuring generalization.

## Limitations

- Small `n` per cell (8) — sufficient to see large effects, not tight enough
  for firm confidence intervals on the borderline task.
- Single model, single codebase (a small calculator app). Results may not
  generalize to other models or more complex codebases.
- No visibility into the model's internal reasoning — only tool calls and
  final text are observed, so explanations for *why* a task fails are
  inferred from behavior patterns, not confirmed directly.
- `add_modulo_operator`'s 0% pass rate may partly reflect task-prompt
  ambiguity (the task doesn't point the model at a specific file, unlike the
  bug-fix tasks which name a broken expression) rather than a pure capability
  gap — worth testing with a more specific prompt in a follow-up.

**Reproducing this:**
```bash
uv run python benchmark/mutate.py   # regenerates mutant tasks in benchmark/tasks/
# set USE_SPECIFIC_PROMPT = True/False in run_benchmark.py to pick the variant, then:
uv run python benchmark/run_benchmark.py
```

Raw results: `benchmark/results/mutant_tasks.json` (generic prompt),
`benchmark/results/mutant_tasks_specific_prompt.json` (specific prompt).
