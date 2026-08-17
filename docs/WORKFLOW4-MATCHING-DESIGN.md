# Workflow 4 — Reply Matching and Suppression Design

Status: **draft, not yet applied to any workflow.** Written 17 August 2026.

This document fixes the reply-matching rule and the suppression guard *before*
either is built, so the implementation pass is mechanical rather than
exploratory. It exists because every previous attempt to change Workflow 4 was
made directly on the canvas without a settled specification, and the resulting
improvisation is what damaged WIP copy 04b.

Applies to `GGD 04c` (`G6FzMSyFNRqYcguD`), then to live `GGD 04`
(`akXDPwB6sTW9304L`) once 04c passes A1–A4 and A9.

---

## 1. The contradiction being resolved

Two descriptions of the matching order are in circulation:

- [QA-INVESTIGATION-LOG.md](QA-INVESTIGATION-LOG.md) describes 04c as
  *sender-email search first, outbound-message/thread fallback second*.
- The partially-built code in 04c does the reverse: *Message-ID first, sender
  as fallback*.

Neither is quite right, because this is not a priority ordering. It is a
**two-key lookup**: the sender address produces a candidate set cheaply, and the
thread header confirms *which* candidate. They do different jobs.

Message-ID remains the stronger signal — it links to one specific outbound
message. Sender address is weaker: it can be a shared mailbox, a forwarded
reply, or a colleague answering from a different address. So sender narrows,
thread confirms.

## 2. Decision table

Evaluated in order. First matching row wins.

| # | Condition | Outcome | `matched_by` |
| --- | --- | --- | --- |
| 0 | `opportunity_id` supplied directly on the input item | Match | `explicit_id` |
| 1 | Exactly one sender candidate whose `ggd_last_message_id` appears in the reply's thread headers | Match | `thread` |
| 2 | More than one sender candidate, and exactly one of them matches on thread | Match | `thread` |
| 3 | Exactly one sender candidate, no usable thread header | Match | `sender_only` |
| 4 | No sender candidates, but a thread header resolves to exactly one opportunity | Match | `thread_fallback` |
| 5 | More than one sender candidate, no thread disambiguation | **Manual review** | — |
| 6 | Nothing found by either key | **Manual review** | — |

Row 0 exists for the fictional fixtures and manual test runs. It must never be
reachable from the live IMAP trigger, because that path does not supply an
opportunity ID. Keep it, but treat its presence as test-only.

Row 3 is the deliberate judgement call: a sender-only match **does** write, but
is tagged so an audit can find every record that was matched on the weaker key.
If sender-only matches later prove unreliable in practice, this is the single
row to change — turn it into manual review and nothing else moves.

Rows 5 and 6 write **nothing** to any Odoo record. One review note, naming every
candidate considered.

## 3. Confirmed node graph (read from the n8n database, 17 August 2026)

`GGD 04c` has 16 nodes. Verified by querying `workflow_entity.nodes` and
`workflow_entity.connections` directly, not by reading the canvas.

```
When clicking 'Execute workflow'
  └─► Test input - Fictional Reply
        └─► Validate and sanitize reply
              └─► Get many opportunities          (sender search, fans out 0–N)
                    └─► Get matched opportunity   (fetches ONE record)
                          └─► Evaluate reply match
                                ├─ true  ─► Basic LLM Chain ─► Code in JavaScript ─► If1
                                │                                                     ├─ true  ─► Update an opportunity ─► Create a record
                                │                                                     └─ false ─► Record invalid reply-analysis output
                                └─ false ─► Create a record1   (manual-review note)
```

Supporting nodes: `Anthropic Chat Model` and `Structured Output Parser` attach
to `Basic LLM Chain` on the AI ports.

All 16 nodes are present and accounted for, including `Code in JavaScript`.
This independently confirms the retraction recorded in
[QA-INVESTIGATION-LOG.md](QA-INVESTIGATION-LOG.md): the node that appeared to be
missing was lost from WIP copy 04b by an accidental deletion, and 04c — rebuilt
from `GGD 04` — has it.

