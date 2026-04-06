import base64
import datetime
import re

import pytz
from markupsafe import Markup
from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError
from odoo.tools import html_escape


class ek_operation_request(models.Model):
  _name = 'ek.operation.request'
  _description = 'Create Operations Request'
  _inherit = ['common.fields.mixin', 'ek.l10n.model.mixin']

  @api.model
  def default_get(self, fields_list):
    """
    Método para pre-llenar campos por defecto basado en el contexto.
    Permite que cuando se navegue desde Buques -> Viajes -> Solicitudes,
    los campos de barco y viaje se pre-llenen automáticamente.

    Funcionalidad adicional:
    - Si hay viaje del contexto: mantenerlo
    - Si no hay viaje pero hay barco: buscar el último viaje del barco
    """
    defaults = super(ek_operation_request, self).default_get(fields_list)

    # Obtener el contexto actual
    context = self.env.context

    # IMPORTANTE: Primero pre-llenar el barco, luego el viaje
    # para evitar que el onchange del barco limpie el viaje

    # Si viene desde la vista de viajes (ek.boats.information)
    if context.get('default_journey_crew_id'):
      journey_id = context.get('default_journey_crew_id')

      # Buscar el viaje para obtener el barco asociado
      journey = self.env['ek.boats.information'].browse(journey_id)

      if journey and journey.ship_name_id:
        # Primero pre-llenar el barco
        ship_id = journey.ship_name_id.id
        defaults['ek_ship_registration_id'] = ship_id

        # Luego pre-llenar el viaje (después del barco)
        defaults['journey_crew_id'] = journey_id

        # Pre-llenar el cliente si está disponible
        if journey.ship_name_id.bussiness_name_id:
          partner_id = journey.ship_name_id.bussiness_name_id.id
          defaults['res_partner_id'] = partner_id

    # Si viene desde la vista de barcos (ek.ship.registration)
    elif context.get('default_ek_ship_registration_id'):
      ship_id = context.get('default_ek_ship_registration_id')

      # Buscar el barco
      ship = self.env['ek.ship.registration'].browse(ship_id)

      if ship:
        # Pre-llenar el barco
        defaults['ek_ship_registration_id'] = ship_id

        # NUEVA FUNCIONALIDAD: Buscar el último viaje del barco si no hay viaje del contexto
        if not context.get('default_journey_crew_id'):
          # Buscar el último viaje del barco que NO esté finalizado
          last_journey = self.env['ek.boats.information'].search(
            [
              ('ship_name_id', '=', ship_id),
              ('state', 'in', ['draft', 'process']),
            ],
            order='create_date desc',
            limit=1,
          )

          if last_journey:
            defaults['journey_crew_id'] = last_journey.id

        # Pre-llenar el cliente si está disponible
        if ship.bussiness_name_id:
          partner_id = ship.bussiness_name_id.id
          defaults['res_partner_id'] = partner_id

    # NUEVA FUNCIONALIDAD: Si solo hay barco en los defaults (sin contexto)
    # pero no hay viaje, buscar el último viaje del barco
    elif (
      defaults.get('ek_ship_registration_id')
      and not defaults.get('journey_crew_id')
      and not context.get('default_journey_crew_id')
    ):
      ship_id = defaults.get('ek_ship_registration_id')

      # Buscar el último viaje del barco que NO esté finalizado
      last_journey = self.env['ek.boats.information'].search(
        [('ship_name_id', '=', ship_id), ('state', 'in', ['draft', 'process'])],
        order='create_date desc',
        limit=1,
      )

      if last_journey:
        defaults['journey_crew_id'] = last_journey.id

    return defaults

  def _get_object_validation_model_config(self):
    return {
      self._name: {
        '_inherit_dinamic_view': 'ek_operation_request_form',
        '_inherit_position_view': 'after',
        '_inherit_xpath_view': "//group[@name='dinamic_view']",
        '_module_dinamic_name': 'ek_l10n_shipping_operations',
        '_inherit_dinamic_fields_position': [
          {
            'name': 'date_end',
            'xpath': "//field[@name='create_date']",
            'position': 'after',
          },
          {
            'name': 'date_start',
            'xpath': "//field[@name='create_date']",
            'position': 'before',
          },
          {
            'name': 'manual_day',
            'xpath': "//field[@name='date_start']",
            'position': 'after',
          },
          {
            'name': 'date_end_request',
            'xpath': "//field[@name='create_date']",
            'position': 'after',
          },
          {
            'name': 'date_emition_request',
            'xpath': "//field[@name='create_date']",
            'position': 'after',
          },
          {
            'name': 'ek_operation_request_id',
            'xpath': "//field[@name='type_id']",
            'position': 'after',
          },
        ],
      }
    }

  name = fields.Char(
    string='#Doc Internal',
    tracking=True,
    copy=True,
    default='/',
  )
  crew_ids = fields.One2many(
    'table.crew.member.ek.operation.request',
    'ek_operation_request_id',
    string='Crew List',
  )
  value_receive = fields.Float(
    string='Value Receive',
    default=0,
    tracking=True,
    help='This field is to define the number of tons that the ship has',
  )
  quantity_bonus = fields.Float(
    string='Fishing Advance (CURRENT) or balance (PREVIOUS)',
    default=0,
    tracking=True,
  )
  fishing_balance = fields.Float(
    string='Total Pending ',
    default=0,
    tracking=True,
    compute='compputed_total_pending',
  )
  fishing_advance = fields.Float(string='Fishing Advance', default=0)
  notes_pay_crew = fields.Text(string='Concept', tracking=True)
  description_name = fields.Text(
    string='Description...',
    tracking=True,
    compute='_compute_description_fields',
    store=True,
    readonly=False,
  )

  description_name_html = fields.Html(
    string='Description (Formatted)',
    help='Descripción con formato HTML editable',
    compute='_compute_description_fields',
    store=True,
    readonly=False,
  )
  res_partner_id = fields.Many2one(
    'res.partner',
    string='Customer',
    tracking=True,
  )
  ek_ship_registration_id = fields.Many2one(
    'ek.ship.registration',
    string='Shipper',
    tracking=True,
  )
  journey_crew_id = fields.Many2one(
    'ek.boats.information',
    string='Journey',
    domain="['&', '|', ('ship_name_id','=',False), ('ship_name_id','=',ek_ship_registration_id), ('state','in',['draft','process'])]",
    tracking=True,
  )
  capital_port_id = fields.Many2one(
    'res.partner', string='Proveedor', tracking=True
  )
  city_id = fields.Many2one('ek.res.country.city', string='City', tracking=True)
  analytic_account_id = fields.Many2one(
    'account.analytic.account', string='Analytical Account', tracking=True
  )
  nationality_id = fields.Many2one('res.country', string='Nationality')
  ek_table_pay_crew_ids = fields.One2many(
    'ek.table.pay.crew',
    'ek_operation_request',
    string='Table Pay Crew',
    copy=True,
  )
  download_report = fields.Boolean(related='type_id.download_report')
  company_id = fields.Many2one(
    'res.company', default=lambda s: s.env.company, tracking=True
  )
  shipping_agent_id = fields.Many2one(
    'res.partner', string='Agente', tracking=True
  )
  additional_explanation = fields.Text(
    string='Additional Explanation', tracking=True
  )
  text_descripton_capman = fields.Html(
    string='Text for billing in Requests Capman',
    default=lambda self: self._default_billing_text_capman(),
  )
  account_move_ids = fields.One2many(
    'account.move', 'operation_request_id', string='Account Move'
  )
  state_document = fields.Selection(
    [
      ('current', 'Current'),
      ('expired', 'Expired'),
    ],
    string='State document',
    default='current',
    tracking=True,
  )
  check_default = fields.Boolean(
    'Check Default',
    default=True,
  )
  block_user_asig = fields.Boolean(string='Block User Asig')
  agent_user_id = fields.Many2one(
    'res.users',
    string='Agent',
    tracking=True,
    domain="[('is_shipping_agent', '=', True)]",
  )
  ek_template_py3o_ids = fields.Many2many(
    'ek.template.py3o',
    'ek_type_request_py3o',
    'ek_type_request',
    copy=False,
    compute='_defaul_template_py3o',
    string='Templates',
  )
  ek_template_py3o_id = fields.Many2one(
    'ek.template.py3o',
    string='Plantilla',
    domain="[('id', 'in', ek_template_py3o_ids)]",
  )
  ek_report_stages_mixin_ids = fields.Many2many(
    'ek.report.stages.mixin',
    'ek_report_stages_mixin_operation_request_rel_q',
    'ek_report_stages_mixin',
    string='Stages Report',
    copy=False,
    readonly=True,
  )

  @api.depends('ek_report_stages_mixin_ids')
  def _defaul_template_py3o(self):
    self.ek_template_py3o_ids = False
    if self.type_id:
      for rec in self.ek_report_stages_mixin_ids.filtered(
        lambda x: x.stage_id.id == self.stage_id.id
      ):
        self.ek_template_py3o_ids = rec.ek_template_py3o_ids

  def _default_billing_text_capman(self):
    """Genera el HTML por defecto para el campo text_descripton_capman"""
    company = self.env.company

    # Obtener el nombre de la empresa
    company_name = company.display_name or company.name or ''

    # Obtener el RUC/VAT
    company_vat = company.vat or company.company_registry or ''

    # Obtener email
    company_email = company.email or ''

    # Construir la dirección desde company_details o campos individuales
    address = ''
    if company.company_details:
      # Extraer texto de los company_details (remover HTML tags)
      import re

      address_text = re.sub(r'<[^>]+>', ' ', company.company_details)
      address_text = re.sub(r'\s+', ' ', address_text).strip()
      # Tomar solo las primeras líneas (empresa, dirección, ciudad)
      lines = address_text.split('\n')[:3]
      if len(lines) > 1:  # Si hay más de una línea, usar desde la segunda
        address = ' - '.join(lines[1:]).strip()

    if not address:
      # Construir dirección manualmente si no hay company_details
      street = company.street or ''
      city = company.city or ''
      if street and city:
        address = f'{city} - {street}'
      elif city:
        address = city

    # Obtener teléfonos
    phone = company.phone or ''

    # Construir el HTML con saltos de línea
    billing_parts = []

    # Agregar nombre de empresa
    if company_name:
      billing_parts.append(
        f'FACTURAR A NOMBRE DE: <strong>{company_name}</strong>'
      )

    # Agregar RUC
    if company_vat:
      billing_parts.append(f'RUC: <strong>{company_vat}</strong>')

    # Agregar dirección
    if address:
      billing_parts.append(f'DIRECCIÓN: {address}')

    # Agregar teléfonos
    if phone:
      billing_parts.append(f'TELÉFONOS: {phone}')

    # Agregar email
    if company_email:
      billing_parts.append(f'EMAIL: {company_email}')

    # Unir todas las partes con saltos de línea
    if billing_parts:
      billing_html = f'<p>{"<br/>".join(billing_parts)}</p>'
    else:
      billing_html = '<p>FACTURAR A NOMBRE DE: <strong>NAVIERA SANTA KATALINA SANTAKATALINA S.A.</strong><br/>RUC: 1391879032001<br/>DIRECCIÓN: MANTA - AVENIDA 3 Y CALLES 13 Y 14<br/>TELÉFONOS: +593 5-262-2012<br/>EMAIL: facturacion@navierasantakatalina.com</p>'

    return billing_html

  # fecha de arribo
  eta = fields.Datetime(string='ETA', copy=False, tracking=True)
  ata = fields.Datetime(string='ATA', copy=False, tracking=True)

  # fecha de zarpe
  etd = fields.Datetime(string='ETD', copy=False, tracking=True)
  atd = fields.Datetime(string='ATD', copy=False, tracking=True)

  type_event_boot = fields.Selection(
    [
      ('zarpe', 'Zarpe'),
      ('arribo', 'Arribo'),
      ('fondeo', 'Fondeo/Maniobra'),
      ('atraque', 'Atraque/Desatraque'),
      ('dique', 'Dique/Otros'),
    ],
    string='Type Event Boot',
    required=False,
    default=False,
    copy=False,
    tracking=True,
  )
  type_event = fields.Selection(
    [
      ('national', 'National'),
      ('internacional', 'Internacional'),
    ],
    string='Type Event Boat',
    required=False,
    default=False,
    copy=False,
    tracking=True,
  )
  order_ids = fields.One2many(
    string='Sale Order',
    comodel_name='sale.order',
    inverse_name='operation_request_id',
  )
  sale_order_count = fields.Integer(
    string='Sale Order Count', compute='_compute_sale_order_count'
  )
  invoice_count = fields.Integer(
    string='Account Move Count', compute='_compute_account_move_count'
  )
  messege_war_doc = fields.Boolean(string='Messege')
  supplier_id = fields.Many2one('res.partner', string='Supplier', tracking=True)
  is_managemente_date = fields.Boolean(
    string='It is an administration that requires an expiration date',
    default=False,
  )
  ek_service_request_line_ids = fields.One2many(
    'ek.product.order.shipp', 'ek_operation_request_id', string='Request'
  )
  product_ids = fields.One2many(
    'ek.product.purchase.ship', 'ek_operation_request_id', string='Products'
  )
  has_crew = fields.Boolean(related='type_id.has_crew')
  has_service_maneuver = fields.Boolean(related='type_id.has_service_maneuver')
  has_data_requeried_n_i = fields.Boolean(
    related='type_id.has_data_requeried_n_i'
  )
  has_operator = fields.Boolean(related='type_id.has_operator')
  has_data_zarpe = fields.Boolean(related='type_id.has_data_zarpe')
  has_data_cargo = fields.Boolean(related='type_id.has_data_cargo')
  amount = fields.Float('Total', compute='_compute_amount_line')

  is_analytic_account = fields.Boolean(
    related='type_id.is_analytic_account'
  )  # eliminar
  is_agent_naviero = fields.Boolean(related='type_id.is_agent_naviero')
  is_change_of_crew = fields.Boolean(string='Is Change of crew')
  state_boats = fields.Selection(related='ek_ship_registration_id.state_boats')
  state_travel = fields.Selection(related='journey_crew_id.state')

  @api.onchange('ek_ship_registration_id')
  def _onchange_ship_registration_clear_journey(self):
    """Auto-fill customer and clear dependent fields when ship changes"""

    if self.ek_ship_registration_id:
      # Auto-fill customer based on ship's business name
      if self.ek_ship_registration_id.bussiness_name_id:
        self.res_partner_id = self.ek_ship_registration_id.bussiness_name_id

      else:
        # Clear customer if ship has no business name assigned

        self.res_partner_id = False

      # IMPORTANTE: Solo limpiar el viaje si NO viene del contexto
      # Esto evita que se limpie cuando se pre-llena automáticamente
      if not self.env.context.get('default_journey_crew_id'):
        # Clear dependent fields when ship changes so user needs to select valid ones
        self.journey_crew_id = False

        # Buscar el último viaje del barco seleccionado que NO esté finalizado
        last_journey = self.env['ek.boats.information'].search(
          [
            ('ship_name_id', '=', self.ek_ship_registration_id.id),
            ('state', 'in', ['draft', 'process']),
          ],
          order='create_date desc',
          limit=1,
        )

        if last_journey:
          self.journey_crew_id = last_journey.id
        else:
          # Verificar si existen viajes pero todos están finalizados
          any_journey = self.env['ek.boats.information'].search(
            [('ship_name_id', '=', self.ek_ship_registration_id.id)],
            limit=1,
          )

          if any_journey:
            # Hay viajes pero todos están finalizados
            return {
              'warning': {
                'title': _('Advertencia'),
                'message': _(
                  'Todos los viajes del barco "%s" están finalizados. '
                  'Por favor, cree un nuevo viaje o contacte al administrador.'
                )
                % self.ek_ship_registration_id.name,
              }
            }
    else:
      # If ship is cleared, also clear customer and dependent fields

      self.res_partner_id = False
      self.journey_crew_id = False

      # Retornar el valor para forzar que el frontend lo reconozca como modificado
      return {'value': {'res_partner_id': False, 'journey_crew_id': False}}

  # @api.onchange('res_partner_id')
  # def _onchange_customer_clear_ship_journey(self):
  #   """
  #   DISABLED: Customer field is now readonly and auto-populated from ship.
  #   Validate customer-ship consistency when customer is manually changed
  #   """
  #   # This method is disabled because res_partner_id is now readonly
  #   # and auto-populated from the selected ship's business_name_id
  #   pass

  signature = fields.Image(
    'Signature',
    help='Signature',
    copy=False,
    attachment=True,
  )
  signed_document = fields.Boolean(
    string='Signed Document',
    copy=False,
    default=False,
    compute='_compute_signed_document',
  )
  signed_document_false = fields.Boolean(
    string='Signed Document ',
    copy=False,
    default=False,
    compute='_compute_signed_document',
  )

  def delete_signature_requets(self):
    for rec in self:
      rec.signature = False

  @api.depends('signature')
  def _compute_signed_document(self):
    for rec in self:
      rec.signed_document = True if rec.signature else False
      rec.signed_document_false = False if rec.signature else True

  inform_data_capman = fields.Char(
    string='Hierarchy and Specialty/Ship and Registration No.:', copy=False
  )

  is_obligator_document = fields.Boolean(string='Is Obligator Document')
  crew_id = fields.Many2many(
    'res.partner',
    'operation_request_crew_rel',
    'operation_request_id',
    string='Crew',
  )

  ###########DOCUEMENTOS############
  document_name = fields.Char(string='Name Document')
  date_start = fields.Date(
    string='Date Start ', tracking=True, default=fields.Date.context_today
  )
  manual_day = fields.Boolean(
    string='Escribe día manualmente',
    default=False,
    help='Oculta el día de la fecha date_start para ser escrito manualmente por el usuario',
  )
  date_end = fields.Date(string='Date End', tracking=True)
  pdf_file = fields.Binary(string='attachments')
  file_name = fields.Char(string='File Name')
  type_binary = fields.Selection(
    [('application/pdf', 'PDF'), ('image/jpeg', 'JPG')],
    string='Type Binary',
  )

  attachment_id = fields.Many2one('ir.attachment', string=' Attachments')
  is_service_request = fields.Boolean(related='type_id.is_service_request')

  is_capital_port = fields.Boolean(related='type_id.is_capital_port')
  is_service_refunf = fields.Boolean(
    related='type_id.is_service_refunf'
  )  # reembolso
  is_request_assignable = fields.Boolean(
    related='type_id.is_request_assignable'
  )  # es si la solicitud lo puede asignar el admin

  ek_boat_location_id = fields.Many2one('ek.boat.location', string='Maneuver')
  is_separate = fields.Boolean(related='type_id.is_separate')
  report_tr_n_n = fields.Char(string='Report T.R.B. and T.R.N.')

  reason_arrival_ids = fields.Many2many(
    'reason.arrival',
    'operation_request_reason_arrival_rel',
    'operation_request_id',
    string='Reasons Arrival',
  )
  ###definir el tipo de reporte que se realizo#######

  type_document_access = fields.Selection(
    related='type_id.type_document_access'
  )

  crew_pay = fields.Boolean(related='type_id.crew_pay')
  send_to_sign_report = fields.Boolean(related='type_id.send_to_sign_report')

  #################ENVIO DE CORREO#############
  ek_group_mail_template_id = fields.Many2one(
    'ek.group.mail.template', string='Group Email Template'
  )
  send_email = fields.Boolean(related='type_id.send_email')
  # comision
  commission = fields.Float(related='type_id.commission')
  has_commission = fields.Boolean(related='type_id.has_commission')
  #####################reporte de operaciones  Solicitud DE ATRAQUE Y FONDEO####################
  # datos de servicios o Maniobras
  # calculo de dias y hora
  day_hour_eta = fields.Char(
    string='Time Required', compute='_compute_day_hour_eta'
  )

  eta_maneuvers = fields.Datetime(string='E.T.A.', tracking=True)
  etd_maneuvers = fields.Datetime(string='E.T.D.', tracking=True)

  mrn_imp = fields.Char(string='MRN IMP', tracking=True)  # etd - eta = dias
  mrn_exp = fields.Char(string='MRN EXP', tracking=True)

  has_embark = fields.Boolean(string='Embark', tracking=True)
  day_embark = fields.Integer(string='Day Embark', tracking=True)

  has_discharge = fields.Boolean(string='Discharge', tracking=True)
  day_discharge = fields.Integer(string='Day Discharge', tracking=True)

  has_maintenance = fields.Boolean(string='Maintenance', tracking=True)
  day_maintenance = fields.Integer(string='Day maintenance', tracking=True)

  has_provision = fields.Boolean(string='Provision', tracking=True)
  day_provision = fields.Integer(string='Day provision', tracking=True)

  has_fondeo = fields.Boolean(string='Fondeo')
  day_fondeo = fields.Integer(string='Day fondeo', tracking=True)

  others_services = fields.Boolean(string='Others.', tracking=True)
  day_others = fields.Integer(string='Day others ', tracking=True)

  #####Operadora########
  cargo_operator1 = fields.Many2many(
    'res.partner',
    'cargo_operator1_rel',
    'operation_request_id',
    string='Cargo Operator',
  )
  cargo_operator2 = fields.Many2many(
    'res.partner',
    'cargo_operator2_rel',
    'operation_request_id',
    string=' ',
  )

  validity_and_physical_security = fields.Many2many(
    'res.partner',
    'validity_and_physical_security_rel',
    'operation_request_id',
    string='Validity and Physical Security',
    tracking=True,
  )

  solid_waste_management = fields.Many2many(
    'res.partner',
    'solid_waste_management_rel',
    'operation_request_id',
    string='Solid and Liquid Waste Management',
    tracking=True,
  )
  fumigation = fields.Many2many(
    'res.partner',
    'fumigation_rel',
    'operation_request_id',
    string='Fumigation',
    tracking=True,
  )
  water_supply = fields.Many2many(
    'res.partner',
    'water_supply_rel',
    'operation_request_id',
    string='Water Supply',
    tracking=True,
  )
  approve_fuel_per_tank_car = fields.Many2many(
    'res.partner',
    'approve_fuel_per_tank_car_rel',
    'operation_request_id',
    string='Approve Fuel Per Tank Car',
  )
  Approve_Provisions = fields.Many2many(
    'res.partner',
    'approve_Provisions_rel',
    'operation_request_id',
    string='Approve of Provisions',
  )

  provision_equipment_spare_parts = fields.Many2many(
    'res.partner',
    'provision_equipment_spare_parts_rel',
    'operation_request_id',
    string='Provision of Equipment and Spare Parts',
  )
  supply_provision = fields.Many2many(
    'res.partner',
    'supply_provision_rel',
    'operation_request_id',
    string='supply provision',
  )
  equipment_inspection = fields.Many2many(
    'res.partner',
    'equipment_inspection_rel',
    'operation_request_id',
    string='Equipment Inspection',
  )
  recharge_against_fire = fields.Many2many(
    'res.partner',
    'recharge_against_fire_rel',
    'operation_request_id',
    string='Inst. and Maintain of Electronic Equipment',
  )
  recharge_maintain_against_fire = fields.Many2many(
    'res.partner',
    'recharge_maintain_against_fire_rel',
    'operation_request_id',
    string='recharge and maintain eq. against fire',
  )
  repair_maintain_nets_fishing = fields.Many2many(
    'res.partner',
    'repair_maintain_nets_fishing_rel',
    'operation_request_id',
    string='repair and maintain of nets and fishing',
  )
  life_raft_service = fields.Many2many(
    'res.partner',
    'life_raft_service_rel',
    'operation_request_id',
    string='life raft service',
  )
  salt = fields.Many2many('res.partner', string='salt')
  others_operators = fields.Many2many(
    'res.partner',
    'others_operators_rel',
    'operation_request_id',
    string='others:',
  )

  # datos requerido para Carga Nacional e Internacion
  ek_requerid_burden_n_i_ids = fields.One2many(
    'ek.requerid.burden.nationanl.international',
    'ek_operation_request_id',
    string='Requerid Burden',
    copy=True,
  )

  ##############################aviso de zarpe###########################
  # datos del zarpe
  datatime_request_practical = fields.Datetime(
    string='Practical Request Time', tracking=True
  )
  datatime_real_dear = fields.Datetime(
    string='Estimated Departure Date and Time', tracking=True
  )
  name_capital_practico = fields.Many2one(
    'res.partner', string='Name Practical', tracking=True
  )
  # datos de carga
  mrn_exit = fields.Many2one(
    'ek.bl.manifest.record', string='MRN Exit (Export Manifest)', tracking=True
  )
  mrn_arribal = fields.Many2one(
    'ek.bl.manifest.record',
    string='MRN Arribal(Import Manifest)',
    tracking=True,
  )
  code_operator_ship = fields.Char(string='Code Operator Ship', tracking=True)
  # acceso pourtario
  ek_acces_port_table_float_ids = fields.One2many(
    'ek.acces.port.table.float',
    'operation_request_id',
    string='Acces Port Table Float',
  )
  has_pier_one = fields.Boolean(string='Pier One', tracking=True)
  has_pier_two = fields.Boolean(string='Pier Two', tracking=True)
  has_yard = fields.Boolean(string='Yard', tracking=True)
  has_ship = fields.Boolean(string='Ship', tracking=True)

  has_marginal_dock = fields.Boolean(string='Marginal Dock', tracking=True)

  is_marginal_dock_setting = fields.Boolean(
    related='type_id.is_marginal_dock_setting'
  )
  has_access_port = fields.Boolean(related='type_id.has_access_port')
  char_name_buquer = fields.Char(string='Name Ship', tracking=True)
  reason_report = fields.Char(string='Reason', tracking=True)
  permanence_period = fields.Date(string='Permanence Period', tracking=True)
  end_period = fields.Char(string='End Period', tracking=True)
  estimated_actual_date = fields.Date(
    string='Estimated Actual Date', tracking=True
  )
  duration = fields.Integer(
    string='Duration (days)', compute='_compute_duration', store=True
  )
  blue_tip_dock = fields.Boolean(string='Blue Tip Dock', tracking=True)
  maintenance_area_report = fields.Boolean(
    string='Maintenance Area', tracking=True
  )

  has_availability = fields.Boolean(string='Availability', tracking=True)
  has_extension = fields.Boolean(string='Extension', tracking=True)
  ek_assignment_number_rp = fields.Char(string='NO. Assignment', tracking=True)

  ek_res_partner_id_certificate_id = fields.Many2one(
    'res.partner', string='Razon Social', tracking=True
  )
  ek_res_partner_id_certificate_ids = fields.Many2many(
    'res.partner',
    string='m2m filter partner',
    compute='_filtered_domain_partner',
  )
  responsible_people_id = fields.Many2one(
    'res.partner',
    string='Responsible People',
    domain="[('id', 'in', ek_res_partner_id_certificate_ids)]",
    tracking=True,
  )
  financial_chief = fields.Many2one(
    'res.partner',
    string='Financial Chief',
    domain="[('id', 'in', ek_res_partner_id_certificate_ids)]",
    tracking=True,
  )
  is_dock_space_expansion = fields.Boolean(
    related='type_id.is_dock_space_expansion'
  )

  ek_authorized_pourtario_operators_table_ids = fields.One2many(
    'ek.authorized.pourtario.operators.table',
    'operation_request_id',
    string='Authorized pourtario operators table',
  )

  # formato muelles , dias, , tripulante y arribo
  authorization_code = fields.Char(string='# Authorization', tracking=True)
  document_number_code = fields.Char(string='Oficio N°', tracking=True)

  ek_boat_location_id = fields.Many2one(
    'ek.boat.location', string='Port of Origin', tracking=True
  )
  ek_res_world_seaport_id_origin = fields.Many2one(
    'ek.res.world.seaports', string='Port of Arrival', tracking=True
  )
  ek_res_world_seaport_id_destination = fields.Many2one(
    'ek.res.world.seaports', string='Port of Destination', tracking=True
  )

  calculation_day_or_hours = fields.Boolean(
    related='type_id.calculation_day_or_hours'
  )
  search_by_authorization = fields.Boolean(
    related='type_id.search_by_authorization'
  )
  processing_status = fields.Selection(
    [
      ('developing', 'En Proceso'),
      ('done', 'Realizado'),
      ('cancel', 'Cancelado'),
    ],
    string='Processing Status',
    tracking=True,
    copy=False,
  )

  ek_management_document_ids = fields.One2many(
    'ek.management.document',
    'ek_operation_request_id',
    string='Management Documents',
  )

  processo_notification = fields.Boolean(
    string='Process Notification', tracking=True
  )

  end_request_datetime = fields.Datetime(
    string='End Request Datetime', tracking=True, copy=False
  )
  days_time_request_results = fields.Float(
    string='Days Time Request Results', tracking=True
  )

  ek_user_groups_reminder_ids = fields.Many2one(
    'ek.user.groups.reminder', string='User Groups Reminder'
  )

  has_notification = fields.Boolean(related='type_id.has_notification')
  has_documents_notification = fields.Boolean(
    related='type_id.has_documents_notification'
  )

  # Campo de notificaciones personalizadas por solicitud
  notification_ids = fields.One2many(
    'ek.operation.request.notification',
    'request_id',
    string='Notificaciones',
    help='Configuración de notificaciones específica para esta solicitud',
  )
  has_report_capitana = fields.Boolean(related='type_id.has_report_capitana')
  ek_service_request_report_line_ids = fields.Many2many(
    'ek.service.request.line',
    'ek_service_request_line_rel',
    'ek_operation_request_id',
    string='Service Request Lines',
  )
  ship_passenger = fields.Many2many(
    'res.partner',
    'ship_passenger_rel',
    'ek_operation_request_id',
    string='Ship Passenger',
    domain="[('is_crew', '=', True)]",
  )
  has_passanger = fields.Boolean(related='type_id.has_passanger')
  fuel = fields.Float(string='Fuel', tracking=True)
  fuel_uom = fields.Many2one('uom.uom', string='Fuel UOM', tracking=True)
  gasoline = fields.Float(string='Gasoline ', tracking=True)
  gasoline_uom = fields.Many2one(
    'uom.uom', string='Gasoline UOM', tracking=True
  )
  water = fields.Float(string='Water', tracking=True)
  water_uom = fields.Many2one('uom.uom', string='Water UOM', tracking=True)
  ek_table_fuel_ids = fields.One2many(
    'ek.table.fuel', 'ek_operation_request_id', string='Table Fuel'
  )
  ek_table_gasoline_ids = fields.One2many(
    'ek.table.gasoline', 'ek_operation_request_id', string='Table Gasoline'
  )
  ek_table_water_ids = fields.One2many(
    'ek.table.water', 'ek_operation_request_id', string='Table Water'
  )

  total_fuel = fields.Float('Total Fuel', compute='_computed_total_table')
  total_gasoline = fields.Float(
    'Total gasoline', compute='_computed_total_table'
  )
  total_water = fields.Float('Total water', compute='_computed_total_table')

  ################################################################
  #########################ADUANA#################################
  # condiciones
  ###campos
  agent_customs_id = fields.Many2one('res.partner', string='Agent Customs')
  operator_id = fields.Many2one('res.partner', string='Operator')
  number_container = fields.Char(string='Number Container')
  number_bl = fields.Char(string='Number BL')
  number_mrn = fields.Char(string='Number MRN')
  number_transfer = fields.Char(string='Number Transfer')
  number_awb = fields.Char(string='Number AWB')
  shipping_lines = fields.Many2one('res.partner', string='Shipping Lines')
  imports_res_partner = fields.Many2one('res.partner', string='Importer')

  type_container_id = fields.Many2one(
    'ek.type.container', string='Type Container'
  )
  date_return_container = fields.Datetime(string='Date Return Container')
  detail_supplies_spare_parts = fields.Text(
    string='Detail Supplies or Spare Parts'
  )
  number_dai = fields.Char(string='Number DAI')
  number_dae = fields.Char(string='Number DAE')
  number_ifi_nfi = fields.Char(string='Number IFI/NFI')
  number_invoice = fields.Char(string='Number Invoice')

  driver_id = fields.Many2one('res.partner', string='Driver')
  placa = fields.Char(string='Placa')
  operation_custom = fields.Char(string='Operation')
  merchatin_detail = fields.Text(string='Merchant Detail')

  insurance_company_id = fields.Many2one(
    'res.partner', string='Insurance Company'
  )
  insurance_id = fields.Many2one('res.partner', string='Insurance')
  insured_object = fields.Text(string='Insured Object')
  warranty_number = fields.Char(string='Warranty Number')
  insurance_amount = fields.Float(string='Insurance Amount')
  insurance_prime = fields.Float(string='Insurance Prime')

  date_max_reports = fields.Datetime(string='Date Max Reports')
  date_arrival = fields.Datetime(string='Date Arrival')
  date_transfer = fields.Datetime(string='Date Transfer')
  for_transhipment_to = fields.Char(string='For Transshipment To')
  ek_regimen_table_id = fields.Many2one('ek.regimen.table', string='Regimen')
  assigned_regimen_70 = fields.Boolean(
    related='ek_ship_registration_id.assigned_regimen_70'
  )

  # 08/07
  has_detail_items = fields.Boolean(related='type_id.has_detail_items')
  ek_manifest_record_id = fields.Many2one(
    'ek.bl.manifest.record',
    string='MRN',
    copy=True,
    domain="[('ek_ship_registration_id', '=', ek_ship_registration_id), ('journey_crew_id', '=', journey_crew_id)]",
  )
  date_emition_request = fields.Date(
    string='Date emition request', copy=True, default=fields.Date.context_today
  )
  date_end_request = fields.Datetime(string='End Date Request', copy=True)

  ek_operation_request_id = fields.Many2one(
    'ek.operation.request',
    string='Related to',
    copy=False,
  )
  parent_id = fields.Many2one(
    'ek.operation.request',
    string='Linked to',
    copy=False,
  )

  informe_work = fields.Html(
    string='informe Work',
  )

  child_ids = fields.One2many(
    'ek.operation.request', 'parent_id', string='Related Request', copy=False
  )

  count_childs = fields.Integer(
    'Count Childs Request', compute='_compute_count_childs'
  )
  consignee_res_partner_id = fields.Many2one(
    'res.partner', string='Consignee', copy=True
  )
  notyfy_party_res_partner_id = fields.Many2one(
    'res.partner', string='Notify Party', copy=True
  )
  port_of_discharge = fields.Many2one(
    'ek.res.world.seaports', string='Port of Discharge', copy=True
  )

  # tabla
  freight_regimen = fields.Float(string='Freight', copy=True)
  lumps = fields.Integer(string='Lumps', copy=True)
  gross_weight = fields.Float(
    string='Gross Weight',
    compute='product_depends_packages_goods',
    default=0,
    copy=True,
    store=True,
  )
  net_weight = fields.Float(string='Net Weight', copy=True)
  ek_produc_packages_goods_ids = fields.One2many(
    'ek.product.packagens.goods',
    'ek_operation_request_id',
    string='Product Packagens Goods',
    copy=True,
  )
  das = fields.Char(string='DAS', copy=True)

  product_weight_in_lbs = fields.Selection(
    [
      ('0', 'kg'),
      ('1', 'lb'),
    ],
    'Weight unit of measure',
    default='0',
    copy=True,
  )

  # 09/07
  has_mrn_number = fields.Boolean(related='type_id.has_mrn_number')
  show_button_copy = fields.Boolean(related='type_id.show_button_copy')
  # MOstrar campos dinamicos
  display_dinamic_field = fields.Json(
    compute='_compute_display_dinamic_field',
    readonly=True,
    store=True,
    copy=True,
  )
  date_end = fields.Datetime(string='Date End')
  not_controlling_weight = fields.Boolean(
    related='type_id.not_controlling_weight'
  )

  type_dae_das = fields.Selection(
    [
      ('das', 'DAS'),
      ('dae', 'DAE'),
    ],
    string='Type DAE/DAS',
    copy=True,
    default='das',
  )

  purchase_count = fields.Integer(
    compute='_compute_purchase_count', string='Purchase Order Count'
  )

  fold = fields.Boolean(related='stage_id.fold')
  confirm_stage = fields.Boolean(related='stage_id.confirm_stage')
  canceled_stage = fields.Boolean(related='stage_id.canceled_stage')
  next_stage_fold = fields.Boolean(
    string='Next Stage is Final',
    compute='_compute_next_stage_fold',
    help='True if the next stage has fold=True (final stage)',
  )

  available_notification_user_ids = fields.Many2many(
    'res.users',
    string='Available Users for Notifications',
    compute='_compute_available_notification_users',
    help='Users that are not already in the notification list',
  )
  shipper_res_partner_id = fields.Many2one('res.partner', string='Shipper ')

  shipping_trade_numbers_ids = fields.One2many(
    'ek.shipping.trade.numbers',
    'request_id',
    string='Shipping Trade Numbers',
    copy=False,
    readonly=False,
  )

  has_trade_numeber = fields.Boolean(related='type_id.has_trade_numeber')

  stage_service_ids = fields.Many2many(related='type_id.stage_service_ids')
  stage_refund_ids = fields.Many2many(related='type_id.stage_refund_ids')
  readonly_mass = fields.Boolean(related='stage_id.readonly_mass')
  has_credentials = fields.Selection(related='type_id.has_credentials')
  table_aditional = fields.Boolean(related='type_id.table_aditional')
  ek_table_aditional_self_ids = fields.One2many(
    'ek.table.aditional.self',
    'operation_request_id',
    string='Table Aditional Self',
    copy=False,
    readonly=True,
  )
  sequence_number_next_ek = fields.Char()

  # Documento entregado reporte capitania
  title = fields.Char(string='Title')
  title_copy = fields.Boolean(string='Title Copy')
  title_original = fields.Boolean(string='Title Original')
  curse_01 = fields.Char(string='Curse 01')
  curse_01_copy = fields.Boolean(string='Curse Copy')
  curse_01_original = fields.Boolean(string='Curse Original')
  curse_02 = fields.Char(string='Curse 02')
  curse_02_copy = fields.Boolean(string='Curse 02 Copy')
  curse_02_original = fields.Boolean(string='Curse 02 Original')
  curse_03 = fields.Char(string='Curse 03')
  curse_03_copy = fields.Boolean(string='Curse 03 Copy')
  curse_03_original = fields.Boolean(string='Curse 03 Original')
  curse_04 = fields.Char(string='Curse 04')
  curse_04_copy = fields.Boolean(string='Curse 04 Copy')
  curse_04_original = fields.Boolean(string='Curse 04 Original')
  curse_05 = fields.Char(string='Curse 05 o mas')
  curse_05_copy = fields.Boolean(string='Curse 05 Copy')
  curse_05_original = fields.Boolean(string='Curse 05 Original')
  certificate_medical = fields.Char(string='Certificate Medical')
  certificate_medical_copy = fields.Boolean(string='Certificate Medical Copy')
  certificate_medical_original = fields.Boolean(
    string='Certificate Medical Original'
  )
  file_medical = fields.Char(string='File Medical')
  file_medical_copy = fields.Boolean(string='File Medical Copy')
  file_medical_original = fields.Boolean(string='File Medical Original')
  seamn_book = fields.Char(string='Seamn Book')
  seamn_book_copy = fields.Boolean(string='Seamn Book Copy')
  seamn_book_original = fields.Boolean(string='Seamn Book Original')
  credential_delivery = fields.Char(string='Credential Delivery')
  credential_delivery_copy = fields.Boolean(string='Credential Delivery Copy')
  credential_delivery_original = fields.Boolean(
    string='Credential Delivery Original'
  )
  complaint_delivery = fields.Char(string='Complaint Delivery')
  complaint_delivery_copy = fields.Boolean(string='Complaint Delivery Copy')
  complaint_delivery_original = fields.Boolean(
    string='Complaint Delivery Original'
  )
  other_document_01 = fields.Char(string='Other Document 01')
  other_document_01_copy = fields.Boolean(string='Other Document 01 Copy')
  other_document_01_original = fields.Boolean(
    string='Other Document 01 Original'
  )
  other_document_02 = fields.Char(string='Other Document 02')
  other_document_02_copy = fields.Boolean(string='Other Document 02 Copy')
  other_document_02_original = fields.Boolean(
    string='Other Document 02 Original'
  )
  other_document_03 = fields.Char(string='Other Document 03')
  other_document_03_copy = fields.Boolean(string='Other Document 03 Copy')
  other_document_03_original = fields.Boolean(
    string='Other Document 03 Original'
  )

  ########### calculo de horas   AMPLIACION O RECUCCION ###################
  type_calcule = fields.Selection(
    [
      ('1', 'Principal'),
      ('2', 'Extension or Reduction'),
    ]
  )
  start_date_calculate = fields.Datetime(string='Start Date', tracking=True)
  end_date_calculate = fields.Datetime(string='End Date', tracking=True)
  next_extended_date = fields.Datetime(
    string='Next Extended Date', tracking=True
  )

  calcule_days = fields.Integer(
    string='Days',
    compute='_compute_duration_calculate',
  )
  calcule_hours = fields.Float(
    string='Hours Principal',
    compute='_compute_duration_calculate',
  )  # principal
  extended_hours = fields.Float(
    string='Hours Extended or Reduced', tracking=True
  )  # hora extendida
  total_hours_acumulate = fields.Float(
    string='Total Extended Hours'
  )  # Resultado de ampliacion

  total_hours_used = fields.Float(
    string='Total Hours used or Reduced', tracking=True
  )
  need_to_extend_hours = fields.Boolean(string='Need To Extend Hours')

  need_extend_hours_text = fields.Text(
    string='Need Extend Hours',
    default='',
    readonly=True,
    compute='calcule_principal',
  )

  contant_text_next = fields.Text(
    string='Contant Text Next',
    default='',
    readonly=True,
    compute='field_date_text_union',
  )

  text_self_calculate = fields.Text(
    string='Text Self Calculate',
    default='',
    readonly=True,
  )
  number_booklet = fields.Char(string='Booklet Number')
  boat_registration = fields.Char(string='Boat Registration')
  vat = fields.Char(string='CC')

  ek_table_reimbursement_expenses_ids = fields.One2many(
    'ek.table.reimbursement.expenses',
    'ek_operation_request_id',
    string='Table Reimbursement Expenses',
    copy=True,
  )
  ek_product_reimbursement_expenses_ids = fields.Many2one(
    related='type_id.ek_product_reimbursement_expenses_ids'
  )
  requesting_contact_id = fields.Many2one(
    'res.partner', string='Requesting Contact'
  )
  has_signature = fields.Boolean(related='type_id.has_signature')
  firm_user_name = fields.Many2one(
    'res.users', compute='_compute_firm_user_name'
  )

  has_delivery_reception = fields.Boolean(
    related='type_id.has_delivery_reception'
  )

  ##acta recepcion
  zarpe_reception = fields.Char(string='Zarpe Reception')
  zarpe_entrega = fields.Char(string='Zarpe Entrega')
  matricula_reception = fields.Char(string='Matricula Reception')
  matricula_entrega = fields.Char(string='Matricula Entrega')
  guia_combustible = fields.Char(string='Guia Combustible reception')
  guia_combustible_entrega = fields.Char(string='Guia Combustible entrega')
  bitacora_navegation = fields.Char(string='Bitacora reception')
  bitacora_navegation_entrega = fields.Char(string='Bitacora entrega')
  bitacora_pesca_reception = fields.Char(string='Bitacora Pesca reception')
  bitacora_pesca_entrega = fields.Char(string='Bitacora Pesca entrega')

  seamans_book_reception = fields.Char(string='Seamans Book reception')
  seamans_book_entrega = fields.Char(string='Seamans Book entrega')
  permiso_provisional_reception = fields.Char(
    string='Permiso Provisional reception'
  )
  permiso_provisional_entrega = fields.Char(
    string='Permiso Provisional entrega'
  )
  passport_reception = fields.Char(string='Passport reception')
  passport_entrega = fields.Char(string='Passport entrega')
  cedula_reception = fields.Char(string='Cedula reception')
  cedula_entrega = fields.Char(string='Cedula entrega')
  otros_reception = fields.Char(string='Otros reception')
  otros_entrega = fields.Char(string='Otros entrega')

  ## Campos para Acta de Entrega/Recepción con secuencia
  delivery_report_code = fields.Char(string='Código de Reporte de Entrega')
  delivery_report_has_sequence = fields.Boolean(
    string='Tiene Secuencia de Trade Number',
    default=False,
    readonly=True
  )
  delivery_report_sequence_code = fields.Char(
    string='Código de Secuencia de Reporte',
    compute='_compute_delivery_report_sequence_code',
    store=True,
    readonly=True
  )
  delivery_report_trade_number_id = fields.Many2one(
    'ek.shipping.trade.numbers',
    string='Trade Number de Reporte de Entrega',
    readonly=True,
    copy=False
  )
  delivery_report_comments = fields.Text(string='Comentarios del Reporte de Entrega')
  can_delete_delivery_sequence = fields.Boolean(
    string='Puede Eliminar Secuencia',
    compute='_compute_can_delete_delivery_sequence',
    help='Indica si se puede eliminar la secuencia (solo si es la última)'
  )

  ##
  @api.depends('delivery_report_trade_number_id', 'shipping_trade_numbers_ids.create_date')
  def _compute_can_delete_delivery_sequence(self):
    """
    Calcula si se puede eliminar la secuencia de delivery report.
    Solo se puede eliminar si es la última secuencia creada para esta solicitud.
    """
    for rec in self:
      if not rec.delivery_report_trade_number_id:
        rec.can_delete_delivery_sequence = False
      else:
        # Obtener todas las secuencias ordenadas por fecha de creación
        all_trade_numbers = rec.shipping_trade_numbers_ids.sorted('create_date')
        current_trade_number = rec.delivery_report_trade_number_id
        
        # Verificar si la secuencia actual es la última
        if all_trade_numbers and all_trade_numbers[-1].id == current_trade_number.id:
          rec.can_delete_delivery_sequence = True
        else:
          rec.can_delete_delivery_sequence = False

  @api.depends('user_id', 'firm_user_name')
  def _compute_firm_user_name(self):
    for record in self:
      record.firm_user_name = self.env.uid

  @api.depends('delivery_report_has_sequence', 'delivery_report_code', 'delivery_report_trade_number_id.name')
  def _compute_delivery_report_sequence_code(self):
    """
    Calcula el código de secuencia del reporte de entrega.
    - Si delivery_report_has_sequence es False: usa delivery_report_code (puede estar vacío)
    - Si delivery_report_has_sequence es True: usa la secuencia generada de ek.shipping.trade.numbers
    """
    for rec in self:
      if rec.delivery_report_has_sequence and rec.delivery_report_trade_number_id:
        rec.delivery_report_sequence_code = rec.delivery_report_trade_number_id.name
      else:
        rec.delivery_report_sequence_code = rec.delivery_report_code or ''

  def action_get_delivery_report_sequence(self):
    """
    Acción del botón para obtener una secuencia de trade number.
    Genera un registro en ek.shipping.trade.numbers y actualiza los campos relacionados.
    """
    self.ensure_one()
    if self.delivery_report_trade_number_id:
      raise UserError(_('Ya existe una secuencia generada para este reporte de entrega.'))
    
    if not self.company_id.trade_sequence_id:
      raise UserError(_('Please configure the sequence in the company'))

    trade_number = self.env['ek.shipping.trade.numbers'].create({
      'request_id': self.id,
      'note': _('Trade Number generado para Acta de Entrega/Recepción'),
      'ship_registration_id': self.ek_ship_registration_id.id if self.ek_ship_registration_id else False,
      'boats_information_id': self.journey_crew_id.id if self.journey_crew_id else False,
      'type_id': self.type_id.id if self.type_id else False,
      'stage_id': self.stage_id.id if self.stage_id else False,
      'user_id': self.env.user.id,
      'date': fields.Date.context_today(self),
      'name': self.company_id.trade_sequence_id.next_by_id(),
    })
    
    self.write({
      'delivery_report_trade_number_id': trade_number.id,
      'delivery_report_has_sequence': True,
    })
    
    # Forzar recálculo de campos computed
    self._compute_delivery_report_sequence_code()
    self._compute_can_delete_delivery_sequence()
    
    # Leer los valores actualizados
    self.invalidate_recordset(['delivery_report_sequence_code', 'can_delete_delivery_sequence'])
    values = self.read(['delivery_report_sequence_code', 'can_delete_delivery_sequence', 'delivery_report_has_sequence', 'delivery_report_code'])[0]
    
    # Retornar acción que recarga la vista del formulario (similar a nsk_pdf_manager)
    return {
      'type': 'ir.actions.client',
      'tag': 'refresh_delivery_fields',
      'params': {
        'message': _('Se ha generado la secuencia: %s') % trade_number.name,
        'parent_model': self._name,
        'parent_id': self.id,
      }
    }

  def action_delete_delivery_report_sequence(self):
    """
    Acción del botón para eliminar la secuencia de trade number.
    Solo permite eliminar si no hay una secuencia posterior en ek.shipping.trade.numbers
    para esta solicitud.
    """
    self.ensure_one()
    
    if not self.delivery_report_trade_number_id:
      raise UserError(_('No hay secuencia para eliminar.'))
    
    # Verificar si hay secuencias posteriores para esta solicitud
    # Buscar todas las secuencias de esta solicitud ordenadas por fecha/ID
    all_trade_numbers = self.shipping_trade_numbers_ids.sorted('create_date')
    current_trade_number = self.delivery_report_trade_number_id
    
    # Encontrar la posición de la secuencia actual
    current_index = None
    for idx, tn in enumerate(all_trade_numbers):
      if tn.id == current_trade_number.id:
        current_index = idx
        break
    
    # Si hay una secuencia posterior, no permitir eliminar
    if current_index is not None and current_index < len(all_trade_numbers) - 1:
      next_trade_number = all_trade_numbers[current_index + 1]
      raise UserError(
        _('No se puede eliminar esta secuencia porque existe una secuencia posterior '
          '(Secuencia: %s, creada el %s). Solo se puede eliminar la última secuencia.')
        % (next_trade_number.name, next_trade_number.create_date.strftime('%d/%m/%Y %H:%M'))
      )
    
    # Eliminar la secuencia y restaurar los campos
    sequence_name = current_trade_number.name
    
    # Intentar reutilizar el número de secuencia si es posible
    # Solo si es la última secuencia generada (ya validado arriba)
    try:
      import re
      import logging
      _logger = logging.getLogger(__name__)
      
      if self.company_id.trade_sequence_id:
        # Extraer el número de la secuencia eliminada (ej: NSK-2025-0016 -> 16)
        match = re.search(r'(\d+)$', sequence_name)
        if match:
          deleted_sequence_number = int(match.group(1))
          
          # Buscar todas las secuencias existentes de la compañía (excluyendo la que vamos a eliminar)
          all_company_trade_numbers = self.env['ek.shipping.trade.numbers'].search([
            ('company_id', '=', self.company_id.id),
            ('name', '!=', sequence_name),
          ])
          
          # Encontrar el número más alto de todas las secuencias existentes de la compañía
          max_existing_number = 0
          for tn in all_company_trade_numbers:
            tn_match = re.search(r'(\d+)$', tn.name)
            if tn_match:
              tn_number = int(tn_match.group(1))
              if tn_number > max_existing_number:
                max_existing_number = tn_number
          
          # Obtener el número actual de la secuencia ANTES de eliminarla
          current_next_before = self.company_id.trade_sequence_id.number_next
          
          _logger.info('DEBUG_DEVELOPMENT: Inicio reutilización. Secuencia eliminada: %s, Máximo existente: %s, number_next antes: %s', 
                      deleted_sequence_number, max_existing_number, current_next_before)
          
          # IMPORTANTE: En Odoo, next_by_id() funciona así:
          # 1. Lee number_next (ej: 1)
          # 2. Formatea el número con el padding: str(1).zfill(4) = "0001"
          # 3. Retorna el valor formateado: "NSK-2025-0001"
          # 4. Incrementa number_next: number_next = number_next + number_increment (1 + 1 = 2)
          # 5. Guarda number_next = 2
          #
          # Por lo tanto:
          # - Si number_next = 0, retorna "0000" (0) y luego establece a 1
          # - Si number_next = 1, retorna "0001" (1) y luego establece a 2
          #
          # Lógica de reutilización:
          # - Si eliminamos la secuencia X y el máximo existente es M (M < X)
          # - Queremos que la próxima secuencia sea M+1
          # - Por lo tanto, establecemos number_next a M+1 para que next_by_id() genere M+1
          #
          # Ejemplo: Si max_existing_number = 0 y eliminamos la 1:
          # - Establecemos number_next a 0 + 1 = 1
          # - next_by_id() retorna "0001" y establece number_next a 2
          
          # Solo ajustar si el número eliminado es mayor al máximo existente
          # Esto asegura que estamos reutilizando un número que estaba "adelante"
          if deleted_sequence_number > max_existing_number:
            # Establecer a max_existing_number + 1 para que next_by_id() genere max_existing_number + 1
            new_next = max_existing_number + 1
            self.company_id.trade_sequence_id.sudo().write({
              'number_next': new_next
            })
            # Verificar que se estableció correctamente
            current_next_after = self.company_id.trade_sequence_id.number_next
            _logger.info('DEBUG_DEVELOPMENT: Secuencia reutilizada. Eliminada: %s, Máximo existente: %s, number_next antes: %s, Establecido a %s, Verificado después: %s', 
                        deleted_sequence_number, max_existing_number, current_next_before, new_next, current_next_after)
          else:
            _logger.info('DEBUG_DEVELOPMENT: No se puede reutilizar secuencia. Eliminada: %s, Máximo existente: %s, number_next actual: %s. La secuencia eliminada no es mayor al máximo.', 
                        deleted_sequence_number, max_existing_number, current_next_before)
    except Exception as e:
      # Si hay algún error al procesar la secuencia, continuar con la eliminación normal
      # Log del error para debugging
      import logging
      _logger = logging.getLogger(__name__)
      _logger.warning('DEBUG_DEVELOPMENT: Error al intentar reutilizar secuencia: %s', str(e))
    
    current_trade_number.unlink()
    
    self.write({
      'delivery_report_trade_number_id': False,
      'delivery_report_has_sequence': False,
      'delivery_report_code': self.delivery_report_code or '',
    })
    
    # Forzar recálculo de campos computed
    self._compute_delivery_report_sequence_code()
    self._compute_can_delete_delivery_sequence()
    
    # Leer los valores actualizados
    self.invalidate_recordset(['delivery_report_sequence_code', 'can_delete_delivery_sequence'])
    values = self.read(['delivery_report_sequence_code', 'can_delete_delivery_sequence', 'delivery_report_has_sequence', 'delivery_report_code'])[0]
    
    # Retornar acción que recarga la vista del formulario (similar a nsk_pdf_manager)
    return {
      'type': 'ir.actions.client',
      'tag': 'refresh_delivery_fields',
      'params': {
        'message': _('Se ha eliminado la secuencia: %s') % sequence_name,
        'parent_model': self._name,
        'parent_id': self.id,
      }
    }

  def get_current_user_signature(self):
    """
    Método seguro para obtener la firma digital del usuario actual.
    Retorna la firma si existe y el usuario tiene acceso, o False en caso contrario.
    """
    current_user = self.env.user.sudo()
    return current_user.sign_signature if current_user.sign_signature else False

  @api.depends(
    'etd_maneuvers',
    'eta_maneuvers',
    'type_id.field_concant_text_template',
  )
  def concatenated_text_description_template(self):
    """
    Función principal que procesa plantillas con wildcards y actualiza description_name.
    Detecta y aplica wildcards globales y locales.
    """
    for record in self:
      type = record.type_id
      if not type:
        continue

      # Validar que existe plantilla
      if (
        not type.field_concant_template_ids
        and not type.field_concant_text_template
      ):
        raise UserError(_('No se encontró la plantilla'))

      if type.field_concant_template_ids and type.field_concant_text_template:
        raise UserError(
          _('No puede tener ambos tipos de plantilla simultáneamente')
        )

      try:
        # 🎯 PROCESAR CON SISTEMA DE WILDCARDS BALANCEADOS
        if type.field_concant_text_template:
          # Usar plantilla de texto
          processed_text = record._process_complete_template(
            type.field_concant_text_template
          )
        elif type.field_concant_template_ids:
          # Usar plantilla por campos (legacy) con sistema aplicado
          processed_text = ''
          for line in type.field_concant_template_ids:
            if hasattr(record, line.field_name.name):
              field_value = getattr(record, line.field_name.name) or ''
              line_text = f'{line.description_name}{field_value}\n'
              processed_text += record._process_complete_template(line_text)
        else:
          processed_text = ''

        # Actualizar campos - description_name con texto plano para tracking amigable
        plain_text = record._html_to_plain_text(processed_text)
        record.description_name = plain_text
        record.description_name_html = processed_text

      except Exception as e:
        # Manejo de errores mejorado
        error_msg = f'❌ Error processing template: {str(e)}'
        record.description_name = error_msg

  def _process_complete_template(self, template_text):
    """
    🎯 PROCESA PLANTILLAS CON WILDCARDS BALANCEADOS

    Sistema único simplificado:
    - **texto** = negrita
    - ##texto## = resaltado amarillo
    - {{**campo**}} = campo en negrita
    """
    if not template_text:
      return ''

    try:
      # 1️⃣ PROCESAR CAMPOS CON WILDCARDS {{**campo**}}
      processed_text = self._process_fields_with_wildcards(template_text)

      # 2️⃣ PROCESAR WILDCARDS BALANCEADOS DE TEXTO **texto**
      processed_text = self._process_balanced_wildcards(processed_text)

      return processed_text

    except Exception as e:
      return f'❌ Error procesando plantilla: {str(e)}'

  def _process_balanced_wildcards(self, text):
    """
    🎯 PROCESA WILDCARDS BALANCEADOS (ÚNICO SISTEMA)

    Wildcards soportados:
    **texto** = negrita
    __texto__ = subrayado
    ##texto## = resaltado amarillo
    &&texto&& = resaltado verde
    ^^texto^^ = resaltado azul
    !!texto!! = texto rojo
    $$texto$$ = texto verde
    %%texto%% = texto azul
    @@texto@@ = formato especial
    """
    if not text:
      return ''

    # Definir wildcards balanceados (único sistema)
    wildcards = {
      '**': '<strong>{content}</strong>',
      '__': '<u>{content}</u>',
      '##': '<span style="background-color: yellow; padding: 2px 4px; border-radius: 3px;">{content}</span>',
      '&&': '<span style="background-color: #c3e6cb; padding: 2px 4px; border-radius: 3px;">{content}</span>',
      '^^': '<span style="background-color: lightblue; padding: 2px 4px; border-radius: 3px;">{content}</span>',
      '!!': '<span style="color: red;">{content}</span>',
      '$$': '<span style="color: green;">{content}</span>',
      '%%': '<span style="color: blue;">{content}</span>',
      '@@': '{content}',
    }

    # Aplicar cada wildcard
    for wildcard, html_template in wildcards.items():
      text = self._apply_balanced_wildcard(text, wildcard, html_template)

    return text

  def _apply_balanced_wildcard(self, text, wildcard, html_template):
    """
    🎯 APLICA UN WILDCARD BALANCEADO ESPECÍFICO

    Algoritmo:
    1. Busca apertura del wildcard
    2. Busca cierre correspondiente
    3. Aplica formato al contenido entre apertura y cierre
    4. Permite anidación recursiva
    """
    if not text or wildcard not in text:
      return text

    result = []
    i = 0
    wildcard_len = len(wildcard)

    while i < len(text):
      # Buscar inicio del wildcard
      if text[i : i + wildcard_len] == wildcard:
        # Buscar la posición después del wildcard de apertura
        start_content = i + wildcard_len

        # Buscar el wildcard de cierre
        end_pos = text.find(wildcard, start_content)

        if end_pos != -1 and end_pos > start_content:
          # Encontró par balanceado
          content = text[start_content:end_pos]

          # Procesar contenido recursivamente (permite anidación)
          processed_content = self._process_nested_wildcards(content, wildcard)

          # Aplicar formato
          formatted_html = html_template.format(content=processed_content)
          result.append(formatted_html)

          # Saltar al final del wildcard de cierre
          i = end_pos + wildcard_len
        else:
          # No encontró par, tratar como texto literal
          result.append(text[i])
          i += 1
      else:
        result.append(text[i])
        i += 1

    return ''.join(result)

  def _process_nested_wildcards(self, content, current_wildcard):
    """
    🎯 PROCESA ANIDACIÓN DE WILDCARDS

    Permite: ##Resaltado con **negrita** dentro##
    """
    if not content:
      return content

    # Lista de wildcards excluyendo el actual
    nested_wildcards = {
      '**': '<strong>{content}</strong>',
      '__': '<u>{content}</u>',
      '##': '<span style="background-color: yellow; padding: 2px 4px; border-radius: 3px;">{content}</span>',
      '&&': '<span style="background-color: #c3e6cb; padding: 2px 4px; border-radius: 3px;">{content}</span>',
      '^^': '<span style="background-color: lightblue; padding: 2px 4px; border-radius: 3px;">{content}</span>',
      '!!': '<span style="color: red;">{content}</span>',
      '$$': '<span style="color: green;">{content}</span>',
      '%%': '<span style="color: blue;">{content}</span>',
      '@@': '{content}',
    }

    # Remover el wildcard actual para evitar recursión infinita
    if current_wildcard in nested_wildcards:
      del nested_wildcards[current_wildcard]

    # Procesar wildcards anidados
    for wildcard, html_template in nested_wildcards.items():
      if wildcard in content:
        content = self._apply_balanced_wildcard(
          content, wildcard, html_template
        )

    return content

  def _get_field_value(self, field_name):
    """
    🎯 OBTIENE EL VALOR DE UN CAMPO DEL REGISTRO

    Args:
        field_name (str): Nombre del campo a obtener

    Returns:
        str: Valor del campo convertido a string, o string vacía si no existe
    """
    try:
      self.ensure_one()

      # Manejar campos relacionales con notación punto (ej: partner_id.name)
      if '.' in field_name:
        # Navegar por los campos relacionales
        parts = field_name.split('.')
        value = self
        for part in parts:
          if hasattr(value, part):
            value = getattr(value, part)
          else:
            return ''

        # Si el valor final es un recordset, obtener display_name
        if hasattr(value, '_name'):  # Es un recordset de Odoo
          return value.display_name if value else ''

        return str(value) if value is not False and value is not None else ''

      # Campo simple
      if hasattr(self, field_name):
        field_value = getattr(self, field_name)

        # Manejar diferentes tipos de campo
        if hasattr(field_value, '_name'):  # Recordset (Many2one, etc.)
          return field_value.display_name if field_value else ''
        elif isinstance(field_value, (list, tuple)):  # Many2many, One2many
          if field_value and hasattr(field_value[0], 'display_name'):
            return ', '.join(
              [rec.display_name for rec in field_value if rec.display_name]
            )
          return ', '.join([str(item) for item in field_value])
        elif field_value is False or field_value is None:
          return ''
        else:
          return str(field_value)

      return ''

    except Exception:
      # Error al obtener el valor del campo
      return f'[Error: {field_name}]'

  def _process_fields_with_wildcards(self, text):
    """
    🎯 PROCESA CAMPOS CON Y SIN WILDCARDS

    Sintaxis soportada:
    {{**campo**}} = campo en negrita
    {{##campo##}} = campo resaltado amarillo
    {{__campo__}} = campo subrayado
    {campo} = campo sin formato (texto normal)
    etc.
    """
    if not text:
      return ''

    # 1️⃣ Procesar campos CON wildcards: {{**campo**}}
    pattern_with_wildcards = r'\{\{([*_#&^!$%@]{2})([^}]+)\1\}\}'

    def replace_field_with_wildcards(match):
      wildcard = match.group(1)  # El wildcard doble (**,##,etc)
      field_name = match.group(2)  # El nombre del campo

      # Mapear wildcard a formato
      wildcard_formats = {
        '**': '<strong>{}</strong>',
        '__': '<u>{}</u>',
        '##': '<span style="background-color: yellow; padding: 2px 4px; border-radius: 3px;">{}</span>',
        '&&': '<span style="background-color: #c3e6cb; padding: 2px 4px; border-radius: 3px;">{}</span>',
        '^^': '<span style="background-color: lightblue; padding: 2px 4px; border-radius: 3px;">{}</span>',
        '!!': '<span style="color: red;">{}</span>',
        '$$': '<span style="color: green;">{}</span>',
        '%%': '<span style="color: blue;">{}</span>',
        '@@': '{}',
      }

      # Aplicar formato si existe el wildcard
      if wildcard in wildcard_formats:
        # Aplicar formato de fecha si es @@
        if wildcard == '@@':
          field_value = self._apply_date_formatting(field_name.strip())
        else:
          # Para otros wildcards, obtener valor del campo normalmente
          field_value = self._get_field_value(field_name.strip())

        return wildcard_formats[wildcard].format(field_value)
      else:
        field_value = self._get_field_value(field_name.strip())
        return str(field_value)

    # Aplicar wildcards con formato
    text = re.sub(pattern_with_wildcards, replace_field_with_wildcards, text)

    # 2️⃣ Procesar campos SIN wildcards: {campo}
    # Patrón que NO capture campos que están dentro de {{ }}
    pattern_simple = r'(?<!\{)\{([^{}]+)\}(?!\})'

    def replace_simple_field(match):
      field_name = match.group(1).strip()  # El nombre del campo

      # Obtener valor del campo sin formato especial
      field_value = self._get_field_value(field_name)
      return str(field_value)

    # Aplicar campos simples
    text = re.sub(pattern_simple, replace_simple_field, text)

    return text

  def _apply_date_formatting(self, field_name):
    """
    Aplica formato de fecha a un campo, obteniendo el valor raw del campo.
    """
    try:
      # Obtener el valor raw del campo (datetime/date object, no string)
      if hasattr(self, field_name):
        raw_field_value = getattr(self, field_name)
        return self.format_dates_to_string(raw_field_value)
    except Exception:
      pass

    # Fallback: usar el método normal si falla el formateo de fecha
    return self._get_field_value(field_name)

  def _html_to_plain_text(self, html_text):
    """
    Convierte texto HTML a texto plano eliminando las etiquetas HTML y entidades.
    Limpia caracteres especiales comunes que aparecen al editar HTML en formularios.
    """
    import re

    if not html_text:
      return ''

    # 1. Convertir saltos de línea HTML antes de remover etiquetas
    clean_text = html_text.replace('<br/>', '\n')
    clean_text = clean_text.replace('<br>', '\n')
    clean_text = clean_text.replace('<br />', '\n')
    clean_text = clean_text.replace('</p>', '\n')
    clean_text = clean_text.replace('<p>', '')

    # 2. Remover etiquetas HTML
    clean_text = re.sub(r'<[^>]+>', '', clean_text)

    # 3. Convertir entidades HTML comunes
    html_entities = {
      '&nbsp;': ' ',  # Espacio no separable
      '&amp;': '&',  # Ampersand
      '&lt;': '<',  # Menor que
      '&gt;': '>',  # Mayor que
      '&quot;': '"',  # Comillas dobles
      '&#39;': "'",  # Comillas simples
      '&apos;': "'",  # Apóstrofe
      '&ndash;': '–',  # Guión corto
      '&mdash;': '—',  # Guión largo
      '&hellip;': '...',  # Puntos suspensivos
      '&copy;': '©',  # Copyright
      '&reg;': '®',  # Marca registrada
      '&trade;': '™',  # Marca comercial
      '&euro;': '€',  # Euro
      '&pound;': '£',  # Libra
      '&yen;': '¥',  # Yen
      '&sect;': '§',  # Sección
      '&para;': '¶',  # Párrafo
      '&laquo;': '«',  # Comillas izquierdas
      '&raquo;': '»',  # Comillas derechas
      '&ldquo;': '"',  # Comillas dobles izquierdas
      '&rdquo;': '"',  # Comillas dobles derechas
      '&lsquo;': """,     # Comillas simples izquierdas
      '&rsquo;': """,  # Comillas simples derechas
      '&deg;': '°',  # Grados
      '&plusmn;': '±',  # Más/menos
      '&times;': '×',  # Multiplicación
      '&divide;': '÷',  # División
    }

    # Aplicar conversiones de entidades
    for entity, replacement in html_entities.items():
      clean_text = clean_text.replace(entity, replacement)

    # 4. Limpiar entidades numéricas (&#123;, &#x1A;)
    clean_text = re.sub(r'&#\d+;', '', clean_text)  # Entidades decimales
    clean_text = re.sub(
      r'&#x[0-9a-fA-F]+;', '', clean_text
    )  # Entidades hexadecimales

    # 5. Limpiar espacios múltiples y caracteres de control
    clean_text = re.sub(
      r'\s+', ' ', clean_text
    )  # Múltiples espacios a uno solo
    clean_text = re.sub(
      r'[\r\n]+', '\n', clean_text
    )  # Múltiples saltos de línea
    clean_text = re.sub(r'[\t]+', ' ', clean_text)  # Tabs a espacios

    # 6. Remover espacios al inicio y final
    return clean_text.strip()

  def _generate_template_description(self):
    """
    🎯 GENERA DESCRIPCIÓN DESDE PLANTILLA
    Método helper para poblar ambos campos desde la plantilla del tipo de solicitud
    """
    try:
      if not self.type_id or not self.type_id.field_concant_text_template:
        return '', ''

      # Procesar la plantilla usando el sistema de wildcards
      template_content = self.type_id.field_concant_text_template

      # Generar HTML formateado (procesar wildcards y convertir saltos de línea)
      html_text = self._process_complete_template(template_content)

      # Generar texto plano (sin HTML) desde el HTML generado
      plain_text = self._html_to_plain_text(html_text or '')

      return plain_text, html_text

    except Exception as e:
      error_msg = f'Error procesando plantilla: {str(e)}'
      return error_msg, f"<p style='color: red;'>{error_msg}</p>"

  @api.depends('type_id', 'type_id.field_concant_text_template')
  def _compute_description_fields(self):
    """Computa automáticamente los campos de descripción desde la plantilla"""
    for record in self:
      try:
        if (
          record.type_id
          and hasattr(record.type_id, 'field_concant_text_template')
          and record.type_id.field_concant_text_template
        ):
          # Generar texto plano y HTML desde la plantilla
          plain_text, html_text = record._generate_template_description()
          record.description_name = plain_text
          record.description_name_html = html_text
        else:
          # Si no hay plantilla o está vacía, dejar campos vacíos sin error
          record.description_name = ''
          record.description_name_html = ''
      except Exception:
        # Manejar errores sin romper la interfaz
        record.description_name = ''
        record.description_name_html = ''

  @api.depends('stage_id', 'type_id', 'type_id.stage_ids')
  def _compute_next_stage_fold(self):
    """Computa si la próxima etapa tiene fold=True"""
    for record in self:
      next_stage = record._get_next_stage()
      record.next_stage_fold = next_stage.fold if next_stage else False

  @api.depends('notification_ids', 'notification_ids.user_id')
  def _compute_available_notification_users(self):
    """Computa los usuarios disponibles que no están ya en la lista de notificaciones"""
    for record in self:
      # Obtener IDs de usuarios ya seleccionados
      selected_user_ids = record.notification_ids.mapped('user_id.id')

      # Obtener todos los usuarios activos
      all_users = self.env['res.users'].search([('active', '=', True)])

      # Filtrar usuarios no seleccionados
      available_users = all_users.filtered(
        lambda u: u.id not in selected_user_ids
      )

      record.available_notification_user_ids = available_users

  @api.onchange('type_id')
  def _onchange_type_id_description(self):
    """Actualiza campos de descripción al cambiar el tipo de solicitud"""
    if self.type_id:
      self._compute_description_fields()
      # Inicializar notificaciones basadas en notify_stage del tipo
      self._initialize_notifications()

  def _get_next_stage(self):
    """Obtiene la próxima etapa en la secuencia"""
    if not self.type_id or not self.stage_id:
      return None

    # Obtener todas las etapas del tipo ordenadas por secuencia
    stages = self.type_id.stage_ids.sorted('sequence')

    # Encontrar la posición de la etapa actual
    current_index = None
    for i, stage in enumerate(stages):
      if stage.id == self.stage_id.id:
        current_index = i
        break

    # Retornar la siguiente etapa si existe
    if current_index is not None and current_index + 1 < len(stages):
      return stages[current_index + 1]

    return None

  def _initialize_notifications(self, force_create=False):
    """Inicializa las notificaciones basadas en la configuración del tipo de solicitud

    Args:
        force_create (bool): Si es True, fuerza la creación aunque el registro tenga ID
    """
    if not self.type_id:
      return

    # Limpiar notificaciones existentes (solo para registros nuevos o forzado)
    if not self.id or force_create:
      self.notification_ids = [(5, 0, 0)]

    # Obtener la próxima etapa
    next_stage = self._get_next_stage()

    # Crear notificaciones para todos los usuarios configurados en notify_stage_ids
    notification_lines = []
    users_added = set()

    for notify_stage in self.type_id.notify_stage_ids:
      for user in notify_stage.user_ids:
        if user.id not in users_added:
          # Marcar notify=True solo si el usuario está configurado para la próxima etapa
          should_notify = (
            next_stage and notify_stage.stage_id.id == next_stage.id
          )

          notification_lines.append(
            (
              0,
              0,
              {
                'user_id': user.id,
                'notify': should_notify,  # True solo si es para la próxima etapa
                'create_activity': False,  # Por ahora deshabilitado
                'sequence': len(notification_lines) + 1,
              },
            )
          )
          users_added.add(user.id)

    if notification_lines and (not self.id or force_create):
      self.notification_ids = notification_lines

  def regenerate_description_fields(self):
    """Regenera los campos de descripción desde la plantilla del tipo de solicitud"""
    # Forzar el recálculo de los campos computed
    try:
      plain_text, html_text = self._generate_template_description()
      self.description_name = plain_text
      self.description_name_html = html_text
    except Exception:
      pass

    return True

  def _process_template_content(self, template_content):
    """Procesa el contenido de la plantilla reemplazando los comodines con valores reales"""
    if not template_content or not isinstance(template_content, str):
      return ''

    try:
      import re

      processed_content = str(template_content)

      # 1. Procesar comodines de fecha {{@@campo@@}}
      date_placeholders = re.findall(r'\{\{@@([^@]+)@@\}\}', processed_content)
      for placeholder in date_placeholders:
        replacement_value = ''
        try:
          clean_placeholder = placeholder.strip()
          if hasattr(self, clean_placeholder):
            field_value = getattr(self, clean_placeholder, None)
            replacement_value = str(field_value) if field_value else '____'
          else:
            replacement_value = '____'
        except Exception:
          replacement_value = '____'

        old_pattern = f'{{{{@@{placeholder}@@}}}}'
        processed_content = processed_content.replace(
          old_pattern, replacement_value
        )

      # 2. Limpiar las estructuras de formato &&**...**&& (ya procesadas)
      processed_content = re.sub(r'&&\*\*(.*?)\*\*&&', r'\1', processed_content)

      # 3. Procesar comodines normales {campo}
      normal_placeholders = re.findall(r'\{([^}]+)\}', processed_content)
      for placeholder in normal_placeholders:
        replacement_value = ''
        try:
          clean_placeholder = placeholder.strip()
          # Manejar campos relacionales con punto
          if '.' in clean_placeholder:
            parts = clean_placeholder.split('.')
            if len(parts) == 2:
              field_name, attr_name = parts[0].strip(), parts[1].strip()
              if hasattr(self, field_name):
                field_value = getattr(self, field_name, None)
                if field_value and hasattr(field_value, attr_name):
                  attr_value = getattr(field_value, attr_name, None)
                  if attr_value is not None:
                    replacement_value = str(attr_value)
          else:
            if hasattr(self, clean_placeholder):
              field_value = getattr(self, clean_placeholder, None)
              if field_value is not None:
                replacement_value = str(field_value)
        except Exception:
          replacement_value = ''

        processed_content = processed_content.replace(
          f'{{{placeholder}}}', replacement_value
        )

      return processed_content.strip()

    except Exception:
      # Si hay cualquier error, devolver cadena vacía en lugar de error
      return ''

  @api.depends(
    'type_calcule',
    'start_date_calculate',
    'end_date_calculate',
    'next_extended_date',
  )
  def _compute_duration_calculate(self):
    for record in self:
      record.calcule_days = 0
      record.calcule_hours = 0
      record.total_hours_used = 0
      record.extended_hours = 0
      record.total_hours_acumulate = 0

      # principal
      if (
        record.start_date_calculate
        and record.end_date_calculate
        and record.type_calcule == '1'
      ):
        start_date_calculate = fields.Date.from_string(
          record.start_date_calculate
        )
        end_date_calculate = fields.Date.from_string(record.end_date_calculate)
        record.calcule_days = (end_date_calculate - start_date_calculate).days
        start_date_calculate_hour = fields.Datetime.to_datetime(
          record.start_date_calculate
        )
        end_date_calculate_hour = fields.Datetime.to_datetime(
          record.end_date_calculate
        )
        duration = end_date_calculate_hour - start_date_calculate_hour
        record.calcule_hours = duration.total_seconds() / 3600

      # Ampliacion o reduccion
      if (
        record.next_extended_date
        and record.type_calcule == '2'
        and record.start_date_calculate
      ):
        start_date_calculate_hour = fields.Datetime.to_datetime(
          record.start_date_calculate
        )
        next_extended_date_hour = fields.Datetime.to_datetime(
          record.next_extended_date
        )
        duration = next_extended_date_hour - start_date_calculate_hour
        record.extended_hours = duration.total_seconds() / 3600

        start_date_calculate = fields.Date.from_string(
          record.start_date_calculate
        )
        next_extended_date = fields.Date.from_string(record.next_extended_date)
        record.calcule_days = (next_extended_date - start_date_calculate).days
        if (
          record.extended_hours
          and record.parent_id
          and record.parent_id.calcule_hours
          and record.parent_id.type_calcule == '1'
        ):
          record.total_hours_acumulate = (
            record.extended_hours - record.parent_id.calcule_hours
          )
        if (
          record.extended_hours
          and record.parent_id
          and record.parent_id.extended_hours
          and record.parent_id.type_calcule == '2'
        ):
          record.total_hours_acumulate = (
            record.extended_hours - record.parent_id.extended_hours
          )

  # fecha principal
  @api.depends(
    'start_date_calculate',
    'end_date_calculate',
    'type_calcule',
    'next_extended_date',
  )
  def calcule_principal(self):
    for record in self:
      user_tz = pytz.timezone(
        self.env.context.get('tz') or self.env.user.tz or 'UTC'
      )

      record.need_extend_hours_text = ''
      if (
        record.start_date_calculate
        and record.end_date_calculate
        and record.type_calcule == '1'
      ):
        end_date_calculate_dt = record.end_date_calculate.astimezone(user_tz)
        horas, minutos = divmod(record.calcule_hours, 1)
        minutos = round(minutos * 60)
        record.need_extend_hours_text = f'*{int(horas)}:{minutos:02d}  HORAS (hasta el {end_date_calculate_dt.strftime("%d/%m/%Y %H:%M:%S")})*_'

      if (
        record.next_extended_date
        and record.type_calcule == '2'
        and record.start_date_calculate
      ):
        next_extended_date = record.next_extended_date.astimezone(user_tz)
        horas, minutos = divmod(record.total_hours_acumulate, 1)
        minutos = round(minutos * 60)

        record.need_extend_hours_text = f'*{int(horas)}:{minutos:02d} HORAS (hasta el {next_extended_date.strftime("%d/%m/%Y %H:%M:%S")})*_'

  @api.depends('need_extend_hours_text')
  def field_date_text_union(self):
    for record in self:
      record.contant_text_next = ''
      if (
        record.need_extend_hours_text
        and record.parent_id
        and record.parent_id.need_extend_hours_text
        and record.type_calcule == '2'
      ):
        record.contant_text_next = str(
          record.parent_id.contant_text_next
        ) + str(record.need_extend_hours_text)
      if (
        record.start_date_calculate
        and record.end_date_calculate
        and record.type_calcule == '1'
        and record.need_extend_hours_text
      ):
        record.contant_text_next = str(record.need_extend_hours_text)

  # @api.depends('extended_hours', 'need_to_extend_hours','end_date_calculate','next_extended_date')
  # def compute_concatenated_field_date_text(self):
  #       for record in self:
  #         record.text_self_calculate = ""
  #         if record.need_to_extend_hours and   record.next_extended_date and record.total_hours_used:
  #             record.text_self_calculate = f"*{record.total_hours_used} HORAS (hasta el {record.next_extended_date.strftime('%d/%m/%Y %H:%M:%S')})*_"

  def compute_concatenated_field_date(self):
    concatenated_text = ''
    # letters = 'abcdefghijklmnopqrstuvwxyz'  # Usaremos letras para el formato a), b), c), etc.
    letter_index = 0

    for record in self:
      if record.next_extended_date:
        new_entry = f'*{record.total_hours_used} HORAS (hasta el {record.next_extended_date.strftime("%d/%m/%Y %H:%M:%S")})*_'
        if concatenated_text:
          concatenated_text += f' - {new_entry}'
        else:
          concatenated_text = new_entry
        letter_index += (
          1  # Avanzar a la siguiente letra para la próxima entrada
        )
      elif record.end_date_calculate:
        new_entry = f'*{record.calcule_hours} HORAS (hasta el {record.end_date_calculate.strftime("%d/%m/%Y %H:%M:%S")})*_'
        if concatenated_text:
          concatenated_text += f' - {new_entry}'
        else:
          concatenated_text = new_entry
        letter_index += 1

    return concatenated_text

  def generate_new_number(self, object, values):
    seq = False

    if self.env.context.get('foce_sequence', False):
      if (
        object.type_id
        and object.type_id.has_internal_sequence
        and object.type_id.internal_sequence
      ):
        # object.write({'name': object.type_id.internal_sequence.next_by_id()})
        return True
      else:
        seq = self.env['ir.sequence'].search(
          [('code', '=', 'ek.operation.request.sequence')], limit=1
        )

    if not seq and values.get('name', '/') == '/':
      if (
        object.type_id
        and object.type_id.has_internal_sequence
        and object.type_id.internal_sequence
      ):
        # object.write({'name': object.type_id.internal_sequence.next_by_id()})
        return True
      else:
        seq = self.env['ir.sequence'].search(
          [('code', '=', 'ek.operation.request.sequence')], limit=1
        )

    if seq and values.get('name', '/') == '/':
      next_name = seq.next_by_id()
      if next_name:
        object.write(
          {'name': next_name, 'sequence_number_next_ek': next_name}
        )  # "number_bl": next_name  preguntar uso de este campo
      else:
        object.write({'name': '/'})

  def write(self, vals):
    """Override write to sync description_name and preserve res_partner_id consistency"""

    # Si se está editando description_name_html, actualizar description_name automáticamente
    if 'description_name_html' in vals:
      # Convertir HTML a texto plano para description_name
      html_content = vals['description_name_html'] or ''
      plain_text = self._html_to_plain_text(html_content)
      vals['description_name'] = plain_text

    # Preservar coherencia de res_partner_id cuando se actualiza ek_ship_registration_id
    for record in self:
      # Si se está actualizando el barco
      if 'ek_ship_registration_id' in vals and vals['ek_ship_registration_id']:
        ship = self.env['ek.ship.registration'].browse(
          vals['ek_ship_registration_id']
        )

        # Si el barco tiene business_name y no se está explícitamente cambiando el cliente
        if ship.bussiness_name_id and 'res_partner_id' not in vals:
          # Auto-actualizar el cliente para que coincida con el barco
          vals['res_partner_id'] = ship.bussiness_name_id.id

        elif not ship.bussiness_name_id and 'res_partner_id' not in vals:
          # Si el barco no tiene business_name, limpiar el cliente
          vals['res_partner_id'] = False

    # Llamar al write original (que manejará el tracking de description_name automáticamente)
    result = super(ek_operation_request, self).write(vals)
    
    # CREAR SEGUIMIENTO DE REEMBOLSOS desde borrador cuando se guarda la solicitud
    if 'type_id' in vals or 'stage_id' in vals:
      for record in self:
        if record.type_id.is_service_refunf:
          record._create_reimbursement_tracking_records()

    # Si cambió la etapa, guardar estado de notificaciones antes de actualizar
    if 'stage_id' in vals:
      for record in self:
        # Guardar estado actual de notificaciones ANTES de actualizar
        if record.notification_ids:
          current_notifications = []
          for notif in record.notification_ids:
            current_notifications.append(
              {
                'user_id': notif.user_id.id,
                'notify': notif.notify,
                'create_activity': notif.create_activity,
              }
            )
          # Almacenar en una caché temporal usando el ID del registro
          if not hasattr(self.__class__, '_notification_cache'):
            self.__class__._notification_cache = {}
          self.__class__._notification_cache[record.id] = current_notifications

        # NO actualizar aquí - lo haremos después de enviar las notificaciones
        # record.update_notification_status()  # Movido a action_next_stage()

    return result

  @api.model_create_multi
  def create(self, values_list):
    # Asegurar coherencia de res_partner_id en create
    for values in values_list:
      # Si se está creando con barco pero sin cliente
      if values.get('ek_ship_registration_id') and not values.get(
        'res_partner_id'
      ):
        ship = self.env['ek.ship.registration'].browse(
          values['ek_ship_registration_id']
        )
        if ship.bussiness_name_id:
          values['res_partner_id'] = ship.bussiness_name_id.id

    records = super(ek_operation_request, self).create(values_list)

    # Generar números después de la creación
    for record, values in zip(records, values_list):
      record.generate_new_number(record, values)

      # Inicializar notificaciones si tiene type_id
      if record.type_id:
        record._initialize_notifications_on_create()
        
      # CREAR SEGUIMIENTO DE REEMBOLSOS desde borrador al crear la solicitud
      if record.type_id and record.type_id.is_service_refunf:
        record._create_reimbursement_tracking_records()
        
      # CREAR LÍNEAS INICIALES para la etapa inicial (solo crear, no órdenes)
      if record.type_id and record.stage_id:
        if record.type_id.is_service_request:
          record.action_fill_pov_line(record.type_id, record.stage_id, 'service')
        if record.type_id.is_service_refunf:
          record.action_fill_pov_line(record.type_id, record.stage_id, 'purchase')

    return records

  display_name = fields.Char(compute='_compute_display_name', store=True)

  @api.depends('type_id', 'name')
  def _compute_display_name(self):
    for record in self:
      if record.type_id and record.type_id.name and record.name:
        record.display_name = record.name + '-' + record.type_id.name
      else:
        record.display_name = record.name

  @api.constrains('journey_crew_id')
  def _check_validation_finizhed_request(self):
    for record in self:
      if record.journey_crew_id.state == 'finished':
        message = f'El Viaje {record.journey_crew_id.name}, del barco {record.ek_ship_registration_id.name} está en estado finalizado, si desea continuar con el proceso, por favor contacte al administrador.'
        raise UserError(_(message))

  @api.depends('value_receive', 'quantity_bonus')
  def compputed_total_pending(self):
    for record in self:
      record.fishing_balance = record.value_receive - record.quantity_bonus

  @api.onchange(
    'ek_table_pay_crew_ids',
    'ek_table_reimbursement_expenses_ids',
  )
  def _onchange_ek_table_pay_crew_ids(self):
    for rec in self:
      if rec.ek_table_pay_crew_ids and rec.crew_pay:
        sum = len(rec.ek_table_pay_crew_ids)
        if sum > 0 and rec.ek_service_request_line_ids:
          rec.ek_service_request_line_ids[0].product_qty = sum
      elif rec.ek_table_reimbursement_expenses_ids:
        unique_providers = set()
        for line in rec.ek_table_reimbursement_expenses_ids:
          if line.partner_id:
            unique_providers.add(line.partner_id.id)
        unique_count = len(unique_providers)
        if unique_count > 0 and rec.ek_service_request_line_ids:
          rec.ek_service_request_line_ids[0].product_qty = unique_count

  @api.onchange('notes_pay_crew')
  def _onchange_notes_pay_crew(self):
    if self.notes_pay_crew:
      for line in self.ek_table_pay_crew_ids:
        line.detail = self.notes_pay_crew

  @api.onchange('quantity_bonus')
  def _onchange_quantity_bonus(self):
    if not self.ek_table_pay_crew_ids and self.crew_pay:
      raise UserError(_('Por favor agregue la tabla de pago'))
    if self.ek_table_pay_crew_ids and self.crew_pay:
      for line in self.ek_table_pay_crew_ids:
        line.v_unitary = self.quantity_bonus

  @api.onchange('crew_ids')
  def _onchange_warning_crew_ids(self):
    if self.crew_ids:
      # Get the last modified crew member
      selected_crew = self.crew_ids[-1] if self.crew_ids else None
      if selected_crew and selected_crew.name:
        # Check if the selected crew member has no documents
        if not selected_crew.name.ek_academic_courses_ids:
          message = (
            f'{selected_crew.name.name} no tiene ningún tipo de documento.'
          )
          return {
            'warning': {
              'title': _('Warning Message'),
              'message': _(message),
            }
          }
        else:
          # Check for expired documents
          expired_documents = []
          for line in selected_crew.name.ek_academic_courses_ids:
            if line.document_status == 'expired':
              expired_documents.append(
                {
                  'document_name': line.course_document_name.name,
                  'end_date': line.end_date,
                }
              )

          if expired_documents:
            document_details = ', '.join(
              [
                f'{doc["document_name"]} {doc["end_date"]}'
                for doc in expired_documents
              ]
            )
            message = f'{selected_crew.name.name} tiene {len(expired_documents)} documento(s) caducado(s) [{document_details}]'
            return {
              'warning': {
                'title': _('Warning Message'),
                'message': _(message),
              }
            }

  def action_download_report(self):
    action = self.action_pdf_render_request('download')
    return action

  def action_send_to_sign_report(self):
    action = self.action_pdf_render_request('sign')
    return action

  def action_pdf_render_request(self, type=False):
    if not self.ek_template_py3o_id:
      raise UserError(_('Seleccione una plantilla para continuar el proceso'))
    self._compute_firm_user_name()
    py3o = self.ek_template_py3o_id.action_report_id.report_type == 'py3o'
    name = self.display_name
    attachment_id = None

    if py3o:
      report = self.ek_template_py3o_id.action_report_id._render_py3o(
        self.ek_template_py3o_id.action_report_id.id, self.ids, {}
      )
      pdf_base64 = base64.b64encode(report[0])
      attachment_id = self.env['ir.attachment'].create(
        {
          'name': name,
          'type': 'binary',
          'datas': pdf_base64,
          'store_fname': name,
          'res_model': self._name,
          'res_id': self.id,
        }
      )
    else:
      report_action = self.ek_template_py3o_id.action_report_id
      if type == 'download':
        return report_action.report_action(self)
      if type == 'sign':
        report_action = report_action.sudo()._render_qweb_pdf(
          self.ek_template_py3o_id.action_report_id.id, self.ids
        )[0]
        pdf_base64 = base64.b64encode(report_action)
        attachment_id = self.env['ir.attachment'].create(
          {
            'name': name,
            'type': 'binary',
            'datas': pdf_base64,
            'store_fname': name,
            'res_model': self._name,
            'res_id': self.id,
          }
        )

    if type == 'download' and py3o:
      action = {
        'type': 'ir.actions.act_url',
        'url': f'/web/content/{attachment_id.id}?download=true',
        'target': 'self',
      }
      return action
    if type == 'sign':
      if not self.ek_template_py3o_id.ek_detail_template_items_ids:
        raise UserError(
          _(
            'The settings to send to sign are missing, select another template or contact the administrator.'
          )
        )
      template = self.env['sign.template'].create(
        {
          'attachment_id': attachment_id.id,
          'sign_item_ids': [(6, 0, [])],
        }
      )
      signers_set = set()
      for sign in self.ek_template_py3o_id.ek_detail_template_items_ids:
        if sign.type_id.item_type == 'signature':
          type_id = self.env.ref('sign.sign_item_type_signature').id
        elif sign.type_id.item_type == 'initial':
          type_id = self.env.ref('sign.sign_item_type_initial').id
        elif sign.type_id.item_type == 'text':
          type_id = self.env.ref('sign.sign_item_type_text').id
        elif sign.type_id.item_type == 'textarea':
          type_id = self.env.ref('sign.sign_item_type_textarea').id
        elif sign.type_id.item_type == 'checkbox':
          type_id = self.env.ref('sign.sign_item_type_checkbox').id
        elif sign.type_id.item_type == 'selection':
          type_id = self.env.ref('sign.sign_item_type_selection').id

        self.env['sign.item'].create(
          {
            'type_id': type_id,
            'name': '',
            'required': sign.required,
            'responsible_id': sign.responsible_id.id,
            'page': sign.page,
            'posX': sign.posX,
            'posY': sign.posY,
            'template_id': template.id,
            'width': sign.width,
            'height': sign.height,
          }
        )
        signer_ids = {
          'role_id': sign.responsible_id.id,
          'partner_id': False,
        }
        if sign.name_field and hasattr(self, sign.name_field):
          partner_model = getattr(self, sign.name_field)
          if partner_model and partner_model.id:
            if not sign.model_res_partner:
              signer_ids['partner_id'] = partner_model.id
            else:
              signer_ids['partner_id'] = partner_model.partner_id.id

        signer_tuple = (0, 0, frozenset(signer_ids.items()))
        signers_set.add(signer_tuple)
      signers = list(signers_set)
      action = self.env['ir.actions.act_window']._for_xml_id(
        'sign.action_sign_send_request'
      )
      signer_request_id = (
        self.env['sign.send.request']
        .sudo()
        .with_context(active_id=template.id, sign_directly_without_mail=False)
        .create({'signer_ids': signers, 'ek_operation_request_id': self.id})
      )
      action['res_id'] = signer_request_id.id
      return action

  def action_open_documents_sign_request(self):
    self.ensure_one()
    return {
      'name': _('Document'),
      'type': 'ir.actions.act_window',
      'res_model': 'sign.request',
      'view_mode': 'kanban',
      'view_id': self.env.ref('sign.sign_request_view_kanban').id,
      'domain': [('ek_operation_request_id', 'in', self.ids)],
      'context': {
        'default_ek_operation_request_id': self.id,
        'create': False,
        'edit': False,
        'delete': False,
      },
      'target': 'current',
    }

  # @api.constrains("journey_crew_id")
  # def _duplip_regimen_70_unique(self):
  #     if self.journey_crew_id.assigned_regimen_70:
  #         duplicate = self.env['ek.operation.request'].search(
  #         [('journey_crew_id', '=', self.journey_crew_id.id), ('fold', '!=', False)])
  #         if len(duplicate) >= 1:
  #             raise UserError(_("You have already created a 70 regimen"))

  @api.constrains('journey_crew_id')
  def _duplip_zarpe_arribo_unique(self):
    duplicate_zarpe = self.env['ek.operation.request'].search(
      [
        ('journey_crew_id', '=', self.journey_crew_id.id),
        ('type_event_boot', '=', 'zarpe'),
      ]
    )
    duplicate_arribo = self.env['ek.operation.request'].search(
      [
        ('journey_crew_id', '=', self.journey_crew_id.id),
        ('type_event_boot', '=', 'arribo'),
      ]
    )

    if len(duplicate_zarpe) > 1:
      raise UserError(_('Ya se ha creado un Zarpe'))
    if len(duplicate_arribo) > 1:
      raise UserError(_('Ya se ha creado un Arribo'))

  @api.constrains('eta', 'ata', 'etd', 'atd')
  def _validate_dates_eta_ata_etd_atd(self):
    """
    Validaciones para los campos de fechas de arribo y zarpe:
    1. ETA debe ser menor o igual que ATA
    2. ETD debe ser menor o igual que ATD
    3. ETD debe ser mayor que ATA
    """
    for record in self:
      # Solo validar si el tipo de solicitud requiere campos de fecha
      if not record.type_id or not record.type_id.type_event_boot:
        continue

      # Solo validar para tipos que realmente manejan fechas de arribo/zarpe
      if record.type_id.type_event_boot not in ['arribo', 'zarpe']:
        continue

      # Validación 1: eta debe ser menor o igual que ata
      if record.eta and record.ata and record.eta > record.ata:
        raise ValidationError(
          _(
            'ETA (Estimated Time of Arrival) must be less than or equal to ATA (Actual Time of Arrival).'
          )
        )

      # Validación 2: etd debe ser menor o igual que atd
      if record.etd and record.atd and record.etd > record.atd:
        raise ValidationError(
          _(
            'ETD (Estimated Time of Departure) must be less than or equal to ATD (Actual Time of Departure).'
          )
        )

      # Validación 3: etd debe ser mayor que ata
      if record.ata and record.etd and record.etd <= record.ata:
        raise ValidationError(
          _(
            'ETD (Estimated Time of Departure) must be greater than ATA (Actual Time of Arrival).'
          )
        )

  @api.constrains('type_id', 'journey_crew_id')
  def _validate_type_requires_journey(self):
    """
    Validación: No permitir guardar un tipo de solicitud sin viaje seleccionado.
    """
    for record in self:
      if record.type_id and not record.journey_crew_id:
        raise ValidationError(
          _(
            'You cannot select a Request Type without first selecting a Journey. Please select a Journey before choosing the Request Type.'
          )
        )

  @api.constrains('ek_ship_registration_id', 'res_partner_id')
  def _validate_customer_ship_consistency(self):
    """
    Validación: El cliente debe coincidir con el business_name_id del barco seleccionado.
    Solo valida cuando ambos campos están establecidos y el registro no está en proceso de creación.
    """
    for record in self:
      # Skip validation during record creation or if either field is missing
      if (
        not record.id
        or not record.ek_ship_registration_id
        or not record.res_partner_id
      ):
        continue

      # Verificar que el cliente coincida con el business_name del barco
      ship_customer = record.ek_ship_registration_id.bussiness_name_id

      # Solo validar si el barco tiene un business_name asignado
      if ship_customer:
        if ship_customer.id != record.res_partner_id.id:
          raise ValidationError(
            _(
              "The selected Customer must match the Ship's Business Name. "
              'Ship "%s" belongs to "%s", but Customer is set to "%s".'
            )
            % (
              record.ek_ship_registration_id.name,
              ship_customer.name,
              record.res_partner_id.name,
            )
          )
        else:
          # Customer matches ship business_name - validation passed
          pass
      else:
        # Si el barco no tiene business_name, solo mostrar warning en logs, no bloquear
        # Ship has no Business Name assigned - validation skipped
        pass

  @api.constrains('type_id', 'agent_user_id')
  def _validate_agent_naviero_required(self):
    """
    Validación de constraint: Si el tipo de solicitud requiere agente naviero,
    debe tener un agente válido asignado.
    """
    for record in self:
      if record.type_id and record.type_id.is_agent_naviero:
        if not record.agent_user_id:
          raise ValidationError(
            _(
              'El tipo de solicitud "%s" requiere un Agente Naviero. '
              'Por favor, seleccione un usuario válido como agente.'
            )
            % record.type_id.name
          )

        if not record.agent_user_id.is_shipping_agent:
          raise ValidationError(
            _(
              'El usuario "%s" no tiene permisos de Agente Naviero. '
              'Por favor, contacte al administrador para habilitar este permiso.'
            )
            % record.agent_user_id.name
          )

  def _get_last_arribo_dates(self):
    """
    Busca el último arribo del barco para obtener las fechas ETA/ATA.
    Retorna un diccionario con las fechas del último arribo.
    """
    self.ensure_one()

    if not self.ek_ship_registration_id:
      return {'eta': False, 'ata': False}

    # Buscar el último arribo del mismo barco
    last_arribo = self.env['ek.operation.request'].search(
      [
        ('ek_ship_registration_id', '=', self.ek_ship_registration_id.id),
        ('type_event_boot', '=', 'arribo'),
        ('eta', '!=', False),
        ('ata', '!=', False),
      ],
      order='ata desc',
      limit=1,
    )

    if last_arribo:
      return {
        'eta': last_arribo.eta,
        'ata': last_arribo.ata,
        'arribo_id': last_arribo.id,
      }
    else:
      # Si no hay arribo previo, usar fechas del journey actual
      if self.journey_crew_id:
        return {
          'eta': self.journey_crew_id.eta,
          'ata': self.journey_crew_id.ata,
          'arribo_id': False,
        }
      else:
        return {'eta': False, 'ata': False, 'arribo_id': False}

  def _get_last_arribo_resources(self):
    """
    Busca el último arribo del barco para obtener los recursos (fuel, gasoline, water).
    Retorna un diccionario con los recursos del último arribo.
    """
    self.ensure_one()

    if not self.ek_ship_registration_id:
      return {'fuel': False, 'gasoline': False, 'water': False}

    # Buscar el último arribo del mismo barco
    last_arribo = self.env['ek.operation.request'].search(
      [
        ('ek_ship_registration_id', '=', self.ek_ship_registration_id.id),
        ('type_event_boot', '=', 'arribo'),
        ('processing_status', '=', 'done'),  # Solo arribos completados
      ],
      order='create_date desc',  # Más reciente primero
      limit=1,
    )

    if last_arribo:
      return {
        'fuel': last_arribo.fuel or False,
        'gasoline': last_arribo.gasoline or False,
        'water': last_arribo.water or False,
        'arribo_id': last_arribo.id,
      }
    else:
      return {'fuel': False, 'gasoline': False, 'water': False, 'arribo_id': False}

  @api.depends('ek_service_request_line_ids')
  def _compute_amount_line(self):
    for record in self:
      total_amount = sum(
        record.ek_service_request_line_ids.mapped('price_unit')
      )
      record.amount = total_amount

  @api.onchange('journey_crew_id', 'ek_ship_registration_id')
  def _onchange_ship_registration_id(self):
    for rec in self:
      rec.analytic_account_id = rec.ek_ship_registration_id.analytic_account_id
      rec.ek_boat_location_id = rec.ek_ship_registration_id.ek_boat_location_id

  @api.onchange('agent_user_id')
  def onchange_agent_user_id(self):
    if self.agent_user_id:
      # Validar que el usuario sea agente naviero
      if not self.agent_user_id.is_shipping_agent:
        return {
          'warning': {
            'title': _('Usuario no válido'),
            'message': _(
              'El usuario seleccionado no tiene permisos de Agente Naviero. '
              'Por favor, contacte al administrador para habilitar este permiso.'
            ),
          },
          'value': {'agent_user_id': False},
        }

      # Si es válido, actualizar el VAT
      if self.agent_user_id.partner_id:
        self.vat = self.agent_user_id.partner_id.vat

  @api.onchange('type_id')
  def _onchange_type_id(self):
    """Set default values for required fields based on request type."""

    if self.type_id:
      # Validación: No permitir seleccionar tipo sin viaje
      if not self.journey_crew_id:
        self.type_id = False
        return {
          'warning': {
            'title': _('Warning'),
            'message': _(
              'You must select a Journey before selecting the Request Type.'
            ),
          }
        }
      type_request = self.type_id

      # Get all fields that could be required in any type
      all_required_fields = self.env['ek.l10n.type.field.mixin'].search(
        [('has_required', '=', True)]
      )

      # Get fields required for this specific type
      type_required_fields = self.type_id.fields_ids.filtered(
        lambda f: f.has_required
      )
      type_required_field_names = type_required_fields.mapped('field_id.name')

      # Fields that should never be overwritten with default values
      protected_fields = [
        'date_start',
        'res_partner_id',
        'ek_ship_registration_id',
        'journey_crew_id',
      ]

      # For each potentially required field
      for field in all_required_fields:
        field_name = field.field_id.name
        # If the field is not required for this type and not in protected fields, set a default value
        if (
          field_name not in type_required_field_names
          and field_name not in protected_fields
        ):
          field_type = self._fields[field_name].type
          if field_type == 'datetime':
            # Use a very old date as a marker for "not applicable"
            setattr(
              self,
              field_name,
              fields.Datetime.from_string('1900-01-01 00:00:00'),
            )
          elif field_type == 'date':
            setattr(self, field_name, fields.Date.from_string('1900-01-01'))
          elif field_type in ['char', 'text']:
            setattr(self, field_name, 'N/A')
          elif field_type in ['integer', 'float']:
            setattr(self, field_name, 0)
          elif field_type == 'boolean':
            setattr(self, field_name, False)
          # Para campos many2one, many2many, etc., se quedan como False

      # --- Lógica de la función completa (asignación de campos por tipo) ---
      self.supplier_id = type_request.supplier_id
      self.ek_user_groups_reminder_ids = (
        type_request.ek_user_groups_reminder_ids
      )
      self.ek_service_request_report_line_ids = (
        type_request.ek_service_request_report_line_ids
      )
      self.ek_group_mail_template_id = type_request.ek_group_mail_template_id

      self.messege_war_doc = (
        self.ek_ship_registration_id.is_practic and type_request.type_event_boot
      )
      trb = self.ek_ship_registration_id.trb or 'NULL'
      quy_trb = (
        self.ek_ship_registration_id.ek_boats_measures_4_id.name or 'NULL'
      )
      trn = self.ek_ship_registration_id.trn or 'NULL'
      quy_trn = (
        self.ek_ship_registration_id.ek_boats_measures_5_id.name or 'NULL'
      )
      trb = str(trb)
      quy_trb = str(quy_trb)
      trn = str(trn)
      quy_trn = str(quy_trn)
      value = (
        'T.R.B:'
        + ' '
        + trb
        + ' '
        + quy_trb
        + ', '
        + 'T.R.N:'
        + ' '
        + trn
        + ' '
        + quy_trn
      )
      self.report_tr_n_n = value

      if (
        type_request.has_report_capitana
        and self.ek_ship_registration_id.boat_registration
      ):
        self.boat_registration = self.ek_ship_registration_id.boat_registration
        self.inform_data_capman = self.ek_ship_registration_id.name
      if type_request.send_to_sign_report or type_request.download_report:
        self.ek_report_stages_mixin_ids = (
          type_request.ek_report_stages_mixin_ids.ids
        )

      if 'reason_arrival_ids' in type_request.mapped(
        'fields_ids.field_id.name'
      ):
        self.reason_arrival_ids = self.journey_crew_id.reason_arrival_ids

      if type_request.type_event_boot in ['fondeo', 'atraque', 'dique']:
        self.type_event_boot = type_request.type_event_boot
        self.eta_maneuvers = self.journey_crew_id.eta
        self.etd_maneuvers = self.journey_crew_id.etd

      if type_request.type_event_boot == 'arribo':
        self.eta = self.journey_crew_id.eta
        self.ata = self.journey_crew_id.ata
        self.etd = False
        self.atd = False
        self.type_event_boot = type_request.type_event_boot
        self.type_event = type_request.type_event

      if type_request.type_event_boot == 'zarpe':
        # Obtener fechas del último arribo
        arribo_dates = self._get_last_arribo_dates()

        if arribo_dates['eta'] and arribo_dates['ata']:
          # Usar fechas del último arribo
          self.eta = arribo_dates['eta']
          self.ata = arribo_dates['ata']

          # Calcular ETD/ATD como ETA/ATA + 1 semana
          self.etd = arribo_dates['eta'] + datetime.timedelta(weeks=1)
          self.atd = arribo_dates['ata'] + datetime.timedelta(weeks=1)
        else:
          # Fallback: usar fechas del journey si no hay arribo previo
          self.etd = (
            self.journey_crew_id.etd
            if self.journey_crew_id.etd
            else fields.Datetime.now() + datetime.timedelta(weeks=1)
          )
          self.atd = (
            self.journey_crew_id.atd
            if self.journey_crew_id.atd
            else fields.Datetime.now() + datetime.timedelta(weeks=1)
          )
          self.eta = (
            self.journey_crew_id.eta
            if self.journey_crew_id.eta
            else fields.Datetime.now()
          )
          self.ata = (
            self.journey_crew_id.ata
            if self.journey_crew_id.ata
            else fields.Datetime.now()
          )
        self.type_event_boot = type_request.type_event_boot
        self.type_event = type_request.type_event

        # EXTRAER RECURSOS DEL ÚLTIMO ARRIBO PARA ZARPE
        # Cuando se crea una solicitud de zarpe, copiar los valores de fuel, gasoline, water
        # desde la última solicitud de arribo completada del mismo barco
        arribo_resources = self._get_last_arribo_resources()

        # Copiar recursos desde el último arribo (si existen valores)
        if arribo_resources['fuel']:
          self.fuel = arribo_resources['fuel']
        if arribo_resources['gasoline']:
          self.gasoline = arribo_resources['gasoline']
        if arribo_resources['water']:
          self.water = arribo_resources['water']

        # SOLUCIÓN PROVISIONAL: Precargar valores por defecto para campos "Otros Documentos"
        # Solo para solicitudes de tipo Zarpe
        # Estos valores se establecen automáticamente al crear una solicitud de zarpe
        self.other_document_01 = 'Matrícula y habilitantes de Agencia y Agente Naviero, Transferencia bancaria.'
        self.other_document_01_copy = True
        self.other_document_01_original = False

        self.other_document_02 = 'Matrícula de nave y tráficos de la nave, guías de combustible.'
        self.other_document_02_copy = True
        self.other_document_02_original = False

        self.other_document_03 = 'Documentación marítima de la tripulación.'
        self.other_document_03_copy = True
        self.other_document_03_original = True

      if type_request.has_data_zarpe:
        self.datatime_request_practical = self.journey_crew_id.etd
        self.datatime_real_dear = self.journey_crew_id.etd
      if type_request.is_request_assignable and type_request.is_agent_naviero:
        self.block_user_asig = False
        # Solo asignar automáticamente si el usuario actual es agente naviero
        current_user = self.env.user
        if current_user.is_shipping_agent:
          self.agent_user_id = self.env.uid
        else:
          self.agent_user_id = False
      if (
        not type_request.is_request_assignable and type_request.is_agent_naviero
      ):
        # Solo asignar automáticamente si el usuario actual es agente naviero
        current_user = self.env.user
        if current_user.is_shipping_agent:
          self.agent_user_id = self.env.uid
        else:
          self.agent_user_id = False
        self.block_user_asig = True
      if type_request.has_access_port or (
        'char_name_buquer' in type_request.mapped('fields_ids.field_id.name')
      ):
        self.char_name_buquer = self.ek_ship_registration_id.name
      if 'ek_res_world_seaport_id_origin' in type_request.mapped(
        'fields_ids.field_id.name'
      ):
        self.ek_res_world_seaport_id_origin = (
          self.journey_crew_id.ek_res_world_seaports_id
        )
      if 'ek_res_world_seaport_id_destination' in type_request.mapped(
        'fields_ids.field_id.name'
      ):
        self.ek_res_world_seaport_id_destination = (
          self.journey_crew_id.ek_res_world_seaports_d_id
        )
      if 'eta' in type_request.mapped('fields_ids.field_id.name'):
        # Solo asignar eta si no es un evento de zarpe
        if type_request.type_event_boot != 'zarpe':
          self.eta = self.journey_crew_id.eta
        else:
          # Para zarpe, ya fue manejado en la lógica principal arriba
          # No sobrescribir aquí, la lógica de zarpe ya se ejecutó
          pass
      if type_request.is_service_request:
        self.action_fill_pov_line(type_request, self.stage_id, 'service')
      if type_request.is_service_refunf:
        self.action_fill_pov_line(type_request, self.stage_id, 'purchase')

      if type_request.has_crew:
        self.crew_ids = [(5, 0, 0)]
        crew_members = [
          (
            0,
            0,
            {
              'name': crew.id,
              'vat': crew.vat,
              'ek_crew_member_hierarchy_id': crew.ek_crew_member_hierarchy_id,
              'nationality_id': crew.nationality_id,
              'ek_crew_member_hierarchy_title_id': crew.ek_crew_member_hierarchy_id,
            },
          )
          for crew in self.journey_crew_id.crew_ids
        ]
        self.crew_ids = crew_members

      # Poblar campos de descripción desde la plantilla del tipo de solicitud
      try:
        plain_text, html_text = self._generate_template_description()
        self.description_name = plain_text
        self.description_name_html = html_text
      except Exception:
        # Si hay error, dejar los campos como están
        pass

    else:
      self.reason_arrival_ids = [(5, 0, 0)]
      self.boat_registration = False
      self.eta_maneuvers = False
      self.etd_maneuvers = False
      self.send_email = False
      self.ek_group_mail_template_id = False
      self.ek_template_py3o_ids = [(5, 0, 0)]
      self.crew_ids = [(5, 0, 0)]
      self.ek_table_pay_crew_ids = [(5, 0, 0)]
      self.ek_service_request_report_line_ids = [(5, 0, 0)]
      self.ek_user_groups_reminder_ids = [(5, 0, 0)]
      self.char_name_buquer = False
      self.block_user_asig = False
      self.agent_user_id = False
      self.state_boats = False
      self.is_service_request = False
      self.eta = fields.Datetime.from_string('1900-01-01 00:00:00')
      self.ata = fields.Datetime.from_string('1900-01-01 00:00:00')
      self.etd = fields.Datetime.from_string('1900-01-01 00:00:00')
      self.atd = fields.Datetime.from_string('1900-01-01 00:00:00')
      self.type_event_boot = False
      self.type_event = False
      self.is_separate = False
      self.messege_war_doc = False
      self.report_tr_n_n = False
      self.ek_report_stages_mixin_ids = [(5, 0, 0)]
      self.ek_service_request_line_ids = [(5, 0, 0)]
      self.product_ids = [(5, 0, 0)]
      self.ek_produc_packages_goods_ids.unlink()

  def add_crew_pay(self):
    crew_members = [
      (
        0,
        0,
        {
          'name': crew.id,
          'vat': crew.vat,
          'ek_crew_member_hierarchy_id': crew.ek_crew_member_hierarchy_id.id,
          'nationality_id': crew.nationality_id.id,
          'ek_crew_member_hierarchy_title_id': crew.ek_crew_member_hierarchy_id.id,
          'amount': crew.fishing_bonus,
          'beneficiary': crew.name,
        },
      )
      for crew in self.journey_crew_id.crew_ids
    ]
    if self.type_id.crew_pay:
      self.ek_table_pay_crew_ids = [(5, 0, 0)]
      self.ek_table_pay_crew_ids = crew_members
    pass

  def send_group_email(
    self,
    template,
    partners,
    email_cc=None,
    attachment_ids=None,
    email_from=None,
    recipient_ids=None,
  ):
    email_values = {
      'subject': 'Document Confirmacion ' + ' ' + self.name,
      'body_html': template.body_html,
      'email_from': self.company_id.email
      or email_from
      or self.env.user.email
      or 'noreply@example.com',
      'email_to': ', '.join(partners.mapped('email')),
      'email_cc': email_cc or '',
      'auto_delete': False,
      'model': self._name,
      'res_id': self.id,
      'recipient_ids': recipient_ids,
      'attachment_ids': [(6, 0, attachment_ids)] if attachment_ids else [],
    }

    mail = self.env['mail.mail'].create(email_values)
    mail.send()
    self.message_post(
      body=f'Email sent to: {partners.email}. CC: {", ".join(recipient_ids.mapped("email"))}.',
      subject=email_values['subject'],
      message_type='comment',
      subtype_xmlid='mail.mt_comment',
    )
    return True

  def check_crew_hierarchy_numbers(self):
    for record in self:
      hierarchy_quantities = {}
      hierarchy_quantities_crew = {}

      # Obtener las jerarquías configuradas con sus cantidades mínimas
      for (
        hierarchy
      ) in record.ek_ship_registration_id.ek_crew_member_hierarchy_number_ids:
        if hierarchy.ek_crew_member_hierarchy_id:
          hierarchy_quantities[hierarchy.ek_crew_member_hierarchy_id] = (
            hierarchy.name
          )

      # Contar la cantidad de tripulantes por jerarquía
      # Contar la cantidad de tripulantes por jerarquía
      for crew_member in record.crew_ids:
        hierarchy = crew_member.ek_crew_member_hierarchy_id
        if hierarchy:
          if hierarchy not in hierarchy_quantities:
            hierarchy_quantities[hierarchy] = 0
          if hierarchy not in hierarchy_quantities_crew:
            hierarchy_quantities_crew[hierarchy] = 0
          hierarchy_quantities_crew[hierarchy] += 1
      # Validar que se cumpla el mínimo requerido por cada jerarquía
      for hierarchy_id, minimum_quantity in hierarchy_quantities.items():
        current_quantity = hierarchy_quantities_crew.get(hierarchy_id, 0)
        if current_quantity < minimum_quantity:
          # Aquí puedes manejar la validación de alguna manera, por ejemplo, lanzando una excepción
          raise ValidationError(
            f'No se cumple el mínimo requerido de {minimum_quantity} tripulantes para la jerarquía {hierarchy_id.name}.'
          )

  def ek_assignable_user_request(self):
    user_from = self.env.uid
    user_name = self.env['res.users'].browse(user_from)
    users = self.agent_user_id
    user_mentions = ', '.join(['@' + user.name for user in users])
    body = f'The user {user_name.name} , assigned you the request  {self.name} is close to its completion date'

    nocontent_body = ('%(body)s %(user_names)s') % {
      'body': body,
      'user_names': user_mentions,
    }

    for record in self:
      record.message_post(
        body=nocontent_body,
        message_type='comment',
        subtype_xmlid='mail.mt_comment',
        author_id=user_from,
        email_from=user_name.email or 'noreply@example.com',
        partner_ids=[user.partner_id.id for user in users],
      )

  def data_crew_history(self, paramts, rec_self):
    datas = {
      'partner_id': paramts.name.id,
      'vat': paramts.vat,
      'ship_name_id': rec_self.ek_ship_registration_id.id,
      'travel_id': rec_self.journey_crew_id.id,
      'ek_res_world_seaports_id': rec_self.journey_crew_id.ek_res_world_seaports_id.id,
      'ek_res_world_seaports_d_id': rec_self.journey_crew_id.ek_res_world_seaports_d_id.id,
      'ek_crew_member_hierarchy_arribo_id': paramts.ek_crew_member_hierarchy_title_id.id,
      'ek_boat_location_arribo_id': rec_self.ek_boat_location_id.id,
      'city_arribo_id': rec_self.city_id.id,
      'eta': rec_self.eta,
      'ata': rec_self.ata,
    }
    return datas

  def action_report_pdf_paramet(self):
    return self.env['ek.service.request.group'].search(
      [('ek_service_request_line_ids.show_by_default', '=', True)],
      order='order asc',
    )

  @api.depends('order_ids')
  def _compute_sale_order_count(self):
    for record in self:
      record.sale_order_count = record.env['sale.order'].search_count(
        [
          ('operation_request_id', '=', record.id),
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
        'default_operation_request_id': self.id,
      },
      'domain': [('operation_request_id', 'in', self.ids)],
      'target': 'current',
    }

  def action_open_documents_sale_order_views(self):
    self.ensure_one()
    return {
      'name': _('Sale Order'),
      'type': 'ir.actions.act_window',
      'res_model': 'sale.order',
      'view_mode': 'tree',
      'views': [
        (
          self.env.ref(
            'ek_l10n_shipping_operations.view_sale_order_tree_custom_ek'
          ).id,
          'tree',
        ),
      ],
      'domain': [('operation_request_id', 'in', self.ids)],
      'target': 'current',
      'context': {
        'create': False,
        'edit': False,
        'delete': False,
        'editable': 'bottom',
      },
    }

  def compute_account_invoice_state(self):
    pass
    # if self.invoice_count > 0:
    #     self.state = "invoiced"

  @api.depends('account_move_ids')
  def _compute_account_move_count(self):
    for record in self:
      record.invoice_count = record.env['account.move'].search_count(
        [
          ('operation_request_id', '=', record.id),
        ]
      )
      record.compute_account_invoice_state()

  def action_open_documents_account_move(self):
    self.ensure_one()
    return {
      'name': _('Invoice'),
      'type': 'ir.actions.act_window',
      'res_model': 'account.move',
      'view_mode': 'tree,form',
      'context': {
        'default_operation_request_id': self.id,
        'default_move_type': 'entry',
      },
      'domain': [('operation_request_id', 'in', self.ids)],
      'target': 'current',
    }

  @api.depends('product_ids')
  def _compute_purchase_count(self):
    for record in self:
      record.purchase_count = record.env['purchase.order'].search_count(
        [
          ('operation_request_id', '=', record.id),
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
        'default_ek_ship_registration_id': self.ek_ship_registration_id.id,
        'default_journey_crew_id': self.journey_crew_id.id,
        'default_operation_request_id': self.id,
      },
      'domain': [('operation_request_id', 'in', self.ids)],
      'target': 'current',
    }

  def action_open_documents_purchase_order_views(self):
    self.ensure_one()
    return {
      'name': _('Purchase Order'),
      'type': 'ir.actions.act_window',
      'res_model': 'purchase.order',
      'view_mode': 'tree',
      'views': [
        (
          self.env.ref(
            'ek_l10n_shipping_operations.view_purchase_order_tree_custom_ek'
          ).id,
          'tree',
        )
      ],
      'domain': [('operation_request_id', 'in', self.ids)],
      'target': 'current',
      'context': {'create': False, 'edit': False, 'delete': False},
    }

  def action_open_documents_related_request(self):
    self.ensure_one()
    return {
      'name': _('Related Request'),
      'type': 'ir.actions.act_window',
      'res_model': 'ek.operation.request',
      'view_mode': 'tree,form',
      'context': {
        'create': False,
        'delete': False,
        'default_parent_id': self.id,
        #'form_view_ref': 'ek_l10n_shipping_operations_charging_regimes.view_ek_boats_information_regimens_form',
        #'tree_view_ref': 'ek_l10n_shipping_operations.ek_boats_information_tree',
      },
      'domain': [('parent_id', 'in', self.ids)],
      'target': 'current',
    }

  def date_spanish_month(self, month):
    """Convierte el número del mes al nombre en español con capitalización apropiada.

    Args:
        month (int): Número del mes (1-12)

    Returns:
        str: Nombre del mes en español con primera letra mayúscula, o None si el mes no es válido
    """
    months = {
      1: 'enero',
      2: 'febrero',
      3: 'marzo',
      4: 'abril',
      5: 'mayo',
      6: 'junio',
      7: 'julio',
      8: 'agosto',
      9: 'septiembre',
      10: 'octubre',
      11: 'noviembre',
      12: 'diciembre',
    }
    return months.get(month) if month else None

  def date_today_report_request(self):
    user_tz = pytz.timezone(
      self.env.context.get('tz') or self.env.user.tz or 'UTC'
    )
    date_current = datetime.datetime.now(tz=user_tz).date()
    month = self.date_spanish_month(date_current.month)
    date_today = date_current.strftime('%d de {} del %Y'.format(month))
    date_and_city = self.city_id.name or ' ' + ' ' + date_today
    return date_and_city

  def action_cancel(self):
    for record in self:
      record.action_cancelle_request()
      record.validacion_cancel_regime_60()
      record.write({'processing_status': 'cancel'})
      
      # Cancelar registros de seguimiento de reembolsos al cancelar la solicitud
      self.env['ek.reimbursement.tracking'].cancel_from_operation_request(record)

    return super().action_cancel()

  def unlink(self):
    """Override unlink para eliminar registros de seguimiento de reembolsos"""
    for record in self:
      # Eliminar registros de seguimiento de reembolsos al eliminar la solicitud
      self.env['ek.reimbursement.tracking'].delete_from_operation_request(record)
    
    return super().unlink()

  def validacion_cancel_regime_60(self):
    self.ensure_one()
    for rec in self:
      if rec.ek_table_regimen_60_ids and rec.use_in_regimen_60:
        for line in rec.ek_table_regimen_60_ids:
          if line.quantity > 0:
            result = (
              line.ek_product_packagens_goods_id.delivery_product
              - line.quantity
            )
            line.ek_product_packagens_goods_id.write(
              {'delivery_product': result}
            )

  def action_cancelle_request(self):
    self.ensure_one()
    for record in self:
      purchase = record.env['purchase.order'].search(
        [('operation_request_id', '=', record.id)]
      )
      sale = record.env['sale.order'].search(
        [
          ('operation_request_id', '=', record.id),
        ]
      )
      for p in purchase:
        if p.state in ['sent', 'to approve', 'purchase']:
          raise UserError(
            _('You can not cancel a request with purchase if it is not draft')
          )
        else:
          p.button_cancel()
      for s in sale:
        if s.state in ['sent', 'sale']:
          raise UserError(
            _('You can not cancel a request with sale if it is not draft')
          )
        else:
          s.action_cancel()
      # record.state = "cancelled"

  @api.depends('eta_maneuvers', 'etd_maneuvers')
  def _compute_day_hour_eta(self):
    for record in self:
      if record.eta_maneuvers and record.etd_maneuvers:
        date_value = record.etd_maneuvers - record.eta_maneuvers
        days = date_value.days
        hours, seconds = divmod(date_value.seconds, 3600)
        record.day_hour_eta = str(days) + ' Days ' + str(hours) + ' Hours '
      else:
        record.day_hour_eta = ' 0 Days 0 Hours '

  @api.depends('ek_res_partner_id_certificate_id')
  def _filtered_domain_partner(self):
    domain = []
    for record in self:
      if self.ek_res_partner_id_certificate_id:
        partners = self.ek_res_partner_id_certificate_id.child_ids
        for partner in partners:
          domain.append(partner.id)
      record.ek_res_partner_id_certificate_ids = [(6, 0, domain)]

  @api.depends('permanence_period', 'estimated_actual_date')
  def _compute_duration(self):
    for record in self:
      if record.permanence_period and record.estimated_actual_date:
        permanence_period = fields.Date.from_string(record.permanence_period)
        estimated_actual_date = fields.Date.from_string(
          record.estimated_actual_date
        )
        record.duration = (estimated_actual_date - permanence_period).days
      else:
        record.duration = 0

  # amplicion o alcanze

  def search_dinamic_botton(self):
    for rec in self:
      for field in rec.type_id.ek_l10n_search_fields_mixin_ids:
        self.update_field_values(
          self, field.fields_relation_id, field.fields_change_id, field.field_id
        )

  def test(self):
    date = self.format_dates_to_string()
    print(date)

  def format_dates_to_string(self, date_value=None, apply_manual_day=False):
    """Formato de fecha para reportes"""
    # Si no se pasa parámetro, usar la fecha de emisión de la solicitud o la fecha actual
    if not date_value:
      date_value = self.date_start or fields.Date.today()

    # Si es un datetime, convertir a date
    if hasattr(date_value, 'date'):
      date_value = date_value.date()

    # Si es un string, intentar convertir a fecha
    if isinstance(date_value, str):
      try:
        from datetime import datetime

        date_value = datetime.strptime(date_value, '%Y-%m-%d').date()
      except (ValueError, TypeError):
        return date_value

    # Si es una fecha, formatear a español
    if hasattr(date_value, 'strftime'):
      try:
        # Si manual_day está activado, mostrar ____ en lugar del día
        if apply_manual_day:
          day_text = '____'
        else:
          day_text = str(date_value.day)

        month = self.date_spanish_month(date_value.month)
        year = date_value.year
        return f'{day_text} de {month} del {year}'
      except (AttributeError, TypeError):
        return str(date_value)

    return str(date_value) if date_value else ''

  def _update_self_attribute(self, xobject, field_name, update_field_name):
    value = self._get_object_attribute(xobject, field_name)
    if value:
      setattr(self, update_field_name, value)

  def change_boolean_stop_processo(self):  # desactivar
    self.write({'processo_notification': False})

  def change_boolean_start_processo(self):  # activo
    self.write({'processo_notification': True})

  def action_close(self):
    for rec in self:
      # VALIDACIÓN: Verificar que las fechas de arribo de la solicitud sean válidas para actualizar el viaje
      if rec.type_event_boot == 'arribo' and rec.journey_crew_id:
        journey = rec.journey_crew_id

        # Verificar que las fechas de arribo de la solicitud sean consistentes con las fechas de zarpe del viaje
        validation_errors = []

        # Verificar que ETA de la solicitud sea anterior a ETD del viaje
        if rec.eta and journey.etd and rec.eta >= journey.etd:
          validation_errors.append(
            f'ETA de la solicitud ({rec.eta.strftime("%d/%m/%Y %H:%M")}) debe ser anterior a ETD del viaje ({journey.etd.strftime("%d/%m/%Y %H:%M")})'
          )

        # Verificar que ATA de la solicitud sea anterior a ATD del viaje
        if rec.ata and journey.atd and rec.ata >= journey.atd:
          validation_errors.append(
            f'ATA de la solicitud ({rec.ata.strftime("%d/%m/%Y %H:%M")}) debe ser anterior a ATD del viaje ({journey.atd.strftime("%d/%m/%Y %H:%M")})'
          )

        # Si hay errores de validación, mostrar mensaje específico
        if validation_errors:
          error_details = '\n• '.join(validation_errors)
          raise UserError(
            _(
              'Las fechas de Arribo de esta solicitud no son válidas para actualizar el viaje.\n\n'
              'Problemas encontrados:\n• %s\n\n'
              'Solución: Modifique las fechas de Arribo en esta solicitud para que sean anteriores '
              'a las fechas de Zarpe del viaje "%s", o ajuste las fechas de Zarpe del viaje si es necesario.\n\n'
              'El arribo debe ocurrir antes que el zarpe.'
            )
            % (error_details, journey.name or journey.display_name)
          )

        # VALIDACIÓN ADICIONAL: Solo para solicitudes de ZARPE, verificar que ETD sea mayor que fecha actual
        # Para solicitudes de ARRIBO, esta validación no aplica porque ETD puede estar en el pasado
        if rec.type_event_boot == 'zarpe':
          current_datetime = fields.Datetime.now()

          if journey.etd and journey.etd <= current_datetime:
            raise UserError(
              _(
                'No se puede cerrar la solicitud de zarpe. '
                'Los valores de zarpe del viaje (ETD: %s) deben ser mayores que la fecha actual (%s). '
                'Por favor, actualice los valores del zarpe del viaje antes de continuar.'
              )
              % (
                journey.etd.strftime('%d/%m/%Y %H:%M')
                if journey.etd
                else 'No definido',
                current_datetime.strftime('%d/%m/%Y %H:%M'),
              )
            )

      rec.end_request_datetime = fields.Datetime.now()
      duration = rec.end_request_datetime - rec.create_date
      rec.days_time_request_results = duration.total_seconds() / 3600

      # Actualizar fechas del viaje según el tipo de solicitud
      # IMPORTANTE: Las fechas del viaje (pronósticos) se actualizan con las fechas REALES de la solicitud
      # Esto asegura que el viaje refleje la realidad confirmada, no solo estimaciones
      if rec.journey_crew_id and rec.type_event_boot:
        current_datetime = fields.Datetime.now()

        if rec.type_event_boot == 'arribo':
          # Para solicitudes de arribo, actualizar ETA y ATA del viaje con las fechas REALES
          journey_update_vals = {}

          # ACTUALIZAR ETA del viaje con la fecha REAL de la solicitud
          # Esto reemplaza el pronóstico con la fecha real confirmada
          if rec.eta:
            journey_update_vals['eta'] = rec.eta
          elif (
            not rec.journey_crew_id.eta
            or rec.journey_crew_id.eta.date() == fields.Date.today()
          ):
            # Solo usar fecha actual si no hay ETA en la solicitud
            journey_update_vals['eta'] = current_datetime

          # ACTUALIZAR ATA del viaje con la fecha REAL de la solicitud
          # Esto reemplaza el pronóstico con la fecha real confirmada
          if rec.ata:
            journey_update_vals['ata'] = rec.ata
          elif not rec.journey_crew_id.ata:
            # Solo usar fecha actual si no hay ATA en la solicitud
            journey_update_vals['ata'] = current_datetime

          if journey_update_vals:
            try:
              rec.journey_crew_id.write(journey_update_vals)

              # Agregar mensaje al chat del viaje
              rec._add_journey_update_message(
                rec.journey_crew_id, journey_update_vals, 'arribo'
              )
            except Exception as e:
              # Error al actualizar viaje
              raise

          # ACTUALIZAR RECURSOS DEL VIAJE (COMBUSTIBLE, GASOLINA, AGUA)
          # Para solicitudes de arribo, actualizar los campos de arribo del viaje
          journey_resource_vals = {}

          # DEBUG: Log valores de recursos

          # Actualizar combustible de arribo (usar campos directos)
          if rec.fuel and rec.fuel > 0:
            journey_resource_vals['fuel'] = rec.fuel

          # Actualizar gasolina de arribo (usar campos directos)
          if rec.gasoline and rec.gasoline > 0:
            journey_resource_vals['gasoline'] = rec.gasoline

          # Actualizar agua de arribo (usar campos directos)
          if rec.water and rec.water > 0:
            journey_resource_vals['water'] = rec.water

          if journey_resource_vals:
            try:
              rec.journey_crew_id.write(journey_resource_vals)

              # Agregar mensaje al chat del viaje para recursos
              rec._add_journey_update_message(
                rec.journey_crew_id, journey_resource_vals, 'arribo'
              )
            except Exception as e:
              raise UserError(
                _(
                  'Error al actualizar los recursos del viaje.\n\n'
                  'Detalles del error: %s\n\n'
                  'Por favor, contacte al administrador del sistema.'
                )
                % str(e)
              )

        elif rec.type_event_boot == 'zarpe':
          # Para solicitudes de zarpe, actualizar ETD y ATD del viaje con las fechas REALES
          journey_update_vals = {}

          # ACTUALIZAR ETD del viaje con la fecha REAL de la solicitud
          # Esto reemplaza el pronóstico con la fecha real confirmada
          if rec.etd:
            journey_update_vals['etd'] = rec.etd
          elif (
            not rec.journey_crew_id.etd
            or rec.journey_crew_id.etd.date() == fields.Date.today()
          ):
            # Solo usar fecha actual si no hay ETD en la solicitud
            journey_update_vals['etd'] = current_datetime

          # ACTUALIZAR ATD del viaje con la fecha REAL de la solicitud
          # Esto reemplaza el pronóstico con la fecha real confirmada
          if rec.atd:
            journey_update_vals['atd'] = rec.atd
          else:
            # Si no hay ATD en la solicitud, usar fecha actual
            journey_update_vals['atd'] = current_datetime

          if journey_update_vals:
            rec.journey_crew_id.write(journey_update_vals)
            # Agregar mensaje al chat del viaje
            rec._add_journey_update_message(
              rec.journey_crew_id, journey_update_vals, 'zarpe'
            )

          # ACTUALIZAR RECURSOS DEL VIAJE (COMBUSTIBLE, GASOLINA, AGUA)
          # Para solicitudes de zarpe, actualizar los campos de zarpe del viaje
          journey_resource_vals = {}

          # Actualizar combustible de zarpe (usar campos directos)
          if rec.fuel and rec.fuel > 0:
            journey_resource_vals['fuel_zarpe'] = rec.fuel

          # Actualizar gasolina de zarpe (usar campos directos)
          if rec.gasoline and rec.gasoline > 0:
            journey_resource_vals['gasoline_zarpe'] = rec.gasoline

          # Actualizar agua de zarpe (usar campos directos)
          if rec.water and rec.water > 0:
            journey_resource_vals['water_zarpe'] = rec.water

          if journey_resource_vals:
            try:
              rec.journey_crew_id.write(journey_resource_vals)

              # Agregar mensaje al chat del viaje para recursos
              rec._add_journey_update_message(
                rec.journey_crew_id, journey_resource_vals, 'zarpe'
              )
            except Exception as e:
              raise UserError(
                _(
                  'Error al actualizar los recursos del viaje.\n\n'
                  'Detalles del error: %s\n\n'
                  'Por favor, contacte al administrador del sistema.'
                )
                % str(e)
              )

      if rec.type_id.is_service_request or rec.type_id.is_service_refunf:
        rec.generate_pvo(rec.stage_id)
        rec.ek_service_request_line_ids.unlink()
        rec.product_ids.unlink()
      if rec.type_id.fields_ids:
        for field in rec.type_id.fields_ids.filtered(
          lambda line: any(
            stage.id in rec.stage_id.ids for stage in line.stage_id
          )
        ):
          name_f = field.fields_relation_id.name
          related_obj = getattr(rec, name_f, None)
          if related_obj:
            rec._set_object_attributes(
              related_obj, [field.fields_change_id.name], [field.field_id.name]
            )
      if rec.stage_id.show_close_button or rec.stage_id.confirm_stage:
        rec.write({'processing_status': 'done'})
        rec._change_ship_state_once()
    return super(ek_operation_request, self).action_close()

  def _change_ship_state_once(self):
    """Cambiar estado del buque SOLO cuando processing_status es 'done'"""
    for rec in self:
      # VERIFICACIÓN PRINCIPAL: Solo proceder si processing_status es 'done'
      if rec.processing_status != 'done':
        continue

      ship = rec.ek_ship_registration_id
      if not ship or not rec.type_event_boot:
        continue

      # Verificar si YA existe un mensaje para esta solicitud ESPECÍFICA
      # Buscar mensajes en el chatter del buque que contengan esta solicitud específica
      existing_messages = ship.message_ids.filtered(
        lambda m: f'por solicitud {rec.display_name} (Estado del Barco)'
        in (m.body or '')
      )

      if existing_messages:
        # Ya existe un mensaje para ESTA solicitud específica, no duplicar
        continue

      old_state = ship.state_boats
      new_state = None

      # Determinar el nuevo estado según el tipo de evento
      if rec.type_event_boot == 'zarpe':
        new_state = 'sailing'
        old_state_text = 'En Puerto' if old_state == 'port' else 'Navegando'
        new_state_text = 'Navegando'
      elif rec.type_event_boot == 'arribo':
        new_state = 'port'
        old_state_text = 'Navegando' if old_state == 'sailing' else 'En Puerto'
        new_state_text = 'En Puerto'

      # Solo cambiar si el estado es diferente
      if new_state and old_state != new_state:
        # Usar savepoint para manejar la transacción como en account_move_line.py
        with self.env.cr.savepoint():
          try:
            # Cambiar el estado del buque
            ship.state_boats = new_state

            # Crear mensaje de tracking usando la técnica del account_move_line.py
            from markupsafe import Markup
            from odoo.tools import html_escape

            display_name_safe = html_escape(rec.display_name)
            old_state_safe = html_escape(old_state_text)
            new_state_safe = html_escape(new_state_text)

            tracking_html = f"""
            <div class="position-relative d-flex">
              <div class="o-mail-Message-content o-min-width-0">
                <div class="o-mail-Message-textContent position-relative d-flex">
                  <div>
                    <ul class="mb-0 ps-4">
                      <li class="o-mail-Message-tracking mb-1" role="group">
                        <span class="o-mail-Message-trackingOld me-1 px-1 text-muted fw-bold">{old_state_safe}</span>
                        <i class="o-mail-Message-trackingSeparator fa fa-long-arrow-right mx-1 text-600"></i>
                        <span class="o-mail-Message-trackingNew me-1 fw-bold text-info">{new_state_safe}</span>
                        <span class="o-mail-Message-trackingField ms-1 fst-italic text-muted">por solicitud {display_name_safe} (Estado del Barco)</span>
                      </li>
                    </ul>
                  </div>
                </div>
              </div>
            </div>
            """

            # Enviar mensaje al chatter del buque
            ship.message_post(
              body=Markup(tracking_html),
              message_type='notification',
              subtype_xmlid='mail.mt_activities',
            )

          except Exception as e:
            # Error changing ship state
            # Re-raise para que se maneje el rollback
            raise

  def _add_journey_update_message(
    self, journey, field_updates, request_type
  ):
    """
    Agrega un mensaje al chat del viaje cuando se actualizan fechas o recursos.

    Args:
        journey: Objeto del viaje (ek.boats.information)
        field_updates: Diccionario con los campos actualizados (fechas y recursos)
        request_type: Tipo de solicitud ('arribo' o 'zarpe')
    """
    try:
      # Verificar si YA existe un mensaje para esta solicitud ESPECÍFICA
      # Buscar mensajes en el chatter del viaje que contengan esta solicitud específica
      existing_messages = journey.message_ids.filtered(
        lambda m: f'por solicitud {self.display_name} (Actualización de Viaje)'
        in (m.body or '')
      )

      if existing_messages:
        # Ya existe un mensaje para ESTA solicitud específica, no duplicar
        return

      # Crear mensaje de tracking usando la técnica del account_move_line.py
      display_name_safe = html_escape(self.display_name)

      # Determinar el texto del tipo de solicitud
      if request_type == 'arribo':
        request_type_text = 'Arribo'
      elif request_type == 'zarpe':
        request_type_text = 'Zarpe'
      else:
        request_type_text = request_type.title()

      # Crear lista de valores actualizados (fechas y recursos)
      update_list = []
      for field, value in field_updates.items():
        # Manejar campos de fechas
        if field == 'eta':
          update_list.append(f'ETA: {value.strftime("%d/%m/%Y %H:%M")}')
        elif field == 'ata':
          update_list.append(f'ATA: {value.strftime("%d/%m/%Y %H:%M")}')
        elif field == 'etd':
          update_list.append(f'ETD: {value.strftime("%d/%m/%Y %H:%M")}')
        elif field == 'atd':
          update_list.append(f'ATD: {value.strftime("%d/%m/%Y %H:%M")}')
        # Manejar campos de recursos
        elif field == 'fuel':
          update_list.append(f'Combustible Arribo: {value:.2f}')
        elif field == 'gasoline':
          update_list.append(f'Gasolina Arribo: {value:.2f}')
        elif field == 'water':
          update_list.append(f'Agua Arribo: {value:.2f}')
        elif field == 'fuel_zarpe':
          update_list.append(f'Combustible Zarpe: {value:.2f}')
        elif field == 'gasoline_zarpe':
          update_list.append(f'Gasolina Zarpe: {value:.2f}')
        elif field == 'water_zarpe':
          update_list.append(f'Agua Zarpe: {value:.2f}')

      updates_text = ', '.join(update_list)

      tracking_html = f"""
      <div class="position-relative d-flex">
        <div class="o-mail-Message-content o-min-width-0">
          <div class="o-mail-Message-textContent position-relative d-flex">
            <div>
              <span class="o-mail-Message-trackingField me-1 fw-bold text-info">Actualización de Viaje</span>
              <span class="o-mail-Message-trackingField ms-1 fst-italic text-muted">por solicitud {display_name_safe} ({request_type_text})</span>
              <ul class="mb-0 ps-4">
                <li class="o-mail-Message-tracking mb-1" role="group">
                  <span class="o-mail-Message-trackingField me-1 text-muted">Valores actualizados:</span>
                  <span class="o-mail-Message-trackingNew me-1 fw-bold text-success">{updates_text}</span>
                </li>
              </ul>
            </div>
          </div>
        </div>
      </div>
      """

      # Enviar mensaje al chatter del viaje
      journey.message_post(
        body=Markup(tracking_html),
        message_type='notification',
        subtype_xmlid='mail.mt_activities',
      )

    except Exception as e:
      # Error adding journey date update message
      # No re-raise para no interrumpir el flujo principal
      pass

  def action_confirm(self):
    """Confirma la solicitud de operación"""
    for record in self:
      # Validaciones antes de confirmar
      if not record.type_id:
        raise UserError(
          _('The operation type is required to confirm the request')
        )
      if not record.ek_ship_registration_id:
        raise UserError(
          _('The ship registration is required to confirm the request')
        )

      # Ejecutar lógica de confirmación específica del tipo
      if record.type_id.has_crew and not record.crew_ids:
        raise UserError(
          _('Crew information is required for this type of request')
        )

      # NUEVA VALIDACIÓN: Verificar que los valores de zarpe del viaje sean válidos para solicitudes de arribo
      if record.type_event_boot == 'arribo' and record.journey_crew_id:
        journey = record.journey_crew_id

        # Verificar que ETD del viaje sea mayor que ETA del viaje
        if journey.etd and journey.eta and journey.etd <= journey.eta:
          raise UserError(
            _(
              'No se puede confirmar la solicitud de arribo. '
              'Los valores de zarpe del viaje (ETD: %s) deben ser mayores que los de arribo (ETA: %s). '
              'Por favor, actualice los valores del zarpe del viaje antes de continuar.'
            )
            % (
              journey.etd.strftime('%d/%m/%Y %H:%M')
              if journey.etd
              else 'No definido',
              journey.eta.strftime('%d/%m/%Y %H:%M')
              if journey.eta
              else 'No definido',
            )
          )

        # Verificar que ATD del viaje sea mayor que ATA del viaje
        if journey.atd and journey.ata and journey.atd <= journey.ata:
          raise UserError(
            _(
              'No se puede confirmar la solicitud de arribo. '
              'Los valores de zarpe del viaje (ATD: %s) deben ser mayores que los de arribo (ATA: %s). '
              'Por favor, actualice los valores del zarpe del viaje antes de continuar.'
            )
            % (
              journey.atd.strftime('%d/%m/%Y %H:%M')
              if journey.atd
              else 'No definido',
              journey.ata.strftime('%d/%m/%Y %H:%M')
              if journey.ata
              else 'No definido',
            )
          )

      # Marcar como confirmado
      record.write(
        {'has_confirmed_type': True, 'processing_status': 'developing'}
      )
    return True

  @api.model
  def cron_create_activity_recordation_maanagent(self):
    operation_requests = self.search(
      [
        ('stage_id.confirm_stage', '=', True),
        ('processo_notification', '=', True),
      ]
    )
    for request in operation_requests:
      try:
        request.create_activity_recordation_maanagent()
      except Exception:
        pass

  def create_activity_recordation_maanagent(self):
    send_settings = self.env['ek.setting.send.notice'].search([])

    for doc in self.ek_management_document_ids.filtered(
      lambda r: r.has_requires_reminder
    ):
      if not doc.date_end:
        continue  # Saltar documentos sin fecha de finalización

      for send in send_settings:
        date_expiration = doc.date_end
        date = datetime.date.today()
        date_activity = False
        summary = None

        if (
          send.document_status == 'expired'
        ):  # Expirado, días después de expirar
          target_date = date - date_expiration
          if target_date.days >= send.days:
            date_activity = True
            summary = f'EXPIRADO  A reminder was created for request {self.name}, Document {doc.name} is close to its completion date'

            doc.write({'document_status': 'expired'})

        elif (
          send.document_status == 'to_wi'
        ):  # Por vencer, días antes de expirar
          target_date = date - date_expiration
          if target_date.days >= send.days and target_date.days < 0:
            date_activity = True
            summary = f'POR VENCER  A reminder was created for request {self.name}, Document {doc.name} is close to its completion date'

            doc.write({'document_status': 'to_wi'})

        if date_activity:
          users = self.ek_user_groups_reminder_ids.user_ids
          self.send_user_reminder(body=summary, users=users)

  def send_user_reminder(self, body=None, users=None):
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

  @api.depends(
    'ek_table_fuel_ids', 'ek_table_gasoline_ids', 'ek_table_water_ids'
  )
  def _computed_total_table(self):
    for record in self:
      record.total_fuel = sum(record.ek_table_fuel_ids.mapped('quantity'))
      record.total_gasoline = sum(
        record.ek_table_gasoline_ids.mapped('quantity')
      )
      record.total_water = sum(record.ek_table_water_ids.mapped('quantity'))

  ################################################################
  def _compute_count_childs(self):
    for rec in self:
      rec.count_childs = len(rec.child_ids)

  def generate_sequence_manifest(self):
    for record in self:
      if not record.ek_manifest_record_id:
        value = {
          'name': self.env['ir.sequence'].next_by_code(
            'ek.bl.manifest.record.sequence'
          )
          or '/',
          'ek_ship_registration_id': record.ek_ship_registration_id.id,
          'journey_crew_id': record.journey_crew_id.id,
        }
        record.ek_manifest_record_id = self.env['ek.bl.manifest.record'].create(
          value
        )
      else:
        raise UserError(
          _('leave the field without data to generate the sequence')
        )

  @api.depends('ek_produc_packages_goods_ids')
  def product_depends_packages_goods(self):
    for rec in self:
      rec.gross_weight = (
        sum(rec.mapped('ek_produc_packages_goods_ids.gross_weight')) or 0
      )
      rec.product_weight_in_lbs = (
        self.env['ir.config_parameter']
        .sudo()
        .get_param('product.weight_in_lbs')
      )

  @api.depends('type_id')
  def _compute_display_dinamic_field(self):
    for rec in self:
      _jfields = {}
      if rec.type_id:
        for _field in rec.type_id.fields_ids:
          if _field.field_id:
            _jfields.update(
              {
                'show_%s' % _field.field_id.name: True,
                'required_%s' % _field.field_id.name: _field.has_required,
                'domain_%s' % _field.field_id.name: _field.definition_domain
                and _field.definition_domain
                or [('1', '=', '1')],
              }
            )

      rec.display_dinamic_field = _jfields

  def copy(self, default=None):
    default = dict(default or {})
    if self.env.context.get('copy_request_self'):
      default['name'] = self.name
    else:
      default['name'] = (
        self.env['ir.sequence'].next_by_code('ek.operation.request.sequence')
        or '/'
      )
    return super(ek_operation_request, self).copy(default)

  validate_correction_request = fields.Boolean(copy=False)
  has_confirmed_type = fields.Boolean(
    string='Has Confirmed Type', copy=False, default=False
  )

  def copy_request_self(self):
    # new_object =self.copy()
    # new_object.write({
    #     "parent_id": self.id,
    # })
    wizard = self.env.ref(
      'ek_l10n_shipping_operations.view_ek_generate_correction_document_form'
    )
    return {
      'name': _('Copy Request'),
      'type': 'ir.actions.act_window',
      'res_model': 'ek.generate.correction.document',
      'view_mode': 'form',
      #'res_id': new_object.id,
      'view_id': wizard.id,
      'views': [(wizard.id, 'form')],
      'target': 'new',
      'context': {'default_operation_request_id': self.id},
    }

  def generate_manual_trade_number(self):
    wizard = self.env.ref(
      'ek_l10n_shipping_operations.view_ek_generate_shipping_trade_numbers_form_related'
    )
    return {
      'name': _('Generate Trade Number'),
      'type': 'ir.actions.act_window',
      'res_model': 'ek.generate.shipping.trade.numbers.wizard',
      'view_mode': 'form',
      'view_id': wizard.id,
      'views': [(wizard.id, 'form')],
      'target': 'new',
      'context': {'default_operation_request_id': self.id},
    }

  def generate_shipping_trade_numbers(self, note):
    self.ensure_one()
    ObjectTrade = self.env['ek.shipping.trade.numbers']
    if not self.company_id.trade_sequence_id:
      raise UserError(_('Please configure the sequence in the company'))

    ObjectTrade.create(
      {
        'request_id': self.id,
        'note': note,
        'ship_registration_id': self.ek_ship_registration_id.id,
        'boats_information_id': self.journey_crew_id.id,
        'type_id': self.type_id.id,
        'stage_id': self.stage_id.id,
        'user_id': self.env.user.id,
        'date': fields.Date.context_today(self),
        'name': self.company_id.trade_sequence_id.next_by_id(),
      }
    )

  def _generate_next_request(self):
    for rec in self:
      if (
        self.type_id
        and self.type_id.generate_for_stage
        and self.type_id.sequence_ids
      ):
        sequence_ids = self.type_id.sequence_ids
        next_request = sequence_ids[0]
        if rec.count_childs > 0:
          _requests = rec.child_ids.filtered(
            lambda a: not a.stage_id.canceled_stage
          )
          if _requests:
            _rid = _requests[-1].type_id
            pos = 0
            for sq in sequence_ids:
              pos += 1
              if sq.type_request_generate_id == _rid:
                break
            if len(sequence_ids) > pos:
              next_request = sequence_ids[pos]
            else:
              # next_request = sequence_ids[-1]
              next_request = False

        if next_request and next_request.auto_generate:
          new_request = self.copy()
          new_request.write(
            {
              'parent_id': self.id,
              'type_id': next_request.type_request_generate_id.id,
            }
          )
          new_request.onchange_ek_type_request()

          if next_request.generate_new_number:
            new_request.with_context(foce_sequence=True).generate_new_number(
              new_request, {}
            )

        # if not next_request and rec.state == "confirmed" and self.env.context.get("action_done", False):
        #     rec.write({'processing_status': 'done'})

  def action_open_wizard_export(self):
    self.ensure_one()
    if self.assigned_regimen_70 and not self.id_bl:
      raise UserError(_('Please generate the ID BL for this request'))
    return {
      'name': _('Importar Datos de Embarque'),
      'type': 'ir.actions.act_window',
      'res_model': 'import.excel.data.embark.wizard',
      'view_mode': 'form',
      'view_id': self.env.ref(
        'ek_l10n_shipping_operations.import_excel_data_embark_wizard_form'
      ).id,
      'context': {
        'default_ek_operation_request_id': self.id,
      },
      'target': 'new',
    }

  def create_crew_access_port(self):
    for record in self:
      if record.journey_crew_id:
        self.ek_acces_port_table_float_ids = [(5, 0, 0)]
        self.ek_table_pay_crew_ids = [(5, 0, 0)]
        crew_members = [
          (
            0,
            0,
            {
              'res_partner_id': crew.id,
              'dni_passport': crew.vat,
              'function': crew.ek_crew_member_hierarchy_id.name,
            },
          )
          for crew in self.journey_crew_id.crew_ids
        ]
        record.ek_acces_port_table_float_ids = crew_members

  def create_notification_record_request(self):
    """Crea un registro de notificación para seguimiento de documentos de gestión"""
    for record in self:
      # Validaciones básicas
      if not record.ek_ship_registration_id:
        raise UserError(_('El registro del barco es obligatorio'))
      if not record.journey_crew_id:
        raise UserError(_('El viaje es obligatorio'))
      if not record.type_id:
        raise UserError(_('El tipo de operación es obligatorio'))
      if not record.estimated_actual_date or not record.permanence_period:
        raise UserError(
          _('The estimated actual date and permanence period are required')
        )
      if record.estimated_actual_date < record.permanence_period:
        raise UserError(
          _(
            'The estimated actual date must be greater than the permanence period'
          )
        )

      # Crear el nombre del documento de notificación
      notification_name = (
        f'{record.type_id.name} - {record.name} - '
        f'{record.ek_ship_registration_id.name} - {record.journey_crew_id.name}'
      )

      # Crear el registro de documento de gestión
      document_values = {
        'name': notification_name,
        'date_end': record.estimated_actual_date,
        'date_start': record.permanence_period,
        'ek_operation_request_id': record.id,
        'has_requires_reminder': True,
        'type_document': 'Notification Request',
      }

      self.env['ek.management.document'].create(document_values)

      # Mensaje de confirmación
      record.message_post(
        body=f'✅ Notification record created: {notification_name}',
        message_type='comment',
        subtype_xmlid='mail.mt_note',
      )

      return {
        'type': 'ir.actions.client',
        'tag': 'display_notification',
        'params': {
          'title': _('Notification Created'),
          'message': f'Notification record created successfully: {notification_name}',
          'type': 'success',
          'sticky': False,
        },
      }

  def action_next_stage(self):
    """Método para avanzar al siguiente stage"""

    for rec in self:
      time_stage = self.stage_id

      # ANTES de cambiar de etapa, guardar estado actual de notificaciones
      if rec.notification_ids:
        current_notifications = []
        for notif in rec.notification_ids:
          current_notifications.append(
            {
              'user_id': notif.user_id.id,
              'notify': notif.notify,
              'create_activity': notif.create_activity,
            }
          )
        # Almacenar en una caché temporal usando el ID del registro
        if not hasattr(self.__class__, '_notification_cache'):
          self.__class__._notification_cache = {}
        self.__class__._notification_cache[rec.id] = current_notifications

      # PRIMERO: Ejecutar notificaciones/actividades ANTES del cambio de etapa
      rec.notify_schedule_custom()

      # SEGUNDO: Validar campos requeridos
      value = rec.action_requeired_stage_fields(rec.stage_id)
      if value:
        from odoo.exceptions import UserError

        raise UserError(
          _('Please fill the following required fields:\n\n%s')
          % ('\n'.join(value))
        )
      rec.write({'block_type': True})

      # TERCERO: Cambiar a la siguiente etapa (SIN notify_schedule del mixin)
      actual_stage = rec.stage_id
      stage = False
      if actual_stage and rec.type_id.stage_ids:
        next_stage = rec.type_id.stage_ids.filtered(
          lambda r: r.sequence > actual_stage.sequence and not r.canceled_stage
        )
        if next_stage:
          stage = next_stage[0]
          rec.write({'stage_id': stage.id})
          rec.type_id.action_close_for_stage(rec, stage)
          # NO llamar notify_schedule del mixin aquí

      # CUARTO: Actualizar configuración para la próxima etapa
      rec.update_notification_status()

      if stage.confirm_stage and not rec.has_confirmed_type:
        rec.action_confirm()
        rec.write({'has_confirmed_type': True})
        if (
          rec.type_id.has_trade_numeber
          and rec.type_id.select_type_trade_number == '2'
        ):
          rec.generate_shipping_trade_numbers(
            _('Generate Shipping Trade Numbers for confirmation')
          )
      if (
        rec.type_id.has_trade_numeber
        and rec.type_id.select_type_trade_number == '1'
        and rec.type_id.stage_trade_ids
      ):
        if rec.type_id.stage_trade_ids.filtered(
          lambda x: x.id == rec.stage_id.id
        ):
          rec.generate_shipping_trade_numbers(
            _(
              'Automatic Generate Shipping Trade Numbers for stage: %s'
              % rec.stage_id.name
            )
          )
      if rec.type_id.is_service_request or rec.type_id.is_service_refunf:
        
        type = rec.type_id
        
        # PASO 1: Generar órdenes para la etapa que estamos SALIENDO (si hay líneas)
        if rec.ek_service_request_line_ids or rec.product_ids:
          rec.generate_pvo(time_stage)
          rec.ek_service_request_line_ids.unlink()
          rec.product_ids.unlink()
        
        # PASO 2: Crear líneas para la etapa que estamos ENTRANDO
        if type.is_service_request:
          rec.action_fill_pov_line(type, stage, 'service')
        if type.is_service_refunf:
          rec.action_fill_pov_line(type, stage, 'purchase')

      if rec.type_id.fields_ids:
        for field in rec.type_id.fields_ids.filtered(
          lambda line: any(
            stage.id in time_stage.ids for stage in line.stage_id
          )
        ):
          name_f = field.fields_relation_id.name
          related_obj = getattr(rec, name_f, None)
          if related_obj:
            rec._set_object_attributes(
              related_obj, [field.fields_change_id.name], [field.field_id.name]
            )
      if rec.journey_crew_id and rec.type_event_boot not in ['zarpe', 'arribo']:
        rec.journey_crew_id.write({'state': 'process'})
      
      # CREAR SEGUIMIENTO DE REEMBOLSOS automáticamente en cada cambio de stage
      # También se crea desde borrador para pronosticar compras tempranas
      if rec.type_id.is_service_refunf:
        rec._create_reimbursement_tracking_records()

      # Cambiar estado del buque al llegar a la etapa final
      # La verificación de condiciones se hace dentro del método
      rec._change_ship_state_once()

  def _create_reimbursement_tracking_records(self):
    """Crear registros de seguimiento de reembolsos automáticamente"""
    if not self.type_id.is_service_refunf:
      return

    # Usar el nuevo método para actualizar desde cambio de stage
    self.env['ek.reimbursement.tracking'].update_from_stage_change(self)

  def action_fill_pov_line(self, type_id, state, service_type):
    """Llenar líneas de productos/servicios según el tipo y estado"""
    if service_type == 'service':
      # Llenar líneas de servicio
      existing_service_lines = self.ek_service_request_line_ids.filtered(
        lambda line: line.product_id
        in type_id.ek_product_request_service_order_ids.mapped('product_id')
      )
      for line in type_id.ek_product_request_service_order_ids.filtered(
        lambda line: any(stage.id in state.ids for stage in line.stage_ids)
      ):
        existing_line = existing_service_lines.filtered(
          lambda line_item: line_item.product_id == line.product_id
        )
        if existing_line:
          existing_line.update(
            {
              'price_unit': line.price_unit,
              'product_qty': line.product_qty,
              'name': line.name,
              'edit_price': line.edit_price,
            }
          )
        else:
          self.ek_service_request_line_ids = [
            (
              0,
              0,
              {
                'product_id': line.product_id.id,
                'price_unit': line.price_unit,
                'product_qty': line.product_qty,
                'name': line.name,
                'edit_price': line.edit_price,
              },
            )
          ]

      # Eliminar líneas que no están en el nuevo tipo de solicitud
      self.ek_service_request_line_ids = [
        (2, line.id)
        for line in self.ek_service_request_line_ids
        if line.product_id
        not in type_id.ek_product_request_service_order_ids.mapped('product_id')
      ]

    if service_type == 'purchase':
      # Obtener todos los productos configurados para este tipo
      all_products = type_id.ek_product_request_service_purchase_ids
      
      # Filtrar productos para esta etapa específica
      products_for_stage = type_id.ek_product_request_service_purchase_ids.filtered(
        lambda line: any(stage.id in state.ids for stage in line.stage_ids)
      )
      # Actualizar product_ids
      existing_purchase_lines = self.product_ids.filtered(
        lambda line: line.product_id
        in type_id.ek_product_request_service_purchase_ids.mapped('product_id')
      )
      
      for line in products_for_stage:
        existing_line = existing_purchase_lines.filtered(
          lambda line_item: line_item.product_id == line.product_id
        )
        if existing_line:
          existing_line.update(
            {
              'price_unit': line.price_unit,
              'product_qty': line.product_qty,
              'name': line.name,
              'supplier_id': line.supplier_id,
              'edit_price': line.edit_price,
            }
          )
        else:
          self.product_ids = [
            (
              0,
              0,
              {
                'product_id': line.product_id.id,
                'price_unit': line.price_unit,
                'product_qty': line.product_qty,
                'name': line.name,
                'supplier_id': line.supplier_id.id,
                'edit_price': line.edit_price,
              },
            )
          ]

      # Eliminar líneas que no están en el nuevo tipo de solicitud
      self.product_ids = [
        (2, line.id)
        for line in self.product_ids
        if line.product_id
        not in type_id.ek_product_request_service_purchase_ids.mapped(
          'product_id'
        )
      ]

  def generate_pvo(self, creation_status):
    """Generar Purchase/Sale Orders"""
    
    for record in self:
      type = record.type_id
      if type.is_service_request and record.ek_service_request_line_ids:
        sale_order_obj = self.env['sale.order']
        sale_order_vals = {
          'partner_id': self.res_partner_id.id,
          'ek_ship_registration_id': self.ek_ship_registration_id.id,
          'journey_crew_id': self.journey_crew_id.id,
          'operation_request_id': self.id,
          'note': record.description_name,
          'creation_status': creation_status.id,
        }
        create_sale_order = sale_order_obj.create(sale_order_vals)

        sale_order_line_obj = self.env['sale.order.line']

        data_sale_order_line_vals = []
        for ln in self.ek_service_request_line_ids:
          product_id = ln.product_id
          sale_order_line_vals = {
            'order_id': create_sale_order.id,
            'name': product_id.name,
            'product_id': product_id.product_variant_id.id,
            'product_uom_qty': ln.product_qty,
            'price_unit': ln.price_unit,
            'analytic_distribution': {
              record.ek_ship_registration_id.analytic_account_id.id: 100
            },
          }

          # Agregar product_template_id solo si el campo existe en el modelo
          if 'product_template_id' in sale_order_line_obj._fields:
            sale_order_line_vals['product_template_id'] = product_id.id

          data_sale_order_line_vals.append(sale_order_line_vals)
        sale_order_line_obj.create(data_sale_order_line_vals)

      # Generar Purchase Orders para reembolsos
      # Solo generar órdenes de compra si hay productos configurados
      # Si no hay productos, simplemente no generar órdenes (no es un error)
      if type.is_service_refunf and record.product_ids:
        purchase_order_obj = self.env['purchase.order']

        # Agrupar por proveedor
        suppliers = record.product_ids.mapped('supplier_id')
        
        for supplier in suppliers:
          supplier_products = record.product_ids.filtered(
            lambda x: x.supplier_id == supplier
          )

          purchase_order_vals = {
            'partner_id': supplier.id,
            'ek_ship_registration_id': self.ek_ship_registration_id.id,
            'journey_crew_id': self.journey_crew_id.id,
            'operation_request_id': self.id,
            'notes': record.description_name,
            'creation_status': creation_status.id,
          }
          create_purchase_order = purchase_order_obj.create(purchase_order_vals)

          purchase_order_line_obj = self.env['purchase.order.line']

          data_purchase_order_line_vals = []
          for ln in supplier_products:
            product_id = ln.product_id
            purchase_order_line_vals = {
              'order_id': create_purchase_order.id,
              'name': product_id.name,
              'product_id': product_id.product_variant_id.id,
              'product_qty': ln.product_qty,
              'qty_received': ln.product_qty,  # Establecer cantidad recibida por defecto
              'price_unit': ln.price_unit,
              'analytic_distribution': {
                record.ek_ship_registration_id.analytic_account_id.id: 100
              }
              if record.ek_ship_registration_id.analytic_account_id
              else {},
            }

            # Agregar product_template_id solo si el campo existe en el modelo
            if 'product_template_id' in purchase_order_line_obj._fields:
              purchase_order_line_vals['product_template_id'] = product_id.id

            data_purchase_order_line_vals.append(purchase_order_line_vals)
          purchase_order_line_obj.create(data_purchase_order_line_vals)
          
          # Vincular orden de compra con registros de tracking
          self._link_purchase_order_to_tracking(create_purchase_order, supplier_products)

  def _link_purchase_order_to_tracking(self, purchase_order, product_lines):
    """Vincular orden de compra con registros de tracking usando reimbursement_tracking_id"""
    
    # Buscar registros de tracking para esta solicitud
    tracking_records = self.env['ek.reimbursement.tracking'].search([
      ('request_id', '=', self.id),
      ('journey_crew_id', '=', self.journey_crew_id.id)
    ])
    
    # Vincular cada línea de la orden con su registro de tracking correspondiente
    for po_line in purchase_order.order_line:
      # Buscar el registro de tracking que corresponde a este producto
      matching_tracking = tracking_records.filtered(
        lambda t: t.product_id.id == po_line.product_id.id
      )
      
      if matching_tracking:
        # Vincular la línea de la orden con el registro de tracking
        po_line.write({'reimbursement_tracking_id': matching_tracking[0].id})
        
        # Actualizar el registro de tracking con la orden de compra
        matching_tracking[0].write({
          'purchase_order_id': purchase_order.id,
          'state': 'purchase_pending'  # Estado cuando se crea la orden de compra
        })

  def update_notification_status(self):
    """Actualiza el estado de notificaciones cuando cambia de etapa"""
    if not self.notification_ids:
      return

    # Obtener la próxima etapa
    next_stage = self._get_next_stage()

    if next_stage:
      # Buscar configuraciones de notify_stage para la próxima etapa
      next_stage_configs = self.type_id.notify_stage_ids.filtered(
        lambda x: x.stage_id.id == next_stage.id
      )

      # Obtener todos los usuarios que deben ser notificados en la próxima etapa
      users_to_notify = set()
      for config in next_stage_configs:
        users_to_notify.update(config.user_ids.ids)

      # Actualizar notificaciones basado en la configuración de la próxima etapa
      for notification in self.notification_ids:
        # Buscar configuración específica para este usuario en la próxima etapa
        user_config = next_stage_configs.filtered(
          lambda x: notification.user_id in x.user_ids
        )

        if user_config:
          # Usuario está configurado para la próxima etapa - activar notify, desactivar create_activity
          notification.write({'notify': True, 'create_activity': False})
        else:
          # Usuario NO está configurado para la próxima etapa - desactivar notify
          notification.write({'notify': False, 'create_activity': False})

      # Buscar configuraciones para etapas posteriores (para create_activity)
      all_future_stages = self.type_id.stage_ids.filtered(
        lambda s: s.sequence > self.stage_id.sequence
      )

      if all_future_stages:
        future_stage_configs = self.type_id.notify_stage_ids.filtered(
          lambda x: x.stage_id in all_future_stages
        )

        # Activar create_activity para usuarios que tienen configuraciones en etapas futuras
        for notification in self.notification_ids:
          user_future_config = future_stage_configs.filtered(
            lambda x: notification.user_id in x.user_ids
            and x.stage_id != next_stage
          )

          if user_future_config and not notification.notify:
            # Solo activar create_activity si no está marcado para notify
            notification.write({'create_activity': True})
    else:
      # Si no hay próxima etapa, desactivar todas las notificaciones y actividades
      for notification in self.notification_ids:
        notification.write({'notify': False, 'create_activity': False})

  def notify_schedule_custom(self, tobjects=None):
    """
    Función exclusiva para manejar notificaciones de solicitudes de operación
    Evita conflictos con la herencia del mixin y proporciona control total
    Separa entre notificaciones (notify=True) y actividades (create_activity=True)
    """

    # Si tobjects no se pasa, usar self
    if tobjects is None:
      tobjects = self

    for rec in tobjects:
      if not rec.notification_ids:
        continue

      # Separar notificaciones y actividades
      notifications_to_send = rec.notification_ids.filtered(lambda n: n.notify)
      activities_to_create = rec.notification_ids.filtered(
        lambda n: n.create_activity
      )

      if not notifications_to_send and not activities_to_create:
        continue

      # Buscar la próxima etapa
      current_stage = rec.stage_id
      next_stage = None
      if current_stage and rec.type_id.stage_ids:
        next_stages = rec.type_id.stage_ids.filtered(
          lambda r: r.sequence > current_stage.sequence
          and not r.canceled_stage
          and not r.fold
        )
        if next_stages:
          next_stage = next_stages[0]

      if not next_stage:
        continue

      # Buscar configuración de plantilla para la próxima etapa (opcional)
      type_notify_stages = rec.type_id.notify_stage_ids.filtered(
        lambda r: r.stage_id == next_stage
      )

      # PROCESAR NOTIFICACIONES (notify=True)
      if notifications_to_send:
        # Recopilar todos los destinatarios
        partner_ids = []
        user_names = []

        for notification in notifications_to_send:
          partner_ids.append(notification.user_id.partner_id.id)
          user_names.append(notification.user_id.name)

        try:
          # Preparar información de la solicitud
          from markupsafe import Markup
          from odoo.tools import html_escape

          # Escapar contenido para seguridad
          request_name_safe = html_escape(rec.name)
          type_name_safe = html_escape(rec.type_id.name)
          stage_name_safe = html_escape(next_stage.name)

          # Información adicional del viaje y cliente
          journey_info = ''
          if rec.journey_crew_id and rec.ek_ship_registration_id:
            journey_name = html_escape(rec.journey_crew_id.name or '')
            ship_name = html_escape(rec.ek_ship_registration_id.name or '')
            journey_info = f'<li class="o-mail-Message-tracking mb-1"><span>Viaje:</span> <span class="fw-bold text-info">{journey_name} (Buque {ship_name})</span></li>'

          client_info = ''
          if rec.res_partner_id:
            client_name = html_escape(rec.res_partner_id.name or '')
            client_info = f'<li class="o-mail-Message-tracking mb-1"><span>Cliente:</span> <span class="fw-bold text-info">{client_name}</span></li>'

          # No incluir nota de plantilla en las notificaciones (solo para actividades)

          # Construir mensaje HTML formateado
          message_body = f"""
          <div class="position-relative d-flex">
            <div class="o-mail-Message-content o-min-width-0">
              <div class="o-mail-Message-textContent position-relative d-flex">
                <div>
                  La solicitud <span class="fw-bold text-info">{request_name_safe}</span> de tipo <span class="fw-bold text-info">{type_name_safe}</span> se encuentra ahora en la etapa
                  <span class="text-nsk-primary">
                    {stage_name_safe}
                  </span>
                  <ul class="mb-0 ps-4">
                    {journey_info}
                    {client_info}
                  </ul>
                </div>
              </div>
            </div>
          </div>
          """

          # Enviar UN SOLO mensaje con todos los destinatarios
          rec.message_post(
            body=Markup(message_body),
            subject=f'Notificación: {next_stage.name}',
            partner_ids=partner_ids,
            message_type='notification',
            subtype_xmlid='mail.mt_comment',
          )

        except Exception as e:
          # Error enviando notificación
          pass

      # PROCESAR ACTIVIDADES (create_activity=True)
      if activities_to_create:
        for notification in activities_to_create:
          # Buscar configuración específica para este usuario en esta etapa (opcional)
          user_config = (
            type_notify_stages.filtered(
              lambda r: notification.user_id in r.user_ids
            )
            if type_notify_stages
            else False
          )

          # Determinar configuración a usar (plantilla o valores por defecto)
          if user_config:
            config = user_config[0]  # Usar configuración de plantilla
            activity_type_id = config.activity_id.id
            delay_days = (
              config.delay_count or config.activity_id.delay_count or 1
            )
            note = (
              config.note
              or f'Solicitud {rec.name} necesita atención en la etapa {next_stage.name}'
            )
          else:
            # Usar valores por defecto cuando no hay configuración de plantilla
            default_activity_type = rec.env['mail.activity.type'].search(
              [('name', 'ilike', 'todo')], limit=1
            ) or rec.env['mail.activity.type'].search([], limit=1)

            if default_activity_type:
              activity_type_id = default_activity_type.id
              delay_days = 1
              note = f'Solicitud {rec.name} necesita atención en la etapa {next_stage.name}'
            else:
              # No se encontró tipo de actividad por defecto
              continue

          try:
            rec.activity_schedule(
              activity_type_id=activity_type_id,
              date_deadline=fields.Datetime.add(
                fields.Datetime.now(),
                days=delay_days,
              ),
              summary=f'Reminder: {rec.type_id.name} at stage {next_stage.name}',
              note=note,
              user_id=notification.user_id.id,
            )

          except Exception as e:
            # Error creando actividad
            pass

  def notify_schedule(self, tobjects=None):
    """
    Override del método del mixin - redirige a nuestra función personalizada
    Mantiene compatibilidad pero usa lógica propia
    """
    return self.notify_schedule_custom(tobjects)

  def create_activities_for_users(self, users):
    """Crea actividades para los usuarios especificados"""
    # Buscar configuraciones de actividades para la etapa actual
    notify_stages = self.type_id.notify_stage_ids.filtered(
      lambda r: r.stage_id.id == self.stage_id.id
    )

    for user in users:
      # Buscar configuración específica para este usuario en la etapa actual
      user_notify_stage = notify_stages.filtered(lambda r: user in r.user_ids)

      if user_notify_stage:
        user_notify_stage = user_notify_stage[0]  # Tomar el primero

        try:
          self.activity_schedule(
            activity_type_id=user_notify_stage.activity_id.id,
            date_deadline=fields.Datetime.add(
              fields.Datetime.now(),
              days=user_notify_stage.delay_count
              or user_notify_stage.activity_id.delay_count
              or 1,
            ),
            summary=user_notify_stage.note or f'Actividad para {self.name}',
            user_id=user.id,
          )
        except Exception:
          pass

  def _initialize_notifications_on_create(self):
    """Inicializa las notificaciones cuando se crea un registro"""

    if not self.type_id:
      return

    # NO verificar notification_ids existentes porque los del onchange están solo en memoria

    # Obtener la próxima etapa
    next_stage = self._get_next_stage()

    # Crear notificaciones para todos los usuarios configurados en notify_stage_ids
    notification_lines = []
    users_added = set()

    for notify_stage in self.type_id.notify_stage_ids:
      for user in notify_stage.user_ids:
        if user.id not in users_added:
          # Marcar notify=True solo si el usuario está configurado para la próxima etapa
          should_notify = (
            next_stage and notify_stage.stage_id.id == next_stage.id
          )

          notification_lines.append(
            {
              'user_id': user.id,
              'notify': should_notify,  # True solo si es para la próxima etapa
              'create_activity': False,  # Por ahora deshabilitado
              'sequence': len(notification_lines) + 1,
              'request_id': self.id,
            }
          )
          users_added.add(user.id)

    if notification_lines:
      self.env['ek.operation.request.notification'].create(notification_lines)

    # Actualizar estado de notificaciones basado en la etapa actual
    self.update_notification_status()


