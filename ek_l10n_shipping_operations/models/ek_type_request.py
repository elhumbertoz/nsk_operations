from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class ek_type_request(models.Model):
  # _name = "ek.type.request"
  _description = 'Create Type Request'
  _inherit = 'ek.l10n.type.model.mixin'

  def _aditional_domain(self, field, domain=[]):
    domain = []
    if field.field_id.name == 'ek_operation_request_id':
      domain = [
        ('ek_ship_registration_id', '=', '@ek_ship_registration_id@'),
        ('journey_crew_id', '=', '@journey_crew_id@'),
      ]

    return super(ek_type_request, self)._aditional_domain(field, domain)

  def copy(self, default=None):
    default = dict(default or {})
    if 'name' not in default:
      default['name'] = self.name + ' (copia)'

    return super(ek_type_request, self).copy(default)

  is_analytic_account = fields.Boolean(
    string='Is Analytic Account',
    copy=True,
  )
  is_agent_naviero = fields.Boolean(
    string='Is Agent Naviero',
    copy=True,
  )
  commission = fields.Float(
    string='Commission',
    copy=True,
  )
  has_commission = fields.Boolean(
    string='Has Commission',
    copy=True,
  )
  ek_product_service_crew_primes_ids = fields.One2many(
    'ek.product.service.crew.primes',
    'ek_type_request',
    string='Primes',
    copy=True,
  )
  download_report = fields.Boolean(string='Show Button Download Report')
  send_to_sign_report = fields.Boolean(string='Show Button Send to Sign Report')
  ek_report_stages_mixin_ids = fields.One2many(
    'ek.report.stages.mixin',
    'type_id',
    string='Report Stages',
    copy=True,
  )

  ek_user_readonly_ids = fields.Many2many(
    'res.users',
    'res_user_rell',
    'type_id_resp',
    string='User Readonly',
    copy=True,
  )

  @api.constrains(
    'ek_report_stages_mixin_ids', 'ek_report_stages_mixin_ids.stage_id'
  )
  def _check_ek_report_stages_mixin_ids(self):
    for record in self:
      stage_ids = [
        line.stage_id.id
        for line in record.ek_report_stages_mixin_ids
        if line.stage_id
      ]
      if len(stage_ids) != len(set(stage_ids)):
        raise ValidationError(
          _('The report stages must be unique within a record.')
        )

  state_boats = fields.Selection(
    [
      ('sailing', 'Navegando'),
      ('port', 'En Puerto'),
    ],
    string='state boat',
    default=False,
  )
  is_obligator_document = fields.Boolean(string='Is Obligator Document')
  is_change_of_crew = fields.Boolean(string='Is Change of crew2')

  crew_pay = fields.Boolean(string='Crew Pay')

  is_capital_port = fields.Boolean(string='Is Capital Port')

  is_service_request = fields.Boolean(string='Is Service Request')  # servicio
  is_service_refunf = fields.Boolean(string='Is Service Refunf')  # reembolso

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
  )
  type_event = fields.Selection(
    [
      ('national', 'National'),
      ('internacional', 'Internacional'),
    ],
    string='Type Event N/I',
    required=False,
  )

  is_request_assignable = fields.Boolean(
    string='Is Request Assignable'
  )  # es si la solicitud lo puede asignar el admin

  ek_product_request_service_order_ids = fields.One2many(
    'ek.product.request.service',
    'ek_type_request',
    copy=True,
    string='Product Type Request Order',
  )

  ek_product_request_service_purchase_ids = fields.One2many(
    'ek.product.request.service.purchase',
    'ek_type_request',
    copy=True,
    string='Product Type Request Purchase',
  )

  supplier_id = fields.Many2one('res.partner', string='Supplier')

  is_separate = fields.Boolean(string='Is separate invoices in supplier')

  type_notification = fields.Selection(
    [
      ('arrival', 'Arrival'),
      ('exit', 'Exit'),
      ('both', 'Both'),
    ],
    string='Type Notification',
    required=False,
  )

  @api.onchange('ek_product_request_service_purchase_ids')
  def _onchange_ek_type_request_id(self):
    if self.is_separate:
      for line in self.ek_product_request_service_purchase_ids:
        line.is_separate = self.is_separate

  #####Conficiones de reportes#####
  has_crew = fields.Boolean(string='Has Crew')
  has_service_maneuver = fields.Boolean(string='Has Service Maneuver')
  has_data_requeried_n_i = fields.Boolean(
    string='Has Data Requeried National/International'
  )
  has_operator = fields.Boolean(string='Has Operator')
  has_data_zarpe = fields.Boolean(string='Has Data Zarpe')
  has_data_cargo = fields.Boolean(string='Has Data Cargo')

  # acesso pourtario

  has_access_port = fields.Boolean(string='Has Access Port')
  is_marginal_dock_setting = fields.Boolean(string='Is Marginal Dock')

  type_document_access = fields.Selection(
    [
      ('1', 'Muelles Comerciales'),
      ('2', 'Muelles  Privados'),
    ],
    string='Type Document Access',
    required=False,
  )
  is_dock_space_expansion = fields.Boolean(string='Dock Space Expansion')

  # amplicion o alcanze
  calculation_day_or_hours = fields.Boolean(string='Calculation Day Or Hours')

  search_by_authorization = fields.Boolean(
    string='search by authorization number',
    help='Keep in mind that this activates the field authorization code',
  )

  ship_ids = fields.Many2many(
    'ek.ship.registration',
    'ek_type_request_ek_ship_rel',
    'ek_type_request_id',
    string='Ship',
  )

  use_in_regimen_61 = fields.Boolean(string='Use in Regimen 61')

  # capitania
  has_notification = fields.Boolean(string='Has Activited')
  has_documents_notification = fields.Boolean(string='Has Documents')
  ek_user_groups_reminder_ids = fields.Many2one(
    'ek.user.groups.reminder', string='User Groups Reminder'
  )
  has_report_capitana = fields.Boolean(string='Has Capitania Report')

  has_passanger = fields.Boolean(string='Has Passanger')
  has_delivery_reception = fields.Boolean(string='Has Delivery Reception')

  ek_service_request_report_line_ids = fields.Many2many(
    'ek.service.request.line',
    'ek_type_request_ek_service_request_line_rel',
    'ek_type_request_id',
    string='Service Request Lines',
  )

  # notificaciion correo
  send_email = fields.Boolean(string='Send Email')
  ek_group_mail_template_id = fields.Many2one(
    'ek.group.mail.template', string='Group Email Template'
  )

  ################################################################
  ################################################################
  #########################ADUANA#################################

  # 08/7/2024
  has_mrn_number = fields.Boolean(string='has MRN')

  has_internal_sequence = fields.Boolean(string='Use Internal Sequence')
  internal_sequence = fields.Many2one('ir.sequence', string='Sequence')

  use_in_regimen_70 = fields.Boolean(string='Use in regimen 70')
  has_detail_items = fields.Boolean(string='Has detail of items')
  show_button_copy = fields.Boolean('Show Button Copy')
  not_controlling_weight = fields.Boolean(
    string='Not Controlling Weight', copy=True
  )

  is_correction_request = fields.Boolean(string='Is Correction Request')
  sequence_ids = fields.One2many(
    string=_('Stage Sequence'),
    comodel_name='ek.type.request.stage.sequence',
    inverse_name='type_id',
    copy=False,
  )
  has_credentials = fields.Selection(
    string='Type Table', selection=[('1', 'Credentials'), ('2', 'Single Table')]
  )

  generate_for_stage = fields.Boolean('Generate for Stage')

  table_aditional = fields.Boolean(string='Table Aditional')

  has_trade_numeber = fields.Boolean(string='Has Trade Number')

  select_type_trade_number = fields.Selection(
    [
      ('1', _('For Stage')),
      ('2', _('In Confirmation')),
    ],
    default='1',
  )
  stage_trade_ids = fields.Many2many(
    'ek.l10n.stages.mixin',
    relation='ek_l10n_type_model_stage_trade_rel',
    string='Stages trade',
    domain="[('id', 'in', stage_ids)]",
  )

  stage_service_ids = fields.Many2many(
    'ek.l10n.stages.mixin',
    relation='ek_l10n_type_model_stage_service_rel',
    string='Stages service',
    domain="[('id', 'in', stage_ids)]",
  )
  stage_refund_ids = fields.Many2many(
    'ek.l10n.stages.mixin',
    relation='ek_l10n_type_model_stage_refund_rel',
    string='Stages refund',
    domain="[('id', 'in', stage_ids)]",
  )
  ek_template_mail_stage_id_request_ids = fields.One2many(
    'ek.template.mail.stage.id.request', 'type_id', string='Template Mail'
  )

  @api.constrains(
    'ek_template_mail_stage_id_request_ids',
    'ek_template_mail_stage_id_request_ids.stage_id',
  )
  def _check_ek_report_stages_mixin_ids(self):
    for record in self:
      stage_ids = [
        line.stage_id.id
        for line in record.ek_template_mail_stage_id_request_ids
        if line.stage_id
      ]
      if len(stage_ids) != len(set(stage_ids)):
        raise ValidationError(
          _('The Mail stages must be unique within a record.')
        )

  ek_l10n_search_fields_mixin_ids = fields.One2many(
    'ek.l10n.search.fields.mixin',
    'type_model_id',
    string='L10n Search Fields',
    copy=True,
  )

  ek_product_reimbursement_expenses_ids = fields.Many2one(
    'product.template', string='Product Reimbursement Expenses'
  )
  has_signature = fields.Boolean(string='Has Signature')

  field_concant_text_template = fields.Text(
    string='Field concant text template'
  )
  field_concant_template_ids = fields.Many2many(
    'ir.model.fields',
    string=_('Field Template'),
    domain="[('model_id.model', '=', 'ek.operation.request'),('ttype','in',['char','date','datetime','float','integer','many2one','text'])]",
    ondelete='cascade',
  )

  @api.onchange('field_concant_template_ids')
  def _onchange_field_concant_template_ids(self):
    concatenated_text = ''
    for record in self.field_concant_template_ids:
      if record.ttype == 'many2one':
        concatenated_text += f'{{{record.name}.name}}.............'
      else:
        concatenated_text += f'{{{record.name}}}.............'
    self.field_concant_text_template = concatenated_text


