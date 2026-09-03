"""Tests for scripts/import-leads.py that need no Odoo and no Docker.

The --commit path builds a Python program and pipes it into `odoo shell`.
Until 2026-09-02 that program could not run: JSON booleans spliced into
Python source raised NameError before any lead was created. These tests
compile and execute the generated program against a stub `env`, so the
regression cannot come back unnoticed.

Run:  python3 -m unittest discover -s tests/scripts
"""
import importlib.util
import io
import unittest
from contextlib import redirect_stdout
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "import-leads.py"


def load_importer():
    spec = importlib.util.spec_from_file_location("import_leads", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class StubRecord:
    def __init__(self, record_id):
        self.id = record_id

    def __bool__(self):
        return self.id is not None


class StubLeadModel:
    """Enough of crm.lead for the generated program: search and create."""

    def __init__(self, existing_emails=(), existing_names=()):
        self.existing_emails = {e.lower() for e in existing_emails}
        self.existing_names = {n.lower() for n in existing_names}
        self.created = []

    def with_context(self, **_kwargs):
        return self

    def search(self, domain, limit=None):
        field, _op, value = domain[0]
        if field == "email_from" and value.lower() in self.existing_emails:
            return StubRecord(7)
        if field == "name" and value.lower() in self.existing_names:
            return StubRecord(8)
        return StubRecord(None)

    def create(self, vals):
        self.created.append(vals)
        return StubRecord(100 + len(self.created))


class StubCursor:
    def __init__(self):
        self.commits = 0

    def commit(self):
        self.commits += 1


class StubEnv:
    def __init__(self, lead_model):
        self.lead_model = lead_model
        self.cr = StubCursor()

    def __getitem__(self, name):
        assert name == "crm.lead", name
        return self.lead_model


def run_program(program, lead_model):
    env = StubEnv(lead_model)
    out = io.StringIO()
    with redirect_stdout(out):
        exec(compile(program, "<odoo-shell>", "exec"), {"env": env})
    return env, out.getvalue()


def sendable_row(**overrides):
    row = {
        "company_name": "Example Manufacturing GmbH",
        "research_only": False,
        "contact_email": "sales@example-manufacturing.de",
        "source_url": "https://www.example-manufacturing.de/",
        "contact_basis": "consent",
        "contact_basis_note": "Opt-in form dated 2026-08-12, reference OPT-2026-0812",
        "industry": "Metal fabrication",
        "notes": "Quoted 'don't' in notes to exercise escaping",
    }
    row.update(overrides)
    return row


def research_row(**overrides):
    row = sendable_row(research_only=True, contact_email="", contact_basis="",
                       contact_basis_note="", industry="", notes="")
    row.update(overrides)
    return row


class BuildShellProgramTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.importer = load_importer()

    def test_program_compiles_with_boolean_flags(self):
        # research_only is a boolean; JSON spells it `true`/`false`, which is
        # not Python. This is the exact shape that used to raise NameError.
        program = self.importer.build_shell_program([sendable_row(), research_row()])
        compile(program, "<odoo-shell>", "exec")

    def test_creates_sendable_lead_with_basis(self):
        program = self.importer.build_shell_program([sendable_row()])
        env, output = run_program(program, StubLeadModel())
        self.assertEqual(len(env.lead_model.created), 1)
        vals = env.lead_model.created[0]
        self.assertEqual(vals["email_from"], "sales@example-manufacturing.de")
        self.assertEqual(vals["ggd_contact_basis"], "consent")
        self.assertIn("2026-08-12", vals["ggd_contact_basis_note"])
        self.assertEqual(vals["ggd_industry"], "Metal fabrication")
        self.assertIn("don't", vals["description"])
        self.assertEqual(env.cr.commits, 1)
        self.assertIn("CREATED 1, SKIPPED 0", output)

    def test_research_only_lead_has_no_address_and_no_basis(self):
        program = self.importer.build_shell_program([research_row()])
        env, output = run_program(program, StubLeadModel())
        vals = env.lead_model.created[0]
        self.assertNotIn("email_from", vals)
        self.assertNotIn("ggd_contact_basis", vals)
        self.assertNotIn("ggd_contact_basis_note", vals)
        self.assertEqual(vals["ggd_source_url"], "https://www.example-manufacturing.de/")
        self.assertIn("CREATED 1, SKIPPED 0", output)

    def test_skips_existing_by_email_and_by_name(self):
        program = self.importer.build_shell_program([
            sendable_row(),
            research_row(company_name="Already Known AG",
                         source_url="https://www.already-known.de/"),
        ])
        model = StubLeadModel(existing_emails=["sales@example-manufacturing.de"],
                              existing_names=["Already Known AG"])
        env, output = run_program(program, model)
        self.assertEqual(env.lead_model.created, [])
        self.assertIn("CREATED 0, SKIPPED 2", output)
        self.assertIn("skipped id=7", output)
        self.assertIn("skipped id=8", output)

    def test_awkward_characters_survive_the_round_trip(self):
        note = 'Meeting 2026-08-12 — "quoted" \\ backslash, umlaut ü, tab\t, newline\nend'
        program = self.importer.build_shell_program([sendable_row(contact_basis_note=note)])
        env, _ = run_program(program, StubLeadModel())
        self.assertEqual(env.lead_model.created[0]["ggd_contact_basis_note"], note)


if __name__ == "__main__":
    unittest.main()
