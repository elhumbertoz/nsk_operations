# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
import calendar
from collections import defaultdict
from datetime import date

from odoo import _, api, Command, fields, models
from odoo.exceptions import ValidationError, UserError
from odoo.tools import float_compare

from odoo.addons.l10n_ec_edi.models.account_tax import L10N_EC_TAXSUPPORTS
from odoo.addons.l10n_ec_edi.models.account_move import L10N_EC_WTH_FOREIGN_GENERAL_REGIME_CODES
from odoo.addons.l10n_ec_edi.models.account_move import L10N_EC_WTH_FOREIGN_TAX_HAVEN_OR_LOWER_TAX_CODES
from odoo.addons.l10n_ec_edi.models.account_move import L10N_EC_WTH_FOREIGN_SUBJECT_WITHHOLD_CODES
from odoo.addons.l10n_ec_edi.models.account_move import L10N_EC_WTH_FOREIGN_DOUBLE_TAXATION_CODES
from odoo.addons.l10n_ec_edi.models.account_move import L10N_EC_WITHHOLD_FOREIGN_REGIME


class L10nEcWizardAccountWithhold(models.TransientModel):
    _inherit = "l10n_ec.wizard.account.withhold"

    # ===== MOVE CREATION METHODS =====manual_document_number
    l10n_ec_authorization_number = fields.Char(
        string="Número de autorización",
        size=49,
        help="Número de autorización EDI (igual que la clave de acceso), establecido al publicar.",
    )

    l10n_ec_withhold_type = fields.Selection(
        string='Tipo de retención',
        related="journal_id.l10n_ec_withhold_type",
        required=False, )


    def _prepare_withhold_header(self):
        vals = super()._prepare_withhold_header()

        if self.withhold_type == 'out_withhold':
            vals.update({
                'l10n_ec_authorization_number': self.l10n_ec_authorization_number,
              #  'l10n_latam_document_sustento': self.
            })

        if 'l10n_latam_document_type_id' not in vals:
            ret_code = self.env.ref("l10n_ec.ec_dt_07",False)
            vals.update({
                'l10n_latam_document_type_id': ret_code and ret_code.id or False
            })

        if 'l10n_latam_document_sustento' not in vals and self.related_invoice_ids:
            invoice = self.related_invoice_ids[0]
            if invoice:
                vals.update({
                    'l10n_latam_document_sustento': invoice.l10n_latam_document_sustento and invoice.l10n_latam_document_sustento.id or False
                })

        return vals

    def action_create_and_post_withhold(self):
        withhold = super().action_create_and_post_withhold()

        if withhold and withhold.l10n_ec_withhold_type == 'out_withhold':
            withhold.partner_id.with_context(validation_skip=True).write({'withholding_issues': True})
        return withhold
