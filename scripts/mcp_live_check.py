#!/usr/bin/env python3
"""Drive the local MCP connector exactly as the ChatGPT desktop app does.

Called by scripts/check-mcp-connector.sh, which creates the fictional
fixtures first and passes their ids in as one JSON argument. This file spawns
mcp/ggd_odoo_mcp.py as a subprocess and speaks newline-delimited JSON-RPC to
it over a pipe, so what is proven here is the same path the desktop app uses,
not a Python function call that happens to share the code.

It also probes Odoo DIRECTLY with the same API key for the operations that
must be refused. That distinction is the whole point: the connector's
allowlist is one boundary and the integration user's Odoo access rights are
the other, and only the second one still holds if the key ever leaks.

Nothing here prints the API key. Everything from Odoo goes through the
connector's own scrub() before it reaches a line of output.
"""

import importlib.util
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MODULE_PATH = os.path.join(ROOT, "mcp", "ggd_odoo_mcp.py")
PYTHON = "/usr/bin/python3"

_spec = importlib.util.spec_from_file_location("ggd_odoo_mcp", MODULE_PATH)
connector = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(connector)

PASSED = []
FAILED = []


def check(label, ok, detail=""):
    if ok:
        PASSED.append(label)
        print("  PASS  %s" % label)
    else:
        FAILED.append(label)
        print("  FAIL  %s%s" % (label, ("  -- %s" % detail) if detail else ""))
    return bool(ok)


def section(title):
    print("")
    print(title)
    print("-" * len(title))


class Server(object):
    """One connector subprocess, spoken to over stdin/stdout."""

    def __init__(self, env_overrides=None):
        env = dict(os.environ)
        env.update(env_overrides or {})
        self.proc = subprocess.Popen(
            [PYTHON, MODULE_PATH],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=subprocess.PIPE, env=env,
            universal_newlines=True, bufsize=1,
        )
        self._next_id = 0

    def request(self, method, params=None):
        self._next_id += 1
        message = {"jsonrpc": "2.0", "id": self._next_id, "method": method}
        if params is not None:
            message["params"] = params
        self.proc.stdin.write(json.dumps(message) + "\n")
        self.proc.stdin.flush()
        line = self.proc.stdout.readline()
        if not line:
            raise RuntimeError(
                "the connector exited: %s"
                % (self.proc.stderr.read() or "no stderr")[:500]
            )
        return json.loads(line)

    def notify(self, method):
        self.proc.stdin.write(
            json.dumps({"jsonrpc": "2.0", "method": method}) + "\n"
        )
        self.proc.stdin.flush()

    def call(self, name, arguments=None):
        """Returns (payload, is_error) the way the desktop app sees it."""
        response = self.request(
            "tools/call", {"name": name, "arguments": arguments or {}}
        )
        if "error" in response:
            return response["error"], True
        result = response["result"]
        return json.loads(result["content"][0]["text"]), result.get("isError", False)

    def close(self):
        try:
            self.proc.stdin.close()
            self.proc.wait(timeout=10)
        except Exception:
            self.proc.kill()


def raw_json2(client, model, method, payload):
    """Talk to Odoo without the connector, to test Odoo's own boundary."""
    request = urllib.request.Request(
        "%s/json/2/%s/%s" % (client.url, model, method),
        data=json.dumps(payload).encode("utf-8"),
        method="POST",
    )
    request.add_header("Content-Type", "application/json")
    request.add_header("X-Odoo-Database", client.database)
    request.add_header("Authorization", "Bearer %s" % client.api_key())
    try:
        response = urllib.request.urlopen(request, timeout=30)
        return response.getcode(), json.loads(response.read() or b"null")
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", "replace")
        try:
            parsed = json.loads(body)
        except ValueError:
            parsed = {"message": body}
        return exc.code, parsed


def refused(client, label, model, method, payload, expect_status, expect_text):
    status, body = raw_json2(client, model, method, payload)
    message = client.scrub(str(body.get("message", body)))[:200]
    check(
        "%s -- Odoo refuses it (HTTP %s)" % (label, expect_status),
        status == expect_status and expect_text.lower() in message.lower(),
        "got HTTP %s: %s" % (status, message),
    )


