# Label audit, 2026-09-23

Four AI annotators from different model families relabeled the 90 hand-written items (`log-triage`, `support-tickets`, `event-extraction`) without seeing the author's labels. They agreed with the author on 86 to 89 of 90 items each. The audit changed 1 label, reworded or replaced 6 items, and tightened 2 task instructions.

## Method

Every annotator received the same packet, [`prompt.md`](prompt.md): each task's guidelines and item text, with no expected values. Each labeled every field and marked any item where a careful reader could reasonably choose a different label.

| Annotator | Model | Tools |
|---|---|---|
| `gemini` | Gemini 3.1 Pro (High), via Antigravity `agy` | allowed, run in an empty directory |
| `codex` | `gpt-6-astra`, via `codex exec` | allowed, run in an empty directory |
| `cursor` | `cursor-agent` default model (not recorded) | allowed, run in an empty directory |
| `omp` | `omp` default model (not recorded) | disabled (`--no-tools`) |

[`author-labels.jsonl`](author-labels.jsonl) snapshots the labels as they were during the audit. `python3 compare.py` reproduces the numbers below.

## Agreement with the author's labels

| Annotator | Fields agreeing | Items agreeing on every field |
|---|---|---|
| gemini | 209/210 | 89/90 |
| cursor | 208/210 | 88/90 |
| codex | 207/210 | 87/90 |
| omp | 206/210 | 86/90 |

The annotators followed the author's written guidelines, and AI annotators can share blind spots, so this agreement shows the labels are consistent with the guidelines. It does not show the guidelines are the only reasonable reading. Human annotation is still open in [#4](https://github.com/SgtPooki/smol-task-bench/issues/4).

## Resulting changes

| Item | Finding | Change |
|---|---|---|
| log-15 | 3 of 4 labeled a scheduled certificate renewal `info` | Label changed from `warn` to `info` |
| event-07 | Split 2 to 2 on whether an arrival window has a duration | Reworded to a booked slot, `from 8 to 10am` |
| event-27 | All 4 flagged a payment deadline as not an event | Replaced with a hearing that has a start time and duration |
| event-17 | All 4 flagged doors vs show time | Reworded to state only the show time |
| event-06, event-13, event-25 | Times without am/pm | Guideline added: a time without am/pm means the daytime reading |
| event-06 | "usually go about two hours" read as habitual | Reworded to "It runs about two hours" |
| ticket-23 | 3 of 4 chose `account-access`, 1 chose `bug`, and 3 flagged it ambiguous | Replaced with an unambiguous `account-access` message |
| ticket-08 | 3 of 4 marked it urgent, and 3 flagged the urgency as ambiguous under the guideline | Guideline added: many users blocked from core functionality is urgent |

log-09, log-23, and log-25 were flagged as close calls, but a majority matched the author's label in each case, so they stay unchanged.
