# tool-calling

This task measures Apple Foundation Models tool calling through the native Swift `FoundationModels` API, because `fm serve` returns raw template tokens instead of `tool_calls`. It runs outside `bench.py` and is reported separately from the HTTP tasks.

Each of the 20 items needs zero, one, or two calls to three tools with canned outputs (`getWeather`, `lookupOrder`, `convertCurrency`). An item passes when the set of tool calls matches exactly (order-insensitive; numbers compared numerically, strings case-insensitively), the final answer contains every `answerContains` value (ignoring case, thousands separators, and a trailing `.00`), and the request doesn't error.

```sh
swiftc -O swift/toolbench.swift -o swift/toolbench
./swift/toolbench   # writes results/apple-fm-native/tool-calling.jsonl and prints a summary
```

The harness uses greedy sampling, so repeated runs give identical results, and sets no token cap, so runaway generation shows up as an error.

## Result (macOS 27.0, 26A428, M1 Max)

17 of 20 items pass. All 16 items that need tools pass, including every two-call item. Of the 4 items that need no tool, "Explain what an API is in one sentence." and "What is 2 + 2?" trigger unnecessary `convertCurrency` calls, and "Write a short haiku about a robot." generates until it exceeds the 4,096-token context (about 150 seconds).
