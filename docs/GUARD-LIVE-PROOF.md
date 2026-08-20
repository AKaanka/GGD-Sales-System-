# Guard Live Proof — duplicate send-key claim on the running system

**Purpose.** Prove that addon 19.0.1.4.0's atomic claim guard actually stops a
second claim *on the live n8n workflow*, not just in the unit tests.

**Time.** About 30 minutes.

**Safety.** Nothing here can send email: the SMTP node is disabled for the whole
procedure. Only `.invalid` fixtures are used. No workflow is activated.

---

## Why this test exists

The addon's unit tests prove the guard works inside Odoo. They do not prove the
live workflow reaches it.

The deployed node **"Claim send key before SMTP"** does **not** call
`ggd_claim_send_key()`. It performs an ordinary Odoo record update. The guard in
19.0.1.4.0 was deliberately placed in `crm.lead.write()` so that this plain
update hits it too — but that has never been observed on the running system.
Until it is, duplicate-send protection is a design claim, not a result.

**The one subtlety that makes this test non-obvious.** The workflow already has
an n8n-level check, the If node **"Send key unused?"**. On a straightforward
second run, that node re-reads the record, sees the key, and routes to the
blocked-note branch — so the claim node is never reached and the database guard
never fires. You would observe a block, but you would have proved the *n8n
check*, not the *database guard*.

Those are different controls, and only one of them survives two executions
running at the same time. The n8n check reads a snapshot taken several RPCs
earlier; two simultaneous runs can both read an empty key and both pass it. The
database guard is the one that holds under a race.

So this procedure **deliberately disables the If node** for the second run. That
is not cheating — it is exactly the state a racing second execution is in: its
stale snapshot said "unused" while the database already held the claim.

---

## Before you touch n8n

Three warnings from `docs/PROJECT-STATUS.md`. All three have already cost time
on this project.

> ⚠ **Close every stale n8n editor tab first.** n8n executes the workflow copy
> loaded in the browser, not necessarily the saved one, and an open editor tab
> can re-save over changes made elsewhere.

> ⚠ **Reload the workflow before running it.** Verify a change by re-reading it
> after saving. A workflow that looks correct on screen may not be the one that
> runs.

> ⚠ **Deactivating a workflow can silently fail.** `GGD 98t` once read
> `active: false` while still firing every minute for at least seven cycles. On
> an outbound workflow that would send while appearing switched off. Confirm by
> watching the executions list, not by reading the toggle.

Also note: **manual runs bypass the shared error handler.** Scheduled runs do
not. Do not expect an error-handler record from this procedure — its absence is
expected and is not a finding.

---

## Step 0 — Confirm the workflow is inactive

1. Open n8n and go to the workflow list.
2. Find **GGD 03 - Approved Send and Record (Manual Test)**.
3. Confirm the Active toggle is **off**.
4. Open **Executions** and confirm no runs have appeared in the last 15 minutes.
   The schedule trigger fires every 15 minutes when active; an empty list is
   your real confirmation that it is off.

**Do not continue if any recent execution appears.** Stop and report it.

---

## Step 1 — Create the fixture in Odoo

The guard checks the *stored* approval state under its lock, so the fixture must
genuinely pass the outbound gate. Approving through the button is what stamps
the approver, the approval time and the basis-verified time — all three are
required.

1. Open Odoo → **CRM** → **Opportunities** → **New**.
2. Set:
   - **Opportunity**: `GUARD-PROOF duplicate claim`
   - **Email**: any address on a `.invalid` domain, e.g.
     `guard-proof@ggd-qa.invalid`
3. Save.
4. Open the **GGD Intelligence** tab → **Outreach control** and set:
   - **Contact basis**: `Prior express consent — opt-in on file`
   - **Contact-basis note**: a real sentence of at least 20 characters, e.g.
     `Fixture for guard proof 2026-08-20, no real opt-in, .invalid only.`
   - **Do not contact**: unticked
5. Save.
6. Click **Approve Outreach** in the header.
7. Confirm on the form that **Approved by**, **Approved at** and **Contact
   basis verified at** are now all filled in. If any is blank, the claim will be
   refused for that reason instead of the duplicate reason, and the test will
   not prove what you want.
8. **Write down the record's numeric ID** — it is the number at the end of the
   browser URL, after `id=`.

---

## Step 2 — Point the workflow at the fixture

