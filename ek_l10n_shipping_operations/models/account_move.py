from odoo import _, api, fields, models
import logging

_logger = logging.getLogger(__name__)

class AccountMove(models.Model):
  _inherit = 'account.move'

  crew_id_domain = fields.Char(
    compute='_compute_crew_id_domain',
    readonly=True,
    store=False,
  )
  ship_name_id = fields.Many2one(
    'ek.ship.registration',
    string='Shipper',
    store=True,
    index=True,
    tracking=True,
  )

  journey_crew_id = fields.Many2one(
    'ek.boats.information',
    string='Journey',
    store=True,
    domain="[('ship_name_id','=',ship_name_id),('state','in',['draft','process','done'])]",
    tracking=True,
  )

  operation_request_id = fields.Many2one(
    'ek.operation.request', string='Operation Request', tracking=True
  )

  # Campo calculado para mostrar productos pendientes de la solicitud
  pending_products_info = fields.Html(
    string='Productos Pendientes',
    compute='_compute_pending_products_info',
    help='Información de productos pendientes de la solicitud de operación'
  )

  @api.onchange('operation_request_id')
  def _onchange_operation_request_id(self):
    """Actualizar seguimiento de reembolsos cuando se asigna solicitud de operación"""
    if self.operation_request_id and self.move_type == 'out_invoice':
      # Actualizar estado a client_invoice_pending cuando se asigna solicitud
      self._update_reimbursement_tracking()

  @api.depends('operation_request_id', 'is_reimbursement_invoice', 'invoice_line_ids', 'journey_crew_id')
  def _compute_pending_products_info(self):
    """Calcula la información de productos pendientes de la solicitud"""
    for move in self:
      if not move.is_reimbursement_invoice or not move.operation_request_id:
        move.pending_products_info = False
        continue
      
      # Actualizar seguimiento cuando cambien las líneas de factura de cliente
      if move.journey_crew_id and move.move_type == 'out_invoice':
        _logger.info(f'INVOICE_DEBUG: _compute_pending_products_info triggering _update_reimbursement_tracking for invoice {move.id}')
        move._update_reimbursement_tracking()

      # Obtener productos pendientes de la solicitud (excluyendo los ignorados)
      tracking_records = self.env['ek.reimbursement.tracking'].search([
        ('request_id', '=', move.operation_request_id.id),
        ('state', 'in', ['draft', 'purchase_pending', 'invoice_pending', 'invoice_received']),
        ('ignored', '=', False)
      ])

      if not tracking_records:
        move.pending_products_info = False
        continue

      # Crear HTML con la información de productos pendientes
      html_content = '<div class="alert alert-info" role="alert">'
      html_content += '<strong>Productos Pendientes de la Solicitud:</strong><br/>'
      
      for record in tracking_records:
        state_label = dict(record._fields['state'].selection)[record.state]
        html_content += f'• {record.product_default_name} - <em>{state_label}</em><br/>'
      
      html_content += '</div>'
      move.pending_products_info = html_content

  @api.depends('partner_id')
  def _compute_crew_id_domain(self):
    for this in self:
      domain = []
      if this.move_type in [
        'out_invoice',
        'out_refund',
      ]:
        domain = [('bussiness_name_id', '=', self.partner_id.id)]
      this.crew_id_domain = domain

  def _post(self, soft=True):
    # Llamar al método original para que realice la contabilización estándar
    result = super(AccountMove, self)._post(soft=soft)

    # Después de la contabilización, asignamos los valores de barco y viaje a todas las líneas
    for move in self:
      if move.ship_name_id or move.journey_crew_id:
        # Obtener la cuenta analítica asociada al barco
        analytic_account = (
          move.ship_name_id.analytic_account_id if move.ship_name_id else False
        )

        # Actualizar TODAS las líneas del apunte contable, incluidas las contrapartidas
        for line in move.line_ids:
          vals = {}
          if move.ship_name_id:
            vals['ship_name_id'] = move.ship_name_id.id
          if move.journey_crew_id:
            vals['journey_crew_id'] = move.journey_crew_id.id
          if analytic_account and not line.analytic_distribution:
            vals['analytic_distribution'] = {analytic_account.id: 100}

          if vals:
            line.write(vals)

  def update_line_travel_ship(self, action_nsk=False, fields_nsk=False):
    for rec in self:
      if not action_nsk:
        fc = str(rec.id)
        id_nsk = fc.split('_')[1]
        if any(char.isalpha() for char in id_nsk):
          continue
      elif action_nsk:
        id_nsk = str(rec.id)

      search = self.env['account.move.line'].search(
        [('move_id.id', '=', id_nsk)]
      )

      if fields_nsk == 'ship_name_id':
        search.update({'ship_name_id': rec.ship_name_id.id})
        if rec.ship_name_id.id:
          search.update(
            {
              'analytic_distribution': {
                rec.ship_name_id.analytic_account_id.id: 100
              }
            }
          )
      if fields_nsk == 'journey_crew_id':
        search.update({'journey_crew_id': rec.journey_crew_id.id})

  @api.onchange('ship_name_id')
  def onchange_ship_name_id(self):
    self.update_line_travel_ship(fields_nsk='ship_name_id')

  @api.onchange('journey_crew_id')
  def onchange_journey_crew_id(self):
    self.update_line_travel_ship(fields_nsk='journey_crew_id')



  def _l10n_ec_get_invoice_additional_info(self):
    # Obtenemos la información adicional del método original
    additional_info = super()._l10n_ec_get_invoice_additional_info()

    # Eliminamos los campos específicos que no queremos
    if 'Referencia' in additional_info:
      additional_info.pop('Referencia')

    if 'E-mail' in additional_info:
      additional_info.pop('E-mail')

    # Añadimos campos específicos navieros si existen y está habilitado
    if getattr(self.company_id, 'show_ship_xml', True):
      if hasattr(self, 'ship_name_id') and self.ship_name_id:
        additional_info.update({'Barco': self.ship_name_id.name or ''})

      if hasattr(self, 'journey_crew_id') and self.journey_crew_id:
        additional_info.update({'Viaje': self.journey_crew_id.name or ''})

    # Añadimos la referencia si existe
    if self.ref:
      additional_info.update({'Referencia': self.ref or ''})

    # Añadimos el correo electrónico del contacto
    if self.partner_id and self.partner_id.email:
      additional_info.update(
        {'Correo del cliente': self.partner_id.email or ''}
      )

    # Añadimos información del vendedor/comercial
    additional_info.update({'Vendedor': self.invoice_user_id.name or ''})

    return additional_info

  def write(self, vals):
    """Override write para actualizar seguimiento de reembolsos"""
    # Capturar tracking IDs que se van a eliminar ANTES de la eliminación
    deleted_tracking_ids = []
    if 'invoice_line_ids' in vals and self.journey_crew_id and self.move_type == 'out_invoice':
      for change in vals['invoice_line_ids']:
        if change[0] == 2:  # Eliminación de línea
          line_id = change[1]
          line = self.env['account.move.line'].browse(line_id)
          if line.exists() and line.reimbursement_tracking_id:
            deleted_tracking_ids.append(line.reimbursement_tracking_id.id)
            _logger.info(f'INVOICE_DEBUG: Tracking {line.reimbursement_tracking_id.id} will be affected by line {line_id} deletion')
    
    res = super().write(vals)
    
    # Actualizar seguimiento si cambia el estado o las líneas de factura
    if 'state' in vals:
      if self.operation_request_id and self.move_type == 'in_invoice':
        _logger.info(f'INVOICE_DEBUG: write method calling _update_reimbursement_tracking for in_invoice {self.id}')
        self._update_reimbursement_tracking()
      elif self.journey_crew_id and self.move_type == 'out_invoice':
        _logger.info(f'INVOICE_DEBUG: write method calling _update_reimbursement_tracking for out_invoice {self.id}')
        self._update_reimbursement_tracking()
    elif 'invoice_line_ids' in vals:
      # Manejar cambios específicos en las líneas de factura
      if self.journey_crew_id and self.move_type == 'out_invoice':
        if deleted_tracking_ids:
          # Actualizar tracking específicos que fueron eliminados
          _logger.info(f'INVOICE_DEBUG: write method calling _update_deleted_tracking for out_invoice {self.id}')
          self._update_deleted_tracking(deleted_tracking_ids)
        else:
          # Actualización normal
          _logger.info(f'INVOICE_DEBUG: write method calling _update_reimbursement_tracking_for_line_changes for out_invoice {self.id}')
          self._update_reimbursement_tracking_for_line_changes(vals.get('invoice_line_ids', []))
      elif self.operation_request_id and self.move_type == 'in_invoice':
        _logger.info(f'INVOICE_DEBUG: write method calling _update_reimbursement_tracking for in_invoice {self.id}')
        self._update_reimbursement_tracking()
    
    # Interceptar cuando se cambia el payment_state
    if 'payment_state' in vals:
      new_payment_state = vals.get('payment_state')
      old_payment_state = self.payment_state
      
      _logger.info(f'PAYMENT_DEBUG: Payment state changed from {old_payment_state} to {new_payment_state} for invoice {self.id}')
      
      if new_payment_state == 'paid':
        # Pago completado
        if self.operation_request_id and self.move_type == 'in_invoice':
          self._update_reimbursement_tracking_for_payment()
        elif self.journey_crew_id and self.move_type == 'out_invoice':
          self._update_reimbursement_tracking_for_payment()
      elif old_payment_state == 'paid' and new_payment_state != 'paid':
        # Pago revertido (conciliación rota)
        _logger.info(f'PAYMENT_DEBUG: Payment was reversed for invoice {self.id}')
        if self.operation_request_id and self.move_type == 'in_invoice':
          self._update_reimbursement_tracking_for_unpayment()
        elif self.journey_crew_id and self.move_type == 'out_invoice':
          self._update_reimbursement_tracking_for_unpayment()
    
    return res

  @api.model_create_multi
  def create(self, vals_list):
    """Override create para actualizar seguimiento cuando se crea factura con solicitud"""
    _logger.info(f'INVOICE_DEBUG: create method called with {len(vals_list)} records')
    moves = super().create(vals_list)
    for move in moves:
      _logger.info(f'INVOICE_DEBUG: Created move {move.id}, operation_request_id: {move.operation_request_id}, journey_crew_id: {move.journey_crew_id}, move_type: {move.move_type}')
      if move.operation_request_id and move.move_type == 'in_invoice':
        _logger.info(f'INVOICE_DEBUG: Calling _update_reimbursement_tracking for in_invoice {move.id}')
        move._update_reimbursement_tracking()
      elif move.journey_crew_id and move.move_type == 'out_invoice':
        _logger.info(f'INVOICE_DEBUG: Calling _update_reimbursement_tracking for out_invoice {move.id}')
        move._update_reimbursement_tracking()
    return moves

  def update_reimbursement_tracking_from_products(self):
    """Método de compatibilidad para el módulo de reembolsos"""
    return self._update_reimbursement_tracking()

  def unlink(self):
    """Override unlink para actualizar seguimiento cuando se elimina factura"""
    # Actualizar seguimiento antes de eliminar
    if self.operation_request_id or self.journey_crew_id:
      self._update_reimbursement_tracking_on_deletion()
    return super().unlink()

  def _update_reimbursement_tracking_on_deletion(self):
    """Actualizar seguimiento cuando se elimina la factura"""
    _logger.info(f'INVOICE_DELETION_DEBUG: Updating tracking for deleted invoice {self.id}, type: {self.move_type}')
    
    # Obtener líneas con seguimiento de reembolso
    lines_with_tracking = self.invoice_line_ids.filtered('reimbursement_tracking_id')
    
    for line in lines_with_tracking:
      tracking = line.reimbursement_tracking_id
      _logger.info(f'INVOICE_DELETION_DEBUG: Updating tracking {tracking.id} - current state: {tracking.state}')
      
      # Determinar el tipo de documento eliminado
      removed_document_type = 'client_invoice' if self.move_type == 'out_invoice' else 'invoice'
      
      # Usar el método de reversión para determinar el estado correcto
      correct_state = tracking._determine_correct_state_with_reversal(
        removed_document_type=removed_document_type,
        removed_document_id=self.id
      )
      
      _logger.info(f'INVOICE_DELETION_DEBUG: Correct state for tracking {tracking.id}: {correct_state}')
      
      if correct_state != tracking.state:
        _logger.info(f'INVOICE_DELETION_DEBUG: Updating tracking {tracking.id} from {tracking.state} to {correct_state}')
        tracking.sudo().write({
          'state': correct_state,
          'invoice_id': False if self.move_type == 'in_invoice' else tracking.invoice_id
        })
      else:
        _logger.info(f'INVOICE_DELETION_DEBUG: Tracking {tracking.id} already in correct state: {correct_state}')

  def _update_deleted_tracking(self, deleted_tracking_ids):
    """Actualizar tracking específicos que fueron eliminados con sus líneas"""
    _logger.info(f'INVOICE_DEBUG: _update_deleted_tracking called for invoice {self.id}')
    _logger.info(f'INVOICE_DEBUG: Deleted tracking IDs: {deleted_tracking_ids}')
    
    for tracking_id in deleted_tracking_ids:
      tracking = self.env['ek.reimbursement.tracking'].browse(tracking_id)
      if tracking.exists():
        _logger.info(f'INVOICE_DEBUG: Updating tracking record {tracking.id} - current state: {tracking.state}')
        
        # Determinar el tipo de documento para la reversión
        removed_document_type = 'client_invoice' if self.move_type == 'out_invoice' else 'invoice'
        
        # Usar el método de reversión para determinar el estado correcto
        correct_state = tracking._determine_correct_state_with_reversal(
          removed_document_type=removed_document_type,
          removed_document_id=self.id
        )
        
        _logger.info(f'INVOICE_DEBUG: Correct state for tracking {tracking.id}: {correct_state}')
        
        if correct_state != tracking.state:
          _logger.info(f'INVOICE_DEBUG: Updating tracking {tracking.id} from {tracking.state} to {correct_state}')
          tracking.sudo().write({'state': correct_state})
        else:
          _logger.info(f'INVOICE_DEBUG: Tracking {tracking.id} already in correct state: {correct_state}')

  def _update_reimbursement_tracking_for_line_changes(self, line_changes):
    """Actualizar seguimiento específicamente para cambios en líneas de factura"""
    _logger.info(f'INVOICE_DEBUG: _update_reimbursement_tracking_for_line_changes called for invoice {self.id}')
    _logger.info(f'INVOICE_DEBUG: Line changes: {line_changes}')
    
    # Identificar líneas que se están eliminando y tienen seguimiento
    deleted_tracking_ids = []
    for change in line_changes:
      if change[0] == 2:  # Eliminar línea
        line_id = change[1]
        deleted_line = self.env['account.move.line'].browse(line_id)
        if deleted_line.exists() and deleted_line.reimbursement_tracking_id:
          deleted_tracking_ids.append(deleted_line.reimbursement_tracking_id.id)
          _logger.info(f'INVOICE_DEBUG: Tracking {deleted_line.reimbursement_tracking_id.id} will be affected by line deletion')
    
    _logger.info(f'INVOICE_DEBUG: Deleted tracking IDs: {deleted_tracking_ids}')
    
    # Si no hay seguimientos afectados, actualizar normalmente
    if not deleted_tracking_ids:
      _logger.info('INVOICE_DEBUG: No tracking records affected, updating normally')
      return self._update_reimbursement_tracking()
    
    # Actualizar solo los seguimientos afectados usando reversión
    for tracking_id in deleted_tracking_ids:
      tracking = self.env['ek.reimbursement.tracking'].browse(tracking_id)
      if tracking.exists():
        _logger.info(f'INVOICE_DEBUG: Updating tracking record {tracking.id} - current state: {tracking.state}')
        
        # Determinar el tipo de documento para la reversión
        removed_document_type = 'client_invoice' if self.move_type == 'out_invoice' else 'invoice'
        
        # Usar el método de reversión para determinar el estado correcto
        correct_state = tracking._determine_correct_state_with_reversal(
          removed_document_type=removed_document_type,
          removed_document_id=self.id
        )
        
        _logger.info(f'INVOICE_DEBUG: Correct state for tracking {tracking.id}: {correct_state}')
        
        if correct_state != tracking.state:
          _logger.info(f'INVOICE_DEBUG: Updating tracking {tracking.id} from {tracking.state} to {correct_state}')
          tracking.sudo().write({'state': correct_state})
        else:
          _logger.info(f'INVOICE_DEBUG: Tracking {tracking.id} already in correct state: {correct_state}')

  def _update_all_journey_products_state(self):
    """Actualizar el estado de todos los productos del viaje basado en sus documentos existentes"""
    _logger.info(f'INVOICE_DEBUG: _update_all_journey_products_state called for journey {self.journey_crew_id.id}')
    
    # Buscar todos los productos de seguimiento del viaje
    tracking_records = self.env['ek.reimbursement.tracking'].search([
      ('journey_crew_id', '=', self.journey_crew_id.id),
      ('ignored', '=', False)
    ])
    
    _logger.info(f'INVOICE_DEBUG: Found {len(tracking_records)} tracking records for journey')
    
    for tracking in tracking_records:
      _logger.info(f'INVOICE_DEBUG: Updating tracking record {tracking.id} - current state: {tracking.state}')
      
      # Usar el método _determine_correct_state del modelo de tracking
      correct_state = tracking._determine_correct_state()
      _logger.info(f'INVOICE_DEBUG: Correct state for tracking {tracking.id}: {correct_state}')
      
      if correct_state != tracking.state:
        _logger.info(f'INVOICE_DEBUG: Updating tracking {tracking.id} from {tracking.state} to {correct_state}')
        tracking.sudo().write({'state': correct_state})
      else:
        _logger.info(f'INVOICE_DEBUG: Tracking {tracking.id} already in correct state: {correct_state}')

  def force_reimbursement_payment_update(self):
    """Método para forzar actualización de estado cuando el pago está completo"""
    if (self.move_type == 'out_invoice' and 
        self.operation_request_id and 
        self.amount_residual == 0):
      self._update_reimbursement_tracking_for_payment()
      return True
    return False

  def _update_reimbursement_tracking(self):
    """Actualizar estado de seguimiento de reembolsos según estado de factura"""
    _logger.info(f'INVOICE_DEBUG: _update_reimbursement_tracking called for invoice {self.id}, type: {self.move_type}, state: {self.state}')
    
    # Obtener líneas con seguimiento de reembolso
    lines_with_tracking = self.invoice_line_ids.filtered('reimbursement_tracking_id')
    _logger.info(f'INVOICE_DEBUG: Found {len(lines_with_tracking)} lines with reimbursement tracking')
    
    if not lines_with_tracking:
      _logger.info('INVOICE_DEBUG: No lines with reimbursement tracking, skipping')
      return
    
    for line in lines_with_tracking:
      tracking = line.reimbursement_tracking_id
      _logger.info(f'INVOICE_DEBUG: Processing tracking record {tracking.id} - current state: {tracking.state}')
      
      if self.state == 'posted' and self.move_type == 'in_invoice':
        # Factura de proveedor confirmada
        _logger.info(f'INVOICE_DEBUG: Updating tracking {tracking.id} to invoice_received')
        tracking.sudo().write({
          'state': 'invoice_received',
          'invoice_id': self.id
        })
      elif self.state == 'posted' and self.move_type == 'out_invoice':
        # Factura al cliente confirmada
        _logger.info(f'INVOICE_DEBUG: Updating tracking {tracking.id} to client_invoice_sent')
        tracking.sudo().write({
          'state': 'client_invoice_sent'
        })
      elif self.state == 'draft' and self.move_type == 'in_invoice':
        _logger.info(f'INVOICE_DEBUG: Updating tracking {tracking.id} to invoice_pending')
        tracking.sudo().write({
          'state': 'invoice_pending',
          'invoice_id': self.id
        })
      elif self.state == 'draft' and self.move_type == 'out_invoice':
        _logger.info(f'INVOICE_DEBUG: Updating tracking {tracking.id} to client_invoice_pending')
        tracking.sudo().write({
          'state': 'client_invoice_pending'
        })
      elif self.state == 'cancel':
        # Cuando se cancela una factura, regresar al estado anterior
        if self.move_type == 'in_invoice':
          tracking.sudo().write({
            'state': 'purchase_confirmed',
            'invoice_id': False
          })
        elif self.move_type == 'out_invoice':
          tracking.sudo().write({
            'state': 'invoice_received',
          })

  def action_register_payment(self):
    """Override para detectar cuando se registra pago vía wizard"""
    res = super().action_register_payment()
    
    # Verificar si después del registro el pago está completo
    if (self.move_type == 'out_invoice' and 
        self.operation_request_id and 
        self.amount_residual == 0):
      self._update_reimbursement_tracking_for_payment()
    
    return res

  def action_invoice_paid(self):
    """Override para marcar reembolsos como recuperados cuando se pague factura cliente"""
    res = super().action_invoice_paid()
    
    # Solo para facturas al cliente
    if self.move_type == 'out_invoice' and self.operation_request_id:
      # Obtener los productos específicos de esta factura
      invoice_product_ids = self.invoice_line_ids.mapped('product_id.id')
      invoice_product_names = self.invoice_line_ids.mapped('product_id.display_name')
      
      # Buscar registros de seguimiento usando product_id (método más confiable)
      if invoice_product_ids:
        tracking_records = self.env['ek.reimbursement.tracking'].search([
          ('request_id', '=', self.operation_request_id.id),
          ('product_id', 'in', invoice_product_ids),
          ('ignored', '=', False)
        ])
      else:
        # Fallback con nombres si no hay product_ids
        tracking_records = self.env['ek.reimbursement.tracking'].search([
          ('request_id', '=', self.operation_request_id.id),
          ('ignored', '=', False)
        ])
        
        # Filtrar por coincidencia de nombres normalizados
        normalized_product_names = [self.env['ek.reimbursement.tracking']._normalize_product_name(name) for name in invoice_product_names]
        tracking_records = tracking_records.filtered(
          lambda t: self.env['ek.reimbursement.tracking']._normalize_product_name(t.product_default_name) in normalized_product_names
        )
      
      filtered_records = tracking_records
      
      for tracking in filtered_records:
        tracking.sudo().write({'state': 'recovered'})

  def _update_reimbursement_tracking_for_payment(self):
    """Actualizar seguimiento cuando se paga factura de cliente"""
    _logger.info(f'PAYMENT_DEBUG: _update_reimbursement_tracking_for_payment called for invoice {self.id}, type: {self.move_type}')
    
    # Solo para facturas al cliente
    if self.move_type == 'out_invoice' and (self.operation_request_id or self.journey_crew_id):
      # Obtener líneas con seguimiento de reembolso
      lines_with_tracking = self.invoice_line_ids.filtered('reimbursement_tracking_id')
      _logger.info(f'PAYMENT_DEBUG: Found {len(lines_with_tracking)} lines with reimbursement tracking')
      
      if not lines_with_tracking:
        _logger.info('PAYMENT_DEBUG: No lines with reimbursement tracking, skipping')
        return
      
      # Actualizar estado a 'recovered' para cada seguimiento
      for line in lines_with_tracking:
        tracking = line.reimbursement_tracking_id
        _logger.info(f'PAYMENT_DEBUG: Updating tracking {tracking.id} to recovered (payment received)')
        tracking.sudo().write({'state': 'recovered'})
    

  def _update_reimbursement_tracking_for_unpayment(self):
    """Actualizar seguimiento cuando se rompe la conciliación de factura de cliente"""
    _logger.info(f'UNPAYMENT_DEBUG: _update_reimbursement_tracking_for_unpayment called for invoice {self.id}, type: {self.move_type}')
    
    # Solo para facturas al cliente
    if self.move_type == 'out_invoice' and (self.operation_request_id or self.journey_crew_id):
      # Obtener líneas con seguimiento de reembolso
      lines_with_tracking = self.invoice_line_ids.filtered('reimbursement_tracking_id')
      _logger.info(f'UNPAYMENT_DEBUG: Found {len(lines_with_tracking)} lines with reimbursement tracking')
      
      if not lines_with_tracking:
        _logger.info('UNPAYMENT_DEBUG: No lines with reimbursement tracking, skipping')
        return
      
      # Usar método de reversión para determinar el estado correcto
      for line in lines_with_tracking:
        tracking = line.reimbursement_tracking_id
        _logger.info(f'UNPAYMENT_DEBUG: Updating tracking {tracking.id} - current state: {tracking.state}')
        
        # Usar el método de reversión para determinar el estado correcto
        correct_state = tracking._determine_correct_state_with_reversal(
          removed_document_type='client_invoice',
          removed_document_id=self.id
        )
        
        _logger.info(f'UNPAYMENT_DEBUG: Correct state for tracking {tracking.id}: {correct_state}')
        
        if correct_state != tracking.state:
          _logger.info(f'UNPAYMENT_DEBUG: Updating tracking {tracking.id} from {tracking.state} to {correct_state}')
          tracking.sudo().write({'state': correct_state})
        else:
          _logger.info(f'UNPAYMENT_DEBUG: Tracking {tracking.id} already in correct state: {correct_state}')

  @api.depends('amount_residual', 'move_type', 'state', 'company_id')
  def _compute_payment_state(self):
    """Override para interceptar cuando se actualiza payment_state a 'paid' o se rompe conciliación"""
    
    # Guardar el estado anterior para detectar cambios
    previous_payment_states = {invoice.id: invoice.payment_state for invoice in self}
    
    # Llamar al método original
    super()._compute_payment_state()
    
    # Interceptar cambios en payment_state
    for invoice in self:
      if (invoice.move_type == 'out_invoice' and 
          invoice.operation_request_id):
        
        previous_state = previous_payment_states.get(invoice.id)
        current_state = invoice.payment_state
        
        # Caso 1: Se marca como 'paid' (pago completo)
        if current_state == 'paid' and previous_state != 'paid':
          invoice._update_reimbursement_tracking_for_payment()
        
        # Caso 2: Pago completo detectado por amount_residual = 0 (alternativo a 'paid')
        elif (current_state == 'in_payment' and 
              invoice.amount_residual == 0 and 
              previous_state not in ['paid', 'in_payment']):
          invoice._update_reimbursement_tracking_for_payment()
        
        # Caso 3: Se marca como 'partial' (pago parcial)
        elif current_state == 'partial' and previous_state not in ['paid', 'partial']:
          invoice._update_reimbursement_tracking_for_payment()
        
        # Caso 4: Se rompe la conciliación (de 'paid' o 'partial' a otro estado)
        elif previous_state in ['paid', 'partial'] and current_state not in ['paid', 'partial']:
          invoice._update_reimbursement_tracking_for_unpayment()

  def update_reimbursement_tracking_from_products(self):
    """
    Método público para actualizar el seguimiento de reembolsos cuando se agregan productos.
    Puede ser llamado desde otros módulos (como el de reembolsos).
    """
    if self.operation_request_id and self.move_type == 'out_invoice':
      self._update_reimbursement_tracking()


