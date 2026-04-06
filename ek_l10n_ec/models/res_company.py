# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models


class ResCompany(models.Model):
  _inherit = 'res.company'

  l10n_ec_withhold_start_date = fields.Date(
    string='Fecha de control',
    help='Fecha de inicio para el control automático de documentos sin retención. A partir de esta fecha el sistema '
    'controlará y alertará sobre todos los documentos de clientes que no posean retención cuando deben tenerla.',
  )
  l10n_ec_withhold_pending_mail_send = fields.Boolean(
    string='Enviar correos por retenciones pendientes',
    default=True,
    help='Si marca esta opción, el sistema revisará todos los documentos pendientes de retención y enviará un correo a los '
    'clientes correspondientes hasta que se cumplan 5 días o hasta que se registre la retención respectiva.',
  )
  l10n_ec_withhold_pending_mail_tempalte_id = fields.Many2one(
    string='Plantilla de envío de retenciones',
    comodel_name='mail.template',
    domain="[('model', '=', 'account.move')]",
    help='Esta será la plantilla del correo que se enviará al cliente cuando tenga una retención pendiente de emitir.',
  )

  l10n_ec_advance_account_receivable_id = fields.Many2one(
    comodel_name='account.account',
    string='Cuenta de Anticipos de Clientes',
    required=False,
  )

  l10n_ec_advance_account_foreign_receivable_id = fields.Many2one(
    comodel_name='account.account',
    string='Cuenta de Anticipos de Clientes del Exterior',
    required=False,
  )

  l10n_ec_advance_account_payable_id = fields.Many2one(
    comodel_name='account.account',
    string='Cuenta de Anticipos a Proveedores',
    required=False,
  )

  l10n_ec_advance_account_foreign_payable_id = fields.Many2one(
    comodel_name='account.account',
    string='Cuenta de Anticipos a Proveedores del Exterior',
    required=False,
  )

  l10n_ec_advance_journal_receivable_id = fields.Many2one(
    comodel_name='account.journal',
    string='Diario para Cruce de Anticipos de Clientes',
    domain=[('type', '=', 'general')],
    required=False,
  )

  l10n_ec_advance_journal_payable_id = fields.Many2one(
    comodel_name='account.journal',
    string='Diario para Cruce de Anticipos de Proveedores',
    domain=[('type', '=', 'general')],
    required=False,
  )
