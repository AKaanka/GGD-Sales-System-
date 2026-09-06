from odoo import fields, models


class GgdOpportunityActionLog(models.Model):
    """One row per guarded opportunity action reaching Odoo from outside.

    Two jobs, and it exists because neither can be done in chatter.

    * Idempotency. Every action that creates something - a manual-contact
      event, a follow-up activity, an outreach draft - carries a caller
      supplied key, and the unique constraint below is what makes a retry
      return the first result instead of minting a second one. Chatter has no
      key to be unique on, so a repeated call would leave two notes and two
      activities and no way to tell a retry from a real second event.

    * Evidence. A manual-contact row is the record that a human actually
      wrote, called or met the contact, and it is one of the two things that
      let an opportunity move to Contacted. A saved draft is not: reading a
      draft off the record and calling it contact is exactly the inference
      this model exists to make impossible.

    Rows are never rewritten and never deleted (unlink is refused for every
    group in ggd_security.xml); they cascade only when the opportunity itself
    is deleted, because a log entry for a record nobody can open is noise.
    """

    _name = "ggd.opportunity.action.log"
    _description = "GGD guarded opportunity action log"
    _order = "id desc"
    _rec_name = "idempotency_key"

    ACTIONS = [
        ("enrich_contact", "Contact enrichment"),
        ("record_manual_contact", "Manual contact recorded"),
        ("transition_stage", "Stage transition"),
        ("schedule_activity", "Follow-up activity scheduled"),
        ("save_outreach_draft", "Outreach draft saved"),
    ]

    CHANNELS = [
        ("email", "Email"),
        ("call", "Call"),
        ("linkedin", "LinkedIn"),
        ("meeting", "Meeting"),
        ("other", "Other"),
    ]

    lead_id = fields.Many2one(
        "crm.lead",
        string="Opportunity",
        required=True,
        index=True,
        ondelete="cascade",
    )
    action = fields.Selection(ACTIONS, string="Action", required=True, index=True)
    idempotency_key = fields.Char(string="Idempotency key", required=True)
    channel = fields.Selection(CHANNELS, string="Contact channel")
    occurred_at = fields.Datetime(string="Occurred at")
    summary = fields.Char(string="Summary")
    # What the action produced, so a retry can answer without repeating the
    # work: a mail.activity id, or a draft version. Never a send key.
    result_ref = fields.Char(string="Result reference")

    _unique_action_key = models.Constraint(
        "UNIQUE (lead_id, action, idempotency_key)",
        "This action has already been recorded for this opportunity with the"
        " same idempotency key.",
    )
