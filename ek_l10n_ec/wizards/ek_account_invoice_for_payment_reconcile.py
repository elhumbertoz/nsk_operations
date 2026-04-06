from odoo import fields, models, api, Command, _
from odoo.exceptions import ValidationError, UserError


class EkAccountInvoicePaymentReconcile(models.TransientModel):
  _name = 'ek.account.invoice.payment.reconcile'
  _description = 'Reconciliación de Anticipos'

  advance_payment_id = fields.Many2one(
    comodel_name='account.payment', string='Anticipo', required=True
  )

  partner_id = fields.Many2one(related='advance_payment_id.partner_id')

  line_ids = fields.One2many(
    comodel_name='ek.account.invoice.payment.reconcile.line',
    inverse_name='wizard_id',
    string='Reconcile Register',
    required=False,
  )

  exist_invoices = fields.Boolean(string='Existen Facturas', required=False)

  currency_id = fields.Many2one(related='advance_payment_id.currency_id')

  advance_amount_residual = fields.Monetary(
    string='Pendiente de Cruce',
    related='advance_payment_id.advance_amount_residual',
    required=False,
  )

  concilie_date = fields.Date(
    string='Fecha Contable', required=False, default=fields.Date.today()
  )
  distribute_amount = fields.Boolean(string='Desglosar Montos', required=False)

  partner_type = fields.Selection(
    related='advance_payment_id.partner_type',
    string='Tipo de Cliente',
    required=False,
  )

  @api.model
  def default_get(self, fields, active_ids=None):
    res = super().default_get(fields)
    advance_payment = self.advance_payment_id
    if not advance_payment:
      advance_payment = self.env['account.payment'].browse(
        self.env.context.get('default_advance_payment_id', 0)
      )
    if advance_payment and advance_payment.partner_id:
      AccountMove = self.env['account.move']
      domain = [
        ('partner_id', '=', advance_payment.partner_id.id),
        ('state', '=', 'posted'),
        ('amount_residual', '>', 0),
      ]
      if advance_payment.partner_type == 'customer':
        domain.extend([('move_type', '=', 'out_invoice')])
      elif self.advance_payment_id.partner_type == 'supplier':
        domain.extend([('move_type', '=', 'in_invoice')])

      ids = AccountMove.search_read(
        domain=domain, order='invoice_date_due', fields=['id']
      )

      if ids:
        res.update({'exist_invoices': True})
        line_ids = []
        sequence = 10
        for idm in ids:
          sequence += 10
          line_ids.append(
            (0, 0, {'move_id': idm, 'sequence': sequence, 'wizard_id': self.id})
          )
        res.update({'line_ids': line_ids})
    return res

  def action_reconcile(self):
    for rec in self:
      if not rec.line_ids:
        raise ValidationError(
          'No es posible conciliar un anticipo si no existen facturas pendientes'
        )
      if rec.advance_payment_id.is_reconciled:
        raise ValidationError(
          'No es posible conciliar un anticipo que ya ha sido conciliado en su totalidad'
        )

      if rec.advance_payment_id.date > rec.concilie_date:
        raise ValidationError(
          'La fecha contable no puede ser menor a la fecha del anticipo'
        )

      AcountMove = self.env['account.move']
      partner = rec.partner_id
      # Create entry to reclassify the advance payment

      amount_total = 0
      invoice_amount = 0
      payment = rec.advance_payment_id
      company = payment.company_id
      move_line_advance_reconcile = self.env['account.move.line']
      move_line_invoice_reconcile = self.env['account.move.line']
      partner_account = False
      credit_acc = False
      date = rec.concilie_date or fields.Date.today()

      if rec.advance_payment_id.partner_type == 'customer':
        journal = company.l10n_ec_advance_journal_receivable_id
        credit_acc = company.l10n_ec_advance_account_receivable_id

        if (
          rec.partner_id.country_code != 'EC'
          and company.l10n_ec_advance_account_foreign_receivable_id
        ):
          credit_acc = company.l10n_ec_advance_account_foreign_receivable_id

        debit_acc = rec.partner_id.with_company(
          company
        ).property_account_receivable_id
        partner_account = debit_acc

        for line in payment.move_id.mapped('line_ids'):
          if not line.is_account_reconcile or line.amount_residual == 0:
            continue
          if line.account_id == credit_acc:
            move_line_advance_reconcile |= line
            amount_total += line.amount_residual

        name = 'Cruce Anticipo de Cliente %s (%s) - %s - %s' % (
          rec.advance_payment_id.name,
          abs(amount_total),
          partner.name,
          date,
        )
        sign = -1
      else:
        journal = company.l10n_ec_advance_journal_payable_id
        debit_acc = rec.partner_id.with_company(
          company
        ).property_account_payable_id
        credit_acc = company.l10n_ec_advance_account_payable_id

        if (
          rec.partner_id.country_code != 'EC'
          and company.l10n_ec_advance_account_foreign_payable_id
        ):
          credit_acc = company.l10n_ec_advance_account_foreign_payable_id

        partner_account = debit_acc
        sign = 1
        for line in payment.move_id.mapped('line_ids'):
          if not line.is_account_reconcile or line.amount_residual == 0:
            continue
          if line.account_id == credit_acc:
            move_line_advance_reconcile |= line
            amount_total += line.amount_residual

        name = 'Cruce Anticipo a Provedor %s (%s) - %s - %s' % (
          rec.advance_payment_id.name,
          abs(amount_total),
          partner.name,
          date,
        )

      invoice_amount = sum(
        rec.line_ids.mapped('move_id').mapped('amount_residual')
      )

      amount_total = min(abs(invoice_amount), abs(amount_total))
      move = AcountMove.create(
        {
          'move_type': 'entry',
          'date': date,
          'journal_id': journal.id,
          'line_ids': [
            Command.create(
              rec._prepare_amount_line(debit_acc, amount_total * sign, name)
            ),
            Command.create(
              rec._prepare_amount_line(
                credit_acc, amount_total * -1 * sign, name
              )
            ),
          ],
        }
      )
      move.action_post()

      lines_advance = move.line_ids.filtered(lambda a: a.account_id.reconcile)

      for line in lines_advance:
        if line.account_id in [
          company.l10n_ec_advance_account_receivable_id,
          company.l10n_ec_advance_account_payable_id,
          company.l10n_ec_advance_account_foreign_receivable_id,
          company.l10n_ec_advance_account_foreign_payable_id,
        ]:
          move_line_advance_reconcile |= line
        elif line.account_id == partner_account:
          move_line_invoice_reconcile = line

      if len(move_line_advance_reconcile) > 1:
        move_line_advance_reconcile.reconcile()

      for inv in rec.line_ids:
        if (
          move_line_invoice_reconcile.full_reconcile_id
          or not move_line_invoice_reconcile.account_id.reconcile
          or move_line_invoice_reconcile.amount_residual == 0
        ):
          continue

        l_reconcile = move_line_invoice_reconcile
        if inv.amount_residual > 0:
          l_reconcile |= inv.move_id.line_ids.filtered(
            lambda a: a.account_id == partner_account
          )

        if len(l_reconcile) > 1:
          l_reconcile.reconcile()

  def action_reconcile_distributed(self):
    for rec in self:
      if not rec.distribute_amount:
        raise ValidationError(
          'No es posible conciliar un anticipo si no se ha distribuido el monto'
        )
      if not rec.line_ids:
        raise ValidationError(
          'No es posible conciliar un anticipo si no existen facturas pendientes'
        )
      if rec.advance_payment_id.is_reconciled:
        raise ValidationError(
          'No es posible conciliar un anticipo que ya ha sido conciliado en su totalidad'
        )
      if rec.advance_payment_id.date > rec.concilie_date:
        raise ValidationError(
          'La fecha contable no puede ser menor a la fecha del anticipo'
        )
      if rec.advance_payment_id.partner_type != 'customer':
        raise ValidationError(
          'No es posible distribuir un anticipo de proveedor'
        )

      total_amount = sum(rec.line_ids.mapped('amount_payment'))
      if total_amount > rec.advance_payment_id.advance_amount_residual:
        raise UserError(
          _(
            'El monto de la distribución debe ser menor o igual al monto del anticipo'
          )
        )
      if total_amount <= 0:
        raise UserError(_('El monto de la distribución debe ser mayor a cero'))

      AcountMove = self.env['account.move']
      partner = rec.partner_id
      # Create entry to reclassify the advance payment

      amount_total = 0

      payment = rec.advance_payment_id

      company = payment.company_id
      move_line_advance_reconcile = self.env['account.move.line']
      # move_line_invoice_reconcile = self.env['account.move.line']
      partner_account = False

      date = rec.concilie_date or fields.Date.today()

      journal = company.l10n_ec_advance_journal_receivable_id
      debit_acc = company.l10n_ec_advance_account_receivable_id

      if (
        rec.partner_id.country_code != 'EC'
        and company.l10n_ec_advance_account_foreign_receivable_id
      ):
        debit_acc = company.l10n_ec_advance_account_foreign_receivable_id

      credit_acc = rec.partner_id.with_company(
        company
      ).property_account_receivable_id
      partner_account = credit_acc

      name = 'Cruce Anticipo de Cliente %s (%s) - %s - %s' % (
        rec.advance_payment_id.name,
        abs(amount_total),
        partner.name,
        date,
      )
      sign = -1

      for line in payment.move_id.mapped('line_ids'):
        if not line.is_account_reconcile or line.amount_residual == 0:
          continue
        if line.account_id == debit_acc:
          move_line_advance_reconcile |= line

      lines = [
        Command.create(
          rec._prepare_amount_line(
            debit_acc,
            (total_amount * -1) * sign,
            name,
          )
        )
      ]

      for adv in rec.line_ids.filtered(lambda a: a.amount_payment > 0):
        lines.append(
          Command.create(
            rec._prepare_amount_line(
              credit_acc, adv.amount_payment * sign, adv.move_id.name
            )
          )
        )
      move = AcountMove.create(
        {
          'move_type': 'entry',
          'date': date,
          'journal_id': journal.id,
          'line_ids': lines,
        }
      )

      move.action_post()

      lines_advance = move.line_ids.filtered(lambda a: a.account_id.reconcile)
      move_line_invoice_reconcile = {}
      for line in lines_advance:
        if line.account_id in [
          company.l10n_ec_advance_account_receivable_id,
          company.l10n_ec_advance_account_payable_id,
          company.l10n_ec_advance_account_foreign_receivable_id,
          company.l10n_ec_advance_account_foreign_payable_id,
        ]:
          move_line_advance_reconcile |= line
        elif line.account_id == partner_account:
          if line.name not in move_line_invoice_reconcile:
            move_line_invoice_reconcile[line.name] = self.env[
              'account.move.line'
            ]

          move_line_invoice_reconcile[line.name] |= line

      if len(move_line_advance_reconcile) > 1:
        move_line_advance_reconcile.reconcile()

      for inv in rec.line_ids:
        l_reconcile = move_line_invoice_reconcile.get(inv.move_id.name, False)
        if l_reconcile and inv.amount_residual > 0:
          l_reconcile |= inv.move_id.line_ids.filtered(
            lambda a: a.account_id == partner_account
          )

          if len(l_reconcile) > 1:
            l_reconcile.reconcile()

  def _prepare_amount_line(self, account, amount, name):
    res = {
      'account_id': account.id,
      'date_maturity': fields.Date.today(),
      'partner_id': self.partner_id.id,
      'name': name,
      'date': fields.Date.today(),
      'debit': amount > 0 and amount,
      'credit': amount < 0 and -amount,
      'ref': 'Anticipo - %s' % self.advance_payment_id.name,
    }
    return res

  @api.constrains('line_ids.amount_payment', 'distribute_amount')
  def _check_amount_payment(self):
    for rec in self:
      if rec.distribute_amount:
        total_amount = round(sum(rec.line_ids.mapped('amount_payment')), 2)
        if total_amount > rec.advance_payment_id.advance_amount_residual:
          raise UserError(
            _(
              'El monto de la distribución debe ser menor o igual al monto del anticipo'
            )
          )
        if total_amount <= 0:
          raise UserError(
            _('El monto de la distribución debe ser mayor a cero')
          )

