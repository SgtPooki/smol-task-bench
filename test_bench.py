"""Scoring, schema, resume, and task-data checks. Run: python3 test_bench.py"""
import json, tempfile
from pathlib import Path

import bench

f = bench.field_ok
# number: tolerance, numeric types only
assert f("number", None, None) and not f("number", 30, None) and not f("number", None, 30)
assert f("number", 60000, 60000) and not f("number", "60000", 60000) and not f("number", 61000, 60000)
assert not f("number", True, 1)
# exact: case/whitespace-insensitive strings, strict types
assert f("exact", "Warn ", "warn") and not f("exact", "error", "warn")
assert f("exact", True, True) and not f("exact", False, True) and not f("exact", "true", True)
assert not f("exact", 1, True) and not f("exact", True, 1)
assert f("exact", 60000, 60000) and f("exact", 60000.0, 60000) and not f("exact", "60000", 60000)
# time: HH:MM and HH:MM:SS are equal, garbage is not
assert f("time", "09:00:00", "09:00") and f("time", "9:00", "09:00") and not f("time", "09:30", "09:00")
assert not f("time", "nine", "09:00") and not f("time", None, "09:00")
# set
assert f("set", ["b", "A"], ["a", "b"]) and not f("set", ["a"], ["a", "b"])

schema = {"type": "object", "properties": {"s": {"type": "string", "enum": ["a", "b"]}, "n": {"type": "integer"}},
          "required": ["s", "n"], "additionalProperties": False}
assert bench.schema_errors(schema, {"s": "a", "n": 1}) == []
assert bench.schema_errors(schema, {"s": "a"}) == ["$.n: missing"]
assert bench.schema_errors(schema, {"s": "c", "n": 1}) == ["$.s: 'c' not in enum"]
assert bench.schema_errors(schema, {"s": "a", "n": True}) == ["$.n: expected integer"]
assert bench.schema_errors(schema, {"s": "a", "n": 1, "x": 0}) == ["$.x: not allowed"]

task = {"schema": schema, "fields": {"s": "exact", "n": "exact"}}
rec = lambda raw, err=None: {"raw": raw, "error": err, **bench.score(task, raw, {"s": "a", "n": 1})}
assert bench.outcome(rec('{"s": "a", "n": 1}')) == "correct"
assert bench.outcome(rec('{"s": "b", "n": 1}')) == "wrong"
assert bench.outcome(rec('{"s": "a", "n": "1"}')) == "schema"
assert bench.outcome(rec("not json")) == "invalid_json"
assert bench.outcome(rec(None, "HTTP 500: The model's safety guardrails were triggered.")) == "refusal"
assert bench.outcome(rec(None, "TimeoutError()")) == "transport"
assert bench.outcome(rec(None, "HTTP 500: The session's transcript exceeded the model's context size.")) == "overflow"

lo, hi = bench.wilson(80, 100)
assert 0.71 < lo < 0.72 and 0.86 < hi < 0.87
assert bench.mcnemar_p(0, 5) == 0.0625 and bench.mcnemar_p(3, 3) == 1.0

# resume: truncated last line from an interrupted write is dropped, not fatal
with tempfile.TemporaryDirectory() as d:
    p = Path(d) / "t.jsonl"
    p.write_text('{"id": "a"}\n\n{"id": "b"}\n{"id": "c", "ra')
    assert [r["id"] for r in bench.read_records(p)] == ["a", "b"]
old = {"model": "m", "task_hashes": {"x": "1"}}
assert bench.check_resumable(old, {"model": "m", "task_hashes": {"x": "1", "y": "2"}})  # adding a task is fine
assert not bench.check_resumable(old, {"model": "m", "task_hashes": {"x": "9"}})  # task data changed
assert not bench.check_resumable(old, {"model": "other", "task_hashes": {"x": "1"}})

# task data: required covers every property, expected values satisfy the schema, ids unique, images exist
for d in bench.TASKS.iterdir():
    if not (d / "task.json").exists():
        continue
    _, t, items = bench.load_task(d.name)
    assert items, d.name
    assert set(t["schema"]["required"]) == set(t["schema"]["properties"]), (d.name, "every property must be required")
    assert set(t["fields"]) <= set(t["schema"]["properties"]), d.name
    assert len({i["id"] for i in items}) == len(items), (d.name, "duplicate ids")
    for it in items:
        assert set(it["expected"]) == set(t["fields"]), (d.name, it["id"])
        assert bench.schema_errors(t["schema"], it["expected"]) == [], (d.name, it["id"])
        assert "image" not in it or (d / it["image"]).exists(), (d.name, it["id"])

print("ok")
