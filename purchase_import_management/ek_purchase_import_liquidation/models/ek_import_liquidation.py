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

import time
from odoo.tools.float_utils import float_round as round
from odoo import api, fields, models
from odoo.tools.translate import _
from odoo.exceptions import UserError, ValidationError
from odoo.tools.float_utils import float_compare

# READONLY_STATES = {
#     'confirmed': [('readonly', True)],
#     'approved': [('readonly', True)],
#     'done': [('readonly', True)],
#     'cancel': [('readonly', True)]
# }

STATE_SELECTION = [
    ("draft", _("Borrador")),
    ("calculate", _("Calculada")),
    ("approved", _("Aprobada")),
    ("confirmed", _("Confirmada")),
    ("except_picking", _("Excepción de envío")),
    ("done", _("Realizado")),
    ("cancel", _("Cancelado"))
]


class EkImportLiquidation(models.Model):
    _name = "ek.import.liquidation"
    _description = "Liquidación de importación"
    _inherit = ["mail.thread", "mail.activity.mixin", "sequence.mixin"]
    _order = "date DESC"

    @api.depends("name", "partner_id","origin")
    def _compute_display_name(self):
        for rec in self:
            if rec.name and rec.partner_id and rec.origin:
                rec.display_name = "%s - %s - (%s)" % (rec.name, rec.partner_id.name, rec.origin)
            elif rec.name and rec.partner_id and not rec.origin:
                rec.display_name = "%s - %s" % (rec.name, rec.partner_id.name)
            else:
                super()._compute_display_name()

    def _get_orders_allow(self):
        for rec in self:
            domain = [('id', '!=', rec.purchase_id.id), ('is_import', '=', True)]
            if rec.type == 'liquidation':
                domain.extend([('state','=','purchase')])
            else:
                domain.extend([('state', 'in', ['draft', 'purchase'])])
            return [s.get('id', 0) for s in self.env['purchase.order'].search_read(domain, ['id'])]

    def _get_picking_in(self):
        type_obj = self.env['stock.picking.type']
        company_id = self.env.company.id
        types = type_obj.search([('code', '=', 'incoming'), ('company_id', '=', company_id)], limit =1)
        if not types:
            raise UserError(_("Asegúrese de tener al menos un tipo de picking entrante definido."))
        return types[0].id

    def _get_company(self):
        return self.env.company.id

    @api.depends('type', 'purchase_id', 'partner_id')
    def _get_allow_purchase_domain(self):
        for rec in self:
            rec.allow_purchase_orders = rec._get_orders_allow()

    name = fields.Char(
        string=_("Número"),
        required=True,
        readonly=False,
        # states=READONLY_STATES,  # TODO: Cambiar en vista; tiene readonly="1" en la vista
        default="/",
    )
    origin = fields.Char(
        string=_("Documento origen"),
        copy=False,
        help=_("Referencia del documento que generó la liquidación de importación."),
    )
    date = fields.Date(
        string=_("Fecha"),
        required=True,
        # states=READONLY_STATES,  # TODO: Cambiar en vista
        copy=False,
        default=time.strftime("%Y-%m-%d"),
    )
    shipment_date = fields.Date(
        string=_("Fecha de embarque"),
        required=False,
        # states=READONLY_STATES,  # TODO: Cambiar en vista
        copy=False,
        default=time.strftime("%Y-%m-%d"),
    )
    arrival_date = fields.Date(
        string=_("Fecha de arribo"),
        required=False,
        # states=READONLY_STATES,  # TODO: Cambiar en vista
        copy=False,
        default=time.strftime("%Y-%m-%d"),
    )
    date_approve = fields.Date(
        string=_("Fecha de aprobación"),
        readonly=True,
        copy=False,
        # states=READONLY_STATES,  # TODO: Cambiar en vista
        help=_("Fecha en que se ha aprobado la importación."),
    )
    cost_type = fields.Selection(
        string="Tipo de costeo",
        # states=READONLY_STATES,  # TODO: Cambiar en vista
        selection=[
            ("fob", _("Basado en Precios")),
            ("weight", _("Basado en Peso")),
            ("qty", _("Basado en Cantidad")),
        ],
        default="fob",
        required=False,
    )
    type_id = fields.Many2one(
        string=_("Tipo de importación"),
        comodel_name="ek.import.liquidation.type",
        required=False,
        # states=READONLY_STATES,  # TODO: Cambiar en vista
    )
    purchase_id = fields.Many2one(
        string=_("Orden de compra"),
        comodel_name="purchase.order",
        required=False,
        # states=READONLY_STATES, # TODO: Cambiar en vista
    )
    purchase_ids = fields.Many2many(
        string=_("Órdenes adicionales"),
        comodel_name="purchase.order",
        relation="purchase_order_import_adicional_rel",
        column1="liquidation_id",
        column2="order_id",
        required=False,
        # states=READONLY_STATES,  # TODO: Cambiar en vista
        help=_("Órdenes de compras adicionales."),
    )
    allow_purchase_orders = fields.Many2many(
        comodel_name="purchase.order",
        compute="_get_allow_purchase_domain",
    )
    country_id = fields.Many2one(
        string=_("País de embarque"),
        comodel_name="res.country",
        required=False,
    )
    partner_id = fields.Many2one(
        string=_("Proveedor"),
        comodel_name="res.partner",
        required=True,
        change_default=True,
        # states=READONLY_STATES,  # TODO: Cambiar en vista
    )
    location_id = fields.Many2one(
        string=_("Destino"),
        comodel_name="stock.location",
        domain=[("usage", "<>", "view")],
        required=True,
        # states=READONLY_STATES,  # TODO: Cambiar en vista
    )
    amount_total = fields.Float(
        string=_("Total de importación"),
        digits="Account",
        # states=READONLY_STATES,  # TODO: Cambiar en vista; tiene readonly="1" en la vista
    )
    amount_fob = fields.Float(
        string=_("Total FOB"),
        digits="Total FOB",
        readonly=True,
        compute="_compute_amount_fob",
        store=True,
        # states=READONLY_STATES,  # TODO: Cambiar en vista; tiene readonly="1" en la vista
    )
    total_weight = fields.Float(
        string=_("Peso total (Kg)"),
        digits="Product Unit of Measure",
        readonly=True,
        compute="_compute_total_weight",
        store=True,
        # states=READONLY_STATES,  # TODO: Cambiar en vista; tiene readonly="1" en la vista
    )
    total_qty = fields.Float(
        string=_("Cantidad total"),
        digits="Product Unit of Measure",
        readonly=True,
        compute="_compute_total_qty",
        store=True,
        # states=READONLY_STATES,  # TODO: Cambiar en vista; no está el campo en la vista
    )
    percent_pvp_mayor = fields.Float(
        string=_("Porcentaje PVP mayor"),
        default=1.2,
    )
    percent_pvp_minor = fields.Float(
        string=_("Porcentaje PVP menor"),
        default=1.5,
    )
    factor = fields.Float(
        string=_("Factor"),
        digits="Account",
        compute="_compute_factor",
        store=True,
        help=_("Porcentaje de incremento de la importación después de gastos e impuestos"),
        # states=READONLY_STATES,  # TODO: Cambiar en vista; tiene readonly="1" en la vista
    )
    state = fields.Selection(
        string=_("Estado"),
        selection=STATE_SELECTION,
        readonly=True,
        copy=False,
        # states=READONLY_STATES,  # TODO: Confirmar bien esto que es el estado y no debería ser manualmente modificable. Se elimina esto.
        default="draft"
    )
    validator = fields.Many2one(
        string=_("Validado por"),
        comodel_name="res.users",
        readonly=True,
        copy=False,
    )
    notes = fields.Text(
        string=_("Términos y condiciones"),
        # states=READONLY_STATES,  # TODO: Cambiar en vista
    )
    incoterm_id = fields.Many2one(
        string=_("Incoterm"),
        comodel_name="account.incoterms",
        # states=READONLY_STATES,  # TODO: Cambiar en vista
        help=_("Corresponden a una serie de términos comerciales predefinidos utilizados en transacciones internacionales."),
    )
    company_id = fields.Many2one(
        string=_("Compañía"),
        comodel_name="res.company",
        required=True,
        # states=READONLY_STATES,  # TODO: Cambiar en vista
        default=lambda self: self.env.company,
    )

    manual_share_import_cost = fields.Boolean(
        compute="_compute_manual_share_import_cost",
        readonly=False,
        store=True
    )

    #invoice_ids = fields.Many2many("account.invoice", relation="ek_import_liquidation_invoice_rel", column1="liquidation_id", column2="invoice", string="Facturas de Proveedor", domain="['|',('liq_purchase','=','in_invoice'),('type','=','in_invoice')]")

    invoice_ids = fields.One2many(
        string=_("Facturas de proveedor"),
        comodel_name="account.move",
        inverse_name="invoice_liquidation_id",
        required=False,
    )
    picking_type_id = fields.Many2one(
        string=_("Entregar a"),
        comodel_name="stock.picking.type",
        required=True,
        # states=READONLY_STATES,  # TODO: Cambiar en vista
        default=_get_picking_in,
        help=_("Esto determinará el tipo de operación del envío entrante"),
    )
    related_location_id = fields.Many2one(
        string=_("Ubicación relacionada"),
        comodel_name="stock.location",
        related="picking_type_id.default_location_dest_id",
        store=True,
    )
    related_usage = fields.Selection(
        related="location_id.usage",
        store=True,
    )
    # TODO: Confirmar uso de campo
    type = fields.Selection(
        string="Tipo",
        selection=[
            ("liquidation", _("Liquidación de Importación")),
            ("simulation", _("Simulación de Importación")),
        ],
        required=False,
    )
    picking_ids = fields.One2many(
        string=_("Selección de lista"),
        comodel_name="stock.picking",
        inverse_name="liquidation_id",
        required=False,
        compute="_get_picking_ids",
        help=_("Esta es la lista de recibos que se han generado para esta orden de compra."),
    )
    order_line = fields.One2many(
        string=_("Lineas de importación"),
        comodel_name="ek.import.liquidation.line",
        inverse_name="order_id",
        # states=READONLY_STATES,  # TODO: Cambiar en vista
        required=False,
    )
    breakdown_expenses_ids = fields.One2many(
        string=_("Gastos de importación"),
        comodel_name="ek.import.liquidation.breakdown.expenses",
        # states=READONLY_STATES,  # TODO: Cambiar en vista
        inverse_name="order_id",
        required=False,
    )
    related_documents_ids = fields.One2many(
        string=_("Documentos relacionados"),
        comodel_name="ek.import.liquidation.related.documents",
        inverse_name="order_id",
        # states=READONLY_STATES,  # TODO: Cambiar en vista
        required=False,
    )

    #remision_guide_ids = fields.Many2many("ek.remission.guides", relation="ek_import_liquidation_remision_guide_rel", column1="import_id", column2="remision_id", string="Guías de Remisión", help="")

    shipment_count = fields.Integer(
        string=_("Envíos entrantes"),
        compute="_count_all",
    )
    shipment_count_not_cancel = fields.Integer(
        string=_("Envíos entrantes no cancelados"),
        compute="_count_all",
    )

    # Puertos
    origin_port_id = fields.Many2one(
        string=_("Puerto de embarque"),
        comodel_name="ek.country.port",
        # states=READONLY_STATES,  # TODO: Cambiar en vista
        required=False,
    )
    destination_port_id = fields.Many2one(
        string=_("Puerto de llegada"),
        comodel_name="ek.country.port",
        # states=READONLY_STATES,  # TODO: Cambiar en vista
        required=False,
    )
    company_country_id = fields.Many2one(
        related="company_id.country_id",
        readonly=True,
    )

    # Campos para reportes
    approximate_expenses = fields.Float(
        string=_("Gastos aproximados"),
        required=False,
        help="Es usado para mostrar el gasto aproximado en el reporte consolidado cuando la liquidación no ha sido confirmada.")

    approximate_insurance_costs = fields.Float(
        string=_("% Gastos aproximados de seguro"),
        required=False,
        default=0.25,
        help=_("Es usado para mostrar el gasto aproximado de seguros en el reporte consolidado cuando la liquidación no ha sido confirmada."),
    )

    @api.depends("company_id","partner_id")
    def _compute_manual_share_import_cost(self):
        for obj in self:
            obj.manual_share_import_cost = obj.company_id.manual_share_import_cost  

    @api.depends("amount_total", "amount_fob")
    def _compute_factor(self):
        for obj in self:
            factor = 0
            if obj.amount_fob > 0:
                f = obj.amount_total / obj.amount_fob
                factor = (f - 1) * 100 if f >= 1 else f * 10
            obj.factor = factor

    @api.onchange("partner_id")
    def onchange_partner_id(self):
        if self.partner_id and self.partner_id.country_id:
            self.country_id = self.partner_id.country_id.id

    # @api.onchange("purchase_id", "purchase_ids")
    def onchange_purchase_id(self):
        for rec in self:
            lines = []
            rec.order_line.unlink()
            if rec.purchase_id:
                for line in rec.purchase_id.order_line.filtered(lambda a: a.ctdad_pending > 0):
                    lines.append((0, 0, {
                        'purchase_line_id': line.id,
                        'product_qty': line.ctdad_pending,
                        'date_planned': line.date_planned,
                        'product_weight': line.product_id.weight * line.ctdad_pending,
                        'product_uom': line.product_uom.id,
                        'product_id': line.product_id.id,
                        'price_unit': line.price_unit,
                        'last_price_unit': line.product_id.amount_fob or line.product_id.last_cost,
                        'discount': line.discount,
                        'name': line.name,
                        'state': 'draft',
                        'tariff_id': line.product_id.tariff_heading_id and line.product_id.tariff_heading_id.id or line.product_id.product_tmpl_id.tariff_heading_id.id,
                        'origin': 'auto'
                    }))
            if rec.purchase_ids:
                for purchase in rec.purchase_ids:
                    if rec.purchase_id and purchase.id == rec.purchase_id.id:
                        continue
                    for line in purchase.order_line.filtered(lambda a: a.ctdad_pending > 0):
                        lines.append((0, 0, {
                            'purchase_line_id': line.id,
                            'product_qty': line.ctdad_pending,
                            'date_planned': line.date_planned,
                            'product_weight': line.product_id.weight * line.ctdad_pending,
                            'product_uom': line.product_uom.id,
                            'product_id': line.product_id.id,
                            'price_unit': line.price_unit,
                            'last_price_unit': line.product_id.amount_fob or line.product_id.last_cost,
                            'discount': line.discount,
                            'name': line.name,
                            'state': 'draft',
                            'tariff_id': line.product_id.tariff_heading_id.id,
                            'origin': 'auto'
                        }))

            rec.order_line = lines

    def button_update(self):
        for rec in self:
            rec.onchange_purchase_id()
            rec._compute_manual_share_import_cost()

    @api.depends("state")
    def _count_all(self):
        for rec in self:
            not_cancel = 0
            shipment_count = 0
            if rec.state == 'done':
                query = """
                    SELECT picking_id, po.id, p.state
                    FROM stock_picking p, stock_move m, ek_import_liquidation_line pol, ek_import_liquidation po
                    WHERE po.id = %s
                    AND po.id = pol.order_id
                    AND pol.id = m.liquidation_line_id
                    AND m.picking_id = p.id
                    GROUP BY picking_id, po.id, p.state
                """
                self._cr.execute(query, (rec.id,))
                picks = self._cr.fetchall()
                shipment_count = len(picks)
                for pi in picks:
                    if pi[2] != 'cancel':
                        not_cancel += 1
            rec.shipment_count_not_cancel = not_cancel
            rec.shipment_count = shipment_count

    def _get_picking_ids(self):
        res = {}
        for po_id in self:
            res[po_id.id] = []
        query = """
            SELECT picking_id, po.id
            FROM stock_picking p, stock_move m, ek_import_liquidation_line pol, ek_import_liquidation po
            WHERE po.id in %s
            AND po.id = pol.order_id 
            AND pol.id = m.liquidation_line_id 
            AND m.picking_id = p.id
            GROUP BY picking_id, po.id
        """
        self._cr.execute(query, (tuple(self._ids),))
        picks = self._cr.fetchall()
        for pick_id, po_id in picks:
            res[po_id].append(pick_id)
        return res

    def action_cancel(self):
        for liq in self:
            picking_ids = liq._get_picking_ids().get(liq.id, [])
            pinkings = self.env['stock.picking'].sudo().browse(picking_ids)
            if pinkings.filtered(lambda m: m.state == 'done'):
                raise UserError(_(
                    "No es posible cancelar la importación %s debido a que ya se han recibido algunos bienes en el inventario."
                ) % liq.name)
            for picking in pinkings.filtered(lambda m: m.state not in ['done','cancel']):
                picking.action_cancel()
            liq.write({'state': 'cancel'})
            liq.order_line.write({'state': 'cancel'})
        return True

    def import_related_documents(self):
        related_docs = self.env['ek.import.liquidation.related.documents']
        invoice_exclude = []
        default_values = related_docs.default_get(related_docs.fields_get())
        operation_vals = []
        for liq in self:
            ids = liq.related_documents_ids.filtered(lambda d: d.invoice_id).mapped('invoice_id').mapped('id')
            invoice_exclude.extend(ids)
            invoice_exclude.extend(liq.invoice_ids.ids)

            moves_to_document = self.env['account.move'].search([
                ('id', 'not in', invoice_exclude),
                ('state', '=', 'posted'),
                ('move_type','=','in_invoice'),
                ('import_liquidation_id', '=', liq.id)
            ])

            for move in moves_to_document:
                dict_values = dict(default_values, **{
                    'invoice_id': move.id,
                    'type': False,
                    'type_doc': 'fiscal',
                    'amount': (move.amount_untaxed and abs(move.amount_untaxed) or abs(move.amount_total)),
                    'name': move.l10n_latam_document_number,
                    'date': move.invoice_date,
                    'partner_id': move.partner_id.id,
                    'apply_by_item': False,
                    'terms_id': move.terms_id.id,
                    'order_id': liq.id
                })
                operation_vals.append(dict_values)
        if operation_vals:
            related_docs.with_context(tracking__disable=True, validation_skip=True).create(operation_vals)
        return True

    def view_picking(self):
        cr = self._cr
        # mod_obj = self.pool.get('ir.model.data')
        # dummy, action_id = tuple(mod_obj.get_object_reference(cr, uid, 'stock', 'action_picking_tree'))
        # action = self.pool.get('ir.actions.act_window').read(cr, uid, action_id, context=context)
        action = self.env['ir.actions.act_window']._for_xml_id('stock.action_picking_tree_all')
        pick_ids = []
        query = """
            SELECT picking_id, po.id
            FROM stock_picking p, stock_move m, ek_import_liquidation_line pol, ek_import_liquidation po
            WHERE po.id in %s
            AND po.id = pol.order_id 
            AND pol.id = m.liquidation_line_id 
            AND m.picking_id = p.id
            GROUP BY picking_id, po.id
        """
        cr.execute(query, (tuple(self._ids),))
        picks = cr.fetchall()
        for pick_id, po_id in picks:
            pick_ids += [pick_id]

        # override the context to get rid of the default filtering on picking type
        action['context'] = {}
        # choose the view_mode accordingly
        if len(pick_ids) > 0:
            action['domain'] = "[('id', 'in', [" + ','.join(map(str, pick_ids)) + "])]"
        return action

    def test_moves_done(self, cr, uid, ids, context=None):
        for purchase in self.browse(cr, uid, ids, context=context):
            # for picking in purchase.picking_ids:
            #     if picking.state != 'done':
            #         return False
            if purchase.picking_ids.filtered(lambda p: p.state != 'done'):
                return False
        return True

    def test_moves_except(self, cr, uid, ids, context=None):
        at_least_one_canceled = False
        all_done_or_cancel = True
        for purchase in self.browse(cr, uid, ids, context=context):
            # for picking in purchase.picking_ids:
            #     if picking.state == 'cancel':
            #         at_least_one_canceled = True
            #     if picking.state not in ['done', 'cancel']:
            #         all_done_or_cancel = False
            if purchase.picking_ids.filtered(lambda p: p.state == 'cancel'):
                at_least_one_canceled = True
            if purchase.picking_ids.filtered(lambda p: p.state not in ['done', 'cancel']):
                all_done_or_cancel = False
        return at_least_one_canceled and all_done_or_cancel

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not 'name' in vals or not vals['name'] or vals['name'] == '/':
                vals['name'] = self.env['ir.sequence'].next_by_code('ek.import.liquidation') or '/'
        res_id = super(EkImportLiquidation, self).create(vals_list)
        return res_id

    @api.onchange('picking_type_id')
    def onchange_picking_type_id(self):
        for rec in self:
            # if rec.picking_type_id:
            #     picking_type = self.env["stock.picking.type"].browse(rec.picking_type_id.id)
            #     if picking_type.default_location_dest_id:
            #         rec.location_id = picking_type.default_location_dest_id.id
            #         rec.related_usage = picking_type.default_location_dest_id.usage
            #         rec.related_location_id = picking_type.default_location_dest_id.id
            if rec.picking_type_id and rec.picking_type_id.default_location_dest_id:
                rec.location_id = rec.picking_type_id.default_location_dest_id.id
                rec.related_usage = rec.picking_type_id.default_location_dest_id.usage
                rec.related_location_id = rec.picking_type_id.default_location_dest_id.id

    @api.onchange('location_id')
    def onchange_location_id(self):
        for rec in self:
            related_usage = False
            if rec.location_id:
                # related_usage = self.env['stock.location'].browse(rec.location_id.id).usage
                related_usage = rec.location_id.usage
            rec.related_usage = related_usage

    @api.onchange('incoterm_id')
    def onchange_incoterm_id(self):
        for rec in self:
            items = []
            for term in rec.incoterm_id.incoterms_terms_ids:
                items.append((0, 0, {
                    'terms_id': term.terms_id.id,
                    'amount': 0.00,
                    'is_required': term.is_required,
                    'manual': False
                }))
            rec.breakdown_expenses_ids = items

    def action_cancel_draft(self):
        for rec in self:
            rec.write({'state': 'draft'})
            rec._compute_manual_share_import_cost()
            rec.order_line.write({'state': 'draft'})

    def action_convert_liquidation(self):
        for rec in self:
            val = {'type': 'liquidation'}
            if rec.name == '/':
                val.update({'name': self.env['ir.sequence'].next_by_code('ek.import.liquidation') or '/'})
            rec.write(val)

    def purchase_confirm(self):
        for rec in self:
            rec.calculate_liq()
            rec.write({'state': 'approved', 'validator': self.env.user.id, 'date_approve': time.strftime('%Y-%m-%d')})
            rec.order_line.write({'state': 'confirmed'})

    @api.depends("order_line", "order_line.price_subtotal")
    def _compute_amount_fob(self):
        for obj in self:
            obj.amount_fob = sum(x.price_subtotal for x in obj.order_line)

    @api.depends("order_line", "order_line.product_weight")
    def _compute_total_weight(self):
        for obj in self:
            obj.total_weight = sum(x.product_weight for x in obj.order_line)

    @api.depends("order_line", "order_line.product_qty")
    def _compute_total_qty(self):
        for obj in self:
            obj.total_qty = sum(x.product_qty for x in obj.order_line)
    
    def calculate_liq(self):
        for rec in self:
            if rec.manual_share_import_cost:
                share_total = round(sum(rec.order_line.mapped('manual_share')),1)
                if share_total < 1 or share_total > 1:
                    raise UserError(_("La suma de los porcentajes de repartición debe ser 100"))

            breakdown_expenses_ids = []
            amount_total = 0
            # RECORRER EL DETALLE YA EXISTENTE
            for line_b in rec.breakdown_expenses_ids.filtered(lambda r: r.manual == True):
                filter_manf = list(filter(lambda x: x[2]['terms_id'] == line_b.terms_id.id, breakdown_expenses_ids))
                if len(filter_manf):
                    filter_manf[0][2]['amount'] = filter_manf[0][2]['amount'] + line_b.amount
                    if line_b.terms_id.is_considered_total:
                        amount_total+=line_b.amount
                else:
                    breakdown_expenses_ids.append((0, 0, {
                        'terms_id': line_b.terms_id.id,
                        'manual': True,
                        'amount': line_b.amount,
                        'type': line_b.terms_id.type
                    }))
                    if line_b.terms_id.is_considered_total:
                        amount_total += line_b.amount
            # RECORRER DOCUMENTOS RELACIONADOS
            for line_b in rec.related_documents_ids.filtered(lambda r: r.apply_by_item == False):
                filter_manf = list(filter(lambda x: x[2]['terms_id'] == line_b.terms_id.id, breakdown_expenses_ids))
                if len(filter_manf):
                    filter_manf[0][2]['amount'] = filter_manf[0][2]['amount'] + line_b.amount
                    if line_b.terms_id.is_considered_total:
                        amount_total += line_b.amount
                else:
                    breakdown_expenses_ids.append((0, 0, {
                        'terms_id': line_b.terms_id.id,
                        'manual': False,
                        'amount': line_b.amount,
                        'type': line_b.terms_id.type
                    }))
                    if line_b.terms_id.is_considered_total:
                        amount_total += line_b.amount

            # RECORRER DETALLE DE DOCUMENTOS RELACIONADOS
            for doc in rec.related_documents_ids.filtered(lambda r: r.apply_by_item == True):
                for line_b in doc.lines:
                    filter_manf = list(filter(lambda x: x[2]['terms_id'] == line_b.terms_id.id, breakdown_expenses_ids))
                    if len(filter_manf):
                        filter_manf[0][2]['amount'] = filter_manf[0][2]['amount'] + line_b.price_subtotal
                        if line_b.terms_id.is_considered_total:
                            amount_total += line_b.price_subtotal
                    else:
                        breakdown_expenses_ids.append((0, 0, {
                            'terms_id': line_b.terms_id.id,
                            'manual': False,
                            'amount': line_b.price_subtotal,
                            'type': line_b.terms_id.type
                        }))
                        if line_b.terms_id.is_considered_total:
                            amount_total += line_b.price_subtotal

            rec.order_line.compute_sheet()
            # RECORRER DETALLE DE DOCUMENTOS RELACIONADOS
            rec.order_line._compute_invoice_avg()
            # Revisando los valores calculados para identificar cuál aplica a los totales
            tmp_fob = 0
            for item in rec.order_line:
                tmp_fob += item.price_subtotal
                for line_b in item.tariff_line_ids.filtered(lambda r: r.terms_id):
                    filter_manf = list(filter(lambda x: x[2]['terms_id'] == line_b.terms_id.id, breakdown_expenses_ids))
                    if len(filter_manf):
                        filter_manf[0][2]['amount'] = filter_manf[0][2]['amount'] + line_b.amount
                        if line_b.terms_id.is_considered_total:
                            amount_total += line_b.amount
                    else:
                        breakdown_expenses_ids.append((0, 0, {
                            'terms_id': line_b.terms_id.id,
                            'manual':   False,
                            'amount':   line_b.amount,
                            'type': line_b.terms_id.type
                        }))
                        if line_b.terms_id.is_considered_total:
                            amount_total += line_b.amount
            rec.breakdown_expenses_ids.unlink()

            if round(tmp_fob, 2) != round(rec.amount_fob, 2):
                amount_total+=tmp_fob
                rec.write({
                    'breakdown_expenses_ids': breakdown_expenses_ids,
                    'state': 'calculate',
                    'amount_fob': tmp_fob,
                    'amount_total': amount_total
                })
            else:
                amount_total += rec.amount_fob
                rec.write({
                    'breakdown_expenses_ids': breakdown_expenses_ids,
                    'state': 'calculate',
                    'amount_total': amount_total
                })

    def _prepare_order_line_move(self,order, order_line, picking_id, group_id):
        product_uom = self.env['uom.uom']
        price_unit = order_line.unit_cost

        # if order_line.product_uom.id != order_line.product_id.uom_id.id:
        #    price_unit *= order_line.product_uom.factor / order_line.product_id.uom_id.factor

        res = []
        name = order_line.name or ''
        move_template = {
            'name': name,
            'product_id': order_line.product_id.id,
            'product_uom': order_line.product_uom.id,
            'date': order_line.date_planned or order.date,
            'date_deadline': order_line.date_planned,
            'location_id': order.partner_id.property_stock_supplier.id,
            'location_dest_id': order.location_id.id,
            'picking_id': picking_id.id,
            'partner_id': order.partner_id.id,
            'state': 'draft',
            'liquidation_line_id': order_line.id,
            'purchase_line_id': order_line.purchase_line_id.id,
            'company_id': order.company_id.id,
            'price_unit': price_unit,
            'picking_type_id': order.picking_type_id.id,
            'group_id': group_id.id,
            'origin': order.name,
            'route_ids': order.picking_type_id.warehouse_id and [(6, 0, [x.id for x in order.picking_type_id.warehouse_id.route_ids])] or [],
            'warehouse_id': order.picking_type_id.warehouse_id.id,
        }

        diff_quantity = order_line.product_qty
        for procurement in order_line.procurement_ids:
            procurement_qty = product_uom._compute_qty(procurement.product_uom.id, procurement.product_qty, to_uom_id=order_line.product_uom.id)
            tmp = move_template.copy()
            tmp.update({
                'product_uom_qty': min(procurement_qty, diff_quantity),
                # TODO: ¿Por qué a group_id se le asigna dos campos distintos? No encontré el campo group_id en el modelo procurement.group
                'group_id': procurement.group_id.id or group_id,
                'group_id': procurement.id,
                'propagate_cancel': procurement.rule_id.propagate,
            })
            diff_quantity -= min(procurement_qty, diff_quantity)
            res.append(tmp)
        if float_compare(diff_quantity, 0.0, precision_rounding=order_line.product_uom.rounding) > 0:
            move_template['product_uom_qty'] = diff_quantity
            res.append(move_template)
        return res

    def _create_stock_moves(self,order, order_lines, new_group, picking_id = False):
        stock_move =  self.env['stock.move']
        todo_moves = []
        for order_line in order_lines:
            if order_line.state == 'cancel':
                continue
            if not order_line.product_id:
                continue
            if order_line.product_id.type in ('product', 'consu'):
                for vals in self._prepare_order_line_move(order, order_line, picking_id, new_group):
                    move = stock_move.create(vals)
                    todo_moves.append(move)
        picking_id.action_confirm()
        # todo_moves = stock_move.action_confirm(todo_moves)
        # stock_move.force_assign(cr, uid, todo_moves)

    def action_picking_create(self):
        for order in self:
            new_group = self.env["procurement.group"].create({'name': order.name, 'partner_id': order.partner_id.id})
            picking_vals = {
                'picking_type_id': order.picking_type_id.id,
                'partner_id': order.partner_id.id,
                'group_id': new_group.id,
                'date': order.date,
                'origin': order.name,
                'location_dest_id': order.location_id.id,
                'liquidation_id': order.id,
                'location_id': order.partner_id.property_stock_supplier.id
                # 'move_type'
            }
            picking_id = self.env['stock.picking'].create(picking_vals)
            self._create_stock_moves(order, order.order_line, new_group, picking_id)

            # order.write({'state': 'done', 'order_line.state': 'done'})
            order.write({'state': 'done'})
            for line in order.order_line:
                line.action_done()
            return picking_id

    def get_line_by_tariff(self):
        for rec in self:
            lines = {}
            for line in rec.order_line:
                key = line.tariff_id and line.tariff_id.code or 'NO DEFINIDA'
                if key not in lines:
                    lines[key] = {
                        'line': [],
                        'product_qty': 0.00,
                        'fob': 0.00,
                        'tariff_code': line.tariff_id and line.tariff_id.code or '0',
                        'tariff_name': line.tariff_id and line.tariff_id.name or 'NO DEFINIDA',
                    }
                lines[key]['line'].append(line)
                lines[key]['product_qty'] += line.product_qty
                lines[key]['fob'] += line.price_subtotal
            if lines:
                for tariff_heading in lines.values():
                    tariff_heading.update({
                        'line': sorted(
                            tariff_heading.get('line'),
                            key=lambda x: x.product_id.default_code
                        )
                    })
            return dict(sorted(lines.items()))

    @api.constrains("order_line.manual_share","manual_share_import_cost")
    def _check_manual_share_import_cost(self):
        for rec in self:
            if rec.manual_share_import_cost and rec.state == 'draft':
                share = sum(rec.order_line.mapped('manual_share'))
                if share < 0 or share > 1:
                    raise ValidationError(_("El procentaje de repartición total del debe ser mayor o igual a 0 y menor o igual a 100."))
            


