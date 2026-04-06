# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models


class ResConfigSettings(models.TransientModel):
  _inherit = 'res.config.settings'

  l10n_ec_withhold_start_date = fields.Date(
    related='company_id.l10n_ec_withhold_start_date',
    readonly=False,
  )
  l10n_ec_withhold_pending_mail_send = fields.Boolean(
    related='company_id.l10n_ec_withhold_pending_mail_send',
    readonly=False,
  )
  l10n_ec_withhold_pending_mail_tempalte_id = fields.Many2one(
    related='company_id.l10n_ec_withhold_pending_mail_tempalte_id',
    readonly=False,
  )
  l10n_ec_final_consumer_limit = fields.Float(
    string='Monto límite por facturación en ventas a Consumidor Final',
    config_parameter='l10n_ec_final_consumer_limit',
    default=50.0,
    readonly=False,
  )

  l10n_ec_advance_account_receivable_id = fields.Many2one(
    related='company_id.l10n_ec_advance_account_receivable_id',
    readonly=False,
  )

  l10n_ec_advance_account_foreign_receivable_id = fields.Many2one(
    related='company_id.l10n_ec_advance_account_foreign_receivable_id',
    readonly=False,
  )

  l10n_ec_advance_account_payable_id = fields.Many2one(
    related='company_id.l10n_ec_advance_account_payable_id',
    readonly=False,
  )

  l10n_ec_advance_account_foreign_payable_id = fields.Many2one(
    related='company_id.l10n_ec_advance_account_foreign_payable_id',
    readonly=False,
  )

  l10n_ec_advance_journal_receivable_id = fields.Many2one(
    related='company_id.l10n_ec_advance_journal_receivable_id',
    readonly=False,
  )

  l10n_ec_advance_journal_payable_id = fields.Many2one(
    related='company_id.l10n_ec_advance_journal_payable_id',
    readonly=False,
  )

  group_account_payment_advance = fields.Boolean(
    'Permitir Anticipos',
    implied_group='ek_l10n_ec.group_account_payment_advance',
  )