There is no thread-fallback search node. Row 4 of the decision table has nowhere
to route yet, and test **A3** currently has nothing to exercise.

### 3.1 Ordering problem discovered

`Get matched opportunity` runs **before** `Evaluate reply match`. The workflow
fetches a record first and decides whether the match was valid afterwards.

That is backwards, and it is not merely inelegant. On the ambiguous-sender case
(A2), `Get matched opportunity` has already resolved and fetched *one* of the
candidates — chosen by an expression that falls back to
`$('Get many opportunities').first().json.id`, i.e. arbitrarily the first — before
anything has decided whether choosing at all was legitimate. The manual-review
outcome then depends on a downstream node declining to write, rather than on the
record never having been selected. That is a guard in the wrong place: it works
only for as long as every downstream write path remembers to check.

**Required rewiring**, to be applied with the code change:

```
Validate and sanitize reply
  └─► Get many opportunities
        └─► Evaluate reply match          ← decision moves here, before any fetch
              ├─ true  ─► Get matched opportunity ─► Basic LLM Chain ─► ...
              └─ false ─► Create a record1
```

`Get matched opportunity` then fetches on the id that `Evaluate reply match`
decided on (`{{ $json.opportunity_id }}`), and it is only reached when a match
was actually established. Keep **Execute Once** set on it.

## 4. `Evaluate reply match` — replacement code

Node names below are confirmed against the database read in section 3.

```js
// Inputs
const src = $('Validate and sanitize reply').first().json;

let candidates = [];
try {
  candidates = $('Get many opportunities').all()
    .map(i => i.json)
    .filter(r => r && r.id);
} catch (e) {
  candidates = []; // upstream node produced nothing
}

// Normalisation
const normEmail = (v) => {
  const s = String(v || '').trim().toLowerCase();
  const m = s.match(/<([^>]+)>/);
  return (m ? m[1] : s).trim();
};
const normMsgId = (v) => String(v || '').trim().replace(/^</, '').replace(/>$/, '');

const senderEmail = normEmail(src.sender_email || src.from || src.email_from);

const threadIds = []
  .concat(src.in_reply_to || [])
  .concat(String(src.references || '').split(/\s+/))
  .map(normMsgId)
  .filter(Boolean);

// Row 0 — explicit id (test path)
if (src.opportunity_id) {
  return [{ json: {
    matched: true,
    matched_by: 'explicit_id',
    opportunity_id: Number(src.opportunity_id),
    candidate_ids: candidates.map(c => c.id),
    review_reason: null,
  }}];
}

// Rows 1 and 2 — thread confirms among sender candidates
const threadHits = candidates.filter(c =>
  c.ggd_last_message_id && threadIds.includes(normMsgId(c.ggd_last_message_id))
);

if (threadHits.length === 1) {
  return [{ json: {
    matched: true,
    matched_by: 'thread',
    opportunity_id: threadHits[0].id,
    candidate_ids: candidates.map(c => c.id),
    review_reason: null,
  }}];
}

// Row 3 — single sender candidate, no usable thread header
if (candidates.length === 1 && threadHits.length === 0) {
  return [{ json: {
    matched: true,
    matched_by: 'sender_only',
    opportunity_id: candidates[0].id,
    candidate_ids: candidates.map(c => c.id),
    review_reason: null,
  }}];
}

// Row 4 — no sender candidates; defer to the thread-fallback search node
if (candidates.length === 0 && threadIds.length > 0) {
  return [{ json: {
    matched: false,
    needs_thread_fallback: true,
    matched_by: null,
    opportunity_id: null,
    thread_ids: threadIds,
    candidate_ids: [],
    review_reason: null,
  }}];
}

// Rows 5 and 6 — manual review
return [{ json: {
  matched: false,
  needs_thread_fallback: false,
  matched_by: null,
  opportunity_id: null,
  candidate_ids: candidates.map(c => c.id),
  review_reason: candidates.length > 1
    ? `Ambiguous sender ${senderEmail}: ${candidates.length} opportunities match (${candidates.map(c => `${c.id} ${c.name}`).join('; ')}). No thread header resolved it.`
    : `No opportunity found for sender ${senderEmail} and no usable thread header.`,
}}];
```

