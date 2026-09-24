# smol-task-bench

smol-task-bench measures how well small local models handle everyday structured tasks: triaging log lines, routing support messages, pulling events out of text, and reading receipts. Every task has fixed answers that code scores directly, so results are reproducible and need no model acting as judge.

It targets Apple's on-device Foundation Model (`fm serve` on macOS 27) and compares it with open models of similar size served by [ollama](https://ollama.com). Any OpenAI-compatible endpoint works.

## Results

<!-- results:start -->
Run on 2026-09-23 on a MacBook Pro (M1 Max, 64 GB), macOS 27.0 (26A428), ollama 0.34.3. The test split is frozen in [`tasks/FROZEN.json`](tasks/FROZEN.json).

Share of items with every field correct, constrained track (`response_format: json_schema`), with median seconds per item:

| Model | log-triage | support-tickets | event-extraction | receipts (CORD) | receipts-synthetic |
|---|---|---|---|---|---|
| Apple FM (`fm serve`) | 70.0% (0.87 s) | 86.7% (0.72 s) | 33.3% (1.50 s) | 55.0% (2.56 s) | 25.0% (3.35 s) |
| gemma3:4b | 66.7% (0.53 s) | 93.3% (0.64 s) | 70.0% (0.84 s) | 27.5% (2.71 s) | 22.5% (3.09 s) |
| llama3.2:3b | 63.3% (0.26 s) | 86.7% (0.29 s) | 73.3% (0.49 s) | text only | text only |
| qwen2.5vl:3b | 70.0% (0.26 s) | 76.7% (0.29 s) | 56.7% (0.64 s) | 77.5% (4.45 s) | 47.5% (3.36 s) |
| qwen3:4b, thinking off | 90.0% (0.34 s) | 90.0% (0.41 s) | 40.0% (0.83 s) | text only | text only |
| qwen3:4b, thinking on | 93.3% (13.12 s) | 100.0% (11.27 s) | 100.0% (97.68 s) | text only | text only |

With 30 to 40 items per task, most differences under about 20 points are not significant. Paired McNemar tests against Apple FM (`python3 bench.py report --vs apple-fm`) find:

- **log-triage and support-tickets:** no model without thinking differs significantly from Apple FM (p ≥ 0.109).
- **event-extraction:** gemma3:4b, llama3.2:3b, and qwen2.5vl:3b beat Apple FM (p ≤ 0.016). 10 of Apple FM's 30 answers are `overflow`: guided generation loops until it fills the context window ([#21](https://github.com/SgtPooki/smol-task-bench/issues/21)). Its field accuracy on the items it did answer is 81.7%.
- **receipts (CORD):** qwen2.5vl:3b beats Apple FM (p = 0.035), and Apple FM beats gemma3:4b (p = 0.019). gemma3:4b reads 37 of 40 totals correctly but counts item lines correctly on only 12.
- **receipts-synthetic:** qwen2.5vl:3b beats Apple FM (p = 0.049). Apple FM reads all 12 yen totals correctly but only 3 of 28 totals with cents: it drops or misplaces the decimal point (for example 108.45 read as 10845). qwen2.5vl:3b reads all 40 totals correctly. Item-line counting is the hardest field for every model (10 to 25 of 40).
- **Thinking:** qwen3:4b with thinking on is the most accurate model on every text task, at 11 to 98 seconds per item.

The `--no-schema` track sends the JSON Schema in the system prompt instead. It removes Apple FM's overflows on event-extraction (46.7% correct, 0 overflows) but introduces schema failures elsewhere: Apple FM answers `"type"` instead of `"category"` on 27 of 30 support tickets (10.0% correct), and llama3.2:3b echoes the schema back on 24 of 30 event items. These failures depend on how the prompt presents the schema, so treat the no-schema track as a measure of what constrained decoding contributes, not of each model's ceiling. qwen3:4b has no no-schema results because ollama 0.34.3 only disables its thinking together with `response_format`.

Moving the task instructions from the system message into the user message (`--instructions-in-user`) changes no model's score significantly on any text task (p ≥ 0.125), so the reference runs keep the system message.

`python3 bench.py report` prints every column for every label, including each failure type.
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
| `log-triage` | One syslog or app log line | 30 | `service`, `severity` | Hand-written |
| `support-tickets` | A short customer message | 30 | `category`, `urgent` | Hand-written |
| `event-extraction` | A message mentioning one event | 30 | `date`, `startTime`, `durationMinutes` | Hand-written |
| `receipts` | A receipt photo | 40 | `total`, `itemCount` | [CORD-v2](https://huggingface.co/datasets/naver-clova-ix/cord-v2) test split |
| `receipts-synthetic` | A generated receipt image | 40 | `total`, `currency`, `date`, `itemCount` | [`scripts/make_synthetic_receipts.py`](scripts/make_synthetic_receipts.py) |

Each task's `items.jsonl` is the frozen test split. The hand-written tasks also have a `dev.jsonl` split, written by a separate AI model, for tuning prompts without touching the test split (`--split dev`).

Each request sends the task's instructions as the system message and asks for JSON through `response_format: json_schema`. Every result falls into exactly one outcome:

- `correct`: valid JSON, valid against the task schema, and every scored field matches
- `wrong`: valid against the schema, but at least one field doesn't match
- `schema fail`: valid JSON that violates the schema (missing, extra, or mistyped property)
- `invalid JSON`: the response isn't a JSON object
- `refused`: the server returned a guardrail error
- `overflow`: generation ran past the model's context window without finishing, which `fm serve` reports as an error
- `errors`: any other transport failure, such as a timeout

The report shows the all-fields-correct rate with a 95% Wilson confidence interval, per-field accuracy over parsed responses, the count of each outcome, and the median seconds per successful request. `--vs LABEL` adds an exact McNemar test per task, which compares two models on the same items and is more sensitive than comparing their separate intervals.

With 30 to 40 items per task, a confidence interval can span up to ±18 points (the width at a 50% score with 30 items). Use the results to separate models that differ by a wide margin, not to rank near-ties.

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
- `fm serve` doesn't enforce `max_tokens`. With a required integer field and an unrelated number in the input (for example "arrive 10 minutes early"), generation can run until it fills the context window, about 85 seconds on an M1 Max, and then fail. The report counts these as `overflow`.
- `fm serve` processes one request at a time and keeps generating after a client times out, so a short `--timeout` delays every later request. Keep the default of 300 seconds.

## Data and license

The [MIT License](LICENSE) covers the code and the hand-written tasks.

The `receipts` task redistributes images and labels from CORD-v2 by Park et al. (2019) under [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/). [`scripts/fetch_cord.py`](scripts/fetch_cord.py) rebuilds the task from the source dataset.
