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
    check("ten tools are advertised", len(tools) == 10, ", ".join(names))
    writes = [t["name"] for t in tools
              if not t["annotations"].get("readOnlyHint")]
    check("exactly four tools are marked as writes",
          sorted(writes) == ["ggd_create_lead", "ggd_opportunity_action",
                             "ggd_save_qualification",
                             "ggd_save_response_draft"],
          str(writes))
    check("the tool declarations stay inside the #65 budget",
          len(json.dumps(tools, separators=(",", ":"))) <= 12500,
          "%d characters" % len(json.dumps(tools, separators=(",", ":"))))

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

    for report_type in ("dashboard", "daily_action", "pipeline",
                        "qualification", "contact_coverage",
                        "outreach_readiness", "activity", "reply_delivery",
                        "industry_market", "data_quality"):
        report, is_error = server.call(
            "ggd_report", {"report_type": report_type, "limit": 10}
        )
        ok = check("ggd_report %s answers against live data" % report_type,
                   not is_error and report.get("report_type") == report_type,
                   json.dumps(report)[:300])
        if ok:
            # Every report must date itself, say how much of the truth it is
            # showing, and carry a warnings list even when it is empty.
            check("  ... with a date, a timezone and completeness",
                  report.get("as_of") and report.get("timezone")
                  and isinstance(report.get("complete"), bool)
                  and isinstance(report.get("warnings"), list),
                  json.dumps(report)[:300])
    dashboard, _ = server.call("ggd_report", {"report_type": "dashboard"})
    if dashboard.get("metrics"):
        print("        dashboard: %s scanned of %s matching, complete=%s"
              % (dashboard.get("scanned"), dashboard.get("total_matching"),
                 dashboard.get("complete")))

    for unavailable in ("conversion_funnel", "usage_efficiency"):
        report, is_error = server.call(
            "ggd_report", {"report_type": unavailable}
        )
        check("%s reports itself unavailable rather than zero" % unavailable,
              not is_error and report.get("available") is False
              and bool(report.get("reason")) and "metrics" not in report,
              json.dumps(report)[:300])

    coverage, _ = server.call("ggd_report",
                              {"report_type": "contact_coverage"})
    check("contact coverage marks source-backed coverage unavailable",
          "source_backed" in (coverage.get("unavailable") or {}),
          json.dumps(coverage)[:300])

    filtered, is_error = server.call("ggd_search_records", {
        "query": "GGD-MCP-TEST", "qualification_state": "pending",
        "has_email": True, "limit": 10,
    })
    check("the fixed search filters reach Odoo without a domain",
          not is_error and "total_matching" in filtered,
          json.dumps(filtered)[:300])
    wrong_model, is_error = server.call("ggd_search_records", {
        "record_type": "contact", "qualification_state": "ready",
    })
    check("a GGD filter on a contact is refused, not silently dropped",
          is_error and wrong_model.get("error") == "invalid_argument",
          json.dumps(wrong_model)[:300])

    sections, is_error = server.call("ggd_get_opportunity", {
        "opportunity_id": lead_id, "sections": ["identity", "qualification"],
    })
    check("an opportunity reads back by section",
          not is_error and sorted(sections.get("sections") or {})
          == ["identity", "qualification"],
          json.dumps(sections)[:300])
    check("an unrequested section is absent, not empty",
          "chatter" not in (sections.get("sections") or {}))

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

    section("8. Saving a reply draft (fictional record only)")
    reply_draft = (
        "Thank you for the fictional reply. Monday works for a short call."
    )
    saved, is_error = server.call("ggd_save_response_draft", {
        "opportunity_id": lead_id,
        "draft": reply_draft,
    })
    stored = saved.get("stored") or {}
    check("a reply draft is saved and read back",
          not is_error and saved.get("status") == "saved"
          and stored.get("stored_characters") == len(reply_draft)
          and stored.get("sent_characters") == len(reply_draft),
          json.dumps(saved)[:300])
    check("the write says plainly that it sent nothing",
          "Nothing was sent" in saved.get("message", ""),
          saved.get("message", ""))

    reply_view, is_error = server.call("ggd_get_opportunity", {
        "opportunity_id": lead_id,
        "sections": ["reply"],
        "detail_level": "full",
    })
    reply_text = (
        ((reply_view.get("sections") or {}).get("reply") or {})
        .get("text", {}).get("ggd_response_draft")
    )
    check("a later opportunity read still returns the saved draft",
          not is_error and reply_text == reply_draft,
          json.dumps(reply_view)[:300])

    section("9. Guarded opportunity actions (fictional record only)")
    # Every action below runs against the same fictional [GGD-MCP-TEST]
    # record, and each one is chained off the write_date the previous receipt
    # returned. That is deliberate: if a successful action did not hand back
    # the next concurrency value, this section could not be written without a
    # read between every step, and the whole sequence would fail here.
    run_key = "live-%d" % int(time.time())
    view, _err = server.call("ggd_get_opportunity", {
        "opportunity_id": lead_id, "sections": ["identity"],
        "history_limit": 0,
    })
    identity = (view.get("sections") or {}).get("identity") or {}
    stamp = identity.get("last_change")
    current_stage = identity.get("stage")
    check("the record read back carries a concurrency value",
          isinstance(stamp, str) and stamp,
          json.dumps(identity)[:200])

    def act(action, **arguments):
        arguments.update({
            "action": action, "opportunity_id": lead_id,
            "expected_write_date": arguments.pop("stamp"),
        })
        return server.call("ggd_opportunity_action", arguments)

    SOURCE = "https://fictional-panels.ggd-mcp-test.invalid/impressum"
    URL_A = "https://fictional-panels.ggd-mcp-test.invalid/contact-a"
    URL_B = "https://fictional-panels.ggd-mcp-test.invalid/contact-b"

    def enrich(url, stamp, overwrite=False):
        return act(
            "enrich_contact", stamp=stamp, contact={"contact_url": url},
            source_urls=[SOURCE], researched_at="2026-01-02 09:00:00",
            confidence=0.9, overwrite=overwrite,
        )

    receipt, is_error = enrich(URL_A, stamp)
    ok = check("source-backed contact enrichment is applied",
               not is_error and receipt.get("ok") is True,
               json.dumps(receipt)[:300])
    stamp = receipt.get("write_date") or stamp

    receipt, is_error = enrich(URL_A, stamp)
    check("the same value again is reported as unchanged",
          not is_error and receipt.get("status") == "unchanged",
          json.dumps(receipt)[:300])
    stamp = receipt.get("write_date") or stamp

    receipt, is_error = enrich(URL_B, stamp)
    check("a different stored value is a conflict, not an overwrite",
          receipt.get("ok") is False
          and receipt.get("reason_code") == "conflict"
          and receipt.get("conflicts") == ["contact_url"],
          json.dumps(receipt)[:300])

    receipt, is_error = enrich(URL_B, stamp, overwrite=True)
    check("an explicit overwrite replaces it", receipt.get("ok") is True,
          json.dumps(receipt)[:300])
    stamp = receipt.get("write_date") or stamp
    # Put the fixture back where this run found it, so the next run starts
    # from the same state rather than from whatever the last one left.
    receipt, is_error = enrich(URL_A, stamp, overwrite=True)
    stamp = receipt.get("write_date") or stamp

    receipt, is_error = enrich(URL_A, "2020-01-01 00:00:00")
    check("a stale write timestamp is refused whole",
          receipt.get("ok") is False
          and receipt.get("reason_code") == "stale_record"
          and receipt.get("write_date") == stamp,
          json.dumps(receipt)[:300])

    receipt, is_error = act(
        "enrich_contact", stamp=stamp, contact={"ggd_do_not_contact": True},
        source_urls=[SOURCE], researched_at="2026-01-02 09:00:00",
        confidence=0.9,
    )
    check("a field outside the contact allowlist is refused",
          is_error and receipt.get("error") == "invalid_argument",
          json.dumps(receipt)[:200])

    contact_args = {
        "channel": "call", "occurred_at": "2026-01-02 10:00:00",
        "summary": "Fictional call with the fixture company.",
        "idempotency_key": "%s-contact" % run_key,
    }
    receipt, is_error = act("record_manual_contact", stamp=stamp, **contact_args)
    first_event = receipt.get("contact_event_id")
    check("a manual contact is recorded",
          not is_error and receipt.get("ok") is True and first_event,
          json.dumps(receipt)[:300])
    stamp = receipt.get("write_date") or stamp
    receipt, is_error = act("record_manual_contact", stamp=stamp, **contact_args)
    check("repeating it with the same key creates nothing new",
          receipt.get("status") == "already_recorded"
          and receipt.get("contact_event_id") == first_event,
          json.dumps(receipt)[:300])

    activity_args = {
        "activity_type": "todo",
        "summary": "Fictional follow-up from the MCP live check",
        "deadline": "2026-12-31",
        "idempotency_key": "%s-activity" % run_key,
    }
    receipt, is_error = act("schedule_activity", stamp=stamp, **activity_args)
    first_activity = receipt.get("activity_id")
    check("a follow-up activity is scheduled",
          not is_error and receipt.get("ok") is True and first_activity,
          json.dumps(receipt)[:300])
    stamp = receipt.get("write_date") or stamp
    receipt, is_error = act("schedule_activity", stamp=stamp, **activity_args)
    check("repeating it with the same key returns the first activity",
          receipt.get("status") == "already_scheduled"
          and receipt.get("activity_id") == first_activity,
          json.dumps(receipt)[:300])

    draft_args = {
        "subject": "Fictional outreach subject (MCP live check)",
        "body": "A fictional outreach body written for the live check only.",
        "language": "de",
        "idempotency_key": "%s-draft" % run_key,
    }
    receipt, is_error = act("save_outreach_draft", stamp=stamp, **draft_args)
    first_version = receipt.get("draft_version")
    check("an outreach draft is saved but not approved",
          not is_error and receipt.get("ok") is True and first_version
          and receipt.get("approved_matches_draft") is False
          and receipt.get("approved_draft_version") is False,
          json.dumps(receipt)[:300])
    check("the receipt carries no draft body",
          "body" not in receipt and draft_args["body"] not in json.dumps(receipt),
          json.dumps(receipt)[:300])
    stamp = receipt.get("write_date") or stamp
    receipt, is_error = act("save_outreach_draft", stamp=stamp, **draft_args)
    check("repeating it with the same key mints no second version",
          receipt.get("status") == "already_saved"
          and receipt.get("draft_version") == first_version,
          json.dumps(receipt)[:300])
    stamp = receipt.get("write_date") or stamp

    receipt, is_error = act(
        "transition_stage", stamp=stamp, target_stage="Qualified",
        expected_stage="A stage this record is not in",
    )
    check("a stale expected stage stops the move",
          receipt.get("ok") is False
          and receipt.get("reason_code") == "stale_stage",
          json.dumps(receipt)[:300])

    receipt, is_error = act(
        "transition_stage", stamp=stamp, target_stage="Won",
        expected_stage=current_stage or "New",
    )
    check("a terminal stage cannot even be named",
          is_error and receipt.get("error") == "invalid_argument",
          json.dumps(receipt)[:200])

    # The suppressed fixture proves the same method refuses to touch a record
    # marked Do not contact, whatever is asked of it.
    dnc_view, _err = server.call("ggd_get_opportunity", {
        "opportunity_id": dnc_id, "sections": ["identity"], "history_limit": 0,
    })
    dnc_identity = (dnc_view.get("sections") or {}).get("identity") or {}
    suppressed, is_error = server.call("ggd_opportunity_action", {
        "action": "record_manual_contact", "opportunity_id": dnc_id,
        "expected_write_date": dnc_identity.get("last_change"),
        "channel": "email", "occurred_at": "2026-01-02 10:00:00",
        "summary": "This must not be recorded.",
        "idempotency_key": "%s-suppressed" % run_key,
    })
    check("a Do-not-contact record refuses every action",
          suppressed.get("ok") is False
          and suppressed.get("reason_code") == "suppressed",
          json.dumps(suppressed)[:300])

    section("10. Operations the connector does not offer")
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

    section("11. Operations Odoo itself refuses for this user")
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

    section("12. A missing or expired key")
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
