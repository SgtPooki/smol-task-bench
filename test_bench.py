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
# digits: formatting ignored
assert f("digits", "(415) 555-0142", "4155550142") and not f("digits", "415 555 0143", "4155550142")
# constraints: every required term (case-insensitive) and a word limit
c = {"required": ["A-10442", "October 6"], "maxWords": 8}
assert f("constraints", "Order a-10442 ships October 6.", c)
assert not f("constraints", "Order A-10442 ships soon.", c)
assert not f("constraints", "Your order A-10442 will definitely ship on October 6, sorry.", c)
assert not f("constraints", "Order A-10442 ships October 6 or 7.", {**c, "forbidden": ["October 7", " or 7"]})
assert f("constraints", "Order A-10442 ships October 6.", {**c, "forbidden": ["October 7"]})

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
assert bench.outcome(rec('```json\n{"s": "a", "n": 1}\n```')) == "correct"
assert bench.outcome(rec('Sure! {"s": "a", "n": 1}')) == "invalid_json"
assert bench.outcome(rec(None, "HTTP 500: The model's safety guardrails were triggered.")) == "refusal"
assert bench.outcome(rec(None, 'HTTP 500: {"error":{"message":"The model refused to answer."}}')) == "refusal"
assert bench.outcome(rec(None, "TimeoutError()")) == "transport"
assert bench.outcome(rec(None, "HTTP 500: The session's transcript exceeded the model's context size.")) == "overflow"

b = bench.request_body("m", {"name": "n", "instructions": "I", "schema": schema}, "hi", {})
assert b["response_format"]["json_schema"]["schema"] == schema and b["stream"] is False
b = bench.request_body("m", {"name": "n", "instructions": "I", "schema": schema}, "hi", {}, constrained=False)
assert "response_format" not in b and json.dumps(schema) in b["messages"][0]["content"]
b = bench.request_body("m", {"name": "n", "instructions": "I", "schema": schema}, "hi", {}, instructions_in_user=True)
assert [m["role"] for m in b["messages"]] == ["user"] and b["messages"][0]["content"] == "I\n\nhi"

lo, hi = bench.wilson(80, 100)
assert 0.71 < lo < 0.72 and 0.86 < hi < 0.87
assert bench.mcnemar_p(0, 5) == 0.0625 and bench.mcnemar_p(3, 3) == 1.0

# resume: truncated last line from an interrupted write is dropped, not fatal
with tempfile.TemporaryDirectory() as d:
    p = Path(d) / "t.jsonl"
    p.write_text('{"id": "a"}\n\n{"id": "b"}\n{"id": "c", "ra')
    assert [r["id"] for r in bench.read_records(p)] == ["a", "b"]
old = {"model": "m", "task_hashes": {"x": "1"}}
assert bench.check_resumable(old, {"model": "m", "task_hashes": {"x": "1", "y": "2"}}) == []  # adding a task is fine
assert bench.check_resumable(old, {"model": "m", "task_hashes": {"x": "9"}}) == ["x"]  # task data changed: rerun x
assert bench.check_resumable(old, {"model": "other", "task_hashes": {"x": "1"}}) is None  # settings changed: refuse
assert bench.check_resumable({**old, "scorer_version": 3}, {**old, "scorer_version": 4}) == []  # re-scored on report

assert "tool-calling" not in bench.http_tasks() and "log-triage" in bench.http_tasks()

# the test split is frozen: changing task.json or test items requires a deliberate tasks/FROZEN.json update
frozen = json.loads((bench.TASKS / "FROZEN.json").read_text())
for name, h in frozen.items():
    assert bench.task_hash(name) == h, f"{name} test data changed; tune on --split dev, or update tasks/FROZEN.json on purpose"

# task data: required covers every property, expected values satisfy the schema, ids unique, images exist
for d, split in [(d, s) for d in bench.TASKS.iterdir() if (d / "task.json").exists() for s in bench.SPLITS
                 if (d / bench.SPLITS[s]).exists()]:
    _, t, items = bench.load_task(d.name, split)
    assert d.name in frozen, (d.name, "missing from tasks/FROZEN.json")
    assert items, d.name
    assert set(t["schema"]["required"]) == set(t["schema"]["properties"]), (d.name, "every property must be required")
    assert set(t["fields"]) <= set(t["schema"]["properties"]), d.name
    assert len({i["id"] for i in items}) == len(items), (d.name, split, "duplicate ids")
    for it in items:
        assert set(it["expected"]) == set(t["fields"]), (d.name, it["id"])
        checked = {k: v for k, v in it["expected"].items() if t["fields"][k] != "constraints"}  # constraints aren't answers
        assert bench.schema_errors({**t["schema"], "required": list(checked)}, checked) == [], (d.name, it["id"])
        assert "image" not in it or (d / it["image"]).exists(), (d.name, it["id"])
    if split == "test" and (d / "images").exists():  # every image belongs to an item, so items can't silently go missing
        used = {it["image"] for it in items if "image" in it}
        orphans = {f"images/{p.name}" for p in (d / "images").iterdir()} - used
        assert not orphans, (d.name, "images with no item", sorted(orphans)[:3])

import sys
sys.path.append(str(Path(__file__).parent / "scripts"))
import fetch_cord

assert fetch_cord.amount("60.000") == 60000
assert fetch_cord.amount("365000.00") == 365000
assert fetch_cord.amount("1.591.600") == 1591600
assert fetch_cord.amount("45.500,00") == 45500
assert fetch_cord.amount("Rp 43.000") == 43000
assert fetch_cord.amount("") is None

print("ok")
