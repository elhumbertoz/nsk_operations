# -*- coding: utf-8 -*-
import logging
from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError
from odoo.tools.misc import formatLang


class AccountMove(models.Model):
  _inherit = 'account.move'

  l10n_ec_to_be_reimbursed = fields.Boolean(
    'Document Reimbursed',
    copy=False,
    compute='_compute_l10n_ec_to_be_reimbursed',
    store=True,
    help='Indica si la factura califica como documento de reembolso'
  )
  reimbursed_move_id = fields.Many2one(
    'account.move',
    string='Reembolso',
    copy=False,
  )

  # Campo calculado para el total de documentos a reembolsar
  reimbursement_total = fields.Monetary(
    string='Total Documentos a Reembolsar',
    compute='_compute_reimbursement_total',
    store=True,
    help='Total de los documentos a reembolsar',
  )

  # Computed fields for credit note information
  credit_notes_applied_amount = fields.Monetary(
    string='Notas de Crédito Aplicadas',
    compute='_compute_credit_notes_info',
    currency_field='currency_id',
    help='Monto total aplicado por notas de crédito',
  )

  credit_notes_applied_percentage = fields.Char(
    string='% Notas de Crédito',
    compute='_compute_credit_notes_info',
    help='Porcentaje del total de la factura aplicado por notas de crédito',
  )

  credit_notes_list = fields.Char(
    string='Notas de Crédito',
    compute='_compute_credit_notes_info',
    help='Lista de notas de crédito aplicadas a esta factura',
  )

  credit_notes_count = fields.Integer(
    string='# Notas de Crédito',
    compute='_compute_credit_notes_info',
    help='Cantidad de notas de crédito aplicadas',
  )

  # Campo relacionado usando reversal_move_id que ya existe
  credit_notes_ids = fields.One2many(
    related='reversal_move_id',
    string='Notas de Crédito',
    help='Notas de crédito aplicadas a esta factura',
  )

  # Campo computado que incluye TODAS las notas de crédito (reversal + conciliación)
  all_credit_notes_ids = fields.Many2many(
    'account.move',
    string='Todas las Notas de Crédito',
    compute='_compute_all_credit_notes_ids',
    help='Todas las notas de crédito aplicadas (reversal + conciliación)',
  )

  # Campo computado para retenciones asumidas
  assumed_retentions = fields.Monetary(
    string='Retenciones Asumidas',
    compute='_compute_assumed_retentions',
    currency_field='currency_id',
    help='Retenciones asumidas en cuentas 52022* que se descuentan del total',
  )

  # Campo computado para total con retenciones descontadas
  reimbursement_total_net = fields.Monetary(
    string='Total Neto (c/retenciones)',
    compute='_compute_reimbursement_total_net',
    currency_field='currency_id',
    help='Total considerando retenciones asumidas',
  )

  @api.depends(
    'reimbursement_ids.total_amount',
  )
  def _compute_reimbursement_total(self):
    """Calcula el total de los documentos a reembolsar usando el campo total_amount"""
    for move in self:
      # Usar el campo total_amount calculado para evitar problemas de redondeo
      move.reimbursement_total = sum(
        move.reimbursement_ids.mapped('total_amount')
      )

  @api.depends('line_ids', 'line_ids.balance', 'line_ids.account_id')
  def _compute_assumed_retentions(self):
    """Calcula las retenciones asumidas en cuentas 52022*"""
    for move in self:
      if move.move_type == 'in_invoice':
        prefix = move.company_id.l10n_ec_assumed_retention_account_prefix or '52022'
        retention_lines = move.line_ids.filtered(
          lambda l: l.account_id.code and l.account_id.code.startswith(prefix)
        )
        move.assumed_retentions = sum(retention_lines.mapped('balance'))
      else:
        move.assumed_retentions = 0.0

  @api.depends('amount_total', 'assumed_retentions')
  def _compute_reimbursement_total_net(self):
    """Calcula el total neto considerando retenciones asumidas"""
    for move in self:
      if move.move_type == 'in_invoice':
        move.reimbursement_total_net = (
          abs(move.amount_total) - move.assumed_retentions
        )
      else:
        move.reimbursement_total_net = abs(move.amount_total)

  @api.depends(
    'reversal_move_id',
    'line_ids.matched_debit_ids',
    'line_ids.matched_credit_ids',
  )
  def _compute_all_credit_notes_ids(self):
    """Compute all credit notes (reversal + reconciliation)"""
    for move in self:
      if move.move_type not in ('out_invoice', 'in_invoice'):
        move.all_credit_notes_ids = [(5, 0, 0)]  # Clear all
        continue

      # Obtener todas las notas de crédito usando el método existente
      credit_notes_data = move._get_related_credit_notes()

      if credit_notes_data:
        # Extraer los IDs de las notas de crédito
        credit_note_ids = list(credit_notes_data.keys())
        move.all_credit_notes_ids = [(6, 0, credit_note_ids)]
      else:
        move.all_credit_notes_ids = [(5, 0, 0)]  # Clear all

  @api.depends(
    'reversal_move_id',
    'reversal_move_id.state',
    'line_ids.matched_debit_ids',
    'line_ids.matched_credit_ids',
    'amount_total',
  )
  def _compute_credit_notes_info(self):
    """Compute credit notes information for invoices"""
    for move in self:
      if move.move_type not in ('out_invoice', 'in_invoice'):
        move.credit_notes_applied_amount = 0.0
        move.credit_notes_applied_percentage = '0.0%'
        move.credit_notes_list = ''
        move.credit_notes_count = 0
        continue

      # Obtener todas las notas de crédito relacionadas con manejo de errores
      try:
        credit_notes_data = move._get_related_credit_notes()
      except Exception:
        # Si hay error al obtener las notas de crédito, usar valores por defecto
        credit_notes_data = {}

      if credit_notes_data:
        # Calcular monto total aplicado (ya viene calculado de _get_related_credit_notes)
        total_applied = sum(
          data['applied_amount'] for data in credit_notes_data.values()
        )
        move.credit_notes_applied_amount = total_applied

        # Calcular porcentaje aplicado y formatearlo para badge
        if move.amount_total != 0:
          percentage = (total_applied / abs(move.amount_total)) * 100
          move.credit_notes_applied_percentage = f'{percentage:.1f}%'
        else:
          move.credit_notes_applied_percentage = '0.0%'

        # Crear lista de notas de crédito para mostrar como texto
        credit_notes_names = [
          data['name'] for data in credit_notes_data.values()
        ]
        move.credit_notes_list = (
          ', '.join(credit_notes_names) if credit_notes_names else ''
        )
        move.credit_notes_count = len(credit_notes_data)
      else:
        move.credit_notes_applied_amount = 0.0
        move.credit_notes_applied_percentage = '0.0%'
        move.credit_notes_list = ''
        move.credit_notes_count = 0

  def _get_related_credit_notes(self):
    """
    Obtiene todas las notas de crédito relacionadas con esta factura,
    tanto por reversal_move_id como por conciliación, y calcula el monto aplicado real
    basándose únicamente en las conciliaciones reales.

    Returns:
        dict: {credit_note_id: {'name': str, 'applied_amount': float}}
    """
    self.ensure_one()
    credit_notes_data = {}

    # Manejo de errores para evitar problemas con transacciones abortadas
    try:
      # Obtener el tipo de nota de crédito esperado
      refund_type = (
        'out_refund' if self.move_type == 'out_invoice' else 'in_refund'
      )

      # Obtener todas las líneas de cuentas por pagar/cobrar de esta factura
      invoice_account_lines = self.line_ids.filtered(
        lambda l: l.account_id.account_type
        in ('payable', 'receivable', 'liability_payable', 'asset_receivable')
      )
    except Exception:
      # Si hay error al obtener las líneas, retornar diccionario vacío
      return credit_notes_data

    # Análisis unificado: buscar TODAS las notas de crédito por conciliación
    # Esto incluye tanto las de reversal_move_id como las aplicadas manualmente
    for line in invoice_account_lines:
      # Buscar en la tabla de conciliaciones directamente con manejo de errores
      try:
        reconcile_lines = self.env['account.partial.reconcile'].search(
          [
            '|',
            ('debit_move_id', '=', line.id),
            ('credit_move_id', '=', line.id),
          ]
        )
      except Exception:
        # Si hay error en la búsqueda (ej: transacción abortada), continuar con la siguiente línea
        continue

      for reconcile in reconcile_lines:
        # Obtener la línea contraria
        if reconcile.debit_move_id.id == line.id:
          # Esta línea es el débito, la otra es el crédito
          other_line = reconcile.credit_move_id
        else:
          # Esta línea es el crédito, la otra es el débito
          other_line = reconcile.debit_move_id

        potential_credit_note = other_line.move_id
        matched_amount = reconcile.amount

        # Verificar si es una nota de crédito válida
        if (
          potential_credit_note.state == 'posted'
          and potential_credit_note.id != self.id
          and matched_amount > 0
        ):
          # Verificación más estricta para detectar notas de crédito
          is_credit_note = False

          # 1. Tipo de movimiento correcto (más estricto)
          if potential_credit_note.move_type == refund_type:
            is_credit_note = True

          # 2. Nombre que indica nota de crédito (más específico)
          elif (
            potential_credit_note.name
            and (
              'notcr' in potential_credit_note.name.lower()
              or potential_credit_note.name.lower().startswith('nc ')
              or potential_credit_note.name.lower().startswith('nota')
              or (
                'credit' in potential_credit_note.name.lower()
                and 'nota' in potential_credit_note.name.lower()
              )
            )
            and potential_credit_note.partner_id == self.partner_id
          ):
            is_credit_note = True

          # 3. Excluir explícitamente retenciones y otros documentos
          if potential_credit_note.name and (
            'ret ' in potential_credit_note.name.lower()
            or 'retencion' in potential_credit_note.name.lower()
            or 'retention' in potential_credit_note.name.lower()
            or potential_credit_note.name.lower().startswith('ret')
          ):
            is_credit_note = False

          if is_credit_note:
            # Si ya existe la nota de crédito, sumar el monto aplicado
            if potential_credit_note.id in credit_notes_data:
              credit_notes_data[potential_credit_note.id]['applied_amount'] += (
                matched_amount
              )
            else:
              # Nueva nota de crédito encontrada
              credit_notes_data[potential_credit_note.id] = {
                'name': potential_credit_note.name
                or f'NC-{potential_credit_note.id}',
                'applied_amount': matched_amount,
              }

    # Resultado final
    for nc_id, nc_data in credit_notes_data.items():
      pass

    return credit_notes_data

  def ckeck_button_cancel(self):
    for rec in self:
      if (
        rec.reimbursed_move_id
        and rec.reimbursed_move_id.state != 'cancel'
        and rec.state == 'posted'
      ):
        raise UserError(
          _(
            'No es posible cancelar una factura asociada a una factura de reembolso activa.\n'
            'Antes anule esta factura de reembolso %s'
            % rec.reimbursed_move_id.name
          )
        )

  def button_cancel(self):
    self.ckeck_button_cancel()
    res = super(AccountMove, self).button_cancel()
    for reimbursement in self.mapped('reimbursement_ids').filtered(
      lambda a: a.link_move_id
    ):
      if reimbursement.link_move_id:
        reimbursement.link_move_id.clear_reimbursement()
      reimbursement.sudo().unlink()
    self.clear_reimbursement()
    return res

  def button_draft(self):
    self.ckeck_button_cancel()
    res = super(AccountMove, self).button_draft()
    for reimbursement in self.mapped('reimbursement_ids').filtered(
      lambda a: a.link_move_id
    ):
      if reimbursement.link_move_id:
        reimbursement.link_move_id.clear_reimbursement()
      reimbursement.sudo().unlink()
    self.clear_reimbursement()
    return res

  def action_post(self):
    """Sobrescribe el método action_post para agregar validación de reembolsos"""
    # Validación para facturas de reembolso
    for move in self:
      if move.is_reimbursement_invoice:
        # Validar que existan documentos a reembolsar
        if not move.reimbursement_ids:
          raise UserError(
            _(
              'No se puede confirmar la factura de reembolso. '
              'Debe agregar al menos un documento a reembolsar antes de confirmar.'
            )
          )

        # Calcula el total de las líneas de la factura
        invoice_total = abs(move.amount_total)
        # Calcula el total de los documentos a reembolsar
        reimbursement_total = move.reimbursement_total

        # Compara los totales con una tolerancia de 0.01 para evitar problemas de redondeo
        if abs(invoice_total - reimbursement_total) > 0.01:
          raise UserError(
            _(
              'No se puede confirmar la factura. El total de las líneas (%(invoice_total)s) '
              'no coincide con el total de los documentos a reembolsar (%(reimbursement_total)s). '
              'Por favor, verifique que los montos sean correctos.'
            )
            % {
              'invoice_total': formatLang(
                self.env, invoice_total, currency_obj=move.currency_id
              ),
              'reimbursement_total': formatLang(
                self.env, reimbursement_total, currency_obj=move.currency_id
              ),
            }
          )
    res = super(AccountMove, self).action_post()
    self.check_l10n_ec_to_be_reimbursed()
    return res

  def clear_reimbursement(self):
    for rec in self:
      rec.write(
        {
          'reimbursed_move_id': False,
          #  'l10n_ec_to_be_reimbursed': False
        }
      )

  @api.depends(
    'move_type',
    'l10n_latam_document_sustento',
    'journal_id',
    'company_id.l10n_ec_ats_sustento_ids',
    'company_id.l10n_ec_reimbursement_journal_ids',
  )
  def _compute_l10n_ec_to_be_reimbursed(self):
    """
    Calcula si la factura califica como documento de reembolso.
    Se actualiza automáticamente cuando cambian los campos relevantes,
    incluso si la factura está en estado 'posted'.
    """
    for rec in self:
      # Inicializar como False
      rec.l10n_ec_to_be_reimbursed = False
      
      # Condición 1: Debe ser factura de proveedor
      if rec.move_type != 'in_invoice':
        continue
      
      # Condición 2: Si hay configuración de ATS Sustento, debe cumplirla
      if rec.company_id.l10n_ec_ats_sustento_ids:
        if not rec.l10n_latam_document_sustento:
          continue
        if (
          rec.l10n_latam_document_sustento
          not in rec.company_id.l10n_ec_ats_sustento_ids
        ):
          continue
      
      # Condición 3: Si hay configuración de Diarios de Reembolso, debe cumplirla
      if rec.company_id.l10n_ec_reimbursement_journal_ids:
        if not rec.journal_id:
          continue
        if (
          rec.journal_id not in rec.company_id.l10n_ec_reimbursement_journal_ids
        ):
          continue
      
      # Si pasa todas las condiciones, es de reembolso
      rec.l10n_ec_to_be_reimbursed = True

  def check_l10n_ec_to_be_reimbursed(self):
    """
    Método legacy mantenido para compatibilidad.
    Ahora el campo se calcula automáticamente con _compute_l10n_ec_to_be_reimbursed.
    Este método fuerza el recálculo del campo computado.
    """
    self._compute_l10n_ec_to_be_reimbursed()

  def action_update_reimbursement_status(self):
    """
    Acción del servidor para actualizar el estado de reembolso de facturas.
    Actualiza el campo l10n_ec_to_be_reimbursed y muestra mensajes explicativos
    si la factura no califica como de reembolso.
    
    Retorna un diccionario con información sobre el resultado de la operación.
    """
    results = {
      'updated': [],
      'not_qualified': [],
      'errors': []
    }
    
    for move in self:
      try:
        # Guardar el valor anterior
        old_value = move.l10n_ec_to_be_reimbursed
        
        # Forzar el recálculo del campo
        move._compute_l10n_ec_to_be_reimbursed()
        
        # Obtener el nuevo valor
        new_value = move.l10n_ec_to_be_reimbursed
        
        # Si cambió el valor, registrar
        if old_value != new_value:
          results['updated'].append({
            'id': move.id,
            'name': move.name or f'ID {move.id}',
            'old_value': old_value,
            'new_value': new_value
          })
        
        # Si no califica, obtener las razones
        if not new_value:
          reasons = move._get_reimbursement_qualification_reasons()
          results['not_qualified'].append({
            'id': move.id,
            'name': move.name or f'ID {move.id}',
            'reasons': reasons
          })
      except Exception as e:
        results['errors'].append({
          'id': move.id,
          'name': move.name or f'ID {move.id}',
          'error': str(e)
        })
    
    # Construir mensaje para el usuario
    messages = []
    
    if results['updated']:
      count = len(results['updated'])
      messages.append(_(
        'Se actualizaron %d factura(s). '
        'El campo "Document Reimbursed" fue recalculado.'
      ) % count)
    
    if results['not_qualified']:
      messages.append(_('\n\nFacturas que NO califican como reembolso:'))
      for item in results['not_qualified']:
        reasons_text = '\n  - '.join(item['reasons'])
        messages.append(
          _('\n• %s:\n  - %s') % (item['name'], reasons_text)
        )
    
    if results['errors']:
      messages.append(_('\n\nErrores encontrados:'))
      for item in results['errors']:
        messages.append(_('\n• %s: %s') % (item['name'], item['error']))
    
    # Mostrar notificación
    if messages:
      message = ''.join(messages)
      return {
        'type': 'ir.actions.client',
        'tag': 'display_notification',
        'params': {
          'title': _('Actualización de Estado de Reembolso'),
          'message': message,
          'type': 'info' if not results['errors'] else 'warning',
          'sticky': True,
        }
      }
    else:
      return {
        'type': 'ir.actions.client',
        'tag': 'display_notification',
        'params': {
          'title': _('Actualización Completada'),
          'message': _('No se encontraron cambios necesarios.'),
          'type': 'info',
          'sticky': False,
        }
      }

  def _get_reimbursement_qualification_reasons(self):
    """
    Obtiene las razones por las que una factura NO califica como reembolso.
    
    Returns:
        list: Lista de strings con las razones
    """
    self.ensure_one()
    reasons = []
    
    # Razón 1: Tipo de documento
    if self.move_type != 'in_invoice':
      move_type_labels = {
        'entry': _('Asiento Contable'),
        'out_invoice': _('Factura de Cliente'),
        'out_refund': _('Nota de Crédito de Cliente'),
        'in_invoice': _('Factura de Proveedor'),
        'in_refund': _('Nota de Crédito de Proveedor'),
        'out_receipt': _('Recibo de Venta'),
        'in_receipt': _('Recibo de Compra'),
      }
      current_type_label = move_type_labels.get(self.move_type, self.move_type)
      reasons.append(
        _('Tipo de documento incorrecto. '
          'Debe ser "Factura de Proveedor" (in_invoice), '
          'actualmente es: %s (%s)') % (current_type_label, self.move_type)
      )
    
    # Razón 2: ATS Sustento
    if self.company_id.l10n_ec_ats_sustento_ids:
      if not self.l10n_latam_document_sustento:
        reasons.append(
          _('Falta el campo "Sustento ATS". '
            'La compañía requiere que las facturas de reembolso tengan un sustento ATS configurado.')
        )
      elif (
        self.l10n_latam_document_sustento
        not in self.company_id.l10n_ec_ats_sustento_ids
      ):
        sustento_name = self.l10n_latam_document_sustento.name or str(self.l10n_latam_document_sustento)
        allowed = ', '.join([
          s.name or str(s) 
          for s in self.company_id.l10n_ec_ats_sustento_ids
        ])
        reasons.append(
          _('El sustento ATS "%s" no está permitido para reembolsos. '
            'Sustentos permitidos: %s') % (sustento_name, allowed)
        )
    
    # Razón 3: Diario de Reembolso
    if self.company_id.l10n_ec_reimbursement_journal_ids:
      if not self.journal_id:
        reasons.append(
          _('Falta el diario. '
            'La compañía requiere que las facturas de reembolso usen uno de los diarios configurados.')
        )
      elif (
        self.journal_id not in self.company_id.l10n_ec_reimbursement_journal_ids
      ):
        journal_name = self.journal_id.name or str(self.journal_id)
        allowed = ', '.join([
          j.name or str(j) 
          for j in self.company_id.l10n_ec_reimbursement_journal_ids
        ])
        reasons.append(
          _('El diario "%s" no está permitido para reembolsos. '
            'Diarios permitidos: %s') % (journal_name, allowed)
        )
    
    # Si no hay razones específicas pero tampoco califica
    if not reasons and not self.l10n_ec_to_be_reimbursed:
      reasons.append(
        _('No se cumplen las condiciones configuradas para calificar como reembolso.')
      )
    
    return reasons

  def action_create_reimbursement(self, invoice):
    """Crea un documento de reembolso para esta factura"""
    if not self:
      raise ValidationError(
        'No se puede crear un reembolso para un registro vacío.'
      )

    self.ensure_one()
    for cinvoice in self:
      partner = cinvoice.partner_id
      tax = cinvoice.mapped('invoice_line_ids.tax_ids')

      series = str(cinvoice.l10n_latam_document_number).split('-')
      if len(series) == 3:
        se = series[0]
        pe = series[1]
        sec = str(series[2]).rjust(9, '0')
      else:
        se = cinvoice.l10n_latam_document_number[0:3]
        pe = cinvoice.l10n_latam_document_number[3:6]
        sec = cinvoice.l10n_latam_document_number[6:15]

      if not se:
        se = '000'
      if not pe:
        pe = '000'
      if not sec:
        sec = '999'

      self.env['account.reimbursement.document'].create(
        {
          'invoice_id': invoice.id,
          'partner_id': partner.id,
          'document_type_id': cinvoice.l10n_latam_document_type_id.id,
          'identification_type_id': partner.l10n_latam_identification_type_id.id,
          'identification_id': partner.vat,
          'serie_entidad': se,
          'serie_emision': pe,
          'num_secuencial': sec,
          'link_move_id': cinvoice.id,
          'autorizacionReemb': cinvoice.l10n_ec_authorization_number or '999',
          'fechaEmisionReemb': cinvoice.invoice_date or cinvoice.date,
          'baseImponibleReemb': abs(
            cinvoice.l10n_latam_amount_untaxed_zero
          ),  # Base Imponible tarifa 0% IVA Reembolso
          'baseImpGravReemb': abs(
            cinvoice.l10n_latam_amount_untaxed_not_zero
          ),  # Base Imponible tarifa IVA diferente de 0% Reembolso
          'montoIceRemb': 0.00,  # Monto ICE Reembolso
          'montoIvaRemb': abs(
            cinvoice.l10n_latam_amount_vat
          ),  # Monto IVA Reembolso
          'baseImpExeReemb': abs(
            cinvoice.l10n_latam_amount_untaxed_exempt_vat
          ),  # Base imponible exenta de IVA Reembolso
          # CORRECCIÓN FINAL: Usar la suma de las líneas de la factura, NO el total del header, 
          # para evitar discrepancias por redondeo en la factura origen.
          'baseNoGraIvaReemb': abs(
            cinvoice.l10n_latam_amount_untaxed_not_charged_vat
          ) + (abs(sum(cinvoice.invoice_line_ids.filtered(lambda l: l.display_type == 'product').mapped('price_total'))) - (
            abs(cinvoice.l10n_latam_amount_untaxed_zero) +
            abs(cinvoice.l10n_latam_amount_untaxed_not_zero) +
            abs(cinvoice.l10n_latam_amount_vat) +
            abs(cinvoice.l10n_latam_amount_untaxed_exempt_vat) +
            abs(cinvoice.l10n_latam_amount_untaxed_not_charged_vat)
          ) if (abs(sum(cinvoice.invoice_line_ids.filtered(lambda l: l.display_type == 'product').mapped('price_total'))) - (
            abs(cinvoice.l10n_latam_amount_untaxed_zero) +
            abs(cinvoice.l10n_latam_amount_untaxed_not_zero) +
            abs(cinvoice.l10n_latam_amount_vat) +
            abs(cinvoice.l10n_latam_amount_untaxed_exempt_vat) +
            abs(cinvoice.l10n_latam_amount_untaxed_not_charged_vat)
          )) > 0.001 else 0.0),  # Base Imponible no objeto de IVA - REEMBOLSO + Retenciones Asumidas + Ajustes Redondeo
          'tax_id': tax and tax[0].id or False,
        }
      )
      
      # LOG DE DEPURACIÓN PARA VERIFICAR CÁLCULO
      _logger = logging.getLogger(__name__)
      lineas_total = sum(cinvoice.invoice_line_ids.filtered(lambda l: l.display_type == 'product').mapped('price_total'))
      diferencia_calc = abs(lineas_total) - (
            abs(cinvoice.l10n_latam_amount_untaxed_zero) +
            abs(cinvoice.l10n_latam_amount_untaxed_not_zero) +
            abs(cinvoice.l10n_latam_amount_vat) +
            abs(cinvoice.l10n_latam_amount_untaxed_exempt_vat) +
            abs(cinvoice.l10n_latam_amount_untaxed_not_charged_vat)
      )
      _logger.info(f"CALCULO_DIFERENCIA_DEBUG: Factura {cinvoice.name} (ID {cinvoice.id}) - Total Lineas: {lineas_total} - Diferencia agregada: {diferencia_calc if diferencia_calc > 0.001 else 0.0}")
      
      # Agregar automáticamente los productos de la factura a la factura de reembolso
      self._add_invoice_products_to_reimbursement(cinvoice, invoice)
      # Usar write normal sin sudo() para evitar problemas de transacción
      cinvoice.write({'reimbursed_move_id': invoice.id})

  def _add_invoice_products_to_reimbursement(self, source_invoice, reimbursement_invoice):
    """
    Agrega automáticamente los productos de la factura fuente a la factura de reembolso.
    
    Args:
        source_invoice (account.move): Factura de la cual se toman los productos
        reimbursement_invoice (account.move): Factura de reembolso donde se agregan los productos
    """
    import logging
    _logger = logging.getLogger(__name__)
    
    if not source_invoice or not reimbursement_invoice:
      return
    
    _logger.info(f"UNIFICATION_DEBUG: Procesando factura {source_invoice.name} para reembolso {reimbursement_invoice.id}")
    
    # Obtener las líneas de productos de la factura fuente (excluyendo líneas de impuestos y otros)
    product_lines = source_invoice.invoice_line_ids.filtered(
      lambda line: line.product_id and line.display_type not in ['line_section', 'line_note']
    )
    
    _logger.info(f"UNIFICATION_DEBUG: Encontradas {len(product_lines)} líneas de productos")
    
    if not product_lines:
      return
    
    # Preparar las líneas de productos para la factura de reembolso con unificación
    invoice_line_vals = []
    unified_lines = {}  # Diccionario para agrupar líneas unificables
    
    for line in product_lines:
      # Calcular el precio unitario considerando descuentos
      price_unit = line.price_unit
      if line.discount:
        price_unit = price_unit * (1 - line.discount / 100.0)
      
      # Determinar y mapear impuestos de VENTA (no compras)
      partner = reimbursement_invoice.partner_id
      company = reimbursement_invoice.company_id
      fpos = reimbursement_invoice.fiscal_position_id or partner.property_account_position_id
      
      # LÓGICA DE MAPEO DINÁMICO DE IMPUESTOS (Fix 5% -> 15%) - V6.3 CROSS-COMPANY
      # 1. Obtener los impuestos de la línea original (Compra)
      # FIX CRÍTICO: NO filtrar por compañía de destino. La factura origen puede ser de otra compañía.
      # Tomamos todos los impuestos de la línea tal cual vienen.
      source_taxes = line.tax_ids
      
      _logger.info(f"IMPUESTOS_DEBUG: Procesando producto {line.product_id.name} - Impuestos Origen IDs (Todas Cías): {source_taxes.ids}")

      # 2. Si hay impuestos de compra, intentar encontrar su equivalente en ventas por porcentaje
      target_taxes = self.env['account.tax']
      
      # Pre-cargar TODOS los impuestos de venta candidatos de la compañía (y compartidos)
      # Esto evita problemas de redondeo en búsquedas ('amount', '=', 5.0) del ORM
      candidate_domain = [
          ('type_tax_use', '=', 'sale'),
          ('active', '=', True),
          '|', ('company_id', '=', company.id), ('company_id', '=', False)
      ]
      if company.country_id:
           candidate_domain += [('country_id', '=', company.country_id.id)]
      
      all_sales_taxes = self.env['account.tax'].sudo().search(candidate_domain)
      
      if source_taxes:
          import math
          for tax in source_taxes:
              # Solo nos interesan impuestos de IVA (no retenciones) para buscar equivalencia
              if tax.tax_group_id.l10n_ec_type and tax.tax_group_id.l10n_ec_type.startswith('withhold'):
                  continue
              
              _logger.info(f"IMPUESTOS_DEBUG: Buscando equivalente para IVA Compra {tax.name} ({tax.amount}%)")
              
              # Filtrar en Python para evitar errores de float en DB
              matching_candidates = all_sales_taxes.filtered(lambda t: math.isclose(t.amount, tax.amount, abs_tol=0.001))
              
              matching_sales_tax = False
              if matching_candidates:
                  # Priorizar impuestos de "Reembolso" si existen
                  reimb_matches = matching_candidates.filtered(lambda t: 'REEMB' in t.name.upper() or 'REEMBOLSO' in t.name.upper())
                  if reimb_matches:
                      matching_sales_tax = reimb_matches[0]
                  else:
                      matching_sales_tax = matching_candidates[0]
              
              if matching_sales_tax:
                  _logger.info(f"IMPUESTOS_DEBUG: Encontrado equivalente Venta: {matching_sales_tax.name} (ID {matching_sales_tax.id})")
                  target_taxes += matching_sales_tax
              else:
                  _logger.info(f"IMPUESTOS_DEBUG: NO se encontró equivalente Venta para {tax.amount}% entre {len(all_sales_taxes)} candidatos")
      
      # 3. Si encontramos impuestos equivalentes, usarlos. Si no, usar los del producto por defecto
      if target_taxes:
          sales_taxes = target_taxes
          _logger.info(f"IMPUESTOS_DEBUG: Usando impuestos mapeados: {sales_taxes.ids}")
      else:
          sales_taxes = line.product_id.taxes_id.filtered(lambda t: t.company_id == company and t.type_tax_use == 'sale')
          _logger.info(f"IMPUESTOS_DEBUG: Fallback - Usando impuestos por defecto del producto: {sales_taxes.ids}")

      if fpos:
        sales_taxes = fpos.map_tax(sales_taxes)
        
      # Excluir cualquier impuesto de retención (safety check final)
      sales_taxes = sales_taxes.filtered(lambda t: not (t.tax_group_id and t.tax_group_id.l10n_ec_type and t.tax_group_id.l10n_ec_type.startswith('withhold')))
      
      # Detectar si es un producto de servicio
      is_service = line.product_id.type == 'service'
      
      _logger.info(f"UNIFICATION_DEBUG_V6: Línea {line.id} - Producto: {line.product_id.id}, Tipo: {line.product_id.type}, Es servicio: {is_service}, Cantidad: {line.quantity}, Precio: {price_unit}")
      
      if is_service:
        # Para servicios: unificar por producto, impuestos y cuenta analítica
        # Convertir analytic_distribution a tupla para que sea hashable
        analytic_key = tuple(sorted(line.analytic_distribution.items())) if line.analytic_distribution else ()
        unification_key = (
          line.product_id.id,
          tuple(sorted(line.tax_ids.ids)),
          analytic_key,
        )
        
        if unification_key in unified_lines:
          # Unificar servicios: cantidad = 1, precio = suma de totales
          existing_line = unified_lines[unification_key]
          existing_line['price_unit'] += (line.quantity * price_unit)
          _logger.info(f"UNIFICATION_DEBUG: Unificando servicio - Clave: {unification_key}, Nuevo precio total: {existing_line['price_unit']}")
          # Mantener el nombre del primer registro (no cambiar)
        else:
          # Crear nueva línea de servicio
          product_code = line.product_id.product_tmpl_id.default_code or ''
          product_name = line.product_id.product_tmpl_id.name
          line_name = f"[{product_code}] {product_name}"
          
          line_vals = {
            'product_id': line.product_id.id,
            'name': line_name,
            'quantity': 1,  # Servicios siempre cantidad 1
            'price_unit': line.quantity * price_unit,  # Precio = total de la línea
            'discount': 0.0,
            'product_uom_id': line.product_uom_id.id,
            'tax_ids': [(6, 0, sales_taxes.ids)],
            'account_id': line.account_id.id,
            'analytic_distribution': line.analytic_distribution,
            'sequence': line.sequence,
            'reimbursement_tracking_id': line.reimbursement_tracking_id.id if line.reimbursement_tracking_id else False,
          }
          
          unified_lines[unification_key] = line_vals
          _logger.info(f"UNIFICATION_DEBUG: Creando nueva línea de servicio - Clave: {unification_key}, Precio: {line_vals['price_unit']}")
      else:
        # Para productos físicos: lógica original
        # Convertir analytic_distribution a tupla para que sea hashable
        analytic_key = tuple(sorted(line.analytic_distribution.items())) if line.analytic_distribution else ()
        unification_key = (
          line.product_id.id,
          price_unit,
          tuple(sorted(line.tax_ids.ids)),
          line.account_id.id,
          line.product_uom_id.id,
          analytic_key,
          0.0,  # discount siempre es 0.0
        )
        
        if unification_key in unified_lines:
          # Unificar con línea existente: sumar cantidades
          existing_line = unified_lines[unification_key]
          existing_line['quantity'] += line.quantity
          # Mantener el nombre del primer registro (no cambiar)
        else:
          # Crear nueva línea para producto físico
          product_code = line.product_id.product_tmpl_id.default_code or ''
          product_name = line.product_id.product_tmpl_id.name
          line_name = f"[{product_code}] {product_name}"
          
          line_vals = {
            'product_id': line.product_id.id,
            'name': line_name,
            'quantity': line.quantity,
            'price_unit': price_unit,
            'discount': 0.0,  # No aplicar descuentos adicionales
            'product_uom_id': line.product_uom_id.id,
            'tax_ids': [(6, 0, sales_taxes.ids)],
            'account_id': line.account_id.id,
            'analytic_distribution': line.analytic_distribution,
            'sequence': line.sequence,
            'reimbursement_tracking_id': line.reimbursement_tracking_id.id if line.reimbursement_tracking_id else False,
          }
          
          unified_lines[unification_key] = line_vals
    
    # Convertir diccionario unificado a lista
    invoice_line_vals = [(0, 0, line_vals) for line_vals in unified_lines.values()]
    
    
    
    _logger.info(f"UNIFICATION_DEBUG: Total de líneas unificadas: {len(invoice_line_vals)}")
    for i, line_vals in enumerate(lines for _, _, lines in invoice_line_vals):
      _logger.info(f"UNIFICATION_DEBUG: Línea {i+1} - Producto: {line_vals.get('product_id')}, Cantidad: {line_vals.get('quantity')}, Precio: {line_vals.get('price_unit')}")
    
    # Agregar las líneas a la factura de reembolso
    if invoice_line_vals:
      reimbursement_invoice.write({
        'invoice_line_ids': invoice_line_vals
      })
      
      # Forzar el recálculo de totales
      reimbursement_invoice._compute_amount()
      
      # Actualizar seguimiento de reembolsos usando el método del módulo de operaciones
      if hasattr(reimbursement_invoice, 'update_reimbursement_tracking_from_products'):
        reimbursement_invoice.update_reimbursement_tracking_from_products()

  def action_sync_reimbursement_products(self):
    """
    Sincroniza las líneas de productos de la factura de reembolso con los documentos de reembolso.
    Elimina todas las líneas de productos existentes y las vuelve a cargar desde los documentos.
    """
    self.ensure_one()
    
    if not self.is_reimbursement_invoice:
      return {
        'type': 'ir.actions.client',
        'tag': 'display_notification',
        'params': {
          'title': 'Error',
          'message': 'Esta función solo está disponible para facturas de reembolso.',
          'type': 'danger',
        },
      }
    
    if self.state != 'draft':
      return {
        'type': 'ir.actions.client',
        'tag': 'display_notification',
        'params': {
          'title': 'Error',
          'message': 'Solo se puede sincronizar cuando la factura está en borrador.',
          'type': 'danger',
        },
      }
    
    if not self.reimbursement_ids:
      return {
        'type': 'ir.actions.client',
        'tag': 'display_notification',
        'params': {
          'title': 'Información',
          'message': 'No hay documentos de reembolso para sincronizar.',
          'type': 'info',
        },
      }
    
    # Eliminar todas las líneas de productos existentes que fueron agregadas por reembolsos
    existing_reimbursement_lines = self.invoice_line_ids.filtered(
      lambda line: line.product_id and line.name and '[' in line.name and ']' in line.name
    )
    
    if existing_reimbursement_lines:
      existing_reimbursement_lines.unlink()
    
    # Volver a cargar las líneas desde los documentos de reembolso
    synced_count = 0
    for reimbursement_doc in self.reimbursement_ids:
      if reimbursement_doc.link_move_id:
        self._add_invoice_products_to_reimbursement(reimbursement_doc.link_move_id, self)
        synced_count += 1
    
    # Recalcular totales
    self._compute_amount()
    
    # Actualizar seguimiento de reembolsos usando el método del módulo de operaciones
    if hasattr(self, 'update_reimbursement_tracking_from_products'):
      self.update_reimbursement_tracking_from_products()
    
    # Forzar actualización de la vista usando reload
    return {
      'type': 'ir.actions.act_window',
      'res_model': 'account.move',
      'res_id': self.id,
      'view_mode': 'form',
      'target': 'current',
      'context': self.env.context,
    }

  def clear_reimbursement_records(self):
    """Elimina todos los registros de Documentos a Reembolsar y sus líneas de productos asociadas"""
    self.ensure_one()
    if self.state != 'draft':
      raise UserError(
        _(
          'Solo se pueden limpiar los registros cuando el documento está en borrador.'
        )
      )

    if not self.reimbursement_ids:
      raise UserError(_('No hay registros de reembolso para eliminar.'))

    # Contar registros antes de eliminar para mostrar mensaje
    count = len(self.reimbursement_ids)

    # Obtener los nombres de las facturas que se van a eliminar para identificar sus líneas
    reimbursement_invoice_names = []
    for reimbursement in self.reimbursement_ids.filtered(lambda r: r.link_move_id):
      if reimbursement.link_move_id:
        reimbursement_invoice_names.append(reimbursement.link_move_id.name)

    # Identificar y eliminar las líneas de productos que pertenecen a los reembolsos que se van a eliminar
    # Usar la misma lógica que funciona en el método write
    lines_to_remove = self.invoice_line_ids.filtered(
      lambda line: line.product_id and line.name and 
      line.display_type == 'product' and
      '[' in line.name and ']' in line.name and
      # Verificar si es una línea de reembolso (contiene patrón de código de producto)
      any(char.isdigit() or char.isalpha() for char in line.name.split(']')[0].split('[')[1] if ']' in line.name)
    )
    
    # Eliminar las líneas de productos específicas de los reembolsos
    if lines_to_remove:
      lines_to_remove.unlink()
      
      # Recalcular totales después de eliminar líneas
      self._compute_amount()

    # Limpiar los campos reimbursed_move_id de las facturas vinculadas
    for reimbursement in self.reimbursement_ids.filtered(
      lambda r: r.link_move_id
    ):
      if reimbursement.link_move_id:
        reimbursement.link_move_id.clear_reimbursement()

    # Eliminar todos los registros de reembolso
    self.reimbursement_ids.sudo().unlink()

    # Invalidar cache para asegurar que se actualicen los valores
    self.invalidate_recordset(['reimbursement_ids', 'reimbursement_total'])

    # Mostrar mensaje de éxito y actualizar solo la tabla
    return {
      'type': 'ir.actions.client',
      'tag': 'display_notification',
      'params': {
        'type': 'success',
        'title': _('Registros Eliminados'),
        'message': _(
          'Se eliminaron %d registro(s) de Documentos a Reembolsar y sus líneas de productos asociadas exitosamente. Cargando...'
        )
        % count,
        'sticky': False,
        'next': {
          'type': 'ir.actions.client',
          'tag': 'soft_reload',
        },
      },
    }

  def write(self, vals):
    """
    Intercepta cambios en reimbursement_ids para eliminar líneas de productos correspondientes
    cuando se eliminan registros de reembolso desde la interfaz.
    """
    # Solo procesar si hay cambios en reimbursement_ids
    if 'reimbursement_ids' in vals:
      for record in self:
        # Verificar si es una factura de reembolso (tiene reimbursement_ids)
        is_reimbursement = bool(record.reimbursement_ids)
        
        if is_reimbursement and record.state == 'draft':
          # Obtener los IDs de reembolsos que se están eliminando
          removed_reimbursement_ids = []
          for command in vals['reimbursement_ids']:
            if command[0] == 2:  # Eliminar (unlink)
              removed_reimbursement_ids.append(command[1])
            elif command[0] == 3:  # Desvincular (unlink)
              removed_reimbursement_ids.append(command[1])
            elif command[0] == 5:  # Reemplazar todos (clear)
              # Si se reemplazan todos, obtener los IDs actuales antes del cambio
              removed_reimbursement_ids = [r.id for r in record.reimbursement_ids]
          
          if removed_reimbursement_ids:
            # Obtener los nombres de las facturas que se van a eliminar
            try:
              reimbursement_docs = self.env['account.reimbursement.document'].browse(removed_reimbursement_ids)
              reimbursement_invoice_names = []
              for doc in reimbursement_docs:
                if doc.link_move_id:
                  reimbursement_invoice_names.append(doc.link_move_id.name)
              
              # Identificar y eliminar las líneas de productos que pertenecen a los reembolsos eliminados
              if reimbursement_invoice_names:
                # Buscar líneas que contengan el patrón de reembolso y que correspondan a las facturas eliminadas
                # Las líneas de reembolso tienen el formato [código] nombre_producto
                lines_to_remove = record.invoice_line_ids.filtered(
                  lambda line: line.product_id and line.name and 
                  line.display_type == 'product' and
                  '[' in line.name and ']' in line.name and
                  # Verificar si es una línea de reembolso (contiene patrón de código de producto)
                  any(char.isdigit() or char.isalpha() for char in line.name.split(']')[0].split('[')[1] if ']' in line.name)
                )
                
                # Si hay múltiples líneas de reembolso, eliminar solo una por cada reembolso eliminado
                if len(lines_to_remove) > len(reimbursement_invoice_names):
                  # Eliminar solo el número de líneas que corresponde a los reembolsos eliminados
                  lines_to_remove = lines_to_remove[:len(reimbursement_invoice_names)]
                
                if lines_to_remove:
                  lines_to_remove.unlink()
                  
                  # Recalcular totales después de eliminar líneas
                  record._compute_amount()
                  
                  # Actualizar seguimiento de reembolsos si existe el método
                  if hasattr(record, 'update_reimbursement_tracking_from_products'):
                    record.update_reimbursement_tracking_from_products()
                    
            except Exception as e:
              # Log error silently to avoid breaking the normal flow
              pass
    
    result = super().write(vals)
    return result
