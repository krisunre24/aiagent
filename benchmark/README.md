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

Ran the same three-task suite through two pinned models to see whether the
task-difficulty pattern found above (easy fixes: reliable, feature additions:
unreliable) holds across models, or is specific to `openai/gpt-oss-20b:free`.

A third model, `google/gemma-4-31b-it:free`, was excluded entirely — every
single request to it returned a 429 from Google AI Studio's shared free pool
(`upstream_provider_shared_pool`), unrelated to anything in this benchmark.
This is itself worth noting: different free models on OpenRouter draw from
different upstream providers with independently varying availability, and a
fair comparison has to detect and exclude this noise rather than let it
silently distort pass rates.

| Model | Task | Pass Rate | Mean Duration |
|---|---|---|---|
| `openai/gpt-oss-20b:free` | add_modulo_operator | 1/8 (12%) | 44.1s |
| `openai/gpt-oss-20b:free` | fix_division_by_zero | 6/7 (86%) | 35.3s |
| `openai/gpt-oss-20b:free` | fix_operator_precedence | n=1 — insufficient data (7/8 attempts hit provider rate limits) | — |
| `nvidia/nemotron-3-nano-30b-a3b:free` | add_modulo_operator | 2/8 (25%) | 19.3s |
| `nvidia/nemotron-3-nano-30b-a3b:free` | fix_division_by_zero | 8/8 (100%) | 52.0s |
| `nvidia/nemotron-3-nano-30b-a3b:free` | fix_operator_precedence | 6/8 (75%) | 37.7s |

**Findings:**

- `nemotron-3-nano` outperformed `gpt-oss-20b` on every task with usable
  data, most clearly on the easy task (100% vs 86%).
- The task-difficulty pattern replicated across both models: neither
  reliably solved the feature-addition task (`add_modulo_operator`, 12% and
  25%), while both handled at least one bug-fix task well. This suggests the
  bug-fix vs. feature-addition distinction found earlier is a property of
  small free-tier models generally, not an artifact of one specific model.
- Free-tier model comparisons need to account for provider-level rate
  limiting as a real confound, separate from task difficulty or prompt
  design — `api_error` outcomes were explicitly filtered out of pass-rate
  calculations above rather than counted as failures, and cells with too few
  clean samples (n=1) are reported as insufficient rather than as a rate.

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

## Reproducing this

```bash
# Before condition: use the minimal prompt in prompts.py, then:
uv run python benchmark/run_benchmark.py

# After condition: swap in the stricter prompt (see prompts.py comments), then run again
```

Raw results: `benchmark/results/three_tasks_before_prompt_fix.json`,
`benchmark/results/three_tasks_after_prompt_fix.json`
