import base64
import datetime
from io import BytesIO

from odoo import _, api, fields, models
from PIL import Image
from dateutil.relativedelta import relativedelta


class ek_table_gmdss_ship(models.Model):
  _name = 'ek.table.gmdss.ship'
  _description = 'Table GMDSS Ship'

  name = fields.Char(string='Equipment', copy=False)
  brand = fields.Char(string='Brand', copy=False)
  model = fields.Char(string='Model', copy=False)
  series = fields.Char(string='Series', copy=False)
  ek_ship_registration_id = fields.Many2one('ek.ship.registration')


class ek_frequency_epirb(models.Model):
  _name = 'ek.frequency.epirb'
  _description = 'Create ship registration'

  name = fields.Char(string='Name', copy=False)


class ek_ship_registration(models.Model):
  _name = 'ek.ship.registration'
  _description = 'Create ship registration'
  _inherit = ['mail.thread', 'mail.activity.mixin']

  inmarsat_a = fields.Char(string='Inmarsat A')
  inmarsat_b = fields.Char(string='Inmarsat B')
  inmarsat_c = fields.Char(string='Inmarsat C')
  frequency = fields.Many2one('ek.frequency.epirb', string='Frequency EPIRB')
  ek_table_gmdss_ship_ids = fields.One2many(
    'ek.table.gmdss.ship', 'ek_ship_registration_id', string='Table GMDSS Ship'
  )

  # number of

  fuel_tank_cons = fields.Char(string='Fuel Tank for Consumption')
  fish_long_tank = fields.Char(string='fish loading tanks')
  fuel_loading_declared = fields.Char(
    string='fuel loading tanks (declared by shipowner)'
  )
  fuel_tank_market = fields.Char(
    string='fuel tank for marketing (only tankers)'
  )

  # fuel capacity for

  diesel_consump_accord = fields.Char(
    string='diesel for consumption (according to plans)'
  )
  other_spaces_ciba = fields.Char(
    string='other diesel spaces in cibas (declared by shipowner)'
  )
  gasoline_fibre_ship = fields.Char(
    string='gasoline for fiber (declared by shipowner)'
  )
  marketing_tank = fields.Char(string='marketing tank')
  avgas = fields.Char(string='AVGAS')
  calculated_fuel_receive = fields.Char(
    string='calculated volume of fuel that can receive'
  )

  maximun_autonomy = fields.Char(string='maximum autonomy with fuel capacity')
  average_consumtion = fields.Char(
    string=' average consumption per hour at 100%'
  )
  average_daily_opera = fields.Char(
    string='average daily fuel consumption to operate'
  )
  total_fuel_capacity_diesel = fields.Char(
    string='  total fuel capacity (diesel)'
  )

  name = fields.Char(string='Ship Name', copy=False)
  boat_color = fields.Char(string='Boat Color')
  ship_flag_id = fields.Many2one('res.country', string='Ship Flag')
  boat_registration = fields.Char(string='Boat Registration')

  @api.onchange('image')
  def apply_opacity_to_image(self):
    for record in self:
      if record.image:
        image_data = base64.b64decode(record.image)
        img = Image.open(BytesIO(image_data))
        img = img.convert('RGBA')
        overlay = Image.new(
          'RGBA', img.size, (255, 255, 255, int(255 * 0.5))
        )  # Blanco semi-transparente
        img = Image.alpha_composite(img, overlay)
        buffered = BytesIO()
        img.save(buffered, format='PNG')
        img_str = base64.b64encode(buffered.getvalue()).decode()
        record.image_copy = img_str
      else:
        record.image_copy = False

  image = fields.Binary(string='Image')
  image_copy = fields.Binary(string='Image Copy')
  image_1 = fields.Binary(string='Image 1')
  image_2 = fields.Binary(string='Image 2')
  image_3 = fields.Binary(string='Image 3')
  image_4 = fields.Binary(string='Image 4')

  type_photo = fields.Selection(
    [
      ('port', 'Babor '),
      ('helmet', 'Casco '),
      ('starboard', 'Estribor '),
      ('bow', 'Proa '),
      ('popa', 'Popa '),
    ],
    string='Type Photo',
    default='port',
  )

  is_practic = fields.Boolean(string='Is Practic', default=False)

  length = fields.Float(string='Length')
  sleeve = fields.Float(string='Sleeve')
  depth = fields.Float(string='Depth')
  trb = fields.Float(string='T.R.B.')
  trn = fields.Float(string='T.R.N.')

  length_uom = fields.Many2one('uom.uom')
  length_between_perpendiculars_uom = fields.Many2one('uom.uom')
  strut_uom = fields.Many2one('uom.uom')
  trb_uom = fields.Many2one('uom.uom')
  sleeve_uom = fields.Many2one('uom.uom')
  agreement_length_uom = fields.Many2one('uom.uom')
  calado_uom = fields.Many2one('uom.uom')
  calado_aereo_uom = fields.Many2one('uom.uom')
  trn_uom = fields.Many2one('uom.uom')

  calado_proa = fields.Char(string='Calado Proa')
  calado_proa_uom = fields.Many2one('uom.uom')

  calado_popa = fields.Char(string='Calado Popa')
  calado_popa_uom = fields.Many2one('uom.uom')

  ek_boats_measures_1_id = fields.Many2one('ek.boats.measures')
  ek_boats_measures_2_id = fields.Many2one('ek.boats.measures')
  ek_boats_measures_3_id = fields.Many2one('ek.boats.measures')
  ek_boats_measures_4_id = fields.Many2one('ek.boats.measures')
  ek_boats_measures_5_id = fields.Many2one('ek.boats.measures')

  image_url = fields.Char(related='ship_flag_id.image_url')
  ek_boat_location_id = fields.Many2one(
    'ek.boat.location',
    string='Location',
    tracking=True,
  )

  send_notificacion_user_ek = fields.Boolean(
    string='Send Notificacion User', default=False
  )
  ek_user_groups_reminder_id = fields.Many2one(
    'ek.user.groups.reminder', string='User Groups Reminder'
  )

  company_id = fields.Many2one('res.company', default=lambda s: s.env.company)

  state_boats = fields.Selection(
    [
      ('sailing', 'Navegando'),
      ('port', 'En Puerto'),
    ],
    string='State Boats',
    default='port',
    tracking=True,
  )

  ek_boats_information_ids = fields.One2many(
    'ek.boats.information', 'ship_name_id', string='Information Boats'
  )
  bussiness_name_id = fields.Many2one('res.partner', string='Shipper')
  capital_name_id = fields.Many2one('res.partner', string='Ship owner')
  analytic_account_id = fields.Many2one(
    'account.analytic.account',
    string='Analytical Account',
  )
  color = fields.Integer(string='Color Index', default=0)
  account_move_ids = fields.One2many(
    'account.move', 'ship_name_id', string='Account Moves'
  )
  ek_crew_member_hierarchy_number_ids = fields.One2many(
    'ek.crew.member.hierarchy.number',
    'ek_ship_registration_id',
    string='Crew member hierarchy number',
  )

  sequence_id = fields.Many2one('ir.sequence', string='Sequence')

  crew_ids = fields.Many2many(
    'res.partner', string='Crew', domain="[('is_crew', '=', True)]"
  )
  agreement_length = fields.Float(string='Agreement Length')

  type_casco = fields.Char(string='Type Casco')
  protection_casco = fields.Char(string='Cathodical Protection Casco')
  ballast_tank = fields.Char(string='Ballast Tank Coating')
  cathodic_ballast = fields.Char(string='Cathodic Ballast Protection')

  #
  assigned_regime_70 = fields.Boolean(string='Assigned Regime 70')

  @api.model
  def create(self, vals):
    record = super(ek_ship_registration, self).create(vals)
    plan = (
      self.env['account.analytic.plan'].search([], limit=1).id
      if self.env['account.analytic.plan'].search([], limit=1)
      else False
    )
    analytic_account = self.env['account.analytic.account'].create(
      {
        'name': vals.get('name', False),
        'company_id': vals.get('company_id', False),
        'plan_id': plan,
        'code': vals.get('boat_registration', False),
      }
    )
    record.analytic_account_id = analytic_account.id
    return record

  sale_order_count = fields.Integer(
    string='Sale Order Count', compute='_compute_sale_order_count'
  )

  @api.depends('ek_boats_information_ids')
  def _compute_sale_order_count(self):
    for record in self:
      record.sale_order_count = record.env['sale.order'].search_count(
        [
          ('ek_ship_registration_id', '=', record.id),
        ]
      )

  def action_open_documents_sale_order(self):
    self.ensure_one()
    return {
      'name': _('Sale Order'),
      'type': 'ir.actions.act_window',
      'res_model': 'sale.order',
      'view_mode': 'tree,form',
      'views': [
        (
          self.env.ref(
            'ek_l10n_shipping_operations.view_sale_order_tree_custom_ek'
          ).id,
          'tree',
        ),
        (False, 'form'),
      ],
      'context': {
        'default_ek_ship_registration_id': self.id,
      },
      'domain': [('ek_ship_registration_id', 'in', self.ids)],
      'target': 'current',
    }

  # def action_open_documents_sale_order_views(self):
  #     self.ensure_one()
  #     return {
  #         "name": _("Sale Order"),
  #         "type": "ir.actions.act_window",
  #         "res_model": "sale.order",
  #         "view_mode": "tree",
  #         "views": [
  #             (
  #                 self.env.ref(
  #                     "ek_l10n_shipping_operations.view_sale_order_tree_custom_ek"
  #                 ).id,
  #                 "tree",
  #             ),

  #         ],

  #         "domain": [("ek_ship_registration_id", "in", self.ids)],
  #         "target": "current",
  #         "context": {"create": False,
  #                      "edit": False,
  #                      "delete": False,
  #                     "editable":"bottom",
  #                       },
  #     }

  travel_count = fields.Integer(
    string='Travel Count', compute='_compute_travel_count'
  )

  @api.depends('ek_boats_information_ids')
  def _compute_travel_count(self):
    for record in self:
      record.travel_count = record.env['ek.boats.information'].search_count(
        [
          ('ship_name_id', '=', record.id),
        ]
      )

  def action_open_documents_travel(self):
    self.ensure_one()
    return {
      'name': _('Travel'),
      'type': 'ir.actions.act_window',
      'res_model': 'ek.boats.information',
      'view_mode': 'tree,form',
      'context': {
        'default_ship_name_id': self.id,
        'default_fuel': self.fuel,
        'default_fuel_uom': self.fuel_uom.id,
        'default_gasoline': self.gasoline,
        'default_gasoline_uom': self.gasoline_uom.id,
        'default_water': self.water,
        'default_water_uom': self.water_uom.id,
      },
      'domain': [('ship_name_id', 'in', self.ids)],
      'target': 'current',
    }

  account_move_count = fields.Integer(
    string='Invoice Count', compute='_compute_account_move_count'
  )

  @api.depends('account_move_ids')
  def _compute_account_move_count(self):
    for record in self:
      record.account_move_count = record.env['account.move'].search_count(
        [
          ('ship_name_id', '=', record.id),
        ]
      )

  def action_open_documents_account_move(self):
    self.ensure_one()
    return {
      'name': _('Invoice'),
      'type': 'ir.actions.act_window',
      'res_model': 'account.move',
      'view_mode': 'tree,form',
      'context': {
        'default_ship_name_id': self.id,
      },
      'domain': [('ship_name_id', 'in', self.ids)],
      'target': 'current',
    }

  # def action_open_documents_account_move_views(self):
  #     self.ensure_one()
  #     return {
  #         "name": _("Invoice"),
  #         "type": "ir.actions.act_window",
  #         "res_model": "account.move",
  #         "view_mode": "tree",
  #         "domain": [("ship_name_id", "in", self.ids)],
  #         "target": "current",
  #         "context": {"create": False,"edit": False, "delete": False},
  #     }

  ek_operation_request_ids = fields.One2many(
    'ek.operation.request',
    'ek_ship_registration_id',
    string='Request',
    domain=[('is_managemente_date', '=', True)],
  )

  request_count = fields.Integer(
    string='ship Count', compute='_compute_request_count'
  )

  @api.depends('ek_operation_request_ids')
  def _compute_request_count(self):
    for record in self:
      record.request_count = record.env['ek.operation.request'].search_count(
        [
          ('ek_ship_registration_id', '=', record.id),
        ]
      )

  def action_open_documents_request(self):
    """
    Abre la vista de solicitudes del barco actual.
    Pasa el contexto necesario para pre-llenar los campos de barco.
    """
    self.ensure_one()


    # Crear el contexto para la nueva solicitud
    context = {
      'default_ek_ship_registration_id': self.id,
      'search_default_group_by_ek_ship_registration_id': 1,
    }

    # Si el barco tiene business_name_id, incluirlo en el contexto
    if self.bussiness_name_id:
      context['default_res_partner_id'] = self.bussiness_name_id.id


    return {
      'name': _('Solicitudes del Barco %s') % self.name,
      'type': 'ir.actions.act_window',
      'res_model': 'ek.operation.request',
      'view_mode': 'tree,form',
      'context': context,
      'domain': [('ek_ship_registration_id', '=', self.id)],
      'target': 'current',
    }

  # Nuevo método para acceso directo a solicitudes con vista mejorada
  def action_open_enhanced_requests(self):
    """
    Abre la vista mejorada de solicitudes del barco actual.
    """
    self.ensure_one()


    # Crear el contexto para la nueva solicitud
    context = {
      'default_ek_ship_registration_id': self.id,
      'search_default_group_by_ek_ship_registration_id': 1,
    }

    # Si el barco tiene business_name_id, incluirlo en el contexto
    if self.bussiness_name_id:
      context['default_res_partner_id'] = self.bussiness_name_id.id


    return {
      'name': _('Solicitudes del Barco %s') % self.name,
      'type': 'ir.actions.act_window',
      'res_model': 'ek.operation.request',
      'view_mode': 'tree,form',
      'context': context,
      'domain': [('ek_ship_registration_id', '=', self.id)],
      'target': 'current',
    }

  purchase_count = fields.Integer(
    compute='_compute_purchase_count', string='Purchase Order Count'
  )

  @api.depends('ek_operation_request_ids')
  def _compute_purchase_count(self):
    for record in self:
      record.purchase_count = record.env['purchase.order'].search_count(
        [
          ('ek_ship_registration_id', '=', record.id),
        ]
      )

  def action_open_documents_purchase_order(self):
    self.ensure_one()
    return {
      'name': _('Purchase Order'),
      'type': 'ir.actions.act_window',
      'res_model': 'purchase.order',
      'view_mode': 'tree,form',
      'views': [
        (
          self.env.ref(
            'ek_l10n_shipping_operations.view_purchase_order_tree_custom_ek'
          ).id,
          'tree',
        ),
        (False, 'form'),
      ],
      'context': {
        'default_ek_ship_registration_id': self.id,
      },
      'domain': [('ek_ship_registration_id', 'in', self.ids)],
      'target': 'current',
    }

  # def action_open_documents_purchase_order_views(self):
  #     self.ensure_one()
  #     return {
  #         "name": _("Purchase Order"),
  #         "type": "ir.actions.act_window",
  #         "res_model": "purchase.order",
  #         "view_mode": "tree",
  #         "views": [
  #             (
  #                 self.env.ref(
  #                     "ek_l10n_shipping_operations.view_purchase_order_tree_custom_ek"
  #                 ).id,
  #                 "tree",
  #             )
  #         ],

  #         "domain": [("ek_ship_registration_id", "in", self.ids)],
  #         "target": "current",
  #         "context": {"create": False, "edit": False, "delete": False},
  #     }

  ###################CAMPOS ADICIONAL ################
  omi = fields.Char(string='OMI')
  type_shipp = fields.Many2one('ek.type.shipp', string='type shipp')
  type_trafic = fields.Selection(
    [('national', 'Nacional'), ('international', 'International')],
    string='Type of traffic',
  )
  construction_site = fields.Many2one(
    'res.country', string='Construction site'
  )  #

  list_authorized = fields.Selection(
    [('yes', 'Yes'), ('no', 'No')], string='Is on the authorized list'
  )
  has_dms = fields.Selection([('yes', 'Yes'), ('no', 'No')], string='Has DMS')
  propulsion = fields.Char(string='Propulsion')  #
  use = fields.Char(string='Use')
  autonomy = fields.Char(string='Autonomy')
  service = fields.Char(string='Service')

  authorized_service = fields.Char(string='Authorized service')
  navigation_area = fields.Char(string='Navigation area')
  maritime_area = fields.Char(string='Maritime area')
  authorized_maritime_area = fields.Char(string='Authorized maritime_area ')
  registration_port = fields.Many2one(
    'ek.res.world.seaports', string='Registration port'
  )

  authorized_route = fields.Char(string='Authorized route')
  displacement_ballast = fields.Char(string='Displacement ballast')

  passenger_capacity = fields.Char(string='Passenger capacity')
  enabled_capacity = fields.Char(string='Enabled capacity')

  load_capacity = fields.Char(string='Load capacity')
  call_sign = fields.Char(string='Call sign')  #
  dead_weight = fields.Char(string='Dead weight')
  crew_capacity = fields.Char(string='Crew capacity')
  warehouse_capacity = fields.Char(string='Warehouse capacity')

  calado = fields.Float(string='Calado')
  calado_aereo = fields.Float(string='Calado Aereo')
  mm_yes = fields.Char(string='MM Yes')
  builder = fields.Char(string='Builder')

  keel_laying_date = fields.Date(string='Keel laying date')
  plan_approval_date = fields.Date(string='Plan approval date')
  registration_date = fields.Date(string='Registration date')
  helmet_material = fields.Char(string='Helmet material')
  origin = fields.Char(string='Origin')
  contract_signing_date = fields.Date(string='Contract signing date')
  cover_numbera = fields.Integer(string='Cover number')
  province_id = fields.Many2one(
    'res.country.state',
    string='Province',
  )
  canton = fields.Many2one('ek.res.country.canton', string='Canton')
  caleta = fields.Char(string='Caleta')
  guild = fields.Char(string='Guild')
  harmonized_to = fields.Char(string='Harmonized to')
  building_date = fields.Date(string='Building date')
  harmonization_date = fields.Date(string='Harmonization date')
  class_date = fields.Date(string='Class date')
  minimum_endowment = fields.Integer(string='Minimum endowment')
  propulsion_type = fields.Char(string='Propulsion type')
  rating_society = fields.Char(string='Rating society')

  #############################

  trip_details_days_count = fields.Integer(
    compute='_compute_trip_details_days_count', string='Purchase Order Count '
  )

  @api.depends('ek_operation_request_ids')
  def _compute_trip_details_days_count(self):
    for record in self:
      record.trip_details_days_count = record.env[
        'trip.details.days'
      ].search_count(
        [
          ('ship_name_id', '=', record.id),
        ]
      )

  def action_open_documents_trip_details_days(self):
    self.ensure_one()
    return {
      'name': _('trip details days'),
      'type': 'ir.actions.act_window',
      'res_model': 'trip.details.days',
      'view_mode': 'tree',
      'view_id': self.env.ref(
        'ek_l10n_shipping_operations.trip_details_days_tree'
      ).id,
      'domain': [('ship_name_id', 'in', self.ids)],
      'target': 'current',
      'context': {
        'create': False,
        'edit': False,
        'delete': False,
      },
    }

  ship_document_certificate_count = fields.Integer(
    compute='_compute_ship_document_certificate_count',
    string=' Purchase Order Count ',
  )
  ek_ship_document_certificate_ids = fields.One2many(
    'ek.ship.document.certificate',
    'ship_name_id',
    string='Ship Document Certificate',
  )

  ship_document_certificate_count_expired = fields.Integer(
    compute='_compute_ship_document_certificate_count_expired',
    string='Document Expired',
  )

  @api.depends('ek_ship_document_certificate_ids')
  def _compute_ship_document_certificate_count_expired(self):
    for record in self:
      record.ship_document_certificate_count_expired = record.env[
        'ek.ship.document.certificate'
      ].search_count(
        [
          ('ship_name_id', '=', record.id),
          ('document_status', 'in', ['expired', 'to_wi']),
        ]
      )

  @api.depends('ek_ship_document_certificate_ids')
  def _compute_ship_document_certificate_count(self):
    for record in self:
      record.ship_document_certificate_count = record.env[
        'ek.ship.document.certificate'
      ].search_count(
        [
          ('ship_name_id', '=', record.id),
        ]
      )

  def action_open_ship_document_certificate_count(self):
    self.ensure_one()
    return {
      'name': _('Ship Document Certificate'),
      'type': 'ir.actions.act_window',
      'res_model': 'ek.ship.document.certificate',
      'view_mode': 'tree,form',
      'context': {
        'default_ship_name_id': self.id,
      },
      'views': [
        (
          self.env.ref(
            'ek_l10n_shipping_operations.ek_ship_document_certificate_tree'
          ).id,
          'tree',
        ),
        (
          self.env.ref(
            'ek_l10n_shipping_operations.ek_ship_document_certificate_form'
          ).id,
          'form',
        ),
      ],
      'domain': [('ship_name_id', 'in', self.ids)],
      'target': 'current',
    }

  @api.model
  def cron_create_reminder_ship_documents(self):
    ships = self.search(
      [
        ('send_notificacion_user_ek', '=', True),
        ('ek_user_groups_reminder_id', '!=', False),
      ]
    )
    for ship in ships:
      try:
        ship.create_reminder_ship_documents()
      except:
        pass

  def create_reminder_ship_documents(self):
    send_settings = self.env['ek.setting.send.boat'].search([])

    for doc in self.ek_ship_document_certificate_ids:
      if not doc.expiration_date:
        continue  # Saltar documentos sin fecha de finalización

      for send in send_settings:
        date_expiration = doc.expiration_date
        date = datetime.date.today()
        date_activity = False
        summary = None

        if (
          send.document_status == 'expired'
        ):  # Expirado, días después de expirar
          target_date = date - date_expiration
          if target_date.days >= send.days:
            date_activity = True
            summary = (
              f'Document {doc.name.name} of Ship  {self.name} is expired'
            )
            doc.write({'document_status': 'expired'})

        elif (
          send.document_status == 'to_wi'
        ):  # Por vencer, días antes de expirar
          target_date = date - date_expiration
          if target_date.days >= send.days and target_date.days < 0:
            date_activity = True
            summary = f'Document {doc.name.name} of Ship  {self.name} is about to expire.'
            doc.write({'document_status': 'to_wi'})

        if date_activity:
          users = self.ek_user_groups_reminder_id.user_ids
          self.send_user_reminder_ship_documents(body=summary, users=users)

  def send_user_reminder_ship_documents(self, body=None, users=None):
    odoobot = self.env.ref('base.partner_root')
    user_mentions = ', '.join(['@' + user.name for user in users])

    nocontent_body = ('%(body)s %(user_names)s') % {
      'body': body,
      'user_names': user_mentions,
    }

    for record in self:
      record.message_post(
        body=nocontent_body,
        message_type='comment',
        subtype_xmlid='mail.mt_comment',
        author_id=odoobot.id,
        partner_ids=[user.partner_id.id for user in users],
      )

  def action_open_boat_arching(self):
    self.ensure_one()
    return {
      'name': _('Arching'),
      'type': 'ir.actions.act_window',
      'res_model': 'ek.ship.registration',
      'view_mode': 'form',
      'res_id': self.id,
      'view_id': self.env.ref(
        'ek_l10n_shipping_operations.ek_ship_registration_form_boat_arching'
      ).id,
      'context': {
        'create': False,
        'delete': False,
      },
      'target': 'new',
    }

  def action_open_boat_characteristics(self):
    self.ensure_one()
    return {
      'name': _('Record'),
      'type': 'ir.actions.act_window',
      'res_model': 'ek.ship.registration',
      'view_mode': 'form',
      'res_id': self.id,
      'view_id': self.env.ref(
        'ek_l10n_shipping_operations.ek_ship_registration_form_boat_registre'
      ).id,
      'context': {
        'create': False,
        'delete': False,
      },
      'target': 'new',
    }

  def action_open_boat_contamination(self):
    self.ensure_one()
    return {
      'name': _('Record'),
      'type': 'ir.actions.act_window',
      'res_model': 'ek.ship.registration',
      'view_mode': 'form',
      'res_id': self.id,
      'view_id': self.env.ref(
        'ek_l10n_shipping_operations.ek_ship_registration_form_contamination'
      ).id,
      'context': {
        'create': False,
        'delete': False,
      },
      'target': 'new',
    }

  def action_open_boat_loading_lines(self):
    self.ensure_one()
    return {
      'name': _('Loading Lines'),
      'type': 'ir.actions.act_window',
      'res_model': 'ek.ship.registration',
      'view_mode': 'form',
      'res_id': self.id,
      'view_id': self.env.ref(
        'ek_l10n_shipping_operations.ek_ship_registration_form_loading_lines'
      ).id,
      'context': {
        'create': False,
        'delete': False,
      },
      'target': 'new',
    }

  def action_open_boat_security_equipments(self):
    self.ensure_one()
    return {
      'name': _('Security Equipments'),
      'type': 'ir.actions.act_window',
      'res_model': 'ek.ship.registration',
      'view_mode': 'form',
      'res_id': self.id,
      'view_id': self.env.ref(
        'ek_l10n_shipping_operations.ek_ship_registration_form_security_equipments'
      ).id,
      'context': {
        'create': False,
        'delete': False,
      },
      'target': 'new',
    }

  def action_open_gmdss(self):
    self.ensure_one()
    return {
      'name': _('GMDSS'),
      'type': 'ir.actions.act_window',
      'res_model': 'ek.ship.registration',
      'view_mode': 'form',
      'res_id': self.id,
      'view_id': self.env.ref(
        'ek_l10n_shipping_operations.ek_ship_registration_gmdss_equipments'
      ).id,
      'context': {
        'create': False,
        'delete': False,
      },
      'target': 'new',
    }

  def action_open_fuel_control(self):
    self.ensure_one()
    return {
      'name': _('Fuel Control'),
      'type': 'ir.actions.act_window',
      'res_model': 'ek.ship.registration',
      'view_mode': 'form',
      'res_id': self.id,
      'view_id': self.env.ref(
        'ek_l10n_shipping_operations.ek_ship_registration_control_fuel'
      ).id,
      'context': {
        'create': False,
        'delete': False,
      },
      'target': 'new',
    }

  length_between_perpendiculars = fields.Float(
    string='Length between perpendiculars'
  )
  strut = fields.Float(string='Strut')
  cellar = fields.Float(string='Cellar')
  capacity = fields.Float(string='Capacity')
  warehouse_capacity = fields.Char(string='Warehouse capacity')

  tropical_free_board = fields.Char(string='Tropical Free Board')
  free_board_summer = fields.Char(string='Free Board Summer')
  free_board_winter = fields.Char(string='Free Board Winter')

  free_board_fresh_water_summer = fields.Char(
    string='Free Board Fresh Water Summer'
  )
  free_board_north_atlantic_winter = fields.Char(
    string='Free Board North Atlantic Winter'
  )

  frank_bordering_tropical_wood = fields.Char(
    string='Frank Bordering Tropical Wood'
  )
  frank_edge_wood_summer = fields.Char(string='Frank Edge Wood Summer')
  free_board_way_winter = fields.Char(string='Free Board Way Winter')
  free_board_fresh_water_wood = fields.Char(
    string='Free Board Fresh Water Wood'
  )
  covered_reference_line = fields.Char(string='Covered Reference Line')

  authorized_maritime_zone = fields.Char(string='Authorized Maritime Zone')
  number_of_fire_bombs = fields.Char(string='Number of Fire Bombs')
  ship_state = fields.Char(string='Ship State')
  observation = fields.Text(string='Observatión')

  fire_pump_type = fields.Char(string='Fire Pump Type')
  non_operational_date = fields.Date(string='Non Operational Date')

  fuel = fields.Float(string='Fuel', tracking=True)
  fuel_uom = fields.Many2one('uom.uom', string='Fuel UOM', tracking=True)
  gasoline = fields.Float(string='Gasoline ', tracking=True)
  gasoline_uom = fields.Many2one(
    'uom.uom', string='Gasoline UOM', tracking=True
  )
  water = fields.Float(string='Water', tracking=True)
  water_uom = fields.Many2one('uom.uom', string='Water UOM', tracking=True)

  # contamination

  lubricating_capacity = fields.Float(string='Lubricating Capacity')
  lubricament_uom = fields.Many2one('uom.uom', string='Lubricament UOM')
  sludge_capacity = fields.Float(string='Sludge Capacity')
  sludge_uom = fields.Many2one('uom.uom', string='Sludge UOM')

  black_water_capacity = fields.Float(string='Black Water Capacity')
  black_water_uom = fields.Many2one('uom.uom', string='Black Water UOM')
  antifouling_manufacturer_name = fields.Char(
    string='Antifouling Manufacturer Name'
  )
  autonomy = fields.Float(string='Autonomy')
  autonomy_uom = fields.Many2one('uom.uom', string='Autonomy UOM')

  capacity_oily_water = fields.Float(string='Capacity Oily Water')
  capacity_oily_water_uom = fields.Many2one(
    'uom.uom', string='Capacity Oily Water UOM'
  )

  waste_capacity = fields.Float(string='Waste Capacity')
  waste_capacity_uom = fields.Many2one('uom.uom', string='Waste Capacity UOM')

  bilge_water_capacity = fields.Float(string='Bilge Water Capacity')
  bilge_water_capacity_uom = fields.Many2one(
    'uom.uom', string='Bilge Water Capacity UOM'
  )
  antifouling_application_date = fields.Datetime(
    string='Antifouling Application Date'
  )
  antifouling_name = fields.Char(string='Antifouling Name')
  speed = fields.Float(string='Speed')
  speed_uom = fields.Many2one('uom.uom', string='Speed UOM')

  # aduana
  assigned_regimen_70 = fields.Boolean(string='Assigned Regimen 70')


