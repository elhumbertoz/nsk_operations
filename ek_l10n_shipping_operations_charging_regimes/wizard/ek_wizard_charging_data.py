from odoo import _, fields, models, api


class ek_wizard_charging_data(models.TransientModel):
  _name = 'ek.wizard.charging.data'
  _description = 'Wizard: Charging Data'

  date_request = fields.Datetime(string='Date Request')
  movement_date = fields.Datetime(string='Movement Date')
  regimen = fields.Selection(
    selection=[
      ('60', '60'),
      ('70', '70'),
    ],
    string='Regimen',
  )
  ship_registration_id = fields.Many2one(
    'ek.ship.registration', string='Ship', copy=False
  )
  boats_information_id = fields.Many2one(
    'ek.boats.information', string='Travel', copy=False
  )
  related_document = fields.Many2one(
    'id.bl.70', string='# Related Document', copy=False
  )
  tariff_item = fields.Char(string='Tariff Item', copy=False)
  product_description = fields.Many2one(
    'ek.requerid.burden.inter.nac', string='Product Description', copy=False
  )
  max_regime_date = fields.Datetime(string='Max Regime Date', copy=False)
  unds = fields.Float(string='UNDS', copy=False)
  unit_cost = fields.Float(string='Unit Cost', copy=False)
  total_cost = fields.Float(
    string='Total Cost', compute='_compute_total_cost', readonly=False
  )  # total_cost
  customs_document = fields.Char(string='Customs Document', copy=False)

  @api.depends('unds', 'unit_cost')
  def _compute_total_cost(self):
    for rec in self:
      rec.total_cost = rec.unds * rec.unit_cost
