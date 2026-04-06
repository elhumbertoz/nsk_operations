# -*- coding: utf-8 -*-

{
    'name': 'Custom Py3o',
    "summary": "Customizations for Custom Py3o",
    "author": "EkuaSoft Software Development Group Solution",
    'maintainer': 'Carlos Eduardo Guaranda',
    "website": "https://www.ekuasoft.com",
    "category": "Ekuasoft S.A",
    'version': '17.0.0.4',
    "license": "OPL-1",
    'depends': ['sign',
                'report_py3o',
                'base'
                ],
    'data': [
        'security/ir.model.access.csv',
        'security/security.xml',
        'views/ek_dynamic_signature.xml',
    ],
    'installable': True,
}