class ek_crew_member_hierarchy_number(models.Model):
  _name = 'ek.crew.member.hierarchy.number'
  _description = 'Create Crew Member Hierarchy'

  name = fields.Integer(string='Name', required=True, default=1, copy=False)
  ek_crew_member_hierarchy_id = fields.Many2one(
    'ek.crew.member.hierarchy', string='Crew member hierarchy'
  )
  ek_ship_registration_id = fields.Many2one(
    'ek.ship.registration', string='Boat Information'
  )


class trip_details_days(models.Model):
  _name = 'trip.details.days'
  _description = 'Create Trip Details Days'
  _inherit = ['common.fields.mixin']

  ship_name_id = fields.Many2one('ek.ship.registration', string='Ship Name')
  journey_crew_id = fields.Many2one('ek.boats.information', string='Journey')
  ek_res_world_seaports_id = fields.Many2one(
    'ek.res.world.seaports', string='Port of Origin'
  )
  ek_res_world_seaports_d_id = fields.Many2one(
    'ek.res.world.seaports', string='Port of Destination'
  )
  eta = fields.Datetime('ETA')
  ata = fields.Datetime('ATA')
  etd = fields.Datetime('ETD')
  atd = fields.Datetime('ATD')

  estimate_port = fields.Float(
    'Estimate days Port', compute='_compute_days_count'
  )  # estimated days in port

  actal_port = fields.Float(
    'Actual days Port', compute='_compute_days_count'
  )  # actual days in port

  estimate_navigation = fields.Float(
    'Estimate days Navigation', compute='_compute_days_count_calculo'
  )  # estimated days in navigation

  actal_navigation = fields.Float(
    'Actual days Navigation', compute='_compute_days_count_calculo'
  )  # real days in navigation
  calculo_journey_crew_id = fields.Many2one(
    'ek.boats.information', string='Related Trip '
  )  # campo para hacer el calculo

  agent_user_id_arribo = fields.Many2one(
    'res.users', string='Agent Arribo', copy=False
  )
  type_event_arribo = fields.Selection(
    [
      ('national', 'National'),
      ('internacional', 'Internacional'),
    ],
    string='Type Event Arribo',
    required=False,
    default=False,
    copy=False,
  )
  ek_boat_location_id_arribo = fields.Many2one(
    'ek.boat.location', string='Boat Location Arribo', copy=False
  )

  agent_user_id_zarpe = fields.Many2one(
    'res.users', string='Agent Zarpe', copy=False
  )
  type_event_zarpe = fields.Selection(
    [
      ('national', 'National'),
      ('internacional', 'Internacional'),
    ],
    string='Type Event Zarpe',
    required=False,
    default=False,
    copy=False,
  )
  ek_boat_location_id_zarpe = fields.Many2one(
    'ek.boat.location', string='Boat Location Zarpe', copy=False
  )

  @api.depends('eta', 'ata', 'etd', 'atd')
  def _compute_days_count(self):
    for record in self:
      if record.etd and record.eta:
        delta = record.etd - record.eta
        record.estimate_port = delta.total_seconds() / 86400
      else:
        record.estimate_port = 0

      if record.atd and record.ata:
        delta = record.atd - record.ata
        record.actal_port = delta.total_seconds() / 86400
      else:
        record.actal_port = 0

  @api.depends(
    'eta', 'ata', 'etd', 'atd', 'calculo_journey_crew_id', 'date_today'
  )
  def _compute_days_count_calculo(self):
    for record in self:
      if record.calculo_journey_crew_id:
        if record.etd and record.calculo_journey_crew_id.eta:
          delta = record.calculo_journey_crew_id.eta - record.etd
          record.estimate_navigation = delta.total_seconds() / 86400
        else:
          record.estimate_navigation = 0

        if record.atd and record.calculo_journey_crew_id.ata:
          delta = record.calculo_journey_crew_id.ata - record.atd
          record.actal_navigation = delta.total_seconds() / 86400
        else:
          record.actal_navigation = 0
      else:
        if record.etd and record.atd and record.date_today:
          delta1 = record.date_today - record.etd.date()
          delta2 = record.date_today - record.atd.date()

          record.estimate_navigation = delta1.total_seconds() / 86400
          record.actal_navigation = delta2.total_seconds() / 86400
        else:
          record.estimate_navigation = 0
          record.actal_navigation = 0