class EkAccountInvoicePaymentReconcileLine(models.TransientModel):
  _name = 'ek.account.invoice.payment.reconcile.line'
  _description = 'Lineas de Reconciliación de Anticipos'
  _order = 'sequence'

  sequence = fields.Integer(string='Sequence', default=10, required=False)

  wizard_id = fields.Many2one(
    comodel_name='ek.account.invoice.payment.reconcile',
    string='Reconcile Register',
    required=False,
  )

  move_id = fields.Many2one(
    comodel_name='account.move', string='Documento', required=False
  )

  invoice_number = fields.Char(
    comodel_name='account.move',
    related='move_id.name',
    string='Documento',
    required=False,
  )

  date_due = fields.Date(related='move_id.invoice_date_due', readonly=True)

  amount_residual = fields.Monetary(
    related='move_id.amount_residual',
    readonly=True,
    currency_field='company_currency_id',
  )

  amount_payment = fields.Monetary(
    readonly=False,
    required=True,
    currency_field='company_currency_id',
  )

  payment_state = fields.Selection(
    related='move_id.payment_state',
    readonly=True,
  )

  company_currency_id = fields.Many2one(
    related='move_id.currency_id', string='Moneda de la empresa', readonly=True
  )

  def _compute_amount_payment(self):
    for rec in self:
      rec.amount_payment = rec.move_id.amount_residual

  @api.constrains('amount_payment', 'move_id.amount_residual')
  def _check_amount_payment(self):
    for rec in self:
      if rec.amount_payment < 0:
        raise UserError(
          _('El monto de la distribución debe ser mayor o igual a cero')
        )
      if round(rec.amount_payment, 2) > rec.move_id.amount_residual:
        print(rec.amount_payment, rec.move_id)
        raise UserError(
          _(
            'El monto de la distribución debe ser menor o igual que el monto pendiente de la factura %s'
            % rec.move_id.name
          )
        )