class ek_type_shipp(models.Model):
  _name = 'ek.type.shipp'
  _description = 'Create Type Request'

  name = fields.Char(string='Name', required=True, copy=False)


class ek_type_fondeo(models.Model):
  _name = 'ek.type.fondeo'
  _description = 'Create Type fondeo'

  name = fields.Char(string='Name', required=True, copy=False)


class ek_setting_send_notice(models.Model):
  _name = 'ek.setting.send.notice'
  _description = 'notification settings requests'

  document_status = fields.Selection(
    [
      ('current', 'Current'),
      ('to_wi', 'To Win'),
      ('expired', 'Expired'),
    ],
    string='Document Status',
    required=True,
  )

  days = fields.Integer(string='Days', required=True, copy=False)

  _sql_constraints = [
    (
      'document_status_unique',
      'unique(document_status)',
      'The setting status must be unique.',
    )
  ]

  @api.constrains('document_status')
  def _check_unique_document_status(self):
    for record in self:
      existing = self.search(
        [
          ('document_status', '=', record.document_status),
          ('id', '!=', record.id),
        ]
      )
      if existing:
        raise ValidationError(
          f"The setting '{record.document_status}' must be unique."
        )


class ek_setting_send_boat(models.Model):
  _name = 'ek.setting.send.boat'
  _description = 'notification settings boats'

  document_status = fields.Selection(
    [
      ('current', 'Current'),
      ('to_wi', 'To Win'),
      ('expired', 'Expired'),
    ],
    string='Document Status',
    required=True,
  )

  days = fields.Integer(string='Days', required=True, copy=False)

  _sql_constraints = [
    (
      'document_status_unique',
      'unique(document_status)',
      'The setting status must be unique.',
    )
  ]

  @api.constrains('document_status')
  def _check_unique_document_status(self):
    for record in self:
      existing = self.search(
        [
          ('document_status', '=', record.document_status),
          ('id', '!=', record.id),
        ]
      )
      if existing:
        raise ValidationError(
          f"The setting '{record.document_status}' must be unique."
        )


