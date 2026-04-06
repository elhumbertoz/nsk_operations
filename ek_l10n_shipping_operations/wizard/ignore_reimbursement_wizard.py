# -*- coding: utf-8 -*-
from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class IgnoreReimbursementWizard(models.TransientModel):
    _name = 'ignore.reimbursement.wizard'
    _description = 'Wizard para ignorar productos de reembolso'

    tracking_id = fields.Many2one(
        'ek.reimbursement.tracking',
        string='Seguimiento de Reembolso',
        required=True
    )
    
    reason_ignored = fields.Text(
        string='Razón para Ignorar',
        required=True,
        help="Explicar por qué no se cobrará este reembolso"
    )

    @api.model
    def default_get(self, fields_list):
        """Obtener valores por defecto"""
        res = super().default_get(fields_list)
        if 'tracking_id' in fields_list and self.env.context.get('active_id'):
            res['tracking_id'] = self.env.context['active_id']
        return res

    def action_ignore(self):
        """Marcar producto como ignorado con la razón proporcionada"""
        self.ensure_one()
        
        if not self.reason_ignored.strip():
            raise ValidationError(_('Debe proporcionar una razón para ignorar el producto.'))
        
        self.tracking_id.write({
            'state': 'ignored',
            'ignored': True,
            'reason_ignored': self.reason_ignored
        })
        
        return {
            'type': 'ir.actions.act_window',
            'name': 'Seguimiento de Reembolsos',
            'res_model': 'ek.reimbursement.tracking',
            'res_id': self.tracking_id.id,
            'view_mode': 'form',
            'target': 'current',
        }
