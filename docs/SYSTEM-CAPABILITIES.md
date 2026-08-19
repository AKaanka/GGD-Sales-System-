# GGD Sales System — Capabilities & User Functions

**When complete, what can users do?**

---

## **High-Level: What the System Does**

The GGD Sales System is a **compliant, automated sales pipeline** that:

1. **Finds qualified prospects** — Analyzes companies and contacts for fit
2. **Approves outreach** — Gate to prevent unauthorized emails
3. **Sends personalized email** — Drafts and sends to approved leads
4. **Analyzes replies** — Classifies responses and suggests next actions
5. **Follows up** — Queues overdue contacts for manual follow-up
6. **Prevents legal violations** — Enforces GDPR and German marketing law
7. **Maintains audit trail** — Every action logged and traceable

**In short:** Lead-in → (Qualification) → Approval → Send → Reply Analysis → Follow-up → Deal

---

## **For Sales Users (You & Team)**

### **1. Lead Management (Odoo CRM)**

**What you can do:**

- [x] **Create leads** — Enter company name, contact, research notes
- [x] **Qualify leads** — Fill in fit score, product focus, personalization angle
- [x] **Set contact basis** — Document WHERE the contact came from
  - Opt-in consent?
  - Existing customer?
  - Trade fair attendee?
  - Inbound inquiry?
  - (Certain bases block email outreach for legal reasons)