class ek_setting_send_crew_member(models.Model):
  _name = 'ek.setting.send.crew.member'
  _description = 'notification settings Crew Member'

  document_status = fields.Selection(
    [
      ('current', 'Current'),
      ('to_wi', 'To Win'),
      ('expired', 'Expired'),
    ],
    string='Document Status',
    required=True,
  )

  days = fields.Integer(string='Days', required=True, copy=False)

  _sql_constraints = [
    (
      'document_status_unique',
      'unique(document_status)',
      'The setting status must be unique.',
    )
  ]

  @api.constrains('document_status')
  def _check_unique_document_status(self):
    for record in self:
      existing = self.search(
        [
          ('document_status', '=', record.document_status),
          ('id', '!=', record.id),
        ]
      )
      if existing:
        raise ValidationError(
          f"The setting '{record.document_status}' must be unique."
        )


class ek_setting_send_reminder_passport(models.Model):
  _name = 'ek.setting.send.reminder.passport'
  _description = 'Notification Settings Crew Member Passport'

  document_status = fields.Selection(
    [
      ('current', 'Current'),
      ('to_wi', 'To Win'),
      ('expired', 'Expired'),
    ],
    string='Document Status',
    required=True,
  )

  days = fields.Integer(string='Days', required=True, copy=False)

  _sql_constraints = [
    (
      'document_status_unique',
      'unique(document_status)',
      'The setting status must be unique.',
    )
  ]

  @api.constrains('document_status')
  def _check_unique_document_status(self):
    for record in self:
      existing = self.search(
        [
          ('document_status', '=', record.document_status),
          ('id', '!=', record.id),
        ]
      )
      if existing:
        raise ValidationError(
          f"The setting '{record.document_status}' must be unique."
        )


