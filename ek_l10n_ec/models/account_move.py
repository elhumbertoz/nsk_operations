# -*- coding: utf-8 -*-
__author__ = 'yordany'

import numbers
from datetime import timedelta

from lxml import etree
from odoo import SUPERUSER_ID, api, fields, models

# Try to import from l10n_ec modules, fallback to local definitions
try:
  from odoo.addons.l10n_ec.models.account_move import _DOCUMENTS_MAPPING
except ImportError:
  _DOCUMENTS_MAPPING = {}

try:
  from odoo.addons.l10n_ec_edi.models.account_move import (
    L10N_EC_VAT_RATES,
    L10N_EC_VAT_SUBTAXES,
    L10N_EC_VAT_TAX_GROUPS,
    L10N_EC_VAT_TAX_NOT_ZERO_GROUPS,
  )
except ImportError:
  # Fallback definitions if modules are not available
  L10N_EC_VAT_RATES = {}
  L10N_EC_VAT_SUBTAXES = {}
  L10N_EC_VAT_TAX_GROUPS = ()
  L10N_EC_VAT_TAX_NOT_ZERO_GROUPS = ()
from odoo.exceptions import UserError
from odoo.tools import config, float_compare, float_is_zero, formatLang
from odoo.tools.misc import format_date
from odoo.tools.translate import _
from odoo.tools.xml_utils import cleanup_xml_node

from . import utils

for key_doc in _DOCUMENTS_MAPPING:
  _DOCUMENTS_MAPPING[key_doc].append('ec_dt_100')
  if key_doc in ['01']:
    _DOCUMENTS_MAPPING[key_doc].append('ec_dt_19')
  if key_doc in ['04', '05', '06', '07']:
    _DOCUMENTS_MAPPING[key_doc].append('ec_dt_18')

if 'vat05' not in L10N_EC_VAT_SUBTAXES:
  L10N_EC_VAT_SUBTAXES['vat05'] = 5
if 'vat13' not in L10N_EC_VAT_SUBTAXES:
  L10N_EC_VAT_SUBTAXES['vat13'] = 10
if 'vat14' not in L10N_EC_VAT_SUBTAXES:
  L10N_EC_VAT_SUBTAXES['vat14'] = 3
if 'vat15' not in L10N_EC_VAT_SUBTAXES:
  L10N_EC_VAT_SUBTAXES['vat15'] = 4
if 'irbpnr' not in L10N_EC_VAT_SUBTAXES:
  L10N_EC_VAT_SUBTAXES['irbpnr'] = 5
if 'other' not in L10N_EC_VAT_SUBTAXES:
  L10N_EC_VAT_SUBTAXES['other'] = 0

if 5 not in L10N_EC_VAT_RATES:
  L10N_EC_VAT_RATES[5] = 5.0
if 10 not in L10N_EC_VAT_RATES:
  L10N_EC_VAT_RATES[10] = 13.0
if 3 not in L10N_EC_VAT_RATES:
  L10N_EC_VAT_RATES[3] = 14.0
if 4 not in L10N_EC_VAT_RATES:
  L10N_EC_VAT_RATES[4] = 15.0

L10N_EC_VAT_TAX_GROUPS = tuple(
  set(L10N_EC_VAT_TAX_NOT_ZERO_GROUPS + ('vat05', 'vat13', 'vat14', 'vat15', 'other'))
)


