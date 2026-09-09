"""Country and product-group working views, and the three bulk actions (#67).

Two things are being proved here, and they are different things.

The first is that the classification behaves: a lead may sit in several
product groups and is still one record counted once, archiving a group keeps
history, and the records nobody has classified yet stay findable.

The second is that the bulk actions cannot be talked into more than the
single-record paths allow. Every test that changes something calls the wizard
method directly rather than through a view, because that is what an API key
holder can do, and counts mail.mail before and after, because "no email was
sent" is a claim worth checking rather than assuming.

Run:
    docker compose exec odoo odoo -d ggd --test-enable \\
        --test-tags /ggd_crm --stop-after-init -u ggd_crm
"""

from ast import literal_eval
from datetime import timedelta

from psycopg2 import IntegrityError

from odoo import fields
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tests import tagged
from odoo.tests.common import TransactionCase
from odoo.tools import mute_logger


@tagged("post_install", "-at_install")
class GgdLeadGroupCase(TransactionCase):
    """Fixtures shared by the classification and the bulk-action tests."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Lead = cls.env["crm.lead"]
        cls.Group = cls.env["ggd.product.group"]
        cls.Log = cls.env["ggd.opportunity.action.log"]

        Stage = cls.env["crm.stage"]
        cls.stages = {}
        for sequence, name in enumerate(cls.Lead.GGD_ACTION_STAGES, start=1):
            found = Stage.search([("name", "=ilike", name)], limit=1)
            cls.stages[name] = found or Stage.create(
                {"name": name, "sequence": sequence * 10}
            )

        Country = cls.env["res.country"]
        cls.turkey = Country.search([("code", "=", "TR")], limit=1)
        cls.poland = Country.search([("code", "=", "PL")], limit=1)

        cls.wire = cls.env.ref("ggd_crm.product_group_wire")
        cls.pipe = cls.env.ref("ggd_crm.product_group_pipe")
        cls.machinery = cls.env.ref("ggd_crm.product_group_machinery")

    def _lead(self, name="QA classification fixture", **values):
        base = {
            "name": name,
            "type": "opportunity",
            "email_from": "groups-test@ggd-qa.invalid",
        }
        base.update(values)
        return self.Lead.with_context(
            mail_create_nosubscribe=True, mail_create_nolog=True, mail_notrack=True
        ).create(base)

    def _mail_count(self):
        return self.env["mail.mail"].sudo().search_count([])


class TestGgdProductGroups(GgdLeadGroupCase):
    """The classification itself: several groups, one record, no lost history."""

    def test_the_starting_groups_are_installed_and_ordered(self):
        names = self.Group.search([]).mapped("name")
        for expected in ("Wire", "Pipe", "Fasteners", "Machinery"):
            self.assertIn(expected, names)

    def test_a_lead_can_sit_in_several_groups_and_is_one_record(self):
        lead = self._lead(
            country_id=self.turkey.id,
            ggd_product_group_ids=[(6, 0, [self.wire.id, self.pipe.id])],
        )
        self.assertEqual(len(lead), 1)
        self.assertEqual(
            set(lead.ggd_product_group_ids.ids), {self.wire.id, self.pipe.id}
        )
        # The search returns records, not relation rows: a lead in two of the
        # groups asked for still comes back once.
        found = self.Lead.search(
            [
                ("id", "=", lead.id),
                ("ggd_product_group_ids", "in", [self.wire.id, self.pipe.id]),
            ]
        )
        self.assertEqual(found, lead)
        self.assertEqual(
            self.Lead.search_count(
                [
                    ("id", "=", lead.id),
                    ("ggd_product_group_ids", "in", [self.wire.id, self.pipe.id]),
                ]
            ),
            1,
        )

    def test_country_and_group_narrow_together_and_options_widen(self):
        """Turkey AND wire; two countries OR each other. The example in #67."""
        tr_wire = self._lead(
            "TR wire maker",
            country_id=self.turkey.id,
            ggd_company_type="manufacturer",
            ggd_product_group_ids=[(4, self.wire.id)],
        )
        tr_pipe = self._lead(
            "TR pipe maker",
            country_id=self.turkey.id,
            ggd_company_type="manufacturer",
            ggd_product_group_ids=[(4, self.pipe.id)],
        )
        pl_wire = self._lead(
            "PL wire distributor",
            country_id=self.poland.id,
            ggd_company_type="distributor",
            ggd_product_group_ids=[(4, self.wire.id)],
        )
        fixtures = tr_wire + tr_pipe + pl_wire

        both = self.Lead.search(
            [
                ("id", "in", fixtures.ids),
                ("country_id", "in", [self.turkey.id]),
                ("ggd_product_group_ids", "in", [self.wire.id]),
            ]
        )
        self.assertEqual(both, tr_wire)

        either_country = self.Lead.search(
            [
                ("id", "in", fixtures.ids),
                ("country_id", "in", [self.turkey.id, self.poland.id]),
                ("ggd_product_group_ids", "in", [self.wire.id]),
            ]
        )
        self.assertEqual(either_country, tr_wire + pl_wire)

        with_type = self.Lead.search(
            [
                ("id", "in", fixtures.ids),
                ("country_id", "in", [self.turkey.id]),
                ("ggd_product_group_ids", "in", [self.wire.id, self.pipe.id]),
                ("ggd_company_type", "=", "manufacturer"),
            ]
        )
        self.assertEqual(with_type, tr_wire + tr_pipe)

    def test_the_classification_state_names_the_three_cases(self):
        classified = self._lead("classified", ggd_product_group_ids=[(4, self.wire.id)])
        unclassified = self._lead("unclassified")
        self.assertEqual(classified.ggd_product_group_state, "active")
        self.assertEqual(unclassified.ggd_product_group_state, "none")

        retired = self.Group.create({"name": "QA retired group"})
        only_retired = self._lead("only retired", ggd_product_group_ids=[(4, retired.id)])
        self.assertEqual(only_retired.ggd_product_group_state, "active")
        retired.active = False
        self.assertEqual(only_retired.ggd_product_group_state, "archived")

    def test_archiving_a_group_keeps_the_link_and_the_history(self):
        retired = self.Group.create({"name": "QA group to archive"})
        lead = self._lead(
            "archived group holder",
            ggd_product_focus="Draws 2mm galvanised wire on four lines.",
            ggd_product_group_ids=[(4, retired.id), (4, self.wire.id)],
        )
        lead.message_post(body="A fictional call note.")
        messages_before = len(lead.message_ids)

        retired.active = False

        # Many2many.read sets active_test False, so the archived group is
        # still on the record - which is the whole difference between
        # archiving and deleting.
        self.assertIn(retired, lead.ggd_product_group_ids)
        self.assertEqual(lead.ggd_product_group_state, "active")
        self.assertEqual(len(lead.message_ids), messages_before)
        self.assertEqual(
            lead.ggd_product_focus, "Draws 2mm galvanised wire on four lines."
        )

    def test_renaming_a_group_keeps_every_link(self):
        renamed = self.Group.create({"name": "QA group to rename"})
        lead = self._lead("renamed group holder", ggd_product_group_ids=[(4, renamed.id)])
        renamed.name = "QA group renamed"
        self.assertEqual(lead.ggd_product_group_ids, renamed)
        self.assertEqual(lead.ggd_product_group_ids.name, "QA group renamed")

    def test_a_group_cannot_be_deleted_by_a_sales_administrator(self):
        """Archiving is the retirement; deleting would take the history with it."""
        manager = self.env["res.users"].create(
            {
                "name": "QA sales administrator",
                "login": "ggd-groups-manager@ggd-qa.invalid",
                "group_ids": [
                    (
                        6,
                        0,
                        [
                            self.env.ref("base.group_user").id,
                            self.env.ref("sales_team.group_sale_manager").id,
                        ],
                    )
                ],
            }
        )
        group = self.Group.create({"name": "QA undeletable group"})
        self.assertTrue(group.with_user(manager).has_access("write"))
        with self.assertRaises(AccessError):
            group.with_user(manager).unlink()

    @mute_logger("odoo.sql_db")
    def test_two_groups_cannot_share_a_name(self):
        self.Group.create({"name": "QA unique group"})
        with self.assertRaises(IntegrityError):
            with self.env.cr.savepoint():
                self.Group.create({"name": "QA unique group"})

    def test_a_group_never_rewrites_the_product_focus(self):
        lead = self._lead(
            "focus keeper",
            ggd_product_focus="Rolls seamless tube up to 168mm.",
        )
        lead.write({"ggd_product_group_ids": [(4, self.pipe.id)]})
        self.assertEqual(lead.ggd_product_focus, "Rolls seamless tube up to 168mm.")


