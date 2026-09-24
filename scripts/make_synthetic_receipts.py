#!/usr/bin/env python3
"""Build tasks/receipts-synthetic: generated receipts rendered to PNG with headless Chromium.

Labels are exact by construction and the images can't be in any model's training data.
Set CHROME to a Chromium/Chrome binary if it isn't found automatically.

  python3 scripts/make_synthetic_receipts.py [N]
"""
import glob, html, json, os, random, shutil, subprocess, sys, tempfile
from datetime import date, timedelta
from pathlib import Path

N = int(sys.argv[1]) if len(sys.argv) > 1 else 40
OUT = Path(__file__).resolve().parent.parent / "tasks" / "receipts-synthetic"
rng = random.Random(20260923)

STORES = ["CORNER PANTRY", "Blue Heron Cafe", "NORTHSIDE HARDWARE", "Lumen Books", "Maple & Rye Bakery",
          "QUICKSTOP #214", "Harbor Noodle Bar", "GreenLeaf Market", "Tinker Electronics", "Sunday Deli"]
ITEMS = ["Oat Milk Latte", "Croissant", "AA Batteries 4pk", "Garden Hose 50ft", "Paperback Novel", "Sourdough Loaf",
         "Pad Thai", "Spring Rolls", "Bananas", "Greek Yogurt", "USB-C Cable", "Phone Case", "Turkey Club",
         "Iced Tea", "Wood Screws", "Duct Tape", "Notebook A5", "Green Curry", "Avocado", "Espresso"]
ADDONS = ["+ Extra shot", "+ Oat milk", "- No onion", "+ Add cheese", "+ Large", "- Sauce on side"]
# code, prefix, suffix, decimals, thousands sep, decimal sep, date format
CURRENCIES = [("USD", "$", "", 2, ",", ".", "%m/%d/%Y"), ("EUR", "", " €", 2, ".", ",", "%d.%m.%Y"),
              ("GBP", "£", "", 2, ",", ".", "%d/%m/%Y"), ("JPY", "¥", "", 0, ",", ".", "%Y/%m/%d")]
FONTS = ["'Courier New', monospace", "Menlo, monospace", "'Andale Mono', monospace", "Monaco, monospace"]


def money(cents, cur):
    _, pre, suf, dec, ts, ds, _ = cur
    whole, frac = divmod(cents, 100) if dec else (cents, 0)
    s = f"{whole:,}".replace(",", ts)
    return f"{pre}{s}{ds}{frac:02d}{suf}" if dec else f"{pre}{s}{suf}"


