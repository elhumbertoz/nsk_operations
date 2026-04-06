import pytz
from odoo import fields, models, api, _
from odoo.exceptions import UserError, ValidationError


class ek_boat_sequence(models.Model):
  _name = 'ek.boat.sequence'
  _description = 'Create Boat Sequence'

  name = fields.Char(string='Name', required=True, copy=False)
  prefix = fields.Char(string='Prefix', required=True)
  sequence = fields.Integer(string='Secuencia', required=True, default=1)
  ek_ship_registration_id = fields.Many2one(
    'ek.ship.registration', string='Boat Information', required=True
  )

  @api.constrains('ek_ship_registration_id')
  def _check_unique_ek_ship_registration_idd(self):
    for record in self:
      if record.ek_ship_registration_id:
        existing_records = self.search(
          [
            ('ek_ship_registration_id', '=', record.ek_ship_registration_id.id),
            ('id', '!=', record.id),
          ]
        )
        if existing_records:
          raise ValidationError('The Boat Information must be unique.')


class ek_boat_location(models.Model):
  _name = 'ek.boat.location'
  _description = 'Create Boat Location'

  name = fields.Char(string='Name', required=True, copy=False)


class ek_crew_member_hierarchy(models.Model):
  _name = 'ek.crew.member.hierarchy'
  _description = 'Create Crew Member Hierarchy'

  name = fields.Char(string='Name', required=True, copy=False)


class reason_arrival(models.Model):
  _name = 'reason.arrival'
  _description = 'Create Reason Arrival'

  name = fields.Char(string='Name', required=True, copy=False)


class ek_type_container(models.Model):
  _name = 'ek.type.container'
  _description = 'Type container'

  name = fields.Char(string='Name', required=True, copy=False)


class ek_group_mail_template(models.Model):
  _name = 'ek.group.mail.template'
  _description = 'Create Group Mail Template'

  name = fields.Char(string='Name', required=True)
  partner_id = fields.Many2one(
    'res.partner', string='Customer', copy=False, required=True
  )

  res_partner_id = fields.Many2many('res.partner', string='CC', copy=False)


class type_service_boat(models.Model):
  _name = 'type.service.boat'
  _description = 'Create type service boat'

  name = fields.Char(string='Name', required=True, copy=False)


class type_boat_operators(models.Model):
  _name = 'type.boat.operators'
  _description = 'Create type boat operators'

  name = fields.Char(string='Name', required=True, copy=False)


class ek_user_groups_reminder(models.Model):
  _name = 'ek.user.groups.reminder'
  _description = 'Create User Groups Reminder'

  name = fields.Char(string='Name', required=True)

  user_ids = fields.Many2many('res.users', string='User', copy=False)


class ek_table_fuel(models.Model):
  _name = 'ek.table.fuel'
  _description = 'Table Fuel'

  name = fields.Char(string='Name', required=True)
  date = fields.Date(string='Date', required=True)
  quantity = fields.Float(string='Quantity', required=True)
  ek_operation_request_id = fields.Many2one(
    'ek.operation.request', string='Operation Request'
  )


class ek_table_gasoline(models.Model):
  _name = 'ek.table.gasoline'
  _description = 'Table Gasoline'

  name = fields.Char(string='Name', required=True)
  date = fields.Date(string='Date', required=True)
  quantity = fields.Float(string='Quantity', required=True)
  ek_operation_request_id = fields.Many2one(
    'ek.operation.request', string='Operation Request'
  )


class ek_table_water(models.Model):
  _name = 'ek.table.water'
  _description = 'Table Water'

  name = fields.Char(string='Name', required=True)
  date = fields.Date(string='Date', required=True)
  quantity = fields.Float(string='Quantity', required=True)
  ek_operation_request_id = fields.Many2one(
    'ek.operation.request', string='Operation Request'
  )


class ek_regimen_table(models.Model):
  _name = 'ek.regimen.table'
  _description = 'Regimen'

  name = fields.Char(string='Name', required=True)
  code = fields.Char(string='Code', required=True)

  description = fields.Text(string='Description')

  ek_regimen_table_ids = fields.Many2many(
    'ek.regimen.table',
    'ek_regimen_table_ek_regimen_table_rel',
    'ek_regimen_table',
    string='Regimen',
    domain="[('id','!=',id)]",
  )

  ################################################################
  ################################################################
  #########################ADUANA#################################


class ek_bl_manifest_record(models.Model):
  _name = 'ek.bl.manifest.record'
  _description = 'Manifest Record'

  name = fields.Char(string='Name', required=True)
  date = fields.Date(string='Date', default=fields.Date.context_today)
  ek_ship_registration_id = fields.Many2one(
    'ek.ship.registration', string='Ship', copy=False
  )
  journey_crew_id = fields.Many2one(
    'ek.boats.information', string='Journey', copy=False
  )


class ek_product_packagens_goods(models.Model):
  _name = 'ek.product.packagens.goods'
  _description = 'Product Packagens Goods'

  ek_operation_request_id = fields.Many2one(
    'ek.operation.request', string='Operation Request'
  )
  name = fields.Text(string='Description')
  ek_requerid_burden_inter_nac_id = fields.Many2one(
    'ek.requerid.burden.inter.nac', string='Items'
  )
  marks = fields.Char(string='Marks', default='S/M')
  gross_weight = fields.Float(string='Gross Weight')
  volume = fields.Float(string='Volume')
  quantity = fields.Float(string='Quantity')

  product_weight_in_lbs = fields.Selection(
    [
      ('0', 'KGS'),
      ('1', 'Pounds'),
    ],
    'Weight unit of measure',
    default=lambda s: s.env['ir.config_parameter']
    .sudo()
    .get_param('product.weight_in_lbs'),
  )
  product_volume_volume_in_cubic_feet = fields.Selection(
    [
      ('0', 'Mt3'),
      ('1', 'Cubic Feet'),
    ],
    'Volume unit of measure',
    default=lambda s: s.env['ir.config_parameter']
    .sudo()
    .get_param('product.volume_in_cubic_feet'),
  )

  @api.onchange('ek_requerid_burden_inter_nac_id')
  def onchange_ek_requerid_burden_inter_nac_id(self):
    if self.ek_requerid_burden_inter_nac_id:
      self.name = self.ek_requerid_burden_inter_nac_id.name
