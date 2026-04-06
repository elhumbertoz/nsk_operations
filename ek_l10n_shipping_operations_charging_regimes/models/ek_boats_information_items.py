# -*- coding: utf-8 -*-
from odoo import models, fields, api


class ek_product_packagens_goods(models.Model):
  _inherit = 'ek.product.packagens.goods'

  tariff_item = fields.Char(
    'Tariff Item',
  )
  id_hs_copmt_cd = fields.Char(
    'Complementary Code',
  )
  id_hs_spmt_cd = fields.Char(
    'Supplementary Code',
  )
  uom_id = fields.Many2one(
    'uom.uom',
    'Uom',
  )
  fob = fields.Float(
    'Fob',
  )
  total_fob = fields.Float('Total Fob', compute='_compute_total_fob')
  invoice_number = fields.Char('Invoice Number', required=False)
  supplier = fields.Char('Supplier', required=False)
  ek_ship_registration_id = fields.Many2one(
    'ek.ship.registration', 'Ship', copy=False
  )
  ek_boats_information_id = fields.Many2one(
    'ek.boats.information', 'Container', copy=False
  )
  date_request = fields.Datetime('Date Request', required=False)
  delivery_product = fields.Float(
    'Delivery Product',
    required=False,
  )
  quantity_hand = fields.Float(
    'Quantity Hand', required=False, compute='_get_quantiy_for_consume'
  )
  max_regime_date = fields.Datetime('Max Regime Date', required=False)
  number_dai = fields.Char('Number Dai', required=False)
  # assigned_regimen_70 = fields.Boolean(related="ek_boats_information_id.assigned_regimen_70")

  @api.depends('quantity', 'fob')
  def _compute_total_fob(self):
    for rec in self:
      rec.total_fob = rec.quantity * rec.fob

  @api.depends('quantity', 'delivery_product')
  def _get_quantiy_for_consume(self):
    for rec in self:
      rec.quantity_hand = rec.quantity - rec.delivery_product
