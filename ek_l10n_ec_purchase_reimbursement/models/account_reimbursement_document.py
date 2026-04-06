# -*- coding: utf-8 -*-
import logging

from odoo import api, fields, models

_logger = logging.getLogger(__name__)


class AccountReimbursementDocument(models.Model):
  _inherit = 'account.reimbursement.document'

  purchase_order_id = fields.Many2one(
    'purchase.order', string='Orden de Compra', copy=False
  )
  link_move_id = fields.Many2one('account.move', string='Factura', copy=False)
  company_id = fields.Many2one(
      'res.company',
      related='link_move_id.company_id',
      string='Compañía',
      store=True,
      readonly=True
  )


  
  # Campo calculado para el total del documento
  total_amount = fields.Float(
    string='Total',
    compute='_compute_total_amount',
    store=True,
    help='Total del documento de reembolso',
  )

  # Campo computado para retenciones asumidas
  assumed_retention = fields.Float(
    string='Retención Asumida',
    compute='_compute_assumed_retention',
    store=True,
    help='Valor de retenciones asumidas por la empresa (Cuentas 52022*)'
  )

  @api.depends('link_move_id', 'link_move_id.line_ids')
  def _compute_assumed_retention(self):
    for record in self:
      amount = 0.0
      if record.link_move_id:
        # Obtener prefijo de la configuración de la compañía
        # Usar 52022 por defecto si no está configurado para mantener compatibilidad
        prefix = record.company_id.l10n_ec_assumed_retention_account_prefix or '52022'
        
        # Buscar líneas con cuentas que empiecen con el prefijo configurado
        # Usamos sudo() por si el usuario no tiene acceso a cuentas contables
        retention_lines = record.link_move_id.sudo().line_ids.filtered(
          lambda l: l.account_id.code and l.account_id.code.startswith(prefix)
        )
        amount = sum(retention_lines.mapped('balance'))
      record.assumed_retention = amount

  @api.depends(
    'baseImponibleReemb',
    'baseImpGravReemb',
    'baseNoGraIvaReemb',
    'baseImpExeReemb',
    'montoIceRemb',
    'montoIvaRemb',
    'assumed_retention',
  )
  def _compute_total_amount(self):
    """Calcula el total sumando las bases e impuestos y restando retenciones asumidas"""
    for record in self:
      total = (
        (record.baseImponibleReemb or 0.0)
        + (record.baseImpGravReemb or 0.0)
        + (record.baseNoGraIvaReemb or 0.0)
        + (record.baseImpExeReemb or 0.0)
        + (record.montoIceRemb or 0.0)
        + (record.montoIvaRemb or 0.0)
        - (record.assumed_retention or 0.0)
      )
      record.total_amount = total

  def _remove_reimbursement_product_lines(self):
    """
    Elimina las líneas de productos de la factura de reembolso que corresponden
    a las facturas vinculadas en este documento de reembolso.
    """
    for record in self:
      if not record.invoice_id or not record.link_move_id:
        continue
      
      # Obtener las líneas de productos de la factura de reembolso
      reimbursement_invoice = record.invoice_id
      if not reimbursement_invoice.exists():
        continue
      
      # Buscar líneas que correspondan a la factura fuente
      # Identificamos las líneas por el nombre que contiene el formato [FACTURA] producto
      source_invoice_name = record.link_move_id.name
      lines_to_remove = reimbursement_invoice.invoice_line_ids.filtered(
        lambda line: line.product_id and line.name and f"[{source_invoice_name}]" in line.name
      )
      
      if lines_to_remove:
        # Eliminar las líneas encontradas
        lines_to_remove.unlink()
        
        # Recalcular totales
        reimbursement_invoice._compute_amount()

  def unlink(self):
    # Eliminar las líneas de productos correspondientes antes de eliminar el documento
    self._remove_reimbursement_product_lines()
    
    if self.purchase_order_id:
      self.purchase_order_id.clear_reimbursement()
    if self.link_move_id:
      self.link_move_id.clear_reimbursement()
    return super(AccountReimbursementDocument, self).unlink()
