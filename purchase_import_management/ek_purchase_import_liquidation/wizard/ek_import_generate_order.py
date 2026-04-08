# -*- coding: utf-8 -*-

from odoo import api, fields, models
from odoo.tools.translate import _
from odoo.exceptions import ValidationError


class EkImportGenerateOrderLine(models.TransientModel):
    _name = "ek.import.generate.order.line"
    _description = "Importar Lineas de ordenes"

    line_id = fields.Many2one(
        string=_("Línea"),
        comodel_name="purchase.order.line",
        required=False,
    )
    product_qty = fields.Float(
        string=_("Cantidad pendiente"),
        related="line_id.product_qty",
    )
    product_qty_import = fields.Float(
        string=_("Cantidad a importar"),
        required=True,
        default=1,
    )
    purchase_order_id = fields.Many2one(
        string=_("Orden de compra"),
        comodel_name="purchase.order",
        related="line_id.order_id",
    )
    partner_id = fields.Many2one(
        string=_("Proveedor"),
        comodel_name="res.partner",
        required=False,
        related="line_id.partner_id",
    )
    order_id = fields.Many2one(
        string=_("Orden"),
        comodel_name="ek.import.generate.order",
        required=False,
    )
    weight = fields.Float(
        string=_("Peso unitario"),
        required=False,
        related="line_id.product_id.weight",
    )
    total_weight = fields.Float(
        string=_("Peso total"),
        required=False,
        compute="_compute_pending_import",
    )
    total_ctdad_pending_weight = fields.Float(
        string=_("Peso por importar"),
        required=False,
        compute="_compute_pending_import",
    )

    @api.depends("line_id", "product_qty_import")
    def _compute_pending_import(self):
        for rec in self:
            rec.update({
                'total_weight': rec.line_id.product_id.weight * rec.product_qty,
                'total_ctdad_pending_weight': rec.line_id.product_id.weight * rec.product_qty_import
            })


class EkImportGenerateOrder(models.TransientModel):
    """Asociar regalias a viaje"""
    _name = "ek.import.generate.order"
    _description = "Asociar lineas de órdenes de compra a importaciones"
    _save_info = []


    @api.model
    def default_get(self, fields):
        res = super(EkImportGenerateOrder, self).default_get(fields)
        active_ids = self.env.context.get('active_ids')
        collector = self.env['ek.import.generate.order.line']
        if active_ids:
            objects = self.env['purchase.order.line'].browse(active_ids).filtered(lambda x: x.state != 'cancel' and x.ctdad_pending > 0)
            if len(objects):
                lis = []
                for rec in objects:
                    lis.append({
                        'line_id': rec.id,
                        'product_qty_import': rec.ctdad_pending,
                        'product_qty': rec.ctdad_pending,
                        'purchase_order_id': rec.order_id.id,
                        'partner_id': rec.partner_id.id
                    })
                xyz = collector.create(lis)
                res.update({'collection_ids': xyz})
        return res

    collection_ids = fields.One2many(
        string=_("Líneas"),
        comodel_name="ek.import.generate.order.line",
        inverse_name="order_id",
    )
    liq_id = fields.Many2one(
        string=_("Liquidación"),
        comodel_name="ek.import.liquidation",
        required=True,
    )
    assigned_to_invoice = fields.Boolean(
        string=_("Asignar a factura"),
    )
    invoice_id = fields.Many2one(
        string=_("Factura"),
        comodel_name="account.move",
        required=False,
        domain=[('move_type', '=', 'in_invoice')],
    )

    @api.constrains('collection_ids')
    def _check_collection_ids(self):
        for rec in self:
            if len(rec.collection_ids) == 0:
                raise ValidationError(_("No se ha definido ninguna línea para importar."))

    def action_confirm(self):
        line_obj = self.env["ek.import.liquidation.line"]
        for rec in self:
            orders = [rec.liq_id.purchase_ids.ids]
            for line in rec.collection_ids:
                line_obj.create({
                    'purchase_line_id': line.line_id.id,
                    'order_id': rec.liq_id.id,
                    'product_qty': line.product_qty_import,
                    'name': line.line_id.name or line.line_id.product_id.name,
                    'product_id': line.line_id.product_id.id,
                    'date_planned': line.line_id.date_planned,
                    'product_uom': line.line_id.product_uom and line.line_id.product_uom.id or False,
                    'tariff_id': line.line_id.product_id.tariff_heading_id and line.line_id.product_id.tariff_heading_id.id or False,
                    'price_unit': line.line_id.price_unit,
                    'discount': line.line_id.discount or 0.00,
                    'account_analytic_id': line.line_id.account_analytic_id and line.line_id.account_analytic_id.id or False,
                    'invoice_id': rec.invoice_id and rec.invoice_id.id or False
                })
                if line.line_id.order_id.id != rec.liq_id.purchase_id.id and line.line_id.order_id.id not in orders:
                    orders.append(line.line_id.order_id.id)
