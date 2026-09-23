#!/usr/bin/env python3
"""smol-task-bench: practical tasks for small local models over any OpenAI-compatible endpoint.

  python3 bench.py run --label apple-fm --base-url http://localhost:1976/v1 --model system
  python3 bench.py run --label qwen3-4b --base-url http://localhost:11434/v1 --model qwen3:4b --tasks log-triage
  python3 bench.py report
"""
import argparse, base64, json, mimetypes, statistics, sys, time, urllib.error, urllib.request
from math import sqrt
from pathlib import Path

ROOT = Path(__file__).parent
TASKS, RESULTS = ROOT / "tasks", ROOT / "results"


def load_task(name):
    d = TASKS / name
    task = json.loads((d / "task.json").read_text())
    items = [json.loads(l) for l in (d / "items.jsonl").read_text().splitlines() if l.strip()]
    return d, task, items


def user_content(task_dir, task, item):
    text = task.get("prompt", "{text}").replace("{text}", item.get("text", ""))
    if "image" not in item:
        return text
    p = task_dir / item["image"]
    mime = mimetypes.guess_type(p.name)[0] or "image/png"
    url = f"data:{mime};base64,{base64.b64encode(p.read_bytes()).decode()}"
    return [{"type": "text", "text": text}, {"type": "image_url", "image_url": {"url": url}}]


def call(base_url, model, task_dir, task, item, extra, timeout):
    body = {
        "model": model,
        "stream": False,  # fm serve streams unless told otherwise
        "temperature": 0,
        "messages": [{"role": "system", "content": task["instructions"]},
                     {"role": "user", "content": user_content(task_dir, task, item)}],
        "response_format": {"type": "json_schema",
                            "json_schema": {"name": task["name"], "schema": task["schema"], "strict": True}},
        **extra,
    }
    req = urllib.request.Request(f"{base_url.rstrip('/')}/chat/completions", json.dumps(body).encode(),
                                 {"content-type": "application/json"})
    t = time.monotonic()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            resp = json.load(r)
        return resp["choices"][0]["message"].get("content") or "", None, time.monotonic() - t
    except urllib.error.HTTPError as e:
        return None, f"HTTP {e.code}: {e.read()[:300].decode(errors='replace')}", time.monotonic() - t
    except Exception as e:
        return None, repr(e)[:300], time.monotonic() - t


def norm(v):
    return v.strip().lower() if isinstance(v, str) else v


def field_ok(kind, got, want):
    if want is None:
        return got is None
    if kind == "number":
        try:
            return abs(float(got) - float(want)) <= 0.005 * max(1.0, abs(float(want)))
        except (TypeError, ValueError):
            return False
    if kind == "set":  # order-insensitive list of strings
        return isinstance(got, list) and {norm(x) for x in got} == {norm(x) for x in want}
    return norm(got) == norm(want)


def score(task, raw, expected):
    """-> (parsed_ok, {field: bool})"""
    try:
        out = json.loads(raw)
        assert isinstance(out, dict)
    except Exception:
        return False, {f: False for f in task["fields"]}
    return True, {f: field_ok(kind, out.get(f), expected[f]) for f, kind in task["fields"].items()}


def cmd_run(a):
    extra = json.loads(a.extra) if a.extra else {}
    names = a.tasks.split(",") if a.tasks else sorted(p.name for p in TASKS.iterdir() if (p / "task.json").exists())
    for name in names:
        task_dir, task, items = load_task(name)
        if a.limit:
            items = items[: a.limit]
        out = RESULTS / a.label / f"{name}.jsonl"
        out.parent.mkdir(parents=True, exist_ok=True)
        done = {json.loads(l)["id"] for l in out.read_text().splitlines()} if out.exists() else set()
        todo = [i for i in items if i["id"] not in done]
        print(f"[{a.label}] {name}: {len(todo)} to run ({len(done)} cached)", file=sys.stderr)
        with out.open("a") as f:
            for n, item in enumerate(todo, 1):
                raw, err, secs = call(a.base_url, a.model, task_dir, task, item, extra, a.timeout)
                parsed, fields = score(task, raw, item["expected"]) if raw is not None else (False, {k: False for k in task["fields"]})
                rec = {"id": item["id"], "parsed": parsed, "fields": fields, "seconds": round(secs, 3),
                       "error": err, "raw": raw, "expected": item["expected"]}
                f.write(json.dumps(rec) + "\n")
                f.flush()
                print(f"  {n}/{len(todo)} {item['id']} {'ok' if all(fields.values()) else 'miss' if parsed else 'ERR'} {secs:.1f}s",
                      file=sys.stderr)


def wilson(k, n, z=1.96):
    if not n:
        return 0.0, 0.0
    p, d = k / n, 1 + z * z / n
    m, h = (p + z * z / (2 * n)) / d, z * sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return m - h, m + h


def cmd_report(a):
    rows = []
    for f in sorted(RESULTS.glob("*/*.jsonl")):
        recs = [json.loads(l) for l in f.read_text().splitlines() if l.strip()]
        if not recs:
            continue
        n = len(recs)
        exact = sum(all(r["fields"].values()) for r in recs)
        field_acc = statistics.mean(statistics.mean(r["fields"].values()) for r in recs)
        lo, hi = wilson(exact, n)
        rows.append((f.stem, f.parent.name, n, exact / n, lo, hi, field_acc,
                     1 - sum(r["parsed"] for r in recs) / n, statistics.median(r["seconds"] for r in recs)))
    print("| task | model | n | all fields correct | 95% CI | field accuracy | invalid output | median s |")
    print("|---|---|---|---|---|---|---|---|")
    for t, m, n, ex, lo, hi, fa, bad, sec in sorted(rows):
        print(f"| {t} | {m} | {n} | {ex:.1%} | {lo:.0%}-{hi:.0%} | {fa:.1%} | {bad:.0%} | {sec:.2f} |")


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run", help="run tasks against one model")
    r.add_argument("--label", required=True, help="results/<label>/ directory name")
    r.add_argument("--base-url", required=True, help="OpenAI-compatible base URL, e.g. http://localhost:11434/v1")
    r.add_argument("--model", required=True)
    r.add_argument("--tasks", help="comma-separated task names (default: all)")
    r.add_argument("--limit", type=int, help="first N items per task")
    r.add_argument("--extra", help="JSON merged into the request body, e.g. '{\"reasoning_effort\":\"none\"}'")
    r.add_argument("--timeout", type=float, default=300)
    r.set_defaults(fn=cmd_run)
    sub.add_parser("report", help="markdown table of all results").set_defaults(fn=cmd_report)
    a = p.parse_args()
    a.fn(a)


if __name__ == "__main__":
    main()
