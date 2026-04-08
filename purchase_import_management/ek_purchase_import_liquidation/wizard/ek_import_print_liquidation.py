# -*- coding: utf-8 -*-

from odoo import api, fields, models
from odoo.tools.translate import _
from odoo.exceptions import ValidationError


class EkImportPrintLiquidation(models.TransientModel):
    _name = "ek.import.print.liquidation.wizard"
    _description = "Consolidado por partidas"

    @api.depends("order_id")
    def _get_allow_product_domain(self):
        for rec in self:
            lines = rec.order_id.mapped('order_line').ids
            tariff_ids = rec.order_id.order_line.mapped('tariff_id').ids
            rec.allow_product_ids = lines
            rec.allow_tariff_ids = tariff_ids

    type = fields.Selection(
        string=_("Tipo de selección"),
        selection=[
            ("all", _("Todos los productos")),
            ("tariff", _("Partidas seleccionadas")),
            ("product", _("Productos seleccionados")),
        ],
        required=True,
        default="all",
    )
    order_id = fields.Many2one(
        string=_("Orden"),
        comodel_name="ek.import.liquidation",
        required=False,
    )
    allow_product_ids = fields.Many2many(
        string=_("Productos permitidos"),
        comodel_name="ek.import.liquidation.line",
        relation="ek_allow_import_liquidation_line_products_rel",
        column1="wizard_id",
        column2="line_id",
        compute="_get_allow_product_domain",
    )
    allow_tariff_ids = fields.Many2many(
        string=_("Partidas Permitidas"),
        comodel_name="ek.tariff.heading",
        relation="ek_allow_tariff_heading_products_rel",
        column1="wizard_id",
        column2="tariff_id",
        compute="_get_allow_product_domain",
    )
    select_product_ids = fields.Many2many(
        string=_("Productos seleccionado"),
        comodel_name="ek.import.liquidation.line",
        relation="ek_select_import_liquidation_line_products_rel",
        column1="wizard_id",
        column2="line_id",
    )
    select_tariff_ids = fields.Many2many(
        string=_("Partidas"),
        comodel_name="ek.tariff.heading",
        relation="ek_select_tariff_heading_products_rel",
        column1="wizard_id",
        column2="tariff_id",
    )
    include_cif = fields.Boolean(
        string=_("Mostrar CIF"),
        required=False,
        help=_("Esta opción permite mostrar los gastos de flete y seguro en el reporte."),
    )

    def get_line_by_tariff(self):
        rec = self.order_id
        lines = {}
        if self.type == 'product':
            _lines = rec.order_line.filtered(lambda a: a.id in self.select_product_ids.ids)
        else:
            _lines = rec.order_line.filtered(lambda a: a.tariff_id in self.select_tariff_ids)

        for line in _lines:
            key = line.tariff_id and line.tariff_id.code or 'NO DEFINIDA'
            if key not in lines:
                lines[key] = {
                    'line': [],
                    'product_qty': 0.00,
                    'freight': 0.00,
                    'fob': 0.00,
                    'insurance': 0.00,
                    'cif': 0.00,
                    'tariff_code': line.tariff_id and line.tariff_id.code or '0',
                    'tariff_name': line.tariff_id and line.tariff_id.name or 'NO DEFINIDA',
                }
            lines[key]['line'].append(line)
            lines[key]['product_qty'] += line.product_qty
            lines[key]['fob'] += line.price_subtotal
            lines[key]['freight'] += line.freight_subtotal
            lines[key]['insurance'] += line.insurance_subtotal
            lines[key]['cif'] += line.related_cif
        return dict(sorted(lines.items()))

    def action_confirm(self):
        self.ensure_one()
        if self.type == 'all':
            report_action = self.env.ref('ek_purchase_import_liquidation.action_report_consolidate_by_tariff').report_action(self.order_id)
        else:
            if self.type == 'product' and not len(self.select_product_ids):
                raise ValidationError("Debe seleccionar al menos una linea para exportar el reporte.")
            if self.type == 'tariff' and not len(self.select_tariff_ids):
                raise ValidationError("Debe seleccionar al menos una partida para exportar el reporte.")

            report = self.env.ref('ek_purchase_import_liquidation.action_report_consolidate_params_by_tariff')
            if self.include_cif:
                report.paperformat_id = self.env.ref('ek_purchase_import_liquidation.paperformat_consolidate_params').id
            report_action = report.report_action(self)
        report_action['close_on_report_download'] = True
        return report_action
