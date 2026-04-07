# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import UserError


class EkShipAssignmentWizard(models.TransientModel):
    """
    Wizard para asignar masivamente un buque a múltiples líneas de mercancía
    REQ-015B: Wizard de Asignación Masiva de Buque
    """
    _name = 'ek.ship.assignment.wizard'
    _description = 'Wizard de Asignación Masiva de Buque'

    ship_id = fields.Many2one(
        'ek.ship.registration',
        string='Buque Destino',
        required=True,
        help="Buque al que se asignarán las líneas seleccionadas"
    )

    line_ids = fields.Many2many(
        'ek.product.packagens.goods',
        string='Líneas a Asignar',
        readonly=True,
        help="Líneas de mercancía seleccionadas para asignar"
    )

    line_count = fields.Integer(
        string="Cantidad de Líneas",
        compute='_compute_line_count',
        store=False
    )

    @api.depends('line_ids')
    def _compute_line_count(self):
        """Contar líneas seleccionadas"""
        for wizard in self:
            wizard.line_count = len(wizard.line_ids)

    @api.model
    def default_get(self, fields_list):
        """Cargar líneas seleccionadas al abrir el wizard"""
        res = super().default_get(fields_list)

        # Obtener líneas seleccionadas desde contexto
        active_ids = self.env.context.get('active_ids', [])
        active_model = self.env.context.get('active_model', '')

        if active_model != 'ek.product.packagens.goods':
            raise UserError(_('Este wizard solo funciona desde las líneas de mercancía'))

        if not active_ids:
            raise UserError(_('Debe seleccionar al menos una línea de mercancía'))

        res['line_ids'] = [(6, 0, active_ids)]

        return res

    def action_assign_ship(self):
        """Asignar el buque seleccionado a todas las líneas"""
        self.ensure_one()

        if not self.ship_id:
            raise UserError(_('Debe seleccionar un buque'))

        if not self.line_ids:
            raise UserError(_('No hay líneas para asignar'))

        # Asignar buque a todas las líneas
        self.line_ids.write({
            'ship_id': self.ship_id.id
        })

        # Obtener la solicitud asociada (asumiendo que todas las líneas pertenecen a la misma solicitud)
        operation_request = self.line_ids.mapped('ek_operation_request_id')[:1]

        if operation_request:
            # Forzar recálculo del resumen de bultos por buque
            operation_request._compute_packages_summary()

            # Log en chatter
            operation_request.message_post(
                body=_('Se asignó el buque "%s" a %s líneas de mercancía') % (
                    self.ship_id.name,
                    len(self.line_ids)
                )
            )

        # Cerrar wizard y mostrar mensaje de éxito
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Asignación Completada'),
                'message': _('Se asignó el buque "%s" a %s líneas') % (
                    self.ship_id.name,
                    len(self.line_ids)
                ),
                'type': 'success',
                'sticky': False,
            }
        }