class EkImportLiquidationInvoice(models.Model):
    _name = "ek.import.liquidation.invoice"
    _description = "Facturas de importación"

    name = fields.Char(
        string=_("Número"),
    )
    date = fields.Date(
        string=_("Fecha"),
        required=False,
    )
    date_due = fields.Date(
        string=_("Fecha de vencimiento"),
        required=False,
    )
    reference = fields.Char(
        string=_("Referencia"),
        required=False,
    )
    partner_id = fields.Many2one(
        string="Proveedor",
        comodel_name="res.partner",
        required=False,
    )
    note = fields.Text(
        string=_("Notas"),
        required=False,
    )
    journal_id = fields.Many2one(
        string=_("Diario"),
        comodel_name="account.journal",
        required=False,
    )
    import_liquidation_id = fields.Many2one(
        string=_("Importación"),
        comodel_name="ek.import.liquidation",
        required=False,
    )
    import_line_ids = fields.One2many(
        string=_("Items"),
        comodel_name="ek.import.liquidation.line",
        inverse_name="invoice_id",
        required=False,
    )
    amount_total = fields.Float(
        string=_("Total"),
        required=False,
        digits="Total FOB",
        readonly=True,
        compute="compute_calculate_amount",
        store=True,
    )
    state = fields.Selection(
        string=_("Estado"),
        selection=[
            ("draft", _("Borrador")),
            ("confirm", _("Confirmado")),
            ("cancel", _("Cancelado"))
        ],
        required=False,
    )
    company_id = fields.Many2one(
        string=_("Compañía"),
        comodel_name="res.company",
        required=False,
        default=lambda self: self.env.company,
    )
    is_details = fields.Boolean(
        string=_("Asiento detallado"),
        help=_("Si se selecciona esta opción, en el asiento contable de la factura se realizará una linea por cada ítem."),
    )
    lines_count = fields.Integer(
        string=_("Líneas de factura"),
        compute="_count_all",
    )
    move_id = fields.Many2one(
        string=_("Asiento"),
        comodel_name="account.move",
        required=False,
        readonly=True,
    )
    payment_term_id = fields.Many2one(
        string="Plazo de pago de",
        comodel_name="account.payment.term",
    )

    def onchange_partner_id(self, partner_id):
        pterm = None
        if partner_id:
            pterm = self.env['res.partner'].browse(partner_id)
        return {'value': {'payment_term_id': pterm and pterm.property_supplier_payment_term.id or None}}

    def onchange_payment_term_date_invoice(self, payment_term_id, date):
        if not date:
            date = fields.Date.context_today(self)
        if not payment_term_id:
            # To make sure the invoice due date should contain due date which is
            # entered by user when there is no payment term defined
            return {'value': {'date_due': self.date_due or date}}
        pterm = self.env['account.payment.term'].browse(payment_term_id)
        pterm_list = pterm.compute(value=1, date_ref=date)[0]
        if pterm_list:
            return {'value': {'date_due': max(line[0] for line in pterm_list)}}
        else:
            raise UserError("El proveedor no tiene términos de pago.")
    
    @api.depends("import_line_ids")
    def _count_all(self):
        for rec in self:
            rec.lines_count = len(rec.import_line_ids)

    def view_liquidation_line(self, cr, uid, ids, context=None):
        if context is None:
            context = {}
        mod_obj = self.pool.get('ir.model.data')
        dummy, action_id = tuple(mod_obj.get_object_reference(cr, uid, 'ek_purchase_import_liquidation', 'import_liquidation_line_action'))
        action = self.pool.get('ir.actions.act_window').read(cr, uid, action_id, context=context)
        invoice = self.browse(cr, uid, ids, context=context)
        pick_ids = len(invoice.import_line_ids)> 0 and invoice.import_line_ids.ids or []

        # override the context to get rid of the default filtering on picking type
        action['context'] = {}
        # choose the view_mode accordingly
        if len(pick_ids) > 1:
            action['domain'] = "[('id', 'in', [" + ','.join(map(str, pick_ids)) + "])]"
        return action

    @api.depends("import_line_ids", "import_line_ids.price_subtotal")
    def compute_calculate_amount(self):
        for rec in self:
            if len(rec.import_line_ids):
                rec.amount_total = sum([l.price_subtotal for l in rec.import_line_ids])
            else:
                rec.amount_total = 0.00

    def action_confirm(self):
        for rec in self:
            # if len(rec.import_line_ids) == 0:
            if not rec.import_line_ids:
                raise UserError("La factura seleccionada no posee lineas de detalles de importación.")
            # TODO: No se hace nada con journal_id
            journal_id = rec.journal_id and rec.journal_id.id or False
            self.create_move(rec)
        return True

    def action_cancel_draft(self):
        """Método que se ejecuta cuando el registro ha sido anulado
        y el usuario decide volver al estado borrador.
        """
        self.write({'state': 'draft'})
        return True

    def action_cancel(self):
        for rec in self:
            if rec.move_id:
                if rec.move_id.state == 'posted':
                    raise UserError(_(
                        "No se permiten cancelar facturas con asientos contables publicados. Por favor, anule antes los correspondientes."
                    ))
                rec.move_id.unlink()
                for line in rec.import_line_ids:
                    line.write({'invoice_id': False})
            rec.write({'state': 'cancel', 'validator': False, 'date_approve': False})

    def create_move(self, rec):
        # TODO: No se usa move_line_pool
        move_line_pool = self.pool.get('account.move.line')
        account_move = self.env['account.move']

        xline = []

        ctx = dict(self._context)

        # TODO: No se usa nunca name
        name = rec.name
        period = False
        # TODO: No se usa nunca company
        company = rec.company_id.id

        if not period:
            period = 1 # self.env['account.period'].with_context(ctx).find(rec.date)[:1]
        journal = rec.journal_id.with_context(ctx)

        # TODO: Si period llega a ser igual a 1, éste no tiene state y dará error
        
        if not journal:
            raise UserError(_("No ha seleccionado un diario correcto."))

        narration = rec.note or "Factura No. %s, Importación %s" % (rec.name, rec.import_liquidation_id.name)

        total = 0
        product_account_id = False
        for line in rec.import_line_ids.filtered(lambda a: a.invoice_id and a.invoice_id.id == rec.id):
            total += line.price_subtotal
            account_id = line.product_id.property_account_expense and line.product_id.property_account_expense.id or False
            if not account_id:
                account_id = line.product_id.categ_id and line.product_id.categ_id.property_account_expense_categ.id or False
            product_account_id = account_id
            if rec.is_details:
                xline.append((0, 0, {
                    'name': "Factura No. %s, Importación %s" % (rec.name, rec.import_liquidation_id.name),
                    'product_id': line.product_id.id,
                    'debit': line.price_subtotal,
                    'account_id': account_id,
                    'credit': 0.00,
                    'ref': rec.name,
                    'partner_id': rec.partner_id.id,
                    'date_maturity': rec.date_due
                }))
        account_id = rec.partner_id.property_account_payable and rec.partner_id.property_account_payable.id or False
        if not rec.is_details:
            xline.append((0, 0, {
                'name': "Factura No. %s, Importación %s" % (rec.name, rec.import_liquidation_id.name),
                'debit': total,
                'account_id': product_account_id,
                'credit': 0.00,
                'ref': narration,
                'partner_id': rec.partner_id.id,
                'date_maturity': rec.date_due
            }))
        xline.append((0, 0, {
            'name': "Factura No. %s, Importación %s" % (rec.name, rec.import_liquidation_id.name),
            'credit': total,
            'debit': 0.00,
            'account_id': account_id,
            'ref': narration,
            'partner_id': rec.partner_id.id,
            'date_maturity': rec.date_due
        }))
        move_vals = {
            'ref': "Factura No. %s, Importación %s" % (rec.name, rec.import_liquidation_id.name),
            'line_id': xline,
            'journal_id': rec.journal_id.id,
            'date': rec.date,
            'narration': narration

        }
        move = account_move.with_context(ctx).create(move_vals)
        rec.write({'move_id': move.id, 'state': 'confirm'})
        if journal.entry_posted:
            pass
            # move.post()


