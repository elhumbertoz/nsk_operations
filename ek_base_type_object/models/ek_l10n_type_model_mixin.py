import base64

from odoo import Command, _, api, fields, models
from odoo.exceptions import UserError


class EkL10nTypeModelMixin(models.Model):
  _name = 'ek.l10n.type.model.mixin'
  _description = _('Type Generic Model')

  default_inherit_dinamic_view = 'view_ek_l10n_model_mixin_form'
  default_inherit_position_view = 'after'
  default_inherit_xpath_view = '//group[last()]'
  default_module_dinamic_name = 'ek_base_type_object'

  @api.model
  def _get_object_validation_model_names(self):
    res = ['ek.l10n.model.mixin']
    for model in (
      self.env['ir.model']
      .sudo()
      .search([('field_id.name', '=', 'l10n_ec_check_model_type')])
    ):
      res.append(model.model)
    return res

  # Example
  # ****
  # {model_name} = {
  #    "_inherit_dinamic_view": "inherit view",
  #    "_inherit_position_view": "inherit position",
  #    "_inherit_xpath_view": "inherit xpath",
  #    "_module_dinamic_name": "inherit module",
  #    "_inherit_dinamic_fields_position": [{
  #          "name": "date_start",
  #          "xpath": "//group[last()]",
  #          "position": "before",
  #    }],
  # }
  #
  # ****

  def _get_object_validation_model_config(self):
    res = {
      self._name: {
        '_inherit_dinamic_view': 'view_ek_l10n_model_mixin_form',
        '_inherit_position_view': 'after',
        '_inherit_xpath_view': '//group[last()]',
        '_module_dinamic_name': self._module or 'ek_base_type_object',
        '_inherit_dinamic_fields_position': [],
      }
    }
    return res

  def _default_stage_ids(self):
    default_stages = self.env['ek.l10n.stages.mixin']
    for xml_id in [
      'stage_new',
      'stage_in_progress',
      'stage_solved',
      'stage_cancelled',
    ]:
      stage = self.env.ref(
        'ek_base_type_object.%s' % xml_id, raise_if_not_found=False
      )
      if stage:
        default_stages += stage
    if not default_stages:
      default_stages = self.env['ek.l10n.stages.mixin'].create(
        {
          'name': _('Draft'),
          'sequence': 0,
        }
      )
    return [Command.set(default_stages.ids)]

  code = fields.Char(string='Code', required=True, copy=True)
  name = fields.Char(string='Name', required=True, copy=True)

  fields_ids = fields.One2many(
    string=_('Fields'),
    comodel_name='ek.l10n.type.field.mixin',
    inverse_name='type_model_id',
    copy=True,
  )

  ir_form_view = fields.Many2one(
    comodel_name='ir.ui.view', string='Form View', readonly=True, copy=False
  )

  model_id = fields.Many2one(
    comodel_name='ir.model',
    string='Flow Model',
    domain=lambda self: [
      ('model', 'in', self._get_object_validation_model_names())
    ],
  )

  model = fields.Char(related='model_id.model', index=True, store=True)

  count_used_types = fields.Integer(compute='_compute_count_used_types')

  used_model_types_ids = fields.One2many(
    comodel_name='ek.l10n.model.mixin',
    inverse_name='type_id',
  )

  active = fields.Boolean(string='Active', default=True, copy=False)

  resource_calendar_id = fields.Many2one(
    comodel_name='resource.calendar',
    string='Working Schedule',
    # compute="_compute_resource_calendar",
    store=True,
    readonly=False,
    copy=True,
    index=True,
    tracking=True,
  )

  stage_ids = fields.Many2many(
    'ek.l10n.stages.mixin',
    relation='ek_l10n_type_model_stage_rel',
    string='Stages',
    default=_default_stage_ids,
    copy=True,
    help=_(
      "Stages the team will use. This type's tickets will only be able to be in these stages."
    ),
  )

  member_ids = fields.Many2many(
    'res.users',
    string='Type Members',
    domain=lambda self: [
      (
        'groups_id',
        'in',
        self.env.ref('ek_base_type_object.group_type_object_user').id,
      )
    ],
    default=lambda self: self.env.user,
    copy=True,
    required=True,
  )

  company_id = fields.Many2one(
    'res.company',
    string='Company',
    store=True,
    default=lambda self: self.env.company,
  )

  report_id = fields.Many2one(
    comodel_name='ir.actions.report',
    string='Report',
    domain="[('model_id', '=', model_id)]",
  )

  has_internal_sequence = fields.Boolean(string='Use Internal Sequence')
  internal_sequence = fields.Many2one(
    'ir.sequence', string='Type Object Sequence'
  )

  next_stage_parent_id = fields.Many2one(
    'ek.l10n.stages.mixin',
    string='Parent Stage',
    copy=False,
    help=_('Parent Stage for cloning this type.'),
    tracking=True,
    domain="[('id', 'in', stage_ids)]",
  )

  notify_stage_ids = fields.One2many(
    comodel_name='ek.l10n.type.notify.stage.model.mixin',
    inverse_name='type_id',
    string='Notify Stages',
    copy=True,
  )

  group_id = fields.Many2one(
    comodel_name='ek.l10n.group.type.model.mixin', string='Group', copy=True
  )

  @api.model
  def calculate_count_used_types(self):
    count_object = 0
    for xmodel in (
      self.env['ir.model']
      .sudo()
      .search([('field_id.name', '=', 'l10n_ec_check_model_type')])
    ):
      count_object += self.env[xmodel.model].search_count(
        [('type_id', '=', self.id)]
      )

    return len(self.used_model_types_ids) + count_object

  def _compute_count_used_types(self):
    for rec in self:
      rec.count_used_types = rec.calculate_count_used_types()

  def action_create_view(self):
    for rec in self:
      if not rec.stage_ids:
        raise UserError(
          _("You can't create this type without fields and stages.")
        )

      rec._create_form_view()

  def action_delete_view(self):
    for rec in self:
      # if rec.count_used_types > 0:
      #     raise UserError(_("You can't delete this type because it is used in other types. Please acheive this type or delete the used types."))

      rec.ir_form_view.sudo().unlink()

  def _create_form_view(self):
    _config_view = {}
    if not hasattr(self.env[self.model], '_get_object_validation_model_config'):
      _config_view = self._get_object_validation_model_config()
    else:
      _config_view = self.env[self.model]._get_object_validation_model_config()

    config_view = _config_view.get(self.model, {})

    ref_view = '%s.%s' % (
      config_view.get('_module_dinamic_name', self.default_module_dinamic_name),
      config_view.get(
        '_inherit_dinamic_view', self.default_inherit_dinamic_view
      ),
    )
    inherit_id = self.env.ref(ref_view, False)
    if not inherit_id:
      raise UserError(_('View %s dont not exist' % ref_view))

    form_view_id = (
      self.env['ir.ui.view']
      .sudo()
      .create(
        {
          'name': 'ek.l10n.type.model.mixin.%s' % self.code,
          'type': 'form',
          'model': self.model,
          'mode': 'extension',
          'inherit_id': inherit_id.id,
          'arch_base': self._prepare_create_form_views(),
          'active': True,
        }
      )
    )

    self.ir_form_view = form_view_id

  def _encode_text_base64(self, text):
    # Convertir el texto a bytes
    bytes_text = text.encode('utf-8')
    # Codificar los bytes en base64
    bytes_base64 = base64.b64encode(bytes_text)
    # Convertir los bytes codificados en base64 a una cadena de texto
    return bytes_base64.decode('utf-8')

  def _aditional_domain(self, field, domain=[]):
    _domain = (
      field.definition_domain
      and domain + eval(field.definition_domain)
      or domain
    )

    return (
      str(_domain).replace('&', '&amp;').replace("'@", '').replace("@'", '')
    )

  def _prepare_create_form_fields(self, field):
    _help = field.help or field.field_id.help
    if not _help:
      _help = ''
    widget = (
      field.widget_id and """widget ='%s' """ % field.widget_id.value or ''
    )
    readonly = ''
    if field.stage_ids:
      readonly = """readonly='stage_id in %s or fold'""" % field.stage_ids.ids
    else:
      readonly = """readonly='fold'"""

    invisible = 'type_id != %s' % self.id
    if field.required_stage_ids:
      required = 'stage_id in %s' % field.required_stage_ids.ids
    else:
      required = (
        (field.field_id.required or field.has_required)
        and 'type_id == %s' % self.id
        or False
      )

    if field.invisible_stage_ids:
      invisible = 'type_id != %s or stage_id in %s' % (
        self.id,
        field.invisible_stage_ids.ids,
      )
    else:
      invisible = 'type_id != %s' % self.id

    if (
      field.field_id.ttype in ['many2many', 'many2one', 'one2many']
      and field.definition_domain
    ):
      _str_field = (
        """\n\t\t\t<field name="%s" required="%s" invisible="%s" string="%s" domain="%s" help="%s" force_save="1" placeholder="%s" %s %s />"""
        % (
          field.field_id.name,
          required,
          invisible,
          field.label or field.field_id.field_description,
          # field.definition_domain.replace("&","&amp;"),
          self._aditional_domain(field),
          _help,
          field.placeholder or '',
          widget,
          readonly,
        )
      )
    else:
      _str_field = (
        """\n\t\t\t<field name="%s" invisible="%s" string="%s" required="%s" help="%s" force_save="1" placeholder="%s" %s %s />"""
        % (
          field.field_id.name,
          invisible,
          field.label or field.field_id.field_description,
          required,
          _help,
          field.placeholder or '',
          widget,
          readonly,
        )
      )

    return _str_field

  def _prepare_create_group_xpath_view(self, struct, config_view):
    arch_base = """\n\t<xpath expr="%s" position="%s">\n""" % (
      config_view.get('_inherit_xpath_view', self.default_inherit_xpath_view),
      config_view.get(
        '_inherit_position_view', self.default_inherit_position_view
      ),
    )
    internal_group = """\t\t<group invisible='type_id != %s'>""" % self.id
    for group, kfields in struct.items():
      if group:
        internal_group += (
          """\n\t\t\t<group name="%s" string="%s" invisible='type_id != %s'>%s\n\t\t\t</group>"""
          % (self._encode_text_base64(group), group, self.id, ''.join(kfields))
        )
      else:
        internal_group += ''.join(kfields)

    internal_group += """\n\t\t</group>\n\t</xpath>"""

    return arch_base + internal_group

  def _prepare_create_dinamic_fields_position_xpath_view(
    self, dinamic_fields_position, xpath_fields
  ):
    arch_base = ''
    for field in dinamic_fields_position:
      name = field.get('name')
      if name not in xpath_fields:
        continue

      xpath = field.get('xpath')
      position = field.get('position')
      arch_base += """\n\t<xpath expr="%s" position="%s">%s\n\t</xpath>\n""" % (
        xpath,
        position,
        xpath_fields.get(name),
      )

    return arch_base

  def _get_fields_dinamic_names(self, dinamic_fields_position):
    return [field.get('name') for field in dinamic_fields_position]

  def _prepare_create_form_views(self):
    struct = {}
    struct_dinamic_fields = {}
    xpath_fields = {}
    arch_base = ''
    if not hasattr(self.env[self.model], '_get_object_validation_model_config'):
      _config_view = self._get_object_validation_model_config()
    else:
      _config_view = self.env[self.model]._get_object_validation_model_config()

    config_view = _config_view.get(self.model, {})
    dinamic_fields_position = []
    if config_view.get('_inherit_dinamic_fields_position', []):
      dinamic_fields_position = config_view.get(
        '_inherit_dinamic_fields_position'
      )

    check_dinamic_fields = self._get_fields_dinamic_names(
      dinamic_fields_position
    )

    for field in self.fields_ids:
      if (
        field.group_name not in struct
        and field.field_id.name not in check_dinamic_fields
      ):
        struct[field.group_name] = []

      _str_field = self._prepare_create_form_fields(field)

      xpath_fields[field.field_id.name] = _str_field

      if field.field_id.name not in check_dinamic_fields:
        struct[field.group_name].append(_str_field)

    xpath_grpup_view = self._prepare_create_group_xpath_view(
      struct, config_view
    )
    xpath_dinamic_fields_view = (
      self._prepare_create_dinamic_fields_position_xpath_view(
        dinamic_fields_position, xpath_fields
      )
    )

    arch_base += xpath_grpup_view
    arch_base += xpath_dinamic_fields_view
    return """<?xml version="1.0"?><data>%s</data>""" % arch_base

  def _get_defaults_fields(self, _model_mixin_object):
    for rec in self:
      for field in rec.fields_ids:
        if hasattr(_model_mixin_object, field.field_id.name):
          if field.apply_default:
            if field.field_id.ttype in ['many2one']:
              setattr(
                _model_mixin_object, field.field_id.name, field.init_many2one.id
              )
            elif field.field_id.ttype in ['float']:
              setattr(
                _model_mixin_object, field.field_id.name, field.init_float
              )
            elif field.field_id.ttype in ['integer']:
              setattr(
                _model_mixin_object, field.field_id.name, field.init_integer
              )
            elif field.field_id.ttype in ['selection']:
              value = (
                field.init_selection and field.init_selection.value or False
              )
              setattr(_model_mixin_object, field.field_id.name, value)
            elif field.field_id.ttype in ['char', 'text']:
              setattr(_model_mixin_object, field.field_id.name, field.init_text)
            elif field.field_id.ttype in ['date']:
              setattr(_model_mixin_object, field.field_id.name, field.init_date)
            elif field.field_id.ttype in ['datetime']:
              setattr(
                _model_mixin_object, field.field_id.name, field.init_datetime
              )
            else:
              setattr(_model_mixin_object, field.field_id.name, False)
          else:
            setattr(_model_mixin_object, field.field_id.name, False)

  def view_objects(self):
    action = {
      'name': self.name,
      'view_type': 'tree',
      'view_mode': 'list,form',
      'res_model': self.model,
      'type': 'ir.actions.act_window',
      'context': self.env.context,
      'domain': [['type_id', '=', self.id]],
    }
    return action

  def _determine_user_to_assign(self):
    return {self.id: self.env.user}

  def _determine_stage(self):
    """Get a dict with the stage (per type) that should be set as first to a created ticket
    :returns a mapping of type identifier with the stage (maybe an empty record).
    :rtype : dict (key=type_id, value=record of helpdesk.stage)
    """
    result = dict.fromkeys(self.ids, self.env['ek.l10n.stages.mixin'])
    for _type in self:
      result[_type.id] = self.env['ek.l10n.stages.mixin'].search(
        [('type_ids', 'in', _type.id)], order='sequence', limit=1
      )
      return result

  def _default_stage_ids(self):
    default_stages = self.env['ek.l10n.stages.mixin']
    for xml_id in [
      'stage_new',
      'stage_in_progress',
      'stage_solved',
      'stage_cancelled',
    ]:
      stage = self.env.ref(
        'ek.l10n.stages.mixin.%s' % xml_id, raise_if_not_found=False
      )
      if stage:
        default_stages += stage
    if not default_stages:
      default_stages = self.env['ek.l10n.stages.mixin'].create(
        {
          'name': _('Daft'),
          'sequence': 0,
        }
      )
    return [Command.set(default_stages.ids)]

  def print_report(self, tobjects):
    if self.report_id:
      report_action = self.report_id.report_action(tobjects)
      return report_action
    elif tobjects.stage_id.report_id:
      report_action = self.report_id.report_action(tobjects)
    else:
      raise UserError(_('No report defined for this type of object.'))

    report_action['close_on_report_download'] = True
    return report_action

  def show_print_button(self, tobjects):
    return self.report_id or tobjects.stage_id.report_id

  def show_button_next_stage(self, tobjects):
    actual_stage = tobjects.stage_id
    if actual_stage.fold:
      return False
    if self.stage_ids:
      next_stage = self.stage_ids.filtered(
        lambda r: r.sequence > actual_stage.sequence
      )
      if next_stage:
        return True
    return False

  def show_button_prev_stage(self, tobjects):
    actual_stage = tobjects.stage_id
    if actual_stage.fold and not actual_stage.canceled_stage:
      return False
    if self.stage_ids:
      prev_stage = self.stage_ids.filtered(
        lambda r: r.sequence < actual_stage.sequence
        and not r.canceled_stage
        and not r.fold
      )
      if prev_stage:
        return True
    return False

  def action_next_stage(self, tobjects):
    actual_stage = tobjects.stage_id
    if actual_stage and self.stage_ids:
      next_stage = self.stage_ids.filtered(
        lambda r: r.sequence > actual_stage.sequence and not r.canceled_stage
      )
      if next_stage:
        stage = next_stage[0]
        tobjects.write({'stage_id': stage.id})
        self.action_close_for_stage(tobjects, stage)
        self.notify_schedule(tobjects)

        return stage
    return False

  def action_prev_stage(self, tobjects):
    actual_stage = tobjects.stage_id
    if actual_stage and self.stage_ids:
      prev_stage = self.stage_ids.filtered(
        lambda r: r.sequence < actual_stage.sequence and not r.canceled_stage
      )
      if prev_stage:
        stage = prev_stage[0]
        tobjects.write({'stage_id': stage.id})
        return stage
    return False

  def next_stage_label(self, tobjects):
    actual_stage = tobjects.stage_id
    if actual_stage and self.stage_ids:
      next_stage = self.stage_ids.filtered(
        lambda r: r.sequence > actual_stage.sequence and not r.canceled_stage
      )
      if next_stage:
        stage = next_stage[0]
        return stage.name

    return _('Next Stage')

  def prev_stage_label(self, tobjects):
    actual_stage = tobjects.stage_id
    if actual_stage and self.stage_ids:
      prev_stage = self.stage_ids.filtered(
        lambda r: r.sequence < actual_stage.sequence and not r.canceled_stage
      )
      if prev_stage:
        stage = prev_stage[0]
        return stage.name

    return _('Prev Stage')

  def show_button_cancel(self, tobjects):
    return tobjects.stage_id.show_canceled_button

  def show_back_button(self, tobjects):
    return tobjects.stage_id.show_back_button

  def show_button_close(self, tobjects):
    return tobjects.stage_id.show_close_button and not tobjects.stage_id.fold

  def action_cancel(self, tobjects):
    tobjects.write(
      {'stage_id': self.stage_ids.filtered(lambda r: r.canceled_stage)[0].id}
    )
    self.notify_schedule(tobjects)

  def action_close(self, tobjects):
    tobjects.write(
      {
        'stage_id': self.stage_ids.filtered(
          lambda r: r.fold and not r.canceled_stage
        )[0].id
      }
    )
    self.action_close_for_stage(tobjects, self.next_stage_parent_id)

  def action_close_for_stage(self, tobjects, stage):
    if tobjects.parent_id and stage:
      tobjects.parent_id.write({'stage_id': stage.id})

  # notify_stage_ids
  def notify_schedule(self, tobjects):
    for rec in self:
      for notify_stage in rec.notify_stage_ids.filtered(
        lambda r: r.stage_id == tobjects.stage_id
      ):
        for user in notify_stage.user_ids:
          tobjects.activity_schedule(
            activity_type_id=notify_stage.activity_id.id,
            date_deadline=fields.Datetime.add(
              fields.Datetime.now(),
              days=notify_stage.delay_count
              or notify_stage.activity_id.delay_count,
            ),
            summary=f'Reminder, document {rec.name} is at stage {tobjects.stage_id.name}',
            note=notify_stage.note
            or f'This notification has been generated because document {rec.name} needs your attention at the stage it is in. Please pay attention to this activity until you complete your process.',
            user_id=user.id,
          )
