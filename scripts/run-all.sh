#!/bin/sh
# Reference run: Apple FM via `fm serve --port 1976`, everything else via ollama. Resumable.
# Models run twice: constrained (response_format json_schema) and --no-schema (schema in the prompt).
set -eux
TEXT=event-extraction,log-triage,support-tickets
O=http://localhost:11434/v1
for mode in "" --no-schema; do
  s=${mode:+-noschema}
  python3 bench.py run --label apple-fm$s --base-url http://localhost:1976/v1 --model system $mode
  python3 bench.py run --label gemma3-4b$s --base-url $O --model gemma3:4b $mode
  python3 bench.py run --label qwen2.5vl-3b$s --base-url $O --model qwen2.5vl:3b $mode
  python3 bench.py run --label llama3.2-3b$s --base-url $O --model llama3.2:3b --tasks $TEXT $mode
done
# ollama 0.34 honors reasoning_effort "none" only together with response_format, so Qwen3 without thinking
# runs constrained only (think:false and /no_think still produce reasoning tokens without a schema)
python3 bench.py run --label qwen3-4b --base-url $O --model qwen3:4b --tasks $TEXT --extra '{"reasoning_effort":"none"}'
# thinking mode is slow (about 100 s per event item on an M1 Max), so it also runs constrained only
python3 bench.py run --label qwen3-4b-thinking --base-url $O --model qwen3:4b --tasks $TEXT
# instruction placement check: task instructions in the user message instead of a system message
for m in "apple-fm http://localhost:1976/v1 system" "gemma3-4b $O gemma3:4b" "qwen2.5vl-3b $O qwen2.5vl:3b" "llama3.2-3b $O llama3.2:3b"; do
  set -- $m
  python3 bench.py run --label $1-userinst --base-url $2 --model $3 --tasks $TEXT --instructions-in-user
done
python3 bench.py run --label qwen3-4b-userinst --base-url $O --model qwen3:4b --tasks $TEXT --extra '{"reasoning_effort":"none"}' --instructions-in-user