class EkImportLiquidationLine(models.Model):
    _name = "ek.import.liquidation.line"
    _description = "Lineas de liquidación de importación"

    origin = fields.Selection(
        string=_("Origen"),
        selection=[
            ("manual", _("Manual")),
            ("auto", _("Automático")),
        ],
        required=False,
        default="manual",
    )
    name = fields.Text(
        string=_("Descripción"),
        required=True,
    )
    product_qty = fields.Float(
        string=_("Cantidad"),
        digits="Product Unit of Measure",
        required=True,
        default=1,
    )
    product_weight = fields.Float(
        string="Peso (Kg)",
        required=False,
        default=0.00,
    )
    date_planned = fields.Datetime(
        string=_("Fecha planificada"),
        required=True,
        default=lambda self: time.strftime("%Y-%m-%d"),
        help=_("Fecha en la que se estima llegará la mercadería"),
    )
    product_uom = fields.Many2one(
        string=_("U/M"),
        comodel_name="uom.uom",
        required=True,
        help=_("Unidad de medida."),
    )
    product_id = fields.Many2one(
        string=_("Producto"),
        comodel_name="product.product",
        domain=[('purchase_ok', '=', True)],
        change_default=True,
        required=True,
    )
    tariff_id = fields.Many2one(
        string=_("Partida Arancelaria"),
        comodel_name="ek.tariff.heading",
        ondelete="restrict",
        domain=[('type', '<>', 'view')]
    )
    ref_import = fields.Char(
        related="product_id.ref_import",
        required=False,
    )
    adv_manual = fields.Float(
        string=_("% Ad valorem manual"),
        required=False,
        default=-1,
        help=_("Porcentaje manual de ad valorem según el convenio aplicado."),
    )
    last_price_unit = fields.Float(
        string=_("FOB Anterior"),
        required=True,
        digits="FOB",
    )
    price_unit = fields.Float(
        string=_("FOB"),
        required=True,
        digits="FOB",
    )
    diff_price_unit = fields.Float(
        string=_("Variación (FOB)"),
        required=True,
        digits="FOB",
        compute="_compute_variation_price",
    )

    percent_diff_price_unit = fields.Float(
        string=_("% Variación (FOB)"),
        required=True,
        digits="FOB",
        compute="_compute_variation_price",
    )
    discount = fields.Float(
        string=_("% Descuento"),
        digits="Discount",
        help=_("Porcentaje de descuento.")
    )
    price_subtotal = fields.Float(
        string=_("Total FOB"),
        digits="Total FOB",
        compute="_amount_line",
        store=True,
    )
    tariff_subtotal = fields.Float(
        string=_("Tributos"),
        digits="Importation Tributes",
        compute="_tariff_subtotal",
        store=True,
    )
    
    freight_subtotal = fields.Float(
        string=_("Flete"),
        digits="Importation Others",
        compute="_amount_general_subtotal",
        store=True,
    )
    freight_provider_assumed_subtotal = fields.Float(
        string=_("Flete asumido"),
        digits="Importation Others",
        compute="_amount_general_subtotal",
        store=True,
        help=_("Total de flete asumido por el proveedor"),
    )
    insurance_subtotal = fields.Float(
        string=_("Seguro"),
        digits="Importation Others",
        compute="_amount_general_subtotal",
        store=True,
    )
    expenses_abroad = fields.Float(
        string=_("Gastos Exteriores"),
        digits="Importation Others",
        compute="_amount_general_subtotal",
        store=True,
        help=_("Gastos del exterior que no afectan el costo. Se utilizan solo para calcular impuestos de aduana."),
    )
    expenses_subtotal = fields.Float(
        string=_("Gastos"),
        digits="Import Expenses",
        compute="_amount_general_subtotal",
        store=True,
    )
    share = fields.Float(
        string=_("% REP"),
        digits="Importation Factor",
        compute="_amount_line_share",
        store=True,
        help=_("Porcentaje de representación es el impacto que tiene cada rubro sobre el total FOB."),
    )
    manual_share = fields.Float(
        string=_("% REP"),
        digits="Importation Factor",
        help=_("Porcentaje de representación manual es el impacto que tiene cada rubro sobre el total FOB."),
    )
    manual_share_import_cost = fields.Boolean(
        related="order_id.manual_share_import_cost",
        readonly=False
    )
    
    amount_total = fields.Float(
        string=_("Total costo"),
        digits="Total Costs of Import",
        compute="_amount_general_total",
        store=True,
    )
    factor = fields.Float(
        string=_("Factor"),
        compute="_amount_general_total",
        store=True,
        help=_("Porcentaje de incremento de la importación después de gastos e impuestos."),
    )
    unit_cost = fields.Float(
        string=_("Costo unit."),
        digits="Importation Costs",
        compute="_amount_general_total",
        store=True,
        help=_("Costo unitario"),
    )
    order_id = fields.Many2one(
        string=_("Importación"),
        comodel_name="ek.import.liquidation",
        ondelete="cascade",
    )
    company_id = fields.Many2one(
        string=_("Compañía"),
        comodel_name="res.company",
        related="order_id.company_id",
        store=True,
    )
    account_analytic_id = fields.Many2one(
        string=_("Cuenta Analítica"),
        comodel_name="account.analytic.account",
    )
    date_order = fields.Date(
        string=_("Fecha"),
        related="order_id.date",
        readonly=True,
    )
    state = fields.Selection(
        string=_("Estado"),
        selection=[
            ("draft", _("Borrador")),
            ("confirmed", _("Confirmado")),
            ("done", _("Realizado")),
            ("cancel", _("Cancelado"))
        ],
        required=True,
        readonly=True,
        copy=False,
        default="draft",
    )
    partner_id = fields.Many2one(
        string=_("Proveedor"),
        comodel_name="res.partner",
        related="order_id.partner_id",
        readonly=True,
        store=True,
    )
    tariff_line_ids = fields.One2many(
        string=_("Reglas"),
        comodel_name="ek.tariff.rule.line",
        inverse_name="line_liquidation_id",
        required=False,
    )
    procurement_ids = fields.One2many(
        string=_("Órdenes asociadas"),
        comodel_name="procurement.group",
        inverse_name="liquidation_line_id",
    )
    invoice_id = fields.Many2one(
        string=_("Factura"),
        comodel_name="account.move",
        required=False,
    )
    purchase_line_id = fields.Many2one(
        string=_("Línea de orden de compra"),
        comodel_name="purchase.order.line",
    )
    # Cálculos adicionales
    related_fodinfa = fields.Float(
        string=_("Valor FODINFA"),
        required=False,
        compute="_calculate_related_arancel",
    )  # FODINFA
    related_advalorem = fields.Float(
        string=_("Valor ADVALOREM"),
        required=False,
        compute="_calculate_related_arancel",
    )  # FODINFA

    related_stock = fields.Float(
        string=_("Disponible"),
        required=False,
        compute="_calculate_stock",
    )  # FODINFA

    related_cif = fields.Float(
        string=_("Valor CIF"),
        required=False,
        compute="_calculate_related_arancel",
    )  # CIF
    related_unitary_cif = fields.Float(
        string=_("Costo unitario CIF"),
        required=False,
        compute="_calculate_related_arancel",
    )  # CIF Unitario
    pvp_mayor = fields.Float(
        string=_("PVP por mayor INC. IVA"),
        required=False,
        help=_("Precio de Venta incluido IVA."),
    )
    pvp_minor = fields.Float(
        string=_("PVP por Menor"),  # TODO: Este precio, ¿no incluye IVA así como el anterior?
        required=False,
        compute="_amount_pvp",
        help=_("Precio de Venta al por menor"),
    )
    pvp_public = fields.Float(
        string=_("PVP Sugerido"),
        required=False,
        compute="_calculate_related_arancel",
        help=_("Precio de Venta Sugerido al publico"),
    )
    allow_certificate_origin = fields.Boolean(
        string=_("¿Certificado de origen?"),
        required=False,
        help=_("Indica si los calculos están condicionados por el certificado de origen de los productos."),
    )
    forecasted_issue = fields.Boolean(
        compute="_compute_forecasted_issue",
    )
    liquidation_incoterm_id = fields.Many2one(
        string=_("Incoterm de importación"),
        related="order_id.incoterm_id",
        store=True,
    )
    liquidation_arrival_date = fields.Date(
        string=_("Fecha de arribo de importación"),
        related="order_id.arrival_date",
        store=True,
    )

    pm_amount = fields.Float(
        string=_("Promedio Mensual de Venta"),
        required=False, compute="_compute_invoice_avg")

    tvpm_amount = fields.Float(
        string=_("Tiempo de Venta Promedio del mes"),
        compute="_compute_invoice_avg",
        required=False)

    vum_amount = fields.Float(
        string=_("Venta de Unidades en el mes"),
        compute="_compute_invoice_avg",
        required=False)

    pr_amount = fields.Float(
        string=_("Precio del Mercado"),
        compute="_compute_invoice_avg",
        required=False)

    dif_gst_amount = fields.Float(
        string=_("CIF/Precio del Mercado"),
        compute="_compute_invoice_avg",
        required=False)

    @api.constrains("manual_share")
    def _check_manual_share_import_cost(self):
        for rec in self:
            if rec.manual_share_import_cost:
                share = rec.manual_share
                if share < 0 or share > 1:
                    raise ValidationError(_("El procentaje de repartición debe ser mayor o igual a 0 y menor o igual a 100."))
            
    @api.depends(
        'order_id',
        'order_id.date',
        'product_id'
    )
    def _compute_invoice_avg(self):
        AccountInvoiceReport = self.env['account.invoice.report']
        order = self.mapped("order_id")
        company = self.env.company
        number_of_month_for_pm = -3
        result = {}
        result_month = {}

        if order:
            if len(order) == 1:
                company = order.company_id
                number_of_month_for_pm = company.number_of_month_for_pm * -1
            else:
                order = order[0]
                company = order.company_id
                number_of_month_for_pm = company.number_of_month_for_pm * -1

            date_end = fields.Date.add(fields.Date.start_of(order.date, "month"), days=-1)
            date_start = fields.Date.add(date_end, months=number_of_month_for_pm)

            invoice_totals = AccountInvoiceReport.read_group(
                [
                    ('product_id','in', self.mapped("product_id").ids),
                    ('state', '=', 'posted'),
                    ('move_type', 'in', ['out_invoice','out_refund']),
                    ('company_id', '=', company.id),
                    ('invoice_date', '>=', date_start),
                    ('invoice_date', '<=', date_end)
                ],
                fields=['quantity'],
                groupby=['product_id']
            )


            result = {l['product_id'][0]: l['quantity'] for l in invoice_totals}

            invoice_month_totals = AccountInvoiceReport.read_group(
                [
                    ('product_id', 'in', self.mapped("product_id").ids),
                    ('state', '=', 'posted'),
                    ('move_type', 'in', ['out_invoice', 'out_refund']),
                    ('company_id', '=', company.id),
                    ('invoice_date', '>=', fields.Date.start_of(order.date,"month")),
                    ('invoice_date', '<=', fields.Date.end_of(order.date,"month"))
                ],
                fields=['quantity'],
                groupby=['product_id']
            )

            result_month = {l['product_id'][0]: l['quantity'] for l in invoice_month_totals}

        for rec in self:
            pm_amount = 0
            tvpm_amount = 0
            vum_amount = 0
            dif_gst_amount = 0
            pr_amount = 0
            if rec.product_id:
                pm_amount = result.get(rec.product_id.id,0) / (abs(number_of_month_for_pm) or 1)
                tvpm_amount = rec.product_id.qty_available / (pm_amount or 1)
                vum_amount = result_month.get(rec.product_id.id,0)
                pr_amount = rec.product_id.get_market_price(order.date)
                dif_gst_amount = ((rec.unit_cost / (pr_amount or 1))-1)*-1

            rec.pm_amount = pm_amount
            rec.pr_amount = pr_amount
            rec.tvpm_amount = tvpm_amount
            rec.vum_amount = vum_amount
            rec.dif_gst_amount = dif_gst_amount


    @api.depends("last_price_unit", "price_unit")
    def _compute_variation_price(self):
        for line in self:
            dif = line.price_unit - line.last_price_unit
            line.diff_price_unit = dif
            sign = line.last_price_unit < line.price_unit and -1 or 1
            line.percent_diff_price_unit = (1 - (line.last_price_unit / (line.price_unit or 1)))
            

    @api.depends("product_qty", "date_planned")
    def _compute_forecasted_issue(self):
        for line in self:
            warehouse = line.order_id.picking_type_id.warehouse_id
            line.forecasted_issue = False
            if line.product_id:
                virtual_available = line.product_id.with_context(warehouse=warehouse.id, to_date=line.date_planned).virtual_available
                if line.state == 'draft':
                    virtual_available += line.product_qty
                if virtual_available < 0:
                    line.forecasted_issue = True

    # _sql_constraints = [
    #     ('discount_limit', 'CHECK (discount <= 100.0)',
    #      'El descuento debe ser inferior al 100%.'),
    # ]

    @api.constrains()
    def _check_discount_limit(self):
        for rec in self:
            if rec.discount > 100:
                raise ValidationError(_("El descuento debe ser menor o igual al 100%."))

    def action_product_forecast_report(self):
        self.ensure_one()
        action = self.product_id.action_product_forecast_report()
        action['context'] = {
            'active_id': self.product_id.id,
            'active_model': 'product.product',
            'move_to_match_ids': self.purchase_line_id.move_ids.filtered(lambda m: m.product_id == self.product_id).ids,
            'purchase_line_to_match_id': self.purchase_line_id.id,
        }
        warehouse = self.order_id.picking_type_id.warehouse_id
        if warehouse:
            action['context']['warehouse'] = warehouse.id
        return action

    @api.model
    def action_update_price(self):
        for rec in self:
            rec.product_id.write({'list_price': rec.pvp_public})

    def change_product_price(self):
        for rec in self:
            if rec.state in ['confirmed','done']:
                rec.product_id.write({'list_price': rec.pvp_mayor})

    @api.depends("pvp_mayor")
    def _amount_pvp(self):
        for obj in self:
            tax = 1.12
            # obj.pvp_mayor = ((obj.unit_cost * obj.order_id.percent_pvp_mayor) * tax)
            obj.pvp_minor = round((((obj.pvp_mayor / tax) * obj.order_id.percent_pvp_minor) * tax), 0)
            # REDONDEAR((((M6/1,12)*1,5)*1,12);0)

    @api.depends("tariff_line_ids")
    def _calculate_related_arancel(self):
        for obj in self:
            FODI = obj.tariff_line_ids.filtered(lambda a: a.code == 'FODINFA')
            related_fodinfa = len(FODI) > 0 and FODI[0].amount or 0.00
            ADVA = obj.tariff_line_ids.filtered(lambda a: a.code in ['ADV'])
            related_advalorem = len(ADVA) > 0 and ADVA[0].amount or 0.00
            PVP = obj.tariff_line_ids.filtered(lambda a: a.code == 'PVP')
            pvp_public = len(PVP) > 0 and PVP[0].amount or 0.00
            CIF = obj.tariff_line_ids.filtered(lambda a: a.code == 'CIF')
            related_cif = len(CIF) > 0 and CIF[0].amount or 0.00
            obj.update({
                'related_unitary_cif': related_cif / (obj.product_qty or 1),
                'related_cif': related_cif,
                'pvp_public': pvp_public,
                'related_advalorem': related_advalorem,
                'related_fodinfa': related_fodinfa
            })
    @api.depends("product_id")
    def _calculate_stock(self):
        for rec in self:
            rec.related_stock = rec.product_id and rec.product_id.qty_available or 0


    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if 'origin' in vals and vals['origin'] == 'manual':
                raise UserError(_(
                    "Línea [%s] incorrecta. No se permite añadir una línea que no tenga como origen una orden de compra."
                ) % vals['name'])
        res_id = super(EkImportLiquidationLine, self).create(vals_list)
        return res_id

    def get_calculation_lines(self, liquidation_line):
        def _sum_salary_rule_category(localdict, category, amount):
            if category.parent_id:
                localdict = _sum_salary_rule_category(localdict, category.parent_id, amount)
            if category.code in localdict['categories'].dict:
                amount += localdict['categories'].dict[category.code]
            localdict['categories'].dict[category.code] = amount
            return localdict

        class BrowsableObject(object):
            def __init__(self, pool, cr, uid, tariff_id, dict):
                self.pool = pool
                self.cr = cr
                self.uid = uid
                self.tariff_id = tariff_id
                self.dict = dict

            def __getattr__(self, attr):
                return attr in self.dict and self.dict.__getitem__(attr) or 0.0

        result_dict = {}
        rules = {}
        categories_dict = {}
        blacklist = []
        liquidation_line_obj = self.env['ek.import.liquidation.line']
        obj_rule = self.env['ek.tariff.rule']
        obj_tariff_heading = self.env['ek.tariff.heading']
        cr = self._cr
        uid = self._uid
        context = self._context
        liquidation_l = liquidation_line_obj.browse(liquidation_line)
        rules_obj = BrowsableObject(self.pool, cr, uid, liquidation_l.tariff_id.id, rules)
        categories_obj = BrowsableObject(self.pool, cr, uid, liquidation_l.tariff_id.id, categories_dict)
        baselocaldict = {'categories': categories_obj,'rules': rules_obj, 'line_obj': liquidation_l}
        line = liquidation_l
        if line:
            rule_ids = obj_tariff_heading.browse(line.tariff_id.id).tariff_rule_ids
            localdict = dict(baselocaldict, line=line, tariff=line.tariff_id)
            for rule in rule_ids:
                key = rule.code + '-' + str(line.id)
                localdict['result'] = None
                localdict['result_qty'] = 1.0
                localdict['result_rate'] = 100
                # check if the rule can be applied
                if rule.id not in blacklist and rule.satisfy_condition(localdict):
                    # compute the amount of the rule
                    amount, qty, rate = rule.compute_rule(localdict)
                    # check if there is already a rule computed with that code
                    previous_amount = rule.code in localdict and localdict[rule.code] or 0.0
                    # set/overwrite the amount computed for this rule in the localdict
                    tot_rule = amount * qty * rate / 100.0
                    localdict[rule.code] = tot_rule
                    rules[rule.code] = rule
                    # sum the amount for its salary category
                    localdict = _sum_salary_rule_category(localdict, rule.category_id, tot_rule - previous_amount)
                    # create/overwrite the rule in the temporary results
                    if amount == 0:
                        continue
                    result_dict[key] = {
                        'rule_id': rule.id,
                        'line_liquidation_id': line.id,
                        'name': rule.name,
                        'code': rule.code,
                        'param': rule.param,
                        'not_cost_tariff': rule.not_cost_tariff,
                        'product_field_id': rule.product_field_id.id,
                        'terms_id': rule.terms_id.id,
                        'category_id': rule.category_id.id,
                        'sequence': rule.sequence,
                        'condition_select': rule.condition_select,
                        'condition_python': rule.condition_python,
                        'condition_range': rule.condition_range,
                        'condition_range_min': rule.condition_range_min,
                        'condition_range_max': rule.condition_range_max,
                        'amount_select': rule.amount_select,
                        'amount_fix': rule.amount_fix,
                        'amount_python_compute': rule.amount_python_compute,
                        'amount_percentage': rule.amount_percentage,
                        'amount_percentage_base': rule.amount_percentage_base,
                        'amount': amount,
                        'quantity': qty,
                    }
        result = [value for code, value in result_dict.items()]
        return result

    def compute_sheet(self):
        slip_line_pool = self.pool.get('ek.tariff.rule')
        slip_line_employee_pool = self.pool.get('ek.tariff.rule.line')

        contract_ids = []
        for rec in self:
            
            rec.tariff_line_ids.unlink()
            lines = [(0, 0, line) for line in self.get_calculation_lines(rec.id)]
            # self.pool.get('ek.import.liquidation.line').get_calculation_lines(self._cr, self._uid, rec.id, context=self._context)]
            rec.write({'tariff_line_ids': lines})
        return True

    def _calc_line_base_price(self, line):
        """Return the base price of the line to be used for tax calculation.

        This function can be extended by other modules to modify this base
        price (adding a discount, for example).
        """
        return line.price_unit

    def _calc_line_quantity(self, line):
        """Return the base quantity of the line to be used for the subtotal.

        This function can be extended by other modules to modify this base
        quantity (adding for example offers 3x2 and so on).
        """
        return line.product_qty

    @api.depends("product_id",'discount', "price_unit", "product_qty")
    def _amount_line(self):
        for obj in self:
            obj.price_subtotal = (obj.product_qty * obj.price_unit) * (1 - obj.discount / 100.0)
            if obj.product_id.weight > 0:
                obj.product_weight = obj.product_id.weight * obj.product_qty

    @api.depends("price_subtotal","manual_share", 'product_weight', 'discount', "order_id", "order_id.amount_fob", "order_id.total_weight", "order_id.cost_type")
    def _amount_line_share(self):
        for obj in self:
            share = 0
            if obj.manual_share > 0:
                share = obj.manual_share
            elif obj.order_id.cost_type:
                if obj.order_id.cost_type == 'fob' and obj.order_id.amount_fob > 0:
                    share = obj.price_subtotal / obj.order_id.amount_fob
                elif obj.order_id.cost_type == 'weight' and obj.order_id.total_weight > 0:
                    share = obj.product_weight / obj.order_id.total_weight
                elif obj.order_id.cost_type == 'qty' and obj.order_id.total_qty > 0:
                    share = obj.product_qty / obj.order_id.total_qty
                else:
                    share = 0
            obj.share = share
            
    @api.depends("manual_share")
    def _amount_line_inverse_share(self):
        for obj in self:
            if obj.manual_share > 0:
                obj.share = obj.manual_share

    @api.depends("tariff_line_ids", "tariff_line_ids.amount", "price_subtotal", "price_unit", 'tariff_id')
    def _tariff_subtotal(self):
        for obj in self:
            obj.tariff_subtotal = sum(
                x.amount for x in obj.tariff_line_ids if not x.param and x.line_liquidation_id.id == obj.id and not x.not_cost_tariff)
            
    @api.depends("price_subtotal", "tariff_subtotal", "freight_subtotal", "insurance_subtotal", 'expenses_subtotal', 'order_id.percent_pvp_mayor')
    def _amount_general_total(self):
        for obj in self:
            #amount_total = obj.price_subtotal + obj.tariff_subtotal + obj.freight_subtotal + obj.insurance_subtotal + obj.expenses_subtotal
            amount_total = obj.price_subtotal + obj.tariff_subtotal + obj.freight_subtotal + obj.insurance_subtotal + obj.expenses_subtotal
            if obj.price_subtotal > 0:
                factor = amount_total / obj.price_subtotal
            else:
                factor = 0
            #unit_cost = factor * obj.price_unit
            unit_cost = (amount_total / (obj.product_qty or 1))
            tax = 1.12
            pvp_mayor = ((unit_cost * obj.order_id.percent_pvp_mayor) * tax)
            obj.update({
                'amount_total': amount_total,
                'factor': factor,
                'unit_cost': unit_cost,
                'pvp_mayor': pvp_mayor
            })

    @api.depends("order_id", "order_id.breakdown_expenses_ids", "share")
    def _amount_general_subtotal(self):
        for obj in self:
            freight_subtotal = 0
            insurance_subtotal = 0
            expenses_subtotal = 0
            expenses_abroad = 0
            freight_provider_assumed_subtotal = 0
            for rec in obj.order_id.breakdown_expenses_ids:
                if rec.terms_id.is_provider_assumed:
                    expenses_abroad+=rec.amount
                    if rec.terms_id.type == 'freight':
                        freight_provider_assumed_subtotal += rec.amount
                else:
                    if rec.type == 'freight':
                        # if obj.order_id.incoterm_id.freight_assumed_provider:
                        freight_subtotal += rec.amount
                    elif rec.type == 'insurance':
                        insurance_subtotal += rec.amount
                    elif rec.type == 'expense':
                        expenses_subtotal+=rec.amount
            obj.update({
                'freight_subtotal': freight_subtotal * obj.share,
                'insurance_subtotal': insurance_subtotal * obj.share,
                'expenses_subtotal': expenses_subtotal * obj.share,
                'expenses_abroad': expenses_abroad * obj.share,
                'freight_provider_assumed_subtotal': freight_provider_assumed_subtotal * obj.share
            })

    def _get_uom_id(self, cr, uid, context=None):
        try:
            proxy = self.pool.get('ir.model.data')
            result = proxy.get_object_reference(cr, uid, 'product', 'product_uom_unit')
            return result[1]
        except Exception:
            return False

    @api.onchange('product_id')
    def onchange_product_id(self):
        for rec in self:
           rec.tariff_id = rec.product_id.tariff_heading_id.id
           rec.name = rec.product_id.name
           rec.product_qty = 1
           rec.product_weight = rec.product_id.weight
           rec.price_unit = rec.product_id.standard_price

    def action_done(self):
        for rec in self:
            rec.write({'state': 'done'})
            data = {
                'amount_fob': rec.price_unit,
                'amount_cif': rec.related_cif,
                'last_cost': rec.unit_cost
            }
            for tline in rec.tariff_line_ids.filtered(lambda a: a.product_field_id):
                data[tline.product_field_id.name] = tline.amount
            rec.product_id.write(data)


