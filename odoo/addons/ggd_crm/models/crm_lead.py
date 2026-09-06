import re
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from markupsafe import Markup, escape

import logging

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, ValidationError
from odoo.tools import email_normalize

_logger = logging.getLogger(__name__)


class CrmLead(models.Model):
    _inherit = "crm.lead"

    # Every contact basis may be approved for email, provided the evidence
    # note below is present. Until 2 September 2026 three bases
    # (trade_fair_no_optin, referral, other) were blocked from email approval;
    # that block came from German law and was removed when the product's
    # market moved outside the EU - see docs/COMPLIANCE-SCOPE.md. The basis
    # is provenance, the note is the evidence, the approver is the decision.

    # The system parameter that holds the daily send cap, and the value used
    # when the parameter is missing. The cap counts send-key claims across all
    # leads in the trailing 24 hours and is enforced in ggd_claim_send_key(),
    # before SMTP. It is the server-side ceiling on how much damage an
    # accidentally published send workflow can do to a cold domain.
    GGD_DAILY_SEND_CAP_PARAM = "ggd_crm.daily_send_cap"
    GGD_DAILY_SEND_CAP_DEFAULT = 20

    # Group that may approve outreach and clear Do not contact.
    GGD_APPROVER_GROUP = "ggd_crm.group_ggd_outreach_approver"

    # Manual mail fetch (#49). The cron polls every 5 minutes; this is the
    # button that does not wait. The floor is server-side because a button a
    # person can hold down is a button that hammers Zoho's IMAP endpoint, and
    # a lockout on info@ would stop all incoming mail rather than one click.
    GGD_FETCH_MIN_INTERVAL_SECONDS = 30
    GGD_FETCH_LAST_RUN_PARAM = "ggd_crm.last_manual_mail_fetch"

    # Senders whose mail is machine-generated: bounces, delivery and DMARC
    # reports, and the no-reply mailboxes they come from. Deliberately close
    # to the bounceSignals regex in GGD-04's "Normalize and sanitize inbound
    # email" node, so the two lists do not drift apart.
    GGD_AUTOMATED_SENDER = re.compile(
        r"(mailer-daemon|postmaster|no-?reply|do-?not-?reply|"
        r"bounce|dmarc|abuse@|nobody@)",
        re.I,
    )

    # Minimum length for the contact-basis note. The note must carry actual
    # evidence - a date, a source, a document reference - not a restatement of
    # the selection label. A length floor cannot enforce quality, but it does
    # stop "ok" and "yes" from passing as evidence.
    GGD_CONTACT_BASIS_NOTE_MIN_LENGTH = 20

    # Length ceiling for a reply draft handed over by the ChatGPT connector.
    # A reply is sentences; a pasted thread or a whole document is a storage
    # accident. Over-long input is refused rather than truncated, for the
    # reason the connector's own CREATE_LIMITS gives: a half-sentence left
    # behind by truncation looks deliberate to whoever reads it next.
    GGD_RESPONSE_DRAFT_MAX_LENGTH = 5000

    # Every column the outbound claim guard must re-read under its row lock.
    # The workflow decides whether a send is allowed from a snapshot taken
    # several RPCs before the claim; anything in that snapshot can be changed
    # by a human in between, so all of it is read again while the row is
    # locked. Fixed module-level names, never caller input - they are
    # interpolated into the SELECT.
    GGD_CLAIM_STATE_COLUMNS = (
        "ggd_last_send_key",
        "ggd_outreach_approved",
        "ggd_outreach_approved_by",
        "ggd_outreach_approved_at",
        "ggd_do_not_contact",
        "ggd_contact_basis",
        "ggd_contact_basis_note",
        "ggd_contact_basis_verified_at",
        "email_from",
        "ggd_draft_subject",
        "ggd_draft_body",
        "ggd_draft_version",
        "ggd_approved_draft_version",
        "ggd_approved_recipient",
    )

    GGD_DRAFT_FIELDS = (
        "ggd_draft_subject",
        "ggd_draft_body",
        "ggd_draft_version",
    )

    GGD_APPROVAL_INPUT_FIELDS = GGD_DRAFT_FIELDS + ("email_from",)

    GGD_REPLY_CATEGORIES = (
        "interested",
        "meeting",
        "information",
        "objection",
        "referral",
        "not_interested",
        "out_of_office",
        "unsubscribe",
        "unclear",
    )

    ggd_industry = fields.Char(string="Industry")
    ggd_product_focus = fields.Text(string="Product / capability focus")
    ggd_source_url = fields.Char(string="Research source URL")
    # Hand order inside a pipeline column. Odoo orders crm.lead by priority
    # and id and resequences a kanban only through a field named "sequence",
    # so without this the board refused to let a card be moved within its
    # column. The model's own order is untouched: only the kanban sorts by
    # it, first, so the list and the search stay as the CRM ships them.
    sequence = fields.Integer(
        string="Pipeline order",
        default=10,
        index=True,
        help="Position of the card inside its pipeline column. Set by dragging.",
    )

    ggd_fit_score = fields.Integer(
        string="GGD fit score",
        help="LLM-assisted or manually reviewed fit score from 0 to 100.",
    )
    ggd_fit_summary = fields.Text(string="Fit assessment")
    ggd_personalization_angle = fields.Text(string="Personalisation angle")
    ggd_recommended_buyer_roles = fields.Text(
        string="Recommended buyer roles",
        copy=False,
    )
    ggd_qualification_state = fields.Selection(
        selection=[
            ("pending", "Pending qualification"),
            ("ready", "Qualified"),
            ("review", "Needs human review"),
            ("failed", "Qualification failed"),
        ],
        string="Qualification status",
        default="pending",
        copy=False,
        index=True,
    )

    ggd_contact_basis = fields.Selection(
        selection=[
            ("consent", "Prior express consent — opt-in on file"),
            (
                "existing_customer",
                "Existing customer — address obtained during a sale",
            ),
            ("inbound", "Inbound enquiry — reply stays within its scope"),
            ("trade_fair", "Trade fair — opt-in recorded at the stand"),
            ("trade_fair_no_optin", "Trade fair — card or conversation, no opt-in"),
            ("referral", "Referral / introduction"),
            ("other", "Other — see the note"),
        ],
        string="Contact basis",
        help=(
            "Where this address came from. Any basis can be approved for "
            "outreach once the note below carries checkable evidence; the "
            "basis is provenance, the note is the evidence, and the approver "
            "is the decision. See docs/COMPLIANCE-SCOPE.md."
        ),
    )
    ggd_contact_basis_note = fields.Text(
        string="Contact-basis note",
        help=(
            "The evidence behind the contact basis: where and when it arose, "
            "and a reference that can be checked today. Required before "
            "outreach can be approved."
        ),
    )
    ggd_contact_basis_verified_at = fields.Datetime(
        string="Contact basis verified at",
        readonly=True,
        copy=False,
        help=(
            "Set only when a human approves outreach, so the age of the "
            "evidence is visible. Cleared when approval is revoked."
        ),
    )
    ggd_outreach_approved = fields.Boolean(
        string="Outreach approved",
        copy=False,
        tracking=True,
    )
    ggd_outreach_approved_by = fields.Many2one(
        "res.users",
        string="Approved by",
        readonly=True,
        copy=False,
    )
    ggd_outreach_approved_at = fields.Datetime(
        string="Approved at",
        readonly=True,
        copy=False,
    )
    ggd_draft_subject = fields.Char(
        string="Reviewed draft subject",
        copy=False,
    )
    ggd_draft_body = fields.Text(
        string="Reviewed draft body",
        copy=False,
    )
    ggd_draft_version = fields.Char(
        string="Draft version",
        readonly=True,
        copy=False,
        index=True,
    )
    # Deliberately NOT part of GGD_DRAFT_FIELDS. That tuple defines the
    # content a human approves and whose change revokes an approval. The
    # language is a record of what the drafting model chose, used by the
    # follow-up workflow so a German first email is not followed up in
    # English. Editing it must not invalidate an approval, and it carries no
    # part of the message a recipient reads.
    ggd_draft_language = fields.Char(
        string="Draft language",
        readonly=True,
        copy=False,
        help=(
            "ISO code of the language the draft was written in, as reported by "
            "the drafting workflow. Informational: the approval gate does not "
            "depend on it."
        ),
    )
    ggd_approved_draft_version = fields.Char(
        string="Approved draft version",
        readonly=True,
        copy=False,
        index=True,
        help="The immutable draft version that the current outreach approval covers.",
    )
    ggd_approved_recipient = fields.Char(
        string="Approved recipient",
        readonly=True,
        copy=False,
        help=(
            "Normalized recipient address covered by the current human approval. "
            "A linked-contact email change invalidates the send at claim time."
        ),
    )
    ggd_draft_status = fields.Selection(
        selection=[
            ("empty", "No draft"),
            ("ready", "Ready for review"),
            ("approved", "Approved for send"),
            ("sent", "Sent"),
        ],
        string="Draft status",
        default="empty",
        copy=False,
        index=True,
    )
    ggd_do_not_contact = fields.Boolean(
        string="Do not contact",
        copy=False,
        tracking=True,
    )

    ggd_reply_category = fields.Selection(
        selection=[
            ("interested", "Interested"),
            ("meeting", "Meeting requested"),
            ("information", "Needs information"),
            ("objection", "Objection"),
            ("referral", "Referral to another person"),
            ("not_interested", "Not interested"),
            ("out_of_office", "Out of office"),
            ("unsubscribe", "Unsubscribe / stop"),
            ("unclear", "Unclear — manual review"),
        ],
        string="Latest reply category",
        copy=False,
        tracking=True,
    )
    ggd_reply_summary = fields.Text(string="Latest reply summary", copy=False)
    ggd_suggested_next_action = fields.Text(
        string="Suggested next action",
        copy=False,
    )
    ggd_ai_confidence = fields.Float(
        string="AI confidence",
        digits=(3, 2),
        copy=False,
        help="Confidence between 0.00 and 1.00. Low confidence requires manual review.",
    )
    ggd_ai_last_analyzed_at = fields.Datetime(
        string="Last AI analysis",
        readonly=True,
        copy=False,
    )
    ggd_last_message_id = fields.Char(
        string="Last email message ID",
        copy=False,
        index=True,
        help="Used by the automation layer to match replies to this opportunity.",
    )
    ggd_last_send_key = fields.Char(
        string="Last send key",
        copy=False,
        index=True,
        help=(
            "Idempotency key for outbound sending, formed from the opportunity "
            "ID and the identifier of the draft being sent. The send workflow "
            "must claim this key BEFORE calling SMTP, so that a crash between "
            "sending and recording cannot result in a second send. A repeat run "
            "that finds the key already claimed must stop before SMTP."
        ),
    )
    ggd_last_confirmed_send_key = fields.Char(
        string="Last SMTP-confirmed send key",
        readonly=True,
        copy=False,
        index=True,
        help="Identifies which claimed draft was most recently accepted by SMTP.",
    )
    ggd_last_sent_at = fields.Datetime(
        string="Outbound send claimed at",
        readonly=True,
        copy=False,
        help=(
            "Legacy claim timestamp retained for compatibility. A message is "
            "confirmed sent only when Confirmed sent at is populated."
        ),
    )
    ggd_claimed_recipient = fields.Char(
        string="Claimed recipient",
        readonly=True,
        copy=False,
        help="Immutable approved recipient captured when the SMTP send is claimed.",
    )
    ggd_claimed_draft_version = fields.Char(
        string="Claimed draft version",
        readonly=True,
        copy=False,
        help="Immutable approved draft version captured when the SMTP send is claimed.",
    )
    ggd_send_confirmed_at = fields.Datetime(
        string="Confirmed sent at",
        readonly=True,
        copy=False,
        help="Set only after SMTP succeeds and the send is finalized in Odoo.",
    )
    ggd_last_claim_released_at = fields.Datetime(
        string="Last failed claim released at",
        readonly=True,
        copy=False,
    )
    ggd_last_claim_released_by = fields.Many2one(
        "res.users",
        string="Last failed claim released by",
        readonly=True,
        copy=False,
    )
    ggd_last_sent_recipient = fields.Char(
        string="Last sent recipient",
        readonly=True,
        copy=False,
    )
    ggd_last_sent_subject = fields.Char(
        string="Last sent subject",
        readonly=True,
        copy=False,
    )
    ggd_last_sent_body_summary = fields.Text(
        string="Last sent body summary",
        readonly=True,
        copy=False,
    )
    ggd_last_sent_draft_version = fields.Char(
        string="Last sent draft version",
        readonly=True,
        copy=False,
    )
    ggd_last_message_date = fields.Date(
        string="Last message date",
        copy=False,
        readonly=True,
        help="Latest date of any message (sent or received); used for follow-up scheduling.",
    )
    ggd_delivery_status = fields.Selection(
        selection=[
            ("none", "No outbound delivery state"),
            ("claimed", "Claimed — SMTP outcome unknown"),
            ("accepted", "Accepted by SMTP"),
            ("bounced", "Bounced"),
        ],
        string="Delivery status",
        default="none",
        copy=False,
        index=True,
    )
    ggd_last_reply_received_at = fields.Datetime(
        string="Last reply received at",
        readonly=True,
        copy=False,
    )
    ggd_last_reply_message_id = fields.Char(
        string="Last reply message ID",
        readonly=True,
        copy=False,
        index=True,
    )
    ggd_response_draft = fields.Text(
        string="Suggested response draft",
        copy=False,
    )
    ggd_suggested_follow_up_at = fields.Datetime(
        string="Suggested follow-up at",
        copy=False,
    )
    ggd_follow_up_draft = fields.Text(
        string="Latest follow-up draft",
        copy=False,
    )
    ggd_last_follow_up_queue_key = fields.Char(
        string="Last follow-up queue key",
        readonly=True,
        copy=False,
        index=True,
    )
    ggd_last_follow_up_queued_at = fields.Datetime(
        string="Last follow-up queued at",
        readonly=True,
        copy=False,
    )
    ggd_automation_needs_review = fields.Boolean(
        string="Automation needs review",
        copy=False,
        index=True,
    )
    ggd_qualification_needs_review = fields.Boolean(
        string="Qualification needs review",
        copy=False,
    )
    ggd_reply_needs_review = fields.Boolean(
        string="Reply needs review",
        copy=False,
    )
    ggd_delivery_needs_review = fields.Boolean(
        string="Delivery needs review",
        copy=False,
    )
    ggd_workflow_needs_review = fields.Boolean(
        string="Workflow error needs review",
        copy=False,
    )
    ggd_automation_review_summary = fields.Text(
        string="Automation review summary",
        copy=False,
    )

    # The one field the pipeline board reads. The Aurora design draws a line
    # under each column title that is the mix of outbound states of the cards
    # in it, and Odoo's <progressbar> draws exactly that - but it groups by a
    # single stored field, and this addon spreads outbound state over five.
    # So the five collapse here, in the order a human would read them: a stop
    # outranks a question, a question outranks a wait, a wait outranks a done.
    # Stored and indexed because read_progress_bar groups on it in SQL, and
    # clicking a segment filters the column, which is a search on it.
    GGD_BOARD_STATE_SELECTION = [
        ("none", "Nothing yet"),
        ("ok", "Done"),
        ("wait", "Waiting on a person"),
        ("review", "Needs a human decision"),
        ("stop", "Stop and look"),
    ]
    ggd_board_state = fields.Selection(
        selection=GGD_BOARD_STATE_SELECTION,
        string="Board state",
        compute="_compute_ggd_board_state",
        store=True,
        index=True,
        readonly=True,
        copy=False,
        help=(
            "The outbound state of this opportunity in one value, for the "
            "line under the pipeline column title. Derived; never written."
        ),
    )

    @api.depends(
        "ggd_do_not_contact",
        "ggd_delivery_status",
        "ggd_qualification_state",
        "ggd_reply_category",
        "ggd_draft_status",
        "ggd_outreach_approved",
        "ggd_automation_needs_review",
        "ggd_qualification_needs_review",
        "ggd_reply_needs_review",
        "ggd_delivery_needs_review",
        "ggd_workflow_needs_review",
    )
    def _compute_ggd_board_state(self):
        """Collapse the outbound state into one of the design's four colours.

        Precedence, highest first, because a card can be in several states at
        once and the colour has to say the most urgent one:

          stop   - do not contact, a claim whose SMTP outcome is unknown, a
                   bounce, an unsubscribe or a refusal. Look before acting.
          review - the automation declined to decide: qualification, reply or
                   any of the review flags.
          wait   - a draft is ready and a person has not approved it.
          ok     - approved, sent, accepted, or a positive reply.
          none   - nothing has happened to this record yet.
        """
        stop_replies = ("unsubscribe", "not_interested")
        review_replies = ("objection", "unclear", "information", "referral")
        ok_replies = ("interested", "meeting")
        for lead in self:
            if (
                lead.ggd_do_not_contact
                or lead.ggd_delivery_status in ("claimed", "bounced")
                or lead.ggd_reply_category in stop_replies
            ):
                lead.ggd_board_state = "stop"
            elif (
                lead.ggd_qualification_state == "review"
                or lead.ggd_reply_category in review_replies
                or lead.ggd_automation_needs_review
                or lead.ggd_qualification_needs_review
                or lead.ggd_reply_needs_review
                or lead.ggd_delivery_needs_review
                or lead.ggd_workflow_needs_review
            ):
                lead.ggd_board_state = "review"
            elif lead.ggd_draft_status == "ready" and not lead.ggd_outreach_approved:
                lead.ggd_board_state = "wait"
            elif (
                lead.ggd_draft_status in ("approved", "sent")
                or lead.ggd_delivery_status == "accepted"
                or lead.ggd_reply_category in ok_replies
            ):
                lead.ggd_board_state = "ok"
            else:
                lead.ggd_board_state = "none"

    # The four chips the design puts above the pipeline columns. They are the
    # same four questions the review desk opens on, asked from the board: what
    # can go out now, what is the automation refusing to decide, what send has
    # an unknown outcome, and who has written back. The domains are the review
    # desk's own filters, so a chip and its filter can never drift apart.
    GGD_BOARD_CHIP_DOMAINS = {
        "sendable": [
            ("ggd_outreach_approved", "=", True),
            ("ggd_draft_status", "=", "approved"),
            ("ggd_do_not_contact", "=", False),
            ("email_from", "!=", False),
        ],
        "needs_review": [
            "|", "|", "|", "|",
            ("ggd_automation_needs_review", "=", True),
            ("ggd_qualification_needs_review", "=", True),
            ("ggd_reply_needs_review", "=", True),
            ("ggd_delivery_needs_review", "=", True),
            ("ggd_workflow_needs_review", "=", True),
        ],
        "unresolved_claim": [("ggd_delivery_status", "=", "claimed")],
        "replies": [("ggd_last_reply_received_at", "!=", False)],
    }

    @api.model
    def ggd_board_chip_counts(self):
        """Counts for the pipeline's quick-filter chips, in one call.

        Read-only and unprivileged: search_count applies the user's own record
        rules, so a chip never claims a record the user cannot open. The cap is
        read with sudo because ir.config_parameter is not readable by a plain
        user, and the number is not a secret - it is printed on the chip.
        """
        counts = {
            key: self.search_count([("type", "=", "opportunity")] + domain)
            for key, domain in self.GGD_BOARD_CHIP_DOMAINS.items()
        }
        try:
            counts["cap"] = self._ggd_daily_send_cap()
        except ValidationError:
            # A malformed cap stops sending; it must not also blank the board.
            counts["cap"] = 0
        return counts

    @api.constrains("ggd_fit_score")
    def _check_ggd_fit_score(self):
        for lead in self:
            if not 0 <= lead.ggd_fit_score <= 100:
                raise ValidationError(_("GGD fit score must be between 0 and 100."))

    @api.constrains("ggd_ai_confidence")
    def _check_ggd_ai_confidence(self):
        for lead in self:
            if not 0 <= lead.ggd_ai_confidence <= 1:
                raise ValidationError(_("AI confidence must be between 0.00 and 1.00."))

    @api.model
    def _ggd_normalise_language(self, language):
        """Return a clean ISO language tag, or False.

        Never raises. This is metadata attached to a draft that has already
        been written; refusing the whole draft because a model returned
        "Deutsch" instead of "de" would trade a useful record for a failed
        workflow run - the same bad trade defect 13 made. An unrecognised
        value is dropped and the draft is stored regardless.
        """
        tag = (language or "").strip()
        if not tag:
            return False
        if not re.fullmatch(r"[A-Za-z]{2,3}(-[A-Za-z0-9]{2,8})?", tag):
            return False
        parts = tag.split("-")
        return parts[0].lower() if len(parts) == 1 else f"{parts[0].lower()}-{parts[1].upper()}"

    def _ggd_check_draft_ready(self, subject, body, version):
        """Require the exact reviewed draft before outreach can be approved."""
        if not (subject or "").strip():
            raise ValidationError(
                _("Prepare and review an email subject before approving outreach.")
            )
        if not (body or "").strip():
            raise ValidationError(
                _("Prepare and review an email body before approving outreach.")
            )
        if not (version or "").strip():
            raise ValidationError(
                _("The reviewed email draft has no version. Prepare the draft again.")
            )

    @staticmethod
    def _ggd_check_recipient_ready(recipient):
        if not (email_normalize(recipient or "") or ""):
            raise ValidationError(
                _("A valid recipient email address is required before approval.")
            )

    def _ggd_check_draft_can_be_approved(self, version, last_sent_version):
        if version and version == last_sent_version:
            raise ValidationError(
                _(
                    "This exact draft version was already sent. Prepare a new "
                    "draft before granting another outreach approval."
                )
            )

    def _ggd_check_no_unresolved_send_claim(
        self, delivery_status, send_key, confirmed_key
    ):
        if delivery_status == "claimed" and send_key != confirmed_key:
            raise ValidationError(
                _(
                    "A previous SMTP outcome is unresolved. Check Zoho Sent. "
                    "If no message left the mailbox, use Release Failed Claim "
                    "before preparing or approving another draft."
                )
            )

    @staticmethod
    def _ggd_parse_workflow_datetime(value, field_label):
        """Accept n8n ISO-8601 values and return Odoo's naive UTC datetime."""
        if not value:
            return False
        if isinstance(value, datetime):
            parsed = value
        else:
            timestamp = str(value).strip()
            if timestamp.endswith("Z"):
                timestamp = timestamp[:-1] + "+00:00"
            try:
                parsed = datetime.fromisoformat(timestamp)
            except (TypeError, ValueError) as exc:
                raise ValidationError(
                    _("%(field)s must be a valid ISO-8601 timestamp.", field=field_label)
                ) from exc
        if parsed.tzinfo:
            parsed = parsed.astimezone(timezone.utc).replace(tzinfo=None)
        return parsed

    def _ggd_review_values(self, source_field, needs_review, summary=False):
        """Update one workflow's review flag without clearing another's issue."""
        review_labels = {
            "ggd_qualification_needs_review": _("qualification"),
            "ggd_reply_needs_review": _("reply"),
            "ggd_delivery_needs_review": _("delivery"),
            "ggd_workflow_needs_review": _("workflow error"),
        }
        review_fields = tuple(review_labels)
        states = {name: bool(getattr(self, name)) for name in review_fields}
        states[source_field] = bool(needs_review)
        any_review = any(states.values())
        remaining = ", ".join(
            review_labels[name] for name, active in states.items() if active
        )
        return {
            source_field: bool(needs_review),
            "ggd_automation_needs_review": any_review,
            "ggd_automation_review_summary": (
                (summary or "").strip()
                if needs_review
                else (
                    _("Review still required for: %(sources)s.", sources=remaining)
                    if any_review
                    else False
                )
            ),
        }

    def ggd_prepare_draft(self, subject, body, language=None):
        """Store one reviewable outbound draft and return its immutable version.

        Workflow 2 calls this method and then stops. Changing a draft always
        consumes any older approval, so Workflow 3 can send only the exact
        subject/body pair a human approved later in Odoo.

        Returns a dict, {"draft_version": <hex>}, NOT a bare string. A bare
        string is legal JSON (RFC 8259 allows a scalar at the top level) and
        Odoo serialises it correctly, but n8n's HTTP Request node refuses to
        parse a top-level scalar string and fails the node with "Response body
        is not valid JSON" - even though Odoo has already stored and committed
        the draft. That produced defect 13: Workflow 2 reported a failed run
        for work that had actually succeeded, which is worse than a plain
        failure because a retry mints a second draft version and silently
        discards the one a human may already have read.

        Every other method the workflows call returns a bool, int, dict or
        list, and those all parse; only this one returned a scalar string.
        Returning a dict fixes it at the source for every client rather than
        depending on one node's Response Format setting, which would not
        survive a workflow re-import.
        """
        self.ensure_one()
        self._ggd_check_no_unresolved_send_claim(
            self.ggd_delivery_status,
            self.ggd_last_send_key,
            self.ggd_last_confirmed_send_key,
        )
        if self.ggd_do_not_contact:
            raise ValidationError(_("Do not contact is set; no outreach draft may be prepared."))
        if not (self.email_from or "").strip():
            raise ValidationError(_("A recipient email address is required before drafting."))
        subject = (subject or "").strip()
        body = (body or "").strip()
        version = uuid4().hex
        self._ggd_check_draft_ready(subject, body, version)
        self.write(
            {
                "ggd_draft_subject": subject,
                "ggd_draft_body": body,
                "ggd_draft_version": version,
                "ggd_draft_language": self._ggd_normalise_language(language),
                "ggd_draft_status": "ready",
                "ggd_outreach_approved": False,
                "ggd_approved_draft_version": False,
                "ggd_approved_recipient": False,
            }
        )
        self.message_post(
            body=_("GGD outreach draft prepared for human review. Nothing was sent.")
        )
        return {"draft_version": version}

    def ggd_apply_qualification(
        self,
        fit_score,
        summary,
        personalization_angle,
        confidence,
        source_url=False,
        industry=False,
        product_focus=False,
        recommended_buyer_roles=False,
    ):
        """Apply validated Workflow 1 output without granting send approval."""
        self.ensure_one()
        try:
            fit_score = int(fit_score)
            confidence = float(confidence)
        except (TypeError, ValueError) as exc:
            raise ValidationError(_("Qualification score and confidence must be numbers.")) from exc
        if not 0 <= fit_score <= 100:
            raise ValidationError(_("GGD fit score must be between 0 and 100."))
        if not 0 <= confidence <= 1:
            raise ValidationError(_("AI confidence must be between 0.00 and 1.00."))
        if not (summary or "").strip() or not (personalization_angle or "").strip():
            raise ValidationError(
                _("Qualification requires both a fit summary and a personalisation angle.")
            )
        needs_review = confidence < 0.7
        values = {
            "ggd_fit_score": fit_score,
            "ggd_fit_summary": summary.strip(),
            "ggd_personalization_angle": personalization_angle.strip(),
            "ggd_ai_confidence": confidence,
            "ggd_ai_last_analyzed_at": fields.Datetime.now(),
            "ggd_qualification_state": "review" if needs_review else "ready",
        }
        if industry:
            values["ggd_industry"] = str(industry).strip()
        if product_focus:
            values["ggd_product_focus"] = str(product_focus).strip()
        if recommended_buyer_roles:
            roles = (
                recommended_buyer_roles
                if isinstance(recommended_buyer_roles, (list, tuple))
                else [recommended_buyer_roles]
            )
            values["ggd_recommended_buyer_roles"] = "\n".join(
                str(role).strip() for role in roles if str(role).strip()
            )
        values.update(
            self._ggd_review_values(
                "ggd_qualification_needs_review",
                needs_review,
                _("Qualification confidence is below 0.70; review the result."),
            )
        )
        if source_url:
            values["ggd_source_url"] = source_url
        self.write(values)
        self.message_post(
            body=_(
                "GGD qualification recorded. Human review status: %(status)s.",
                status=_("required") if needs_review else _("not required"),
            )
        )
        return not needs_review

    @api.model
    def ggd_find_reply_candidates(self, in_reply_to=False, sender_email=False):
        """Return the minimal Odoo match result needed by Workflow 4."""
        fields_to_read = [
            "id",
            "name",
            "email_from",
            "ggd_last_message_id",
            "ggd_do_not_contact",
        ]
        in_reply_to = (in_reply_to or "").strip()
        sender_email = email_normalize(sender_email or "") or ""
        searchable = self.with_context(active_test=False)
        if in_reply_to:
            exact = searchable.search(
                [("ggd_last_message_id", "=", in_reply_to)], limit=2
            )
            if exact:
                return {
                    "match_type": "message_id",
                    "candidates": exact.read(fields_to_read),
                }
        candidates = self.browse()
        if sender_email:
            candidates = searchable.search(
                [("email_normalized", "=", sender_email)], limit=3
            )
        return {
            "match_type": "sender" if candidates else "none",
            "candidates": candidates.read(fields_to_read),
        }

    @api.model
    def ggd_queue_unmatched_inbound(
        self,
        message_id,
        sender_email,
        subject,
        reason,
        received_at=False,
    ):
        """Create one visible CRM review record for unmatched inbound mail."""
        message_id = (message_id or "").strip()
        sender_email = email_normalize(sender_email or "") or ""
        subject = (subject or "").strip()
        reason = (reason or "").strip()
        if not message_id or not sender_email or not reason:
            raise ValidationError(
                _("Unmatched inbound review requires Message-ID, sender, and reason.")
            )
        existing = self.with_context(active_test=False).search(
            [("ggd_last_reply_message_id", "=", message_id)], limit=1
        )
        if existing:
            return existing.id
        received = self._ggd_parse_workflow_datetime(
            received_at, _("Inbound received at")
        ) or fields.Datetime.now()
        lead = self.create(
            {
                "name": _(
                    "Manual inbound review: %(subject)s",
                    subject=subject[:120] or _("no subject"),
                ),
                "email_from": sender_email,
                "description": reason[:1000],
                "ggd_qualification_state": "failed",
                "ggd_reply_category": "unclear",
                "ggd_last_reply_message_id": message_id,
                "ggd_last_reply_received_at": received,
                "ggd_last_message_date": received.date(),
                "ggd_reply_needs_review": True,
                "ggd_automation_needs_review": True,
                "ggd_automation_review_summary": reason[:1000],
            }
        )
        lead.activity_schedule(
            "mail.mail_activity_data_todo",
            date_deadline=fields.Date.context_today(lead),
            summary=_("Match inbound email manually"),
            note=escape(reason[:1000]),
            user_id=self.env.user.id,
        )
        lead.message_post(
            body=_(
                "GGD created this review record because inbound Message-ID "
                "%(message_id)s could not be matched unambiguously.",
                message_id=message_id,
            )
        )
        return lead.id

    def ggd_record_automation_error(self, summary, send_may_have_occurred=False):
        """Record a concise shared-workflow failure without storing message bodies."""
        self.ensure_one()
        summary = (summary or "").strip()
        if not summary:
            raise ValidationError(_("An automation error summary is required."))
        values = self._ggd_review_values(
            "ggd_workflow_needs_review", True, summary
        )
        if send_may_have_occurred:
            values.update(
                self._ggd_review_values(
                    "ggd_delivery_needs_review", True, summary
                )
            )
        self.write(values)
        self.message_post(
            body=Markup("<p>%s</p><p>%s</p>")
            % (escape(_("GGD automation error requires review.")), escape(summary))
        )
        return True

    def action_ggd_resolve_automation_review(self):
        """Let a human close reviewed workflow items without editing flags."""
        for lead in self:
            if not lead.ggd_automation_needs_review:
                continue
            lead.write(
                {
                    "ggd_qualification_needs_review": False,
                    "ggd_reply_needs_review": False,
                    "ggd_delivery_needs_review": False,
                    "ggd_workflow_needs_review": False,
                    "ggd_automation_needs_review": False,
                    "ggd_automation_review_summary": False,
                }
            )
            lead.message_post(
                body=_(
                    "GGD automation review resolved by %(user)s after manual review.",
                    user=self.env.user.display_name,
                )
            )
        return True

    @api.model
    def message_new(self, msg_dict, custom_values=None):
        """Suppress leads the mail gateway creates from machine mail.

        The info@ alias mints an opportunity for every message delivered to
        it, so DMARC aggregate reports, delivery notifications and vendor
        no-reply mail all arrive as leads carrying a live, deliverable
        address. Nothing downstream recognises them for what they are:
        GGD-01 skips them only because they happen to have no source URL,
        and approval is refused only because they happen to have no contact
        basis - a field a person can fill in to make the validation error go
        away, which is what the error text invites. Setting Do not contact
        on arrival makes the suppression a property of the record instead of
        an absent field, and clearing it already requires an approver.

        The lead is still created. Refusing would drop mail on the floor,
        and a suppressed record that a human can see is worth more than a
        message nobody knows arrived.
        """
        values = dict(custom_values or {})
        sender = (msg_dict or {}).get("email_from") or ""
        automated = bool(self.GGD_AUTOMATED_SENDER.search(sender))
        if automated:
            values["ggd_do_not_contact"] = True
            values["ggd_automation_needs_review"] = True
        lead = super().message_new(msg_dict, values)
        if automated:
            lead.message_post(
                body=_(
                    "Created from machine-generated mail (%(sender)s). Marked "
                    "Do not contact on arrival; clearing it needs an approver.",
                    sender=sender,
                )
            )
        return lead

    @api.model
    def ggd_fetch_incoming_mail(self):
        """Poll the incoming mail servers now, for a user without Settings rights.

        Reading the mailbox this database is already configured to read is not
        an administrative act, but `fetchmail.server` is admin-only, so the
        fetch runs under sudo. Two things keep that narrow: the method takes no
        arguments, so a caller cannot name a server and make Odoo connect
        somewhere of their choosing, and it only touches servers already
        confirmed in Settings.

        Returns a plain dict for the UI rather than raising. A mail server that
        is unreachable is an ordinary Tuesday, not an error worth a traceback
        in the user's face.
        """
        Param = self.env["ir.config_parameter"].sudo()
        now = fields.Datetime.now()

        previous = fields.Datetime.to_datetime(
            Param.get_param(self.GGD_FETCH_LAST_RUN_PARAM) or False
        )
        if previous:
            waited = (now - previous).total_seconds()
            if 0 <= waited < self.GGD_FETCH_MIN_INTERVAL_SECONDS:
                return {
                    "ok": False,
                    "reason": "rate_limited",
                    "message": _(
                        "Mail was fetched %(seconds)s seconds ago. Wait a moment "
                        "before fetching again — the mail server rate-limits, and "
                        "the 5-minute poll is still running either way.",
                        seconds=int(waited),
                    ),
                }

        servers = self.env["fetchmail.server"].sudo().search([("state", "=", "done")])
        if not servers:
            return {
                "ok": False,
                "reason": "no_server",
                "message": _(
                    "No confirmed incoming mail server is configured, so there is "
                    "nothing to fetch from."
                ),
            }

        Message = self.env["mail.message"].sudo()
        before = Message.search([], order="id desc", limit=1).id or 0

        # Claim the slot before fetching, not after: a fetch that hangs must
        # still hold the rate limit, or holding the button queues them up.
        Param.set_param(self.GGD_FETCH_LAST_RUN_PARAM, fields.Datetime.to_string(now))

        try:
            servers.fetch_mail()
        except Exception:  # noqa: BLE001 - surfaced to the user, not swallowed
            _logger.exception("Manual mail fetch failed")
            return {
                "ok": False,
                "reason": "error",
                "message": _(
                    "The mail server could not be reached. The 5-minute poll will "
                    "keep trying; check Settings > Technical > Incoming Mail "
                    "Servers if this persists."
                ),
            }

        arrived = Message.search_count([("id", ">", before)])
        return {
            "ok": True,
            "reason": "fetched",
            "count": arrived,
            "message": (
                _("Fetched %(count)s new message(s).", count=arrived)
                if arrived
                else _("Fetched — nothing new.")
            ),
        }

    def _ggd_check_approver(self, action):
        """Raise AccessError unless the acting user may authorise outreach.

        Approving outreach and clearing Do not contact are the two writes
        that turn a record into something the send workflow will email. Both
        require membership of the approver group. The check is on the write
        path, not on the field, because the automation user must still READ
        these fields: every workflow's search_read filters on them.

        The superuser is exempt, as it is from every Odoo access rule; the
        automation user is an ordinary internal user and is not. That is
        the whole point: n8n's API key can qualify, draft, claim, finalise and
        suppress, but it cannot approve and it cannot un-suppress.
        """
        if self.env.su or self.env.user.has_group(self.GGD_APPROVER_GROUP):
            return
        raise AccessError(
            _(
                "Only a member of the 'Outreach approver' group may %(action)s. "
                "Ask an administrator to add you to that group in Settings > "
                "Users. The automation user must never be in it.",
                action=action,
            )
        )

    def _ggd_check_approval_allowed(self, do_not_contact, contact_basis, basis_note):
        """Raise if this combination may not be approved for email outreach.

        Shared by the approval button, write() and create(), so that setting
        ggd_outreach_approved directly is subject to the same rules. A gate
        enforced only in a UI button is not a gate. Takes plain values rather
        than reading self, so it can also run before a record exists.

        Approving requires nothing of the record itself, by Kaan's decision
        on 4 September 2026: not a contact basis, not a note, not a drafted
        subject or body, not a recipient. Two rules survive, and neither is
        something a person fills in - who is clicking, and whether the
        contact asked not to be written to.

        The send path is unchanged and still requires a real email. An
        approval granted with no draft produces no approved draft version,
        so _ggd_expected_send_key returns False and GGD-03 cannot claim.
        That is deliberate: the send key is the idempotency guarantee, and
        an empty draft is not a message anyone can send.

        The contact basis and its note stopped being required here by the
        same decision. They were checked in two places - at
        approval and again in _ggd_claim_blockers - and both have been
        removed, so an approved lead can actually be sent rather than
        failing later at the claim. The fields remain and are still worth
        filling in; nothing enforces them. This reverses criterion 2 of #6.
        What still refuses: a non-approver, and Do not contact.
        """
        self._ggd_check_approver(_("approve outreach"))
        if do_not_contact:
            raise ValidationError(
                _("This opportunity is marked Do not contact and cannot be approved.")
            )

    def action_ggd_approve_outreach(self):
        for lead in self:
            lead._ggd_check_approval_allowed(
                lead.ggd_do_not_contact,
                lead.ggd_contact_basis,
                lead.ggd_contact_basis_note,
            )
            lead.write(
                {
                    "ggd_outreach_approved": True,
                    "ggd_outreach_approved_by": self.env.user.id,
                    "ggd_outreach_approved_at": fields.Datetime.now(),
                    "ggd_contact_basis_verified_at": fields.Datetime.now(),
                    "ggd_approved_draft_version": lead.ggd_draft_version,
                    "ggd_approved_recipient": email_normalize(lead.email_from),
                    "ggd_draft_status": "approved",
                }
            )
            lead.message_post(body=_("GGD outreach approved for manual-gated automation."))
        return True

    def _ggd_check_claim_access(self):
        """Run the ORM's own access and record-rule checks before raw SQL.

        The claim guard reads with SQL, which bypasses ir.model.access and
        ir.rule completely. Calling the ORM check first means a user who could
        not write these records cannot use the claim path to lock their rows or
        to learn anything about their approval state.
        """
        checker = getattr(self, "check_access", None)
        if checker is not None:
            # Odoo 18+ merged the rights and rule checks into one call.
            checker("write")
            return
        self.check_access_rights("write")
        self.check_access_rule("write")

    def _ggd_lock_outbound_state(self):
        """Lock these crm.lead rows and return {id: committed outbound state}.

        This is the core of the duplicate-send guard, and it deliberately uses
        SQL rather than an ORM read. An ORM read is answered from this
        transaction's cache and cannot see a change another n8n execution, or a
        human in Odoo, committed a moment ago - which is precisely the case
        that produces a duplicate or an unauthorised send. SELECT ... FOR UPDATE
        takes a row lock and, under PostgreSQL's READ COMMITTED default,
        re-reads the latest committed version of the row once any competing
        transaction has released it.

        Every column in GGD_CLAIM_STATE_COLUMNS is read in that single locked
        statement, not just the send key. The approval, suppression and
        contact-basis state is therefore read at the same instant as the key and
        under the same lock, which closes the window between the workflow's
        earlier snapshot and the claim.

        Rows are locked one at a time in ascending id order. A single statement
        with ORDER BY would usually lock in the same sequence, but the planner
        is free to sort after locking; an explicit loop makes the ordering
        guaranteed rather than probable. Deterministic ordering is what stops
        two overlapping multi-record writes from deadlocking against each
        other.

        The lock is held until the surrounding transaction ends, so a caller
        that locks and then writes cannot be overtaken in between.

        SQL is used only for the lock and the read. The field update itself
        always goes through the ORM, so tracking, chatter and constraints
        behave normally.

        The pending ORM write buffer is flushed first. Odoo defers the UPDATE
        behind write() until something forces a flush, and raw SQL is not one
        of those things, so without this the lock read could miss a change made
        earlier in this same transaction.
        """
        self._ggd_check_claim_access()
        self.flush_recordset(list(self.GGD_CLAIM_STATE_COLUMNS))
        columns = ", ".join('"%s"' % name for name in self.GGD_CLAIM_STATE_COLUMNS)
        query = "SELECT " + columns + " FROM crm_lead WHERE id = %s FOR UPDATE"
        locked = {}
        for lead_id in sorted(self.ids):
            self.env.cr.execute(query, (lead_id,))
            row = self.env.cr.dictfetchone()
            if row is not None:
                locked[lead_id] = row
        return locked

    def _ggd_claim_blockers(self, state):
        """Reasons the stored record may not be claimed for an outbound send.

        Takes the committed values read under the row lock, so this judges the
        record as it is at claim time rather than as the workflow first saw it.

        Returns reasons, never values. The caller turns these into an error
        message that crosses the RPC boundary into n8n logs, and the contents
        of a locked row must not travel with it.
        """
        blockers = []
        if not state.get("ggd_outreach_approved"):
            blockers.append(_("outreach is not approved"))
        if not state.get("ggd_outreach_approved_by"):
            blockers.append(_("the approving user is missing"))
        if not state.get("ggd_outreach_approved_at"):
            blockers.append(_("the approval timestamp is missing"))
        if state.get("ggd_do_not_contact"):
            blockers.append(_("the record is marked Do not contact"))
        if not state.get("ggd_contact_basis_verified_at"):
            blockers.append(_("the contact-basis verification timestamp is missing"))
        if not (state.get("email_from") or "").strip():
            blockers.append(_("the recipient email address is missing"))
        approved_recipient = (state.get("ggd_approved_recipient") or "").strip()
        current_recipient = email_normalize(state.get("email_from") or "") or ""
        if not approved_recipient:
            blockers.append(_("the approved recipient is missing"))
        elif current_recipient != approved_recipient:
            blockers.append(_("the current recipient is not the recipient that was approved"))
        if not (state.get("ggd_draft_subject") or "").strip():
            blockers.append(_("the reviewed draft subject is missing"))
        if not (state.get("ggd_draft_body") or "").strip():
            blockers.append(_("the reviewed draft body is missing"))
        draft_version = state.get("ggd_draft_version")
        approved_version = state.get("ggd_approved_draft_version")
        if not draft_version or not approved_version:
            blockers.append(_("the reviewed draft version is missing"))
        elif draft_version != approved_version:
            blockers.append(_("the current draft is not the draft that was approved"))
        return blockers

    def _ggd_raise_claim_blocked(self, blockers):
        raise ValidationError(
            _(
                "This opportunity cannot be claimed for an outbound send: "
                "%(reasons)s. The stored record was re-read under a lock at "
                "claim time, so this reflects the record as it is now, not as "
                "the workflow first read it. No message was sent.",
                reasons="; ".join(blockers),
            )
        )

    @staticmethod
    def _ggd_expected_send_key(lead_id, state):
        version = state.get("ggd_approved_draft_version")
        return "%s:%s" % (lead_id, version) if version else False

    def _ggd_check_send_key_matches_approved_draft(self, lead_id, state, send_key):
        if send_key != self._ggd_expected_send_key(lead_id, state):
            raise ValidationError(
                _(
                    "The send key does not identify the currently approved draft. "
                    "Use opportunity ID + ':' + approved draft version. No message was sent."
                )
            )

    def ggd_claim_send_key(self, send_key):
        """Atomically claim a send key. Returns True if this caller may send.

        Called by the outbound workflow immediately BEFORE SMTP. The write
        happens first so that a crash between claiming and sending leaves the
        key claimed - the failure mode is a missed send that a human can
        investigate, never a duplicate send.

        Returns False if the key is already claimed, which means the send has
        already happened or is in flight. The caller must then stop without
        contacting anyone.

        Raises ValidationError if the stored record is not currently safe to
        send: approval missing or incomplete, Do not contact set, or the
        contact-basis evidence absent or insufficient. False and a raise mean
        different things and callers depend on the difference - False is
        "already sent", a raise is "must not send" - so the two are never
        collapsed.

        The duplicate check runs before the approval check on purpose. A record
        that has just been sent has had its approval consumed, so checking
        approval first would report an already-sent key as "not approved" and
        lose the idempotency signal the caller relies on.

        The claim is decided here, under the row lock taken by
        _ggd_lock_outbound_state(), rather than by catching the error write()
        would raise. Catching would risk turning an unrelated ValidationError -
        an approval-gate refusal, a field constraint - into a False that the
        caller would read as "already sent". Because the lock is held for the
        rest of the transaction, the re-check inside write() cannot disagree
        with the decision taken here.
        """
        self.ensure_one()
        if not send_key:
            raise ValidationError(_("A send key is required before sending."))
        state = self._ggd_lock_outbound_state().get(self.id) or {}
        if state.get("ggd_last_send_key") == send_key:
            return False
        blockers = self._ggd_claim_blockers(state)
        if blockers:
            self._ggd_raise_claim_blocked(blockers)
        self._ggd_check_send_key_matches_approved_draft(self.id, state, send_key)
        now = fields.Datetime.now()
        self._ggd_check_daily_send_cap(now)
        self.write({
            "ggd_last_send_key": send_key,
            "ggd_last_sent_at": now,
        })
        return True

    def _ggd_daily_send_cap(self):
        """The configured cap as a non-negative int, or raise.

        A parameter that cannot be read as an integer, or is negative, stops
        sending rather than falling back to the default. A typo in the one
        value that limits outbound volume must fail closed.
        """
        raw = (
            self.env["ir.config_parameter"]
            .sudo()
            .get_param(self.GGD_DAILY_SEND_CAP_PARAM)
        )
        if raw is False or raw is None:
            return self.GGD_DAILY_SEND_CAP_DEFAULT
        try:
            cap = int(str(raw).strip())
        except ValueError:
            cap = -1
        if cap < 0:
            raise ValidationError(
                _(
                    "The system parameter %(param)s is set to %(value)r, which "
                    "is not a whole number of zero or more. Sending is stopped "
                    "until it is corrected. No message was sent.",
                    param=self.GGD_DAILY_SEND_CAP_PARAM,
                    value=raw,
                )
            )
        return cap

    def _ggd_check_daily_send_cap(self, now):
        """Refuse the claim if it would exceed the trailing-24-hour cap.

        Counts claims, not confirmed sends: a claim is the moment the addon
        commits to an SMTP call, and an uncertain or failed send still cost
        the domain a connection. Released claims clear ggd_last_sent_at and
        so drop out of the count, which is right - releasing is a human
        saying "this one never went".

        The row lock taken earlier covers only this lead. Two workflow
        executions claiming two different leads at the same instant would
        each count the other as absent and both pass a cap of n with n-1
        already used. A transaction-scoped advisory lock on a fixed key
        serialises the count-and-claim across leads; it is released at
        commit, after the ORM write below has been flushed, so the next
        claimant sees this one.
        """
        cap = self._ggd_daily_send_cap()
        self.env.cr.execute("SELECT pg_advisory_xact_lock(hashtext(%s))", (self.GGD_DAILY_SEND_CAP_PARAM,))
        self.flush_model(["ggd_last_sent_at"])
        self.env.cr.execute(
            "SELECT count(*) FROM crm_lead WHERE ggd_last_sent_at >= %s",
            (now - timedelta(hours=24),),
        )
        used = self.env.cr.fetchone()[0]
        if used >= cap:
            raise ValidationError(
                _(
                    "The daily send cap has been reached: %(used)s send(s) "
                    "were claimed in the last 24 hours and the cap "
                    "(%(param)s) is %(cap)s. No message was sent. Raise the "
                    "cap in Settings > Technical > System Parameters if this "
                    "is intended, or wait.",
                    used=used,
                    param=self.GGD_DAILY_SEND_CAP_PARAM,
                    cap=cap,
                )
            )

    def ggd_finalize_send(
        self,
        message_id=False,
        recipient=False,
        subject=False,
        body_summary=False,
    ):
        """Confirm SMTP success, store its full audit data, and consume approval."""
        self.ensure_one()
        self._ggd_check_claim_access()
        self.flush_recordset(
            [
                "ggd_last_send_key",
                "ggd_last_sent_at",
                "ggd_last_confirmed_send_key",
                "ggd_delivery_status",
                "ggd_claimed_recipient",
                "ggd_claimed_draft_version",
                "ggd_draft_subject",
            ]
        )
        self.env.cr.execute(
            "SELECT ggd_last_send_key, ggd_last_sent_at, "
            "ggd_last_confirmed_send_key, ggd_delivery_status, "
            "ggd_claimed_recipient, ggd_claimed_draft_version, "
            "ggd_draft_subject FROM crm_lead WHERE id = %s FOR UPDATE",
            (self.id,),
        )
        claim = self.env.cr.dictfetchone() or {}
        if not claim.get("ggd_last_send_key") or not claim.get("ggd_last_sent_at"):
            raise ValidationError(
                _(
                    "This opportunity has no claimed send to finalise. A send "
                    "key must be claimed before a completed send can be recorded."
                )
            )
        supplied = [message_id, recipient, subject, body_summary]
        if not all((value or "").strip() for value in supplied):
            raise ValidationError(
                _(
                    "Finalising a workflow send requires the SMTP message ID, "
                    "recipient, exact subject, and a body summary."
                )
            )
        if claim.get("ggd_last_confirmed_send_key") == claim.get("ggd_last_send_key"):
            return False
        if claim.get("ggd_delivery_status") != "claimed":
            raise ValidationError(_("The claimed send is no longer in flight."))
        normalized_recipient = email_normalize(recipient or "") or ""
        if normalized_recipient != (claim.get("ggd_claimed_recipient") or "").strip():
            raise ValidationError(_("The SMTP recipient does not match the approved lead."))
        if subject.strip() != (claim.get("ggd_draft_subject") or "").strip():
            raise ValidationError(_("The sent subject does not match the approved draft."))
        now = fields.Datetime.now()
        values = {
            "ggd_last_message_date": now.date(),
            "ggd_send_confirmed_at": now,
            "ggd_last_confirmed_send_key": claim.get("ggd_last_send_key"),
            "ggd_delivery_status": "accepted",
            "ggd_last_sent_draft_version": claim.get("ggd_claimed_draft_version"),
            "ggd_draft_status": "sent",
            "ggd_outreach_approved": False,
            "ggd_outreach_approved_by": False,
            "ggd_outreach_approved_at": False,
            "ggd_approved_recipient": False,
            "ggd_claimed_recipient": False,
            "ggd_claimed_draft_version": False,
        }
        values.update(
            {
                "ggd_last_message_id": message_id.strip(),
                "ggd_last_sent_recipient": recipient.strip(),
                "ggd_last_sent_subject": subject.strip(),
                "ggd_last_sent_body_summary": body_summary.strip(),
            }
        )
        self.write(values)
        self.message_post(
            body=_(
                "GGD outreach accepted by SMTP. Approval was consumed; inbound "
                "reply and bounce monitoring must determine the delivery outcome."
            )
        )
        return True

    def ggd_record_reply(
        self,
        category,
        summary,
        suggested_next_action,
        confidence,
        response_draft=False,
        reply_message_id=False,
        received_at=False,
        suggested_follow_up_at=False,
    ):
        """Apply one validated Workflow 4 result to the matched opportunity."""
        self.ensure_one()
        if category not in self.GGD_REPLY_CATEGORIES:
            raise ValidationError(_("Unknown reply category."))
        try:
            confidence = float(confidence)
        except (TypeError, ValueError) as exc:
            raise ValidationError(_("Reply confidence must be a number.")) from exc
        if not 0 <= confidence <= 1:
            raise ValidationError(_("AI confidence must be between 0.00 and 1.00."))
        if not (summary or "").strip() or not (suggested_next_action or "").strip():
            raise ValidationError(
                _("Reply analysis requires a summary and suggested next action.")
            )
        received = self._ggd_parse_workflow_datetime(
            received_at, _("Reply received at")
        ) or fields.Datetime.now()
        normalized_message_id = (reply_message_id or "").strip()
        self._ggd_check_claim_access()
        self.flush_recordset(
            [
                "ggd_last_reply_message_id",
                "ggd_last_reply_received_at",
                "ggd_do_not_contact",
            ]
        )
        self.env.cr.execute(
            "SELECT ggd_last_reply_message_id, ggd_last_reply_received_at, "
            "ggd_do_not_contact FROM crm_lead WHERE id = %s FOR UPDATE",
            (self.id,),
        )
        latest = self.env.cr.dictfetchone() or {}
        if (
            normalized_message_id
            and normalized_message_id == latest.get("ggd_last_reply_message_id")
        ):
            return False
        last_received = latest.get("ggd_last_reply_received_at")
        if last_received and received <= last_received:
            if category == "unsubscribe" and not latest.get("ggd_do_not_contact"):
                self.write({"ggd_do_not_contact": True})
                self.message_post(
                    body=_(
                        "GGD received an older unsubscribe message and applied suppression "
                        "without replacing the latest reply analysis."
                    )
                )
            return False
        follow_up = self._ggd_parse_workflow_datetime(
            suggested_follow_up_at, _("Suggested follow-up at")
        )
        needs_review = confidence < 0.7 or category == "unclear"
        suppressed = latest.get("ggd_do_not_contact") or category == "unsubscribe"
        values = {
            "ggd_reply_category": category,
            "ggd_reply_summary": summary.strip(),
            "ggd_suggested_next_action": (
                _("No outbound action — contact is suppressed.")
                if suppressed
                else suggested_next_action.strip()
            ),
            "ggd_ai_confidence": confidence,
            "ggd_ai_last_analyzed_at": fields.Datetime.now(),
            "ggd_last_reply_received_at": received,
            "ggd_last_message_date": received.date(),
            "ggd_response_draft": (
                False if suppressed else (response_draft or "").strip() or False
            ),
            "ggd_suggested_follow_up_at": False if suppressed else follow_up,
        }
        values.update(
            self._ggd_review_values(
                "ggd_reply_needs_review",
                needs_review,
                _("Reply analysis needs human review because confidence is low or unclear."),
            )
        )
        if normalized_message_id:
            values["ggd_last_reply_message_id"] = normalized_message_id
        if category == "unsubscribe":
            values["ggd_do_not_contact"] = True
        self.write(values)
        self.message_post(
            body=Markup("<p>%s</p><p>%s</p>")
            % (
                escape(_("GGD reply analysis recorded.")),
                escape(summary.strip()),
            )
        )
        return not needs_review

    def ggd_save_response_draft(self, draft):
        """Store one hand-written reply draft. Returns {"saved": True}.

        The ChatGPT connector calls this when Kaan has written the reply there
        instead of taking the one Workflow 4 suggested. It writes exactly one
        field. ggd_response_draft is a suggestion for a human to read: nothing
        sends it, and it is not the gated outreach draft, so this method is
        outside the outbound gate rather than a second door into it.

        Suppression is honoured exactly as ggd_record_reply honours it. That
        method stores no draft when the contact is suppressed, so a
        hand-written one must not become the way around it - otherwise this
        would be the single path that puts a reply draft on a lead that asked
        not to be contacted.

        Returns a dict rather than a bare bool or string for the reason
        ggd_prepare_draft documents at length: a top-level JSON scalar is legal
        but some HTTP clients refuse to parse it, and a caller that cannot read
        the result of a write it has already made is the shape defect 13 took.
        """
        self.ensure_one()
        draft = (draft or "").strip()
        if not draft:
            raise ValidationError(_("A reply draft cannot be empty. Nothing was saved."))
        if len(draft) > self.GGD_RESPONSE_DRAFT_MAX_LENGTH:
            raise ValidationError(
                _(
                    "The reply draft is %(length)s characters and the maximum "
                    "is %(maximum)s. Nothing was saved.",
                    length=len(draft),
                    maximum=self.GGD_RESPONSE_DRAFT_MAX_LENGTH,
                )
            )
        if self.ggd_do_not_contact or self.ggd_reply_category == "unsubscribe":
            raise ValidationError(
                _(
                    "This contact is suppressed, so no reply draft may be "
                    "stored for it. Nothing was saved."
                )
            )
        self.write({"ggd_response_draft": draft})
        self.message_post(
            body=_("Reply draft written by hand and saved. Nothing was sent.")
        )
        return {"saved": True}

    def ggd_record_bounce(self, message_id, summary, hard_bounce=True):
        """Record a delivery failure and suppress hard-bounce recipients."""
        self.ensure_one()
        if not (message_id or "").strip() or not (summary or "").strip():
            raise ValidationError(_("Bounce handling requires a message ID and summary."))
        if (
            not self.ggd_send_confirmed_at
            or not self.ggd_last_message_id
            or message_id.strip() != self.ggd_last_message_id
        ):
            raise ValidationError(_("The bounce message ID does not match this opportunity."))
        values = {
            "ggd_delivery_status": "bounced",
        }
        values.update(
            self._ggd_review_values(
                "ggd_delivery_needs_review", True, summary.strip()
            )
        )
        if hard_bounce:
            values["ggd_do_not_contact"] = True
        self.write(values)
        self.message_post(
            body=Markup("<p>%s</p><p>%s</p>")
            % (escape(_("GGD email bounce recorded.")), escape(summary.strip()))
        )
        return True

    def ggd_queue_follow_up(self, draft):
        """Atomically create one manual follow-up activity per confirmed send."""
        self.ensure_one()
        draft = (draft or "").strip()
        if not draft:
            raise ValidationError(_("A follow-up draft is required."))
        self._ggd_check_claim_access()
        self.flush_recordset(
            [
                "active",
                "stage_id",
                "ggd_do_not_contact",
                "ggd_automation_needs_review",
                "ggd_send_confirmed_at",
                "ggd_last_confirmed_send_key",
                "ggd_delivery_status",
                "ggd_last_reply_received_at",
                "ggd_last_follow_up_queue_key",
            ]
        )
        self.env.cr.execute(
            "SELECT active, stage_id, ggd_do_not_contact, "
            "ggd_automation_needs_review, ggd_send_confirmed_at, "
            "ggd_last_confirmed_send_key, ggd_delivery_status, "
            "ggd_last_reply_received_at, ggd_last_follow_up_queue_key "
            "FROM crm_lead WHERE id = %s FOR UPDATE",
            (self.id,),
        )
        state = self.env.cr.dictfetchone() or {}
        confirmed_at = state.get("ggd_send_confirmed_at")
        stage = self.env["crm.stage"].browse(state.get("stage_id"))
        if not state.get("active") or stage.is_won:
            raise ValidationError(
                _("Won, lost, or archived opportunities are not follow-up candidates.")
            )
        if state.get("ggd_do_not_contact"):
            raise ValidationError(_("Do not contact is set; no follow-up may be queued."))
        if state.get("ggd_automation_needs_review"):
            raise ValidationError(
                _("Resolve the automation review item before queuing follow-up.")
            )
        if state.get("ggd_delivery_status") != "accepted":
            raise ValidationError(
                _("Only an SMTP-accepted outbound message can be followed up.")
            )
        if not confirmed_at:
            raise ValidationError(_("No confirmed outbound send exists to follow up."))
        if confirmed_at > fields.Datetime.now() - timedelta(days=7):
            raise ValidationError(_("The last confirmed send is not yet seven days old."))
        reply_received_at = state.get("ggd_last_reply_received_at")
        if reply_received_at and reply_received_at >= confirmed_at:
            raise ValidationError(
                _("A reply was received after the last send; follow-up is not due.")
            )
        confirmed_key = state.get("ggd_last_confirmed_send_key")
        if not confirmed_key:
            raise ValidationError(_("The confirmed send has no durable send key."))
        queue_key = "%s:%s" % (self.id, confirmed_key)
        if state.get("ggd_last_follow_up_queue_key") == queue_key:
            return False
        responsible = self.user_id or self.env.user
        note = Markup("<p>%s</p><pre>%s</pre>") % (
            escape(_("Review this suggested follow-up. Nothing was sent automatically.")),
            escape(draft),
        )
        self.write(
            {
                "ggd_follow_up_draft": draft,
                "ggd_last_follow_up_queue_key": queue_key,
                "ggd_last_follow_up_queued_at": fields.Datetime.now(),
            }
        )
        self.activity_schedule(
            "mail.mail_activity_data_todo",
            date_deadline=fields.Date.context_today(self),
            summary=_("Review GGD follow-up draft"),
            note=note,
            user_id=responsible.id,
        )
        self.message_post(
            body=_("GGD follow-up draft queued for manual review. Nothing was sent.")
        )
        return True

    def action_ggd_release_failed_send_claim(self):
        """Release a known-failed SMTP claim after a human checks Zoho Sent."""
        for lead in self:
            lead._ggd_check_claim_access()
            lead.flush_recordset(
                [
                    "ggd_last_send_key",
                    "ggd_last_confirmed_send_key",
                    "ggd_delivery_status",
                ]
            )
            lead.env.cr.execute(
                "SELECT ggd_last_send_key, ggd_last_confirmed_send_key, "
                "ggd_delivery_status FROM crm_lead WHERE id = %s FOR UPDATE",
                (lead.id,),
            )
            state = lead.env.cr.dictfetchone() or {}
            if (
                state.get("ggd_delivery_status") != "claimed"
                or not state.get("ggd_last_send_key")
                or state.get("ggd_last_send_key")
                == state.get("ggd_last_confirmed_send_key")
            ):
                raise ValidationError(
                    _("Only an unresolved, unconfirmed SMTP claim can be released.")
                )
            lead.write(
                {
                    "ggd_last_send_key": False,
                    "ggd_last_sent_at": False,
                    "ggd_delivery_status": "none",
                    "ggd_claimed_recipient": False,
                    "ggd_claimed_draft_version": False,
                    "ggd_last_claim_released_at": fields.Datetime.now(),
                    "ggd_last_claim_released_by": self.env.user.id,
                }
            )
            lead.message_post(
                body=_(
                    "GGD failed send claim released by %(user)s after manual "
                    "mailbox verification. The approved draft may be claimed again.",
                    user=self.env.user.display_name,
                )
            )
        return True

    def action_ggd_revoke_outreach(self):
        for lead in self:
            lead.write(
                {
                    "ggd_outreach_approved": False,
                    "ggd_outreach_approved_by": False,
                    "ggd_outreach_approved_at": False,
                    "ggd_contact_basis_verified_at": False,
                    "ggd_approved_draft_version": False,
                    "ggd_approved_recipient": False,
                    "ggd_draft_status": "ready" if lead.ggd_draft_version else "empty",
                }
            )
            lead.message_post(body=_("GGD outreach approval revoked."))
        return True

    @api.onchange("ggd_do_not_contact")
    def _onchange_ggd_do_not_contact(self):
        if self.ggd_do_not_contact:
            self.ggd_outreach_approved = False

    @api.model_create_multi
    def create(self, vals_list):
        for values in vals_list:
            has_draft_content = bool(
                (values.get("ggd_draft_subject") or "").strip()
                or (values.get("ggd_draft_body") or "").strip()
            )
            if has_draft_content:
                values.setdefault("ggd_draft_version", uuid4().hex)
                values.setdefault("ggd_draft_status", "ready")
            if values.get("ggd_last_send_key"):
                # A send key is a claim against an already-stored, already
                # approved record. create() never passes through the locked
                # approval check in write(), so a key accepted here would be a
                # claim nobody validated - a record springing into existence
                # with a send already marked as taken. There is no legitimate
                # caller for this.
                raise ValidationError(
                    _(
                        "A send key cannot be set when an opportunity is "
                        "created. Create the record, have a human approve "
                        "outreach, then let the send workflow claim the key "
                        "against the stored record."
                    )
                )
            if values.get("ggd_do_not_contact"):
                values.update(
                    {
                        "ggd_outreach_approved": False,
                        "ggd_outreach_approved_by": False,
                        "ggd_outreach_approved_at": False,
                        "ggd_contact_basis_verified_at": False,
                        "ggd_approved_draft_version": False,
                        "ggd_approved_recipient": False,
                    }
                )
            elif values.get("ggd_outreach_approved"):
                # Closes the same hole as write(): a record must not be able to
                # come into existence already approved on a basis that could
                # never have been approved afterwards.
                self._ggd_check_approval_allowed(
                    values.get("ggd_do_not_contact"),
                    values.get("ggd_contact_basis"),
                    values.get("ggd_contact_basis_note"),
                )
                values.setdefault("ggd_outreach_approved_by", self.env.user.id)
                values.setdefault("ggd_outreach_approved_at", fields.Datetime.now())
                values.setdefault("ggd_contact_basis_verified_at", fields.Datetime.now())
                values.setdefault(
                    "ggd_approved_draft_version", values.get("ggd_draft_version")
                )
                values.setdefault(
                    "ggd_approved_recipient", email_normalize(values.get("email_from"))
                )
                values["ggd_draft_status"] = "approved"
        return super().create(vals_list)

    @staticmethod
    def _ggd_is_revoking_approval(values):
        """True when this write sets outreach approval to any falsy value.

        n8n, the Odoo client and a hand-written RPC call can each send False, 0
        or None for a boolean. All three mean the same thing to a human, so all
        three must clear the approver, the approval time and the basis-verified
        time. Recognising only an exact False left the other two producing an
        unapproved record that still carried the metadata of its old approval,
        which reads as a live approval to anyone auditing it.

        One definition, used both by the revocation branch in write() and by
        the suppression check, so the two cannot drift apart again.
        """
        return "ggd_outreach_approved" in values and not values["ggd_outreach_approved"]

    @classmethod
    def _ggd_is_clearing_draft(cls, values):
        """True when this write REMOVES the draft rather than editing it.

        write() treats any touch of a draft field as an edit and forces
        ggd_draft_status to "ready". That is right for an edit and wrong for a
        clear: writing subject, body and version all to False left the record
        claiming to be draft-ready with no version and nothing to approve - a
        state no legitimate path should be able to produce, and one that reads
        to a human reviewer as "there is a draft here" when there is not.

        The condition is deliberately narrow and record-independent: the write
        must set BOTH the subject and the body, and both must be empty after
        stripping. Anything less is an edit. Requiring both fields keeps this
        correct for a multi-record write, because the answer depends only on
        the values being written and never on what any individual record
        currently holds.
        """
        if "ggd_draft_subject" not in values or "ggd_draft_body" not in values:
            return False
        subject = (values.get("ggd_draft_subject") or "").strip()
        body = (values.get("ggd_draft_body") or "").strip()
        return not subject and not body

    @classmethod
    def _ggd_is_suppressing(cls, values):
        """True when this write revokes approval or marks Do not contact.

        Detected broadly, because letting a claim through by mistake is the
        expensive error and dropping one is not.
        """
        if values.get("ggd_do_not_contact"):
            return True
        return cls._ggd_is_revoking_approval(values)

    def write(self, values):
        if len(self) > 1 and (
            values.get("ggd_outreach_approved")
            or any(
                field_name in values
                for field_name in self.GGD_APPROVAL_INPUT_FIELDS
            )
        ):
            for lead in self:
                lead.write(dict(values))
            return True
        approval_input_changed = any(
            field_name in values for field_name in self.GGD_APPROVAL_INPUT_FIELDS
        )
        draft_changed = any(field_name in values for field_name in self.GGD_DRAFT_FIELDS)
        if "ggd_do_not_contact" in values and not values["ggd_do_not_contact"]:
            # Setting the flag is open to everyone, including the reply
            # workflow that acts on an unsubscribe. Clearing it re-opens a
            # person to outreach and is an approver's decision.
            if any(lead.ggd_do_not_contact for lead in self):
                self._ggd_check_approver(_("clear Do not contact"))
        if approval_input_changed:
            for lead in self:
                lead._ggd_check_no_unresolved_send_claim(
                    lead.ggd_delivery_status,
                    lead.ggd_last_send_key,
                    lead.ggd_last_confirmed_send_key,
                )
        # Kaan's decision, 4 September 2026: editing a draft or changing the
        # recipient no longer revokes the approval. It used to, on the reasoning
        # that a human approved one specific version and an edited version is
        # not that one. The approval now follows the edit instead: the approved
        # version and recipient are re-pointed at what the record says after the
        # write, so the send goes out with the edited text rather than stalling.
        #
        # Removing the revocation alone would not have been enough - the claim
        # compares the current draft version against the approved one, so an
        # edited draft would have failed later at the claim instead of here.
        # Both had to move together or the change would only relocate the
        # failure. The chatter note below is what is left of the old guarantee:
        # the record still says that its approved content changed, and when.
        edited_after_approval = self.filtered("ggd_outreach_approved")
        if draft_changed:
            values = dict(values)
            if self._ggd_is_clearing_draft(values):
                values.update(
                    {
                        "ggd_draft_version": False,
                        "ggd_draft_status": "empty",
                        # Nothing left to send, so no version can be approved.
                        # The approval flag stays; the claim refuses on the
                        # missing subject and body, as it does for any approval
                        # granted without a draft.
                        "ggd_approved_draft_version": False,
                    }
                )
            else:
                values.setdefault("ggd_draft_version", uuid4().hex)
                values["ggd_draft_status"] = "ready"
                if edited_after_approval:
                    values["ggd_approved_draft_version"] = values[
                        "ggd_draft_version"
                    ]
        if "email_from" in values and edited_after_approval:
            values = dict(values)
            values.setdefault(
                "ggd_approved_recipient", email_normalize(values.get("email_from"))
            )
        send_key = values.get("ggd_last_send_key")
        if send_key and self._ggd_is_suppressing(values):
            # Suppression always wins. A write that marks Do not contact or
            # revokes approval must succeed even when it also carries a send
            # key, so the guard steps aside rather than refusing the write and
            # rolling the suppression back. The key is dropped instead, because
            # a suppression is not a send and must not leave a claim behind.
            # An explicitly supplied ggd_last_sent_at is left alone; only the
            # automatic stamp below is skipped.
            values = dict(values)
            values.pop("ggd_last_send_key", None)
            send_key = None

        if send_key:
            # The duplicate-send guard lives here, not only in
            # ggd_claim_send_key(), because the deployed n8n workflow does not
            # call that method: its "Claim send key before SMTP" node performs
            # an ordinary Odoo record update. A guard that protects only one
            # route is not a guard. Enforcing it in write() covers the n8n
            # update node, the RPC method, the Odoo interface and any future
            # caller alike.
            #
            # Raising is what makes the n8n node fail closed: the RPC returns a
            # fault, the node errors, and the run stops before the SMTP node.
            if values.get("ggd_outreach_approved"):
                raise ValidationError(
                    _(
                        "A send key cannot be claimed in the same write that "
                        "grants outreach approval. Human approval must already "
                        "be committed, and re-read under the claim lock, before "
                        "a send is claimed."
                    )
                )
            locked = self._ggd_lock_outbound_state()
            for lead_id, state in locked.items():
                # Duplicate first: an already-sent record has had its approval
                # consumed, and must be reported as a duplicate rather than as
                # an approval failure.
                if state.get("ggd_last_send_key") == send_key:
                    raise ValidationError(
                        _(
                            "This send key is already claimed for this "
                            "opportunity. A message for this approval has been "
                            "sent or is in flight, so this send must stop "
                            "before SMTP. Check the sent-mail folder before "
                            "revoking and re-approving."
                        )
                    )
                blockers = self._ggd_claim_blockers(state)
                if blockers:
                    self._ggd_raise_claim_blocked(blockers)
                self._ggd_check_send_key_matches_approved_draft(
                    lead_id, state, send_key
                )
            # A successful claim is what marks the send as in flight, so record
            # when it happened. setdefault leaves an explicit value from the
            # caller - ggd_claim_send_key() supplies one - untouched. The copy
            # keeps the caller's dict unmodified.
            values = dict(values)
            values.setdefault("ggd_last_sent_at", fields.Datetime.now())
            values.setdefault("ggd_delivery_status", "claimed")
            if len(self) == 1:
                claim_state = locked.get(self.id) or {}
                values.setdefault(
                    "ggd_claimed_recipient",
                    email_normalize(claim_state.get("email_from") or ""),
                )
                values.setdefault(
                    "ggd_claimed_draft_version",
                    claim_state.get("ggd_approved_draft_version"),
                )

        if values.get("ggd_do_not_contact"):
            values.update(
                {
                    "ggd_outreach_approved": False,
                    "ggd_outreach_approved_by": False,
                    "ggd_outreach_approved_at": False,
                    "ggd_contact_basis_verified_at": False,
                    "ggd_approved_draft_version": False,
                    "ggd_approved_recipient": False,
                }
            )
        elif self._ggd_is_revoking_approval(values):
            values.update(
                {
                    "ggd_outreach_approved_by": False,
                    "ggd_outreach_approved_at": False,
                    "ggd_contact_basis_verified_at": False,
                    "ggd_approved_draft_version": False,
                    "ggd_approved_recipient": False,
                }
            )
        elif values.get("ggd_outreach_approved"):
            # Approval is being granted directly rather than through the
            # button. Apply the same checks, evaluated against the values this
            # write will leave behind.
            for lead in self:
                lead._ggd_check_approval_allowed(
                    values.get("ggd_do_not_contact", lead.ggd_do_not_contact),
                    values.get("ggd_contact_basis", lead.ggd_contact_basis),
                    values.get("ggd_contact_basis_note", lead.ggd_contact_basis_note),
                )
            # Stamp the approval metadata and approved draft version that the
            # button would have set. Without these, the outbound claim cannot
            # prove which human-reviewed subject/body it covers.
            values.setdefault("ggd_outreach_approved_by", self.env.user.id)
            values.setdefault("ggd_outreach_approved_at", fields.Datetime.now())
            values.setdefault("ggd_contact_basis_verified_at", fields.Datetime.now())
            if len(self) == 1:
                values.setdefault(
                    "ggd_approved_draft_version",
                    values.get("ggd_draft_version", self.ggd_draft_version),
                )
                values.setdefault(
                    "ggd_approved_recipient",
                    email_normalize(values.get("email_from", self.email_from)),
                )
                values.setdefault("ggd_draft_status", "approved")
        result = super().write(values)
        if edited_after_approval and (draft_changed or "email_from" in values):
            changed = [
                label
                for field, label in (
                    ("ggd_draft_subject", _("the subject")),
                    ("ggd_draft_body", _("the body")),
                    ("email_from", _("the recipient")),
                )
                if field in values
            ]
            if changed:
                for lead in edited_after_approval:
                    lead.message_post(
                        body=_(
                            "Approved outreach edited: %(changed)s changed after "
                            "approval. The approval now covers this version — it "
                            "was not revoked. Re-read the draft before it sends.",
                            changed=", ".join(changed),
                        )
                    )
        return result
