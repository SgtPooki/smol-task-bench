#!/usr/bin/env python3
"""smol-task-bench: practical tasks for small local models over any OpenAI-compatible endpoint.

  python3 bench.py run --label apple-fm --base-url http://localhost:1976/v1 --model system
  python3 bench.py run --label qwen3-4b --base-url http://localhost:11434/v1 --model qwen3:4b --tasks log-triage
  python3 bench.py report [--vs apple-fm]
"""
import argparse, base64, hashlib, json, math, mimetypes, platform, re, shutil, statistics, subprocess, sys, time
import urllib.error, urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).parent
TASKS, RESULTS = ROOT / "tasks", ROOT / "results"
SCORER_VERSION = 4  # bump when field_ok/score semantics change


SPLITS = {"test": "items.jsonl", "dev": "dev.jsonl"}  # tune prompts on dev; test is frozen (tasks/FROZEN.json)


def load_task(name, split="test"):
    d = TASKS / name
    task = json.loads((d / "task.json").read_text())
    items = [json.loads(l) for l in (d / SPLITS[split]).read_text().splitlines() if l.strip()]
    return d, task, items


def task_hash(name, split="test"):
    """sha256 over task.json, the split's items file, and every referenced image."""
    d, _, items = load_task(name, split)
    h = hashlib.sha256((d / "task.json").read_bytes() + (d / SPLITS[split]).read_bytes())
    for it in items:
        if "image" in it:
            h.update((d / it["image"]).read_bytes())
    return h.hexdigest()


# ---------- request ----------

def user_content(task_dir, task, item):
    text = task.get("prompt", "{text}").replace("{text}", item.get("text", ""))
    if "image" not in item:
        return text
    p = task_dir / item["image"]
    mime = mimetypes.guess_type(p.name)[0] or "image/png"
    url = f"data:{mime};base64,{base64.b64encode(p.read_bytes()).decode()}"
    return [{"type": "text", "text": text}, {"type": "image_url", "image_url": {"url": url}}]


def request_body(model, task, content, extra, constrained=True, instructions_in_user=False):
    system = task["instructions"]
    if not constrained:  # schema goes in the prompt instead of the backend's constrained decoder
        system += "\n\nRespond with only a JSON object matching this JSON Schema:\n" + json.dumps(task["schema"])
    if instructions_in_user:  # some small models follow user-turn instructions better than a system message
        if isinstance(content, str):
            content = f"{system}\n\n{content}"
        else:
            content = [{"type": "text", "text": system}, *content]
        messages = [{"role": "user", "content": content}]
    else:
        messages = [{"role": "system", "content": system}, {"role": "user", "content": content}]
    body = {
        "model": model,
        "stream": False,  # fm serve streams unless told otherwise
        "temperature": 0,
        "messages": messages,
        **extra,
    }
    if constrained:
        body["response_format"] = {"type": "json_schema",
                                   "json_schema": {"name": task["name"], "schema": task["schema"], "strict": True}}
    return body


def call(base_url, body, timeout):
    """-> (content | None, error | None, seconds)"""
    req = urllib.request.Request(f"{base_url.rstrip('/')}/chat/completions", json.dumps(body).encode(),
                                 {"content-type": "application/json"})
    t = time.monotonic()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            resp = json.load(r)
        return resp["choices"][0]["message"].get("content") or "", None, time.monotonic() - t
    except urllib.error.HTTPError as e:
        return None, f"HTTP {e.code}: {e.read()[:2000].decode(errors='replace')}", time.monotonic() - t
    except Exception as e:
        return None, repr(e)[:2000], time.monotonic() - t


# ---------- scoring ----------

