# Odoo Setup for Germany Growth Desk

## Applications

Install only what the first workflow needs:

1. CRM
2. Contacts, if it is not already installed as a dependency
3. Germany Growth Desk CRM Controls, from the included custom addons directory

Avoid adding Marketing Automation, Studio, Sales, Accounting, or other applications until a concrete requirement exists.

## Pipeline stages

Create these CRM stages in order:

| Sequence | Stage | Exit condition |
| ---: | --- | --- |
| 10 | Target Identified | Company and source are recorded |
| 20 | Qualified | Fit score and fit assessment reviewed |
| 30 | Draft Prepared | Draft exists; nothing sent |
| 40 | Waiting for Approval | Contact basis recorded; Kaan must decide |
| 50 | Contacted | Approved email sent and logged |
| 60 | Reply Received | Reply classified and summarised |
| 70 | Meeting Proposed | Specific dates or format proposed |
| 80 | Meeting Booked | Calendar date confirmed |
| 90 | Meeting Held | Notes and buyer feedback recorded |
| 100 | Active Opportunity | Commercial next step exists |
| 110 | Won | Engagement or commercial outcome confirmed |
| 120 | Lost | Reason recorded |
| 130 | Do Not Contact | Future outreach suppressed |

Keep `Do Not Contact` as a visible stage and also select the `Do not contact` checkbox. The checkbox is the machine-enforced control used by n8n.

## Required data before qualification

- Opportunity name
- Company name
- Website/source URL
- Contact person and role, if known
- Work email, if legitimately available
- Country and industry
- Product/capability focus
- Lead source

## Required data before approval

- Fit assessment
- Personalisation angle
- Contact basis
- Contact-basis note with the supporting facts
- Draft reviewed by Kaan
- `Do not contact` is false

The approval button refuses approval when the contact basis is missing or the opportunity is marked `Do not contact`.

## Recommended tags

- `Turkey to Germany`
- `Germany to Turkey`
- `Manufacturer`
- `Distributor`
- `Trade fair`
- `Inbound`
- `Referral`
- industry tags such as `Packaging`, `Machinery`, or `Building products`

## Automation service user

After local testing, create a separate Odoo user for n8n rather than using the administrator account.

Recommended principles:

- grant CRM access only;
- do not grant Settings or user-management access;
- use a unique password/API credential;
- disable the account immediately if the automation is retired;
- review the chatter/audit trail for automated updates.

## First test record

Create a fictional company and move it through the pipeline. Verify:

1. fit score rejects values below 0 or above 100;
2. AI confidence rejects values below 0 or above 1;
3. approval fails when contact basis is blank;
4. approval fails when `Do not contact` is selected;
5. selecting `Do not contact` revokes an existing approval;
6. approval and revocation appear in the chatter.