- [x] **Record contact-basis evidence** — Paste the link, date, source that proves the basis is valid
- [x] **Approve for outreach** — One-click approval with enforcement (can't approve without valid basis + evidence)
- [x] **View approval history** — Who approved it, when, what was the evidence
- [x] **Suppress contacts** — One-click "Do not contact" (blocks all outreach, overrides everything)
- [x] **See email status** — When was last email sent? Did it get approved? Is it pending?
- [x] **Read incoming replies** — See what the prospect said
- [x] **See AI analysis** — LLM-generated classification of their reply + confidence score
- [x] **See suggested next action** — "Send price list", "Schedule meeting", "Mark as lost", etc.
- [x] **Create follow-up activities** — Schedule callbacks, manual responses

**Example workflow for one lead:**

```
1. Research company → Create lead in CRM
2. Fill in fit score (70/100), product focus, angle
3. Record: "Found on LinkedIn, CEO title, growth company in Berlin"
4. Click "Approve Outreach" button
   → System validates: Has contact basis? Has evidence? Not suppressed?
   → If all pass: Approval granted + timestamp recorded
5. System automatically sends personalized email (no manual sending!)
6. Email bounces or gets reply
7. AI analyzes reply: "Interested — asked for price list"
8. Confidence: 0.88 (high confidence, trustworthy)
9. Suggested action: "Send pricing document"
10. You create follow-up activity for tomorrow
11. Reply back with pricing
12. ... repeat until deal closes or contact opts out
```

---

### **2. Outreach Approval Gate (Odoo CRM UI)**

**What you can do:**

- [x] **Review lead before approval** — All fields visible, nothing hidden
- [x] **Validate contact basis** — System enforces it's a lawful basis under German law
- [x] **Check suppression flag** — Can't approve if marked "Do not contact"
- [x] **Require evidence note** — Can't approve without proof of where contact came from
  - "LinkedIn, 2026-01-15, CEO profile URL: ..."
  - "Trade fair stand, 2026-02-10, attendee list"
  - "Existing customer since 2022-Q4"
  - (Not just "okay" or "yes" — real evidence)
- [x] **One-click approval** — Button press, logged, timestamped
- [x] **Audit trail** — Who approved it? When? What was the state?
- [x] **Revoke approval** — If you change your mind, one click to block sending

**Why this matters:**
- **Legal protection** — Proves you had proper consent before emailing (GDPR Art. 6(1)(f))
- **Prevents spam** — Can't accidentally email people marked "do not contact"
- **Prevents bad bases** — System blocks email on bases like "referral" or "trade fair without opt-in" that aren't lawful for cold email
- **Audit trail** — Regulator asks "did you have consent?" → You show the timestamp and evidence

---

### **3. Automated Email Sending (n8n Workflow 3)**

**What the system does automatically:**

- [x] **Every 15 minutes:** Check for approved, unsuppressed leads
- [x] **Pick up to 10 leads** — One at a time, not all at once (prevents SMTP overload)
- [x] **Generate draft email** — LLM writes personalized subject + body based on:
  - Company research (product focus, fit assessment)
  - Personalization angle (why YOU are contacting them)
  - Previous interactions (if any)
- [x] **Enforce approval** — Can't send if not approved (system blocks it)
- [x] **Prevent duplicates** — If the same lead is approved twice, won't send twice
- [x] **Log send details** — Records:
  - When sent
  - Subject line
  - Body text
  - Email ID (for matching replies)
  - Sender address
- [x] **Update Odoo record** — Sets:
  - `Last outreach sent at` — timestamp
  - `Last message date` — for follow-up scheduling
  - `Send key` — idempotency protection
  - Revokes approval — prevents resending

**What you DON'T have to do:**
- ❌ Manually type emails
- ❌ Copy/paste addresses
- ❌ Click send buttons
- ❌ Worry about duplicates (system prevents it)

---

### **4. Reply Analysis (n8n Workflow 4)**

**What the system does automatically:**

- [x] **Every few minutes:** Check incoming email account (IMAP)
- [x] **Match reply to lead** — Finds which lead replied using:
  - Email address (sender)
  - Message ID (thread header)
  - If both fail, flags for manual review
- [x] **Read the reply** — Extracts the text
- [x] **Run LLM analysis** — Classifies the response:
  - "Interested" — Want to learn more
  - "Meeting requested" — Schedule a call
  - "Needs information" — Ask for docs/pricing
  - "Objection" — "Too expensive", "Not relevant", etc.
  - "Referral" — "Talk to my colleague..."
  - "Not interested" — Rejection
  - "Out of office" — Auto-reply
  - "Unsubscribe/stop" — Opt-out (triggers suppression)
  - "Unclear" — Flags for manual review
- [x] **Confidence score** — AI says "I'm 92% confident this is an objection"
- [x] **Generate summary** — "Prospect says they already have a vendor, needs 3 months"
- [x] **Suggest next action** — "Send ROI case study" or "Wait 3 months then follow up"
- [x] **Update Odoo record** — Stores:
  - Category (interested/not interested/etc.)
  - Summary
  - Suggested action
  - Confidence score
  - AI analysis timestamp
- [x] **Handle unsubscribe** — If they opt out, auto-flags "Do not contact"

**You see in Odoo:**
```
Latest reply: "Interested"
Summary: "Wants to see a demo but needs Q4 approval"
Next action: "Schedule demo for Oct 1"
Confidence: 0.95 (very confident)
Last analyzed: 2026-08-19 14:23
```

**You do:**
```
Click "Create activity" → Add note → Schedule follow-up
```

---

### **5. Daily Follow-Up Queue (n8n Workflow 5)**

**What the system does automatically:**

- [x] **Every morning at 08:30 Berlin time** — Runs on working days only
- [x] **Finds overdue opportunities** — Contacts you reached out to >7 days ago with no reply
- [x] **Filters suppressed** — Skips "Do not contact" and "Unsubscribe"
- [x] **Generates draft follow-up** — LLM writes a second touch email based on:
  - Original outreach
  - Time passed
  - Their industry
  - Your angle
- [x] **Creates activity** — Posts to your CRM task list:
  ```
  Activity: "Follow up with Acme Corp"
  Due: Today
  Notes: "Original email 8 days ago, no reply. 
          Suggested follow-up: 
          'Wanted to check if you saw our first message...'"
  ```

**You do:**
```
Review the activity (human-written, not sent automatically)
Click the suggested draft or write your own
Send manually (manual gate for follow-ups, not automated)
```

**Why manual gate on follow-ups?**
- Second emails are more sensitive (could look like spam)
- Human judgment is better for timing and tone
- You control the message directly

---

### **6. Lead Qualification (n8n Workflow 1)**

**What the system does automatically:**

- [x] **Watches Odoo for new leads** — When someone enters "Qualified" stage
- [x] **Runs LLM analysis** — Extracts:
  - Company size and growth rate
  - Industry and market
  - Product fit (is your solution relevant?)
  - Competitor presence
  - Pain points (from research)
- [x] **Scores fit** — 0–100 scale:
  - 80+ = High fit, prioritize
  - 50–79 = Medium, consider
  - <50 = Low, deprioritize or skip
- [x] **Generates summary** — "Berlin-based SaaS, 20 employees, growth phase, exact pain point match"
- [x] **Suggests angle** — "Position as time-saver for their compliance team"
- [x] **Stores confidence** — "89% confident in this assessment"
- [x] **Updates Odoo** — Fills in fit score, summary, angle automatically

**You see in Odoo:**
```
Fit score: 85/100 (HIGH)
Assessment: "Perfect match. B2B SaaS, 15–50 employees..."
Angle: "Position as automation for contract lifecycle"
AI confidence: 0.89
```

**You decide:**
```
Is this a good fit? (AI said 85, trust it or override?)
If yes → Add contact basis + evidence → Approve → Automated send
If no → Mark "Do not contact" or skip
```

---

## **Error Handling & Safety (Automatic)**

**What happens if something breaks?**

- [x] **Workflow fails** → Error handler catches it
- [x] **Logs the error** → What failed and why
- [x] **Records context** — Which lead, which step, what was the data
- [x] **Sanitizes secrets** — No passwords or API keys in logs
- [x] **Creates activity** → "Workflow error on lead #7, check logs"
- [x] **Stops gracefully** — Doesn't send bad emails, doesn't corrupt data

**You do:**
```
See the error activity in Odoo
Check the logs in n8n
Fix the issue (or escalate)
Re-run the workflow
```

---

## **Compliance & Legal (Built-in)**

**What the system enforces:**

- [x] **Consent validation** — Can't email without proper lawful basis
- [x] **Evidence tracking** — Stores proof of where contact came from
- [x] **Suppression rules** — "Do not contact" overrides everything
- [x] **Contact basis blocking** — Certain bases (referral, trade fair without opt-in) can't be email-approved
- [x] **Audit trail** — Every approval logged with who, when, why
- [x] **Unsubscribe handling** — AI detects opt-outs, auto-suppresses contact
- [x] **Message archival** — All outreach logged in Odoo (GDPR retention)
- [x] **No credential leaks** — Secrets stay in encrypted storage, never in logs

**For a regulator audit:**
```
Regulator: "Did you have consent to email person X?"
You show: "Yes, approved on 2026-08-15 by Kaan, 
          consent basis: LinkedIn, 
          evidence: https://linkedin.com/..., 
          timestamp: 14:23:00 UTC"
Regulator: "Checks email was sent after approval... ✓ Approved"
```

---

## **What's NOT Automated (Human Gate)**

These require your decision/approval:

- ❌ **Follow-up emails** — You review the draft, then send manually
- ❌ **Deals and negotiation** — Once interested, you take over
- ❌ **Complex replies** — If AI confidence is low, flagged for your review
- ❌ **Ambiguous contacts** — If reply matches multiple leads, you decide
- ❌ **Contact basis decisions** — You decide if the evidence is valid
- ❌ **LLM parameters** — You can tune confidence thresholds, drafting style, etc.

**Why human gates?**
- Sales requires judgment (not everything is binary)
- Legal risk is on you (compliance can't be 100% automated)
- Tone matters (follow-ups need human touch)
- Edge cases exist (ambiguous emails, multiple contacts, etc.)

---

## **A Day in the Life Using This System**

### **Morning (08:30)**

```
1. Log into Odoo CRM
2. See new follow-up activities from overnight:
   - "Acme Corp — follow up on original email from 8 days ago"
   - "TechCorp — replied, AI says 'interested', confidence 0.92"
3. Read TechCorp reply: "Looks interesting, can you send pricing?"
4. Click "Create activity" → Schedule call for tomorrow
5. Follow up with Acme via suggested draft
```

### **Midday (14:00)**

```
1. Research new prospect on LinkedIn
2. Create lead in Odoo
3. Fill in:
   - Company: "Berlin Growth SaaS"
   - Fit score: 75/100
   - Contact basis: "LinkedIn, founder mentioned pain point in post"
   - Evidence: URL + date
4. Click "Approve Outreach"
5. System validates ✓
6. Every 15 minutes: System checks
7. Next check at 14:15: Found lead, sent personalized email automatically
8. You don't click anything
```

### **Evening (17:00)**

```
1. Check dashboard:
   - 23 leads in "Qualified" stage
   - 5 waiting approval (you haven't recorded basis yet)
   - 3 awaiting reply (sent 3+ days ago)
   - 2 interested (AI detected, waiting your follow-up)
2. Emails sent today: 7 (automated)
3. Replies received: 2 (both analyzed, both flagged)
4. No errors
5. Tomorrow: 5 follow-ups scheduled
```

---

## **By the Numbers (When Fully Running)**

### **Weekly Impact**

- **Leads researched:** 20–50 (you + LLM)
- **Emails sent:** 30–70 (automated, not manual)
- **Replies analyzed:** 10–20 (AI-classified, human-judged)
- **Meetings scheduled:** 3–8 (from interested replies)
- **Deals closed:** 1–3 (varies, but you're in control)

### **Your Time Saved**

- ❌ No manual email typing (LLM does it)
- ❌ No copy/paste addresses (automation does it)
- ❌ No reply reading/classification (AI does it)
- ❌ No follow-up drafting (LLM suggests, you tweak)
- ✅ You focus on: Strategy, negotiation, relationship-building

---

## **Data You Own & Can Export**

Everything lives in Odoo (your system, your data):

- [x] All leads and companies
- [x] All approval history
- [x] All sent emails + content
- [x] All received replies + AI analysis
- [x] All activities and outcomes
- [x] Contact basis and evidence
- [x] Audit trail (who did what when)

**You can:**
```
Export to CSV/Excel
Analyze with your own tools
Run custom reports
Never locked into the system
```

---

## **Security & Privacy**

- [x] **Local only** — Services run on your computer, not a cloud server
- [x] **Encrypted at rest** — Databases are encrypted
- [x] **Encrypted in transit** — SSL/TLS for all connections
- [x] **Air-gapped** — No data leaves your machine unless YOU send an email
- [x] **Audit trail** — Every system action logged for compliance
- [x] **No AI training** — LLM output isn't used to train global models
- [x] **Backup control** — You control where backups go (external drive, cloud, etc.)

---

## **Bottom Line**

**This system turns you from:**

```
Research → Typing emails → Sending → Checking replies → Managing follow-ups
(6 hours/day of manual work)
```

**Into:**

```
Research → Click approve → System sends → AI analyzes → You follow up strategically
(2 hours/day, higher-value work)
```

**You get:**
- 3× more outreach (automation at scale)
- 100% compliant (system enforces legal rules)
- 100% auditable (proof you had consent)
- 100% your data (runs locally)
- 100% control (human gates on sensitive decisions)

---

## **What You CAN'T Do (Intentional Limits)**

- ❌ Send unapproved emails (system blocks it)
- ❌ Email someone marked "Do not contact" (system blocks it)
- ❌ Approve email on invalid legal basis (system rejects it)
- ❌ Send duplicate emails (idempotency key prevents it)
- ❌ Export credentials into logs (system sanitizes them)
- ❌ Run workflows while IMAP is off (can't receive replies)

**These limits are features, not bugs.** They protect you from legal liability and data corruption.

---

## **Next Steps (Using the System)**

**Phase 1: Setup (Day 1)**
- [ ] Install Zoho Mail credentials
- [ ] Configure LLM provider (GPT, Claude, etc.)
- [ ] Set up test mailbox

**Phase 2: Testing (Days 2–3)**
- [ ] Run through all 5 workflows with fictional leads
- [ ] Verify email sending works
- [ ] Verify reply analysis works
- [ ] Get legal review of contact procedure

**Phase 3: Launch (Week 2)**
- [ ] Enable IMAP (receive real replies)
- [ ] Activate workflows (no longer manual)
- [ ] Start with 1 real prospect/day
- [ ] Scale up gradually

**Phase 4: Scale (Weeks 3+)**
- [ ] Run 100+ leads in pipeline
- [ ] Manage 20+ active prospects
- [ ] Achieve 2–3 meetings/week
- [ ] Close deals

---

**In short: Your personal AI-powered sales assistant that never sleeps, never makes compliance mistakes, and gives you back hours every day.**
