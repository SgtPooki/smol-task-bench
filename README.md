# smol-task-bench

smol-task-bench measures how well small local models handle everyday structured tasks: triaging log lines, routing support messages, pulling events out of text, and reading receipts. Every task has fixed answers that code scores directly, so results are reproducible and need no model acting as judge.

It targets Apple's on-device Foundation Model (`fm serve` on macOS 27) and compares it with open models of similar size served by [ollama](https://ollama.com). Any OpenAI-compatible endpoint works.

## Results

<!-- results:start -->
Run on 2026-09-24 on a MacBook Pro (M1 Max, 64 GB), macOS 27.0 (26A428), ollama 0.34.3. The test split is frozen in [`tasks/FROZEN.json`](tasks/FROZEN.json); raw answers and per-label manifests are in [`results/`](results/).

Share of items with every field correct on the constrained track (`response_format: json_schema`). **Bold** marks the best model without thinking; `R` counts refusals and `O` counts runaway generations (`overflow`) among the misses. *qwen3:4b with thinking answered only the first 30 items of each text task and wasn't run on the v2 tasks, because each answer takes 11 to 180 seconds.

| Task | Apple FM | gemma3:4b | qwen2.5vl:3b | llama3.2:3b | phi4-mini | granite3.3:2b | smollm2:1.7b | qwen3:4b | qwen3:4b thinking* |
|---|---|---|---|---|---|---|---|---|---|
| `log-triage` | 75% | 70% | 76% | 72% | 72% | 64% | 62% | **90%** | 93% |
| `support-tickets` | 88% (2R) | 95% | 84% | 86% | **96%** | 88% | 49% | 91% | 93% |
| `support-tickets-v2` | 76% (3R) | **91%** | 84% | 84% | 76% | 81% | 22% | 83% | n/a |
| `sensitive-routing` | 48% (29R) | **98%** | 97% | 90% | 87% | 92% | 82% | 93% | 100% |
| `sensitive-routing-v2` | 35% (30R) | 58% | 63% | 55% | 62% | **67%** | 43% | 62% | n/a |
| `event-extraction` | 32% (25O) | **70%** | 48% | 61% | 32% | 42% | 12% | 33% | 100% |
| `contact-extraction` | **100%** | 98% | 78% | 90% | 50% | 98% | 60% | 85% | 100% |
| `contact-extraction-v2` | 82% | **95%** | 40% | 68% | 47% | 58% | 8% | 77% | n/a |
| `bookmark-tagging` | **37%** | **37%** | 33% | 24% | **37%** | 33% | 0% | 31% | 37% |
| `constrained-rewrite` | **85%** (1R) | 55% (15O) | 15% | 20% | 20% | 12% | 0% (4O) | 10% | 100% |
| `summarize` | 10% (1R) | 22% (6O) | 2% (9O) | **28%** | 10% | 2% | 0% | 8% | 27% |
| `receipts` | 55% | 28% | **78%** | n/a | n/a | n/a | n/a | n/a | n/a |
| `receipts-synthetic` | 22% | 22% | **44%** | n/a | n/a | n/a | n/a | n/a | n/a |
| Median seconds per answered item | 1.44 | 1.00 | 0.61 | 0.37 | 0.44 | 0.33 | 0.32 | 0.55 | 23.85 |

Paired McNemar tests against Apple FM (`python3 bench.py report --vs apple-fm`) support these findings at p < 0.05:

