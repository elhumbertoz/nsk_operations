# -*- coding: utf-8 -*-
import logging

from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError

_logger = logging.getLogger(__name__)


class EkPurchaseReimbursementWizard(models.TransientModel):
    _name = 'ek.purchase.reimbursement.wizard'
    _description = _('Importar Reembolsos de Compras')

    invoice_id = fields.Many2one("account.move", string="Factura")
    partner_id = fields.Many2one(related="invoice_id.partner_id", string="Cliente")

    purchase_ids = fields.Many2many(
        comodel_name='purchase.order',
        string='Compras',
        required=False,
    )

    allow_purchase_ids = fields.Many2many(
        comodel_name='purchase.order',
        string='Compras Permitidas',
        required=False,
        compute='_compute_allow_purchase_ids'
    
    )

    @api.depends('invoice_id')
    def _compute_allow_purchase_ids(self):
        self.ensure_one()
        purchasePurchase = self.env['purchase.order']

        domain = self.get_domain()

        # if self.invoice_id.company_id.l10n_ec_ats_sustento_ids:
        #     domain.append(('invoice_ids.l10n_latam_document_sustento', 'in', self.invoice_id.company_id.l10n_ec_ats_sustento_ids.ids))

        # if self.invoice_id.company_id.l10n_ec_reimbursement_journal_ids:
        #     domain.append(('invoice_ids.journal_id', 'in', self.invoice_id.company_id.l10n_ec_reimbursement_journal_ids.ids))

        domain.extend(self.aditional_domain())

        self.allow_purchase_ids = purchasePurchase.search(domain=domain, order="date_order")

    def aditional_domain(self):
        self.ensure_one()
        return []

    @api.model
    def get_domain(self):
        self.ensure_one()
        return [
            ('state', 'in', ['purchase', 'done']),
            ('is_reimbursement', '=', False),
            ('invoice_count', '>', 0),
            ('invoice_ids.state', '=', 'posted'),
            ('invoice_ids.move_type', '=', 'in_invoice'),
            ("invoice_ids.l10n_ec_to_be_reimbursed", "=", True),
            ("invoice_ids.reimbursed_move_id", "=", False),
        ]

    def action_import_from_purchase(self):
        self.ensure_one()
        if not self.invoice_id:
            raise UserError(_("No se ha seleccionado una factura"))
        if not self.purchase_ids:
            raise UserError(_("No se han seleccionado compras"))
        for purchase in self.purchase_ids:
            purchase.action_create_reimbursement(self.invoice_id)