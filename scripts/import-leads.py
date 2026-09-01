#!/usr/bin/env python3
"""Validate a CSV of real prospects and create them as Odoo leads.

    ./scripts/import-leads.py leads.csv             # dry run: validate only
    ./scripts/import-leads.py leads.csv --commit    # create them

Dry run is the default on purpose. Nothing is written until --commit.

Every rule enforced here mirrors a rule the addon or Workflow 1 enforces
later, so a row that passes this check cannot get stuck downstream:

  * ggd_source_url must be a public http(s) URL - Workflow 1's
    requirePublicHttpUrl guard rejects private hosts and non-HTTP schemes,
    and the fetch fails on domains that do not resolve.
  * contact_basis must not be one of GGD_NO_EMAIL_BASES
    (trade_fair_no_optin, referral, other). The addon refuses to approve
    those for email outreach - see crm_lead.py and
    docs/LAWFUL-CONTACT-PROCEDURE.md section 4.
  * contact_basis_note must be at least 20 characters and carry real
    evidence: a date, a source, a reference. The floor is the addon's
    GGD_CONTACT_BASIS_NOTE_MIN_LENGTH.

Created leads land at ggd_qualification_state = pending with no draft and
no approval, which is exactly what GGD-01 picks up. Nothing here sends
email or approves anything.
"""
import csv, json, os, re, subprocess, sys

SENDABLE_BASES = {"consent", "existing_customer", "inbound", "trade_fair"}
NO_EMAIL_BASES = {"trade_fair_no_optin", "referral", "other"}
NOTE_MIN = 20
REQUIRED = ["company_name", "contact_email", "source_url", "contact_basis", "contact_basis_note"]
OPTIONAL = ["industry", "notes"]
TEST_TLDS = (".invalid", ".test", ".example", ".localhost")
PRIVATE_HOST = re.compile(
    r"^(localhost|127\.|10\.|192\.168\.|172\.(1[6-9]|2\d|3[01])\.|169\.254\.|\[?::1\]?)", re.I)
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[A-Za-z]{2,}$")


def check_url(url):
    u = (url or "").strip()
    if not u:
        return "source_url is empty"
    m = re.match(r"^(https?)://([^/\s:]+)(:\d+)?(/.*)?$", u, re.I)
    if not m:
        return "source_url must start with http:// or https:// and have a host"
    host = m.group(2).lower()
    if PRIVATE_HOST.match(host):
        return f"source_url host '{host}' is private/internal; Workflow 1 blocks it"
    if "." not in host or host.endswith(".local"):
        return f"source_url host '{host}' is not a public domain"
    if host.endswith(TEST_TLDS):
        return f"source_url host '{host}' is a reserved test domain; the page fetch will fail"
    return None


TEMPLATE_MARKERS = ("replace me", "replace this", "example-company.invalid",
                    "replace-me@", "delete this row")


def check_row(i, row, seen_emails):
    errs = []
    for f in REQUIRED:
        if not (row.get(f) or "").strip():
            errs.append(f"{f} is empty")
    if errs:
        return errs

    # The template ships with one example row. Importing it unedited would put
    # a real-looking company into the CRM carrying an opt-in reference that
    # never existed. Catch it explicitly rather than relying on the operator
    # noticing.
    joined = " ".join((row.get(f) or "") for f in REQUIRED + OPTIONAL).lower()
    if any(m in joined for m in TEMPLATE_MARKERS):
        return ["this is the template's example row, not a real lead. "
                "Replace every field with your own data (and delete the example row)."]

    email = row["contact_email"].strip().lower()
    if not EMAIL_RE.match(email):
        errs.append(f"contact_email '{email}' is not a valid address")
    elif email.endswith(TEST_TLDS):
        errs.append(f"contact_email '{email}' is a reserved test domain, not a real prospect")
    if email in seen_emails:
        errs.append(f"contact_email '{email}' appears twice in this file (row {seen_emails[email]})")
    else:
        seen_emails[email] = i

    u = check_url(row["source_url"])
    if u:
        errs.append(u)

    basis = row["contact_basis"].strip().lower()
    if basis in NO_EMAIL_BASES:
        errs.append(
            f"contact_basis '{basis}' is not a lawful basis for a first marketing email. "
            "The addon will refuse to approve it. Call them instead, or record a real opt-in.")
    elif basis not in SENDABLE_BASES:
        errs.append(f"contact_basis '{basis}' unknown; use one of: {', '.join(sorted(SENDABLE_BASES))}")

    note = row["contact_basis_note"].strip()
    if len(note) < NOTE_MIN:
        errs.append(f"contact_basis_note is {len(note)} chars; needs at least {NOTE_MIN} and real evidence "
                    "(a date, a source, a reference) - not a restatement of the label")
    return errs


