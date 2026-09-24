#!/usr/bin/env python3
"""Build tasks/contact-extraction: generated email signatures with exact labels and distractor contacts.

All names, companies, and numbers are invented; emails use example.com/net/org and phones use the 555-01xx range.

  python3 scripts/make_contacts.py [N]
"""
import json, random, sys
from pathlib import Path

N = int(sys.argv[1]) if len(sys.argv) > 1 else 60
OUT = Path(__file__).resolve().parent.parent / "tasks" / "contact-extraction"
rng = random.Random(20260924)

FIRST = ["Alice", "Bob", "Carmen", "Deepak", "Elena", "Farid", "Grace", "Hiro", "Ines", "Jonas", "Keiko", "Luis",
         "Maya", "Nikolai", "Olga", "Priya", "Quinn", "Rafael", "Sana", "Tomás", "Uma", "Viktor", "Wen", "Yara"]
LAST = ["Okafor", "Lindqvist", "Moreau", "Nakamura", "Patel", "Rossi", "Schmidt", "Tanaka", "Varga", "Whitfield",
        "Achebe", "Brennan", "Castillo", "Dubois", "Eriksen", "Fontaine", "Gallagher", "Haddad", "Ivanova", "Jensen"]
COMPANIES = ["Northwind Robotics", "Bluefern Analytics", "Cobalt Harbor Logistics", "Juniper Lane Studio",
             "Quarry Peak Energy", "Silverline Clinics", "Tidewater Software", "Oakridge Legal Partners"]
TLDS = ["example.com", "example.net", "example.org"]
TITLES = ["Operations Manager", "Senior Engineer", "Account Executive", "Head of Research", "Paralegal",
          "Customer Success Lead", "Office Coordinator", "Product Designer"]


def phone():
    """-> (formatted, digits) in the reserved 555-01xx range, formatted several ways."""
    area, line = rng.choice(["212", "415", "617", "303", "503"]), f"01{rng.randint(0, 99):02d}"
    fmt = rng.choice(["({a}) 555-{l}", "{a}-555-{l}", "+1 {a} 555 {l}", "{a}.555.{l}"])
    return fmt.format(a=area, l=line), f"{area}555{line}"


def person():
    first, last = rng.choice(FIRST), rng.choice(LAST)
    return first, last, f"{first} {last}"


def item(i):
    first, last, name = person()
    company = rng.choice(COMPANIES)
    domain = company.lower().split()[0] + "." + rng.choice(TLDS)
    email = rng.choice([f"{first}.{last}", f"{first[0]}{last}", f"{first}"]).lower().replace("á", "a") + "@" + domain
    direct, digits = phone()
    office, _ = phone()
    label = rng.choice(["Mobile", "Direct", "Cell", "Tel"])
    lines = [rng.choice(["Best,", "Thanks,", "Cheers,", "Regards,", "Talk soon,"]), "", name,
             f"{rng.choice(TITLES)} | {company}" if rng.random() < 0.5 else f"{rng.choice(TITLES)}\n{company}",
             f"{label}: {direct}"]
    if rng.random() < 0.6:  # distractor: shared office or fax line
        lines.append(f"{rng.choice(['Main office', 'Fax', 'Front desk'])}: {office}")
    lines.append(email if rng.random() < 0.5 else f"Email: {email}")
    body = rng.choice(["Following up on the invoice from last week; the corrected copy is attached.",
                       "Can we move Thursday's call to the afternoon?",
                       "Here are the notes from today's site visit.",
                       "Looping in my colleague for the scheduling details."])
    if "colleague" in body or rng.random() < 0.3:  # distractor: another person's contact in the thread
        other = name
        while other == name:
            _, _, other = person()
        oe = other.split()[0].lower() + "@" + domain
        body += f" (cc {other}, {oe})"
    return {"id": f"contact-{i:03d}", "text": body + "\n\n" + "\n".join(lines),
            "expected": {"name": name, "email": email, "phone": digits, "company": company}}


OUT.mkdir(parents=True, exist_ok=True)
items = [item(i) for i in range(N)]
(OUT / "items.jsonl").write_text("".join(json.dumps(x, ensure_ascii=False) + "\n" for x in items))
(OUT / "task.json").write_text(json.dumps({
    "name": "contact",
    "description": "Generated email bodies with the sender's signature, plus distractor phone lines and cc'd colleagues (scripts/make_contacts.py). Labels are exact by construction.",
    "instructions": "You extract the sender's contact details from an email. name is the sender's full name as written in the signature. email is the sender's email address. phone is the sender's own direct, mobile, or cell number as digits only with no country code (for example '(415) 555-0142' is 4155550142); ignore main office, front desk, and fax lines. company is the sender's company name as written. Ignore contact details of anyone cc'd.",
    "prompt": "Email:\n{text}",
    "schema": {"type": "object", "properties": {"name": {"type": "string"}, "email": {"type": "string"},
               "phone": {"type": "string"}, "company": {"type": "string"}},
               "required": ["name", "email", "phone", "company"], "additionalProperties": False},
    "fields": {"name": "exact", "email": "exact", "phone": "digits", "company": "exact"},
}, indent=2, ensure_ascii=False) + "\n")
print(f"wrote {len(items)} items to {OUT}")