Set **Execute Once** on this node. It consumes a fan-out (`Get many
opportunities` returns 0–N items) and must produce exactly one decision.

### Thread-fallback branch (row 4)

`needs_thread_fallback: true` routes to a second Odoo search on
`ggd_last_message_id in thread_ids`. That search returns:

- exactly one record → match, `matched_by: 'thread_fallback'`
- zero or more than one → manual review

This is the branch test **A3** exercises. It does not exist yet in 04c.

## 5. Suppression guard (A9)

The known A9 defect is that `ggd_do_not_contact` persists correctly but
`ggd_suggested_next_action` still recommends further contact.

The earlier proposed fix was a ternary on that one field. **Reject that
approach.** It guards one field and silently fails to cover the next field
anyone adds — `response_draft`, follow-up activity creation, stage advancement.

Instead, branch on `ggd_do_not_contact` — but note *where*. The analysis must
still run for suppressed contacts, so the branch does not go before the LLM. It
goes on the **write** side, where the leak actually occurs: between
`Code in JavaScript` and the Odoo update.

```
Code in JavaScript
        │
        ▼
      If1                        (existing: valid analysis output?)
        ├─ false ─► Record invalid reply-analysis output
        │
        └─ true ──► If2: suppressed?      ggd_do_not_contact === true
                      │
                      ├─ true ──► Update an opportunity (restricted)
                      │             • ggd_reply_category, summary, confidence
                      │             • chatter note
                      │             • NO next action, NO draft
                      │             • NO follow-up activity
                      │             • NO stage change
                      │
                      └─ false ─► Update an opportunity ─► Create a record
                                    (existing full path, unchanged)
```

The suppressed path still classifies and records, because an inbound message
from a suppressed contact is meaningful — it may be a second objection, or a
withdrawal of one, and it must land in the chatter. What it must not do is
produce anything capable of becoming outbound contact.

This makes the guard structural rather than per-field. A field added to the full
path cannot leak into the suppressed path, because the suppressed path is a
different node. The earlier proposal — a ternary on `ggd_suggested_next_action`
inside the single shared `Update an opportunity` node — would have left
`response_draft`, follow-up activity creation and stage advancement unguarded.

`ggd_do_not_contact` must be read from the record fetched by
`Get matched opportunity` in the same run, not from the reply payload.

## 6. Application order

1. Fetch `GGD 04c` JSON via `GET /rest/workflows/G6FzMSyFNRqYcguD` (requires an
   authenticated n8n browser session).
2. ~~Confirm the node names~~ — done, section 3, read from the database.
3. Apply the section 4 code, the section 3.1 rewiring, and the section 5 branch
   to the JSON offline.
4. Diff old against new; confirm the node count only increases, and that no
   existing node is dropped. This is the check that would have caught the 04b
   damage on the day it happened.
5. `PATCH` the workflow back. Save.
6. Verify the persisted result by querying `workflow_entity.nodes` in the n8n
   database — not by reading the canvas.
7. Run A1, A2, A3, A4, A9 against 04c.
8. Only then port to live `GGD 04`, by JSON replacement rather than by
   hand-repeating the edits on a second canvas.

Step 8 matters: hand-replication across two canvases is how the original damage
occurred. Export 04c, import over 04, verify by database query again.

## 7. Open points

- Whether a `sender_only` match should write at all (section 2, row 3) is a
  judgement call, recorded here so it can be revisited deliberately rather than
  rediscovered.
- Row 0 (`explicit_id`) is a test affordance sitting in production code. Before
  live activation, decide whether to remove it or gate it behind a workflow
  variable.
- `ggd_last_message_id` is only populated for records that have received an
  outbound send. Every record contacted before that field existed will match on
  sender only. Worth a one-off audit before activation.
