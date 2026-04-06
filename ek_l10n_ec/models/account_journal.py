from odoo import fields, models, api
from odoo.exceptions import ValidationError

class AccountJournal(models.Model):
    _inherit = 'account.journal'

    l10n_latam_document_auth_required = fields.Boolean(
        string="Núm. Autorización requerido",
        required=False,
        help="Si marca esta casilla, el documento de autorización será requerido en los documentos donde use este diario.",
    )
    l10n_latam_document_sustento_required = fields.Boolean(
        string="Sustento requerido",
        required=False,
        help="Si marca esta casilla, el sustento será requerido en los documentos donde use este diario.",
    )
    fiscalyear_lock_date = fields.Date(
        string="Lock Date",
        tracking=True,
        help="No users, including Advisers, can edit accounts prior "
             "to and inclusive of this date for this journal. Use it "
             "for fiscal year locking for this journal, for example.",
    )
    period_lock_date = fields.Date(
        string="Lock Date for Non-Advisers",
        tracking=True,
        help="Only users with the 'Adviser' role can edit accounts "
             "prior to and inclusive of this date for this journal. "
             "Use it for period locking inside an open fiscal year "
             "for this journal, for example.",
    )

    def _default_outbound_payment_methods(self):
        all_out = self.env["account.payment.method"].search(
            [("payment_type", "=", "outbound")]
        )
        return all_out

    def _default_inbound_payment_methods(self):
        method_info = self.env[
            "account.payment.method"
        ]._get_payment_method_information()
        unique_codes = tuple(
            code for code, info in method_info.items() if info.get("mode") == "unique"
        )
        all_in = self.env["account.payment.method"].search(
            [
                ("payment_type", "=", "inbound"),
                ("code", "not in", unique_codes),  # filter out unique codes
            ]
        )
        return all_in

    @api.constrains("company_id")
    def company_id_account_payment_mode_constrains(self):
        for journal in self:
            mode = self.env["account.payment.mode"].search(
                [
                    ("fixed_journal_id", "=", journal.id),
                    ("company_id", "!=", journal.company_id.id),
                ],
                limit=1,
            )
            if mode:
                raise ValidationError(
                    _(
                        "The company of the journal %(journal)s does not match "
                        "with the company of the payment mode %(paymode)s where it is "
                        "being used as Fixed Bank Journal.",
                        journal=journal.name,
                        paymode=mode.name,
                    )
                )
            mode = self.env["account.payment.mode"].search(
                [
                    ("variable_journal_ids", "in", [journal.id]),
                    ("company_id", "!=", journal.company_id.id),
                ],
                limit=1,
            )
            if mode:
                raise ValidationError(
                    _(
                        "The company of the journal  %(journal)s does not match "
                        "with the company of the payment mode  %(paymode)s where it is "
                        "being used in the Allowed Bank Journals.",
                        journal=journal.name,
                        paymode=mode.name,
                    )
                )