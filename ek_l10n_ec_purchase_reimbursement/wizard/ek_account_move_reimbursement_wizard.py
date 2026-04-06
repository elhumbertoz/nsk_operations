# -*- coding: utf-8 -*-
from odoo import api, fields, models


class EkAccountMoveReimbursementWizard(models.TransientModel):
  _name = 'ek.account.move.reimbursement.wizard'
  _description = 'Wizard for Reimbursement Invoice Import'

  partner_id = fields.Many2one('res.partner', string='Cliente', readonly=True)
  invoice_id = fields.Many2one('account.move', string='Factura', readonly=True)
  move_ids = fields.Many2many(
    'account.move',
    string='Facturas a Importar',
    help='Facturas pre-seleccionadas. Puede eliminar las que no desee importar.',
  )

  # Computed field to provide the domain for move_ids
  available_move_ids = fields.Many2many(
    'account.move',
    string='Available Moves',
    compute='_compute_available_move_ids',
    store=False,
  )

  @api.depends('invoice_id')
  def _compute_available_move_ids(self):
    """Compute available moves for the domain"""
    for record in self:
      if record.invoice_id:
        filtered_ids = record._get_filtered_invoices(record.invoice_id)
        record.available_move_ids = [(6, 0, filtered_ids)]
      else:
        record.available_move_ids = [(6, 0, [])]

  @api.model
  def default_get(self, fields_list):
    """Pre-load the filtered invoices automatically"""
    res = super().default_get(fields_list)

    # Get context values
    active_id = self.env.context.get('active_id')
    if not active_id:
      return res

    # Get the reimbursement invoice
    reimbursement_invoice = self.env['account.move'].browse(active_id)
    if not reimbursement_invoice.exists():
      return res

    res['partner_id'] = reimbursement_invoice.partner_id.id
    res['invoice_id'] = active_id

    # Get the filtered invoices using the same logic
    filtered_move_ids = self._get_filtered_invoices(reimbursement_invoice)

    # Pre-load the invoices in move_ids
    if filtered_move_ids:
      res['move_ids'] = [(6, 0, filtered_move_ids)]

    return res

  def _get_filtered_invoices(self, reimbursement_invoice):
    """Get filtered invoices based on journey_crew_id"""
    # Base domain for reimbursable invoices
    base_domain = [
      ('move_type', '=', 'in_invoice'),
      ('state', '=', 'posted'),
      ('l10n_ec_to_be_reimbursed', '=', True),
      ('reimbursed_move_id', '=', False),
    ]

    # Get all invoices matching base criteria
    all_moves = self.env['account.move'].search(base_domain)

    # Get journey_crew_id from reimbursement invoice using SQL
    reimbursement_journey_crew_id = None
    if reimbursement_invoice.id:
      self.env.cr.execute(
        """
        SELECT journey_crew_id 
        FROM account_move 
        WHERE id = %s
      """,
        (reimbursement_invoice.id,),
      )
      result = self.env.cr.fetchone()
      if result:
        reimbursement_journey_crew_id = result[0]

    if not reimbursement_journey_crew_id:
      return []

    # Filter by journey_crew_id using SQL
    if all_moves:
      move_ids_str = ','.join(str(mid) for mid in all_moves.ids)
      self.env.cr.execute(
        f"""
        SELECT id 
        FROM account_move 
        WHERE id IN ({move_ids_str})
        AND journey_crew_id = %s
      """,
        (reimbursement_journey_crew_id,),
      )

      filtered_ids = [row[0] for row in self.env.cr.fetchall()]

      # Filtrar facturas que NO tienen 100% de descuento por notas de crédito
      if filtered_ids:
        final_filtered_ids = self._filter_invoices_with_remaining_balance(
          filtered_ids
        )
        return final_filtered_ids

    return []

  def _filter_invoices_with_remaining_balance(self, invoice_ids):
    """
    Filtra facturas que tienen saldo restante (no 100% cubierto por notas de crédito)
    y que cumplen con las reglas de negocio para reembolsos.

    Args:
        invoice_ids (list): Lista de IDs de facturas a filtrar

    Returns:
        list: IDs de facturas que tienen saldo restante y son válidas para reembolso
    """
    if not invoice_ids:
      return []

    invoices = self.env['account.move'].browse(invoice_ids)
    remaining_invoices = []

    for invoice in invoices:
      try:
        # Forzar el cálculo de notas de crédito si no está actualizado
        invoice._compute_credit_notes_info()

        # Obtener el porcentaje de descuento por NC
        percentage_str = invoice.credit_notes_applied_percentage or '0.0%'
        # Extraer el número del porcentaje (ej: "58.8%" -> 58.8)
        percentage = float(percentage_str.replace('%', ''))

        # Solo incluir facturas con menos del 100% de descuento
        if percentage < 100.0:
          # Aplicar regla de negocio: solo facturas donde todos los productos tienen impuestos
          if not invoice._has_lines_without_taxes():
            remaining_invoices.append(invoice.id)

      except Exception:
        # En caso de error, incluir la factura para evitar perder datos
        remaining_invoices.append(invoice.id)

    return remaining_invoices

  def action_import_from_move(self):
    """Import selected invoices as reimbursement lines"""

    if not self.move_ids:
      return {
        'type': 'ir.actions.client',
        'tag': 'display_notification',
        'params': {
          'title': 'Aviso',
          'message': 'No hay facturas seleccionadas para importar.',
          'type': 'warning',
        },
      }

    # Process the selected invoices using the same method as original wizard
    reimbursement_invoice = self.invoice_id
    imported_count = 0

    for move in self.move_ids:
      # Use the existing method to create reimbursement documents
      move.action_create_reimbursement(reimbursement_invoice)
      imported_count += 1

    # Mostrar notificación y cerrar wizard
    return {
      'type': 'ir.actions.client',
      'tag': 'display_notification',
      'params': {
        'title': 'Éxito',
        'message': f'Se importaron {imported_count} facturas correctamente. Cargando...',
        'type': 'success',
        'sticky': False,
        'next': {'type': 'ir.actions.act_window_close'},
      },
    }

  def action_clear_selection(self):
    """Clear all selected invoices"""
    # Create a new wizard instance without pre-loaded invoices
    new_wizard = self.create(
      {
        'partner_id': self.partner_id.id,
        'invoice_id': self.invoice_id.id,
        'move_ids': [(5, 0, 0)],  # Empty many2many
      }
    )

    return {
      'type': 'ir.actions.act_window',
      'res_model': self._name,
      'res_id': new_wizard.id,
      'view_mode': 'form',
      'target': 'new',
      'context': {**self.env.context, 'selection_cleared': True},
    }

  def action_load_all(self):
    """Load all available invoices for the current journey"""
    if not self.invoice_id:
      return {
        'type': 'ir.actions.client',
        'tag': 'display_notification',
        'params': {
          'title': 'Aviso',
          'message': 'No hay factura de reembolso seleccionada.',
          'type': 'warning',
        },
      }

    # Get all filtered invoices
    filtered_ids = self._get_filtered_invoices(self.invoice_id)

    if not filtered_ids:
      return {
        'type': 'ir.actions.client',
        'tag': 'display_notification',
        'params': {
          'title': 'Información',
          'message': 'No hay facturas disponibles para cargar en este viaje.',
          'type': 'info',
        },
      }

    # Create a new wizard instance with all invoices loaded
    new_wizard = self.create(
      {
        'partner_id': self.partner_id.id,
        'invoice_id': self.invoice_id.id,
        'move_ids': [(6, 0, filtered_ids)],
      }
    )

    return {
      'type': 'ir.actions.act_window',
      'res_model': self._name,
      'res_id': new_wizard.id,
      'view_mode': 'form',
      'target': 'new',
      'context': {
        **self.env.context,
        'loaded_all': True,
        'loaded_count': len(filtered_ids),
      },
    }
