import json, re
from collections import Counter
from pathlib import Path

HERE = Path(__file__).parent
gold, text = {}, {}
for l in (HERE / "author-labels.jsonl").read_text().splitlines():  # labels as they were when annotated
    it = json.loads(l)
    gold[it["id"]], text[it["id"]] = it["expected"], it["text"]


def norm(k, v):
    if v is None or v == "null":
        return None
    if k == "startTime" and isinstance(v, str):
        return v[:5]
    if k == "durationMinutes":
        try:
            return int(v) or None  # treat 0 as "none"
        except (TypeError, ValueError):
            return None
    return v.strip().lower() if isinstance(v, str) else v


ann = {}
for f in sorted(HERE.glob("*.jsonl")):
    if f.stem == "author-labels" or f.stem.startswith("dev"):
        continue
    rows = {}
    for line in f.read_text().splitlines():
        m = re.search(r"\{.*\}", line)
        if not m:
            continue
        try:
            o = json.loads(m.group(0))
        except json.JSONDecodeError:
            continue
        if o.get("id") in gold:
            rows[o["id"]] = o
    ann[f.stem] = rows

print("annotator coverage and per-field agreement with author labels:")
for name, rows in ann.items():
    pairs = [(k, norm(k, rows[i].get(k)) == norm(k, g[k])) for i, g in gold.items() if i in rows for k in g]
    item_ok = sum(all(norm(k, rows[i].get(k)) == norm(k, g[k]) for k in g) for i, g in gold.items() if i in rows)
    print(f"  {name:8} items {len(rows):3}/90  fields agree {sum(o for _, o in pairs)}/{len(pairs)}  items fully agree {item_ok}/{len(rows)}")

print("\nitems to adjudicate (majority disagrees with author, or labelers split, or >=2 flag ambiguous):")
flagged = 0
for i, g in gold.items():
    votes = {n: r[i] for n, r in ann.items() if i in r}
    if not votes:
        continue
    issues = []
    for k in g:
        c = Counter(json.dumps(norm(k, v.get(k))) for v in votes.values())
        top, cnt = c.most_common(1)[0]
        if json.loads(top) != norm(k, g[k]) and cnt > len(votes) / 2:
            issues.append(f"{k}: author={g[k]!r} majority={json.loads(top)!r} ({cnt}/{len(votes)})")
        elif len(c) > 1 and c.get(json.dumps(norm(k, g[k])), 0) <= len(votes) / 2:
            issues.append(f"{k}: author={g[k]!r} split={dict(c)}")
    amb = [f"{n}: {v.get('note', '')}" for n, v in votes.items() if v.get("ambiguous")]
    if issues or len(amb) >= 2:
        flagged += 1
        print(f"\n[{i}] {text[i][:140]}")
        for s in issues:
            print("   *", s)
        for s in amb:
            print("   ?", s[:200])
print(f"\n{flagged} items flagged")