def main():
    fixtures = json.loads(sys.argv[1])
    lead_id = fixtures["lead_id"]
    lead_name = fixtures["lead_name"]
    dnc_id = fixtures["dnc_id"]
    doomed_id = fixtures["doomed_id"]

    server = Server()
    client = connector.OdooClient()

    section("1. Handshake and tool discovery")
    init = server.request("initialize", {
        "protocolVersion": "2025-06-18",
        "capabilities": {},
        "clientInfo": {"name": "ggd-live-check", "version": "1.0"},
    })
    server.notify("notifications/initialized")
    check("initialize returns a protocol version and server name",
          init["result"]["serverInfo"]["name"] == "ggd-odoo",
          json.dumps(init)[:200])
    tools = server.request("tools/list")["result"]["tools"]
    names = sorted(t["name"] for t in tools)
    check("seven tools are advertised", len(tools) == 7, ", ".join(names))
    writes = [t["name"] for t in tools
              if not t["annotations"].get("readOnlyHint")]
    check("exactly two tools are marked as writes",
          sorted(writes) == ["ggd_create_lead", "ggd_save_qualification"],
          str(writes))

    section("2. Authentication")
    status, is_error = server.call("ggd_connection_status")
    ok = check("the stored key authenticates", not is_error,
               json.dumps(status)[:300])
    if ok:
        print("        %s as %s, %s open opportunities visible"
              % (status["database"], status["login"],
                 status["open_opportunities_visible"]))
    else:
        print("")
        print("Cannot continue without a working key. Nothing was written.")
        server.close()
        return 1

    section("3. Finding and reading a fictional customer")
    found, is_error = server.call(
        "ggd_search_records", {"query": "GGD-MCP-TEST", "limit": 10}
    )
    ids = [r["id"] for r in found.get("records", [])]
    check("the fictional opportunity is found by name",
          not is_error and lead_id in ids, json.dumps(found)[:300])
    check("the result carries a clear record identifier",
          any(r.get("record") == "crm.lead,%d" % lead_id
              for r in found.get("records", [])))
    check("the result reports the total number of matches",
          isinstance(found.get("total_matching"), int))

    detail, is_error = server.call(
        "ggd_get_opportunity", {"opportunity_id": lead_id, "history_limit": 5}
    )
    check("the opportunity reads back by id",
          not is_error and detail["opportunity"]["name"] == lead_name,
          json.dumps(detail)[:300])
    check("its chatter history comes with it",
          "messages" in detail.get("history", {}),
          json.dumps(detail.get("history"))[:200])
    check("free text is returned under a 'text' key, labelled untrusted",
          "text" in detail["opportunity"] and "untrusted" in detail)

    section("4. Pagination and incomplete results")
    page1, _ = server.call("ggd_search_records", {"limit": 1, "offset": 0})
    total = page1.get("total_matching") or 0
    check("one record per page is honoured", page1.get("returned") <= 1)
    if total > 1:
        check("more pages are announced, not hidden",
              page1.get("has_more") is True
              and page1.get("next_page_offset") == 1,
              json.dumps(page1)[:200])
        page2, _ = server.call("ggd_search_records", {"limit": 1, "offset": 1})
        first = [r["id"] for r in page1.get("records", [])]
        second = [r["id"] for r in page2.get("records", [])]
        check("the second page is a different record", first != second,
              "%s vs %s" % (first, second))
    over = server.call("ggd_search_records", {"limit": 9999})[0]
    check("an oversized limit is clamped and said so",
          over.get("limit") == connector.MAX_LIMIT and "limit_note" in over,
          json.dumps({k: over.get(k) for k in ("limit", "limit_note")}))

    section("5. Reports")
    pipeline, is_error = server.call("ggd_pipeline_report", {"group_by": "stage"})
    check("the pipeline report groups by stage",
          not is_error and isinstance(pipeline.get("groups"), list),
          json.dumps(pipeline)[:300])
    check("the pipeline report says whether it is complete",
          isinstance(pipeline.get("complete"), bool))
    if pipeline.get("groups"):
        print("        %d groups, %s open opportunities, expected revenue %s"
              % (len(pipeline["groups"]),
                 pipeline["totals"]["opportunities_counted"],
                 pipeline["totals"]["expected_revenue"]))
    by_person, is_error = server.call(
        "ggd_pipeline_report", {"group_by": "salesperson"}
    )
    check("the pipeline report regroups by salesperson", not is_error)

    followup, is_error = server.call("ggd_followup_report", {"limit": 10})
    check("the follow-up report returns overdue activities",
          not is_error and "records" in followup, json.dumps(followup)[:300])
    check("the follow-up report reports what it left out",
          "suppressed_on_this_page" in followup)
    if followup.get("records"):
        print("        %d of %d overdue activities on this page"
              % (followup["returned"], followup["total_matching"]))

    section("6. Creating a lead from a researched company")
    # A fresh name per run. The teardown archives fixtures rather than
    # deleting them, so a stable name would be found archived on the next run
    # and the create path would never be exercised twice.
    run_tag = time.strftime("%Y%m%d-%H%M%S")
    company = "[GGD-MCP-TEST] Fictional Fence Works GmbH %s" % run_tag
    source_url = "https://fence-works.ggd-mcp-test.invalid/home"

    # Every forbidden field the outbound gate is made of is passed in here on
    # purpose. The schema does not declare them, so a correct connector must
    # ignore them and produce an unapproved, undrafted, unclaimed record.
    created, is_error = server.call("ggd_create_lead", {
        "company_name": company,
        "source_url": source_url,
        "contact_name": "A. Fictional",
        "job_title": "Head of Fictional Procurement",
        "email": "einkauf@fence-works.ggd-mcp-test.invalid",
        "city": "Berlin",
        "country": "Germany",
        "industry": "Fictional fencing systems",
        "product_focus": "Fictional welded mesh panels.",
        "lead_source_note": "Created by the MCP connector live check. Not real.",
        "ggd_outreach_approved": True,
        "ggd_do_not_contact": True,
        "ggd_draft_body": "Dear sir",
        "ggd_last_send_key": "1:deadbeef",
    })
    ok = check("a researched company becomes a new opportunity",
               not is_error and created.get("created") is True,
               json.dumps(created)[:400])
    new_lead_id = (created.get("opportunity") or {}).get("id")
    if ok:
        print("        created crm.lead,%s at stage %r"
              % (new_lead_id, (created.get("opportunity") or {}).get("stage")))
    check("it lands at Target Identified",
          (created.get("opportunity") or {}).get("stage") == "Target Identified",
          json.dumps(created.get("opportunity"))[:200])
    check("it is not yet qualified",
          (created.get("opportunity") or {}).get("qualification_state")
          == "pending")
    gate = created.get("outbound_gate") or {}
    check("the outbound gate is shut on the new record",
          gate.get("outreach_approved") is False
          and gate.get("has_draft") is False
          and gate.get("has_send_key") is False
          and gate.get("do_not_contact") is False
          and gate.get("contact_basis") is None,
          json.dumps(gate))
    check("the forbidden fields passed in were ignored, not stored",
          "deadbeef" not in json.dumps(created))
    check("it points at ggd_save_qualification as the next step",
          "ggd_save_qualification" in created.get("next_step", ""))

    again, is_error = server.call("ggd_create_lead", {
        "company_name": company, "source_url": source_url,
    })
    check("asking again does not create a duplicate",
          not is_error and again.get("created") is False
          and again.get("status") == "already_in_crm",
          json.dumps(again)[:300])
    check("it hands back the record that already exists",
          new_lead_id in [r.get("id") for r in
                          again.get("existing_opportunities", [])],
          json.dumps(again.get("existing_opportunities"))[:300])

    bad_url, is_error = server.call("ggd_create_lead", {
        "company_name": "[GGD-MCP-TEST] Never Created", "source_url": "fercelik.com",
    })
    check("a source_url that is not a web address is refused",
          is_error and bad_url.get("error") == "invalid_argument",
          json.dumps(bad_url)[:200])

    secretish, is_error = server.call("ggd_create_lead", {
        "company_name": "[GGD-MCP-TEST] Never Created Either",
        "source_url": "https://example.invalid/x",
        "lead_source_note": "portal api_key: abc123",
    })
    check("a value that looks like a credential is refused",
          is_error and secretish.get("error") == "invalid_argument",
          json.dumps(secretish)[:200])

    if new_lead_id:
        qualified, is_error = server.call("ggd_save_qualification", {
            "opportunity_id": new_lead_id,
            "fit_score": 68,
            "confidence": 0.82,
            "fit_summary": "Fictional assessment of a fictional company.",
            "personalization_angle": "Fictional angle. Connector test only.",
            "source_url": source_url,
        })
        check("the created lead can then be qualified",
              not is_error and qualified.get("status") == "saved"
              and (qualified.get("stored") or {}).get("qualification_state")
              == "ready",
              json.dumps(qualified)[:300])
        after = server.call(
            "ggd_get_opportunity",
            {"opportunity_id": new_lead_id, "history_limit": 0},
        )[0]
        after_ggd = (after.get("opportunity") or {}).get("ggd") or {}
        check("qualifying it still did not open the outbound gate",
              after_ggd.get("outreach_approved") is False
              and after_ggd.get("draft_status") == "empty"
              and after_ggd.get("do_not_contact") is False,
              json.dumps(after_ggd)[:300])

    section("7. Saving a qualification (fictional record only)")
    high, is_error = server.call("ggd_save_qualification", {
        "opportunity_id": lead_id,
        "fit_score": 74,
        "confidence": 0.85,
        "fit_summary": "Fictional test assessment. Not a real evaluation.",
        "personalization_angle": "Fictional angle for connector testing only.",
        "source_url": "https://ggd-mcp-test.invalid/about",
        "industry": "Fictional test industry",
        "recommended_buyer_roles": ["Head of Fictional Procurement"],
    })
    check("a confident assessment is saved",
          not is_error and high.get("status") == "saved",
          json.dumps(high)[:300])
    check("the saved values are read back from Odoo",
          high.get("stored", {}).get("fit_score") == 74 and
          high.get("stored", {}).get("qualification_state") == "ready",
          json.dumps(high.get("stored"))[:300])
    check("the shared ggd_ai_confidence field is disclosed",
          "reply analysis" in high.get("confidence_field_note", ""))

    low, is_error = server.call("ggd_save_qualification", {
        "opportunity_id": lead_id,
        "fit_score": 41,
        "confidence": 0.55,
        "fit_summary": "Fictional low-confidence assessment. Not real.",
        "personalization_angle": "Fictional angle, deliberately uncertain.",
    })
    check("a low-confidence assessment is still SAVED",
          not is_error and low.get("saved") is True and
          low.get("status") == "saved_needs_review",
          json.dumps(low)[:300])
    check("Odoo's false return is reported as saved, not as a failure",
          low.get("odoo_return_value") is False and low.get("retry") is False)
    check("it is routed to human review in Odoo",
          low.get("stored", {}).get("qualification_state") == "review" and
          low.get("stored", {}).get("qualification_needs_review") is True,
          json.dumps(low.get("stored"))[:300])
    check("the answer tells the caller not to retry",
          "Do not call this tool again" in low.get("message", ""))

    bad, is_error = server.call("ggd_save_qualification", {
        "opportunity_id": lead_id, "fit_score": 140, "confidence": 0.9,
        "fit_summary": "x", "personalization_angle": "y",
    })
    check("an out-of-range fit score is refused before Odoo is touched",
          is_error and bad.get("error") == "invalid_argument",
          json.dumps(bad)[:200])

    section("8. Operations the connector does not offer")
    unknown = server.request("tools/call", {
        "name": "ggd_send_email", "arguments": {}
    })
    check("an invented tool name is rejected",
          unknown.get("error", {}).get("code") == -32602,
          json.dumps(unknown)[:200])
    for model, method in (
        ("crm.lead", "write"),
        ("crm.lead", "unlink"),
        ("res.partner", "create"),
        ("crm.lead", "action_ggd_approve_outreach"),
        ("crm.lead", "ggd_claim_send_key"),
        ("mail.mail", "send"),
        ("res.users", "search_read"),
    ):
        try:
            client.call(model, method)
            check("the connector refuses %s.%s" % (model, method), False,
                  "it did not refuse")
        except connector.ConnectorError as exc:
            check("the connector refuses %s.%s" % (model, method),
                  exc.kind == "not_allowed", exc.message[:120])

    section("9. Operations Odoo itself refuses for this user")
    refused(client, "approve outreach", "crm.lead",
            "action_ggd_approve_outreach", {"ids": [lead_id]},
            403, "Outreach approver")
    refused(client, "clear Do not contact", "crm.lead", "write",
            # crm.lead's own write() override names the argument "values",
            # and JSON-2 binds by the signature it finds on the model.
            {"ids": [dnc_id], "values": {"ggd_do_not_contact": False}},
            403, "Outreach approver")
    refused(client, "claim a send key", "crm.lead", "ggd_claim_send_key",
            {"ids": [lead_id], "send_key": "%d:live-check" % lead_id},
            422, "approv")
    refused(client, "delete an opportunity", "crm.lead", "unlink",
            {"ids": [doomed_id]}, 403, "not allowed to delete")

    section("10. A missing or expired key")
    absent = Server({"GGD_KEYCHAIN_SERVICE": "ggd-odoo-mcp-does-not-exist"})
    absent.request("initialize", {"protocolVersion": "2025-06-18",
                                  "capabilities": {},
                                  "clientInfo": {"name": "x", "version": "1"}})
    payload, is_error = absent.call("ggd_connection_status")
    check("a missing key fails safely with a usable message",
          is_error and payload.get("error") == "credentials_unavailable",
          json.dumps(payload)[:200])
    check("the failure names the fix without naming a secret",
          "add-generic-password" in payload.get("hint", ""))
    key = client.api_key()
    check("no output anywhere contained the API key",
          key not in json.dumps(payload) and len(key) > 8)
    absent.close()

    server.close()

    print("")
    print("=" * 74)
    print("%d passed, %d failed" % (len(PASSED), len(FAILED)))
    if FAILED:
        for label in FAILED:
            print("  FAILED: %s" % label)
    print("=" * 74)
    return 1 if FAILED else 0


if __name__ == "__main__":
    sys.exit(main())