class ek_product_service_crew_primes(models.Model):
  _name = 'ek.product.service.crew.primes'
  _description = _('Products Crew Primes')

  name = fields.Char(string=_('Description'), copy=False)
  ek_type_request = fields.Many2one(
    'ek.l10n.type.model.mixin', string='Type Request'
  )
  product_id = fields.Many2one(
    comodel_name='product.template', string=_('Product Template'), required=True
  )

  @api.onchange('product_id')
  def _onchange_product_id_crew(self):
    self.name = self.product_id.name


class ek_type_request_stage_sequence(models.Model):
  _name = 'ek.type.request.stage.sequence'
  _description = 'Create Type Request Stage Sequence'
  _order = 'order ASC'

  order = fields.Integer('Sequence', default=10)
  auto_generate = fields.Boolean('Auto Generate', default=True)
  generate_new_number = fields.Boolean('Generate New Number', default=True)

  type_id = fields.Many2one(
    comodel_name='ek.l10n.type.model.mixin', string=_('Request'), required=False
  )

  type_request_generate_id = fields.Many2one(
    comodel_name='ek.l10n.type.model.mixin',
    string=_('Request Generate'),
    required=True,
  )


class ek_l10n_type_field_mixin(models.Model):
  _inherit = 'ek.l10n.type.field.mixin'

  fields_relation_id = fields.Many2one(
    comodel_name='ir.model.fields',
    string='Fields Relation',
    domain="[('model_id.model', '=', object_model_id),('ttype', '=', 'many2one')]",
  )

  fields_change_id = fields.Many2one(
    comodel_name='ir.model.fields', string='Field to Change'
  )

  domain = fields.Char()
  stage_id = fields.Many2many(
    'ek.l10n.stages.mixin',
    'ek_l10n_type_field_mixin_ek_l10n_stages_mixin',
    'type_field_id',
    string='Stages',
    default=lambda self: self.type_model_id.stage_ids,
    domain="[('type_ids','in',type_model_id)]",
  )

  @api.onchange('fields_relation_id', 'field_id')
  def _compute_domain(self):
    self.domain = False
    if self.field_id and self.fields_relation_id:
      field = self.field_id
      field_type = field.ttype
      field_relation = field.relation
      model_id = self.fields_relation_id.relation

      domain = [
        ('ttype', '=', field_type),
        ('relation', '=', field_relation),
        ('model_id.model', '=', model_id),
      ]
      self.domain = domain


