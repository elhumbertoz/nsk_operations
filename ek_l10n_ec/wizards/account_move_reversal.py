# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import models, fields, api


class AccountMoveReversal(models.TransientModel):
    _inherit = "account.move.reversal"

    l10n_latam_document_sustento = fields.Many2one(
        comodel_name="account.ats.sustento",
        string="Sustento",
        required=False,
    )
    l10n_ec_authorization_number = fields.Char(
        string="Número de Autorización",
    )
    l10n_latam_document_auth_required = fields.Boolean(
        related="journal_id.l10n_latam_document_auth_required",
    )
    l10n_latam_document_sustento_required = fields.Boolean(
        related="journal_id.l10n_latam_document_sustento_required",
    )

    reason_id = fields.Many2one("account.move.refund.reason", string="Refund Reason")
    reason = fields.Char(
        compute="_compute_reason", precompute=True, store=True, readonly=False
    )

    def _prepare_default_reversal(self, move):
        """Set the default document type and number in the new reversal move taking into account the ones selected in the wizard."""
        res = super(AccountMoveReversal, self)._prepare_default_reversal(move)
        res.update({
            'l10n_latam_document_sustento': self.l10n_latam_document_sustento.id,
            'l10n_ec_authorization_number': self.l10n_ec_authorization_number,
            'reason_id': self.reason_id.id
        })
        return res

    @api.depends("reason_id")
    def _compute_reason(self):
        for record in self:
            if record.reason_id:
                record.reason = record.reason_id.name