class AccountPayment(models.Model):
  _inherit = 'account.payment'

  ship_name_id = fields.Many2one(
    'ek.ship.registration', string='Shipper', tracking=True
  )

  journey_crew_id = fields.Many2one(
    'ek.boats.information',
    string='Journey',
    tracking=True,
    domain="[('ship_name_id','=',ship_name_id),('state','in',['draft','process','done'])]",
  )

  def onchange_action_journey_crew_id(self, fields_nsk):
    fc = str(self.move_id.id)
    id_nsk_move = fc.split('_')[1]
    if any(char.isalpha() for char in id_nsk_move):
      return
    move_id = self.env['account.move'].search([('id', '=', id_nsk_move)])
    if fields_nsk == 'ship_name_id':
      move_id.ship_name_id = self.ship_name_id.id
    if fields_nsk == 'journey_crew_id':
      move_id.journey_crew_id = self.journey_crew_id.id
    move_id.update_line_travel_ship(True, fields_nsk)

  @api.onchange('ship_name_id')
  def onchange_ship_name_id(self):
    self.onchange_action_journey_crew_id('ship_name_id')

  @api.onchange('journey_crew_id')
  def onchange_journey_crew_id(self):
    self.onchange_action_journey_crew_id('journey_crew_id')


class AccountPaymentRegister(models.TransientModel):
  _inherit = 'account.payment.register'

  journey_crew_id = fields.Many2one(
    'ek.boats.information',
    domain="[('ship_name_id','=',ship_name_id),('state','in',['draft','process','done'])]",
    tracking=True,
    string='Journey',
  )
  ship_name_id = fields.Many2one(
    'ek.ship.registration', tracking=True, string='Shipper'
  )

  @api.model
  def _get_line_batch_key(self, line):
    # OVERRIDE
    res = super(AccountPaymentRegister, self)._get_line_batch_key(line)
    self.journey_crew_id = line.move_id.journey_crew_id.id
    self.ship_name_id = line.move_id.ship_name_id.id

    return res

  def _create_payment_vals_from_wizard(self, batch_result):
    # OVERRIDE
    payment_vals = super(
      AccountPaymentRegister, self
    )._create_payment_vals_from_wizard(batch_result)
    payment_vals.update(
      {
        'journey_crew_id': self.journey_crew_id.id,
        'ship_name_id': self.ship_name_id.id,
      }
    )
    return payment_vals

  def _create_payment_vals_from_batch(self, batch_result):
    payment_vals = super(
      AccountPaymentRegister, self
    )._create_payment_vals_from_batch(batch_result)
    if 'journey_crew_id' in batch_result:
      payment_vals['journey_crew_id'] = batch_result['journey_crew_id']
      payment_vals['ship_name_id'] = batch_result['ship_name_id']
    else:
      payment_vals.update(
        {
          'journey_crew_id': self.journey_crew_id.id,
          'ship_name_id': self.ship_name_id.id,
        }
      )

    return payment_vals