class table_crew_member_ek_operation_request(models.Model):
  _name = 'table.crew.member.ek.operation.request'
  _description = 'Table Crew Member'
  name = fields.Many2one(
    'res.partner',
    string='Name',
    domain="[('is_crew', '=', True), ('id', 'not in', used_crew_member_ids)]",
  )
  vat = fields.Char(string='ID or Passport')
  nationality_id = fields.Many2one('res.country', string='Nationality')

  ek_operation_request_id = fields.Many2one(
    'ek.operation.request', string='Operation Request'
  )

  used_crew_member_ids = fields.Many2many(
    comodel_name='res.partner', string='Used Crew Members'
  )
  ek_academic_courses_ids = fields.Many2many(
    'ek.academic.courses',
    'table_crew_member_ek_academic_courses_rel',
    'table_crew_member_id',
    string='Document Crew Member',
  )
  ek_crew_member_hierarchy_title_id = fields.Many2one(
    'ek.crew.member.hierarchy', string='Title'
  )
  ek_crew_member_hierarchy_id = fields.Many2one(
    'ek.crew.member.hierarchy', string='Plaza'
  )

  @api.onchange('ek_operation_request_id', 'name')
  def _onchange_ek_operation_request_id(self):
    if self.ek_operation_request_id:
      used_crew_ids = self.ek_operation_request_id.crew_ids.mapped('name').ids
      self.used_crew_member_ids = [(6, 0, used_crew_ids)]

  @api.onchange('name')
  def onchange_name(self):
    if self.name:
      self.vat = self.name.vat
      self.ek_crew_member_hierarchy_id = self.name.ek_crew_member_hierarchy_id
      self.ek_crew_member_hierarchy_title_id = (
        self.name.ek_crew_member_hierarchy_id
      )
      self.nationality_id = self.name.nationality_id
      self.ek_academic_courses_ids = [(5, 0, 0)]
      curses_ids = [(4, crew.id) for crew in self.name.ek_academic_courses_ids]
      self.ek_academic_courses_ids = curses_ids