class ek_report_stages_mixin(models.Model):
  _name = 'ek.report.stages.mixin'

  ek_template_py3o_ids = fields.Many2many(
    'ek.template.py3o',
    'ek_report_stages_mixin_ek_template_py3o',
    'template_id',
    copy=False,
    string='Templates',
  )
  stage_id = fields.Many2one(
    comodel_name='ek.l10n.stages.mixin',
    string='Stage',
    required=True,
    copy=False,
    domain="[('id','in',stage_ids)]",
  )
  type_id = fields.Many2one(
    comodel_name='ek.l10n.type.model.mixin',
    string='Type',
    required=True,
    copy=False,
  )
  stage_ids = fields.Many2many(related='type_id.stage_ids')


class ek_template_mail_stage_id_request(models.Model):
  _name = 'ek.template.mail.stage.id.request'
  _description = 'Create Template Mail Stage Id Request'

  template_ids = fields.Many2many(
    'mail.template',
    'ek_template_mail_stage_id_request_1',
    'template_id',
    copy=False,
    string='Email Template',
    domain="[('model', '=', 'ek.operation.request')]",
    help='Email automatically sent to the customer when the type reaches this stage.\n'
    'By default, the email will be sent from the email alias of the type.\n'
    "Otherwise it will be sent from the company's email address, or from the catchall (as defined in the System Parameters).",
  )
  stage_id = fields.Many2one(
    comodel_name='ek.l10n.stages.mixin',
    string='Stage',
    required=True,
    copy=False,
    domain="[('id','in',stage_ids)]",
  )
  type_id = fields.Many2one(
    comodel_name='ek.l10n.type.model.mixin',
    string='Type',
    required=True,
    copy=False,
  )
  stage_ids = fields.Many2many(related='type_id.stage_ids')
  template_id = fields.Many2one('mail.template')


class ek_l10n_search_fields_mixin(models.Model):
  _name = 'ek.l10n.search.fields.mixin'

  type_model_id = fields.Many2one(
    comodel_name='ek.l10n.type.model.mixin',
    string=_('Type Model'),
    required=True,
  )

  object_model_id = fields.Char(related='type_model_id.model')

  field_id = fields.Many2one(
    'ir.model.fields',
    string=_('Field Update'),
    domain="[('readonly','=',False),('model_id.model', '=', object_model_id),('name', 'not in', ['l10n_ec_check_model_type','activity_ids','activity_summary','activity_type_id','campaign_id','medium_id','message_follower_ids','message_ids','message_partner_ids','rating_ids','source_id','type_id','website_message_ids','state_id','name','parent_id','child_ids','stage_id','user_id','assign_date','assign_hours','done_date','done_hours','confirmed_hours','active','company_id','date_last_stage_update','oldest_unanswered_customer_message_date','block_type'])]",
    ondelete='cascade',
    required=True,
  )

  fields_relation_id = fields.Many2one(
    'ir.model.fields',
    ondelete='cascade',
    string='Model Field',
    domain="[('model_id.model', '=', object_model_id),('ttype', '=', 'many2one')]",
    required=True,
  )

  fields_change_id = fields.Many2one(
    'ir.model.fields',
    ondelete='cascade',
    string='Field to Capture',
    required=True,
  )

  domain = fields.Char()

  @api.onchange('fields_relation_id', 'field_id')
  def _compute_domain(self):
    self.domain = False
    if self.field_id and self.fields_relation_id:
      field = self.field_id
      field_type = field.ttype
      field_relation = field.relation
      model_id = self.fields_relation_id.relation

      domain = [
        ('ttype', '=', field_type),
        ('relation', '=', field_relation),
        ('model_id.model', '=', model_id),
      ]
      self.domain = domain