class EkTariffRuleLine(models.Model):
    _name = "ek.tariff.rule.line"
    _inherit = "ek.tariff.rule"
    _description = "Calculo de líneas"
    _order = "sequence"

    line_liquidation_id = fields.Many2one(
        string=_("Líneas"),
        comodel_name="ek.import.liquidation.line",
        required=False,
        ondelete="cascade",
    )
    rule_id = fields.Many2one(
        string=_("Regla"),
        comodel_name="ek.tariff.rule",
        required=False,
    )
    amount = fields.Float(
        string=_("Valor"),
        required=False,
        digits="Total Costs of Rule",
    )
    terms_id = fields.Many2one(
        string=_("Aplicar a"),
        comodel_name="ek.incoterms.terms",
        required=False,
    )
    tariff_heading_ids = fields.Many2many(
        string=_("Partidas"),
        comodel_name="ek.tariff.heading",
        relation="ek_tariff_heading_rule_line_rel",
        column1="rule_id",
        column2="tariff_id",
        copy=False,
    )


class EkImportLiquidationBreakdownExpenses(models.Model):
    _name = 'ek.import.liquidation.breakdown.expenses'
    _description = 'Desglose de gastos de importación'
    _order = 'sequence'

    order_id = fields.Many2one(
        string=_("Importación"),
        comodel_name="ek.import.liquidation",
        ondelete="cascade",
    )
    terms_id = fields.Many2one(
        string=_("Término"),
        comodel_name="ek.incoterms.terms",
        required=True,
    )
    amount = fields.Float(
        string=_("Valor"),
        digits="Account",
    )
    code = fields.Char(
        string=_("Código"),
        size=64,
        required=False,
        readonly=False,
        related="terms_id.code",
        store=True,
    )
    type = fields.Selection(
        string=_("Tipo"),
        store=True,
        related="terms_id.type",
    )
    sequence = fields.Integer(
        string=_("Orden"),
        required=False,
        related="terms_id.sequence",
        store=True,
        help=_("Úselo para organizar la secuencia de cálculo"),
    )
    manual = fields.Boolean(
        string=_("Manual"),
        default=True,
    )
    is_required = fields.Boolean(
        string="Requerido",
    )
    is_considered_total = fields.Boolean(
        string=_("¿Considerado en el total?"),
        related="terms_id.is_considered_total",
        store=True,
    )
    # amount_type = fields.Selection(string="Tipo de monto", selection=[('value', 'Por Valor'), ('weight', 'Por Peso'), ('quantity', 'Por Cantidad'), ], required=True, default="value")


