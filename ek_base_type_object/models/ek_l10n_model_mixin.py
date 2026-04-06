from dateutil.relativedelta import relativedelta
from odoo import _, api, fields, models
from odoo.exceptions import UserError
from odoo.osv import expression


class irModel(models.Model):
  _inherit = 'ir.model'
  abstract = fields.Boolean()


class EkL10nModelMixin(models.Model):
  _name = 'ek.l10n.model.mixin'
  _description = _('Model Generic')
  _ek_l10n_model_studio = True
  # _inherit = [
  #     'mail.activity.mixin',
  #     'utm.mixin',
  #     'mail.tracking.duration.mixin',
  # ]

  _inherit = [
    'mail.thread.cc',
    'utm.mixin',
    'mail.activity.mixin',
    'mail.tracking.duration.mixin',
  ]

  _track_duration_field = 'stage_id'

  name = fields.Char(
    string='#Doc Internal',
    tracking=True,
    copy=True,
    default='/',
  )

  type_id = fields.Many2one(
    comodel_name='ek.l10n.type.model.mixin',
    string='Type',
    domain="[('ir_form_view', '!=', False)]",
  )
  parent_id = fields.Many2one(
    comodel_name='ek.l10n.model.mixin',
    string='Parent',
    ondelete='cascade',
    readonly=True,
  )
  child_ids = fields.One2many(
    comodel_name='ek.l10n.model.mixin',
    inverse_name='parent_id',
    string='Children',
    readonly=True,
  )
  child_count = fields.Integer(
    compute='_compute_child_count', string='Children Count', readonly=True
  )
  # state = fields.Selection(selection=[('draft', _('Draft')), ('confirmed', _('Confirmed')), ('done', _('Done')),('cancel', _('Cancelled'))], default='draft', required=True)

  stage_id = fields.Many2one(
    'ek.l10n.stages.mixin',
    string='Stage',
    compute='_compute_user_and_stage_ids',
    store=True,
    readonly=False,
    ondelete='restrict',
    tracking=1,
    group_expand='_read_group_stage_ids',
    copy=False,
    index=True,
    domain="[('type_ids', '=', type_id)]",
  )

  user_id = fields.Many2one(
    'res.users',
    string='Assigned to',
    compute='_compute_user_and_stage_ids',
    store=True,
    readonly=False,
    tracking=True,
    default=lambda self: self.env.user,
    domain=lambda self: [
      (
        'groups_id',
        'in',
        self.env.ref('ek_base_type_object.group_type_object_user').id,
      )
    ],
  )

  # next 4 fields are computed in write (or create)
  assign_date = fields.Datetime('First assignment date')
  assign_hours = fields.Integer(
    'Time to first assignment (hours)',
    compute='_compute_assign_hours',
    store=True,
  )
  done_date = fields.Datetime('Close date', copy=False)
  done_hours = fields.Integer(
    'Time to close (hours)', compute='_compute_close_hours', store=True
  )
  confirmed_hours = fields.Integer(
    'Open Time (hours)',
    compute='_compute_open_hours',
    search='_search_open_hours',
  )

  active = fields.Boolean(default=True)

  company_id = fields.Many2one(
    related='type_id.company_id', string='Company', store=True, readonly=True
  )

  show_print_button = fields.Boolean(compute='_compute_show_print_button')

  show_button_next_stage = fields.Boolean(
    compute='_compute_show_button_next_stage'
  )

  show_button_cancel = fields.Boolean(compute='_compute_show_button_cancel')
  show_back_button = fields.Boolean(compute='_compute_show_back_button')
  show_button_close = fields.Boolean(compute='_compute_show_button_close')
  show_button_prev_stage = fields.Boolean(
    compute='_compute_show_button_prev_stage'
  )

  fold = fields.Boolean(related='stage_id.fold')

  date_last_stage_update = fields.Datetime(
    'Last Stage Update', copy=False, readonly=True
  )
  oldest_unanswered_customer_message_date = fields.Datetime(
    'Oldest Unanswered Customer Message Date'
  )
  next_stage_label = fields.Char(
    'Next Stage Label', compute='_compute_next_stage_label'
  )
  prev_stage_label = fields.Char(
    'Prev Stage Label', compute='_compute_prev_stage_label'
  )
  block_type = fields.Boolean()
  has_confirmed_type = fields.Boolean()
  l10n_ec_check_model_type = fields.Boolean(default=True)

  @api.depends('type_id', 'stage_id')
  def _compute_next_stage_label(self):
    for record in self:
      if record.stage_id:
        record.next_stage_label = record.type_id.next_stage_label(record)
      else:
        record.next_stage_label = _('Next Stage')

  @api.depends('type_id', 'stage_id')
  def _compute_prev_stage_label(self):
    for record in self:
      if record.stage_id:
        record.prev_stage_label = record.type_id.prev_stage_label(record)
      else:
        record.prev_stage_label = _('Prev Stage')

  @api.depends('type_id', 'stage_id')
  def _compute_show_button_close(self):
    for record in self:
      if record.type_id:
        record.show_button_close = record.type_id.show_button_close(record)
      else:
        record.show_button_close = False

  @api.depends('type_id', 'stage_id')
  def _compute_show_button_prev_stage(self):
    for record in self:
      if record.type_id:
        record.show_button_prev_stage = record.type_id.show_button_prev_stage(
          record
        )
      else:
        record.show_button_prev_stage = False

  @api.depends('type_id', 'stage_id')
  def _compute_show_button_cancel(self):
    for record in self:
      if record.type_id:
        record.show_button_cancel = record.type_id.show_button_cancel(record)
      else:
        record.show_button_cancel = False

  @api.depends('type_id', 'stage_id')
  def _compute_show_back_button(self):
    for record in self:
      if record.type_id:
        record.show_back_button = record.type_id.show_back_button(record)
      else:
        record.show_back_button = False

  @api.depends('type_id', 'stage_id')
  def _compute_show_button_next_stage(self):
    for record in self:
      if record.type_id:
        record.show_button_next_stage = record.type_id.show_button_next_stage(
          record
        )
      else:
        record.show_button_next_stage = False

  @api.depends('type_id', 'stage_id')
  def _compute_show_print_button(self):
    for record in self:
      if record.type_id:
        record.show_print_button = record.type_id.show_print_button(record)
      else:
        record.show_print_button = False

  @api.onchange('type_id')
  def _onchange_type_id(self):
    if self.type_id:
      self.type_id._get_defaults_fields(self)

    return {
      'type': 'ir.actions.client',
      'tag': 'reload',
    }

  @api.depends('child_ids')
  def _compute_child_count(self):
    for record in self:
      record.child_count = len(record.child_ids)

  @api.constrains('parent_id')
  def check_parent_id(self):
    if not self._check_recursion():
      raise UserError(_('You cannot create recursive Models.'))

  @api.depends('assign_date')
  def _compute_assign_hours(self):
    for request in self:
      create_date = fields.Datetime.from_string(request.create_date)
      if (
        create_date
        and request.assign_date
        and request.type_id.resource_calendar_id
      ):
        duration_data = (
          request.type_id.resource_calendar_id.get_work_duration_data(
            create_date,
            fields.Datetime.from_string(request.assign_date),
            compute_leaves=True,
          )
        )
        request.assign_hours = duration_data['hours']
      else:
        request.assign_hours = False

  @api.depends('create_date', 'done_date')
  def _compute_close_hours(self):
    for request in self:
      create_date = fields.Datetime.from_string(request.create_date)
      if (
        create_date
        and request.done_date
        and request.type_id
        and request.type_id.resource_calendar_id
      ):
        duration_data = (
          request.type_id.resource_calendar_id.get_work_duration_data(
            create_date,
            fields.Datetime.from_string(request.done_date),
            compute_leaves=True,
          )
        )
        request.done_hours = duration_data['hours']
      else:
        request.done_hours = False

  @api.depends('done_hours')
  def _compute_open_hours(self):
    for request in self:
      if request.create_date:  # fix from https://github.com/odoo/enterprise/commit/928fbd1a16e9837190e9c172fa50828fae2a44f7
        if request.done_date:
          time_difference = request.done_date - fields.Datetime.from_string(
            request.create_date
          )
        else:
          time_difference = fields.Datetime.now() - fields.Datetime.from_string(
            request.create_date
          )
        request.confirmed_hours = (
          time_difference.seconds
        ) / 3600 + time_difference.days * 24
      else:
        request.confirmed_hours = 0

  @api.model
  def _search_open_hours(self, operator, value):
    dt = fields.Datetime.now() - relativedelta(hours=value)

    d1, d2 = False, False
    if operator in ['<', '<=', '>', '>=']:
      d1 = [
        '&',
        ('done_date', '=', False),
        ('create_date', expression.TERM_OPERATORS_NEGATION[operator], dt),
      ]
      d2 = ['&', ('done_date', '!=', False), ('done_hours', operator, value)]
    elif operator in ['=', '!=']:
      subdomain = [
        '&',
        ('create_date', '>=', dt.replace(minute=0, second=0, microsecond=0)),
        ('create_date', '<=', dt.replace(minute=59, second=59, microsecond=99)),
      ]
      if operator in expression.NEGATIVE_TERM_OPERATORS:
        subdomain = expression.distribute_not(subdomain)
      d1 = expression.AND([[('done_date', '=', False)], subdomain])
      d2 = ['&', ('done_date', '!=', False), ('done_hours', operator, value)]
    return expression.OR([d1, d2])

  @api.depends('type_id')
  def _compute_user_and_stage_ids(self):
    for request in self.filtered(lambda request: request.type_id):
      if not request.user_id:
        request.user_id = request.type_id._determine_user_to_assign()[
          request.type_id.id
        ]
      if (
        not request.stage_id
        or request.stage_id not in request.type_id.stage_ids
      ):
        request.stage_id = request.type_id._determine_stage()[
          request.type_id.id
        ]

  def _track_template(self, changes):
    res = super(EkL10nModelMixin, self)._track_template(changes)

    _object = self[0]
    # if 'stage_id' in changes and _object.stage_id and _object.stage_id.template_id and _object.partner_email and (
    #     not self.env.user.partner_id or not _object.partner_id or _object.partner_id != self.env.user.partner_id
    #     or self.env.user._is_portal() or _object._context.get('mail_notify_author')
    # ):
    if (
      'stage_id' in changes
      and _object.stage_id
      and _object.stage_id.template_id
    ):
      res['stage_id'] = (
        _object.stage_id.template_id,
        {
          'auto_delete_keep_log': False,
          'subtype_id': self.env['ir.model.data']._xmlid_to_res_id(
            'mail.mt_note'
          ),
          'email_layout_xmlid': 'mail.mail_notification_light',
        },
      )
    return res

  def _get_sequence_for_new_number(self):
    for rec in self:
      seq = False
      if self.env.context.get('foce_sequence', False):
        if rec.type_id:
          _type = rec.type_id
          if _type and _type.has_internal_sequence and _type.internal_sequence:
            seq = _type.internal_sequence

      if not seq and rec.name == '/' and rec.type_id:
        _type = rec.type_id
        if _type and _type.has_internal_sequence and _type.internal_sequence:
          seq = _type.internal_sequence

      return seq

  @api.model_create_multi
  def create(self, list_value):
    now = fields.Datetime.now()
    # determine user_id and stage_id if not given. Done in batch.
    types = self.env['ek.l10n.type.model.mixin'].browse(
      [vals['type_id'] for vals in list_value if vals.get('type_id')]
    )
    types_default_map = dict.fromkeys(types.ids, dict())
    for _type in types:
      types_default_map[_type.id] = {
        'stage_id': _type._determine_stage()[_type.id].id,
        'user_id': _type._determine_user_to_assign()[_type.id].id,
      }

    for vals in list_value:
      if vals.get('type_id'):
        type_default = types_default_map[vals['type_id']]
        if 'stage_id' not in vals:
          vals['stage_id'] = type_default['stage_id']
        # Note: this will break the randomly distributed user assignment. Indeed, it will be too difficult to
        # equally assigned user when creating ticket in batch, as it requires to search after the last assigned
        # after every ticket creation, which is not very performant. We decided to not cover this user case.
        if 'user_id' not in vals:
          vals['user_id'] = type_default['user_id']
        if vals.get(
          'user_id'
        ):  # if a user is finally assigned, force ticket assign_date and reset assign_hours
          vals['assign_date'] = fields.Datetime.now()
          vals['assign_hours'] = 0

      if vals.get('stage_id'):
        vals['date_last_stage_update'] = now
      vals['oldest_unanswered_customer_message_date'] = now

    # context: no_log, because subtype already handle this
    objects = super(EkL10nModelMixin, self).create(list_value)

    # make customer follower
    for record in objects:
      seq = record._get_sequence_for_new_number()
      if seq:
        next_name = seq.next_by_id()
        if next_name:
          record.write({'name': next_name})

      # record._portal_ensure_token()

    return objects

  def write(self, vals):
    # we set the assignation date (assign_date) to now for tickets that are being assigned for the first time
    # same thing for the closing date
    assigned_object = closed_object = self.browse()
    if vals.get('user_id'):
      assigned_object = self.filtered(lambda fobject: not fobject.assign_date)

    if vals.get('stage_id'):
      if self.env['ek.l10n.stages.mixin'].browse(vals.get('stage_id')).fold:
        closed_object = self.filtered(lambda fobject: not fobject.done_date)
      else:  # auto reset the 'closed_by_partner' flag
        vals['done_date'] = False

    now = fields.Datetime.now()

    # update last stage date when changing stage
    if 'stage_id' in vals:
      vals['date_last_stage_update'] = now

    res = super(EkL10nModelMixin, self - assigned_object - closed_object).write(
      vals
    )
    res &= super(EkL10nModelMixin, assigned_object - closed_object).write(
      dict(
        vals,
        **{
          'assign_date': now,
        },
      )
    )
    res &= super(EkL10nModelMixin, closed_object - assigned_object).write(
      dict(
        vals,
        **{
          'done_date': now,
          'oldest_unanswered_customer_message_date': False,
        },
      )
    )
    res &= super(EkL10nModelMixin, assigned_object & closed_object).write(
      dict(
        vals,
        **{
          'assign_date': now,
          'done_date': now,
        },
      )
    )

    return res

  def action_next_stage(self):
    self.ensure_one()
    value = self.action_requeired_stage_fields(self.stage_id)
    if value:
      raise UserError(
        _('Please fill the following required fields:\n\n%s')
        % ('\n'.join(value))
      )
    self.write({'block_type': True})
    stage = self.type_id.action_next_stage(self)

    return stage

  def action_requeired_stage_fields(self, stage):
    value = []
    if self.type_id.fields_ids:
      for field in self.type_id.fields_ids.filtered(
        lambda f: f.has_required and f.required_stage_ids
      ):
        for stage_requeired in field.required_stage_ids:
          if stage_requeired.id == stage.id:
            if not self[field.field_id.name]:
              value.append(field.label or field.field_id.field_description)

    return value

  def action_prev_stage(self):
    self.ensure_one()
    self.write({'block_type': True})
    return self.type_id.action_prev_stage(self)

  def action_print(self):
    self.ensure_one()
    return self.type_id.print_report(self)

  def action_cancel(self):
    self.ensure_one()
    return self.type_id.action_cancel(self)

  def action_close(self):
    self.ensure_one()
    return self.type_id.action_close(self)

  def _set_object_attributes(self, xobject, fields_object=[], fields_value=[]):
    if len(fields_object) != len(fields_value):
      raise UserError(
        _('The number of fields does not match the number of values.')
      )
    if not xobject:
      raise UserError(_('The record does not exist.'))

    for index, field in enumerate(fields_object):
      if hasattr(xobject, field):
        model_object = getattr(self, fields_value[index], None)
        if model_object:
          if hasattr(model_object, 'id'):
            setattr(xobject, field, model_object.id)
          else:
            setattr(xobject, field, model_object)
