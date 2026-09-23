"""Scoring checks. Run: python3 test_bench.py"""
import json
from pathlib import Path

import bench

f = bench.field_ok
assert f("number", None, None) and not f("number", 30, None) and not f("number", None, 30)
assert f("number", 60000, 60000) and f("number", "60000", 60000) and not f("number", 61000, 60000)
assert f("exact", "Warn ", "warn") and not f("exact", "error", "warn")
assert f("exact", True, True) and not f("exact", False, True) and not f("exact", "true", True)
assert f("set", ["b", "A"], ["a", "b"]) and not f("set", ["a"], ["a", "b"])

ok, fields = bench.score({"fields": {"a": "exact"}}, "not json", {"a": 1})
assert not ok and fields == {"a": False}
ok, fields = bench.score({"fields": {"a": "exact", "d": "number"}}, '{"a": "x"}', {"a": "X", "d": None})
assert ok and fields == {"a": True, "d": True}  # omitted optional field == null

lo, hi = bench.wilson(80, 100)
assert 0.71 < lo < 0.72 and 0.86 < hi < 0.87

# every item's expected keys match its task's scored fields
for d in bench.TASKS.iterdir():
    if (d / "task.json").exists():
        _, task, items = bench.load_task(d.name)
        assert items, d.name
        for it in items:
            assert set(it["expected"]) == set(task["fields"]), (d.name, it["id"])
            assert "image" not in it or (d / it["image"]).exists(), (d.name, it["id"])

print("ok")
