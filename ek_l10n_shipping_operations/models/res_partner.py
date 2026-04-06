import datetime

from dateutil.relativedelta import relativedelta
from odoo import _, api, fields, models


class ResPartner(models.Model):
  _inherit = 'res.partner'

  ek_academic_courses_ids = fields.One2many(
    'ek.academic.courses', 'partner_id', string='Document Crew Member'
  )
  nationality_id = fields.Many2one('res.country', string='Nationality')
  age = fields.Integer(string='Age', readonly=True, compute='_compute_age')
  is_crew = fields.Boolean(string='Is Crew', default=False)
  send_notificacion_user_ek = fields.Boolean(
    string='Send Notificacion User', default=False
  )
  ek_user_groups_reminder_id = fields.Many2one(
    'ek.user.groups.reminder', string='User Groups Reminder'
  )

  fishing_bonus = fields.Float('Fishing Bonus')

  ek_crew_member_hierarchy_id = fields.Many2one(
    'ek.crew.member.hierarchy', string='Crew member hierarchy'
  )
  ek_type_service_boat_ids = fields.Many2many(
    'type.service.boat',
    'type_service_boat_rel',
    'partner_id',
    string='Type of Service',
  )
  ek_type_boat_operators_ids = fields.Many2many(
    'type.boat.operators',
    'type_boat_operators_rel',
    'partner_id',
    string='Type of Operators',
  )
  registration_number_opc = fields.Char(string='Registration NO.')
  count_documento_nsk = fields.Integer(
    compute='count_document_nsk', string='Count Document'
  )

  @api.depends('ek_academic_courses_ids')
  def count_document_nsk(self):
    self.count_documento_nsk = len(self.ek_academic_courses_ids)

  @api.depends('l10n_ec_birthdate')
  def _compute_age(self):
    for record in self:
      age = 0
      if record.l10n_ec_birthdate:
        age = relativedelta(fields.Date.today(), record.l10n_ec_birthdate).years
      record.age = age

  count_crew_pay = fields.Integer(
    compute='_compute_ek_crew_history_count', string='Crew Pay'
  )

  ek_crew_history_count = fields.Integer(
    compute='_compute_ek_crew_history_count', string='Crew History'
  )

  @api.depends('is_crew')
  def _compute_ek_crew_history_count(self):
    for record in self:
      record.ek_crew_history_count = record.env['ek.crew.history'].search_count(
        [
          ('partner_id', '=', record.id),
        ]
      )

      record.count_crew_pay = record.env['ek.table.pay.crew'].search_count(
        [
          ('name', '=', record.id),
        ]
      )

  def action_open_ek_table_pay_crew(self):
    self.ensure_one()
    return {
      'name': _('Crew Pay'),
      'type': 'ir.actions.act_window',
      'res_model': 'ek.table.pay.crew',
      'view_mode': 'tree',
      'view_id': self.env.ref(
        'ek_l10n_shipping_operations.ek_table_pay_crew_tree'
      ).id,
      'domain': [('name', 'in', self.ids)],
      'context': {
        'create': False,
        'edit': False,
        'delete': False,
      },
      'target': 'current',
    }

  def action_open_ek_crew_history_count(self):
    self.ensure_one()
    return {
      'name': _('Crew History'),
      'type': 'ir.actions.act_window',
      'res_model': 'ek.crew.history',
      'view_mode': 'tree',
      'view_id': self.env.ref(
        'ek_l10n_shipping_operations.ek_crew_history_tree'
      ).id,
      'domain': [('partner_id', 'in', self.ids)],
      'context': {
        'create': False,
        'edit': False,
        'delete': False,
      },
      'target': 'current',
    }

  def action_open_ek_academic_course(self):
    self.ensure_one()
    return {
      'type': 'ir.actions.act_window',
      'name': 'Documento NSK',
      'res_model': 'ek.academic.courses',
      'view_mode': 'tree',
      'view_id': self.env.ref(
        'ek_l10n_shipping_operations.ek_academic_courses_tree'
      ).id,
      'domain': [('partner_id', 'in', self.ids)],
      'target': 'current',
    }

  @api.model
  def cron_create_reminder_crew_documents(self):
    partners = self.search(
      [
        ('send_notificacion_user_ek', '=', True),
        ('ek_user_groups_reminder_id', '!=', False),
      ]
    )
    for partner in partners:
      try:
        partner.create_reminder_crew_documents()
      except Exception:
        pass

  def create_reminder_crew_documents(self):
    send_settings = self.env['ek.setting.send.crew.member'].search([])
    send_settings_passport = self.env[
      'ek.setting.send.reminder.passport'
    ].search([])

    self._process_documents('document', send_settings)
    self._process_documents('passport', send_settings_passport)

  def _process_documents(self, doc_type, settings):
    documents = self.ek_academic_courses_ids.filtered(
      lambda d: d.type_send == doc_type
    )
    date_today = datetime.date.today()

    for doc in documents:
      if not doc.end_date:
        continue

      date_expiration = doc.end_date
      for send in settings:
        days_diff = (date_today - date_expiration).days
        date_activity = False
        summary = None

        if send.document_status == 'expired' and days_diff >= send.days:
          date_activity = True
          summary = f'{doc.document_type.name} {doc.course_document_name.name} of crew member {self.name} is expired'

          doc.write({'document_status': 'expired'})

        elif (
          send.document_status == 'to_wi'
          and days_diff >= send.days
          and days_diff < 0
        ):
          date_activity = True
          summary = f'{doc.document_type.name}  {doc.course_document_name.name} of crew member {self.name} is about to expire.'
          doc.write({'document_status': 'to_wi'})

        if date_activity:
          users = self.ek_user_groups_reminder_id.user_ids
          self.send_user_reminder_crew_documents(body=summary, users=users)

  def send_user_reminder_crew_documents(self, body=None, users=None):
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


