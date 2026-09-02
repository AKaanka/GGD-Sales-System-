import re
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from markupsafe import Markup, escape

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError
from odoo.tools import email_normalize


class CrmLead(models.Model):
    _inherit = "crm.lead"

    # Contact bases that are NOT, by themselves, a lawful basis for a first
    # marketing email under UWG s 7 Abs. 2 Nr. 2. See
    # docs/LAWFUL-CONTACT-PROCEDURE.md section 4. A record on one of these
    # bases can still be called or approached by other means; it cannot be
    # approved for automated email outreach.
    GGD_NO_EMAIL_BASES = (
        "trade_fair_no_optin",
        "referral",
        "other",
    )

    # Minimum length for the contact-basis note. The note must carry actual
    # evidence - a date, a source, a document reference - not a restatement of
    # the selection label. A length floor cannot enforce quality, but it does
    # stop "ok" and "yes" from passing as evidence.
    GGD_CONTACT_BASIS_NOTE_MIN_LENGTH = 20

    # Every column the outbound claim guard must re-read under its row lock.
    # The workflow decides whether a send is lawful from a snapshot taken
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
                "Existing customer — all four UWG §7(3) conditions met",
            ),
            ("inbound", "Inbound enquiry — reply stays within its scope"),
            ("trade_fair", "Trade fair — opt-in recorded at the stand"),
            ("trade_fair_no_optin", "Trade fair — no opt-in (do not email)"),
            ("referral", "Referral / introduction (do not email)"),
            ("other", "Other — requires legal review (do not email)"),
        ],
        string="Contact basis",
        help=(
            "The label states the effect on email outreach. Bases marked "
            "'do not email' cannot be approved for automated outreach; use "
            "telephone, a warm introduction, or post instead. Operational "
            "record only — it does not replace legal review."
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

    def _ggd_check_approval_allowed(self, do_not_contact, contact_basis, basis_note):
        """Raise if this combination may not be approved for email outreach.

        Shared by the approval button, write() and create(), so that setting
        ggd_outreach_approved directly is subject to the same rules. A gate
        enforced only in a UI button is not a gate. Takes plain values rather
        than reading self, so it can also run before a record exists.
        """
        if do_not_contact:
            raise ValidationError(
                _("This opportunity is marked Do not contact and cannot be approved.")
            )
        if not contact_basis:
            raise ValidationError(
                _("Record and review the contact basis before approving outreach.")
            )
        if contact_basis in self.GGD_NO_EMAIL_BASES:
            label = dict(
                self._fields["ggd_contact_basis"].selection
            ).get(contact_basis, contact_basis)
            raise ValidationError(
                _(
                    "Contact basis '%(label)s' is not a lawful basis for a first "
                    "marketing email under UWG §7. Outreach cannot be approved. "
                    "Use a telephone call, a warm introduction, or post instead — "
                    "or record the opt-in evidence and change the basis.",
                    label=label,
                )
            )
        note = (basis_note or "").strip()
        if len(note) < self.GGD_CONTACT_BASIS_NOTE_MIN_LENGTH:
            raise ValidationError(
                _(
                    "Record the evidence for the contact basis before approving. "
                    "State where and when it arose and give a reference that can "
                    "be checked today — not a restatement of the label."
                )
            )

    def action_ggd_approve_outreach(self):
        for lead in self:
            lead._ggd_check_approval_allowed(
                lead.ggd_do_not_contact,
                lead.ggd_contact_basis,
                lead.ggd_contact_basis_note,
            )
            lead._ggd_check_draft_ready(
                lead.ggd_draft_subject,
                lead.ggd_draft_body,
                lead.ggd_draft_version,
            )
            lead._ggd_check_recipient_ready(lead.email_from)
            lead._ggd_check_no_unresolved_send_claim(
                lead.ggd_delivery_status,
                lead.ggd_last_send_key,
                lead.ggd_last_confirmed_send_key,
            )
            lead._ggd_check_draft_can_be_approved(
                lead.ggd_draft_version, lead.ggd_last_sent_draft_version
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
        that produces a duplicate or an unlawful send. SELECT ... FOR UPDATE
        takes a row lock and, under PostgreSQL's READ COMMITTED default,
        re-reads the latest committed version of the row once any competing
        transaction has released it.

        Every column in GGD_CLAIM_STATE_COLUMNS is read in that single locked
        statement, not just the send key. The approval, suppression and
        lawful-basis state is therefore read at the same instant as the key and
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
        basis = state.get("ggd_contact_basis")
        if not basis:
            blockers.append(_("the contact basis is missing"))
        elif basis in self.GGD_NO_EMAIL_BASES:
            blockers.append(
                _("the contact basis is not a lawful basis for a first marketing email")
            )
        note = (state.get("ggd_contact_basis_note") or "").strip()
        if len(note) < self.GGD_CONTACT_BASIS_NOTE_MIN_LENGTH:
            blockers.append(_("the contact-basis note is missing or too short"))
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
        lawful-basis evidence absent or insufficient. False and a raise mean
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
        self.write({
            "ggd_last_send_key": send_key,
            "ggd_last_sent_at": fields.Datetime.now(),
        })
        return True

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
                self._ggd_check_draft_ready(
                    values.get("ggd_draft_subject"),
                    values.get("ggd_draft_body"),
                    values.get("ggd_draft_version"),
                )
                self._ggd_check_recipient_ready(values.get("email_from"))
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
        if approval_input_changed:
            for lead in self:
                lead._ggd_check_no_unresolved_send_claim(
                    lead.ggd_delivery_status,
                    lead.ggd_last_send_key,
                    lead.ggd_last_confirmed_send_key,
                )
        if draft_changed:
            values = dict(values)
            # A draft change always revokes approval, whether the draft was
            # edited or removed: the human approved a specific version, and
            # that version no longer stands either way.
            revocation = {
                "ggd_outreach_approved": False,
                "ggd_outreach_approved_by": False,
                "ggd_outreach_approved_at": False,
                "ggd_contact_basis_verified_at": False,
                "ggd_approved_draft_version": False,
                "ggd_approved_recipient": False,
            }
            if self._ggd_is_clearing_draft(values):
                values.update(revocation)
                values.update(
                    {
                        "ggd_draft_version": False,
                        "ggd_draft_status": "empty",
                    }
                )
            else:
                values.setdefault("ggd_draft_version", uuid4().hex)
                values.update(revocation)
                values["ggd_draft_status"] = "ready"
        elif "email_from" in values and not values.get("ggd_outreach_approved"):
            for lead in self.filtered("ggd_outreach_approved"):
                values = dict(values)
                values.update(
                    {
                        "ggd_outreach_approved": False,
                        "ggd_outreach_approved_by": False,
                        "ggd_outreach_approved_at": False,
                        "ggd_contact_basis_verified_at": False,
                        "ggd_approved_draft_version": False,
                        "ggd_approved_recipient": False,
                        "ggd_draft_status": (
                            "ready" if lead.ggd_draft_version else "empty"
                        ),
                    }
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
                lead._ggd_check_draft_ready(
                    values.get("ggd_draft_subject", lead.ggd_draft_subject),
                    values.get("ggd_draft_body", lead.ggd_draft_body),
                    values.get("ggd_draft_version", lead.ggd_draft_version),
                )
                lead._ggd_check_recipient_ready(
                    values.get("email_from", lead.email_from)
                )
                lead._ggd_check_no_unresolved_send_claim(
                    values.get("ggd_delivery_status", lead.ggd_delivery_status),
                    values.get("ggd_last_send_key", lead.ggd_last_send_key),
                    values.get(
                        "ggd_last_confirmed_send_key",
                        lead.ggd_last_confirmed_send_key,
                    ),
                )
                lead._ggd_check_draft_can_be_approved(
                    values.get("ggd_draft_version", lead.ggd_draft_version),
                    values.get(
                        "ggd_last_sent_draft_version",
                        lead.ggd_last_sent_draft_version,
                    ),
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
        return super().write(values)
