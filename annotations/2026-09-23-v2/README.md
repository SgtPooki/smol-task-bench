# Second annotator and dev split, 2026-09-23

A second annotator relabeled all 90 hand-written test items blind, after the [first audit](../2026-09-23/README.md) changes, and a separate model wrote the dev split.

## Second annotator

`gpt-6-astra`, via `codex exec` in an empty directory, received [`prompt.md`](prompt.md): each task's current guidelines and item text, with no expected values. It agreed with 88 of 90 labels and 208 of 210 fields ([`codex.jsonl`](codex.jsonl); `python3 compare.py` reproduces this against [`author-labels.jsonl`](author-labels.jsonl)).

Both disagreements were items the first audit had also flagged as close calls, so they were rewritten to be unambiguous rather than relabeled:

| Item | Disagreement | Change |
|---|---|---|
| log-09 | `warn` vs `critical` for pending disk sectors | Replaced with a clock-drift warning (`chronyd`, `warn`) |
| log-15 | `info` vs `warn` for a scheduled certificate renewal | Replaced with a completed renewal (`certbot`, `info`) |

## Dev split

Gemini 3.1 Pro (High), via Antigravity `agy`, wrote 10 new labeled items per text task from [`dev-prompt.md`](dev-prompt.md) ([`dev-gemini.jsonl`](dev-gemini.jsonl)). Three near-duplicates of test items were dropped (log-dev-02, log-dev-08, ticket-dev-09), and the rest became each task's `dev.jsonl`.
