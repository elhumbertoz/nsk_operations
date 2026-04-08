# -*- coding: utf-8 -*-
#
#    Sistema FINAMSYS
#    Copyright (C) 2016-Today Ekuasoft S.A All Rights Reserved
#    Ing. Yordany Oliva Mateos <yordanyoliva@ekuasoft.com>
#    Ing. Wendy Alvarez Chavez <wendyalvarez@ekuasoft.com>
#    EkuaSoft Software Development Group Solution
#    http://www.ekuasoft.com
#
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
from odoo import api, fields, models
from odoo.tools.translate import _
from odoo.addons.ek_l10n_ec.models.account_move import _DOCUMENTS_MAPPING

if _DOCUMENTS_MAPPING:
    if not _DOCUMENTS_MAPPING.get("03", False):
        _DOCUMENTS_MAPPING["03"] = []

    _DOCUMENTS_MAPPING['03'].append("ec_dt_110")


class AccountMove(models.Model):
    _inherit = "account.move"

    import_liquidation_id = fields.Many2one(
        string=_("Importación"),
        comodel_name="ek.import.liquidation",
        required=False,
    )
    terms_id = fields.Many2one(
        string=_("Término"),
        comodel_name="ek.incoterms.terms",
        required=False,
    )
    invoice_liquidation_id = fields.Many2one(
        string=u"Fec. Importación",
        comodel_name="ek.import.liquidation",
        required=False,
    )

    partner_code = fields.Char(
        string="Partner Country Code",
        related="partner_id.country_id.code", readonly=True
    )

    apply_import = fields.Boolean(
        string='Aplicar a Importación?',
        required=False)

    @api.model
    def _get_l10n_ec_documents_allowed(self, identification_code):
        documents_allowed = super(AccountMove, self)._get_l10n_ec_documents_allowed(identification_code)
        for document_ref in _DOCUMENTS_MAPPING.get(identification_code, []):
            liquidation_document_allowed = self.env.ref('ek_purchase_import_liquidation.%s' % document_ref, False)
            if liquidation_document_allowed and self.env.context.get('default_move_type', False) != 'out_invoice':
                documents_allowed |= liquidation_document_allowed
        return documents_allowed

    @api.onchange('apply_import')
    def onchange_apply_import(self):
        for rec in self:
            if not rec.apply_import:
                rec.write({'terms_id': False, 'import_liquidation_id': False})

        for line in self.mapped("invoice_line_ids"):
            line._compute_account_id()


class AccountMoveLine(models.Model):
    _inherit = "account.move.line"

    liquidation_line_id = fields.Many2one(
        string=u"Linea de Importación",
        comodel_name="ek.import.liquidation.line",
        required=False,
    )

    def _compute_account_id(self):
        for line in self:
            if line and line.move_id and line.move_id.apply_import and line.display_type == 'product' and line.account_id and line.account_id.account_type not in ('liability_payable','asset_receivable'):
                if line.product_id:
                    account = self.product_id.product_tmpl_id._get_product_accounts()['import']
                else:
                    account = self.env['ir.property']._get('property_stock_account_import_cost_id', 'product.category')

                if account:
                    line.account_id = account.id
                else:
                    super()._compute_account_id()
            else:
                super()._compute_account_id()