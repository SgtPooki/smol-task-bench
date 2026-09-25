#!/usr/bin/env python3
"""Build tasks/contact-extraction-v2: harder generated emails with exact labels.

Harder than v1: forwarded threads whose quoted message carries another person's signature, obfuscated
email addresses, phone extensions, both a mobile and a direct line, and "Last, First" signatures.
All names, companies, and numbers are invented; emails use example.com/net/org, phones the 555-01xx range.

  python3 scripts/make_contacts_v2.py [N]
"""
import json, random, sys
from pathlib import Path

N = int(sys.argv[1]) if len(sys.argv) > 1 else 60
OUT = Path(__file__).resolve().parent.parent / "tasks" / "contact-extraction-v2"
rng = random.Random(20260925)

FIRST = ["Alice", "Bob", "Carmen", "Deepak", "Elena", "Farid", "Grace", "Hiro", "Ines", "Jonas", "Keiko", "Luis",
         "Maya", "Nikolai", "Olga", "Priya", "Quinn", "Rafael", "Sana", "Uma", "Viktor", "Wen", "Yara", "Zoe"]
LAST = ["Okafor", "Lindqvist", "Moreau", "Nakamura", "Patel", "Rossi", "Schmidt", "Tanaka", "Varga", "Whitfield",
        "Achebe", "Brennan", "Castillo", "Dubois", "Eriksen", "Fontaine", "Gallagher", "Haddad", "Ivanova", "Jensen"]
COMPANIES = ["Northwind Robotics", "Bluefern Analytics", "Cobalt Harbor Logistics", "Juniper Lane Studio",
             "Quarry Peak Energy", "Silverline Clinics", "Tidewater Software", "Oakridge Legal Partners"]
TLDS = ["example.com", "example.net", "example.org"]


def phone():
    area, line = rng.choice(["212", "415", "617", "303", "503"]), f"01{rng.randint(0, 99):02d}"
    fmt = rng.choice(["({a}) 555-{l}", "{a}-555-{l}", "+1 {a} 555 {l}", "{a}.555.{l}"])
    return fmt.format(a=area, l=line), f"{area}555{line}"


def person():
    first, last = rng.choice(FIRST), rng.choice(LAST)
    return first, last


def contact():
    """-> dict with a signature block and the exact expected values."""
    first, last = person()
    company = rng.choice(COMPANIES)
    domain = company.lower().split()[0] + "." + rng.choice(TLDS)
    local = rng.choice([f"{first}.{last}", f"{first[0]}{last}", first]).lower()
    email = f"{local}@{domain}"
    shown_email = email
    if rng.random() < 0.4:  # obfuscated address
        shown_email = f"{local} at {domain.replace('.', ' dot ')}"
    mobile, mobile_digits = phone()
    direct, direct_digits = phone()
    lines = [f"{last}, {first}" if rng.random() < 0.3 else f"{first} {last}", company]
    if rng.random() < 0.5:  # both numbers: the mobile is the one to extract
        lines += [f"Direct: {direct} ext. {rng.randint(100, 499)}", f"Mobile: {mobile}"]
        rng.shuffle(lines[-2:])
    else:
        lines.append(f"{rng.choice(['Mobile', 'Cell'])}: {mobile}")
    if rng.random() < 0.5:
        lines.append(f"{rng.choice(['Main office', 'Fax'])}: {phone()[0]}")
    lines.append(shown_email if rng.random() < 0.5 else f"Email: {shown_email}")
    return {"block": "\n".join(lines),
            "expected": {"name": f"{first} {last}", "email": email, "phone": mobile_digits, "company": company}}


def item(i):
    sender, quoted = contact(), contact()
    while quoted["expected"]["name"] == sender["expected"]["name"]:
        quoted = contact()
    reply = rng.choice(["Forwarding this so you have the full history. I can take the call on Friday.",
                        "Adding my notes below; the numbers in the original are out of date.",
                        "See the thread below. Please use my details going forward, not the ones quoted."])
    if rng.random() < 0.7:  # forwarded thread: the quoted message has someone else's signature
        text = (f"{reply}\n\n{rng.choice(['Best,', 'Thanks,', 'Regards,'])}\n{sender['block']}\n\n"
                f"---------- Forwarded message ----------\n"
                f"Hi team, the updated schedule is attached.\n\n{quoted['block']}")
    else:
        text = f"{reply}\n\n{rng.choice(['Best,', 'Thanks,', 'Regards,'])}\n{sender['block']}"
    return {"id": f"contact2-{i:03d}", "text": text, "expected": sender["expected"]}


OUT.mkdir(parents=True, exist_ok=True)
items = [item(i) for i in range(N)]
(OUT / "items.jsonl").write_text("".join(json.dumps(x, ensure_ascii=False) + "\n" for x in items))
(OUT / "task.json").write_text(json.dumps({
    "name": "contact",
    "description": "Harder generated emails: forwarded threads with a second signature, obfuscated emails, extensions, mobile plus direct lines, and 'Last, First' names (scripts/make_contacts_v2.py). Labels are exact by construction.",
    "instructions": "You extract the sender's contact details from an email. The sender is the person who wrote the newest message at the top; ignore signatures inside forwarded or quoted messages. name is the sender's name as 'First Last' even if the signature writes 'Last, First'. email is the sender's address in normal form (for example 'alice at acme dot example dot com' is alice@acme.example.com). phone is the sender's mobile or cell number as digits only with no country code or extension (for example '(415) 555-0142' is 4155550142); if both a mobile and a direct line are listed, use the mobile; ignore main office and fax lines. company is the sender's company name as written.",
    "prompt": "Email:\n{text}",
    "schema": {"type": "object", "properties": {"name": {"type": "string"}, "email": {"type": "string"},
               "phone": {"type": "string"}, "company": {"type": "string"}},
               "required": ["name", "email", "phone", "company"], "additionalProperties": False},
    "fields": {"name": "exact", "email": "exact", "phone": "digits", "company": "exact"},
}, indent=2, ensure_ascii=False) + "\n")
print(f"wrote {len(items)} items to {OUT}")
