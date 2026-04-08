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
    'name' : 'Ekuasoft Suggested Purchase History Master',
    'summary': """Modulo para usar histórico maestro de ventas en sugerido de compras""",
    'version' : '17.0.1.2',
    'author' : 'EkuaSoft Software Development Group Solution',
    'category': 'Inventory/Purchase',
    'complexity': 'normal',
    'license': 'OPL-1',
    'website': 'https://www.ekuasoft.com',
    'data': [
        'security/ir.model.access.csv',
        'security/ir_rule.xml',
        'views/suggested_purchases_history_master_view.xml'
    ],
    'depends' : [
        'base_suggested_purchase'
    ],
    'installable': True,
    'auto_install': False,
    'application': False,
}
