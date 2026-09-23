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

   Runs are resumable: the runner skips items already in `results/<label>/<task>.jsonl`. Text-only models fail on image tasks, so pass `--tasks` to pick a subset. `--limit N` runs the first N items of each task.

3. Print the comparison table:

   ```sh
   python3 bench.py report
   ```

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

Each request sends the task's instructions as the system message and asks for JSON through `response_format: json_schema`. An item counts as correct only when every scored field matches. The report also shows per-field accuracy, the share of invalid (unparseable) outputs, the median seconds per item, and a 95% Wilson confidence interval on the all-fields-correct rate.

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

- `exact`: case-insensitive, whitespace-trimmed equality. Booleans compare as booleans.
- `number`: within 0.5% of the expected value.
- `set`: order-insensitive list equality.

An `expected` value of `null` matches an omitted or null output.

Keep schemas within what every target model accepts. Apple's Foundation Model rejects union types such as `["integer", "null"]`, so express optional values by leaving the field out of `required`.

Run `python3 test_bench.py` after editing. It checks the scorers and verifies that every item's `expected` keys match its task's `fields`.

## Apple Foundation Model notes

- `fm serve` streams responses unless the request sets `"stream": false`. The runner always sets it.
- The only model name `fm serve` accepts is `system`.
- The context window holds about 4,096 tokens, including instructions and output. Every task item fits well within it.
- Image input works through the standard `image_url` content part with a base64 data URL.

## Data and license

The [MIT License](LICENSE) covers the code and the hand-written tasks.

The `receipts` task redistributes images and labels from CORD-v2 by Park et al. (2019) under [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/). [`scripts/fetch_cord.py`](scripts/fetch_cord.py) rebuilds the task from the source dataset.
