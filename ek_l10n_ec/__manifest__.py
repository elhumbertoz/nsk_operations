# -*- coding: utf-8 -*-
#
#    Sistema FINAMSYS
#    Copyright (C) 2016-Today Ekuasoft S.A All Rights Reserved
#    Ing. Yordany Oliva Mateos <yordanyoliva@ekuasoft.com>
#    Ing. Wendy Alvarez Chavez <wendyalvarez@ekuasoft.com>
#    EkuaSoft Software Development Group Solution
#    http://www.ekuasoft.com
#
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
{
    'name': 'Ekuasoft Ecuadorian Localization Base Module',
    'version': '17.0.3.5.8',
    'author': 'EkuaSoft Software Development Group Solution',
    "maintainer": 'Yordany Oliva Mateos',
    'category': 'Ekuasoft S.A/Accounting',
    'complexity': 'normal',
    'license': 'OPL-1',
    'website': 'https://www.ekuasoft.com/',
    "data": [
        "security/ir.model.access.csv",
        "views/main_menu_sri.xml",
        "security/account_move_security.xml",
        "wizards/account_move_reversal_view.xml",
        "wizards/update_journal_lock_dates_views.xml",
        "wizards/account_move_update_analytic_view.xml",
        "wizards/l10n_ec_wizard_account_withhold_view.xml",
        "wizards/invoice_merge_view.xml",
        "wizards/ats_wizard.xml",
        "wizards/dinardap_supercias_wizard.xml",
        "wizards/ek_account_invoice_for_payment_reconcile_view.xml",
        "wizards/account_payment_register_views.xml",
        "wizards/sri_cancellation_number_wizard_view.xml",
        "views/account_ats_sustento_view.xml",
        "views/account_move_view.xml",
        "views/account_journal_view.xml",
        "views/account_document_type_ats.xml",
        "views/l10n_latam_identification_type_view.xml",
        "views/res_config_settings_views.xml",
        "views/reimbursement_invoice_view.xml",
        "views/account_account_views.xml",
        "views/account_move_refund_reason_view.xml",
        "views/account_payment_term.xml",
        "views/account_payment_view.xml",
        "views/account_payment_method.xml",
        "views/account_payment_mode.xml",
        "views/res_partner_view.xml",
        "views/product_views.xml",
        "views/account_report_form.xml",
        "reports/ek_account_invoice.xml",
        "reports/ek_account_invoice_with_details.xml",
        "reports/ek_account_bank_statement_with_details.xml",
        "reports/voucher_report.xml",
        "reports/voucher_report_with_move.xml",
        "reports/move_report.xml",
        "reports/voucher_print_report.xml",
        "reports/account_partner_balance.xml",
        "reports/account_partner_check_receivable_balance.xml",
        "reports/report_pdf_export.xml",
        "data/account_ats_sustento.xml",
        "data/edi_document.xml",
        "data/account_move_refund_reason.xml",
        "data/l10n_latam_identification_type.xml",
        "data/account_payment_method_data.xml",
        "data/mail_template.xml",
        "data/cron.xml",
        "views/account_analytic_distribution_model_views.xml",
        "reports/header.xml",
    ],
    'depends': [
        'account',
        'account_payment',
        'report_xlsx_helper',
        'ek_l10n_ec_ote',
        'l10n_ec',
        'l10n_latam_invoice_document',
        'l10n_ec_edi',
        'l10n_ec_reports',
        'l10n_latam_check'
    ],
    # "assets": {
    #     "web.assets_backend": [
    #         "/ek_l10n_ec/static/src/styles.css"
    #     ],
    # },
    'installable': True,
    'auto_install': False,
    "pre_init_hook": "_pre_init_hook",
    'post_init_hook': '_post_install_hook_configure_ecuadorian_ekuasoft_data',
}