class EkImportLiquidationTypeDocs(models.Model):
    _name = "ek.import.liquidation.type.docs"
    _description = "Tipos de Documentos de Importación"

    name = fields.Char(
        string=_("Documento"),
        required=True,
    )


class EkImportLiquidationRelatedDocuments(models.Model):
    _name = "ek.import.liquidation.related.documents"
    _description = "Desglose de documentos de importación"

    order_id = fields.Many2one(
        string=_("Importación"),
        comodel_name="ek.import.liquidation",
        ondelete="cascade",
    )
    type_doc = fields.Selection(
        string="Tipo de Documento",
        selection=[
            ("fiscal", _("Relacionado")),
            ("others", _("Sin relación"))
        ],
        required=False
    )
    # baseImponibleReemb|baseImpGravReemb
    invoice_id = fields.Many2one(
        string=_("Documento"),
        comodel_name="account.move",
        required=False,
    )
    voucher_id = fields.Many2one(
        string=_("Documento Voucher"),
        comodel_name="account.move",
        required=False,
    )
    # generic_document_id = fields.Many2one("ek.generic.documents", string="Documento", required=False, help="")
    type = fields.Many2one(
        string=_("Tipo"),
        comodel_name="ek.import.liquidation.type.docs",
        required=False,
    )
    amount = fields.Float(
        string=_("Total"),
        digits="Account",
    )
    name = fields.Char(
        string=_("Número"),
        required=False,
    )
    date = fields.Date(
        string=_("Fecha"),
        required=False,
    )
    partner_id = fields.Many2one(
        string=_("Proveedor"),
        comodel_name="res.partner",
        change_default=True,
    )
    lines = fields.One2many(
        inverse_name=_("related_documents_id"),
        comodel_name="ek.import.liquidation.related.documents.line",
        string="Líneas",
        required=False,
    )
    apply_by_item = fields.Boolean(
        string=_("Detallar ítems"),
        help=_("Permite detallar los valores por cada ítem"),
    )
    terms_id = fields.Many2one(
        string=_("Aplicar a"),
        comodel_name="ek.incoterms.terms",
        required=False,
    )

    @api.onchange("type_doc","invoice_id")
    def onchange_document_id(self):
        for res in self:
            if res.type_doc == 'fiscal' and res.invoice_id:
                invoice_pool = self.env['account.move']
                invoice = invoice_pool.browse(res.invoice_id.id)
                if invoice:
                    res.update({'amount': (invoice.amount_untaxed and abs(invoice.amount_untaxed) or abs(invoice.amount_total)), 'name': invoice.l10n_latam_document_number, 'date': invoice.invoice_date})