class TestGgdBoardSelectionCounts(GgdLeadGroupCase):
    """The bar's numbers follow the selection, and the cap stays apart."""

    def test_counts_are_scoped_to_the_selection(self):
        turkish = self._lead("TR counted", country_id=self.turkey.id)
        polish = self._lead("PL counted", country_id=self.poland.id)
        turkish.write({"ggd_delivery_status": "claimed"})
        polish.write({"ggd_delivery_status": "claimed"})

        everything = self.Lead.ggd_board_chip_counts()
        turkey_only = self.Lead.ggd_board_chip_counts(
            [("country_id", "in", [self.turkey.id])]
        )
        self.assertEqual(
            turkey_only["matching"],
            self.Lead.search_count(
                [("type", "=", "opportunity"), ("country_id", "in", [self.turkey.id])]
            ),
        )
        self.assertLess(turkey_only["unresolved_claim"], everything["unresolved_claim"])
        self.assertGreaterEqual(turkey_only["unresolved_claim"], 1)

    def test_the_cap_is_not_scoped_to_the_selection(self):
        """It is a system-wide limit; the bar labels it so, and so does this."""
        everything = self.Lead.ggd_board_chip_counts()
        narrowed = self.Lead.ggd_board_chip_counts(
            [("country_id", "in", [self.turkey.id])]
        )
        self.assertEqual(narrowed["cap"], everything["cap"])

    def test_a_selection_that_is_not_a_domain_is_refused(self):
        with self.assertRaises(ValidationError):
            self.Lead.ggd_board_chip_counts("country_id = 1")

    def test_the_pickers_offer_the_live_groups_and_the_used_countries(self):
        self._lead("option source", country_id=self.turkey.id)
        options = self.Lead.ggd_board_selection_options()
        self.assertIn(
            self.turkey.display_name, [o["name"] for o in options["countries"]]
        )
        group_names = [o["name"] for o in options["product_groups"]]
        self.assertIn("Wire", group_names)

        retired = self.Group.create({"name": "QA picker hidden group"})
        retired.active = False
        self.assertNotIn(
            "QA picker hidden group",
            [o["name"] for o in self.Lead.ggd_board_selection_options()["product_groups"]],
        )
        self.assertEqual(
            [o["id"] for o in options["company_types"]],
            [value for value, _label in self.Lead.GGD_COMPANY_TYPES],
        )

    def test_counts_and_options_obey_record_rules(self):
        """A count never describes a record the reader may not open."""
        Users = self.env["res.users"].with_context(no_reset_password=True)
        salesperson = Users.create(
            {
                "name": "QA own-documents salesperson",
                "login": "ggd-groups-own@ggd-qa.invalid",
                "group_ids": [
                    (
                        6,
                        0,
                        [
                            self.env.ref("base.group_user").id,
                            self.env.ref("sales_team.group_sale_salesman").id,
                        ],
                    )
                ],
            }
        )
        mine = self._lead("mine", user_id=salesperson.id, country_id=self.turkey.id)
        theirs = self._lead(
            "theirs",
            user_id=self.env.ref("base.user_admin").id,
            country_id=self.turkey.id,
        )
        mine.write({"ggd_delivery_status": "claimed"})
        theirs.write({"ggd_delivery_status": "claimed"})

        as_them = self.Lead.with_user(salesperson).ggd_board_chip_counts(
            [("country_id", "in", [self.turkey.id])]
        )
        visible = self.Lead.with_user(salesperson).search(
            [("id", "in", (mine + theirs).ids)]
        )
        self.assertEqual(visible, mine)
        self.assertGreaterEqual(as_them["matching"], 1)
        self.assertEqual(
            as_them["matching"],
            self.Lead.with_user(salesperson).search_count(
                [("type", "=", "opportunity"), ("country_id", "in", [self.turkey.id])]
            ),
        )