class AccountMove(models.Model):
  _inherit = 'account.move'

  l10n_latam_document_sustento = fields.Many2one(
    string='Sustento tributario',
    comodel_name='account.ats.sustento',
    required=False,
    ondelete='restrict',
  )
  l10n_latam_document_auth_required = fields.Boolean(
    related='journal_id.l10n_latam_document_auth_required',
  )
  l10n_latam_document_sustento_required = fields.Boolean(
    related='journal_id.l10n_latam_document_sustento_required',
  )
  credit_note_ids = fields.One2many(
    string='Notas de crédito',
    comodel_name='account.move',
    inverse_name='reversed_entry_id',
    help='Notas de crédito creadas para la factura.',
  )
  credit_note_count = fields.Integer(
    string='Número de notas de crédito',
    compute='_compute_credit_count',
    help='Cantidad de notas de crédito creadas para la factura.',
  )
  ats_declare = fields.Boolean(
    string='Declarado en ATS',
    related='l10n_latam_document_type_id.ats_declare',
    required=False,
  )
  # Technical field to show/hide "ADD WITHHOLD" button
  l10n_ec_withhold_pending = fields.Boolean(
    string='Retención pendiente',
    compute='_compute_l10n_ec_withhold_pending',
    store=True,
  )
  l10n_latam_amount_untaxed_zero = fields.Monetary(
    string='Base 0%',
    store=True,
    compute='_compute_l10n_latam_amount_untaxed_zero',
  )
  l10n_latam_amount_untaxed_not_charged_vat = fields.Monetary(
    string='No objeto de IVA',
    store=True,
    compute='_compute_l10n_latam_amount_untaxed_zero',
  )
  l10n_latam_amount_untaxed_exempt_vat = fields.Monetary(
    string='Exento de IVA',
    store=True,
    compute='_compute_l10n_latam_amount_untaxed_zero',
  )
  l10n_latam_amount_untaxed_not_zero = fields.Monetary(
    string='Base distinta de 0%',
    store=True,
    compute='_compute_l10n_latam_amount_untaxed_zero',
  )
  l10n_latam_amount_vat = fields.Monetary(
    string='IVA',
    store=True,
    compute='_compute_l10n_latam_amount_vat',
  )
  reimbursement_ids = fields.One2many(
    string='Documentos a reembolsar',
    comodel_name='account.reimbursement.document',
    inverse_name='invoice_id',
    required=False,
  )
  is_reimbursement_invoice = fields.Boolean(
    string='¿Es factura de reembolso?',
    default=False,
    readonly=True,
    compute='_compute_is_reimbursement_invoice',
    help='Si marca esta casilla, se indicará que se trata de una factura de rembolso de gastos y podrá ingresar la información respectiva.',
  )
  l10n_ec_credit_days = fields.Integer(
    string='Días de Crédito',
    compute='_compute_l10n_ec_credit_days',
    store=True,
  )
  l10n_ec_additional_information_move_ids = fields.One2many(
    string='Additional Information',
    comodel_name='ek_l10n_ec.additional.information',
    inverse_name='move_id',
  )

  reason_id = fields.Many2one(
    'account.move.refund.reason',
    string='Refund Reason',
    readonly=True,
    ondelete='restrict',
  )

  payment_mode_filter_type_domain = fields.Char(
    compute='_compute_payment_mode_filter_type_domain'
  )
  partner_bank_filter_type_domain = fields.Many2one(
    comodel_name='res.partner',
    compute='_compute_partner_bank_filter_type_domain',
  )
  payment_mode_id = fields.Many2one(
    comodel_name='account.payment.mode',
    compute='_compute_payment_mode_id',
    store=True,
    ondelete='restrict',
    readonly=False,
    check_company=True,
    tracking=True,
  )
  bank_account_required = fields.Boolean(
    related='payment_mode_id.payment_method_id.bank_account_required',
    readonly=True,
  )
  partner_bank_id = fields.Many2one(
    compute='_compute_partner_bank_id',
    store=True,
    ondelete='restrict',
    readonly=False,
  )
  has_reconciled_items = fields.Boolean(
    help='Technical field for supporting the editability of the payment mode',
    compute='_compute_has_reconciled_items',
  )

  l10n_ec_sri_cancellation_number = fields.Char(
    string='Código de anulación',
    help='Código emitido del SRI (10 dígitos)',
    size=10,
    required=False,
    readonly=True,
  )
  tax_closing_show_multi_closing_warning = fields.Char(
    string='Tax_closing_show_multi_closing_warning', required=False
  )

  def button_cancel_posted_moves(self):
    for rec in self:
      if rec.company_id.country_code == 'EC' and not self.env.context.get(
        'code_anulation_skip'
      ):
        return {
          'type': 'ir.actions.act_window',
          'name': _('Anulación Electrónica'),
          'res_model': 'sri.cancellation.number.wizard',
          'target': 'new',
          'view_id': self.env.ref(
            'ek_l10n_ec.sri_cancellation_number_wizard_form'
          ).id,
          'view_mode': 'form',
          'context': {
            **self.env.context,
            'default_move_id': rec.id,
          },
        }

    return super(AccountMove, self).button_cancel_posted_moves()

  def _l10n_ec_map_tax_groups(self, tax_id):
    # Maps different tax types (aka groups) to codes for electronic invoicing
    ec_type = tax_id.tax_group_id.l10n_ec_type
    if ec_type in L10N_EC_VAT_TAX_GROUPS:
      return 2
    elif ec_type == 'ice':
      return 3
    elif ec_type == 'irbpnr':
      return 5

    return super()._l10n_ec_map_tax_groups(tax_id)

  @api.depends('move_type')
  def _compute_payment_mode_filter_type_domain(self):
    for move in self:
      if move.move_type in ('out_invoice', 'in_refund'):
        move.payment_mode_filter_type_domain = 'inbound'
      elif move.move_type in ('in_invoice', 'out_refund'):
        move.payment_mode_filter_type_domain = 'outbound'
      else:
        move.payment_mode_filter_type_domain = False

  @api.depends('partner_id', 'move_type')
  def _compute_partner_bank_filter_type_domain(self):
    for move in self:
      if move.move_type in ('out_invoice', 'in_refund'):
        move.partner_bank_filter_type_domain = move.bank_partner_id
      elif move.move_type in ('in_invoice', 'out_refund'):
        move.partner_bank_filter_type_domain = move.commercial_partner_id
      else:
        move.partner_bank_filter_type_domain = False

  @api.depends('partner_id', 'company_id')
  def _compute_payment_mode_id(self):
    for move in self:
      if move.company_id and move.payment_mode_id.company_id != move.company_id:
        move.payment_mode_id = False
      if move.partner_id:
        partner = move.with_company(move.company_id.id).partner_id
        if move.move_type == 'in_invoice':
          move.payment_mode_id = partner.supplier_payment_mode_id
        elif move.move_type == 'out_invoice':
          move.payment_mode_id = partner.customer_payment_mode_id
        elif (
          move.move_type in ['out_refund', 'in_refund']
          and move.reversed_entry_id
        ):
          move.payment_mode_id = (
            move.reversed_entry_id.payment_mode_id.refund_payment_mode_id
          )
        elif not move.reversed_entry_id:
          if move.move_type == 'out_refund':
            move.payment_mode_id = (
              partner.customer_payment_mode_id.refund_payment_mode_id
            )
          elif move.move_type == 'in_refund':
            move.payment_mode_id = (
              partner.supplier_payment_mode_id.refund_payment_mode_id
            )

  @api.depends('bank_partner_id', 'payment_mode_id')
  def _compute_partner_bank_id(self):
    res = super()._compute_partner_bank_id()
    for move in self:
      payment_mode = move.payment_mode_id
      if payment_mode:
        if (
          move.move_type == 'in_invoice'
          and payment_mode.payment_type == 'outbound'
          and not payment_mode.payment_method_id.bank_account_required
        ):
          move.partner_bank_id = False
          continue
        elif move.move_type == 'out_invoice':
          if payment_mode.payment_method_id.bank_account_required:
            if (
              payment_mode.bank_account_link == 'fixed'
              and payment_mode.fixed_journal_id.bank_account_id
            ):
              move.partner_bank_id = (
                payment_mode.fixed_journal_id.bank_account_id
              )
              continue
          else:
            move.partner_bank_id = False
      else:
        move.partner_bank_id = False
    return res

  @api.depends('line_ids.matched_credit_ids', 'line_ids.matched_debit_ids')
  def _compute_has_reconciled_items(self):
    for record in self:
      lines_to_consider = record.line_ids.filtered(
        lambda x: x.account_id.account_type
        in ('asset_receivable', 'liability_payable')
      )
      record.has_reconciled_items = bool(
        lines_to_consider.matched_credit_ids
        + lines_to_consider.matched_debit_ids
      )

  def _reverse_moves(self, default_values_list=None, cancel=False):
    if not default_values_list:
      default_values_list = [{} for _ in self]
    for move, default_values in zip(self, default_values_list, strict=True):
      default_values['payment_mode_id'] = (
        move.payment_mode_id.refund_payment_mode_id.id
      )
      if move.move_type == 'in_invoice':
        default_values['partner_bank_id'] = move.partner_bank_id.id
    return super()._reverse_moves(
      default_values_list=default_values_list, cancel=cancel
    )

  def partner_banks_to_show(self):
    self.ensure_one()
    if self.partner_bank_id:
      return self.partner_bank_id
    if self.payment_mode_id.show_bank_account_from_journal:
      if self.payment_mode_id.bank_account_link == 'fixed':
        return self.payment_mode_id.fixed_journal_id.bank_account_id
      else:
        return self.payment_mode_id.variable_journal_ids.mapped(
          'bank_account_id'
        )
    if (
      self.payment_mode_id.payment_method_id.code == 'sepa_direct_debit'
    ):  # pragma: no cover
      return (
        self.mandate_id.partner_bank_id
        or self.partner_id.valid_mandate_id.partner_bank_id
      )
    # Return this as empty recordset
    return self.partner_bank_id

  @api.model_create_multi
  def create(self, vals_list):
    for vals in vals_list:
      # Force compute partner_bank_id when invoice is created from SO
      # to avoid that odoo _prepare_invoice method value will be set.
      if (
        self.env.context.get('active_model') == 'sale.order'
      ):  # pragma: no cover
        virtual_move = self.new(vals)
        virtual_move._compute_partner_bank_id()
        vals['partner_bank_id'] = virtual_move.partner_bank_id.id
    return super().create(vals_list)

  def _post(self, soft=True):
    res = super()._post(soft=soft)
    self.mapped('line_ids')._check_analytic_required()
    return res

  def _l10n_ec_get_invoice_additional_info(self):
    additiona_info = super()._l10n_ec_get_invoice_additional_info()
    if not additiona_info:
      additiona_info = {}

    if self.l10n_ec_additional_information_move_ids:
      for info in self.l10n_ec_additional_information_move_ids:
        additiona_info.update({info.name: info.description})

    return additiona_info

  @api.depends('invoice_date', 'invoice_date_due')
  def _compute_l10n_ec_credit_days(self):
    now = fields.Date.context_today(self)
    for invoice in self:
      date_invoice = invoice.invoice_date or now
      date_due = invoice.invoice_date_due or date_invoice
      invoice.l10n_ec_credit_days = (date_due - date_invoice).days

  @api.depends('l10n_latam_document_type_id')
  def _compute_is_reimbursement_invoice(self):
    for rec in self:
      rec.is_reimbursement_invoice = (
        rec.l10n_latam_document_type_id
        and rec.l10n_latam_document_type_id.code in ['41', '03']
        or False
      )

  @api.depends('credit_note_ids')
  def _compute_credit_count(self):
    for inv in self:
      inv.credit_note_count = len(inv.credit_note_ids)

  @api.depends(
    'l10n_ec_show_add_withhold',
    'country_code',
    'partner_id.withholding_issues',
    'state',
  )
  def _compute_l10n_ec_withhold_pending(self):
    date_init = (
      self.env.company.l10n_ec_withhold_start_date or fields.Date.today()
    )
    invoices_ec = self.filtered(
      lambda inv: inv.country_code == 'EC'
      and inv.invoice_date
      and inv.l10n_ec_show_add_withhold
      and inv.invoice_date >= date_init
      and inv.state == 'posted'
    )

    (self - invoices_ec).l10n_ec_withhold_pending = False
    for invoice in invoices_ec:
      if (
        invoice.move_type == 'out_invoice'
        and invoice.state == 'posted'
        and invoice.partner_id
        and invoice.partner_id.withholding_issues
      ):
        invoice.l10n_ec_withhold_pending = True
      else:
        invoice.l10n_ec_withhold_pending = False

  @api.depends(
    'invoice_line_ids.product_id',
    'invoice_line_ids.tax_ids',
    'invoice_line_ids.price_subtotal',
  )
  def _compute_l10n_latam_amount_vat(self):
    objectGroup = self.env['account.tax.group']
    tax_group_objects = objectGroup.search_read(
      [('l10n_ec_type', 'in', ['vat05', 'vat12', 'vat13', 'vat14', 'vat15', 'vat08'])], ['id']
    )
    for rec in self:
      try:
        invoice_totals = rec.tax_totals
        tax_group_ids = [group.get('id', 0) for group in tax_group_objects]
        amount_vat = 0.00
        for amount_by_group_list in invoice_totals[
          'groups_by_subtotal'
        ].values():
          for amount_by_group in amount_by_group_list:
            if amount_by_group['tax_group_id'] in tax_group_ids:
              amount_vat += amount_by_group.get('tax_group_amount', 0.00)
        if rec.is_inbound():
          sign = 1
        else:
          sign = -1
        rec.update({'l10n_latam_amount_vat': amount_vat * sign})
      except:
        rec.update({'l10n_latam_amount_vat': 0})

  @api.depends(
    'invoice_line_ids.product_id',
    'invoice_line_ids.tax_ids',
    'invoice_line_ids.price_subtotal',
  )
  def _compute_l10n_latam_amount_untaxed_zero(self):
    # recs_invoice = self.filtered(lambda x: x.is_invoice())
    for invoice in self:
      if invoice.is_invoice():
        base_zero = 0.00
        base_not_zero = 0.00
        base_not_charged_vat = 0.00
        base_exempt_vat = 0.00

        # Corregir lógica del signo según el tipo de factura
        sign = 1  # Para facturas de proveedor (in_invoice) debe ser positivo
        if invoice.move_type in ('out_invoice', 'in_refund'):
          sign = -1

        for line in invoice.invoice_line_ids:
          # Solo procesar líneas de producto/servicio (no líneas de cuenta)
          if line.display_type not in ('line_section', 'line_note'):
            has_tax = False

            if len(
              line.tax_ids.filtered(
                lambda a: a.tax_group_id.l10n_ec_type in ['zero_vat']
              )
            ):
              base_zero += line.price_subtotal
              has_tax = True

            if len(
              line.tax_ids.filtered(
                lambda a: a.tax_group_id.l10n_ec_type in ['not_charged_vat']
              )
            ):
              base_not_charged_vat += line.price_subtotal
              has_tax = True

            if len(
              line.tax_ids.filtered(
                lambda a: a.tax_group_id.l10n_ec_type in ['exempt_vat']
              )
            ):
              base_exempt_vat += line.price_subtotal
              has_tax = True

            if len(
              line.tax_ids.filtered(
                lambda a: a.tax_group_id.l10n_ec_type
                in ['vat05', 'vat12', 'vat13', 'vat14', 'vat08', 'vat15', 'irbpnr']
              )
            ):
              base_not_zero += line.price_subtotal
              has_tax = True

            # NOTA: Las líneas sin impuestos NO se incluyen automáticamente
            # porque deben ser filtradas en el wizard de importación de reembolsos

        invoice.update(
          {
            'l10n_latam_amount_untaxed_zero': base_zero * sign,
            'l10n_latam_amount_untaxed_not_zero': base_not_zero * sign,
            'l10n_latam_amount_untaxed_not_charged_vat': base_not_charged_vat
            * sign,
            'l10n_latam_amount_untaxed_exempt_vat': base_exempt_vat * sign,
          }
        )
      else:
        invoice.update(
          {
            'l10n_latam_amount_untaxed_zero': 0,
            'l10n_latam_amount_untaxed_not_zero': 0,
            'l10n_latam_amount_untaxed_not_charged_vat': 0,
            'l10n_latam_amount_untaxed_exempt_vat': 0,
          }
        )

  def _get_l10n_latam_documents_domain(self):
    self.ensure_one()
    try:
      return super()._get_l10n_latam_documents_domain()
    except:
      invoice_type = self.move_type
      internal_types = []
      if invoice_type in ['out_refund', 'in_refund']:
        internal_types = ['credit_note']
      elif invoice_type in ['out_invoice', 'in_invoice']:
        internal_types = ['invoice', 'debit_note']
      if self.debit_origin_id:
        internal_types = ['debit_note']
      internal_types += ['all']
      return [
        ('internal_type', 'in', internal_types),
        ('country_id', '=', self.company_id.account_fiscal_country_id.id),
      ]

  @api.depends(
    'country_code', 'l10n_latam_document_type_id.code', 'l10n_ec_withhold_ids'
  )
  def _compute_l10n_ec_show_add_withhold(self):
    # shows/hide "ADD WITHHOLD" button on invoices
    invoices_ec = self.filtered(lambda inv: inv.country_code == 'EC')
    (self - invoices_ec).l10n_ec_show_add_withhold = False
    for invoice in invoices_ec:
      final_consumer = self.env.ref('l10n_ec.ec_final_consumer', False)
      if final_consumer and invoice.partner_id == final_consumer:
        invoice.l10n_ec_show_add_withhold = False
      elif invoice.partner_id and invoice.partner_id.vat == 9999999999999:
        invoice.l10n_ec_show_add_withhold = False
      else:
        codes_to_withhold = [
          '01',  # Factura compra
          '18',  # Factura venta
          '41',  # Factura Reembolsos
          '100',  # Factura Reembolsos
          '02',  # Nota de venta
          '03',  # Liquidación compra
          '08',  # Entradas a espectáculos
          '09',  # Tiquetes
          '11',  # Pasajes
          '12',  # Inst Financieras
          '19',  # pago de aportes
          '20',  # Estado
          '21',  # Carta porte aéreo
          '47',  # Nota de crédito de reembolso
          '48',  # Nota de débito de reembolso
        ]
        add_withhold = (
          invoice.country_code == 'EC'
          and invoice.l10n_latam_document_type_id.code in codes_to_withhold
        )
        add_withhold = (
          add_withhold
          and not invoice.l10n_ec_withhold_ids.filtered(
            lambda w: w.state == 'posted'
          )
        )
        # Check if invoice has tax 332 (RIMPE) - if so, don't allow withholding
        if add_withhold and invoice.move_type == 'in_invoice':
          if invoice._has_tax_332():
            add_withhold = False
        invoice.l10n_ec_show_add_withhold = add_withhold

  def _check_withhold_tax_332_restriction(self):
    """
    Validates that invoices with tax 332 (RIMPE) cannot have withholdings applied.
    This method can be called before creating withholdings to prevent the error.
    """
    self.ensure_one()
    if self.move_type == 'in_invoice' and self._has_tax_332():
      raise UserError(
        _(
          'No se puede realizar retención a la factura %s porque contiene el impuesto 332 (RIMPE). '
          'Este tipo de impuesto no permite la aplicación de retenciones.'
        )
        % self.name
      )

  def _has_tax_332(self):
    """
    Helper method to check if an invoice has tax 332 (RIMPE).
    Returns True if the invoice contains tax 332, False otherwise.
    """
    self.ensure_one()
    if self.move_type == 'in_invoice':
      return any(
        line.tax_ids.filtered(lambda t: t.l10n_ec_code_base == '332')
        for line in self.invoice_line_ids
      )
    return False

  def _has_lines_without_taxes(self):
    """
    Helper method to check if an invoice has lines without taxes.
    Returns True if the invoice contains product/service lines without taxes.
    Used to filter invoices in reimbursement import wizard.
    """
    self.ensure_one()
    for line in self.invoice_line_ids:
      if line.display_type not in ('line_section', 'line_note'):
        if not line.tax_ids:
          return True
    return False

  def _is_reimbursement_journal(self):
    """
    Helper method to check if an invoice is using a reimbursement journal.
    First checks if the invoice is a reimbursement invoice by document type,
    then checks if the journal is configured as a reimbursement journal.
    """
    self.ensure_one()

    # First check: Is this a reimbursement invoice based on document type?
    if (
      hasattr(self, 'is_reimbursement_invoice')
      and self.is_reimbursement_invoice
    ):
      return True

    # Second check: Is the journal configured as a reimbursement journal?
    company = self.company_id or self.env.company
    if hasattr(company, 'l10n_ec_reimbursement_journal_ids'):
      reimbursement_journals = company.l10n_ec_reimbursement_journal_ids
      if reimbursement_journals and self.journal_id in reimbursement_journals:
        return True

    return False

  @api.onchange('partner_id')
  def _onchange_partner_id(self):
    res = super()._onchange_partner_id()
    if self.partner_id:
      rec_sustento = self.partner_id.l10n_latam_document_sustento
      rec_sri_payment = self.partner_id.l10n_ec_sri_payment_id
      if rec_sustento:
        self.l10n_latam_document_sustento = rec_sustento.id
      if rec_sri_payment:
        self.l10n_ec_sri_payment_id = rec_sri_payment.id
    return res

  @api.model
  def _get_l10n_ec_documents_allowed(self, identification_code):
    documents_allowed = super()._get_l10n_ec_documents_allowed(
      identification_code
    )
    for document_ref in _DOCUMENTS_MAPPING.get(identification_code.value, []):
      document_allowed = self.env.ref('ek_l10n_ec.%s' % document_ref, False)
      if document_allowed:
        documents_allowed |= document_allowed
    return documents_allowed

  @api.model
  def cron_send_email_for_withhold_pending(self, days=5):
    date_check = fields.Date.today() - timedelta(days=days)
    for rec in self.sudo().search(
      [
        ('l10n_ec_withhold_pending', '=', True),
        ('move_type', '!=', 'in_invoice'),
        ('company_id.l10n_ec_withhold_start_date', '!=', False),
        ('company_id.l10n_ec_withhold_pending_mail_tempalte_id', '!=', False),
        ('company_id.l10n_ec_withhold_pending_mail_send', '=', True),
        ('invoice_date', '>=', date_check),
      ]
    ):
      template = rec.company_id.l10n_ec_withhold_pending_mail_tempalte_id
      if template:
        template.send_mail(rec.id, force_send=True)

  def _check_fiscalyear_lock_date(self):
    res = super()._check_fiscalyear_lock_date()
    if self.env.context.get('bypass_journal_lock_date'):
      return res

    date_min = fields.date.min
    for move in self:
      if self.user_has_groups('account.group_account_manager'):
        lock_date = move.journal_id.fiscalyear_lock_date or date_min
      else:
        lock_date = max(
          move.journal_id.period_lock_date or date_min,
          move.journal_id.fiscalyear_lock_date or date_min,
        )
      if move.date <= lock_date:
        lock_date = format_date(self.env, lock_date)
        if self.user_has_groups('account.group_account_manager'):
          message = _(
            "You cannot add/modify entries for the journal '%(journal)s' "
            'prior to and inclusive of the lock date %(journal_date)s'
          ) % {
            'journal': move.journal_id.display_name,
            'journal_date': lock_date,
          }
        else:
          message = _(
            "You cannot add/modify entries for the journal '%(journal)s' "
            'prior to and inclusive of the lock date %(journal_date)s. '
            'Check the Journal settings or ask someone '
            "with the 'Adviser' role"
          ) % {
            'journal': move.journal_id.display_name,
            'journal_date': lock_date,
          }
        raise UserError(message)
      else:  # Check date client block
        if (
          move.move_type in ['out_invoice', 'out_refund']
          and move.partner_id
          and move.partner_id.l10n_ec_max_day_for_receipt_invoices > 0
        ):
          lock_day = move.partner_id.l10n_ec_max_day_for_receipt_invoices
          invoice_day = (
            move.invoice_date and move.invoice_date.day or move.date.day
          )

          if invoice_day > lock_day:
            message = _(
              "El documento de tipo '%(type)s' no puede ser validado ya que la fecha de emisión "
              "'%(date)s' es posterior al día que que esta espablecido en el contacto como día "
              'tope para facturación.\n'
              'Por restricciones contables del cliente, solo se aceptan documentos emitidos hasta '
              "el '%(day)s' de cada mes. Ajuste la fecha de emisión del documento antes de "
              'proceder con la validación.'
            ) % {
              'type': move.l10n_latam_document_type_id.display_name,
              'date': format_date(self.env, (move.invoice_date or move.date)),
              'day': lock_day,
            }
            raise UserError(message)
    return res

  def _test_invoice_line_tax(self):
    errors = []
    error_template = _(
      'La factura tiene una línea cuyo producto %s no tiene impuestos.'
    )
    error_template_iva = _(
      'La factura tiene una línea cuyo producto %s tiene más de un impuesto IVA.'
    )
    error_template_withhold_332 = _(
      'La factura tiene una línea cuyo producto %s contiene el impuesto 332 (RIMPE). '
      'No se permite agregar este impuesto cuando la factura es de proveedor y contiene retenciones.'
    )

    for invoice_line in self.mapped('invoice_line_ids').filtered(
      lambda x: x.display_type not in ('line_section', 'line_note')
    ):
      if not invoice_line.tax_ids:
        error_string = error_template % invoice_line.name
        errors.append(error_string)
      elif (
        len(
          invoice_line.tax_ids.filtered(
            lambda a: a.tax_group_id.l10n_ec_type
            in [
              'vat12',
              'vat14',
              'vat15',
              'vat08',
              'zero_vat',
              'not_charged_vat',
              'exempt_vat',
            ]
          )
        )
        > 1
      ):
        error_string = error_template_iva % invoice_line.name
        errors.append(error_string)
      # Validate that tax 332 is not allowed when invoice is from supplier and contains withholding
      elif (
        self.move_type == 'in_invoice'
        and self.l10n_ec_withhold_ids.filtered(lambda w: w.state == 'posted')
        and invoice_line.tax_ids.filtered(
          lambda t: t.l10n_ec_code_base == '332'
        )
      ):
        error_string = error_template_withhold_332 % invoice_line.name
        errors.append(error_string)

    if errors:
      raise UserError(
        _(
          '%(message)s\n%(errors)s',
          message='Los impuestos no están definidos o son incorrectos.',
          errors=('\n'.join(x for x in errors)),
        )
      )

  def action_post(self):
    # Always test if it is required by context
    force_test = self.env.context.get('test_tax_required')
    skip_test = any(
      (
        # It usually fails when installing other addons with demo data
        self.with_user(SUPERUSER_ID)
        .env['ir.module.module']
        .search(
          [
            ('state', 'in', ['to install', 'to upgrade']),
            ('demo', '=', True),
          ]
        ),
        # Avoid breaking unaware addons' tests by default
        config['test_enable'],
      )
    )

    l10n_ec_final_consumer_limit = float(
      self.env['ir.config_parameter']
      .sudo()
      .get_param('l10n_ec_final_consumer_limit', 50)
    )
    for move in self:
      # Reimbursement invoice validation: check if lines without taxes exist
      if move._is_reimbursement_journal() and move._has_lines_without_taxes():
        raise UserError(
          'Las facturas de reembolso no pueden confirmarse con líneas que no tengan impuestos aplicados. '
          'Por favor, agregue impuestos a todas las líneas de la factura antes de confirmar.'
        )

      if (
        move.l10n_latam_document_type_id
        and move.l10n_latam_document_type_id.required_tax
      ):
        if move.move_type != 'entry' and (force_test or not skip_test):
          move._test_invoice_line_tax()

      if move.country_code == 'EC' and move.move_type == 'out_invoice':
        company = move.company_id or self.env.company
        final_consumer = self.env.ref('l10n_ec.ec_final_consumer', False)
        if (
          final_consumer
          and move.partner_id == final_consumer
          and float_compare(
            move.amount_total,
            l10n_ec_final_consumer_limit,
            precision_digits=2,
          )
          == 1
        ) or (move.partner_id and move.partner_id.vat == 9999999999999):
          raise UserError(
            _(
              'El monto total %(Total)s es mayor que %(Limit)s que es el valor máximo permitido a facturar para Consumidor Final.'
            )
            % {
              'Total': formatLang(
                self.env,
                move.amount_total,
                currency_obj=company.currency_id,
              ),
              'Limit': formatLang(
                self.env,
                l10n_ec_final_consumer_limit,
                currency_obj=company.currency_id,
              ),
            }
          )
    return super(AccountMove, self).action_post()

  def action_view_credit_notes(self):
    self.ensure_one()
    return {
      'type': 'ir.actions.act_window',
      'name': _('Notas de Crédito'),
      'res_model': 'account.move',
      'view_mode': 'tree,form',
      'domain': [('reversed_entry_id', '=', self.id)],
    }

  def action_import_from_xml(self):
    import_from_xml_wizard = self.env.ref(
      'ek_l10n_ec.view_import_from_xml_wizard_form', False
    )
    return {
      'name': _('Importar desde XML'),
      'type': 'ir.actions.act_window',
      'view_type': 'form',
      'view_mode': 'form',
      'res_model': 'account.import.from.xml',
      'views': [(import_from_xml_wizard.id, 'form')],
      'view_id': import_from_xml_wizard.id,
      'target': 'new',
      'context': {'default_move_id': self.id},
    }

  def get_payment_amount(self, payment):
    self.ensure_one()
    move = self
    reconcile_lines = move.line_ids
    payment_total = 0
    payment_total += sum(
      reconcile_lines.mapped('matched_credit_ids')
      .filtered(
        lambda a: (a.credit_move_id and a.credit_move_id.payment_id == payment)
        or (a.debit_move_id and a.debit_move_id.payment_id == payment)
      )
      .mapped('amount')
    )
    payment_total += sum(
      reconcile_lines.mapped('matched_debit_ids')
      .filtered(
        lambda a: (a.credit_move_id and a.credit_move_id.payment_id == payment)
        or (a.debit_move_id and a.debit_move_id.payment_id == payment)
      )
      .mapped('amount')
    )

    return abs(payment_total)

  @api.model
  def _get_invoice_key_cols(self):
    return [
      'partner_id',
      'user_id',
      'move_type',
      'currency_id',
      'journal_id',
      'company_id',
      'partner_bank_id',
    ]

  @api.model
  def _get_invoice_line_key_cols(self):
    fields = [
      'name',
      'discount',
      'tax_ids',
      'price_unit',
      'product_id',
      'account_id',
      'analytic_distribution',
      'product_uom_id',
    ]
    for field in [
      'sale_line_ids',  # odoo/sale
      'purchase_line_id',  # odoo/purchase
      'purchase_price',  # OCA/account_invoice_margin
    ]:
      if field in self.env['account.move.line']._fields:
        fields.append(field)
    return fields

  @api.model
  def _get_first_invoice_fields(self, invoice):
    return {
      'invoice_origin': '%s' % (invoice.invoice_origin or '',),
      'partner_id': invoice.partner_id.id,
      'journal_id': invoice.journal_id.id,
      'user_id': invoice.user_id.id,
      'currency_id': invoice.currency_id.id,
      'company_id': invoice.company_id.id,
      'move_type': invoice.move_type,
      'state': 'draft',
      'payment_reference': '%s' % (invoice.payment_reference or '',),
      'name': '%s' % (invoice.name or '',),
      'fiscal_position_id': invoice.fiscal_position_id.id,
      'invoice_payment_term_id': invoice.invoice_payment_term_id.id,
      'invoice_line_ids': {},
      'partner_bank_id': invoice.partner_bank_id.id,
    }

  @api.model
  def _get_sum_fields(self):
    return ['quantity']

  @api.model
  def _get_invoice_line_vals(self, line):
    field_names = self._get_invoice_line_key_cols() + self._get_sum_fields()
    vals = {}
    origin_vals = line._convert_to_write(line._cache)
    for field_name, val in origin_vals.items():
      if field_name in field_names:
        vals[field_name] = val
    return vals

  def _get_draft_invoices(self):
    """Overridable function to return draft invoices to merge"""
    return self.filtered(lambda x: x.state == 'draft')

  def make_key(self, br, fields):
    """
    Return a hashable key
    """
    list_key = []
    for field in fields:
      field_val = getattr(br, field)
      if isinstance(field_val, dict):
        field_val = str(field_val)
      elif isinstance(field_val, models.Model):
        field_val = tuple(sorted(field_val.ids))
      list_key.append((field, field_val))
    list_key.sort()
    return tuple(list_key)

  # flake8: noqa: C901
  def do_merge(
    self,
    keep_references=True,
    date_invoice=False,
    remove_empty_invoice_lines=True,
  ):
    """
    To merge similar type of account invoices.
    Invoices will only be merged if:
    * Account invoices are in draft
    * Account invoices belong to the same partner
    * Account invoices are have same company, partner, address, currency,
      journal, currency, salesman, account, type
    Lines will only be merged if:
    * Invoice lines are exactly the same except for the quantity and unit

     @param self: The object pointer.
     @param keep_references: If True, keep reference of original invoices

     @return: new account invoice id

    """

    # compute what the new invoices should contain
    new_invoices = {}
    seen_origins = {}
    seen_client_refs = {}
    sum_fields = self._get_sum_fields()

    for account_invoice in self._get_draft_invoices():
      invoice_key = self.make_key(account_invoice, self._get_invoice_key_cols())
      new_invoice = new_invoices.setdefault(invoice_key, ({}, []))
      origins = seen_origins.setdefault(invoice_key, set())
      client_refs = seen_client_refs.setdefault(invoice_key, set())
      new_invoice[1].append(account_invoice.id)
      invoice_infos = new_invoice[0]
      if not invoice_infos:
        invoice_infos.update(self._get_first_invoice_fields(account_invoice))
        origins.add(account_invoice.invoice_origin)
        client_refs.add(account_invoice.payment_reference)
        if not keep_references:
          invoice_infos.pop('name')
      else:
        if (
          account_invoice.name
          and keep_references
          and invoice_infos.get('name') != account_invoice.name
        ):
          invoice_infos['name'] = (
            (invoice_infos['name'] or '') + ' ' + account_invoice.name
          )
        if (
          account_invoice.invoice_origin
          and account_invoice.invoice_origin not in origins
        ):
          invoice_infos['invoice_origin'] = (
            (invoice_infos['invoice_origin'] or '')
            + ' '
            + account_invoice.invoice_origin
          )
          origins.add(account_invoice.invoice_origin)
        if (
          account_invoice.payment_reference
          and account_invoice.payment_reference not in client_refs
        ):
          invoice_infos['payment_reference'] = (
            (invoice_infos['payment_reference'] or '')
            + ' '
            + account_invoice.payment_reference
          )
          client_refs.add(account_invoice.payment_reference)

      for invoice_line in account_invoice.invoice_line_ids:
        line_key = self.make_key(
          invoice_line, self._get_invoice_line_key_cols()
        )
        o_line = invoice_infos['invoice_line_ids'].setdefault(line_key, {})

        if o_line:
          # merge the line with an existing line
          for sum_field in sum_fields:
            if sum_field in invoice_line._fields:
              sum_val = invoice_line[sum_field]
              if isinstance(sum_val, numbers.Number):
                o_line[sum_field] += sum_val
        else:
          # append a new "standalone" line
          o_line.update(self._get_invoice_line_vals(invoice_line))

    allinvoices = []
    allnewinvoices = []
    invoices_info = {}
    old_invoices = self.env['account.move']
    qty_prec = self.env['decimal.precision'].precision_get(
      'Product Unit of Measure'
    )
    for invoice_key, (invoice_data, old_ids) in new_invoices.items():
      # skip merges with only one invoice
      if len(old_ids) < 2:
        allinvoices += old_ids or []
        continue

      if remove_empty_invoice_lines:
        invoice_data['invoice_line_ids'] = [
          (0, 0, value)
          for value in invoice_data['invoice_line_ids'].values()
          if not float_is_zero(value['quantity'], precision_digits=qty_prec)
        ]
      else:
        invoice_data['invoice_line_ids'] = [
          (0, 0, value) for value in invoice_data['invoice_line_ids'].values()
        ]

      if date_invoice:
        invoice_data['invoice_date'] = date_invoice

      # create the new invoice
      newinvoice = self.with_context(is_merge=True).create(invoice_data)
      invoices_info.update({newinvoice.id: old_ids})
      allinvoices.append(newinvoice.id)
      allnewinvoices.append(newinvoice)
      # cancel old invoices
      old_invoices = self.env['account.move'].browse(old_ids)
      old_invoices.with_context(is_merge=True).button_cancel()
    self.merge_callback(invoices_info, old_invoices)
    return invoices_info

  def get_reimbursument_values(self):
    """
    get values for reimbursument
    :param move:
    :return:
    """
    totalComprobantesReembolso = 0.00
    totalBaseImponibleReembolso = 0.00
    totalImpuestoReembolso = 0.00
    for reem in self.reimbursement_ids:
      totalComprobantesReembolso += (
        reem.baseImpGravReemb
        + reem.baseImponibleReemb
        + reem.baseImpExeReemb
        + reem.montoIvaRemb
        + reem.baseNoGraIvaReemb
        + reem.montoIceRemb
      )
      totalBaseImponibleReembolso += (
        reem.baseImpGravReemb
        + reem.baseImponibleReemb
        + reem.baseImpExeReemb
        + reem.baseNoGraIvaReemb
      )
      totalImpuestoReembolso += reem.montoIvaRemb + reem.montoIceRemb

    return {
      'codDocReembolso': 41,
      'totalComprobantesReembolso': totalComprobantesReembolso,
      'totalBaseImponibleReembolso': totalBaseImponibleReembolso,
      'totalImpuestoReembolso': totalImpuestoReembolso,
    }

  def _reembolsos(self):
    """ """
    reembolsos = []
    for line in self.reimbursement_ids:
      reembolsoDetalle = {
        'tipoIdentificacionProveedorReembolso': line.partner_id._get_sri_code_for_partner().value,
        'identificacionProveedorReembolso': line.partner_id.vat,
        'codPaisPagoProveedorReembolso': line.partner_id
        and line.partner_id.country_id
        and line.partner_id.country_id.l10n_ec_code_ats
        or 593,
        'tipoProveedorReembolso': '02'
        if line.partner_id.is_company
        else '01',  # 02 Sociedad #01 Natural
        'codDocReembolso': line.document_type_id.code,
        'estabDocReembolso': line.serie_entidad,
        'ptoEmiDocReembolso': line.serie_emision,
        'secuencialDocReembolso': line.num_secuencial,
        'fechaEmisionDocReembolso': line.fechaEmisionReemb,
        'numeroautorizacionDocReemb': line.autorizacionReemb,
      }
      detalleImpuestos = []

      if line.baseImponibleReemb:  # IVA 0
        detalleImpuesto = {
          'codigo': utils.codigoImpuesto['vat0'],
          'codigoPorcentaje': utils.tarifaImpuesto['vat0'],  # noqa
          'tarifa': '0',
          'baseImponibleReembolso': '{:.2f}'.format(line.baseImponibleReemb),
          'impuestoReembolso': '{:.2f}'.format(0.00),
        }
        detalleImpuestos.append(detalleImpuesto)
      if line.baseImpGravReemb:  # IVA 12
        detalleImpuesto = {
          'codigo': utils.codigoImpuesto['vat'],
          'codigoPorcentaje': utils.tarifaImpuesto['vat'],  # noqa
          'tarifa': line.tax_id
          and line.tax_id.amount
          and str(int(abs(line.tax_id.amount)))
          or '15',
          'baseImponibleReembolso': '{:.2f}'.format(line.baseImpGravReemb),
          'impuestoReembolso': '%.2f' % round(line.montoIvaRemb, 2),
        }
        detalleImpuestos.append(detalleImpuesto)

      reembolsoDetalle.update({'detalleImpuestos': detalleImpuestos})
      reembolsos.append(reembolsoDetalle)
    return {'reembolsos': reembolsos}

  def _l10n_ec_get_invoice_edi_data(self):
    invoice_edi_data = super()._l10n_ec_get_invoice_edi_data()
    invoice_edi_data.update(
      {'is_reimbursement_invoice': self.is_reimbursement_invoice}
    )
    if self.move_type == 'out_invoice' and self.is_reimbursement_invoice:
      inforeinbursument = self.get_reimbursument_values()
      invoice_edi_data.update(inforeinbursument)
      invoice_edi_data.update(self._reembolsos())

    return invoice_edi_data

  @staticmethod
  def order_line_update_invoice_lines(todos, all_old_inv_line):
    for todo in todos:
      for line in todo.order_line:
        invoice_line = line.invoice_lines.filtered(
          lambda x: x.parent_state != 'cancel' or x.id not in all_old_inv_line
        )
        if invoice_line:
          line.write({'invoice_lines': [(6, 0, invoice_line.ids)]})

  @api.model
  def merge_callback(self, invoices_info, old_invoices):
    # Make link between original sale order
    # None if sale is not installed
    # None if purchase is not installed
    if invoices_info:
      all_old_inv_line = old_invoices.mapped('invoice_line_ids').ids
      if 'sale.order' in self.env.registry:
        sale_todos = old_invoices.mapped(
          'invoice_line_ids.sale_line_ids.order_id'
        )
        self.order_line_update_invoice_lines(sale_todos, all_old_inv_line)

      if 'purchase.order' in self.env.registry:
        purchase_todos = old_invoices.mapped(
          'invoice_line_ids.purchase_line_id.order_id'
        )
        self.order_line_update_invoice_lines(purchase_todos, all_old_inv_line)

  def _l10n_ec_set_authorization_number(self):
    self.ensure_one()
    # Herencia por reembolsos enviar codigo de factura
    if self.l10n_latam_document_type_id.code == '41':
      company = self.company_id
      # NOTE: withholds don't have l10n_latam_document_type_id (WTH journals use separate sequence)
      document_code_sri = '01'  # if self._l10n_ec_is_withholding() else self.l10n_latam_document_type_id.code
      environment = company.l10n_ec_production_env and '2' or '1'
      serie = self.journal_id.l10n_ec_entity + self.journal_id.l10n_ec_emission
      sequential = self.name.split('-')[2].rjust(9, '0')
      num_filler = '31215214'  # can be any 8 digits, thanks @3cloud !
      emission = '1'  # corresponds to "normal" emission, "contingencia" no longer supported

      if not (
        document_code_sri
        and company.partner_id.vat
        and environment
        and serie
        and sequential
        and num_filler
        and emission
      ):
        return ''

      now_date = (
        self.l10n_ec_withhold_date
        if self._l10n_ec_is_withholding()
        else self.invoice_date
      ).strftime('%d%m%Y')
      key_value = (
        now_date
        + document_code_sri
        + company.partner_id.vat
        + environment
        + serie
        + sequential
        + num_filler
        + emission
      )
      self.l10n_ec_authorization_number = key_value + str(
        self._l10n_ec_get_check_digit(key_value)
      )
      return self.l10n_ec_authorization_number
    return super()._l10n_ec_set_authorization_number()