1. Open **GGD 03 - Approved Send and Record (Manual Test)**.
2. Open the node **"Test input - Fictional Opportunity"**.
3. Set `opportunity_id` to the ID from step 1.8.
4. Save.
5. **Reload the page** and reopen the node to confirm the value stuck.

---

## Step 3 — Disable the SMTP node

This is the safety interlock. With it disabled, no message can leave the system
even if every guard in the chain failed.

1. Right-click the node **"Send an Email"** → **Deactivate** (or select it and
   press `D`). It should grey out.
2. Save.
3. **Reload the page** and confirm it is still greyed out.

---

## Step 4 — Run 1: establish the claim

1. Click **Test workflow**.
2. Expected behaviour:
   - `Get current opportunity before outbound gate` — green
   - `Apply fresh outbound approval gate` — green
   - `Outbound allowed?` — green, takes the **true** branch
   - `Lawful basis and recipient present?` — green, **true** branch
   - `Send key unused?` — green, **true** branch
   - **`Claim send key before SMTP` — green.** This is the claim being written.
   - `Send an Email` — greyed out, skipped
   - `Prepare send audit record.` — **red is expected here.** With SMTP
     disabled there is no Message-ID, so that node throws
     *"SMTP reported success but returned no Message-ID. Do not retry
     automatically; check Zoho Sent first."* That is correct behaviour and not
     a defect. Run 1 only needs the claim node to be green.
3. In Odoo, reload the fixture record → **GGD Intelligence** tab → **Reply
   analysis** group. Confirm:
   - **Last send key** is now filled, in the form `<id>-<approval timestamp>`
   - **Last outbound send at** is now filled

**Do not continue until Last send key is visibly set.** If it is blank, the
claim did not happen and there is nothing to duplicate.

---

## Step 5 — Put the workflow into the racing state

Disable the n8n-level pre-check so the run reaches the database guard, exactly
as a simultaneous second execution would.

1. Right-click the node **"Send key unused?"** → **Deactivate**. It greys out.
2. Save.
3. **Reload the page** and confirm both `Send an Email` and `Send key unused?`
   are greyed out.

---

## Step 6 — Run 2: the proof

1. Click **Test workflow**.
2. **`Claim send key before SMTP` must turn RED.**
3. Open that node's error panel. It must contain this text:

```
This send key is already claimed for this opportunity. A message for this
approval has been sent or is in flight, so this send must stop before SMTP.
Check the sent-mail folder before revoking and re-approving.
```

n8n may wrap it in an Odoo fault envelope, and may re-flow the line breaks. The
wording is what matters, not the layout.

4. **Confirm nothing after it ran.** `Send an Email`, `Prepare send audit
   record.`, `Record send and consume approval.` and `GGD controlled send audit`
   must all show **no execution data** for this run. The run stopped at the
   claim, before SMTP.
5. In Odoo, reload the fixture record and confirm **Last send key** and **Last
   outbound send at** are **unchanged** from step 4.3. The refused claim wrote
   nothing.

If the node is red with the text above and nothing downstream executed, **the
guard is proven on the live system.**

### If it goes differently

| What you see | What it means |
| --- | --- |
| Claim node **green** on run 2 | The guard did not fire. **Stop and report.** This is the failure the whole exercise exists to detect. |
| Red, but a *different* message about approval, basis or Do-not-contact | The fixture's stored state is not sendable. Re-check step 1.7, then redo from step 1. |
| Red with *"A send key cannot be claimed in the same write that grants outreach approval"* | The claim node is also writing the approval flag. Not expected in this workflow — report it. |
| Workflow blocks earlier, at `Send key unused?` | That node is still enabled. Redo step 5. |

---

## Step 7 — Put the workflow back

Do this immediately, before you forget. A workflow left with its guards disabled
is worse than no test at all.

1. Right-click **"Send key unused?"** → **Activate**.
2. Right-click **"Send an Email"** → **Activate**.
3. Save.
4. **Reload the page** and confirm neither node is greyed out.
5. Confirm the workflow's Active toggle is still **off**.

---

## Step 8 — Rollback: clear the claimed key

The fixture now carries a claim and cannot be re-sent under that approval. The
addon deliberately permits clearing the key — only a *non-empty* key is treated
as a claim, so writing a blank value is allowed and is the intended recovery
path.

`ggd_last_send_key` is read-only on the Odoo form, so this is done through n8n.