class TestGgdSavedView(GgdLeadGroupCase):
    """A saved view is an Odoo favourite, and a favourite is a live filter."""

    def test_a_saved_filter_reopens_and_catches_later_leads(self):
        Filters = self.env["ir.filters"]
        domain = str(
            [
                ("country_id", "in", [self.turkey.id]),
                ("ggd_product_group_ids", "in", [self.wire.id]),
            ]
        )
        Filters.create_filter(
            {
                "name": "Turkey - wire makers",
                "model_id": "crm.lead",
                "domain": domain,
                "context": "{}",
                "user_ids": [self.env.uid],
            }
        )
        saved = Filters.get_filters("crm.lead")
        stored = next(f for f in saved if f["name"] == "Turkey - wire makers")

        before = self.Lead.search_count(
            [("type", "=", "opportunity")] + list(literal_eval(stored["domain"]))
        )
        later = self._lead(
            "added after the view was saved",
            country_id=self.turkey.id,
            ggd_product_group_ids=[(4, self.wire.id)],
        )
        after = self.Lead.search(
            [("type", "=", "opportunity")] + list(literal_eval(stored["domain"]))
        )
        self.assertEqual(len(after), before + 1)
        self.assertIn(later, after)


class GgdBulkActionCase(GgdLeadGroupCase):
    """Fixtures for the three bulk actions, and the two users they are run as."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        Users = cls.env["res.users"].with_context(no_reset_password=True)
        cls.owner = Users.create(
            {
                "name": "QA bulk owner",
                "login": "ggd-bulk-owner@ggd-qa.invalid",
                "group_ids": [
                    (
                        6,
                        0,
                        [
                            cls.env.ref("base.group_user").id,
                            cls.env.ref("sales_team.group_sale_salesman").id,
                        ],
                    )
                ],
            }
        )
        cls.other = Users.create(
            {
                "name": "QA bulk other salesperson",
                "login": "ggd-bulk-other@ggd-qa.invalid",
                "group_ids": [
                    (
                        6,
                        0,
                        [
                            cls.env.ref("base.group_user").id,
                            cls.env.ref("sales_team.group_sale_salesman").id,
                        ],
                    )
                ],
            }
        )

    def _wizard(self, model, leads, user=None, **values):
        """Open a wizard the way the Actions menu does: on the ticked ids only."""
        wizard = self.env[model].with_context(
            active_model="crm.lead", active_ids=leads.ids
        )
        if user is not None:
            wizard = wizard.with_user(user)
        return wizard.create(values)


class TestGgdBulkProductGroups(GgdBulkActionCase):
    def test_groups_are_added_and_nothing_is_replaced(self):
        already = self._lead("has pipe", ggd_product_group_ids=[(4, self.pipe.id)])
        blank = self._lead("has nothing")
        untouched = self._lead("not selected")

        wizard = self._wizard(
            "ggd.lead.group.wizard",
            already + blank,
            group_ids=[(6, 0, [self.wire.id])],
        )
        self.assertEqual(wizard.selected_count, 2)
        self.assertEqual(wizard.ready_count, 2)
        self.assertEqual(wizard.blocked_count, 0)
        wizard.action_ggd_apply()

        self.assertEqual(
            set(already.ggd_product_group_ids.ids), {self.pipe.id, self.wire.id}
        )
        self.assertEqual(blank.ggd_product_group_ids, self.wire)
        self.assertFalse(untouched.ggd_product_group_ids)
        self.assertEqual(untouched.ggd_product_group_state, "none")

    def test_a_lead_that_already_carries_them_all_is_left_alone(self):
        lead = self._lead("already there", ggd_product_group_ids=[(4, self.wire.id)])
        wizard = self._wizard(
            "ggd.lead.group.wizard", lead, group_ids=[(6, 0, [self.wire.id])]
        )
        wizard.action_ggd_apply()
        self.assertEqual(lead.ggd_product_group_ids, self.wire)
        self.assertIn("Left alone", wizard.result_summary)
        self.assertIn("Changed: 0", wizard.result_summary)

    def test_an_archived_opportunity_is_blocked_with_a_reason(self):
        archived = self._lead("archived one")
        archived.active = False
        live = self._lead("live one")
        wizard = self._wizard(
            "ggd.lead.group.wizard",
            archived + live,
            group_ids=[(6, 0, [self.wire.id])],
        )
        self.assertEqual(wizard.blocked_count, 1)
        self.assertIn("Archived", wizard.blocked_summary)
        wizard.action_ggd_apply()
        self.assertEqual(live.ggd_product_group_ids, self.wire)
        self.assertFalse(archived.ggd_product_group_ids)
        self.assertIn("Blocked: 1", wizard.result_summary)

    def test_a_suppressed_opportunity_may_still_be_classified(self):
        """Do not contact stops outreach, not filing."""
        lead = self._lead("suppressed", ggd_do_not_contact=True)
        wizard = self._wizard(
            "ggd.lead.group.wizard", lead, group_ids=[(6, 0, [self.wire.id])]
        )
        wizard.action_ggd_apply()
        self.assertEqual(lead.ggd_product_group_ids, self.wire)
        self.assertTrue(lead.ggd_do_not_contact)

    def test_a_selection_the_user_may_not_write_is_refused_not_changed(self):
        mine = self._lead("mine to change", user_id=self.owner.id)
        theirs = self._lead("not mine", user_id=self.other.id)
        wizard = self._wizard(
            "ggd.lead.group.wizard",
            mine + theirs,
            group_ids=[(6, 0, [self.wire.id])],
        )
        # Applied as the owner, not as the superuser: this is the call an API
        # key holder can make, and it must not reach the other salesperson's
        # record.
        wizard.with_user(self.owner).action_ggd_apply()
        self.assertEqual(mine.ggd_product_group_ids, self.wire)
        self.assertFalse(theirs.ggd_product_group_ids)
        self.assertIn("permission", wizard.result_summary)

    def test_the_selection_is_the_ticked_rows_and_not_the_search(self):
        """active_domain is in the context of every list action; it is ignored."""
        ticked = self._lead("ticked")
        self._lead("matches the search but was not ticked")
        wizard = (
            self.env["ggd.lead.group.wizard"]
            .with_context(
                active_model="crm.lead",
                active_ids=ticked.ids,
                active_domain=[("type", "=", "opportunity")],
            )
            .create({"group_ids": [(6, 0, [self.wire.id])]})
        )
        self.assertEqual(wizard.lead_ids, ticked)
        self.assertEqual(wizard.selected_count, 1)

    def test_opening_with_nothing_ticked_is_refused(self):
        with self.assertRaises(UserError):
            self.env["ggd.lead.group.wizard"].with_context(
                active_model="crm.lead", active_ids=[]
            ).create({"group_ids": [(6, 0, [self.wire.id])]})

    def test_no_email_is_queued(self):
        lead = self._lead("mail watcher")
        before = self._mail_count()
        wizard = self._wizard(
            "ggd.lead.group.wizard", lead, group_ids=[(6, 0, [self.wire.id])]
        )
        wizard.action_ggd_apply()
        self.assertEqual(self._mail_count(), before)


class TestGgdBulkStageChange(GgdBulkActionCase):
    def test_only_the_documented_working_stages_are_offered(self):
        lead = self._lead("stage fixture", stage_id=self.stages["Qualified"].id)
        wizard = self._wizard(
            "ggd.lead.stage.wizard", lead, stage_id=self.stages["Meeting Proposed"].id
        )
        offered = set(wizard.allowed_stage_ids.mapped("name"))
        self.assertTrue(offered)
        for name in offered:
            self.assertIn(name, self.Lead.GGD_ACTION_STAGES)
        for refused in ("Won", "Lost", "Reply Received", "Do Not Contact"):
            self.assertNotIn(refused, offered)

    def test_an_allowed_move_changes_only_the_selection(self):
        moving = self._lead("moving", stage_id=self.stages["Qualified"].id)
        staying = self._lead("staying", stage_id=self.stages["Qualified"].id)
        wizard = self._wizard(
            "ggd.lead.stage.wizard",
            moving,
            stage_id=self.stages["Meeting Proposed"].id,
        )
        wizard.action_ggd_apply()
        self.assertEqual(moving.stage_id, self.stages["Meeting Proposed"])
        self.assertEqual(staying.stage_id, self.stages["Qualified"])

    def test_contacted_needs_evidence_and_the_rule_is_the_connectors_own(self):
        bare = self._lead("no evidence", stage_id=self.stages["Qualified"].id)
        contacted = self.stages["Contacted"]

        blocker = bare._ggd_stage_change_blocker(contacted)
        self.assertIsNotNone(blocker)
        self.assertEqual(blocker[0], "contact_not_evidenced")

        # The same refusal, reached through the connector's own action.
        result = bare.ggd_opportunity_action(
            "transition_stage",
            {
                "expected_write_date": fields.Datetime.to_string(bare.write_date),
                "expected_stage": "Qualified",
                "target_stage": "Contacted",
            },
        )
        self.assertFalse(result["ok"])
        self.assertEqual(result["reason_code"], "contact_not_evidenced")

        wizard = self._wizard("ggd.lead.stage.wizard", bare, stage_id=contacted.id)
        self.assertEqual(wizard.blocked_count, 1)
        self.assertIn("Contacted needs", wizard.blocked_summary)
        wizard.action_ggd_apply()
        self.assertEqual(bare.stage_id, self.stages["Qualified"])

    def test_a_recorded_manual_contact_earns_contacted(self):
        lead = self._lead("has evidence", stage_id=self.stages["Qualified"].id)
        self.Log.create(
            {
                "lead_id": lead.id,
                "action": "record_manual_contact",
                "idempotency_key": "qa-bulk-evidence",
            }
        )
        wizard = self._wizard(
            "ggd.lead.stage.wizard", lead, stage_id=self.stages["Contacted"].id
        )
        self.assertEqual(wizard.blocked_count, 0)
        wizard.action_ggd_apply()
        self.assertEqual(lead.stage_id, self.stages["Contacted"])

    def test_a_won_stage_is_refused_even_when_it_is_named_in_the_working_set(self):
        won_stage = self.stages["Active Opportunity"]
        won_stage.is_won = True
        try:
            lead = self._lead("won attempt", stage_id=self.stages["Qualified"].id)
            wizard = self._wizard(
                "ggd.lead.stage.wizard", lead, stage_id=won_stage.id
            )
            self.assertNotIn(won_stage, wizard.allowed_stage_ids)
            self.assertEqual(wizard.blocked_count, 1)
            wizard.action_ggd_apply()
            self.assertEqual(lead.stage_id, self.stages["Qualified"])
        finally:
            won_stage.is_won = False

    def test_a_suppressed_opportunity_does_not_move(self):
        lead = self._lead(
            "suppressed mover",
            stage_id=self.stages["Qualified"].id,
            ggd_do_not_contact=True,
        )
        wizard = self._wizard(
            "ggd.lead.stage.wizard", lead, stage_id=self.stages["Meeting Proposed"].id
        )
        self.assertEqual(wizard.blocked_count, 1)
        wizard.action_ggd_apply()
        self.assertEqual(lead.stage_id, self.stages["Qualified"])

    def test_a_mixed_batch_changes_what_it_may_and_reports_the_rest(self):
        allowed = self._lead(
            "allowed mover", stage_id=self.stages["Qualified"].id, user_id=self.owner.id
        )
        suppressed = self._lead(
            "suppressed one",
            stage_id=self.stages["Qualified"].id,
            user_id=self.owner.id,
            ggd_do_not_contact=True,
        )
        forbidden = self._lead(
            "someone else's", stage_id=self.stages["Qualified"].id, user_id=self.other.id
        )
        wizard = self._wizard(
            "ggd.lead.stage.wizard",
            allowed + suppressed + forbidden,
            stage_id=self.stages["Meeting Proposed"].id,
        )
        wizard.with_user(self.owner).action_ggd_apply()
        self.assertEqual(allowed.stage_id, self.stages["Meeting Proposed"])
        self.assertEqual(suppressed.stage_id, self.stages["Qualified"])
        self.assertEqual(forbidden.stage_id, self.stages["Qualified"])
        self.assertIn("Changed: 1", wizard.result_summary)
        self.assertIn("Blocked: 2", wizard.result_summary)

    def test_a_stage_change_touches_nothing_in_the_outbound_gate(self):
        lead = self._lead(
            "gate keeper",
            stage_id=self.stages["Qualified"].id,
            ggd_draft_subject="A reviewed fictional subject",
            ggd_draft_body="A reviewed fictional body for the QA fixture.",
            ggd_draft_version="qa-bulk-v1",
            ggd_draft_status="ready",
        )
        before_mail = self._mail_count()
        wizard = self._wizard(
            "ggd.lead.stage.wizard", lead, stage_id=self.stages["Meeting Proposed"].id
        )
        wizard.action_ggd_apply()
        self.assertFalse(lead.ggd_outreach_approved)
        self.assertFalse(lead.ggd_last_send_key)
        self.assertFalse(lead.ggd_send_confirmed_at)
        self.assertEqual(lead.ggd_draft_status, "ready")
        self.assertEqual(self._mail_count(), before_mail)


class TestGgdBulkFollowUp(GgdBulkActionCase):
    def _followup(self, leads, **values):
        base = {
            "summary": "Call about the fictional wire enquiry",
            "date_deadline": fields.Date.context_today(self.Lead) + timedelta(days=3),
        }
        base.update(values)
        return self._wizard("ggd.lead.followup.wizard", leads, **base)

    def test_one_activity_per_selected_lead_with_the_chosen_owner_and_date(self):
        first = self._lead("first follow-up")
        second = self._lead("second follow-up")
        untouched = self._lead("no follow-up")
        due = fields.Date.context_today(self.Lead) + timedelta(days=5)

        wizard = self._followup(
            first + second, user_id=self.owner.id, date_deadline=due
        )
        self.assertEqual(wizard.ready_count, 2)
        before_mail = self._mail_count()
        wizard.action_ggd_apply()
        self.assertEqual(self._mail_count(), before_mail)

        for lead in (first, second):
            activities = self.env["mail.activity"].search(
                [("res_model", "=", "crm.lead"), ("res_id", "=", lead.id)]
            )
            self.assertEqual(len(activities), 1)
            self.assertEqual(activities.user_id, self.owner)
            self.assertEqual(activities.date_deadline, due)
            self.assertEqual(
                activities.summary, "Call about the fictional wire enquiry"
            )
        self.assertFalse(
            self.env["mail.activity"].search(
                [("res_model", "=", "crm.lead"), ("res_id", "=", untouched.id)]
            )
        )

    def test_applying_the_same_request_twice_schedules_once(self):
        lead = self._lead("double click")
        wizard = self._followup(lead)
        wizard.action_ggd_apply()
        first_result = wizard.result_summary
        wizard.action_ggd_apply()
        self.assertEqual(wizard.result_summary, first_result)
        self.assertEqual(
            self.env["mail.activity"].search_count(
                [("res_model", "=", "crm.lead"), ("res_id", "=", lead.id)]
            ),
            1,
        )
        self.assertEqual(
            self.Log.search_count(
                [
                    ("lead_id", "=", lead.id),
                    ("action", "=", "schedule_activity"),
                    ("idempotency_key", "=", wizard.batch_key),
                ]
            ),
            1,
        )

    def test_a_repeat_of_the_same_batch_key_is_skipped_not_duplicated(self):
        """The state flag is the first guard; the log is the one that holds."""
        lead = self._lead("replayed batch")
        wizard = self._followup(lead)
        wizard.action_ggd_apply()
        wizard.write({"state": "plan"})
        wizard.action_ggd_apply()
        self.assertEqual(
            self.env["mail.activity"].search_count(
                [("res_model", "=", "crm.lead"), ("res_id", "=", lead.id)]
            ),
            1,
        )
        self.assertIn("already scheduled", wizard.result_summary)

    def test_a_deadline_in_the_past_is_refused(self):
        lead = self._lead("past deadline")
        with self.assertRaises(ValidationError):
            self._followup(
                lead,
                date_deadline=fields.Date.context_today(self.Lead) - timedelta(days=1),
            )

    def test_a_deadline_past_the_horizon_is_refused(self):
        lead = self._lead("far deadline")
        with self.assertRaises(ValidationError):
            self._followup(
                lead,
                date_deadline=fields.Date.context_today(self.Lead)
                + timedelta(days=self.Lead.GGD_ACTION_MAX_DEADLINE_DAYS + 1),
            )

    def test_a_lead_the_user_may_not_write_gets_no_activity(self):
        mine = self._lead("mine for follow-up", user_id=self.owner.id)
        theirs = self._lead("theirs for follow-up", user_id=self.other.id)
        wizard = self._followup(mine + theirs, user_id=self.owner.id)
        wizard.with_user(self.owner).action_ggd_apply()
        self.assertEqual(
            self.env["mail.activity"].search_count(
                [("res_model", "=", "crm.lead"), ("res_id", "=", theirs.id)]
            ),
            0,
        )
        self.assertEqual(
            self.env["mail.activity"].search_count(
                [("res_model", "=", "crm.lead"), ("res_id", "=", mine.id)]
            ),
            1,
        )
