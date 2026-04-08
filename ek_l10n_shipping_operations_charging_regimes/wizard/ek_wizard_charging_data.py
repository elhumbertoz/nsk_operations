from odoo import _, fields, models, api


class ek_wizard_charging_data(models.TransientModel):
  _name = 'ek.wizard.charging.data'
  _description = 'Wizard: Charging Data'
  _order = 'id'

  date_request = fields.Datetime(string='Fecha Ingreso')
  movement_date = fields.Datetime(string='Fecha Movimiento')
  regimen = fields.Selection(
    selection=[
      ('60', '60'),
      ('70', '70'),
    ],
    string='Régimen',
  )
  ship_registration_id = fields.Many2one(
    'ek.ship.registration', string='Buque', copy=False
  )
  boats_information_id = fields.Many2one(
    'ek.boats.information', string='Contenedor', copy=False
  )
  related_document = fields.Many2one(
    'id.bl.70', string='BL', copy=False
  )
  tariff_item = fields.Char(string='Subpartida', copy=False)
  product_description = fields.Many2one(
    'ek.requerid.burden.inter.nac', string='Descripción', copy=False
  )
  max_regime_date = fields.Datetime(string='F. Max Régimen', copy=False)
  unds_in = fields.Float(string='Entrada', copy=False)
  unds_out = fields.Float(string='Salida', copy=False)
  balance = fields.Float(string='Saldo', copy=False)
  unit_cost = fields.Float(string='FOB Unit.', copy=False)
  total_cost = fields.Float(
    string='Total FOB', compute='_compute_total_cost', store=True
  )
  customs_document = fields.Char(string='Doc. Aduanas', copy=False)

  @api.depends('unds_in', 'unds_out', 'unit_cost')
  def _compute_total_cost(self):
    for rec in self:
      qty = (rec.unds_in or 0) - (rec.unds_out or 0)
      rec.total_cost = qty * (rec.unit_cost or 0)