class EkImportLiquidationRelatedDocumentsLine(models.Model):
    _name = "ek.import.liquidation.related.documents.line"
    _description = "Lineas de Documentos Relacionados"


    line_invoice_id = fields.Many2one(
        string=_("Línea Factura"),
        comodel_name="account.move.line",
        required=False,
    )
    name = fields.Text(
        string=_("Descripción"),
        required=True,
    )
    product_qty = fields.Float(
        string=_("Cantidad"),
        digits="Product Unit of Measure",
        required=True,
        default=1,
    )
    product_weight = fields.Float(
        string=_("Peso (Kg)"),
        digits="Product Unit of Measure",
        required=False,
        default=0.00,
    )
    product_uom = fields.Many2one(
        string=_("Unidad de Medida"),
        comodel_name="uom.uom",
        required=False,
    )
    product_id = fields.Many2one(
        string=_("Producto"),
        comodel_name="product.product",
        domain=[('purchase_ok', '=', True)],
        change_default=True,
        required=False,
    )

    # TODO: ¿Qué es esto?
    '''price_unit = fields.Float('Precio Unitario', required=True,
                              digits='Product Price'))'''

    price_subtotal = fields.Float(
        string=_("Monto"),
        digits="Account",
    )
    related_documents_id = fields.Many2one(
        string=_("Documento"),
        comodel_name="ek.import.liquidation.related.documents",
        required=False,
    )
    terms_id = fields.Many2one(
        string=_("Aplicar a"),
        comodel_name="ek.incoterms.terms",
        required=False,
    )

    def _get_uom_id(self, cr, uid, context = None):
        try:
            proxy = self.pool.get('ir.model.data')
            result = proxy.get_object_reference(cr, uid, 'product', 'product_uom_unit')
            return result[1]
        except Exception:
            return False

    @api.onchange("line_invoice_id")
    def onchange_line_invoice_id(self):
        for rec in self:
            if rec.line_invoice_id:
                rec.update({
                    'name': rec.line_invoice_id.name,
                    'product_qty': rec.line_invoice_id.quantity,
                    'product_uom': rec.line_invoice_id.product_uom_id and rec.line_invoice_id.product_uom_id.id or False,
                    'product_id': rec.line_invoice_id.product_id and rec.line_invoice_id.product_id.id or False,
                    'price_subtotal': abs(rec.line_invoice_id.price_subtotal)
                })

    @api.onchange('product_id')
    def onchange_product_id(self):
        for rec in self:
            rec.update({
                'name': rec.product_id.name,
                'product_qty': 1,
                'product_weight': rec.product_id.weight
            })

    def onchange_product_uom(self, cr, uid, ids, product_id, qty, uom_id,
                             partner_id, date = False,
                             name=False, price_unit=False, context=None):
        """
        onchange handler of product_uom.
        """
        if context is None:
            context = {}
        if not uom_id:
            return {'value': {'price_unit': price_unit or 0.0, 'name': name or '', 'product_uom': uom_id or False}}
        context = dict(context, purchase_uom_check=True)

        return self.onchange_product_id(
            cr, uid, ids, product_id, qty, uom_id, partner_id,
            date=date, name=name, price_unit=price_unit, context=context
        )


class EkCountryPort(models.Model):
    _name = "ek.country.port"
    _description = "Puertos"

    code = fields.Char(
        string=_("Código"),
        required=True,
    )
    name = fields.Char(
        string="Nombre",
        required=True,
    )
    country_id = fields.Many2one(
        string="País",
        comodel_name="res.country",
        required=True,
    )


class EkImportLiquidationType(models.Model):
    _name = "ek.import.liquidation.type"
    _description = "Tiposs de importación"

    code = fields.Char(
        string=_("Código"),
        required=True,
    )
    name = fields.Char(
        string=_("Nombre"),
        required=True,
    )

    # _sql_constraints = [
    #     (
    #         "code_type_unique",
    #         "unique(code, name)",
    #         "El tipo de importación debe ser unico",
    #     )
    # ]

    @api.constrains("code", "name")
    def _check_import_liquidation_type_uniqueness(self):
        for rec in self:
            import_liquidation_type = self.search([
                ('id', '!=', rec.id),
                ('code', '=', rec.code),
                ('name', '=', rec.name),
            ], limit=1)
            if import_liquidation_type:
                raise ValidationError(_("El tipo de importación debe ser único."))