class ek_authorized_pourtario_operators_table(models.Model):
  _name = 'ek.authorized.pourtario.operators.table'
  _description = 'Create authorized pourtario operators table'
  _order = 'res_partner_id asc'

  operation_request_id = fields.Many2one(
    'ek.operation.request', string='Operation Request'
  )
  res_partner_id = fields.Many2one('res.partner', string='Company')
  ek_type_service_boat_ids = fields.Many2many(
    'type.service.boat',
    'type_service_boat_rel1',
    'ek_authorized_pourtario_operators_table_id1',
    string='Type of Service',
  )
  ek_type_boat_operators_ids = fields.Many2many(
    'type.boat.operators',
    'type_boat_operators_rel2',
    'ek_authorized_pourtario_operators_table2',
    string='Type of Operators',
  )
  registration_number_opc = fields.Char(string='Registration NO.')

  @api.onchange('res_partner_id')
  def _onchange_res_partner_id_table(self):
    if self.res_partner_id:
      self.ek_type_service_boat_ids = (
        self.res_partner_id.ek_type_service_boat_ids
      )
      self.ek_type_boat_operators_ids = (
        self.res_partner_id.ek_type_boat_operators_ids
      )
      self.registration_number_opc = self.res_partner_id.registration_number_opc
    else:
      self.ek_type_service_boat_ids = [(5, 0, 0)]
      self.ek_type_boat_operators_ids = [(5, 0, 0)]
      self.registration_number_opc = False