def is_num(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def norm(v):
    return v.strip().lower() if isinstance(v, str) else v


def norm_time(v):
    m = re.fullmatch(r"\s*(\d{1,2}):(\d{2})(?::\d{2})?\s*", v) if isinstance(v, str) else None
    return f"{int(m[1]):02d}:{m[2]}" if m else None


def field_ok(kind, got, want):
    if want is None:
        return got is None
    if kind == "time":
        return norm_time(got) is not None and norm_time(got) == norm_time(want)
    if kind == "number":
        return is_num(got) and abs(got - want) <= 0.005 * max(1.0, abs(want))
    if kind == "digits":  # phone numbers: compare digits only
        return isinstance(got, str) and re.sub(r"\D", "", got) == re.sub(r"\D", "", want)
    if kind == "constraints":  # want = {"required": [terms], "maxWords": n, optional "forbidden": [terms]}
        return (isinstance(got, str) and all(t.lower() in got.lower() for t in want["required"])
                and not any(t.lower() in got.lower() for t in want.get("forbidden", []))
                and len(got.split()) <= want["maxWords"])
    if kind == "set":  # order-insensitive list of strings
        return isinstance(got, list) and {norm(x) for x in got} == {norm(x) for x in want}
    # exact: types must agree (1 is not True, "5" is not 5)
    if isinstance(want, bool) or isinstance(got, bool):
        return type(got) is type(want) and got == want
    if is_num(want):
        return is_num(got) and got == want
    return isinstance(got, str) and norm(got) == norm(want)


TYPES = {"string": str, "integer": int, "number": (int, float), "boolean": bool, "object": dict, "array": list}


def schema_errors(schema, v, path="$"):
    """Validate the JSON Schema subset tasks use: type, enum, properties, required, additionalProperties, items."""
    t = schema.get("type")
    if t:
        ok = isinstance(v, TYPES[t]) and not (t in ("integer", "number") and isinstance(v, bool))
        if not ok:
            return [f"{path}: expected {t}"]
    if "enum" in schema and v not in schema["enum"]:
        return [f"{path}: {v!r} not in enum"]
    errs = []
    if t == "object":
        props = schema.get("properties", {})
        errs += [f"{path}.{k}: missing" for k in schema.get("required", []) if k not in v]
        if schema.get("additionalProperties") is False:
            errs += [f"{path}.{k}: not allowed" for k in v if k not in props]
        for k, sub in props.items():
            if k in v:
                errs += schema_errors(sub, v[k], f"{path}.{k}")
    if t == "array" and "items" in schema:
        for i, x in enumerate(v):
            errs += schema_errors(schema["items"], x, f"{path}[{i}]")
    return errs


def outcome(rec):
    """Classify one result: transport | refusal | overflow | invalid_json | schema | wrong | correct."""
    if rec["raw"] is None:
        err = (rec["error"] or "").lower()
        if "guardrail" in err or "refused to answer" in err:  # fm serve's two refusal messages
            return "refusal"
        if "exceeded the model's context size" in err:  # fm serve: output ran past the context window
            return "overflow"
        return "transport"
    if not rec["json_ok"]:
        return "invalid_json"
    if not rec["schema_ok"]:
        return "schema"
    return "correct" if all(rec["fields"].values()) else "wrong"


def score(task, raw, expected):
    """-> dict(json_ok, schema_ok, schema_errors, fields)"""
    if raw is not None:  # unconstrained models often wrap JSON in one markdown fence
        m = re.fullmatch(r"\s*```(?:json)?\s*(.*?)\s*```\s*", raw, re.S)
        raw = m[1] if m else raw
    try:
        out = json.loads(raw) if raw is not None else None
    except (json.JSONDecodeError, TypeError):
        out = None
    if not isinstance(out, dict):
        return {"json_ok": False, "schema_ok": False, "schema_errors": [], "fields": {f: False for f in task["fields"]}}
    errs = schema_errors(task["schema"], out)
    return {"json_ok": True, "schema_ok": not errs, "schema_errors": errs,
            "fields": {f: field_ok(kind, out.get(f), expected[f]) for f, kind in task["fields"].items()}}


# ---------- provenance ----------

def sh(*cmd):
    try:
        return subprocess.run(cmd, capture_output=True, text=True, timeout=10).stdout.strip() or None
    except Exception:
        return None


def get_json(url, data=None):
    try:
        req = urllib.request.Request(url, json.dumps(data).encode() if data else None,
                                     {"content-type": "application/json"})
        with urllib.request.urlopen(req, timeout=10) as r:
            return json.load(r)
    except Exception:
        return None


def server_info(base_url, model):
    """Best-effort server/model identity: ollama version, digest, quantization; /v1/models for anything else."""
    host = re.sub(r"/v1/?$", "", base_url.rstrip("/"))
    listed = (get_json(f"{base_url.rstrip('/')}/models") or {}).get("data", [])
    info = {"model": next((m for m in listed if m.get("id") == model), None)}  # never the full local model list
    ver = get_json(f"{host}/api/version")
    if ver:
        info["ollama_version"] = ver.get("version")
        tags = get_json(f"{host}/api/tags") or {}
        info["digest"] = next((m["digest"] for m in tags.get("models", []) if m["name"] == model), None)
        info["details"] = (get_json(f"{host}/api/show", {"model": model}) or {}).get("details")
        loaded = (get_json(f"{host}/api/ps") or {}).get("models", [])
        info["context_length"] = next((m.get("context_length") for m in loaded if m["name"] == model), None)
    return info


def run_config(a, names, extra):
    # only settings that change what a result means; --limit and --timeout may differ between resumes
    config = {"model": a.model, "base_url": a.base_url, "extra": extra, "constrained": not a.no_schema,
              "scorer_version": SCORER_VERSION, "task_hashes": {n: task_hash(n, a.split) for n in names}}
    # only recorded when set, so existing manifests stay resumable
    if a.instructions_in_user:
        config["instructions_in_user"] = True
    if a.split != "test":
        config["split"] = a.split
    return config


def write_manifest(label_dir, config):
    manifest = {
        "config": config,
        "created": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "host": {"platform": platform.platform(), "macos": platform.mac_ver()[0] or None,
                 "macos_build": sh("sw_vers", "-buildVersion"), "machine": platform.machine(),
                 "hw_model": sh("sysctl", "-n", "hw.model"), "cpu": sh("sysctl", "-n", "machdep.cpu.brand_string"),
                 "memory_bytes": sh("sysctl", "-n", "hw.memsize"), "python": platform.python_version()},
        "server": server_info(config["base_url"], config["model"]),
    }
    (label_dir / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")


# ---------- run ----------

def read_records(path):
    """Parse a results file, dropping blank and truncated lines left by an interrupted write."""
    if not path.exists():
        return []
    recs = []
    for line in path.read_text().splitlines():
        try:
            recs.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return recs


def check_resumable(old, new):
    """A resumed run must use the same settings. -> task names whose data changed since their results were saved"""
    strip = lambda c: {k: v for k, v in c.items() if k != "task_hashes"}
    if strip(old) != strip(new):
        return None
    return [n for n, h in new["task_hashes"].items() if old["task_hashes"].get(n, h) != h]


def cmd_run(a):
    extra = json.loads(a.extra) if a.extra else {}
    names = a.tasks.split(",") if a.tasks else sorted(p.name for p in TASKS.iterdir() if (p / SPLITS[a.split]).exists())
    label_dir = RESULTS / a.label
    if a.overwrite and label_dir.exists():
        shutil.rmtree(label_dir)
    label_dir.mkdir(parents=True, exist_ok=True)
    config = run_config(a, names, extra)
    mpath = label_dir / "manifest.json"
    if mpath.exists():
        old = json.loads(mpath.read_text())["config"]
        changed = check_resumable(old, config)
        if changed is None:
            sys.exit(f"results/{a.label} was produced with different settings; use a new --label or pass --overwrite")
        for name in changed:  # task data changed: old answers were scored against different items
            print(f"[{a.label}] {name}: task data changed, discarding old results", file=sys.stderr)
            (label_dir / f"{name}.jsonl").unlink(missing_ok=True)
        config["task_hashes"] = {**old["task_hashes"], **config["task_hashes"]}
    elif any(label_dir.glob("*.jsonl")):
        sys.exit(f"results/{a.label} has results but no manifest; use a new --label or pass --overwrite")
    write_manifest(label_dir, config)

    for name in names:
        task_dir, task, items = load_task(name, a.split)
        if a.limit:
            items = items[: a.limit]
        out = label_dir / f"{name}.jsonl"
        recs = read_records(out)
        if a.retry_errors:
            recs = [r for r in recs if r["raw"] is not None]
        out.write_text("".join(json.dumps(r) + "\n" for r in recs))  # rewrite clean (drops partial lines)
        done = {r["id"] for r in recs}
        todo = [i for i in items if i["id"] not in done]
        print(f"[{a.label}] {name}: {len(todo)} to run ({len(done)} cached)", file=sys.stderr)
        with out.open("a") as f:
            for n, item in enumerate(todo, 1):
                body = request_body(a.model, task, user_content(task_dir, task, item), extra, not a.no_schema,
                                    a.instructions_in_user)
                raw, err, secs = call(a.base_url, body, a.timeout)
                rec = {"id": item["id"], "raw": raw, "error": err, "seconds": round(secs, 3),
                       "expected": item["expected"], **score(task, raw, item["expected"])}
                f.write(json.dumps(rec) + "\n")
                f.flush()
                print(f"  {n}/{len(todo)} {item['id']} {outcome(rec)} {secs:.1f}s", file=sys.stderr)
    write_manifest(label_dir, config)  # again, now that the model is loaded (records ollama's context_length)


# ---------- report ----------

def wilson(k, n, z=1.96):
    if not n:
        return 0.0, 0.0
    p, d = k / n, 1 + z * z / n
    m, h = (p + z * z / (2 * n)) / d, z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return max(0.0, m - h), min(1.0, m + h)


def mcnemar_p(b, c):
    """Exact two-sided McNemar p-value from discordant counts b and c."""
    n = b + c
    if not n:
        return 1.0
    return min(1.0, 2 * sum(math.comb(n, i) for i in range(min(b, c) + 1)) / 2 ** n)


def label_split(label_dir):
    m = label_dir / "manifest.json"
    return json.loads(m.read_text())["config"].get("split", "test") if m.exists() else "test"


def rescored(label_dir, name):
    """Re-score saved raw outputs against current task data. -> (records by id, stale)"""
    split = label_split(label_dir)
    if not (TASKS / name / SPLITS[split]).exists():
        return {}, True
    _, task, items = load_task(name, split)
    exp = {i["id"]: i["expected"] for i in items}
    recs = {r["id"]: {**r, **score(task, r["raw"], exp[r["id"]])}
            for r in read_records(label_dir / f"{name}.jsonl") if r["id"] in exp}
    manifest = label_dir / "manifest.json"
    stale = (not manifest.exists()
             or json.loads(manifest.read_text())["config"]["task_hashes"].get(name) != task_hash(name, split))
    return recs, stale


def cmd_report(a):
    rows, by = [], {}
    for label_dir in sorted(p for p in RESULTS.glob("*") if p.is_dir()):
        for f in sorted(label_dir.glob("*.jsonl")):
            recs, stale = rescored(label_dir, f.stem)
            if not recs:
                continue
            by[(f.stem, label_dir.name)] = recs
            vals = list(recs.values())
            n, total = len(vals), len(load_task(f.stem, label_split(label_dir))[2])
            oc = [outcome(r) for r in vals]
            k = oc.count("correct")
            lo, hi = wilson(k, n)
            answered = [r for r in vals if r["json_ok"]]
            fa = statistics.mean(statistics.mean(r["fields"].values()) for r in answered) if answered else 0.0
            ok_secs = [r["seconds"] for r in vals if r["raw"] is not None]
            flags = ("" if n == total else f" (incomplete {n}/{total})") + (" (stale)" if stale else "")
            rows.append((f.stem, label_dir.name + flags, n, k / n, lo, hi, fa, oc.count("wrong"), oc.count("schema"),
                         oc.count("invalid_json"), oc.count("refusal"), oc.count("overflow"), oc.count("transport"),
                         statistics.median(ok_secs) if ok_secs else float("nan")))
    print("| task | model | n | all fields correct | 95% CI | field accuracy | wrong | schema fail | invalid JSON | refused | overflow | errors | median s |")
    print("|---|---|---|---|---|---|---|---|---|---|---|---|---|")
    for t, m, n, ex, lo, hi, fa, w, s, j, rf, ov, e, sec in sorted(rows):
        print(f"| {t} | {m} | {n} | {ex:.1%} | {lo:.0%}-{hi:.0%} | {fa:.1%} | {w} | {s} | {j} | {rf} | {ov} | {e} | {sec:.2f} |")
    if a.vs:
        print(f"\nPaired comparison against {a.vs} on items both answered (exact McNemar test):\n")
        print("| task | model | both correct | only model | only baseline | neither | p |")
        print("|---|---|---|---|---|---|---|")
        ok = lambda r: outcome(r) == "correct"
        for (t, m), recs in sorted(by.items()):
            base = by.get((t, a.vs))
            if m == a.vs or not base:
                continue
            ids = recs.keys() & base.keys()
            both = sum(ok(recs[i]) and ok(base[i]) for i in ids)
            only_m = sum(ok(recs[i]) and not ok(base[i]) for i in ids)
            only_b = sum(ok(base[i]) and not ok(recs[i]) for i in ids)
            print(f"| {t} | {m} | {both} | {only_m} | {only_b} | {len(ids) - both - only_m - only_b} | {mcnemar_p(only_m, only_b):.3f} |")


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run", help="run tasks against one model")
    r.add_argument("--label", required=True, help="results/<label>/ directory name")
    r.add_argument("--base-url", required=True, help="OpenAI-compatible base URL, e.g. http://localhost:11434/v1")
    r.add_argument("--model", required=True)
    r.add_argument("--tasks", help="comma-separated task names (default: all)")
    r.add_argument("--limit", type=int, help="first N items per task")
    r.add_argument("--split", choices=SPLITS, default="test", help="test (frozen, default) or dev (for prompt tuning)")
    r.add_argument("--extra", help="JSON merged into the request body, e.g. '{\"reasoning_effort\":\"none\"}'")
    r.add_argument("--timeout", type=float, default=300)
    r.add_argument("--retry-errors", action="store_true", help="re-run items that failed with a transport error or refusal")
    r.add_argument("--overwrite", action="store_true", help="delete results/<label>/ before running")
    r.add_argument("--instructions-in-user", action="store_true",
                   help="send task instructions in the user message instead of a system message")
    r.add_argument("--no-schema", action="store_true",
                   help="omit response_format and put the schema in the system prompt (measures the model without "
                        "the backend's constrained decoding)")
    r.set_defaults(fn=cmd_run)
    rp = sub.add_parser("report", help="markdown table of all results, re-scored with the current scorer")
    rp.add_argument("--vs", metavar="LABEL", help="add a paired comparison of every model against LABEL")
    rp.set_defaults(fn=cmd_report)
    a = p.parse_args()
    a.fn(a)


if __name__ == "__main__":
    main()
