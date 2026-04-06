# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
{
    'name': 'Ekuasoft OTE for Ecuador',
    'version': '17.0.1.2.6',
    'author' : 'EkuaSoft Software Development Group Solution',
    'category': 'Ekuasoft S.A/Localization',
    'maintainer': 'Ekuasoft Group Solutions',
    'website': 'https://www.ekuasoft.com/',
    'license': 'OEEL-1',
    'depends': [
        'base', 'l10n_ec', "contacts", "sales_team",
        "base_geolocalize",
        "base_address_extended",
        "web_map",
        "knowledge",
        'partner_autocomplete'
    ],   
    'data': [
        'security/group_security_view.xml',
        'security/ir.model.access.csv',        
        'views/ek_res_city_view.xml',
        'views/res_company.xml',
        'views/res_partner_bank_views.xml',
        'views/account_country_aditionals_view.xml',
        'views/res_partner_advance_route_view.xml',
        'data/visit_frequency_data.xml',
        "data/res.country.state.csv",
        "data/ek.res.country.city.csv",
        "data/res_city_data.xml",
        "data/ek.res.country.canton.csv",
        "data/ek.res.region.csv",
    ],
    'installable': True,
    'auto_install': False,
    'application': False,
}
