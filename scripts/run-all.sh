#!/bin/sh
# Reference run: Apple FM via `fm serve --port 1976`, everything else via ollama. Resumable.
set -x
TEXT=event-extraction,log-triage,support-tickets
O=http://localhost:11434/v1
python3 bench.py run --label apple-fm --base-url http://localhost:1976/v1 --model system
python3 bench.py run --label gemma3-4b --base-url $O --model gemma3:4b
python3 bench.py run --label qwen2.5vl-3b --base-url $O --model qwen2.5vl:3b
python3 bench.py run --label llama3.2-3b --base-url $O --model llama3.2:3b --tasks $TEXT
python3 bench.py run --label qwen3-4b --base-url $O --model qwen3:4b --tasks $TEXT --extra '{"reasoning_effort":"none"}'
python3 bench.py run --label qwen3-4b-thinking --base-url $O --model qwen3:4b --tasks $TEXT