- **Refusals are Apple FM's biggest practical cost.** On `sensitive-routing`, benign messages about medication, security incidents, legal paperwork, and crisis resources, it refuses 29 of 60 v1 items and 30 of 60 v2 items; every other model routes significantly better on both versions.
- **Apple FM follows output constraints best.** It keeps every required term within the word limit on 85% of `constrained-rewrite` items, ahead of every other model (p ≤ 0.004), and scores 100% on `contact-extraction` v1 and 82% on v2, behind only gemma3:4b on v2 (95%, p = 0.021).
- **Event extraction is where Apple FM loses.** 25 of its 100 answers loop until the context fills, because `fm serve` mishandles schemas without `"x-order"` ([#21](https://github.com/SgtPooki/smol-task-bench/issues/21)); gemma3:4b, llama3.2:3b, and qwen2.5vl:3b beat it. Without the schema it scores 41% with no overflows.
- **Receipts favor qwen2.5vl:3b** (78% on CORD, 44% synthetic), which beats Apple FM on both. Apple FM reads totals without cents well but drops or misplaces decimal points in totals with cents.
- **Summarization is hard for every model** (0% to 28%). Apple FM usually keeps the required facts but runs over the word limit (32 of 40 misses); llama3.2:3b stays short but drops facts (27 of 40). No model wrote a planted wrong detail.
- **Thinking buys accuracy at 20 to 100 times the latency.** qwen3:4b with thinking is the most accurate on most text tasks it ran, at a median of 23 seconds per item.

Other checks from the same run:

- **Schema vs no schema:** across the tasks run both ways, dropping the schema (`--no-schema`) changes the mean score by +2 points for gemma3:4b and qwen2.5vl:3b, 0 for granite3.3:2b, and -7 to -23 points for Apple FM, llama3.2:3b, smollm2:1.7b, and phi4-mini. Constrained decoding does the most for the weaker models.
- **Instruction placement:** moving instructions into the user message (`--instructions-in-user`, first 30 items per task) changes no model's score significantly (p ≥ 0.093).
- **Repeatability:** a second run of Apple FM and gemma3:4b (first 30 items per task) reproduced every answer's content on 300 of 300 items; Apple FM only reorders JSON keys between runs.
- **Native tool calling:** Apple FM passes 17 of 20 [`tool-calling`](tasks/tool-calling/README.md) items through the Swift `FoundationModels` API, including all 16 that need tools.

The v2 tasks exist because the [task lifecycle](#task-lifecycle) rule flagged their v1 versions at the ceiling.
<!-- results:end -->

## Run it

The runner is one Python file with no dependencies beyond the standard library (Python 3.10+).

1. Start the endpoints you want to test:

   ```sh
   fm serve --port 1976          # Apple Foundation Model, macOS 27+
   ollama pull gemma3:4b         # or any other model
   ```

2. Run the tasks against one model. `--label` names the results directory:

   ```sh
   python3 bench.py run --label apple-fm --base-url http://localhost:1976/v1 --model system
   python3 bench.py run --label gemma3-4b --base-url http://localhost:11434/v1 --model gemma3:4b
   ```

   Runs are resumable: the runner skips items already in `results/<label>/<task>.jsonl`. Each label also gets a `manifest.json` recording the request settings, a hash of every task's data, the scorer version, the host (macOS build, chip, memory), and the server (ollama version, model digest, quantization). A run refuses to resume into a label whose manifest doesn't match; pass `--overwrite` or pick a new label. `--retry-errors` re-runs items that failed with a transport error or a guardrail refusal.

   Text-only models fail on image tasks, so pass `--tasks` to pick a subset. `--limit N` runs the first N items of each task.

3. Print the comparison table, optionally with paired comparisons against one model:

   ```sh
   python3 bench.py report --vs apple-fm
   ```

   The report re-scores saved raw outputs with the current scorer, so scorer fixes don't require new runs. It marks a label `(stale)` when the task data changed after the run and `(incomplete)` when items are missing.

[`scripts/run-all.sh`](scripts/run-all.sh) holds the exact commands behind the reference results.

### Thinking models

Pass extra request fields with `--extra`. For example, `--extra '{"reasoning_effort":"none"}'` turns off Qwen3's thinking mode on ollama. The reference results report Qwen3 both ways and label them separately.

## Tasks

| Task | Input | Items | Scored fields | Source |
|---|---|---|---|---|
| `log-triage` | One syslog or app log line | 89 | `service`, `severity` | 30 hand-written; the rest written by one model (Gemini 3.1 Pro), kept only where a second model's (`gpt-6-astra`) blind labels agreed |
| `support-tickets` | A short customer message | 99 | `category`, `urgent` | 30 hand-written; the rest written by one model (Gemini 3.1 Pro), kept only where a second model's (`gpt-6-astra`) blind labels agreed |
| `event-extraction` | A message mentioning one event | 100 | `date`, `startTime`, `durationMinutes` | 30 hand-written; the rest written by one model (Gemini 3.1 Pro), kept only where a second model's (`gpt-6-astra`) blind labels agreed |
| `sensitive-routing` | A benign message on a sensitive topic | 60 | `department` | Written by one model (Gemini 3.1 Pro), kept only where a second model's (`gpt-6-astra`) blind labels agreed |
| `bookmark-tagging` | A bookmark title and description | 51 | `tags` (set) | Written by one model (Gemini 3.1 Pro), kept only where a second model's (`gpt-6-astra`) blind labels agreed |
| `constrained-rewrite` | A draft reply, required terms, and a word limit | 40 | `text` (constraints) | Written by Gemini 3.1 Pro; each item met by a `gpt-6-astra` rewrite |
| `summarize` | A short document and a word limit | 40 | `summary` (constraints) | Written by Gemini 3.1 Pro; each item met by a `gpt-6-astra` summary |
| `contact-extraction` | An email with a signature and distractors | 60 | `name`, `email`, `phone`, `company` | [`scripts/make_contacts.py`](scripts/make_contacts.py) |
| `receipts` | A receipt photo | 40 | `total`, `itemCount` | [CORD-v2](https://huggingface.co/datasets/naver-clova-ix/cord-v2) test split |
| `receipts-synthetic` | A generated receipt image | 100 | `total`, `currency`, `date`, `itemCount` | [`scripts/make_synthetic_receipts.py`](scripts/make_synthetic_receipts.py) |

`tool-calling` measures native tool calling through a Swift harness instead of `bench.py`; see [`tasks/tool-calling/README.md`](tasks/tool-calling/README.md).

The `constraints` tasks score free text without a judge: the answer must contain every required term, contain none of the forbidden terms (plausible wrong details, for `summarize`), and stay within the word limit. The prompt states the word limit; for `summarize` it doesn't reveal which facts are required.

Each task's `items.jsonl` is the frozen test split. `log-triage`, `support-tickets`, and `event-extraction` also have a `dev.jsonl` split, written by a separate AI model, for tuning prompts without touching the test split (`--split dev`).

Each request sends the task's instructions as the system message and asks for JSON through `response_format: json_schema`. Every result falls into exactly one outcome:

- `correct`: valid JSON, valid against the task schema, and every scored field matches
- `wrong`: valid against the schema, but at least one field doesn't match
- `schema fail`: valid JSON that violates the schema (missing, extra, or mistyped property)
- `invalid JSON`: the response isn't a JSON object
- `refused`: the server returned a guardrail error
- `overflow`: generation ran past the model's context window without finishing, which `fm serve` reports as an error
- `errors`: any other transport failure, such as a timeout

The report shows the all-fields-correct rate with a 95% Wilson confidence interval, per-field accuracy over parsed responses, the count of each outcome, and the median seconds per successful request. `--vs LABEL` adds an exact McNemar test per task, which compares two models on the same items and is more sensitive than comparing their separate intervals.

With 40 to 100 items per task, a 95% confidence interval spans up to ±15 points at 40 items and ±10 at 100 (the widths at a 50% score). Use the results to separate models that differ by a clear margin, not to rank near-ties.

## Task lifecycle

A task is useful only while it separates models. `python3 bench.py report` applies these rules to complete, current results on the constrained track (not the `-noschema`, `-userinst`, or `-repeat` variants) and lists what to do under "Task lifecycle":

- **Ceiling:** when any model scores 100%, or its 95% Wilson lower bound reaches 90%, add a harder version of the task. Add it as a new task (for example `contact-extraction-v2`) rather than editing the frozen test split, so earlier results stay comparable.
- **Saturated:** when every non-thinking model scores at least 95%, record the date as `"saturatedSince"` in the task's `task.json`.
- **Deprecated:** after a task has been saturated for 365 days, set `"deprecated": true` in its `task.json`. Deprecated tasks and their results stay in the repository, but `bench.py run` skips them unless named with `--tasks`.

## Add a task

A task is a directory under `tasks/` with two files.

`task.json` defines the prompt, the output schema, and how each field is scored:

```json
{
  "name": "log_triage",
  "instructions": "System message: define every field and allowed value.",
  "prompt": "Log line:\n{text}",
  "schema": {"type": "object", "properties": {"severity": {"type": "string", "enum": ["info", "warn"]}}, "required": ["severity"], "additionalProperties": false},
  "fields": {"severity": "exact"}
}
```

`items.jsonl` holds one item per line, with either `text` or an `image` path relative to the task directory:

```json
{"id": "log-01", "text": "Sep 23 08:14:02 nas01 sshd[2211]: Accepted publickey ...", "expected": {"severity": "info"}}
```

Field scorers:

- `exact`: equality with matching types; strings compare case-insensitively after trimming whitespace, and `1` never equals `true`.
- `number`: a numeric value within 0.5% of the expected value.
- `time`: `HH:MM` and `HH:MM:SS` compare as the same minute.
- `set`: order-insensitive list equality.
- `digits`: digits-only equality, for phone numbers.
- `constraints`: `expected` holds `required` terms, optional `forbidden` terms, and `maxWords`; the answer passes when it contains every required term, no forbidden term (case-insensitive), and at most `maxWords` words.

Bump `SCORER_VERSION` in `bench.py` when scorer semantics change.

List every property in `required`. Apple's Foundation Model rejects union types such as `["integer", "null"]` and omitted the optional property in all 30 answers when tested, and OpenAI-style strict mode requires every property to be required, so use a documented sentinel value such as `0` when a field has no value.

Add the new task's hash to `tasks/FROZEN.json` (`python3 -c "import bench; print(bench.task_hash('my-task'))"`). `test_bench.py` fails when a frozen task's `task.json` or test items change, so tune instructions against `dev.jsonl` and update `FROZEN.json` only as a deliberate test-set revision.

Run `python3 test_bench.py` after editing. It checks the scorers, schema validation, and resume handling, and verifies that every task lists all properties as required and that every item's `expected` values satisfy the task schema.

## Fairness and limitations

Results measure a model together with its serving stack, not the model weights alone.

- **Constrained decoding differs by backend.** `fm serve` enforces the schema with Apple's guided generation, and ollama compiles it to its own grammar. `--no-schema` sends the schema in the system prompt instead, so a model's answers can be compared with and without its backend's decoder. Without a schema, the scorer accepts JSON wrapped in one markdown code fence.
- **Determinism.** At `temperature: 0`, Apple FM and gemma3:4b returned identical outputs on 12 of 12 repeated items, so each reference result comes from one run.
- **Context size.** ollama loaded gemma3:4b with a 131,072-token context, so receipt images aren't truncated. The manifest records the loaded context size per run.
- **Thinking models.** With `--extra '{"reasoning_effort":"none"}'`, Qwen3 on ollama returned 16 completion tokens and no reasoning text for a support ticket, against 670 tokens with thinking on.
- **Hand-written items.** The text tasks were written by one author, audited blind by four AI annotators, and relabeled blind by a second annotator (`gpt-6-astra` via `codex exec`), which agreed with 88 of 90 labels; the two disagreements were rewritten to be unambiguous. See [`annotations/`](annotations/).
- **Contamination.** CORD-v2 is a widely used document-AI dataset and is likely in the training data of open vision models; whether Apple FM saw it is unknown. `receipts-synthetic` is generated for this benchmark, so no model has seen it, but its clean rendered receipts differ from photographed ones.

## Apple Foundation Model notes

- `fm serve` streams responses unless the request sets `"stream": false`. The runner always sets it.
- The only model name `fm serve` accepts is `system`.
- The context window holds about 4,096 tokens, including instructions and output. Every task item fits well within it.
- Image input works through the standard `image_url` content part with a base64 data URL.
- `fm serve` accepts standard JSON Schema, but a schema without the `"x-order"` key (the property-order list that `fm schema` always emits) can make guided generation loop until it fills the context window, about 85 seconds on an M1 Max, and then fail. The report counts these as `overflow`. Adding `"x-order"` removed the overflow on all 10 affected event-extraction items. The reference runs keep the standard schema that OpenAI-compatible clients send. Reported to Apple as FB24922665 ([#21](https://github.com/SgtPooki/smol-task-bench/issues/21)).
- `fm serve` doesn't enforce `max_tokens`.
- `fm serve` processes one request at a time and keeps generating after a client times out, so a short `--timeout` delays every later request. Keep the default of 300 seconds.

## Data and license

The [MIT License](LICENSE) covers the code and the hand-written tasks.

The `receipts` task redistributes images and labels from CORD-v2 by Park et al. (2019) under [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/). [`scripts/fetch_cord.py`](scripts/fetch_cord.py) rebuilds the task from the source dataset.
