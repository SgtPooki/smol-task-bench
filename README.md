# smol-task-bench

smol-task-bench measures how well small local models handle everyday structured tasks: triaging log lines, routing support messages, pulling events out of text, and reading receipts. Every task has fixed answers that code scores directly, so results are reproducible and need no model acting as judge.

It targets Apple's on-device Foundation Model (`fm serve` on macOS 27) and compares it with open models of similar size served by [ollama](https://ollama.com). Any OpenAI-compatible endpoint works.

## Results

<!-- results:start -->
This benchmark is a pilot. Known scoring and labeling problems are tracked in the [P0 issues](https://github.com/SgtPooki/smol-task-bench/issues?q=is%3Aissue+label%3AP0), and reference results will be published after those land.
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

List every property in `required`. Apple's Foundation Model rejects union types such as `["integer", "null"]` and omitted an optional property in every pilot answer, and OpenAI-style strict mode requires every property to be required, so use a documented sentinel value such as `0` when a field has no value.

Run `python3 test_bench.py` after editing. It checks the scorers, schema validation, and resume handling, and verifies that every task lists all properties as required and that every item's `expected` values satisfy the task schema.

## Fairness and limitations

Results measure a model together with its serving stack, not the model weights alone.

- **Constrained decoding differs by backend.** `fm serve` enforces the schema with Apple's guided generation, and ollama compiles it to its own grammar. `--no-schema` sends the schema in the system prompt instead, so a model's answers can be compared with and without its backend's decoder. Without a schema, the scorer accepts JSON wrapped in one markdown code fence.
- **Determinism.** At `temperature: 0`, Apple FM and gemma3:4b returned identical outputs on 12 of 12 repeated items, so each reference result comes from one run.
- **Context size.** ollama loaded gemma3:4b with a 131,072-token context, so receipt images aren't truncated. The manifest records the loaded context size per run.
- **Thinking models.** With `--extra '{"reasoning_effort":"none"}'`, Qwen3 on ollama returned 16 completion tokens and no reasoning text for a support ticket, against 670 tokens with thinking on.
- **Hand-written items.** The text tasks were written by one author and audited by four AI annotators; see [`annotations/`](annotations/). A human second annotator is tracked in [#4](https://github.com/SgtPooki/smol-task-bench/issues/4).
- **Contamination.** CORD-v2 is a widely used document-AI dataset and is likely in the training data of open vision models. Whether Apple FM saw it is unknown. Treat receipt results as an upper bound until a fresh receipt set is added ([#8](https://github.com/SgtPooki/smol-task-bench/issues/8)).

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