class ek_crew_history(models.Model):
  _name = 'ek.crew.history'
  _description = 'History the Crew'

  partner_id = fields.Many2one('res.partner', string='Crew Members')
  vat = fields.Char(string='ID ')
  ship_name_id = fields.Many2one(
    'ek.ship.registration', string='Ship Registration'
  )
  travel_id = fields.Many2one('ek.boats.information', string='Travel')
  ek_res_world_seaports_id = fields.Many2one(
    'ek.res.world.seaports', string='Port of Origin'
  )  # viaje
  ek_res_world_seaports_d_id = fields.Many2one(
    'ek.res.world.seaports', string='Port of Destination'
  )  # viaje

  # arribo
  ek_crew_member_hierarchy_arribo_id = fields.Many2one(
    'ek.crew.member.hierarchy', string='hierarchy Arribo'
  )  # arribo
  ek_boat_location_arribo_id = fields.Many2one(
    'ek.boat.location', string='Boat Location arribo'
  )
  city_arribo_id = fields.Many2one('ek.res.country.city', string='City arribo')
  eta = fields.Datetime(string='ETA')
  ata = fields.Datetime(string='ATA')

  # zarpe
  ek_crew_member_hierarchy_zarpe_id = fields.Many2one(
    'ek.crew.member.hierarchy', string='hierarchy Zarpe'
  )  # arribo
  ek_boat_location_zarpe_id = fields.Many2one(
    'ek.boat.location', string='Boat Location Zarpe'
  )
  city_zarpe_id = fields.Many2one('ek.res.country.city', string='City Zarpe')
  etd = fields.Datetime(string='ETD')
  atd = fields.Datetime(string='ATD')


class ek_academic_courses(models.Model):
  _name = 'ek.academic.courses'
  _description = 'Contact Documentation'
  _inherit = ['mail.thread', 'mail.activity.mixin', 'common.fields.mixin']

  partner_id = fields.Many2one('res.partner', string='Crew Members')
  document_type = fields.Many2one(
    'ek.type.document.crew.member', string='Document Type', tracking=True
  )
  course_document_name = fields.Many2one(
    'ek.type.courses.crew.member', string='Course or Document', tracking=True
  )
  start_date = fields.Date(string='Start Date', tracking=True)
  end_date = fields.Date(string='End Date', tracking=True)
  document_certificate = fields.Char(
    string='N°Document/Certificate', tracking=True
  )
  observation = fields.Text(string='Observation', tracking=True)
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
  )
  type_send = fields.Selection(
    [
      ('document', 'Document'),
      ('passport', 'Passport'),
    ],
    tracking=True,
    string='Type Send',
  )

  days = fields.Integer(
    string='Days', compute='_compute_days', store=True, readonly=True, default=0
  )

  @api.depends('start_date', 'end_date', 'date_today')
  def _compute_days(self):
    for record in self:
      if record.start_date and record.end_date:
        record._compute_date_today()
        today = record.date_today
        if record.end_date >= today:
          delta = record.end_date - today
          record.days = delta.days
        else:
          delta = today - record.end_date
          record.days = delta.days

  @api.depends('end_date', 'date_today')
  def _onchange_date_end(self):
    self.document_status = 'to_wi'
    for record in self:
      if record.end_date:
        today = datetime.date.today()
        expiration_date = fields.Date.from_string(record.end_date)
        if expiration_date <= today:
          record.document_status = 'expired'

        elif expiration_date > today:
          record.document_status = 'current'

  def open_document_id(self):
    return {
      'type': 'ir.actions.act_window',
      'name': 'Document',
      'res_model': 'ek.academic.courses',
      'view_mode': 'form',
      'res_id': self.id,
      'view_id': self.env.ref(
        'ek_l10n_shipping_operations.ek_academic_courses_form'
      ).id,
      'target': 'current',
      'context': {'create': False},
    }


class ek_type_document_crew_member(models.Model):
  _name = 'ek.type.document.crew.member'
  _description = 'Create Type Document Crew Member'

  name = fields.Char(string='Name', required=True, copy=False)


class ek_type_courses_crew_member(models.Model):
  _name = 'ek.type.courses.crew.member'
  _description = 'Create Type Courses Crew Member'

  name = fields.Char(string='Name', required=True, copy=False)