class ek_acces_port_table_float(models.Model):
  _name = 'ek.acces.port.table.float'
  _description = 'Create acces port table float'
  _order = 'res_partner_id asc'

  name = fields.Integer(string='No.', copy=False, default=1)
  res_partner_id = fields.Many2one(
    'res.partner',
    string='Lastname Name',
  )
  dni_passport = fields.Char(string='DNI/Passport')
  function = fields.Char(string='Cargo')
  fleet_vehicle_ids = fields.Many2many(
    'fleet.vehicle',
    'fleet_vehicle_rel',
    'operation_request_id',
    string='Vehicles',
  )
  aditionals = fields.Char(string='Aditionals')

  operation_request_id = fields.Many2one(
    'ek.operation.request', string='Operation Request'
  )
  has_vehiculo = fields.Boolean(string='Has Vehicle')

  @api.onchange('res_partner_id')
  def _onchange_res_partner_id(self):
    if self.res_partner_id:
      self.dni_passport = self.res_partner_id.vat
      self.function = self.res_partner_id.function or ' '


class ek_requerid_burden_nationanl_international(models.Model):
  _name = 'ek.requerid.burden.nationanl.international'
  _description = 'Create Requerid Burden'

  name = fields.Char(string='Product ', copy=False)
  product_id = fields.Many2one('ek.requerid.burden.inter.nac', string='Product')
  customer_consignment = fields.Many2one('res.partner', string='Consignment')
  tm = fields.Float(string='TM')
  n_bl = fields.Char(string='N° de BL')
  senae_authorization = fields.Selection(
    [
      ('yes', 'Yes'),
      ('no', 'No'),
    ],
    string='Senae Authorization (SI/NO)',
  )
  dae_authorization = fields.Char(string='N° DAE Authorization')
  ek_operation_request_id = fields.Many2one(
    'ek.operation.request', string='EK Operation'
  )


