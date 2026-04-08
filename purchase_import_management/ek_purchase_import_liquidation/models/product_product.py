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
from odoo import api, fields, models
from odoo.tools.translate import _
from collections import defaultdict


class ProductCategory(models.Model):
    _inherit = "product.category"

    utility_percent = fields.Float(
        string=_("Porcentaje de Utilidad"),
        required=False,
        help=_("Este valor sera usado para calcular el incremento sobre el costo de una importación para otener el PVP."),
    )

    property_stock_account_import_cost_id = fields.Many2one(
        'account.account', 'Cuenta de Importaciones', company_dependent=True,
        domain="[('deprecated', '=', False)]", check_company=True,
        help="""Esta cuenta se utilizará como contrapartida de en los documentos de importación.""")

    def _get_stock_account_property_field_names(self):
        return super()._get_stock_account_property_field_names() + ['property_stock_account_import_cost_id']


class ProductTemplate(models.Model):
    _inherit = "product.template"

    tariff_heading_id = fields.Many2one(
        string=_("Partida arancelaria"),
        comodel_name="ek.tariff.heading",
        required=False,
    )
    amount_fob = fields.Float(
        string=_("Valor FOB"),
        digits="Total FOB",
        compute="_compute_fob_cif",
        readonly=True,
        help=_("Valor FOB referencial a la ultima liquidación de importación"),
    )
    amount_cif = fields.Float(
        string=_("Valor CIF"),
        digits="Total FOB",
        compute="_compute_fob_cif",
        help=_("Valor CIF referencial a la ultima liquidación de importación"),
        readonly=True,
    )
    last_cost = fields.Float(
        string=_("Ultimo Costo"),
        digits="Product Price",
        help=_("Valor del ultimo costo de compra o importación"),
        compute="_compute_fob_cif",
        readonly=True,
    )
    qty_in_ordered = fields.Float(
        string=_("Ctdad. Pedida"),
        readonly=True,
        compute="_compute_qty_import_transit",
        help=_("Cantidad pedida."),
    )
    qty_in_transit = fields.Float(
        string=_("Ctdad. Transito"),
        readonly=True,
        compute="_compute_qty_import_transit",
        help=_("Cantidad en tránsito."),
    )

    @api.depends('product_variant_ids', "product_variant_ids.amount_fob", "product_variant_ids.amount_cif")
    def _compute_fob_cif(self):
        calc_amount_fob = 0
        calc_amount_cif = 0
        calc_last_cost = 0
        n_product = 0
        for p in self.product_variant_ids:
            calc_amount_fob =p.amount_fob
            calc_amount_cif =p.amount_cif
            calc_last_cost = p.last_cost
            n_product+=1

        #if n_product > 0:
        #    self.amount_fob = calc_amount_fob / n_product
        #    self.amount_cif = calc_amount_cif / n_product

        #else:
        #    self.amount_fob = 0.00
        #    self.amount_cif = 0.00
        # self.amount_cif = calc_amount_cif
        # self.amount_fob = calc_amount_fob
        # self.last_cost = calc_last_cost

        self.update({
            'amount_cif': calc_amount_cif,
            'amount_fob': calc_amount_fob,
            'last_cost': calc_last_cost
        })

    def _product_available(self, cr, uid, ids, name, arg, context=None):
        prod_available = {}
        product_ids = self.browse(cr, uid, ids, context=context)
        var_ids = []
        for product in product_ids:
            var_ids += [p.id for p in product.product_variant_ids]
        variant_available= self.pool['product.product']._product_available(cr, uid, var_ids, context=context)

        for product in product_ids:
            qty_available = 0
            virtual_available = 0
            incoming_qty = 0
            outgoing_qty = 0
            for p in product.product_variant_ids:
                qty_available += variant_available[p.id]["qty_available"]
                virtual_available += variant_available[p.id]["virtual_available"]
                incoming_qty += variant_available[p.id]["incoming_qty"]
                outgoing_qty += variant_available[p.id]["outgoing_qty"]
            prod_available[product.id] = {
                "qty_available": qty_available,
                "virtual_available": virtual_available,
                "incoming_qty": incoming_qty,
                "outgoing_qty": outgoing_qty,
            }
        return prod_available

    def action_view_import_transit(self):
        action = self.env["ir.actions.actions"]._for_xml_id("ek_purchase_import_liquidation.ek_product_for_sale_import_transit_action")
        action['domain'] = [('product_id.product_tmpl_id', 'in', self.ids)]
        return action

    def _compute_qty_import_transit(self):
        import_transit = self.env['ek.product.for.sale.import.transit'].sudo().read_group([
            ('company_id', '=', self.env.company.id),
            ('product_tmpl_id', '=', self.ids)
        ], fields=['product_qty', 'qty_in_transit'], groupby=['product_tmpl_id'])
        product_qty_total = defaultdict(float)
        qty_in_transit_total = defaultdict(float)

        for l in import_transit:
            product_qty_total[l['product_tmpl_id'][0]] += l['product_qty']
            qty_in_transit_total[l['product_tmpl_id'][0]] += l['qty_in_transit']

        for rec in self:
            rec.update({
                'qty_in_ordered': product_qty_total.get(rec.id, 0.00),
                'qty_in_transit': qty_in_transit_total.get(rec.id, 0.00)
            })

    def _get_product_accounts(self):
        accounts = super()._get_product_accounts()
        accounts.update({
            'import': self.categ_id.property_stock_account_import_cost_id,
        })
        return accounts