class ek_ship_document_type(models.Model):
  _name = 'ek.ship.document.type'
  _description = 'Create Ship Document Type'

  name = fields.Char(string='Name', required=True, copy=False)


class ek_ship_document_certificate(models.Model):
  _name = 'ek.ship.document.certificate'
  _description = 'Create Ship Document Certificate'
  _inherit = ['mail.thread', 'mail.activity.mixin', 'common.fields.mixin']

  name = fields.Many2one(
    'ek.ship.document.type',
    string='Name',
    required=True,
    copy=False,
    tracking=True,
  )
  date_issue = fields.Date(
    string='Date Issue', required=True, copy=False, tracking=True
  )
  next_endorsement_date = fields.Date(
    string='Next Endorsement Date', required=False, copy=False, tracking=True
  )
  expiration_date = fields.Date(
    string='Expiration Date', required=True, copy=False, tracking=True
  )
  date_limit = fields.Date(
    string='Date Limit', required=False, copy=False, tracking=True
  )
  code = fields.Char(string='Code', required=False, copy=False, tracking=True)
  institution_id = fields.Many2one('res.partner', string='Institution', tracking=True, help="Entity issuing or managing this certificate (e.g. DIRNEA)")
  ship_name_id = fields.Many2one('ek.ship.registration', string='Ship Name')

  range_from_date = fields.Date(
      string='Tolerance Range From', tracking=True,
      help="Start date of the permitted tolerance range to renew the inspection or document."
  )
  range_to_date = fields.Date(
      string='Tolerance Range To', tracking=True,
      help="Limit date of the permitted tolerance range. If there's a subsequent grace period, set it here."
  )
  periodicity = fields.Integer(
      string='Renews Every', 
      help="Indicate how often this procedure must be performed (e.g. set 2 if it's every 2 years)."
  )
  periodicity_type = fields.Selection([
      ('days', 'Days'),
      ('weeks', 'Weeks'),
      ('months', 'Months'),
      ('years', 'Years')
  ], string='Frequency Type', default='months', tracking=True)
  
  alert_time = fields.Integer(
      string='Notify Before', tracking=True, 
      help="Lead time period before which the alarm email will be triggered (e.g. 1 month before expiration)."
  )
  alert_time_type = fields.Selection([
      ('days', 'Days'),
      ('weeks', 'Weeks'),
      ('months', 'Months'),
      ('years', 'Years')
  ], string='Alert Unit', default='months', tracking=True)
  alert_start_time = fields.Float(
      string='Alert Start Time', tracking=True, default=8.0,
      help="Time of day (in current timezone) from which the alert email should be triggered."
  )
  
  contact_ids = fields.Many2many(
      'res.partner', string='Alert Contacts', tracking=True,
      help="Select the managers, technicians, owners or entities that must necessarily receive the reminder email."
  )
  notes = fields.Html(
      string='Notes & Requirements',
      help="Additional observations, necessary documents, or details of what the inspector requires at the moment of the visit. This note will be included in the body of the email."
  )
  last_alert_sent_date = fields.Date(string='Last Alert Sent Date', readonly=True)
  next_alert_date = fields.Date(
      string='Next Alert Date',
      compute='_compute_next_alert_date',
      store=True,
      help="Estimated date when the next alert will be automatically sent."
  )

  def get_contact_ids_str(self):
      return ','.join(map(str, self.contact_ids.ids))

  @api.depends('expiration_date', 'alert_time', 'alert_time_type')
  def _compute_next_alert_date(self):
      for record in self:
          if record.expiration_date and record.alert_time and record.alert_time_type:
              try:
                  alert_delta = relativedelta()
                  if record.alert_time_type == 'days':
                      alert_delta = relativedelta(days=record.alert_time)
                  elif record.alert_time_type == 'weeks':
                      alert_delta = relativedelta(weeks=record.alert_time)
                  elif record.alert_time_type == 'months':
                      alert_delta = relativedelta(months=record.alert_time)
                  elif record.alert_time_type == 'years':
                      alert_delta = relativedelta(years=record.alert_time)
                  record.next_alert_date = record.expiration_date - alert_delta
              except Exception:
                  record.next_alert_date = False
          else:
              record.next_alert_date = False

  document_status = fields.Selection(
    [
      ('current', 'Current'),
      ('to_wi', 'To Win'),
      ('expired', 'Expired'),
    ],
    string='Document Status',
    default='current',
    tracking=True,
    compute='_onchange_date_end',
    store=True,
  )

  @api.depends('expiration_date', 'date_today')
  def _onchange_date_end(self):
    self.document_status = 'to_wi'
    for record in self:
      if record.expiration_date:
        today = datetime.date.today()
        expiration_date = fields.Date.from_string(record.expiration_date)
        if expiration_date <= today:
          record.document_status = 'expired'

        elif expiration_date > today:
          record.document_status = 'current'

  @api.model
  def cron_check_and_send_alerts(self):
    today = fields.Date.today()
    records = self.search([('expiration_date', '!=', False)])
    for doc in records:
      if not doc.alert_time or not doc.alert_time_type or not doc.contact_ids:
          continue

      alert_delta = relativedelta()
      if doc.alert_time_type == 'days':
          alert_delta = relativedelta(days=doc.alert_time)
      elif doc.alert_time_type == 'weeks':
          alert_delta = relativedelta(weeks=doc.alert_time)
      elif doc.alert_time_type == 'months':
          alert_delta = relativedelta(months=doc.alert_time)
      elif doc.alert_time_type == 'years':
          alert_delta = relativedelta(years=doc.alert_time)

      alert_date = doc.expiration_date - alert_delta
      
      if today >= alert_date:
          if not doc.last_alert_sent_date or doc.last_alert_sent_date < alert_date:
              # Verificar la hora de inicio de la alerta (alert_start_time) si está configurada
              current_time_float = fields.Datetime.context_timestamp(self, fields.Datetime.now()).hour + fields.Datetime.context_timestamp(self, fields.Datetime.now()).minute / 60.0
              if current_time_float >= (doc.alert_start_time or 0.0):
                  doc._send_alert_email()
                  doc.last_alert_sent_date = today

  def _send_alert_email(self):
      template = self.env.ref('ek_l10n_shipping_operations.email_template_certificate_alert', raise_if_not_found=False)
      if template:
          template.send_mail(self.id, force_send=True)