class AccountMoveLine(models.Model):
  _inherit = 'account.move.line'

  journey_crew_id = fields.Many2one(
    'ek.boats.information',
    tracking=True,
    domain="[('ship_name_id','=',ship_name_id),('state','in',['draft','process','done'])]",
  )
  ship_name_id = fields.Many2one(
    'ek.ship.registration',
    tracking=True,
  )
  
  # Campo para seguimiento de reembolsos
  reimbursement_tracking_id = fields.Many2one(
    'ek.reimbursement.tracking', 
    string='Seguimiento de Reembolso'
  )

  @api.onchange('product_id')
  def _onchange_product_id_ship(self):
    account = self.move_id
    analytic = account.ship_name_id.analytic_account_id
    if analytic:
      for rec in self:
        rec.update(
          {
            'journey_crew_id': account.journey_crew_id.id,
            'ship_name_id': account.ship_name_id.id,
            'analytic_distribution': {analytic.id: 100},
          }
        )

  @api.onchange('account_id')
  def _onchange_line_ids_ship(self):
    account = self.move_id
    analytic = account.ship_name_id.analytic_account_id
    if analytic:
      for rec in self:
        rec.update(
          {
            'journey_crew_id': account.journey_crew_id.id,
            'ship_name_id': account.ship_name_id.id,
            'analytic_distribution': {analytic.id: 100},
          }
        )

  def update_line_travel_ship(self):
    return {
      'name': _('Actualizar'),
      'type': 'ir.actions.act_window',
      'res_model': 'wizard.update.lines.nsk',
      'view_mode': 'form',
      'views': [
        (
          self.env.ref(
            'ek_l10n_shipping_operations.wizard_update_lines_nsk_wizard_form'
          ).id,
          'form',
        ),
        (False, 'tree'),
      ],
      'context': {
        'default_ship_name_id': self.ship_name_id.id,
        'default_journey_crew_id': self.journey_crew_id.id,
      },
      'target': 'new',
    }


class L10nEcWizardAccountWithhold(models.TransientModel):
  _inherit = 'l10n_ec.wizard.account.withhold'

  journey_crew_id = fields.Many2one(
    'ek.boats.information', related='related_invoice_ids.journey_crew_id'
  )
  ship_name_id = fields.Many2one(
    'ek.ship.registration', related='related_invoice_ids.ship_name_id'
  )

  def _prepare_withhold_header(self):
    res = super(L10nEcWizardAccountWithhold, self)._prepare_withhold_header()

    additional_data = {
      'journey_crew_id': self.journey_crew_id.id,
      'ship_name_id': self.ship_name_id.id,
    }

    res.update(additional_data)

    return res
