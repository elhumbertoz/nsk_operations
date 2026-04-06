# -*- coding: utf-8 -*-

from odoo import fields, models


class ResUsers(models.Model):
  """Extensión del modelo res.users para funcionalidad de agentes navieros."""

  _inherit = 'res.users'

  is_shipping_agent = fields.Boolean(
    string='Es Agente Naviero',
    default=False,
    tracking=True,
    help='Determina si el usuario puede ser asignado como agente en solicitudes de operación',
  )
