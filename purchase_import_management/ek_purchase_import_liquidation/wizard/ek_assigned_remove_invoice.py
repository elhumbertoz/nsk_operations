# -*- coding: utf-8 -*-

from odoo import fields, models
from odoo.exceptions import UserError
from odoo.tools.translate import _


class EkAssignedRemoveInvoice(models.TransientModel):
    """Asociar regalias a viaje"""
    _name = "ek.assigned.remove.invoice"
    _description = "Asignación de facturas importación"

    type = fields.Selection(
        string=_("Tipo"),
        selection=[
            ("add", _("Asignar")),
            ("del", _("Eliminar")),
        ],
        required=False,
    )

    def action_confirm(self):
        active_ids = self.env.context.get('active_ids')
        objects = self.env['ek.import.liquidation.line'].browse(active_ids).filtered(lambda x: x.order_id.state in ['draft', 'calculate'])

        if len(objects) == 0:
            raise UserError("Las lineas seleccionadas no cumplen las condiciones para la acción indicada.")

        for rec in objects:
            if self.type == 'add':
                if not rec.invoice_id:
                    if self.invoice_id.partner_id.id == rec.purchase_line_id.order_id.partner_id.id:
                        rec.write({'invoice_id': self.invoice_id.id})
            else:
                if rec.invoice_id and rec.invoice_id.state == 'draft':
                    rec.write({'invoice_id': False})