class ek_requerid_burden_inter_nac(models.Model):
  _name = 'ek.requerid.burden.inter.nac'
  _description = 'Create Carge Burden'

  name = fields.Char(string='name', copy=False)
  group_cargo = fields.Many2one(
    'ek.requerid.burden.inter.nac.group', string='Group'
  )


class ek_requerid_burden_inter_nac_group(models.Model):
  _name = 'ek.requerid.burden.inter.nac.group'
  _description = 'Create Carge Burden'

  name = fields.Char(string='name', copy=False)


class ek_table_aditional_self(models.Model):
  _name = 'ek.table.aditional.self'
  _description = 'table aditional'

  field1 = fields.Char(string='Field 1')
  field2 = fields.Char(string='Field 2')
  field3 = fields.Char(string='Field 3')
  field4 = fields.Char(string='Field 4')
  field5 = fields.Char(string='Field 5')
  field6 = fields.Char(string='Field 6')
  field7 = fields.Char(string='Field 7')
  field8 = fields.Char(string='Field 8')

  operation_request_id = fields.Many2one(
    'ek.operation.request', string='Operation Request'
  )


class ek_service_request_group(models.Model):
  _name = 'ek.service.request.group'
  _description = 'Create Service request'

  name = fields.Char(string='Name')
  order = fields.Integer(string='Order', default=1)
  line_strong = fields.Boolean(string='Line', default=False)
  position = fields.Selection(
    [
      ('left', 'Left'),
      ('right', 'Right'),
    ],
    string='Position',
    copy=False,
  )
  ek_service_request_line_ids = fields.One2many(
    'ek.service.request.line',
    'ek_service_request_group_id',
    string='Service line',
  )


