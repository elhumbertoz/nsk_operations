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
    'name' : 'Ekuasoft Purchase for Ecuadorian Localization',
    'version' : '17.0.1.3.0',
    'author' : 'EkuaSoft Software Development Group Solution',
    "maintainer": 'Yordany Oliva Mateos',
    'category': 'Ekuasoft S.A/Purchase Management',
    'complexity': 'normal',
    'license': 'OPL-1',
    'website': 'https://www.ekuasoft.com/',
    'data': [
        'views/purchase_order_view.xml',
        "views/res_partner_views.xml",
        "views/product_category_view.xml",
        "wizard/purchase_merge_views.xml",
        'views/res_config_settings_views.xml',
        'security/security.xml',
        'security/ir.model.access.csv'
    ],
    'depends': [
        'purchase',
        'purchase_stock',
        'base_tier_validation',
        'ek_l10n_ec'
    ],
    'installable': True,
    'auto_install': False
}