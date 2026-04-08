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

from odoo import api, fields, models , SUPERUSER_ID, _

# READONLY_STATES = {
#     'confirmed': [('readonly', True)],
#     'approved': [('readonly', True)],
#     'done': [('readonly', True)],
#     'purchase': [('readonly', True)]
# }


class PurchaseOrderLine(models.Model):
    _inherit = "purchase.order.line"

    @api.depends("order_id","order_id.is_import","product_id")
    def compute_is_import_field(self):
        for obj in self:
            if obj.order_id:
                obj.is_import = obj.order_id.is_import

    ctdad_imported = fields.Float(
        string=_("Ctdad. Importada"),
        required=False,
        readonly=True,
        compute="_compute_pending_import",
        store=True,
        help=_("Cantidad importada."),
    )
    ctdad_pending = fields.Float(
        string=_("Ctdad. Pendiente"),
        required=False,
        readonly=True,
        compute="_compute_pending_import",
        store=True,
        help=_("Cantidad pendiente de importar."),
    )
    ctdad_transit = fields.Float(
        string=_("Ctdad. Tránsito"),
        required=False,
        readonly=True,
        compute="_compute_pending_import",
        store=True,
        help=_("Cantidad en tránsito."),
    )
    liquidation_line_ids = fields.One2many(
        comodel_name="ek.import.liquidation.line",
        inverse_name="purchase_line_id",
        string="Importación",
        required=False,
    )
    is_import = fields.Boolean(
        string=_("Orden de Importación"),
        compute="compute_is_import_field",
        store=True,
    )
    weight = fields.Float(
        string=_("Peso unitario"),
        required=False,
        related="product_id.weight",
        store=True,
    )
    total_weight = fields.Float(
        string=_("Peso total"),
        required=False,
        store=True,
        compute="_compute_total_weight",
    )
    total_ctdad_pending_weight = fields.Float(
        string=_("Peso por importar"),
        required=False,
        store=True,
        compute="_compute_pending_import",
    )
    tariff_id = fields.Many2one(
        string=_("Partida arancelaria"),
        comodel_name="ek.tariff.heading",
        ondelete="restrict",
        domain=[('type', '<>', 'view')],
        related="product_id.tariff_heading_id",
    )
    ref_import = fields.Char(
        related="product_id.ref_import",
        required=False,
    )
    import_liquidation_id = fields.Many2one(
        string=_("Liquidación de importación"),
        comodel_name="ek.import.liquidation",
        compute="_compute_import_liquidation",
        required=False,
        readonly=True,
        store=True,
    )
    import_liquidation_arrival_date = fields.Date(
        string=_("Fecha de arribo (liquidación)"),
        compute="_compute_import_liquidation",
        required=False,
        readonly=True,
        store=True,
    )
    import_liquidation_incoterm_id = fields.Many2one(
        string=_("Incoterm (liquidación)"),
        comodel_name="account.incoterms",
        compute="_compute_import_liquidation",
        required=False,
        readonly=True,
        store=True,
    )

    @api.depends("product_id", "product_qty")
    def _compute_total_weight(self):
        for rec in self:
            rec.update({
                'total_weight': rec.product_id.weight * rec.product_qty
            })

    @api.model
    def _calc_line_base_price(self, line):
        res = super(PurchaseOrderLine, self)._calc_line_base_price(line)
        return res * (1 - line.discount / 100.0)

    @api.depends("is_import", "product_qty", "liquidation_line_ids", "liquidation_line_ids.state", "liquidation_line_ids.product_qty")
    def _compute_pending_import(self):
        for rec in self:
            if not rec.is_import:
                rec.update({
                    'ctdad_imported': 0,
                    'ctdad_transit': 0,
                    'ctdad_pending': 0,
                    'total_ctdad_pending_weight': 0
                })
            elif len(rec.liquidation_line_ids) == 0:
                rec.update({
                    'ctdad_imported': 0,
                    'ctdad_transit': 0,
                    'ctdad_pending': rec.product_qty,
                    'total_ctdad_pending_weight': rec.product_id.weight * rec.product_qty
                })
            else:
                imported = 0
                transit = 0
                for p in rec.liquidation_line_ids.filtered(lambda a: a.state not in ['cancel']):
                    if p.state in ['draft', 'confirmed']:
                        transit = p.product_qty
                    else:
                        imported = p.product_qty
                diff = rec.product_qty - (imported + transit)
                pending = diff > 0 and diff or 0
                rec.update({
                    'ctdad_imported': imported,
                    'ctdad_transit': transit,
                    'ctdad_pending': pending,
                    'total_ctdad_pending_weight': rec.product_id.weight * pending
                })

    @api.depends()
    def _compute_import_liquidation(self):
        for rec in self:
            import_liquidation = self.env["ek.import.liquidation"].search([
                ('state', 'not in', ['draft', 'cancel']),
                ('purchase_id', '=', rec.order_id.id),
            ], limit=1)
            if import_liquidation:
                rec.update({
                    'import_liquidation_id': import_liquidation.id,
                    'import_liquidation_arrival_date': import_liquidation.arrival_date,
                    'import_liquidation_incoterm_id': import_liquidation.incoterm_id.id,
                })


class PurchaseOrder(models.Model):
    _inherit = 'purchase.order'

    is_import = fields.Boolean(
        string=_("Orden de Importación"),
        # states=READONLY_STATES,  # TODO: Cambiar en vista
        help=_("Indica que esta orden de compra se realizará como importación desde el exterior."),
        tracking=True,
    )

    def button_approve_liquidation(self, force=False):
        self = self.filtered(lambda order: order._approval_allowed())
        self.write({'state': 'purchase', 'date_approve': fields.Datetime.now()})
        self.filtered(lambda p: p.company_id.po_lock == 'lock').write({'state': 'done'})
        return {}

    def button_approve(self, force=False):
        result = False
        for rec in self:
            if not rec.is_import:
                result = super(PurchaseOrder, self).button_approve(force=force)
            else:
                result = self.button_approve_liquidation(force=force)
        return result

    def action_invoice_create(self, cr, uid, ids, context=None):
        picking_id = False
        for order in self.browse(cr, uid, ids):
            if not order.is_import:
                return super(PurchaseOrder, self).action_invoice_create(cr, uid, ids, context=context)
        return picking_id

    @api.model
    def _prepare_inv_line(self, account_id, order_line):
        result = super(PurchaseOrder, self)._prepare_inv_line(account_id, order_line)
        result['discount'] = order_line.discount or 0.0
        # result['discount1'] = order_line.discount or 0.0
        return result

    def _prepare_order_line_move(self, cr, uid, order, order_line, picking_id, group_id, context=None):
        res = super(PurchaseOrder, self)._prepare_order_line_move(cr, uid, order, order_line, picking_id, group_id, context=context)
        for vals in res:
            vals['price_unit'] = (vals.get('price_unit', 0.0) * (1 - (order_line.discount / 100)))
        return res
