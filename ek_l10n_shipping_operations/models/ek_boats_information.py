import datetime

from odoo import _, api, fields, models
from odoo.exceptions import UserError


class ek_boats_information(models.Model):
  _name = 'ek.boats.information'
  _description = 'Create shipping boats information'
  _inherit = ['mail.thread', 'mail.activity.mixin']

  @api.model
  def _default_eta_ata(self):
    """Valor por defecto para ETA y ATA: fecha de hoy"""
    default_value = fields.Datetime.now()
    return default_value

  @api.model
  def _default_etd_atd(self):
    """Valor por defecto para ETD y ATD: fecha de hoy + 1 semana"""
    default_value = fields.Datetime.now() + datetime.timedelta(weeks=1)
    return default_value

  @api.model
  def default_get(self, fields_list):
    """Sobrescribir default_get para asegurar que los valores por defecto se apliquen"""
    defaults = super(ek_boats_information, self).default_get(fields_list)

    # Aplicar valores por defecto para fechas
    if 'eta' in fields_list:
      defaults['eta'] = self._default_eta_ata()

    if 'ata' in fields_list:
      defaults['ata'] = self._default_eta_ata()

    if 'etd' in fields_list:
      defaults['etd'] = self._default_etd_atd()

    if 'atd' in fields_list:
      defaults['atd'] = self._default_etd_atd()

    return defaults

  def test_journey_defaults(self):
    """
    Método para probar que los valores por defecto se apliquen correctamente.
    Solo para propósitos de testing - no usar en producción.
    """
    test_results = []

    # Test 1: Verificar método default_get
    try:
      defaults = self.default_get(['eta', 'ata', 'etd', 'atd'])

      if 'eta' in defaults and defaults['eta']:
        test_results.append(
          f'✅ Test 1a PASSED: ETA default set to {defaults["eta"]}'
        )
      else:
        test_results.append('❌ Test 1a FAILED: ETA default not set')

      if 'ata' in defaults and defaults['ata']:
        test_results.append(
          f'✅ Test 1b PASSED: ATA default set to {defaults["ata"]}'
        )
      else:
        test_results.append('❌ Test 1b FAILED: ATA default not set')

      if 'etd' in defaults and defaults['etd']:
        test_results.append(
          f'✅ Test 1c PASSED: ETD default set to {defaults["etd"]}'
        )
      else:
        test_results.append('❌ Test 1c FAILED: ETD default not set')

      if 'atd' in defaults and defaults['atd']:
        test_results.append(
          f'✅ Test 1d PASSED: ATD default set to {defaults["atd"]}'
        )
      else:
        test_results.append('❌ Test 1d FAILED: ATD default not set')

    except Exception as e:
      test_results.append(f'❌ Test 1 ERROR: {str(e)}')

    # Test 2: Verificar métodos helper directamente
    try:
      eta_default = self._default_eta_ata()
      ata_default = self._default_eta_ata()
      etd_default = self._default_etd_atd()
      atd_default = self._default_etd_atd()

      if eta_default:
        test_results.append(
          f'✅ Test 2a PASSED: _default_eta_ata returns {eta_default}'
        )
      else:
        test_results.append('❌ Test 2a FAILED: _default_eta_ata returns None')

      if ata_default:
        test_results.append(
          f'✅ Test 2b PASSED: _default_eta_ata returns {ata_default}'
        )
      else:
        test_results.append('❌ Test 2b FAILED: _default_eta_ata returns None')

      if etd_default:
        test_results.append(
          f'✅ Test 2c PASSED: _default_etd_atd returns {etd_default}'
        )
      else:
        test_results.append('❌ Test 2c FAILED: _default_etd_atd returns None')

      if atd_default:
        test_results.append(
          f'✅ Test 2d PASSED: _default_etd_atd returns {atd_default}'
        )
      else:
        test_results.append('❌ Test 2d FAILED: _default_etd_atd returns None')

    except Exception as e:
      test_results.append(f'❌ Test 2 ERROR: {str(e)}')

    return test_results

  def action_open_documents_request(self):
    """
    Abre la vista de solicitudes del viaje actual.
    Pasa el contexto necesario para pre-llenar los campos de barco y viaje.
    """
    self.ensure_one()


    # Crear el contexto para la nueva solicitud
    context = {
      'default_journey_crew_id': self.id,
      'default_ek_ship_registration_id': self.ship_name_id.id
      if self.ship_name_id
      else False,
      'search_default_group_by_journey_crew_id': 1,
      'search_default_group_by_ek_ship_registration_id': 1,
    }

    # Si el barco tiene business_name_id, incluirlo en el contexto
    if self.ship_name_id and self.ship_name_id.bussiness_name_id:
      context['default_res_partner_id'] = self.ship_name_id.bussiness_name_id.id


    return {
      'name': _('Solicitudes del Viaje %s') % self.name,
      'type': 'ir.actions.act_window',
      'res_model': 'ek.operation.request',
      'view_mode': 'tree,form',
      'context': context,
      'domain': [('journey_crew_id', '=', self.id)],
      'target': 'current',
    }

  name = fields.Char(string='name', default='/', copy=False)
  bussiness_name_id = fields.Many2one('res.partner', string='Shipper')
  ship_name_id = fields.Many2one('ek.ship.registration', string='Ship Name')
  capital_name_id = fields.Many2one('res.partner', string='Capital Name')
  boat_color = fields.Char(string='Boat Color')
  ship_flag_id = fields.Many2one('res.country', string='Ship Flag')
  boat_registration = fields.Char(string='Boat Registration')
  crew_ids = fields.Many2many(
    'res.partner', string='Crew', domain="[('is_crew', '=', True)]"
  )
  ship_document_certificate_count_expired = fields.Integer(
    related='ship_name_id.ship_document_certificate_count_expired',
  )

  @api.onchange('crew_ids')
  def _onchange_warning_crew_ids(self):
    if self.crew_ids:
      selected_crew = self.crew_ids[-1]
      if not selected_crew.ek_academic_courses_ids:
        message = f'{selected_crew.name} no tiene ningún tipo de documento.'
        return {
          'warning': {
            'title': _('Warning Message'),
            'message': _(message),
          }
        }
      else:
        expired_documents = []
        for line in selected_crew.ek_academic_courses_ids:
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
          message = f'{selected_crew.name} tiene {len(expired_documents)} documento(s) caducado(s) [{document_details}]'
          return {
            'warning': {
              'title': _('Warning Message'),
              'message': _(message),
            }
          }

  ek_boats_measures_1_id = fields.Many2one('ek.boats.measures')
  ek_boats_measures_2_id = fields.Many2one('ek.boats.measures')
  ek_boats_measures_3_id = fields.Many2one('ek.boats.measures')
  ek_boats_measures_4_id = fields.Many2one('ek.boats.measures')
  ek_boats_measures_5_id = fields.Many2one('ek.boats.measures')

  length = fields.Float(string='Length')
  sleeve = fields.Float(string='Sleeve')
  depth = fields.Float(string='Depth')
  trb = fields.Float(string='T.R.B.')
  trn = fields.Float(string='T.R.N.')

  company_id = fields.Many2one('res.company', default=lambda s: s.env.company)

  state_boats = fields.Selection(
    [
      ('sailing', 'Navegando'),
      ('port', 'En Puerto'),
    ],
    string='State Boats',
  )

  mrn_arribal = fields.Many2one(
    'ek.bl.manifest.record',
    string='MRN Arrival(Import Manifest)',
    tracking=True,
  )
  mrn_exit = fields.Many2one(
    'ek.bl.manifest.record', string='MRN Exit(Export Manifest)', tracking=True
  )

  ek_res_world_seaports_id = fields.Many2one(
    'ek.res.world.seaports', string='Puerto Origen'
  )
  ek_res_world_seaports_d_id = fields.Many2one(
    'ek.res.world.seaports', string='Puerto Destino '
  )
  travel_block = fields.Boolean(default=False)
  reason_arrival_ids = fields.Many2many(
    'reason.arrival',
    'reasons_arrival_boat_rel',
    'boat_id',
    string='Reasons Arrival',
  )

  #####Campos adicionales para el modulo de operaciones
  state = fields.Selection(
    [
      ('draft', 'Draft'),
      ('arribo', 'Arribo'),
      ('process', 'Process'),
      ('zarpe', 'Zarpe'),
      ('finished', 'Finished'),
      ('cancelled', 'Cancelled'),
    ],
    string='State Travel',
    default='draft',
    copy=False,
    tracking=True,
    ondelete={
      'draft': 'cascade',
    },
  )

  def get_operation_requests_list(self):
    search_operation_request = self.env['ek.operation.request'].search(
      [
        ('company_id', '=', self.company_id.id),
        ('journey_crew_id', '=', self.id),
        ('processing_status', 'in', ['developing']),
      ]
    )

    operation_list = []
    for record in search_operation_request:
      operation_list.append(f'{record.display_name}')

    return operation_list

  def write(self, vals):
    if 'state' in vals:
      new_state = vals.get('state')
      search_operation_request = self.get_operation_requests_list()
      if new_state == 'finished' and not self.assigned_regimen_70:
        if (
          not self.date_finished
          and not search_operation_request
          and not self.validate_finalized
        ):
          vals['date_finished'] = fields.Datetime.now()
          self.action_finalize_travel(state=False)
        elif search_operation_request:
          formatted_requests = '\n'.join(search_operation_request)
          message = _(
            'Cannot finalize the request as the following operations are not finalized:\n%s'
            % formatted_requests
          )
          raise UserError(message)
    return super(ek_boats_information, self).write(vals)

  ###arribo
  eta = fields.Datetime(
    string='ETA', copy=False, tracking=True, default=_default_eta_ata
  )
  ata = fields.Datetime(
    string='ATA', copy=False, tracking=True, default=_default_eta_ata
  )

  ##zarpe
  etd = fields.Datetime(
    string='ETD', copy=False, tracking=True, default=_default_etd_atd
  )
  atd = fields.Datetime(
    string='ATD', copy=False, tracking=True, default=_default_etd_atd
  )

  @api.constrains('eta', 'ata', 'etd', 'atd')
  def _check_dates_validate_(self):
    """
    Validaciones para los campos de fechas de arribo y zarpe en Journey:
    1. ETA debe ser menor o igual que ATA
    2. ETD debe ser menor o igual que ATD
    3. ETD debe ser mayor que ATA
    """
    for record in self:

      if not record.assigned_regimen_70:
        # Validación 1: eta debe ser menor o igual que ata
        if record.eta and record.ata and record.eta > record.ata:
          raise UserError(
            _(
              'ETA (Estimated Time of Arrival) must be less than or equal to ATA (Actual Time of Arrival).'
            )
          )

        # Validación 2: etd debe ser menor o igual que atd
        if record.etd and record.atd and record.etd > record.atd:
          raise UserError(
            _(
              'ETD (Estimated Time of Departure) must be less than or equal to ATD (Actual Time of Departure).'
            )
          )

        # Validación 3: etd debe ser mayor que ata
        if record.ata and record.etd and record.etd <= record.ata:
          raise UserError(
            _(
              'ETD (Estimated Time of Departure) must be greater than ATA (Actual Time of Arrival).'
            )
          )


  # fecha de terminado
  date_finished = fields.Datetime(
    string='Date Finished', copy=False, tracking=True
  )
  validate_finalized = fields.Boolean(string='Validate Finalized', copy=False)

  def action_finalize_travel(self, state=True):
    for record in self:
      record.ship_name_id.state_boats = 'sailing'
      if state:
        record.state = 'finished'
        record.date_finished = fields.Datetime.now()
        record.validate_finalized = True
      last_trip = self.env['trip.details.days'].search(
        [('ship_name_id', '=', record.ship_name_id.id)],
        order='id desc',
        limit=1,
      )
      arribo = self.env['ek.operation.request'].search(
        [
          ('ek_ship_registration_id', '=', record.ship_name_id.id),
          ('journey_crew_id', '=', record.id),
          ('type_event_boot', '=', 'arribo'),
        ],
        limit=1,
      )
      zarpe = self.env['ek.operation.request'].search(
        [
          ('ek_ship_registration_id', '=', record.ship_name_id.id),
          ('journey_crew_id', '=', record.id),
          ('type_event_boot', '=', 'zarpe'),
        ],
        limit=1,
      )

      value = {
        'ship_name_id': record.ship_name_id.id,
        'journey_crew_id': record.id,
        'ek_res_world_seaports_id': record.ek_res_world_seaports_id.id,
        'ek_res_world_seaports_d_id': record.ek_res_world_seaports_d_id.id,
        'eta': record.eta,
        'ata': record.ata,
        'etd': record.etd,
        'atd': record.atd,
        'type_event_arribo': arribo.type_event or False,
        'ek_boat_location_id_arribo': arribo.ek_boat_location_id.id or False,
        'agent_user_id_arribo': arribo.agent_user_id.id or False,
        'type_event_zarpe': zarpe.type_event or False,
        'ek_boat_location_id_zarpe': zarpe.ek_boat_location_id.id or False,
        'agent_user_id_zarpe': zarpe.agent_user_id.id or False,
      }
      id_trip = self.env['trip.details.days'].create(value)
      if last_trip:
        last_trip.write({'calculo_journey_crew_id': id_trip.journey_crew_id.id})

  def check_crew_id_validate(self):
    for record in self:
      data = []
      crew_search = self.search(
        [('company_id', '=', self.company_id.id), ('state', '=', 'process')]
      )
      for line in crew_search:
        for ln in line.crew_id:
          for rec in record.crew_id:
            if rec.name == ln.name and record.ship_name_id != line.ship_name_id:
              data.append(rec.name)
      return data

  @api.constrains('ship_name_id')
  def _check_ship_name_id(self):
    for record in self:
      if not record.ship_name_id.sequence_id:
        raise UserError(_('Add a sequence to the ship to be able to save.'))

      # Verificar si el usuario pertenece al grupo Administrador Operaciones
      is_admin_operations = self.env.user.has_group(
        'ek_l10n_shipping_operations.group_shipping_agent_manager'
      )

      # Si el usuario es Administrador Operaciones, permitir crear el viaje
      if is_admin_operations:
        return

      crew_count = self.search(
        [
          ('company_id', '=', record.company_id.id),
          ('ship_name_id', '=', record.ship_name_id.id),
          ('state', 'in', ['draft', 'arribo', 'zarpe', 'process']),
          ('assigned_regimen_70', '=', False),
        ],
      )

      if len(crew_count) > 1:
        crew = crew_count[0]

        message = f'No se puede crear porque ya existe el Viaje {crew.name}, en estado {crew.state}, cancele o finalice el viaje para continuar con el proceso, o contacte al administrador.'

        raise UserError(_(message))

  def action_confirm_request(self):
    value_error = self.check_crew_id_validate()
    if value_error:
      raise UserError(
        _('members who are still in a process %s' % (value_error))
      )
    for rec in self:
      if rec.crew_id:
        crew_search = self.search(
          [
            ('company_id', '=', rec.company_id.id),
            ('ship_name_id', '=', rec.ship_name_id.id),
            ('state', '=', 'process'),
          ],
          limit=1,
        )
        if crew_search:
          for line in crew_search:
            rec.state = 'process'
            line.state = 'done'
        else:
          rec.state = 'process'
      else:
        raise UserError(_('You cannot confirm without having a crew member'))

  def action_done_request(self):
    self.state = 'done'

  def action_open_documents_expired_boat(self):
    self.ensure_one()
    return {
      'name': _('Documents Expired'),
      'type': 'ir.actions.act_window',
      'res_model': 'ek.ship.document.certificate',
      'view_mode': 'tree',
      'domain': [
        ('ship_name_id', 'in', self.ship_name_id.ids),
        ('document_status', 'in', ['expired', 'to_wi']),
      ],
      'context': {
        'create': False,
        'edit': False,
        'delete': False,
      },
      'target': 'new',
    }

  def action_cancelled_request(self):
    self.ensure_one()
    for record in self:
      purchase = record.env['purchase.order'].search(
        [('journey_crew_id', '=', record.id)]
      )
      sale = record.env['sale.order'].search(
        [
          ('journey_crew_id', '=', record.id),
        ]
      )
      for p in purchase:
        if p.state in ['sent', 'to approve', 'purchase']:
          raise UserError(
            _('You can not cancel a Travel with purchase if it is not draft')
          )
        else:
          p.button_cancel()
      for s in sale:
        if s.state in ['sent', 'sale']:
          raise UserError(
            _('You can not cancel a Travel with sale if it is not draft')
          )
        else:
          s.action_cancel()
      record.state = 'cancelled'

  @api.onchange('ship_name_id')
  def _onchange_ship_name_id(self):
    ship_rec = self.ship_name_id
    if not ship_rec:
      return

    data = {
      'boat_color': ship_rec.boat_color,
      'ship_flag_id': ship_rec.ship_flag_id,
      'boat_registration': ship_rec.boat_registration,
      'company_id': ship_rec.company_id,
      # "length": ship_rec.length,
      # "sleeve": ship_rec.sleeve,
      # "depth": ship_rec.depth,
      # "trb": ship_rec.trb,
      # "trn": ship_rec.trn,
      # "ek_boats_measures_1_id": ship_rec.ek_boats_measures_1_id,
      # "ek_boats_measures_2_id": ship_rec.ek_boats_measures_2_id,
      # "ek_boats_measures_3_id": ship_rec.ek_boats_measures_3_id,
      # "ek_boats_measures_4_id": ship_rec.ek_boats_measures_4_id,
      # "ek_boats_measures_5_id": ship_rec.ek_boats_measures_5_id,
      'state_boats': ship_rec.state_boats,
      'bussiness_name_id': ship_rec.bussiness_name_id,
      'capital_name_id': ship_rec.capital_name_id,
    }
    self.update(data)

    # Verificar si el usuario pertenece al grupo Administrador Operaciones
    is_admin_operations = self.env.user.has_group(
      'ek_l10n_shipping_operations.group_shipping_agent_manager'
    )

    # Verificar si existe un viaje activo para este barco
    company_id = self.company_id.id if self.company_id else self.env.company.id
    domain = [
      ('company_id', '=', company_id),
      ('ship_name_id', '=', ship_rec.id),
      ('state', 'in', ['draft', 'arribo', 'zarpe', 'process']),
      ('assigned_regimen_70', '=', False),
    ]
    # Excluir el registro actual si estamos editando
    if self.id:
      domain.append(('id', '!=', self.id))

    active_journeys = self.search(domain, order='create_date desc')

    if active_journeys:
      journey = active_journeys[0]
      state_labels = {
        'draft': 'Borrador',
        'arribo': 'Arribo',
        'zarpe': 'Zarpe',
        'process': 'En Proceso',
      }
      state_label = state_labels.get(journey.state, journey.state)

      # Mensaje diferente según el grupo del usuario
      if is_admin_operations:
        warning_message = _(
          'ADVERTENCIA: Ya existe un viaje no finalizado para este barco.\n\n'
          'Viaje: %s\n'
          'Estado: %s\n\n'
          'Como Administrador Operaciones, puede proceder con la creación del nuevo viaje o cancelar esta operación.'
        ) % (journey.name, state_label)
      else:
        warning_message = _(
          'ADVERTENCIA: Ya existe un viaje no finalizado para este barco.\n\n'
          'Viaje: %s\n'
          'Estado: %s\n\n'
          'No se podrá guardar este viaje hasta que se cancele o finalice el viaje existente.'
        ) % (journey.name, state_label)

      return {
        'warning': {
          'title': _('Viaje Activo Encontrado'),
          'message': warning_message,
        }
      }

    # Validación original para estado del barco
    if self.ship_name_id.state_boats == 'port' and not self.assigned_regimen_70:
      return {
        'warning': {
          'title': _('Boat Status Check'),
          'message': _(
            'The current status of the ship is in port. Check the status of the ship.'
          ),
        }
      }

  @api.model_create_multi
  def create(self, values_list):
    for value in values_list:
      if value.get('name', '/') == '/':
        ship = self.env['ek.ship.registration'].browse(value['ship_name_id'])
        if ship.sequence_id:
          value['name'] = ship.sequence_id.next_by_id()
          if not ship.assigned_regimen_70:
            value['crew_ids'] = [(6, 0, ship.crew_ids.ids)]
    return super(ek_boats_information, self).create(values_list)

  ek_operation_request_ids = fields.One2many(
    'ek.operation.request',
    'journey_crew_id',
    string='Request',
  )
  request_count = fields.Integer(
    string='request Count', compute='_compute_request_count'
  )

  @api.depends('ek_operation_request_ids')
  def _compute_request_count(self):
    for record in self:
      record.request_count = record.env['ek.operation.request'].search_count(
        [
          ('journey_crew_id', '=', record.id),
        ]
      )

  def action_open_enhanced_requests(self):
    """
    Abre la vista mejorada de solicitudes del viaje actual.
    """
    self.ensure_one()


    # Crear el contexto para la nueva solicitud
    context = {
      'default_journey_crew_id': self.id,
      'default_ek_ship_registration_id': self.ship_name_id.id
      if self.ship_name_id
      else False,
      'search_default_group_by_journey_crew_id': 1,
      'search_default_group_by_ek_ship_registration_id': 1,
    }

    # Si el barco tiene business_name_id, incluirlo en el contexto
    if self.ship_name_id and self.ship_name_id.bussiness_name_id:
      context['default_res_partner_id'] = self.ship_name_id.bussiness_name_id.id


    return {
      'name': _('Solicitudes del Viaje %s') % self.name,
      'type': 'ir.actions.act_window',
      'res_model': 'ek.operation.request',
      'view_mode': 'tree,form',
      'context': context,
      'domain': [('journey_crew_id', '=', self.id)],
      'target': 'current',
    }

  order_ids = fields.One2many(
    'sale.order',
    'journey_crew_id',
    string='Request ',
  )
  sale_order_count = fields.Integer(
    string='sale Order Count', compute='_compute_sale_order_count'
  )

  @api.depends('order_ids')
  def _compute_sale_order_count(self):
    for record in self:
      record.sale_order_count = record.env['sale.order'].search_count(
        [
          ('journey_crew_id', '=', record.id),
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
        'default_journey_crew_id': self.id,
        'default_ek_ship_registration_id': self.ship_name_id.id,
      },
      'domain': [('journey_crew_id', 'in', self.ids)],
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
      'domain': [('journey_crew_id', 'in', self.ids)],
      'target': 'current',
      'context': {
        'create': False,
        'edit': False,
        'delete': False,
        'editable': 'bottom',
      },
    }

  account_move_ids = fields.One2many(
    'account.move',
    'journey_crew_id',
    string='invoice',
  )
  invoice_count = fields.Integer(
    string='Invoice Count', compute='_compute_account_move_count'
  )
  
  # Campos para seguimiento de reembolsos
  reimbursement_tracking_ids = fields.One2many(
    'ek.reimbursement.tracking',
    'journey_crew_id',
    string='Seguimiento de Reembolsos'
  )
  reimbursement_tracking_count = fields.Integer(
    string='Total Reembolsos',
    compute='_compute_reimbursement_counts'
  )
  pending_reimbursements_count = fields.Integer(
    string='Reembolsos Pendientes',
    compute='_compute_reimbursement_counts'
  )
  recovered_reimbursements_count = fields.Integer(
    string='Reembolsos Recuperados',
    compute='_compute_reimbursement_counts'
  )
  total_reimbursement_amount = fields.Monetary(
    string='Total Reembolsos',
    compute='_compute_reimbursement_amounts',
    currency_field='currency_id'
  )
  pending_reimbursement_amount = fields.Monetary(
    string='Reembolsos Pendientes',
    compute='_compute_reimbursement_amounts',
    currency_field='currency_id'
  )
  recovered_reimbursement_amount = fields.Monetary(
    string='Reembolsos Recuperados',
    compute='_compute_reimbursement_amounts',
    currency_field='currency_id'
  )
  currency_id = fields.Many2one(
    'res.currency',
    string='Moneda',
    default=lambda self: self.env.company.currency_id,
    readonly=True
  )

  @api.depends('account_move_ids')
  def _compute_account_move_count(self):
    for record in self:
      record.invoice_count = record.env['account.move'].search_count(
        [
          ('journey_crew_id', '=', record.id),
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
        'default_journey_crew_id': self.id,
        'default_ship_name_id': self.ship_name_id.id,
      },
      'domain': [('journey_crew_id', 'in', self.ids)],
      'target': 'current',
    }

  @api.depends('reimbursement_tracking_ids', 'reimbursement_tracking_ids.state')
  def _compute_reimbursement_counts(self):
    """Calcular contadores de reembolsos por estado"""
    for record in self:
      reimbursements = record.reimbursement_tracking_ids.filtered(lambda r: not r.ignored)
      record.reimbursement_tracking_count = len(record.reimbursement_tracking_ids)
      record.pending_reimbursements_count = len(reimbursements.filtered(
        lambda r: r.state not in ['recovered', 'cancelled']
      ))
      record.recovered_reimbursements_count = len(reimbursements.filtered(
        lambda r: r.state == 'recovered'
      ))

  @api.depends('reimbursement_tracking_ids', 'reimbursement_tracking_ids.amount', 'reimbursement_tracking_ids.state')
  def _compute_reimbursement_amounts(self):
    """Calcular montos de reembolsos por estado"""
    for record in self:
      reimbursements = record.reimbursement_tracking_ids.filtered(lambda r: not r.ignored)
      record.total_reimbursement_amount = sum(record.reimbursement_tracking_ids.mapped('amount'))
      record.pending_reimbursement_amount = sum(reimbursements.filtered(
        lambda r: r.state not in ['recovered', 'cancelled']
      ).mapped('amount'))
      record.recovered_reimbursement_amount = sum(reimbursements.filtered(
        lambda r: r.state == 'recovered'
      ).mapped('amount'))

  def action_view_reimbursement_tracking(self):
    """Acción para ver todos los reembolsos del viaje"""
    self.ensure_one()
    return {
      'name': _('Reembolsos del Viaje: %s') % self.name,
      'type': 'ir.actions.act_window',
      'res_model': 'ek.reimbursement.tracking',
      'view_mode': 'tree,form',
      'domain': [('journey_crew_id', '=', self.id)],
      'context': {
        'default_journey_crew_id': self.id,
        'search_default_group_by_request': 1,
      },
      'target': 'current',
    }

  def action_view_pending_reimbursements(self):
    """Acción para ver reembolsos pendientes del viaje"""
    self.ensure_one()
    return {
      'name': _('Reembolsos Pendientes: %s') % self.name,
      'type': 'ir.actions.act_window',
      'res_model': 'ek.reimbursement.tracking',
      'view_mode': 'tree,form',
      'domain': [
        ('journey_crew_id', '=', self.id),
        ('ignored', '=', False),
        ('state', 'not in', ['recovered', 'cancelled'])
      ],
      'context': {
        'default_journey_crew_id': self.id,
        'search_default_filter_6_15_days': 1,
      },
      'target': 'current',
    }

  def action_view_recovered_reimbursements(self):
    """Acción para ver reembolsos recuperados del viaje"""
    self.ensure_one()
    return {
      'name': _('Reembolsos Recuperados: %s') % self.name,
      'type': 'ir.actions.act_window',
      'res_model': 'ek.reimbursement.tracking',
      'view_mode': 'tree,form',
      'domain': [
        ('journey_crew_id', '=', self.id),
        ('state', '=', 'recovered')
      ],
      'context': {
        'default_journey_crew_id': self.id,
      },
      'target': 'current',
    }

  # def action_open_documents_account_move_views(self):
  #         self.ensure_one()
  #         return {
  #             "name": _("Invoice"),
  #             "type": "ir.actions.act_window",
  #             "res_model": "account.move",
  #             "view_mode": "tree",
  #             "domain": [("journey_crew_id", "in", self.ids)],
  #             "target": "current",
  #             "context": {"create": False,"edit": False, "delete": False},
  #         }

  purchase_count = fields.Integer(
    compute='_compute_purchase_count', string='Purchase Order Count'
  )

  @api.depends('ek_operation_request_ids')
  def _compute_purchase_count(self):
    for record in self:
      record.purchase_count = record.env['purchase.order'].search_count(
        [
          ('journey_crew_id', '=', record.id),
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
        'default_journey_crew_id': self.id,
      },
      'domain': [('journey_crew_id', 'in', self.ids)],
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
      'domain': [('journey_crew_id', 'in', self.ids)],
      'target': 'current',
      'context': {'create': False, 'edit': False, 'delete': False},
    }

  fuel = fields.Float(string='Fuel Arribo', tracking=True)
  fuel_uom = fields.Many2one('uom.uom', string='Fuel UOM Arribo', tracking=True)
  gasoline = fields.Float(string='Gasoline Arribo ', tracking=True)
  gasoline_uom = fields.Many2one(
    'uom.uom', string='Gasoline UOM Arribo', tracking=True
  )
  water = fields.Float(string='Water Arribo', tracking=True)
  water_uom = fields.Many2one(
    'uom.uom', string='Water UOM Arribo', tracking=True
  )

  fuel_zarpe = fields.Float(string='Fuel Zarpe', tracking=True)
  fuel_uom_zarpe = fields.Many2one(
    'uom.uom', string='Fuel UOM Zarpe', tracking=True
  )
  gasoline_zarpe = fields.Float(string='Gasoline Zarpe', tracking=True)
  gasoline_uom_zarpe = fields.Many2one(
    'uom.uom', string='Gasoline UOM Zarpe', tracking=True
  )
  water_zarpe = fields.Float(string='Water Zarpe', tracking=True)
  water_uom_zarpe = fields.Many2one(
    'uom.uom', string='Water UOM Zarpe', tracking=True
  )

  # aduana

  assigned_regimen_70 = fields.Boolean(
    related='ship_name_id.assigned_regimen_70'
  )
