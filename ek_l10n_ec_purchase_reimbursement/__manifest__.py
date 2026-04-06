# -*- coding: utf-8 -*-
{
  'name': 'Account Reimbursement for Purchase',
  'version': '17.0.0.0.3',
  'summary': """ Generates Reimbursement for Purchases with Validation """,
  'author': 'EkuaSoft Software Development Group Solution',
  'maintainer': 'Yordany Oliva Mateos',
  'category': 'Ekuasoft S.A/Accounting',
  'website': 'https://www.ekuasoft.com',
  'depends': ['base', 'purchase', 'account', 'ek_l10n_ec', 'ek_l10n_shipping_operations'],
  'data': [
    'wizard/ek_purchase_reimbursement_wizard.xml',
    'wizard/ek_account_move_reimbursement_wizard.xml',
    'wizard/change_journal_wizard.xml',
    'security/ir.model.access.csv',
    'views/account_move_views.xml',
    'views/account_reimbursement_document_views.xml',
    'views/res_configuration_settings_views.xml',
  ],
  'application': False,
  'installable': True,
  'auto_install': False,
  'license': 'OPL-1',
}
