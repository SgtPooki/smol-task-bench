#!/usr/bin/env python3
"""Build tasks/receipts from the CORD-v2 test split (CC-BY-4.0, naver-clova-ix/cord-v2).

Receipts are Indonesian; prices use '.' or ',' as thousands separators, so expected values are integers.
"""
import json, re, sys, time, urllib.error, urllib.request
from pathlib import Path

N = int(sys.argv[1]) if len(sys.argv) > 1 else 40
OUT = Path(__file__).resolve().parent.parent / "tasks" / "receipts"
API = "https://datasets-server.huggingface.co/rows?dataset=naver-clova-ix/cord-v2&config=default&split=test"


def get(url, tries=4):
    for i in range(tries):
        try:
            return urllib.request.urlopen(url, timeout=60).read()
        except urllib.error.HTTPError as e:
            if e.code < 500 or i == tries - 1:
                raise
            time.sleep(2 ** i)


def subs(m):
    sub = m.get("sub") or []
    return [sub] if isinstance(sub, dict) else sub


def amount(s):
    s = re.sub(r"[.,]\d{2}$", "", (s or "").strip())  # '365000.00' -> cents; 3-digit groups are thousands
    digits = re.sub(r"[^\d]", "", s)
    return int(digits) if digits else None


(OUT / "images").mkdir(parents=True, exist_ok=True)
items = []
for offset in range(0, 100, 20):
    rows = json.loads(get(f"{API}&offset={offset}&length=20"))["rows"]
    for row in rows:
        idx, r = row["row_idx"], row["row"]
        gt = json.loads(r["ground_truth"])["gt_parse"]
        total = amount((gt.get("total") or {}).get("total_price"))
        menu = gt.get("menu") or []
        menu = [menu] if isinstance(menu, dict) else menu
        if total is None or not menu:
            continue  # unlabeled total: can't score
        img = OUT / "images" / f"cord-test-{idx:03d}.jpg"
        img.write_bytes(get(r["image"]["src"]))
        items.append({"id": f"cord-test-{idx:03d}", "image": f"images/{img.name}",
                      # every printed item line, including add-on lines CORD nests under "sub"
                      "expected": {"total": total, "itemCount": sum(1 + len(subs(m)) for m in menu)}})
        if len(items) == N:
            break
    if len(items) == N:
        break

(OUT / "items.jsonl").write_text("".join(json.dumps(i) + "\n" for i in items))
print(f"wrote {len(items)} items to {OUT}")
