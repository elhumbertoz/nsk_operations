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
    'name' : 'Ekuasoft Base Suggested Purchase',
    'summary': """Modulo base para sugerido de compras""",
    'version' : '17.0.2.0',
    'author' : 'EkuaSoft Software Development Group Solution',
    'category': 'Inventory/Purchase',
    'complexity': 'normal',
    'license': 'OPL-1',
    'website': 'https://www.ekuasoft.com',
    'data': [
        'security/ir.model.access.csv',
        'security/ir_rule.xml',
        'wizard/add_purchase_order_line_view.xml',

        'views/ek_purchase_suggested_report_views.xml',
        'wizard/generate_purchase_sugget_view.xml',
        'views/ek_purchase_adjustment_factor_view.xml',
        'data/adjustment_factor_data.xml',
        'data/cron.xml'
    ],
    'depends' : [
        'base',
        'stock',
        'stock_account',
        'purchase',
        'purchase_stock',
        'sale_management',
        'ek_purchase_import_liquidation'
    ],
    'installable': True,
    'auto_install': False,
    'application': True,
}
