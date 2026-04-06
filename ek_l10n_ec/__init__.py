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
from odoo import SUPERUSER_ID, api
from . import models
from . import wizards
from . import xlsx
from . import reports
from odoo.tools import column_exists, create_column

def _query_update_account(cr):
    query = """
        update account_account
        set analytic_policy = 'never'
        where reconcile = true
        """
    cr.execute(query)

def _query_update_document_type(cr):
    query = """
        update l10n_latam_document_type
        set required_tax = true
        where l10n_ec_check_format = true
        """
    cr.execute(query)

def _post_install_hook_configure_ecuadorian_ekuasoft_data(env):
    cr = env.cr
    # Force setup as l10n_ec_edi module was not installed at moment of creation of first company
    companies = env['res.company'].search([('account_fiscal_country_id.code', '=', 'EC')])

    env['account.chart.template']._l10n_ec_configure_ecuadorian_ekuasoft_journals(companies)
    env['account.chart.template']._l10n_ec_configure_l10n_ec_withhold_pending(companies)

    ##Requerir el uso de impuesto en los documentos con formato ecuatoriano
    _query_update_document_type(cr)

    ##No permitir que se puedan usar analiticas en las cuentas que tienen conciliación
    _query_update_account(cr)

def _pre_init_hook(env):
    if not column_exists(env.cr, "account_account", "analytic_policy"):
        create_column(env.cr, "account_account", "analytic_policy", "VARCHAR")
    if not column_exists(env.cr, "l10n_latam_document_type", "required_tax"):
        create_column(env.cr, "l10n_latam_document_type", "required_tax", "boolean")