class ek_service_request_line(models.Model):
  _name = 'ek.service.request.line'
  _description = 'Create Service request line'

  name = fields.Char(string='Description', copy=False)
  ek_service_request_group_id = fields.Many2one(
    'ek.service.request.group', string='Service Request Group'
  )
  show_by_default = fields.Boolean(string='Show By Default')
  order = fields.Integer(string='Order', default=1)
  space = fields.Integer(string='Space')


####Producto compras
class ek_product_purchase_ship(models.Model):
  _name = 'ek.product.purchase.ship'
  _description = _('Products purchase ship')

  name = fields.Char(string=_('Description'), copy=False)

  ek_operation_request_id = fields.Many2one(
    comodel_name='ek.operation.request', string=_('Request'), required=False
  )

  product_id = fields.Many2one(
    comodel_name='product.template', string=_('Product Template'), required=True
  )

  price_unit = fields.Float(string=_('Price Unit'))

  product_qty = fields.Float(
    string=_('Quantity Request'), required=False, default=1
  )
  edit_price = fields.Boolean(string='Edit Price', default=False)
  supplier_id = fields.Many2one('res.partner', string='Supplier')

  @api.onchange('product_id')
  def _onchange_product_id(self):
    self.price_unit = self.product_id.list_price
    self.name = self.product_id.name


