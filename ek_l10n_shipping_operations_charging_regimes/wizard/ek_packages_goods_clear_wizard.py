# -*- coding: utf-8 -*-

from odoo import api, fields, models


class EkPackagesGoodsClearWizard(models.TransientModel):
  _name = 'ek.packages.goods.clear.wizard'
  _description = 'Asistente para confirmar eliminación de paquetes y mercancías'

  operation_request_ids = fields.Many2many(
    'ek.operation.request', string='Solicitudes de operación'
  )

  total_records = fields.Integer(string='Total de registros', readonly=True)

  warning_message = fields.Html(
    string='Mensaje de advertencia', compute='_compute_warning_message'
  )

  @api.depends('total_records')
  def _compute_warning_message(self):
    for wizard in self:
      if wizard.total_records > 0:
        wizard.warning_message = f"""
                <div style="background-color: #fff3cd; border: 1px solid #ffeaa7; padding: 15px; border-radius: 5px; margin: 10px 0;">
                    <div style="display: flex; align-items: center; margin-bottom: 10px;">
                        <i class="fa fa-exclamation-triangle" style="color: #f39c12; font-size: 24px; margin-right: 10px;"></i>
                        <strong style="color: #856404;">¡ADVERTENCIA!</strong>
                    </div>
                    <p style="color: #856404; margin: 0;">
                        Está a punto de eliminar <strong>{wizard.total_records}</strong> registro(s) de paquetes y mercancías.
                    </p>
                    <p style="color: #856404; margin: 5px 0 0 0;">
                        <strong>Esta acción no se puede deshacer.</strong> ¿Está seguro de que desea continuar?
                    </p>
                </div>
                """
      else:
        wizard.warning_message = ''

  def action_confirm_clear(self):
    """Confirmar y proceder con la eliminación"""
    if self.operation_request_ids:
      # Llamar al método confirmado en los registros
      self.operation_request_ids.action_clear_packages_goods_confirmed()

    return {'type': 'ir.actions.act_window_close'}

  def action_cancel(self):
    """Cancelar la operación"""
    return {'type': 'ir.actions.act_window_close'}