class ProductProduct(models.Model):
    _inherit = "product.product"

    tariff_heading_id = fields.Many2one(
        string=_("Partida arancelaria"),
        comodel_name="ek.tariff.heading",
        required=False,
    )
    ref_import = fields.Char(
        string=_("Alias de importación"),
        required=False,
        help=_("Este campo se usa para los reportes donde los nombres de los productos deben ser estándares."),
    )
    amount_fob = fields.Float(
        string=_("Valor FOB"),
        digits="Total FOB",
        readonly=True,
        help=_("Valor FOB referencial a la ultima liquidación de importación."),
    )
    amount_cif = fields.Float(
        string=_("Valor CIF"),
        digits="Total FOB",
        readonly=True,
        help=_("Valor CIF referencial a la ultima liquidación de importación"),
    )
    last_cost = fields.Float(
        string=_("Último costo"),
        digits="Product Price",
        readonly=True,
        help=_("Valor del ultimo costo de compra o importación"),
    )
    qty_in_ordered = fields.Float(
        string=_("Ctdad. Pedida"),
        readonly=True,
        compute="_compute_qty_import_transit",
        help=_("Cantidad pedida."),
    )
    qty_in_transit = fields.Float(
        string=_("Ctdad. Tránsito"),
        readonly=True,
        compute='_compute_qty_import_transit',
        help=_("Cantidad en tránsito."),
    )

    def _compute_qty_import_transit(self):
        import_transit = self.env['ek.product.for.sale.import.transit'].sudo().read_group([
            ('company_id','=',self.env.company.id),
            ('product_id', '=', self.ids)
        ], fields=['product_qty', 'qty_in_transit'], groupby=['product_id'])
        product_qty_total = defaultdict(float)
        qty_in_transit_total = defaultdict(float)

        for l in import_transit:
            product_qty_total[l['product_id'][0]] += l['product_qty']
            qty_in_transit_total[l['product_id'][0]] += l['qty_in_transit']

        for rec in self:
            rec.update({
                'qty_in_ordered': product_qty_total.get(rec.id,0.00),
                'qty_in_transit': qty_in_transit_total.get(rec.id,0.00)
            })

    def action_view_import_transit(self):
        action = self.env["ir.actions.actions"]._for_xml_id(
            "ek_purchase_import_liquidation.ek_product_for_sale_import_transit_action")
        action['domain'] = [('product_id', 'in', self.ids)]

        return action

    # TODO: ¿Por qué está esto así?
    '''def name_get(self):
        result = []
        for rec in self:
            name = rec.name

            if self.user_has_groups('purchase.group_purchase_manager') or self.user_has_groups('purchase.group_purchase_user'):
                name = '[%s] %s' % (rec.default_code, name)
            else:
                name = '[00000%s] %s' % (rec.id, name)

            result.append((rec.id, name))
        return result
    '''
    '''def name_get(self, cr, user, ids, context=None):
        if context is None:
            context = {}
        if isinstance(ids, (int, float)):
            ids = [ids]
        if not len(ids):
            return []

        def _name_get(d):
            name = d.get('name', '')
            code = context.get('display_default_code', True) and d.get('default_code', False) or False
            if code:
                name = '[%s] %s' % (code, name)
            return (d['id'], name)

        partner_id = context.get('partner_id', False)
        if partner_id:
            partner_ids = [partner_id, self.pool['res.partner'].browse(cr, user, partner_id,
                                                                       context=context).commercial_partner_id.id]
        else:
            partner_ids = []

        # all user don't have access to seller and partner
        # check access and use superuser
        self.check_access_rights(cr, user, "read")
        self.check_access_rule(cr, user, ids, "read", context=context)

        result = []
        for product in self.browse(cr, self._uid, ids, context=context):
            variant = ", ".join([v.name for v in product.attribute_value_ids])
            name = variant and "%s (%s)" % (product.name, variant) or product.name
            sellers = []
            if partner_ids:
                sellers = filter(lambda x: x.name.id in partner_ids, product.seller_ids)
            if sellers:
                for s in sellers:
                    seller_variant = s.product_name and (
                        variant and "%s (%s)" % (s.product_name, variant) or s.product_name
                    ) or False
                    mydict = {
                        'id': product.id,
                        'name': seller_variant or name,
                        'default_code': s.product_code or product.default_code,
                    }
                    result.append(_name_get(mydict))
            else:
                mydict = {
                    'id': product.id,
                    'name': name,
                    'default_code': product.default_code or (product.tariff_heading_id and product.tariff_heading_id.code or False),
                }
                result.append(_name_get(mydict))
        return result'''