# producto ventas
class ek_product_order_shipp(models.Model):
  _name = 'ek.product.order.shipp'
  _description = _('Products order ship')

  name = fields.Char(string=_('Description'), copy=False)
  ek_operation_request_id = fields.Many2one(
    comodel_name='ek.operation.request', string=_('Request'), required=False
  )
  product_id = fields.Many2one(
    comodel_name='product.template', string=_('Product Template'), required=True
  )
  price_unit = fields.Float(string=_('Price Unit'))
  product_qty = fields.Float(
    string=_('Quantity Request'), required=False, default=1
  )
  edit_price = fields.Boolean(string='Edit Price', default=False)

  @api.onchange('product_id')
  def _onchange_product_id(self):
    self.price_unit = self.product_id.list_price
    self.name = self.product_id.name


# tipo de servicio para pedido de ventas
class ek_product_request_service(models.Model):
  _name = 'ek.product.request.service'
  _description = _('Products request service')

  name = fields.Char(string=_('Description'), copy=False)
  ek_type_request = fields.Many2one(
    'ek.l10n.type.model.mixin', string='Type Request'
  )
  product_id = fields.Many2one(
    comodel_name='product.template', string=_('Product Template'), required=True
  )
  price_unit = fields.Float(string=_('Price Unit'))
  product_qty = fields.Float(
    string=_('Quantity Request'), required=False, default=1
  )
  edit_price = fields.Boolean(string='Edit Price', default=False)

  stage_ids = fields.Many2many(
    'ek.l10n.stages.mixin',
    'ek_product_request_service_stage_rel',
    'product_request_service_id',
    default=lambda self: self.ek_type_request.stage_ids.filtered(
      lambda s: not s.fold and not s.canceled_stage
    ),
    domain="[('type_ids','in',ek_type_request)]",
    string='Stage',
  )

  @api.onchange('product_id')
  def _onchange_product_id(self):
    self.price_unit = self.product_id.list_price
    self.name = self.product_id.name


