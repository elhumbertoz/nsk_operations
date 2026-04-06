# Copyright 2021 Akretion France (http://www.akretion.com/)
# @author: Alexis de Lattre <alexis.delattre@akretion.com>
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

{
    "name": "Base Type Generic Object",
    "version": "17.0.1.2.10",
    "category": "Generic",
    "license": "AGPL-3",
    "summary": "Add Date Range menu entry in Invoicing app",
    "author": "Ekuasoft S.A.",
    "maintainers": ["Yordany Oliva"],
    "website": "https://www.ekuasoft.com",
    "depends": ["base","resource", 'base_setup', 'utm','mail'],
    "data": [
        "security/ir.model.access.csv",
        "security/ek_l10n_type_object_security.xml",
        "data/ek_l10n_type_widget_mixin_data.xml",
        "data/ek_l10n_stage_data.xml",
        "wizard/ek_l10n_stages_delete_mixin_views.xml",
        "views/ek_l10n_type_model_mixin_views.xml",
        "views/ek_l10n_stages_mixin_views.xml",
        "views/ek_l10n_lab_form_views.xml",
        "views/ek_l10n_group_type_model_mixin_views.xml",
        "views/ir_menu_view.xml",
        "views/ek_l10n_type_field_mixin_views.xml"
    ],
    "installable": True,
    "application": True,
    "auto_install": False,
}
