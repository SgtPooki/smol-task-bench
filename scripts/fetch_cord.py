#!/usr/bin/env python3
"""Build tasks/receipts from the CORD-v2 test split (CC-BY-4.0, naver-clova-ix/cord-v2).

Receipts are Indonesian; prices use '.' or ',' as thousands separators, so expected values are integers.
"""
import argparse, hashlib, json, re, socket, sys, time, urllib.error, urllib.request
from pathlib import Path


def get(url, tries=4):
    for i in range(tries):
        try:
            return urllib.request.urlopen(url, timeout=60).read()
        except (urllib.error.HTTPError, urllib.error.URLError, socket.timeout) as e:
            if (isinstance(e, urllib.error.HTTPError) and e.code < 500) or i == tries - 1:
                raise
            time.sleep(2 ** i)


def subs(m):
    sub = m.get("sub") or []
    return [sub] if isinstance(sub, dict) else sub


def amount(s):
    if s is None:
        return None
    s = re.sub(r"[.,]\d{2}$", "", str(s).strip())  # '365000.00' -> cents; 3-digit groups are thousands
    digits = re.sub(r"[^\d]", "", s)
    return int(digits) if digits else None


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("N", type=int, nargs="?", default=40)
    parser.add_argument("--include-validation", action="store_true")
    args = parser.parse_args()
    N = args.N

    OUT = Path(__file__).resolve().parent.parent / "tasks" / "receipts"

    rev_info = json.loads(get("https://huggingface.co/api/datasets/naver-clova-ix/cord-v2"))
    revision = rev_info["sha"]
    API = f"https://datasets-server.huggingface.co/rows?dataset=naver-clova-ix/cord-v2&config=default&revision={revision}"

    (OUT / "images").mkdir(parents=True, exist_ok=True)
    items = []

    source_data = {
        "revision": revision,
        "images": {},
        "original_annotations": {},
        "excluded": []
    }

    splits = ["test"]
    if args.include_validation:
        splits.append("validation")

    for split in splits:
        offset = 0
        while True:
            resp_bytes = get(f"{API}&split={split}&offset={offset}&length=100")
            rows = json.loads(resp_bytes).get("rows", [])
            if not rows:
                break

            for row in rows:
                idx, r = row["row_idx"], row["row"]
                gt = json.loads(r["ground_truth"])["gt_parse"]
                total_obj = gt.get("total")
                total_price = total_obj.get("total_price") if isinstance(total_obj, dict) else None
                total = amount(total_price)
                menu = gt.get("menu") or []
                menu = [menu] if isinstance(menu, dict) else menu

                if total is None or not menu:
                    source_data["excluded"].append({"split": split, "row_idx": idx, "reason": "unlabeled total or empty menu"})
                    continue  # unlabeled total: can't score

                img_url = r["image"]["src"]
                img_bytes = get(img_url)
                img_hash = hashlib.sha256(img_bytes).hexdigest()

                img = OUT / "images" / f"cord-{split}-{idx:03d}.jpg"
                img.write_bytes(img_bytes)

                item_id = f"cord-{split}-{idx:03d}"
                items.append({
                    "id": item_id,
                    "image": f"images/{img.name}",
                    # every printed item line, including add-on lines CORD nests under "sub"
                    "expected": {"total": total, "itemCount": sum(1 + len(subs(m)) for m in menu)}
                })

                source_data["images"][item_id] = img_hash
                source_data["original_annotations"][item_id] = gt

                if len(items) == N:
                    break

            if len(items) == N:
                break
            offset += 100

        if len(items) == N:
            break

    if len(items) < N:
        print(f"Error: could only produce {len(items)} items, less than requested {N}.", file=sys.stderr)
        sys.exit(1)

    (OUT / "items.jsonl").write_text("".join(json.dumps(i) + "\n" for i in items))
    (OUT / "SOURCE.json").write_text(json.dumps(source_data, indent=2) + "\n")
    print(f"wrote {len(items)} items to {OUT}")