class AccountEdiFormat(models.Model):
  _inherit = 'account.edi.format'

  def _l10n_ec_get_xml_common_values(self, move):
    data = super()._l10n_ec_get_xml_common_values(move=move)

    data.update({'calculate_rate': self._l10n_ec_calculate_rate})
    return data

  def _l10n_ec_calculate_rate(self, data):
    return (
      abs(data.get('tax_amount', 0) / (data.get('base_amount', 1) or 1)) * 100
    )

  def _l10n_ec_generate_xml_testing(self, move):
    # Gather XML values
    move_info = self._l10n_ec_get_xml_common_values(move)
    if move.journal_id.l10n_ec_withhold_type:  # withholds
      doc_type = 'withhold'
      template = 'l10n_ec_edi.withhold_template'
      move_info.update(move._l10n_ec_get_withhold_edi_data())
    else:  # invoices
      doc_type = move.l10n_latam_document_type_id.internal_type
      template = {
        'credit_note': 'l10n_ec_edi.credit_note_template',
        'debit_note': 'l10n_ec_edi.debit_note_template',
        'invoice': 'l10n_ec_edi.invoice_template',
        'purchase_liquidation': 'l10n_ec_edi.purchase_liquidation_template',
      }[doc_type]
      move_info.update(move._l10n_ec_get_invoice_edi_data())

    # Generate XML document
    errors = []
    if move_info.get('taxes_data'):
      errors += self._l10n_ec_remove_negative_lines_from_move_info(move_info)
    xml_content = self.env['ir.qweb']._render(template, move_info)
    xml_content = cleanup_xml_node(xml_content)
    errors += self._l10n_ec_validate_with_xsd(xml_content, doc_type)
    # Sign the document
    xml_signed = etree.tostring(xml_content, encoding='unicode')
    xml_signed = (
      '<?xml version="1.0" encoding="utf-8" standalone="no"?>' + xml_signed
    )
    return xml_signed, errors
