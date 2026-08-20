from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


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
    ggd_last_sent_at = fields.Datetime(
        string="Last outbound send at",
        readonly=True,
        copy=False,
    )
    ggd_last_message_date = fields.Date(
        string="Last message date",
        copy=False,
        readonly=True,
        help="Latest date of any message (sent or received); used for follow-up scheduling.",
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
            lead.write(
                {
                    "ggd_outreach_approved": True,
                    "ggd_outreach_approved_by": self.env.user.id,
                    "ggd_outreach_approved_at": fields.Datetime.now(),
                    "ggd_contact_basis_verified_at": fields.Datetime.now(),
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
        self.write({
            "ggd_last_send_key": send_key,
            "ggd_last_sent_at": fields.Datetime.now(),
        })
        return True

    def ggd_finalize_send(self):
        """Mark send as complete and revoke approval to prevent resends.

        Called by the outbound workflow immediately AFTER successful SMTP.
        Updates message date for follow-up scheduling and clears approval.

        Refuses unless a send key has actually been claimed and stamped. That
        claim is the only evidence the record passed the locked outbound gate.
        Without it, finalising would post a "message sent" audit note and set a
        follow-up date for a send that was never authorised - a control
        reporting success for something that did not happen, which is the
        failure mode this addon has already been bitten by twice.
        """
        self.ensure_one()
        if not self.ggd_last_send_key or not self.ggd_last_sent_at:
            raise ValidationError(
                _(
                    "This opportunity has no claimed send to finalise. A send "
                    "key must be claimed, and its send time stamped, before a "
                    "completed send can be recorded. No audit note was posted "
                    "and no follow-up date was set."
                )
            )
        now = fields.Datetime.now()
        self.write({
            "ggd_last_message_date": now.date(),
            "ggd_outreach_approved": False,
            "ggd_outreach_approved_by": False,
            "ggd_outreach_approved_at": False,
        })
        self.message_post(
            body=_("GGD outreach sent. Approval revoked; reply analysis will run on inbound.")
        )

    def action_ggd_revoke_outreach(self):
        for lead in self:
            lead.write(
                {
                    "ggd_outreach_approved": False,
                    "ggd_outreach_approved_by": False,
                    "ggd_outreach_approved_at": False,
                    "ggd_contact_basis_verified_at": False,
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
    def _ggd_is_suppressing(cls, values):
        """True when this write revokes approval or marks Do not contact.

        Detected broadly, because letting a claim through by mistake is the
        expensive error and dropping one is not.
        """
        if values.get("ggd_do_not_contact"):
            return True
        return cls._ggd_is_revoking_approval(values)

    def write(self, values):
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
            for state in locked.values():
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
            # A successful claim is what marks the send as in flight, so record
            # when it happened. setdefault leaves an explicit value from the
            # caller - ggd_claim_send_key() supplies one - untouched. The copy
            # keeps the caller's dict unmodified.
            values = dict(values)
            values.setdefault("ggd_last_sent_at", fields.Datetime.now())

        if values.get("ggd_do_not_contact"):
            values.update(
                {
                    "ggd_outreach_approved": False,
                    "ggd_outreach_approved_by": False,
                    "ggd_outreach_approved_at": False,
                    "ggd_contact_basis_verified_at": False,
                }
            )
        elif self._ggd_is_revoking_approval(values):
            values.update(
                {
                    "ggd_outreach_approved_by": False,
                    "ggd_outreach_approved_at": False,
                    "ggd_contact_basis_verified_at": False,
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
            # Stamp the approval metadata that the button would have set.
            # Without this, a record approved by a direct write carries no
            # approver and no timestamp, and the outbound send key - which is
            # derived from the approval time - cannot distinguish one approval
            # from the next.
            values.setdefault("ggd_outreach_approved_by", self.env.user.id)
            values.setdefault("ggd_outreach_approved_at", fields.Datetime.now())
            values.setdefault("ggd_contact_basis_verified_at", fields.Datetime.now())
        return super().write(values)