1. Create a new workflow, name it `GGD 99t - clear send key (throwaway)`.
2. Add a **Manual Trigger**.
3. Add an **Odoo** node using the existing `odooApi` credential:
   - **Resource**: `Opportunity`
   - **Operation**: `Update`
   - **Opportunity ID**: the fixture ID from step 1.8
   - **Fields to Send** → add `ggd_last_send_key`, with the value set by
     expression to `{{ false }}`

   Use the expression rather than an empty text box. An empty box may be
   dropped before it reaches Odoo; `{{ false }}` is the same pattern the
   existing "Record send and consume approval." node uses for
   `ggd_outreach_approved`, so it is known to work here.
4. Run it once. The node should be green.
5. In Odoo, reload the fixture and confirm **Last send key** is now empty.
6. **Delete the throwaway workflow.** Surplus workflow copies are already on
   the cleanup list; do not add another.

**Simpler alternative.** Instead of clearing the key, click **Revoke Approval**
and then **Approve Outreach** again on the fixture. That produces a new approval
timestamp, therefore a new key, therefore a claimable record — no throwaway
workflow needed. Note the key has one-second resolution, so revoke and
re-approve a few seconds apart, not in the same instant.

**Simplest of all.** Create a fresh fixture next time. These records are
disposable.

---

## Results checklist

Fill this in and keep it with the test pack.

```
GUARD LIVE PROOF — results
Date:  ____________________     Run by:  ____________________
Addon version:  19.0.1.4.0      Fixture record ID:  ____________
Fixture email domain is .invalid                        [ ] yes  [ ] no

STEP 0  Workflow inactive, no recent executions          [ ] yes  [ ] no

STEP 1  Approved by / Approved at / Basis verified at
        all populated after Approve Outreach             [ ] yes  [ ] no

STEP 3  "Send an Email" disabled and confirmed
        after a page reload                              [ ] yes  [ ] no

STEP 4  Run 1: "Claim send key before SMTP" green        [ ] yes  [ ] no
        Odoo shows Last send key populated               [ ] yes  [ ] no
        Value observed:  ____________________________________
        Odoo shows Last outbound send at populated       [ ] yes  [ ] no

STEP 5  "Send key unused?" disabled and confirmed
        after a page reload                              [ ] yes  [ ] no

STEP 6  Run 2: "Claim send key before SMTP" RED          [ ] yes  [ ] no
        Error text matches the duplicate-claim wording   [ ] yes  [ ] no
        "Send an Email" shows no execution data          [ ] yes  [ ] no
        "Prepare send audit record." not executed        [ ] yes  [ ] no
        "Record send and consume approval." not executed [ ] yes  [ ] no
        "GGD controlled send audit" not executed         [ ] yes  [ ] no
        Odoo record unchanged since step 4               [ ] yes  [ ] no

STEP 7  Both nodes re-enabled, confirmed after reload    [ ] yes  [ ] no
        Workflow Active toggle still off                 [ ] yes  [ ] no

STEP 8  Claim cleared, or fixture re-approved            [ ] yes  [ ] no
        Throwaway workflow deleted (if one was made)     [ ] n/a  [ ] yes

NO EMAIL WAS SENT AT ANY POINT                           [ ] confirmed

OVERALL:   [ ] PASS      [ ] FAIL      [ ] INCONCLUSIVE

Notes / anything unexpected:
______________________________________________________________________
______________________________________________________________________
______________________________________________________________________
```

---

## What a PASS does and does not establish

**Does establish.** The live n8n update node reaches the database guard, and a
second claim of the same key is refused before SMTP by Odoo itself, not by a
check in the workflow that a race could slip past.

**Does not establish.** That two *genuinely simultaneous* executions are
serialised. That property comes from the PostgreSQL `FOR UPDATE` row lock and
cannot be demonstrated by hand from the n8n UI — you cannot reliably start two
runs inside the same few milliseconds by clicking. It is covered by the addon's
unit tests and by the database's own guarantees. This procedure proves the
*route*; the lock provides the *simultaneity*.

**Also worth knowing.** If you ever take the alternative path and let the
`Send key unused?` node do the blocking, the review note it produces currently
renders with an **empty reason line**. That is a known open defect in the
blocked-note code path, not a symptom of the guard. It does not affect this
procedure, which deliberately routes around that node.
