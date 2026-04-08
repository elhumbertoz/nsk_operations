{
  'name': 'Ekuasoft Shipping Operations Charging Regimenes',
  'version': '17.0.1.0.0',
  'author': 'EkuaSoft Software Development Group Solution',
  'maintainer': 'Yordany Oliva Mateos',
  'category': 'Ekuasoft S.A',
  'complexity': 'normal',
  'license': 'OPL-1',
  'website': 'https://ekuasoft.com',
  'data': [
    # 1. Datos base (necesarios antes que cualquier vista)
    'data/product_category.xml',
    'data/product_sequence.xml',
    'data/ek_type_request_data.xml',
    'data/mail_templates_regime_70.xml',
    # NOTA: Las etapas de Régimen 70 se gestionan desde Configuración → Tipos de Solicitud
    # 2. Seguridad (permisos y grupos)
    'security/ir.model.access.csv',
    'security/security.xml',
    # 3. Wizards (cargar ANTES de las vistas que los referencian)
    'wizard/ek_wizard_filter_regimen.xml',
    'wizard/ek_wizard_charging_data.xml',

    'wizard/ek_packages_goods_clear_wizard_view.xml',

    'wizard/ek_ship_assignment_wizard_view.xml',
    # 4. Vistas de modelos principales
    'views/ek_ship_registration_views.xml',
    'views/ek_boats_information_views.xml',
    'views/ek_type_request_views.xml',
    'views/views_ek_operation_request.xml',
    'views/ek_operation_request_kanban_view.xml',
    'views/views_regime_70_fields.xml',
    'views/res_config_settings_views.xml',
    'views/mail_template_views.xml',
    # 5. Reportes (al final porque pueden depender de otros elementos)
    'report/kardex_container.xml',
    'report/regime_70_reports.xml',
  ],
  'depends': [
    'ek_l10n_shipping_operations',
    'resource',
    'ek_l10n_ec_purchase_reimbursement',
    'sale',
    # 'nsk_llm',  # Descomentar cuando esté listo para usar IA
  ],
  'demo': [],
  'qweb': [],
  'images': [],
  'installable': True,
  'application': False,
  'auto_install': False,
}