# tipo de servicio para pedido de compra
class ek_product_request_service_purchase(models.Model):
  _name = 'ek.product.request.service.purchase'
  _description = _('Products request service purchase')

  name = fields.Char(string=_('Description'), copy=False)
  ek_type_request = fields.Many2one(
    'ek.l10n.type.model.mixin', string='Type Request'
  )
  product_id = fields.Many2one(
    comodel_name='product.template', string=_('Product Template'), required=True
  )
  price_unit = fields.Float(string=_('Price Unit'))
  product_qty = fields.Float(
    string=_('Quantity Request'), required=False, default=1
  )
  supplier_id = fields.Many2one('res.partner', string='Supplier')
  is_separate = fields.Boolean(
    string='Is separate invoices in supplier',
    default=False,
    compute='_compute_is_separate',
  )
  edit_price = fields.Boolean(string='Edit Price', default=False)
  stage_ids = fields.Many2many(
    'ek.l10n.stages.mixin',
    'ek_product_request_service_stage',
    'product_request_service_id',
    default=lambda self: self.ek_type_request.stage_ids.filtered(
      lambda s: not s.fold and not s.canceled_stage
    ),
    domain="[('type_ids','in',ek_type_request)]",
    string='Stage',
  )

  @api.depends('ek_type_request')
  def _compute_is_separate(self):
    for rec in self:
      rec.is_separate = bool(rec.ek_type_request.is_separate)

  @api.onchange('product_id')
  def _onchange_product_id(self):
    self.price_unit = self.product_id.list_price
    self.name = self.product_id.name


# gestion de documento y notificacion
class ek_management_document(models.Model):
  _name = 'ek.management.document'
  _description = 'Create management Document'
  _inherit = ['common.fields.mixin', 'mail.thread', 'mail.activity.mixin']

  name = fields.Char(string='Name', copy=False, tracking=True)
  date_start = fields.Date(string='Date Start', tracking=True)
  pdf_file = fields.Binary(string='attachments')
  ek_operation_request_id = fields.Many2one(
    'ek.operation.request', string='Operation Request'
  )
  type_document = fields.Char(string='Type Document')
  has_requires_reminder = fields.Boolean(
    string='Send Notification', default=True
  )
  date_end = fields.Date(string='Date End', tracking=True)
  days = fields.Integer(string='Days', compute='_compute_days')
  document_status = fields.Selection(
    [
      ('current', 'Current'),
      ('to_wi', 'To Win'),
      ('expired', 'Expired'),
    ],
    string='Document Status',
    default='current',
    compute='onchange_date_end_today',
    store=True,
  )
  one_recordatorio = fields.Boolean(string='One Recordatorio', default=False)

  ek_ship_registration_id = fields.Many2one(
    related='ek_operation_request_id.ek_ship_registration_id',
  )
  journey_crew_id = fields.Many2one(
    related='ek_operation_request_id.journey_crew_id',
  )

  @api.depends('date_end', 'date_today')
  def _compute_days(self):
    for record in self:
      if record.date_end and record.date_today:
        end_date = fields.Date.from_string(record.date_end)
        today_date = fields.Date.from_string(record.date_today)
        delta = end_date - today_date
        record.days = delta.days
      else:
        record.days = 0

  @api.depends('date_end', 'date_today')
  def onchange_date_end_today(self):
    self.document_status = 'to_wi'
    for record in self:
      if record.date_end:
        today = datetime.date.today()
        expiration_date = fields.Date.from_string(record.date_end)
        if expiration_date <= today:
          record.document_status = 'expired'

        elif expiration_date > today:
          record.document_status = 'current'

  @api.model
  def create(self, vals):
    if 'ek_operation_request_id' in vals:
      operation_request = self.env['ek.operation.request'].browse(
        vals['ek_operation_request_id']
      )
      if operation_request.type_id and not vals['name']:
        vals['name'] = operation_request.type_id.name
    return super(ek_management_document, self).create(vals)


class ek_request_report_detail(models.Model):
  _name = 'ek.request.report.detail'
  _description = 'Create  request report detail'
  #  _inherit = ['common.fields.mixin']

  state_boats = fields.Selection(
    [
      ('sailing', 'Navegando'),
      ('port', 'En Puerto'),
    ],
    string='State Boats',
  )
  commission_zarpe = fields.Float('Commission Zarpe')
  commission_arribo = fields.Float('Commission Arribo')
  ship_name_id = fields.Many2one('ek.ship.registration', string='Ship Name')
  journey_crew_id = fields.Many2one('ek.boats.information', string='Journey')
  state = fields.Selection(related='journey_crew_id.state')

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


class ek_table_pay_crew(models.Model):
  _name = 'ek.table.pay.crew'
  _description = 'Report Detail Pay Crew'

  ek_operation_request = fields.Many2one(
    'ek.operation.request', string='Operation Request', copy=False
  )
  name = fields.Many2one(
    'res.partner',
    string='Crew Name',
    domain="[('is_crew', '=', True), ('id', 'not in', used_crew_ids)]",
  )
  used_crew_ids = fields.Many2many(
    comodel_name='res.partner', string='Used Crew Members'
  )
  beneficiary = fields.Char('Beneficiary')
  vat = fields.Char('ID or Pass')
  ek_crew_member_hierarchy_title_id = fields.Many2one(
    'ek.crew.member.hierarchy', string='Title'
  )
  ek_crew_member_hierarchy_id = fields.Many2one(
    'ek.crew.member.hierarchy', string='Plaza'
  )
  nationality_id = fields.Many2one('res.country', string='Nationality')
  v_unitary = fields.Float('Quantity', default=0)
  amount = fields.Float('V .Unitary', default=0)
  gross_total = fields.Float('Gross Total', compute='compute_gross_total')
  discount = fields.Float('Discount')
  total_liquidation = fields.Float(
    'Total Liquidation', compute='compute_liquidation_total'
  )
  date = fields.Date('Date', default=fields.Date.context_today)
  document = fields.Char('Document')
  detail = fields.Text('Detail')
  other_values = fields.Float('Other Values')

  @api.depends('amount', 'v_unitary')
  def compute_gross_total(self):
    for record in self:
      record.gross_total = record.amount * record.v_unitary

  @api.depends('gross_total', 'discount')
  def compute_liquidation_total(self):
    for record in self:
      record.total_liquidation = record.gross_total - record.discount

  @api.onchange('name')
  def name_action_record(self):
    for record in self:
      name = record.name
      record.beneficiary = name.name
      record.vat = name.vat
      record.ek_crew_member_hierarchy_title_id = (
        name.ek_crew_member_hierarchy_id
      )
      record.ek_crew_member_hierarchy_id = name.ek_crew_member_hierarchy_id
      record.nationality_id = name.nationality_id
      record.v_unitary = record.ek_operation_request.quantity_bonus
      record.amount = name.fishing_bonus
      used_crew_ids = [
        rec.name.id
        for rec in record.ek_operation_request.ek_table_pay_crew_ids
        if rec.name
      ]
      record.used_crew_ids = [(6, 0, used_crew_ids)]


class ek_table_reimbursement_expenses(models.Model):
  _name = 'ek.table.reimbursement.expenses'
  _description = 'Report Detail Reimbursement Expenses'

  partner_id = fields.Many2one('res.partner', string='Supplier')
  n_document = fields.Char('N° Document')
  name = fields.Text('Name')
  date_emision = fields.Date('Date Emision')
  amount = fields.Float('Amount')
  ek_operation_request_id = fields.Many2one(
    'ek.operation.request', string='Operation Request', copy=False
  )