def main():
    args = [a for a in sys.argv[1:]]
    commit = "--commit" in args
    paths = [a for a in args if not a.startswith("--")]
    if len(paths) != 1:
        print(__doc__)
        return 2
    path = paths[0]
    if not os.path.isfile(path):
        print(f"ABORT: no such file: {path}", file=sys.stderr)
        return 1

    with open(path, newline="", encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))
    if not rows:
        print("ABORT: the CSV has no data rows", file=sys.stderr)
        return 1
    missing = [c for c in REQUIRED if c not in rows[0]]
    if missing:
        print(f"ABORT: missing required column(s): {', '.join(missing)}", file=sys.stderr)
        print(f"Expected header: {','.join(REQUIRED + OPTIONAL)}", file=sys.stderr)
        return 1

    good, bad, seen = [], [], {}
    for i, row in enumerate(rows, start=2):
        errs = check_row(i, row, seen)
        if errs:
            bad.append((i, row.get("company_name", "?"), errs))
        else:
            good.append({
                "company_name": row["company_name"].strip(),
                "contact_email": row["contact_email"].strip().lower(),
                "source_url": row["source_url"].strip(),
                "contact_basis": row["contact_basis"].strip().lower(),
                "contact_basis_note": row["contact_basis_note"].strip(),
                "industry": (row.get("industry") or "").strip(),
                "notes": (row.get("notes") or "").strip(),
            })

    print(f"Read {len(rows)} row(s) from {path}")
    print(f"  valid  : {len(good)}")
    print(f"  invalid: {len(bad)}")
    for i, name, errs in bad:
        print(f"\n  row {i} ({name[:40]}):")
        for e in errs:
            print(f"    - {e}")
    if bad:
        print("\nFix the rows above and re-run. Nothing was created.")
        return 1
    if not commit:
        print("\nDry run only - nothing created. Re-run with --commit to create these leads.")
        return 0

    payload = json.dumps(good)
    program = "ROWS = " + payload + "\n" + r'''
Lead = env["crm.lead"]
created, skipped = [], []
for r in ROWS:
    existing = Lead.with_context(active_test=False).search(
        [("email_from", "=ilike", r["contact_email"])], limit=1)
    if existing:
        skipped.append((existing.id, r["contact_email"]))
        continue
    vals = {
        "name": r["company_name"],
        "partner_name": r["company_name"],
        "type": "opportunity",
        "email_from": r["contact_email"],
        "ggd_source_url": r["source_url"],
        "ggd_contact_basis": r["contact_basis"],
        "ggd_contact_basis_note": r["contact_basis_note"],
    }
    if r["industry"]:
        vals["ggd_industry"] = r["industry"]
    if r["notes"]:
        vals["description"] = r["notes"]
    lead = Lead.create(vals)
    created.append((lead.id, r["contact_email"]))
env.cr.commit()
print("CREATED %d, SKIPPED %d (already present)" % (len(created), len(skipped)))
for i, e in created:
    print("  created id=%s %s" % (i, e))
for i, e in skipped:
    print("  skipped id=%s %s" % (i, e))
'''
    cmd = ["docker", "compose", "exec", "-T", "odoo", "/bin/bash", "-lc",
           'exec odoo shell --config=/tmp/ggd-odoo.conf -d "$ODOO_DB_NAME" --no-http']
    proc = subprocess.run(cmd, input=program, text=True,
                          cwd=os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    return proc.returncode


if __name__ == "__main__":
    sys.exit(main())