def receipt(i):
    cur = rng.choice(CURRENCIES)
    unit = 100 if cur[3] else 1  # JPY has no minor unit
    lines, n_lines, products = [], 0, 0
    subtotal = 0
    for _ in range(rng.randint(1, 7)):
        qty = rng.choice([1, 1, 1, 2, 3])
        price = rng.randint(1, 60) * unit * (1 if cur[3] else 100) + (rng.choice([0, 25, 49, 50, 99]) if cur[3] else 0)
        name = rng.choice(ITEMS)
        label = f"{qty} x {name}" if qty > 1 else name
        lines.append((label, money(price * qty, cur), False))
        subtotal += price * qty
        n_lines += 1
        products += 1
        if rng.random() < 0.25:  # zero-price add-on printed on its own line
            lines.append((rng.choice(ADDONS), money(0, cur), True))
            n_lines += 1
    discount = (subtotal * rng.choice([5, 10])) // 100 if rng.random() < 0.2 else 0
    taxable = subtotal - discount
    tax = (taxable * rng.choice([0, 6, 8, 10])) // 100
    tip = (taxable * rng.choice([10, 15])) // 100 if rng.random() < 0.2 else 0
    total = taxable + tax + tip
    d = date(2026, 1, 1) + timedelta(days=rng.randint(0, 250))
    while d.day <= 12:  # keep day/month order unambiguous
        d += timedelta(days=1)
    paid = ((total // (500 * unit)) + 1) * 500 * unit if rng.random() < 0.5 else None

    rows = "".join(f'<tr><td class="{"addon" if a else ""}">{html.escape(l)}</td><td>{html.escape(p)}</td></tr>'
                   for l, p, a in lines)
    summary = [("SUBTOTAL", money(subtotal, cur))]
    if discount:
        summary.append(("DISCOUNT", "-" + money(discount, cur)))
    if tax:
        summary.append(("TAX", money(tax, cur)))
    if tip:
        summary.append(("TIP", money(tip, cur)))
    summary_rows = "".join(f"<tr><td>{k}</td><td>{v}</td></tr>" for k, v in summary)
    pay = (f"<tr><td>CASH</td><td>{money(paid, cur)}</td></tr><tr><td>CHANGE</td><td>{money(paid - total, cur)}</td></tr>"
           if paid else "<tr><td>CARD ****" + str(rng.randint(1000, 9999)) + f"</td><td>{money(total, cur)}</td></tr>")
    printed_count = f"<p>ITEMS: {products}</p>" if rng.random() < 0.4 else ""  # counts products, not lines
    tilt, blur, bg = rng.uniform(-2.5, 2.5), rng.choice([0, 0, 0.3, 0.5]), rng.choice(["#6b5b4b", "#2f3b45", "#8a8a80"])
    page = f"""<!doctype html><meta charset="utf-8"><style>
body{{margin:0;background:{bg};padding:30px;font-family:{rng.choice(FONTS)};font-size:{rng.choice([14, 15, 16])}px}}
.r{{background:#fbfaf6;width:340px;padding:22px;transform:rotate({tilt:.2f}deg);filter:blur({blur}px);color:#222;
box-shadow:0 3px 12px rgba(0,0,0,.4)}} h1{{font-size:18px;text-align:center;margin:0 0 4px}}
p{{margin:2px 0;text-align:center}} table{{width:100%;border-collapse:collapse;margin:8px 0}}
td:last-child{{text-align:right}} td.addon{{padding-left:14px}} hr{{border:0;border-top:1px dashed #555}}
.t td{{font-weight:bold;font-size:1.15em}}</style>
<div class="r"><h1>{html.escape(rng.choice(STORES))}</h1><p>{d.strftime(cur[6])} {rng.randint(7, 21):02d}:{rng.randint(0, 59):02d}</p>
<hr><table>{rows}</table><hr><table>{summary_rows}<tr class="t"><td>TOTAL</td><td>{money(total, cur)}</td></tr>{pay}</table>
{printed_count}<p>THANK YOU</p></div>"""
    total_value = total / 100 if cur[3] else total
    height = 260 + 24 * (len(lines) + len(summary) + 3)
    return page, height, {"total": total_value, "currency": cur[0], "itemCount": n_lines, "date": d.isoformat()}


def chrome():
    found = os.environ.get("CHROME") or next(iter(sorted(glob.glob(os.path.expanduser(
        "~/Library/Caches/ms-playwright/chromium_headless_shell-*/chrome-headless-shell-*/chrome-headless-shell")))), None)
    for c in [found, "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome", shutil.which("chromium"),
              shutil.which("google-chrome")]:
        if c and Path(c).exists():
            return c
    sys.exit("no Chromium found; set CHROME=/path/to/chrome")


bin_ = chrome()
if (OUT / "images").exists():
    shutil.rmtree(OUT / "images")
(OUT / "images").mkdir(parents=True)
items = []
with tempfile.TemporaryDirectory() as tmp:
    for i in range(N):
        page, height, expected = receipt(i)
        src = Path(tmp) / f"r{i}.html"
        src.write_text(page)
        img = OUT / "images" / f"synth-{i:03d}.png"
        subprocess.run([bin_, "--headless", "--hide-scrollbars", "--disable-gpu", f"--screenshot={img}",
                        f"--window-size=460,{height}", src.as_uri()], check=True, capture_output=True, timeout=60)
        if not img.exists():
            sys.exit(f"screenshot failed for item {i}")
        items.append({"id": f"synth-{i:03d}", "image": f"images/{img.name}", "expected": expected})
(OUT / "items.jsonl").write_text("".join(json.dumps(i) + "\n" for i in items))
print(f"wrote {len(items)} items to {OUT}")
