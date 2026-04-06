# -*- coding: utf-8 -*-
import logging

from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError

_logger = logging.getLogger(__name__)


class EkAccountMoveReimbursementWizard(models.TransientModel):
    _name = 'ek.account.move.reimbursement.wizard'
    _description = _('EkAccountMoveReimbursementWizard')

    @api.model
    def get_domain(self):
        domain = [
            ('move_type', '=', 'in_invoice'),
            ("state", "=", "posted"),
            ("l10n_ec_to_be_reimbursed", "=", True),
            ("reimbursed_move_id", "=", False),
            
        ]
        
        return domain

    invoice_id = fields.Many2one("account.move", string="Factura")
    partner_id = fields.Many2one(related="invoice_id.partner_id", string="Cliente")

    move_ids = fields.Many2many(
        comodel_name='account.move',
        string='Compras',
        required=False,
        domain=lambda self: self.get_domain(),
    )

    allow_move_ids = fields.Many2many(
        comodel_name='account.move',
        string='Facturas Permitidas',
        required=False,
        compute='_compute_allow_move_ids'
    
    )
   
    @api.depends('invoice_id')
    def _compute_allow_move_ids(self):
        self.ensure_one()
        accountMove = self.env['account.move']

        domain = self.get_domain()

        domain.extend(self.aditional_domain())

        self.allow_move_ids = accountMove.search(domain=domain, order="invoice_date")

    def aditional_domain(self):
        self.ensure_one()
        return []


    def action_import_from_move(self):
        self.ensure_one()
        if not self.invoice_id:
            raise UserError(_("No se ha seleccionado una factura"))
        if not self.move_ids:
            raise UserError(_("No se han seleccionado facturas"))
        for move in self.move_ids:
            move.action_create_reimbursement(self.invoice_id)
