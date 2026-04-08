from odoo import fields, models, api,_
from datetime import datetime, timedelta
from odoo.tools import float_round
from odoo.exceptions import ValidationError
from ast import literal_eval
import calendar

_MONTH=['',_("Enero"),_('Febrero'),_('Marzo'),_('Abril'),_('Mayo'),_('Junio'),_('Julio'),_('Agosto'),_('Septiembre'),
        _('Octubre'),_('Noviembre'),_('Diciembre')]

class ProductTemplate(models.Model):
    _inherit = 'product.template'

    allow_suggested = fields.Boolean(
        string='Sugerencia de Compras (Plantilla)?',
        required=False, default=True, help="Si desmarca esta opción ninguno de los productos que pertenecen a la "
                                           "plantilla serán tomados en cuenta para la sugerencia de pedidos.")
    multiplicity = fields.Float(
        string='Cantidad x Venta',
        help="Multiplicada de venta, ejemplo sirve para identificar que este producto se vende de 2 en 2",
        required=False, default=1)

class ProductProduct(models.Model):
    _inherit = 'product.product'

    allow_suggested_product = fields.Boolean(
        string='Sugerencia de Compras (Producto)?',
        required=False, default=True, help="Si desmarca esta opción solo este producto "
                                           "no será tomado en cuenta para la sugerencia de pedidos.")


class SuggestedPurchaseRelatedStock(models.Model):
    _name = 'ek.suggested.purchase.related.stock'
    _description = _('Stock de productos relacionados')
    
    product_name = fields.Char(
        string='Producto',
        required=False)
    quantity = fields.Float(
        string='Cantidad',
        required=False)

    suggested_id = fields.Many2one(
        comodel_name='ek.suggested.purchase',
        string='Sugerido',
        required=False, ondelete='cascade')


class SuggestedPurchaseRelatedSales(models.Model):
    _name = 'ek.suggested.purchase.related.sales'
    _description = _('Ventas de productos relacionados')

    product_name = fields.Char(
        string='Producto',
        required=False)
    quantity = fields.Float(
        string='Cantidad',
        required=False)

    suggested_id = fields.Many2one(
        comodel_name='ek.suggested.purchase',
        string='Sugerido',
        required=False, ondelete='cascade')

class SuggestedPurchaseRelatedTransit(models.Model):
    _name = 'ek.suggested.purchase.related.transit'
    _description = _('Transito de productos relacionados')

    product_name = fields.Char(
        string='Producto',
        required=False)
    quantity = fields.Float(
        string='Cantidad',
        required=False)

    suggested_id = fields.Many2one(
        comodel_name='ek.suggested.purchase',
        string='Sugerido',
        required=False, ondelete='cascade')

class DaysOutOfStock(models.Model):
    _name = 'ek.days.out.of.stock'
    _description = 'Dias sin stock'

    product_id = fields.Many2one(
        comodel_name='product.product',
        string=_('Producto'),
        required=False)

    days = fields.Integer(
        string='Dias',
        required=False)


    @api.model
    def cron_check_days_out_of_stock(self):
        suggestedPurchase = self.env['ek.suggested.purchase']
        product_templates = suggestedPurchase.get_template_product_suggested()
        products = product_templates.mapped("product_variant_ids")
        product_in_stock = suggestedPurchase.get_available_stock_stock_by_warehouse(products=products)
        data_create = []
        data_all = {}
        lines = self.search([])
        for rec in lines:
            data_all[rec.product_id.id] = rec.days

        lines.sudo().unlink()

        for product in products:
            if product.id not in product_in_stock or product_in_stock[product.id]['quantity'] <= 0:
                data_create.append({
                    'product_id': product.id,
                    'days': data_all.get(product.id,0) + 1
                })

        if data_create:
            self.create(data_create)

class SuggestedPurchaseKit(models.Model):
    _name = 'ek.suggested.purchase.kit'
    _description = _('Kit de Sugerido de Compras Base')

    name = fields.Char(
        string=_('Kit'),
        required=False)
    
    line_ids = fields.One2many(
        comodel_name='ek.suggested.purchase',
        inverse_name='kit_id',
        string=_('Detalle'),
        required=False)

    partner_id = fields.Many2one('res.partner', string="Supplier", readonly=True)

    company_id = fields.Many2one('res.company', string=_('Company'), required=False, readonly=False,
                                 default=lambda self: self.env.company)

    def action_unlink(self):
        for rec in self:
            rec.sudo().unlink()

    def update_line_kit(self, qty_base_suggested):
        for rec in self:
            for line in rec.line_ids.filtered(lambda a: a.product_base == False):
                line.update({
                    'qty_suggested': line.multiply * qty_base_suggested
                })
            self.flush()

class SuggestedPurchase(models.Model):
    _name = 'ek.suggested.purchase'
    _description = _('Sugerido de Compras Base')
    
    kit_id = fields.Many2one(
        'ek.suggested.purchase.kit',
        string=_('Kit'),
        required=False)

    related_stock_ids = fields.One2many(
        comodel_name='ek.suggested.purchase.related.stock',
        inverse_name='suggested_id',
        string='Stock Relacionado',
        required=False)

    related_sales_ids = fields.One2many(
        comodel_name='ek.suggested.purchase.related.sales',
        inverse_name='suggested_id',
        string='Venta relacionadas',
        required=False)

    related_transit_ids = fields.One2many(
        comodel_name='ek.suggested.purchase.related.transit',
        inverse_name='suggested_id',
        string='Transito relacionadas',
        required=False)

    partner_id = fields.Many2one('res.partner', string=_("Supplier"), readonly=True)

    multiplicity = fields.Float(
        string='Multiplo de',
        help="Multiplicada de venta, ejemplo sirve para identificar que este producto se vende de 2 en 2",
        required=False, default=1, readonly=True)

    name = fields.Char(
        string=_('Name'),
        required=False, readonly=True)
    default_code = fields.Char(
        string=_('Code'),
        required=False, readonly=True)

    default_code2 = fields.Char(
        string=_('Código 2'),
        required=False, readonly=True)

    default_code3 = fields.Char(
        string=_('Código 3'),
        required=False, readonly=True)



    company_id = fields.Many2one('res.company', string=_('Company'), required=False, readonly=False,
                                 default=lambda self: self.env.company)
    product_id = fields.Many2one('product.product', string=_("Product"), readonly=True)
    product_uom_id = fields.Many2one(
        string=_("Uom"), comodel_name="uom.uom"
    )

    product_tmpl_id = fields.Many2one('product.template', string=_("Plantilla"), readonly=True)

    qty_stock = fields.Float(string=_('Stock'), required=False, help=_("Cantidad disponible en inventario"), copy=False, default='0', readonly=True,digits='Product Unit of Measure',)
    qty_stock_related = fields.Float(string=_('Stock Relacionado'), required=False, help=_("Cantidad disponible en inventario relacionado"), copy=False, default='0', readonly=True,digits='Product Unit of Measure',)
    qty_pending_deliver = fields.Float(string=_('Por Entregar'), help=_("Cantidad de items por entregar"), required=False, copy=False, default='0', readonly=True,digits='Product Unit of Measure',)
    sales_ytd = fields.Float(string=_('Ventas 365'), help=_("Ventas del ultimo año calendario"), required=False, copy=False, default='0', readonly=True,digits='Product Unit of Measure',)
    calendar_yearly_qty = fields.Float(string=_('Ventas Anuales'), help=_("Ventas desde enero a diciembre del año actual"), required=False, copy=False, default='0', readonly=True,digits='Product Unit of Measure',)
    sales_month = fields.Float(string=_('Sales Month'), required=False, copy=False, default='0', readonly=True,digits='Product Unit of Measure',)
    sales_1_month = fields.Float(string=_('Ventas Mes Anterior'), required=False, copy=False, default='0', readonly=True,
                               digits='Product Unit of Measure', )
    check_sales = fields.Selection(
        string=_('Check Sale'),
        selection=[('equal', _('Equal')),
                   ('higher', _('Higher')),
                   ('minor', _('Minor')), ],
        required=False, )
    number = fields.Char(
        string='No',
        required=False, default='/')
    sales_related = fields.Float(string=_('Ventas Relacionadas'), help=_("Ventas de productos de la misma plantilla"), required=False, copy=False, default='0', readonly=True,digits='Product Unit of Measure')
    projected_sales = fields.Float(string=_('Ventas Proyectadas'), required=False, copy=False, default='0', readonly=True,digits='Product Unit of Measure')
    sales_esp = fields.Float(string=_('Sales ESP'), required=False, copy=False, default='0', readonly=True,digits='Product Unit of Measure',)
    sales_year_old = fields.Float(string=_('Sales year Old'), required=False, copy=False, default='0', readonly=True,digits='Product Unit of Measure',)
    sales_year_old_month = fields.Float(string=_('Sales year Old Month'), required=False, copy=False, default='0', readonly=True,digits='Product Unit of Measure',)
    previous_date = fields.Date(string=_("Primera Venta"), readonly=True)
    last_date = fields.Date(string=_("Last Date"), readonly=True)
    last_purchase = fields.Date(string=_("Última compra"), readonly=True)
    sample_months = fields.Integer(
        string=_('Meses de Ejemplo'), help=_('Cantidad de meses de datos históricos'),
        required=False, default=0)

    sale_avg_month = fields.Float(
        string=_('Ventas Prom. Mes'),help=_('Total de ventas promedios por mes'),
        required=False, compute="_compute_product_sale_avg_month", default=0)

    date = fields.Date(  # OK
        string=_('Fecha de Corte'),
        required=False, default=fields.Date.today())
    over_stock = fields.Boolean(
        string=_('Sobre-Stock'),
        required=False, readonly=True)
    purchase_local = fields.Float(string=_('Purchase local'), required=False, copy=False, default='0', readonly=True)
    transit = fields.Float(string=_('Transito'), required=False, copy=False, default='0', readonly=True)
    transit_related = fields.Float(string=_('Transito Relacionado'), required=False, copy=False, default='0', readonly=True)
    day_not_stock = fields.Integer(string=_('Day not stock'), required=False, copy=False, default='0', readonly=True, group_operator='avg',)
    minimum = fields.Float(string=_('Minimo'), required=False, copy=False, default='0', readonly=True)
    maximum = fields.Float(string=_('Máximo'), required=False, copy=False, default='0', readonly=True)
    day_transit = fields.Integer(string=_('Dias de Transito'), required=False, copy=False, default='0', readonly=True, group_operator='avg',)
    qty_suggested = fields.Float(string=_('Suggested'), required=True, copy=False, default='0', readonly=False)
    cost_sale_inventory = fields.Float(string=_('Costo de Venta'), required=True, copy=False, default='0', readonly=False)
    arrival_date = fields.Date(string=_("Arrival Date"), readonly=True)
    cost = fields.Float(string=_('Cost'), required=False, copy=False, default='0', readonly=True,digits='Product Price',)
    last_cost = fields.Float(string=_('FOB'), required=False, copy=False, default='0', readonly=True,
                        digits='Product Price', )
    weight = fields.Float(string=_('Peso'), required=False, copy=False, default='0', readonly=True,digits='Stock Weight',)
    investment = fields.Float(string=_('Investment'), required=False, copy=False, default='0', readonly=True, compute="_compute_general_values", store=True)
    total_weight = fields.Float(string=_('Peso total'), required=False, copy=False, default='0', readonly=True,digits='Stock Weight', compute="_compute_general_values", store=True)
    turnover = fields.Float(string=_('Rotación'), required=False, copy=False, default='0', readonly=True,
                                digits='Stock Weight', compute="_compute_inventary_turnover", store=True, group_operator='avg',)

    product_base = fields.Boolean(
        string=_('Producto Base'),
        required=False,readonly=True)

    month_security = fields.Integer(
        string=_('Meses de Seguridad'),
        required=False,readonly=True)

    month_transit = fields.Integer(
        string=_('Meses de Transito'),
        required=False,readonly=True)

    factor_name = fields.Char(string=_('Code factor'),readonly=True)
    factor = fields.Float(
        string=_('Factor'),
        required=False,readonly=True)

    required_qty_stock = fields.Float(string=_('Stock Requerido'), required=False, copy=False, default='0',
                                      readonly=True,digits='Product Unit of Measure',help=_("Stock requerido hasta el próximo pedido"))

    f_x = fields.Float(
        string=_('F(x) Value'),
        required=False,readonly=True)

    f_y = fields.Float(
        string=_('F(y) Value'),
        required=False,readonly=True)

    def calculate_suggest_by_multiplicity(self,multiplicity,suggest_qty):
        if suggest_qty <= 0:
            return 0
        elif multiplicity == 1:
            return suggest_qty
        elif multiplicity > suggest_qty:
            suggest_qty = multiplicity
        elif multiplicity < suggest_qty:
            residual = suggest_qty%multiplicity
            if residual > 0:
                suggest_qty = suggest_qty + (multiplicity - residual)

        return suggest_qty

    def calculate_master_suggest(self,round_type=False,precision_digits=False):
        result = self.env['ek.purchase.adjustment.factor'].list_suggeted_by_factors()
        for rec in self:
            if rec.kit_id and not rec.product_base:
                continue
           #if rec.over_stock:
            #    continue
            multiplicity = rec.multiplicity or 1
            factor = result.get(rec.id,False)


            if factor:
                required_qty_stock = (rec.sale_avg_month * (rec.month_transit + factor.month_security))
                qty_suggested = (required_qty_stock - rec.qty_stock - rec.transit) + rec.qty_suggested

                if qty_suggested < 0:
                    qty_suggested = 0
                else:
                    qty_suggested = qty_suggested * factor.factor
                    qty_suggested = float_round(qty_suggested, precision_digits=precision_digits,
                                rounding_method=round_type)

                qty_suggested = rec.calculate_suggest_by_multiplicity(multiplicity,qty_suggested)
                rec.update({
                    'factor_name': factor.name,
                    'factor': factor.factor,
                    'month_security': factor.month_security,
                    'investment': qty_suggested * (rec.last_cost or rec.cost),
                    'total_weight': qty_suggested * rec.weight,
                    'required_qty_stock': required_qty_stock,
                    'qty_suggested': qty_suggested
                })
            else:
                qty_suggested = 0
                # Todo Si  F(x) >= F(y) el sistema mostrara en el sugerido la compra de F(y), por el contrario si F(x) < F(y), tambien se controlan los productos nuevos
                if rec.f_x >= rec.f_y and not rec.is_new_product_object():
                    qty_suggested = rec.f_y
                else:
                    qty_suggested = rec.f_x

                qty_suggested = rec.over_stock and 0.00 or qty_suggested

                qty_suggested = rec.calculate_suggest_by_multiplicity(multiplicity, qty_suggested)

                required_qty_stock = (rec.sale_avg_month * (rec.month_transit))
                rec.update({
                    'investment': qty_suggested * (rec.last_cost or rec.cost),
                    'total_weight': qty_suggested * rec.weight,
                    'required_qty_stock': required_qty_stock,
                    'qty_suggested': qty_suggested
                })


                #'name': self.compute_name_product(product, qty_stock, cost, last_date),


    def action_show_relate_qty(self):
        xid = "base_suggested_purchase.ek_suggested_purchase_related_action"
        action = self.env["ir.actions.act_window"]._for_xml_id(xid)
        # domain = safe_eval(action["domain"])
        # domain.append(("collection_id", "=", self.id))
        # action["domain"] = domain
        action['res_id'] = self.id
        action['name'] = _('Stock Relacionado')
        return action

    def action_show_relate_sales_qty(self):
        xid = "base_suggested_purchase.ek_suggested_purchase_related_action"
        action = self.env["ir.actions.act_window"]._for_xml_id(xid)
        # domain = safe_eval(action["domain"])
        # domain.append(("collection_id", "=", self.id))
        # action["domain"] = domain
        action['res_id'] = self.id
        action['name'] = _('Ventas Relacionadas')
        return action

    def action_show_relate_transit(self):
        xid = "base_suggested_purchase.ek_suggested_purchase_related_action"
        action = self.env["ir.actions.act_window"]._for_xml_id(xid)
        # domain = safe_eval(action["domain"])
        # domain.append(("collection_id", "=", self.id))
        # action["domain"] = domain
        action['res_id'] = self.id
        action['name'] = _('Transito Relacionado')
        return action

    def action_unlink(self):
        for rec in self:
            rec.sudo().unlink()



    @api.depends('sales_ytd','date')
    def _compute_product_sale_avg_month(self):
        for rec in self:
            sale_avg_month = 0
            #Todo Dias con stock mayor a cero
            #date_to = fields.Date.to_date("%s-01-01" % rec.date.year)
            date_to = (rec.date - timedelta(days=365))  # fields.Date.to_date("%s-01-01" % date.year)
            date_end = rec.date
            if date_to and date_end:
                days = (date_end - date_to).days - rec.day_not_stock

                if days > 0:
                    sale_avg_month = (rec.sales_ytd/days) * 30

            round_type = self.env['ir.config_parameter'].sudo().get_param('suggest.default_round_type_c%s' % self.env.company.id,'UP')
            precision_digits = int(self.env['ir.config_parameter'].sudo().get_param('suggest.default_precision_digits_c%s' % self.env.company.id,0))

            sale_avg_month = float_round(sale_avg_month,precision_digits=precision_digits,
                        rounding_method=round_type)

            rec.update({'sale_avg_month': sale_avg_month})

    @api.depends('qty_suggested')
    def _compute_general_values(self):
        for rec in self:
            rec.update({
                'investment': rec.qty_suggested * (rec.last_cost or rec.cost),
                'total_weight': rec.qty_suggested * rec.weight
            })

            if rec.product_base and rec.kit_id:
                rec.kit_id.update_line_kit(rec.qty_suggested)


    @api.depends('sales_ytd', 'cost_sale_inventory')
    def _compute_inventary_turnover(self):
        for rec in self:
            valuate_inventory = rec.qty_stock * rec.cost
            total_cost_sale = rec.cost_sale_inventory

            if valuate_inventory > 0:
                rri_ytd = float_round(total_cost_sale/valuate_inventory, precision_digits=2,rounding_method='HALF-UP')
            else:
                rri_ytd = 0

            rec.update({'turnover': rri_ytd})

    #Todo Promedio de ventas
    def get_product_sale_avg_month(self,date,day_not_stock,sales_ytd):
        sale_avg_month = 0
        #Todo Dias con stock mayor a cero
        date_to = (date - timedelta(days=365)) #fields.Date.to_date("%s-01-01" % date.year)
        date_end = date
        if date_to and date_end:
            days = (date_end - date_to).days - day_not_stock

            if days > 0:
                sale_avg_month = (sales_ytd/days) * 30



        return sale_avg_month

    #Todo Formulas para sugerido
    #Todo F(x) = (MAX - STK) - CDT + PRV
    #Todo El resultado de F(x) me indicaría cuando debemos comprar pero el histórico de venta
    # me debe confirmar estos valores, para ello tenemos la siguiente formula
    #Todo [FD] Factor Diario = Promedio([VAP/365];[VMP/30];[VAA/MTA/30])
    #Todo F(y) = (FD * DDT) + (FD * DST)
    #Todo Si  F(x) >= F(y) el sistema mostrara en el sugerido la compra de F(y), por el contrario si F(x) < F(y)
    # el sistema solo sugeriría comprar el máximo permitido en el stock y de esta forma evitar un sobre-stock
    # u ocupación innecesaria en los almacenes.

    #Todo Variable
    #Todo [MTA] - Meses transcurridos del año actual
    def get_months_elapsed(self, month=False):
        return month and month or fields.Date.today().month

    # Todo Variable
    # Todo [MTR] - Meses restantes del año actual
    def get_months_ends(self, date):
        return 12 - date.month

    # Todo Dominio a tener en cuenta para encontrar las plantillas de productos que usaremos en el sugerido de compras
    def get_domain_product_suggested(self, other_domain=[]):
        domain = [('allow_suggested','=',True),('purchase_ok','=',True),('detailed_type','=','product')]
        if other_domain:
            domain.extend(other_domain)
            #return other_domain

        return domain

    #Todo Productos a tener en cuenta para el sugerido de compras
    def get_template_product_suggested(self, product_template=False,categ_ids=False):
        if product_template:
            return product_template

        init_domain = []

        if categ_ids:
           init_domain= [('categ_id','in',categ_ids.ids)]

        productTemplate = self.env['product.template'].search(self.get_domain_product_suggested(other_domain=init_domain))

        return productTemplate

    #Todo [DDT] - Días de transito (Cantidad de dias que demora un producto en llegar desde que se realiza un pedido
    # hasta que se encuentra en la bodega listo para la venta) esto se detalla en el producto
    #return dict
    def get_transit_days(self, template_ids=False, provider_ids=[],only_partner=False):
        if not template_ids:
            template_ids = self.get_template_product_suggested()
        transit_days = {}
        for templ in template_ids:
            if provider_ids:
                line_seller = templ.variant_seller_ids.filtered(lambda a: a.partner_id.id in provider_ids)
            else:
                line_seller = templ.variant_seller_ids

            for variant in line_seller:
                #tiene variantes
                if variant.product_id:
                    if not variant.product_id.id in transit_days:
                        transit_days[variant.product_id.id] = {
                            'product_id': variant.product_id.id,
                            'product_templ_id': templ.id,
                            'default_partner_id': False,
                            'default_days': 99999,
                            'default_balanced': 99999,
                            'default_price': variant.product_id.standard_price,
                            'partner_and_time': []
                        }

                    transit_days[variant.product_id.id]['partner_and_time'].append({
                        'partner_id': variant.partner_id.id,
                        'days': variant.delay,
                        'price': variant.price
                    })
                else: #no tiene variantes indicadas
                    if not only_partner:
                        for product_id in templ.product_variant_ids:
                            if not product_id.id in transit_days:
                                transit_days[product_id.id] = {
                                    'product_id': product_id.id,
                                    'product_templ_id': templ.id,
                                    'default_partner_id': False,
                                    'default_days': 99999,
                                    'default_balanced': 99999,
                                    'default_price': variant.product_id.standard_price,
                                    'partner_and_time': []
                                }

                            transit_days[product_id.id]['partner_and_time'].append({
                                'partner_id': variant.partner_id.id,
                                'days': variant.delay,
                                'price': variant.price
                            })

        return transit_days


    #Todo Obtener el mejor proveedor para la compra, esto funciona si se le compra a varios proveedores
    #Todo [Metodos para escoger el mejor proveedor] = {'cost' => Menor Costo, 'time' => Menor Tiempo, 'balanced' => 'Ponderado', 'specific' => 'Especifico'}
    def get_best_supplier(self, method='cost', template_ids=False, provider_ids=[],only_partner=False):
        if not template_ids:
            template_ids = self.get_template_product_suggested()

        transit_days = self.get_transit_days(template_ids=template_ids, provider_ids=provider_ids,only_partner=only_partner)

        for product_id, line in transit_days.items():
            _count_provider = len(line['partner_and_time'])
            if _count_provider == 0:
                continue
            elif _count_provider == 1:
                line['default_partner_id'] = line['partner_and_time'][0]['partner_id']
                line['default_days'] = line['partner_and_time'][0]['days']
                line['default_price'] = line['partner_and_time'][0]['price']
            else:
                for prov in line['partner_and_time']:
                    if method == 'cost':
                        if line['default_price'] > prov['price'] or line['default_price'] == 0:
                            line['default_partner_id'] = prov['partner_id']
                            line['default_days'] = prov['days']
                            line['default_price'] = prov['price']
                    elif method=='time':
                        if line['default_days'] > prov['days']:
                            line['default_partner_id'] = prov['partner_id']
                            line['default_days'] = prov['days']
                            line['default_price'] = prov['price']
                    elif method == 'balanced':
                        balanced_days = (prov['days']/7) * prov['price']
                        if line['default_balanced'] > balanced_days:
                            line['default_partner_id'] = prov['partner_id']
                            line['default_days'] = prov['days']
                            line['default_price'] = prov['price']
                            line['default_balanced'] = balanced_days


        return transit_days

    #Todo Costo de la mercancia vendida para sacar los ratios de rotacion
    def get_cost_of_goods_sold(self, products=False, year=False, date=False):
        if not products:
            product_templates = self.get_template_product_suggested()
            products = product_templates.mapped("product_variant_ids")

        if not year:
            year = fields.Date.today().year


        data_sale = {}


        date_start = '%s-01-01 00:00:00' % year
        date_end = '%s-12-31 23:59:59' % year

        if date:
            date_start = (date - timedelta(days=365)).strftime('%Y-%m-%d 00:00:00')
            date_end = date.strftime('%Y-%m-%d 23:59:59')

        domain_yearly = [('product_id', 'in', products.ids),('quantity', '<', 0), ('create_date', '>=', date_start),
                         ('create_date', '<=', date_end)]

        domain_yearly += [('stock_move_id.is_inventory','=',False)]

        for group in self.env['stock.valuation.layer'].read_group(domain_yearly, ['product_id', 'quantity','value'],
                                                            ['product_id']):
            product_id = group['product_id'][0]
            if product_id not in data_sale:
                data_sale[product_id] = {
                    'quantity': 0.00,
                    'valuate': 0.00,
                }
            data_sale[product_id]['quantity'] += abs(group['quantity'])
            data_sale[product_id]['valuate'] += abs(group['value'])


        return data_sale

    #Todo [VAA] - Ventas del año actual (Todas las ventas del producto en cuestión en un año calendario
    # sean normales o especiales)
    #Todo [VAP] - Ventas del año pasado (Todas las ventas del producto en cuestión sean normales o especiales del año anterior)
    #Todo [VMP] - Ventas del mes a reponer del año pasado  (Todas las ventas del producto en cuestión sean normales o especiales
    # del mes del año anterior perteneciente al mes que se quiere reponer)
    def get_sale_yearly_and_monthly(self, products=False, year=False, month=False,type=False, external_data={}, date=False,type_sale_qty='product_uom_qty'):
        if not products:
            product_templates = self.get_template_product_suggested()
            products = product_templates.mapped("product_variant_ids")

        if not year:
            year = fields.Date.today().year

        if not month:
            month = fields.Date.today().month

        data_sale = {}

        previous_year = year-1

        date_start = '%s-01-01 00:00:00' % year
        date_end = '%s-12-31 23:59:59' % year

        previous_date_start = '%s-01-01 00:00:00' % (previous_year)
        previous_date_end = '%s-12-31 23:59:59' % (previous_year)

        previous_day_end = calendar.monthrange(previous_year, month)[1]
        month_end_day_end = calendar.monthrange(year, month)[1]

        month_start = '%s-%s-01 00:00:00' % (year, (month > 9 and month or "0%s" % month))
        month_end = '%s-%s-%s 23:59:59' % (year, (month > 9 and month or "0%s" % month),
                                           (month_end_day_end > 9 and month_end_day_end or "0%s" % month_end_day_end))
        if date:
            date_start = (date - timedelta(days=365)).strftime('%Y-%m-%d 00:00:00')
            date_end = date.strftime('%Y-%m-%d 23:59:59')

            previous_date = fields.Date.today().replace(year=previous_year)

            previous_date_start = (previous_date - timedelta(days=365)).strftime('%Y-%m-%d 00:00:00')
            previous_date_end = previous_date.strftime('%Y-%m-%d 23:59:59')


            month_end = date.replace(year=year, month=month,day=month_end_day_end).strftime('%Y-%m-%d 23:59:59')
            month_start = date.replace(year=year, month=month).strftime('%Y-%m-01 00:00:00')

        previous_month_start = '%s-%s-01 00:00:00' % (previous_year,(month > 9 and month or "0%s"%month))
        previous_month_end = '%s-%s-%s 23:59:59' % (previous_year,(month > 9 and month or "0%s"%month),(previous_day_end > 9 and previous_day_end or "0%s"%previous_day_end))

        domain_yearly = [('product_id','in',products.ids),('date','>=', date_start),('date','<=', date_end),("state", "not in", ("draft", "cancel", "sent"))]
        domain_previous_yearly = [('product_id', 'in', products.ids), ('date', '>=', previous_date_start),
                         ('date', '<=', previous_date_end),("state", "not in", ("draft", "cancel", "sent"))]

        domain_monthly = [('product_id','in',products.ids),('date','>=', month_start),('date','<=', month_end),("state", "not in", ("draft", "cancel", "sent"))]

        domain_previous_monthly = [('product_id', 'in', products.ids), ('date', '>=', previous_month_start),
                         ('date', '<=', previous_month_end),("state", "not in", ("draft", "cancel", "sent"))]

        month_1 = month == 1 and 1 or month - 1
        month_1_start = '%s-%s-01 00:00:00' % (year,(month_1 > 9 and month_1 or "0%s" % month_1))
        month_1_day_end = calendar.monthrange(year, month_1)[1]
        month_1_end = '%s-%s-%s 23:59:59' % (year,(month_1 > 9 and month_1 or "0%s" % month_1),(month_1_day_end > 9 and month_1_day_end or "0%s" % month_1_day_end))

        domain_1_monthly = [('product_id', 'in', products.ids), ('date', '>=', month_1_start),
                          ('date', '<=', month_1_end),("state", "not in", ("draft", "cancel", "sent"))]


        #Agrupado para el anno actual
        date_to = fields.Date.to_string(fields.Date.start_of(date, "year"))
        date_end = fields.Date.to_string(fields.Date.end_of(date, "year"))
        domain_calendar_yearly = [('product_id', 'in', products.ids), ('date', '>=', date_to), ('date', '<=', date_end),
                         ("state", "not in", ("draft", "cancel", "sent"))]

        for group in self.env['sale.report'].read_group(domain_calendar_yearly, ['product_id', type_sale_qty], ['product_id']):
            product_id = group['product_id'][0]
            if product_id not in data_sale:

                data_sale[product_id] = {
                    'yearly_qty': 0.00,
                    'calendar_yearly_qty': 0.00,
                    'previous_yearly_qty': 0.00,
                    'monthly_qty': 0.00,
                    'previous_monthly_qty': 0.00,
                    'last_date': False,
                    'last_purchase': False,
                    'previous_date': False,
                    'sales_1_month': 0.00
                }
            data_sale[product_id]['calendar_yearly_qty']+= group[type_sale_qty]

        # Agrupado para anno calendario
        for group in self.env['sale.report'].read_group(domain_yearly, ['product_id', type_sale_qty],
                                                        ['product_id']):
            product_id = group['product_id'][0]
            if product_id not in data_sale:
                data_sale[product_id] = {
                    'yearly_qty': 0.00,
                    'previous_yearly_qty': 0.00,
                    'calendar_yearly_qty': 0.00,
                    'monthly_qty': 0.00,
                    'previous_monthly_qty': 0.00,
                    'last_date': False,
                    'last_purchase': False,
                    'previous_date': False,
                    'sales_1_month': 0.00
                }
            data_sale[product_id]['yearly_qty'] += group[type_sale_qty]

        # Agrupado para el anno anterior
        for group in self.env['sale.report'].read_group(domain_previous_yearly, ['product_id', type_sale_qty],
                                                       ['product_id']):
            product_id = group['product_id'][0]
            if product_id not in data_sale:
                data_sale[product_id] = {
                    'yearly_qty': 0.00,
                    'previous_yearly_qty': 0.00,
                    'calendar_yearly_qty': 0.00,
                    'monthly_qty': 0.00,
                    'previous_monthly_qty': 0.00,
                    'last_date': False,
                    'last_purchase': False,
                    'previous_date': False,
                    'sales_1_month': 0.00
                }
            data_sale[product_id]['previous_yearly_qty'] += group[type_sale_qty]

        # Agrupado para el mes actual
        for group in self.env['sale.report'].read_group(domain_monthly, ['product_id', type_sale_qty],
                                                       ['product_id']):
            product_id = group['product_id'][0]
            if product_id not in data_sale:
                data_sale[product_id] = {
                    'yearly_qty': 0.00,
                    'previous_yearly_qty': 0.00,
                    'calendar_yearly_qty': 0.00,
                    'monthly_qty': 0.00,
                    'previous_monthly_qty': 0.00,
                    'last_date': False,
                    'last_purchase': False,
                    'previous_date': False,
                    'sales_1_month': 0.00
                }
            data_sale[product_id]['monthly_qty'] += group[type_sale_qty]

        # Agrupado para el mes pasado
        for group in self.env['sale.report'].read_group(domain_1_monthly, ['product_id', type_sale_qty],
                                                            ['product_id']):
            product_id = group['product_id'][0]
            if product_id not in data_sale:
                data_sale[product_id] = {
                    'yearly_qty': 0.00,
                    'previous_yearly_qty': 0.00,
                    'calendar_yearly_qty': 0.00,
                    'monthly_qty': 0.00,
                    'previous_monthly_qty': 0.00,
                    'last_date': False,
                    'last_purchase': False,
                    'previous_date': False,
                    'sales_1_month': 0.00
                }
            data_sale[product_id]['sales_1_month'] += group[type_sale_qty]

        # Agrupado para el mes anterior
        for group in self.env['sale.report'].read_group(domain_previous_monthly, ['product_id', type_sale_qty],
                                                       ['product_id']):
            product_id = group['product_id'][0]
            if product_id not in data_sale:
                data_sale[product_id] = {
                    'yearly_qty': 0.00,
                    'previous_yearly_qty': 0.00,
                    'calendar_yearly_qty': 0.00,
                    'monthly_qty': 0.00,
                    'previous_monthly_qty': 0.00,
                    'last_date': False,
                    'last_purchase': False,
                    'previous_date': False,
                    'sales_1_month': 0.00
                }
            data_sale[product_id]['previous_monthly_qty'] += group[type_sale_qty]

        #obteniendo fecha de ultima venta
        SQL = """
            SELECT MAX(so.date_order)::date as last_date,MIN(so.date_order)::date as previous_date, sol.product_id
                 FROM sale_order_line sol
                 JOIN sale_order so ON sol.order_id = so.id
                 WHERE sol.product_id in %s  AND so.state in ('sale','done')
                 GROUP BY sol.product_id
        """
        self._cr.execute(SQL, (tuple(products.ids),))
        for group in self._cr.dictfetchall():

            product_id = group['product_id']
            if product_id not in data_sale:
                continue
            data_sale[product_id]['last_date'] = group['last_date']
            data_sale[product_id]['previous_date'] = group['previous_date']

        # obteniendo fecha de ultima compra
        SQL = """
                SELECT MAX(po.date_approve)::date as last_purchase, pol.product_id
                     FROM purchase_order_line pol
                     JOIN purchase_order po ON pol.order_id = po.id
                     WHERE pol.product_id in %s AND po.state in ('purchase','done')
                     GROUP BY pol.product_id
         """
        self._cr.execute(SQL, (tuple(products.ids),))
        for group in self._cr.dictfetchall():

            product_id = group['product_id']
            if product_id not in data_sale:
                continue
            data_sale[product_id]['last_purchase'] = group['last_purchase']


        if external_data:
            for eternal_product_id, data in external_data.items():
                if not eternal_product_id in data_sale:
                    data_sale[eternal_product_id] = data
                else:
                    data_sale[eternal_product_id]['yearly_qty'] += data.get('yearly_qty',0)
                    data_sale[eternal_product_id]['previous_yearly_qty'] += data.get('previous_yearly_qty',0)
                    data_sale[eternal_product_id]['monthly_qty'] += data.get('monthly_qty',0)
                    data_sale[eternal_product_id]['previous_monthly_qty'] += data.get('previous_monthly_qty',0)

                    if data.get('last_date',False) and not data_sale[eternal_product_id].get('last_date',False):
                        data_sale[eternal_product_id]['last_date'] = data.get('last_date',False)
                    elif data.get('last_date',False) and data.get('last_date',False) > data_sale[eternal_product_id].get('last_date',False):
                        data_sale[eternal_product_id]['last_date'] = data.get('last_date', False)

                    if data.get('previous_date', False) and not data_sale[eternal_product_id].get('previous_date', False):
                        data_sale[eternal_product_id]['previous_date'] = data.get('previous_date', False)
                    elif data.get('previous_date', False) and data.get('previous_date', False) < data_sale[eternal_product_id].get(
                            'previous_date', False):
                        data_sale[eternal_product_id]['previous_date'] = data.get('previous_date',False)


        return data_sale

    #Todo [STK] - Existencia disponible (stock actual) del producto en el almacén
    def get_available_stock_stock_by_warehouse(self, warehouse=False, products=False):
        result = {}
        if not products:
            product_templates = self.get_template_product_suggested()
            products = product_templates.mapped("product_variant_ids")

        if not warehouse:
            warehouse = self.env['stock.warehouse'].search([])



        domain_quant_loc, domain_move_in_loc, domain_move_out_loc = products.with_context(warehouse=warehouse.ids)._get_domain_locations()

        domain_quant = [('product_id', 'in', products.ids)] + domain_quant_loc

        Quant = self.env['stock.quant'].with_context(active_test=False)

        quants_location = Quant.read_group(domain_quant,
                                           ['location_id', 'product_id', 'quantity', 'reserved_quantity'],
                                           ['product_id'], lazy=False)


        for item in quants_location:
            product_id = item['product_id'][0]

            if product_id not in result:
                result[product_id] = {
                    'quantity': 0,
                    'reserved_quantity': 0
                }


            result[product_id]['quantity'] += item['quantity']
            result[product_id]['reserved_quantity'] += item['reserved_quantity']

        return result

    #Todo [MIN] - Existencia mínima deseada del producto en el almacén
    #Todo [MAX] - Existencia máxima deseada del producto en el almacén
    def get_warehouse_orderpoint(self,warehouse=False, products=False):
        result = {}
        if not products:
            product_templates = self.get_template_product_suggested()
            products = product_templates.mapped("product_variant_ids")

        if not warehouse:
            warehouse = self.env['stock.warehouse'].search([])

        OrderPoint = self.env['stock.warehouse.orderpoint']

        _point = OrderPoint.read_group([('warehouse_id', 'in', warehouse.ids),('product_id', 'in', products.ids)],
                         ['product_id', 'product_min_qty', 'product_max_qty'],
                         ['product_id'], lazy=False)

        for item in _point:
            product_id = item['product_id'][0]

            if product_id not in result:
                result[product_id] = {
                    'product_min_qty': 0,
                    'product_max_qty': 0
                }

            result[product_id]['product_min_qty'] += item['product_min_qty']
            result[product_id]['product_max_qty'] += item['product_max_qty']

        return result

    #Todo Ontener Kit del producto, la necesidad y el stock de los mismos
    #Todo data = {
    #  'product_id':
    #     [
    #      {'kit_id': 1,'weight': 0.2,'stock': 100, multiply: 5, 'maximum': 10, 'minimum': 50, 'cost': 1.29, 'name': 'Ejemplo', 'code': '0101010'},
    #      {'kit_id': 23,'weight': 0.5, 'stock': 5, multiply: 5, 'maximum': 10, 'minimum': 50, 'cost': 2.50, 'name': 'Ejemplo', 'code': '0101010'}
    #     ]
    # }
    def get_product_kit(self, warehouse=False, products=False):
        return False

    #Todo [CDT] - Cantidad en tránsito (Cantidad del producto en cuestión que se encuentra en camino a los almacenes para su venta)
    def get_stock_in_transit(self, warehouse=False, products=False):
        data_in_transit = {}

        if not products:
            product_templates = self.get_template_product_suggested()
            products = product_templates.mapped("product_variant_ids")

        if not warehouse:
            warehouse = self.env['stock.warehouse'].search([])

        domain_ = [('product_id','in',products.ids),('warehouse_id', 'in', warehouse.ids),
                   ('state', 'in', ['draft', 'confirmed', 'assigned', 'waiting']),
                   ('picking_type_id.code', '=', 'incoming')
                   ]
        for group in self.env['stock.move'].read_group(domain_, ['product_id', 'product_uom_qty'],
                                                            ['product_id']):
            product_id = group['product_id'][0]
            if product_id not in data_in_transit:
                data_in_transit[product_id] = {
                    'product_in_transit_qty': 0.00,
                }

            data_in_transit[product_id]['product_in_transit_qty'] += group['product_uom_qty']

        return data_in_transit

    # Todo [CDT] - Cantidad en tránsito basada en pedidos de importacion (Cantidad del producto en cuestión que se encuentra en camino a los almacenes para su venta)
    def get_stock_in_transit_for_liquidation_import(self, products=False):
        data_in_transit = {}

        if not products:
            product_templates = self.get_template_product_suggested()
            products = product_templates.mapped("product_variant_ids")

        domain_ = [('product_id', 'in', products.ids), ('is_import','=',True),
                   ('ctdad_pending','>',0),('state','!=','cancel')
                   ]

        for group in self.env['purchase.order.line'].read_group(domain_, ['product_id', 'ctdad_pending'],
                                                       ['product_id']):
            product_id = group['product_id'][0]
            if product_id not in data_in_transit:
                data_in_transit[product_id] = {
                    'product_in_transit_qty': 0.00,
                }

            data_in_transit[product_id]['product_in_transit_qty'] += group['ctdad_pending']

        return data_in_transit

    # Todo [PRV] - Pedidos Reservados (Los pedidos realizados en el sistema que aun no son entregados
    #[Todo] a los clientes pero que cuentan con reserva de mercadería)
    def get_stock_pending_deliver(self, warehouse=False, products=False):
        stock_pending_deliver = {}

        if not products:
            product_templates = self.get_template_product_suggested()
            products = product_templates.mapped("product_variant_ids")

        if not warehouse:
            warehouse = self.env['stock.warehouse'].search([])

        domain_ = [('product_id', 'in', products.ids), ('warehouse_id', 'in', warehouse.ids),
                   ('state', 'in', ['draft', 'confirmed', 'assigned', 'waiting']),
                   ('picking_type_id.code', '=', 'outgoing')
                   ]
        for group in self.env['stock.move'].read_group(domain_, ['product_id', 'product_uom_qty'],
                                                       ['product_id']):
            product_id = group['product_id'][0]
            if product_id not in stock_pending_deliver:
                stock_pending_deliver[product_id] = {
                    'product_stock_pending_deliver': 0.00,
                }

            stock_pending_deliver[product_id]['product_stock_pending_deliver'] += group['product_uom_qty']

        return stock_pending_deliver
    #stock_pending_deliver = self.get_stock_pending_deliver(warehouse=warehouse, products=products)
    #[Todo] obtener las compas locales de un items
    def get_local_purchase(self, products=False):
        stock_local_purchase = {}

        if not products:
            product_templates = self.get_template_product_suggested()
            products = product_templates.mapped("product_variant_ids")


        domain_ = [('product_id', 'in', products.ids),
                   ('order_id.state', 'in', ['purchase','done']),
                   ('order_id.is_import', '=', False)
                   ]
        for group in self.env['purchase.order.line'].read_group(
                domain_, ['product_id', 'qty_received'],
                                                       ['product_id']):
            product_id = group['product_id'][0]
            if product_id not in stock_local_purchase:
                stock_local_purchase[product_id] = {
                    'qty_received': 0.00,
                }

            stock_local_purchase[product_id]['qty_received'] += group['qty_received']

        return stock_local_purchase

    #Todo [DST] - Dias sin stock (Cantidad de dias en el que el producto no se encontró disponible en el rango de fecha seleccionado)
    def get_days_out_of_stock(self, products=False):
        if not products:
            product_templates = self.get_template_product_suggested()
            products = product_templates.mapped("product_variant_ids")

        days_out_of_stock = self.env['ek.days.out.of.stock'].search([('product_id','in',products.ids)])
        result = {}
        for rec in days_out_of_stock:
            result[rec.product_id.id] = rec.days

        return result

    def compute_name_product(self, product,qty_stock=0,cost=0,last_date=False):
        return product.with_context(display_default_code=False).name_get()[0][1]

    def compute_code_product(self, product,qty_stock=0,cost=0,last_date=False):
        if qty_stock == 0 and not last_date:
            return "*** %s" % (product.default_code or '')
        return product.default_code or ''

    def is_new_product(self,product,qty_stock=0,last_date=False):
        return qty_stock == 0 and not last_date

    def is_new_product_object(self):
        return self.qty_stock == 0 and not self.last_date

    @api.model
    def fields_get(self, allfields=None, attributes=None):
        res = super(SuggestedPurchase, self).fields_get(allfields=allfields, attributes=attributes)
        try:
            year = fields.Date.today().year
            month = fields.Date.today().month


            year_filter = int(self.env['ir.config_parameter'].get_param('suggest.default_year_c%s' % self.env.company.id, default=year))
            month_filter = int(self.env['ir.config_parameter'].get_param('suggest.default_month_c%s' % self.env.company.id, default=month))
            year_old_filter = year_filter - 1


            month_str = "%s/%s" % (month_filter < 10 and "0%s" % month_filter or month_filter, year_filter)
            month_str_1 = "%s/%s" % ((month_filter-1) < 10 and "0%s" % (month_filter-1) or (month_filter-1), year_filter)
            month_old_str = "%s/%s" % (month_filter < 10 and "0%s" % month_filter or month_filter, year_old_filter)
            str_salse = _('Ventas')
            res['sales_ytd']['string'] = "%s %s" % (str_salse,year_filter)
            res['sales_month']['string'] = "%s %s" % (str_salse,month_str)
            res['sales_1_month']['string'] = "%s %s" % (str_salse,month_str_1)

            res['sales_year_old']['string'] = "%s %s" % (str_salse,year_old_filter)
            res['sales_year_old_month']['string'] = "%s %s" % (str_salse,month_old_str)
        except Exception as ex:
            print(ex.__str__())

        return res

    def get_sales_related(self, result_suggest_purchase={}):
        sum_for_template = {}
        detail_for_template={}
        for line in result_suggest_purchase.values():
            product_tmpl_id = line.get('product_tmpl_id', False)
            name = line.get('name', '')
            default_code = line.get('default_code', '')
            product_name = "[%s] %s" % (default_code,name)
            if product_tmpl_id:
                if product_tmpl_id not in sum_for_template:
                    sum_for_template[product_tmpl_id] = 0
                if product_tmpl_id not in detail_for_template:
                    detail_for_template[product_tmpl_id] = {}
                if product_name not in detail_for_template[product_tmpl_id]:
                    detail_for_template[product_tmpl_id][product_name] = 0.00

                detail_for_template[product_tmpl_id][product_name] += line.get('sales_ytd',0.00)
                sum_for_template[product_tmpl_id] += line.get('sales_ytd',0.00)
        return (sum_for_template,detail_for_template)



    @api.model
    def generate_suggest_purchase(self, warehouse=False,aditional_sale_or_cosume_products={},provider_ids=[],
                                  method='cost', date_order=False,date_filter=False, only_suggest=False,
                                  day_with_last_date=False, product_with_last_date=False,product_out_of_stock=False,
                                  categ_ids=False, type='sale', auto=False, date=False,round_type=False,precision_digits=False,only_partner=False, based_in_liquidation=False,type_sale_qty='product_uom_qty'):
        for rec in self.create({}):
            number = self.env['ir.sequence'].next_by_code('ek.suggested.purchase') or '/'
            date_filter = not date_filter and fields.Date.today() or date_filter
            year = date_filter and date_filter.year or fields.Date.today().year
            month =date_filter and date_filter.month or fields.Date.today().month
            product_templates = self.get_template_product_suggested(categ_ids=categ_ids)
            transit_days = self.get_transit_days(template_ids=product_templates, provider_ids=provider_ids,only_partner=only_partner)
            products = product_templates.mapped("product_variant_ids").filtered(lambda a: a.id in transit_days.keys() and a.allow_suggested_product == True and a.detailed_type == 'product')
            all_product_for_stock = product_templates.mapped("product_variant_ids")


            if not auto and not products:
                raise ValidationError(_("No se encontraron productos para los parámetros seleccionados"))

            if not date_order:
                date_order = fields.Date.today()
            min_and_max = self.get_warehouse_orderpoint(warehouse=warehouse, products=products)
            available_stock = self.get_available_stock_stock_by_warehouse(warehouse=warehouse, products=all_product_for_stock)
            sales_data = self.get_sale_yearly_and_monthly(products=all_product_for_stock, year=year, month=month,type=type, external_data=aditional_sale_or_cosume_products, date=date,type_sale_qty=type_sale_qty)
            inventory_valuate = self.get_cost_of_goods_sold(products=products, year=year, date=date)

            if based_in_liquidation:
                stock_in_transit = self.get_stock_in_transit_for_liquidation_import(products=all_product_for_stock)
            else:
                stock_in_transit = self.get_stock_in_transit(warehouse=warehouse, products=all_product_for_stock)
            stock_pending_deliver = self.get_stock_pending_deliver(warehouse=warehouse, products=products)
            days_out_of_stock = self.get_days_out_of_stock(products=products)
            best_supplier = self.get_best_supplier(method=method, template_ids=product_templates, provider_ids=provider_ids,only_partner=only_partner)
            kits = self.get_product_kit(warehouse=warehouse, products=products)
            local_products = self.get_local_purchase(products=all_product_for_stock)


            result_suggest_purchase = {}
            for product in products:
                qty_stock_related = 0
                qty_sale_related = 0
                qty_transit_related = 0
                product_order_point = min_and_max.get(product.id,False)
                product_available_stock = available_stock.get(product.id,False)
                #data relates for stock related
                related_stock_ids = []
                related_sales_ids = []
                related_transit_ids = []
                for pt in product.product_tmpl_id.product_variant_ids:
                    if pt.id != product.id:
                        related_available_stock = available_stock.get(pt.id,False)
                        if related_available_stock:
                            quantity = related_available_stock.get('quantity', 0.00)
                            qty_stock_related += quantity
                            related_stock_ids.append((0,0,{
                                'product_name': pt.display_name,
                                'quantity': quantity
                            }))
                        related_sales = sales_data.get(pt.id, False)
                        if related_sales:
                            sales_ytd = related_sales.get('yearly_qty', 0.00)
                            qty_sale_related += sales_ytd
                            related_sales_ids.append((0, 0, {
                                'product_name': pt.display_name,
                                'quantity': sales_ytd
                            }))
                        transit_related_disct = stock_in_transit.get(pt.id, False)
                        if transit_related_disct:
                            transit_related_ytd = transit_related_disct.get('product_in_transit_qty', 0.00)
                            qty_transit_related += transit_related_ytd
                            related_transit_ids.append((0, 0, {
                                'product_name': pt.display_name,
                                'quantity': transit_related_ytd
                            }))


                product_sales_data = sales_data.get(product.id,False)
                product_stock_in_transit = stock_in_transit.get(product.id,False)
                product_stock_pending_deliver = stock_pending_deliver.get(product.id,False)
                product_days_out_of_stock = days_out_of_stock.get(product.id,0)
                product_transit_days = best_supplier.get(product.id,False)
                product_inventory_valuate = inventory_valuate.get(product.id,False)
                last_date = product_sales_data and product_sales_data.get('last_date', False)
                last_purchase = product_sales_data and product_sales_data.get('last_purchase', False)
                previous_date = product_sales_data and product_sales_data.get('previous_date', False)
                qty_suggested = 0.00
                day_transit = product_transit_days and product_transit_days.get('default_days', 1)
                local_product_total = 0
                for xlocal in product.product_tmpl_id.product_variant_ids:
                    local_product = local_products.get(xlocal.id,False)
                    if local_product:
                        local_product_total += local_product.get('qty_received', 0)

                if hasattr(product, 'amount_fob') and product.amount_fob > 0.01:
                    last_cost = product.amount_fob
                elif hasattr(product,'last_cost') and product.last_cost > 0.01:
                    last_cost = product.last_cost
                else:
                    last_cost = product.standard_price
                cost = product_transit_days and product_transit_days.get('default_price', product.standard_price) or product.standard_price
                provider_id = product_transit_days and product_transit_days.get('default_partner_id', False)
                qty_stock = product_available_stock and product_available_stock.get('quantity', 0.00)
                maximum = product_order_point and product_order_point.get('product_max_qty', 0.00)
                minimum = product_order_point and product_order_point.get('product_min_qty', 0.00)
                transit = product_stock_in_transit and product_stock_in_transit.get('product_in_transit_qty', False)
                VAP = product_sales_data and product_sales_data.get('previous_yearly_qty', 0.00)
                VMP = product_sales_data and product_sales_data.get('previous_monthly_qty', 0.00)
                MTA = self.get_months_elapsed(month)
                PRV = product_stock_pending_deliver and product_stock_pending_deliver.get('product_stock_pending_deliver',0.00)
                DDT = product_transit_days and product_transit_days.get('default_days', 0)
                VAA = product_sales_data and product_sales_data.get('yearly_qty', 0.00)
                YTD = product_sales_data and product_sales_data.get('calendar_yearly_qty', 0.00)
                # Todo [FD] Factor Diario = Promedio([VAP/365];[VMP/30];[VAA/MTA/30])
                # Todo F(y) = (FD * DDT) + (FD * DST)
                x1 = VAP / 365
                x2 = VMP / 30
                x3 = VAA / MTA / 30
                FD_day_factor = (x1 + x2 + x3) / 3
                stock_for_relivery = (PRV - qty_stock) > 0 and (PRV - qty_stock) or 0
                #Todo calcular maximo dinamico si no esta establecido
                if not maximum:
                    _max = ((qty_stock - PRV) + transit) - (FD_day_factor * (DDT or 1))
                    if _max < 0:
                        maximum =  float_round(abs(_max), precision_digits=0,rounding_method='HALF-UP') or 0.00
                        minimum = 1
                # Todo F(x) = (MAX - STK) - CDT + PRV
                F_x = (maximum - qty_stock) - transit + PRV

                if F_x > 0:
                    F_x = float_round(F_x, precision_digits=0,rounding_method='HALF-UP') or 0.00
                else:
                    F_x = 0


                F_y = (FD_day_factor * (DDT or 1)) + (FD_day_factor * product_days_out_of_stock) + stock_for_relivery

                if F_y > 0:
                    F_y = float_round(F_y, precision_digits=0, rounding_method='HALF-UP') or 0.00
                else:
                    F_y = 0

                #if only_suggest and qty_suggested <= 0:
                #    continue


                if product_with_last_date:
                    if not last_date:
                        continue
                    if day_with_last_date and day_with_last_date > 0:
                        days_pased = (date_filter - last_date).days
                        if not last_date:
                            continue
                        if days_pased > day_with_last_date:
                            continue

                if product_out_of_stock and qty_stock > 0:
                    continue

                if provider_ids and not provider_id:
                    continue


                sale_avg_month = self.get_product_sale_avg_month(date, product_days_out_of_stock or 0, VAA)
                over_stock = False
                if sale_avg_month <= 0 and qty_stock > 0:
                    over_stock = True
                elif qty_stock > 0 and (qty_stock/sale_avg_month) >= 15:
                    over_stock = True

                sample_months = 0
                if last_date and previous_date:
                    sample_months = (last_date - previous_date).days / 30

                sales_month = product_sales_data and product_sales_data.get('monthly_qty', 0.00) or 0.00
                sales_1_month = product_sales_data and product_sales_data.get('sales_1_month', 0.00) or 0.00
                check_sales = 'equal'
                if sales_1_month > sales_month:
                    check_sales = 'higher'
                elif sales_1_month < sales_month:
                    check_sales = 'minor'

                #code_tmpl_ids
                default_code2 = ''
                default_code3 = ''
                if hasattr(product.product_tmpl_id, "code_tmpl_ids"):

                    i = 0
                    for code in product.product_tmpl_id.code_tmpl_ids:
                        if i == 0:
                            i += 1
                            continue
                        if i == 1:
                            default_code2 = code.name
                        if i == 2:
                            default_code3 = code.name

                        i+=1






                result_suggest_purchase[product.id] = {
                    'number': number,
                    'multiplicity': product.product_tmpl_id.multiplicity,
                    'company_id': self.env.company.id,
                    'product_id': product.id,
                    'product_uom_id': product.uom_po_id.id,
                    'product_tmpl_id': product.product_tmpl_id.id,
                    'partner_id': provider_id,
                    'qty_stock': qty_stock, #reserved_quantity
                    'qty_stock_related': qty_stock_related,  # reserved_quantity
                    'related_stock_ids': related_stock_ids,
                    'related_sales_ids': related_sales_ids,
                    'sales_related': qty_sale_related,
                    'qty_pending_deliver': PRV, #reserved_quantity
                    'sales_ytd': VAA,
                    'calendar_yearly_qty': YTD,
                    'sales_month': sales_month,
                    'sales_1_month': sales_1_month,
                    'check_sales': check_sales,
                    'sales_esp': 0,
                    'sales_year_old': VAP,
                    'sales_year_old_month': VMP,
                    'previous_date': previous_date,
                    'last_date': last_date,
                    'last_purchase': last_purchase,
                    'purchase_local': local_product_total,
                    'transit': product_stock_in_transit and product_stock_in_transit.get('product_in_transit_qty',False),
                    'transit_related': qty_transit_related,
                    'related_transit_ids': related_transit_ids,
                    'day_not_stock': product_days_out_of_stock or 0,
                    'maximum': maximum,
                    'minimum': minimum,
                    'day_transit': DDT,
                    'over_stock': over_stock,
                    'sample_months': sample_months,
                    'month_transit': DDT/30,
                    #'required_qty_stock': 1 ,
                    'projected_sales': float_round(self.get_months_ends(date) * sale_avg_month, precision_digits=precision_digits,rounding_method=round_type),
                    #'qty_suggested': over_stock and 0.00 or qty_suggested,
                    'arrival_date': (date_order + timedelta(days=day_transit)),
                    'date': date,
                    'cost': cost,
                    'last_cost': last_cost == 0 and cost or last_cost,
                    'weight': product.weight,
                    #'investment': cost * qty_suggested,
                    #'total_weight': product.weight * qty_suggested,
                    'name': self.compute_name_product(product,qty_stock,cost,last_date),
                    'default_code': self.compute_code_product(product,qty_stock,cost,last_date),
                    'default_code2': default_code2,
                    'default_code3': default_code3,
                    'kit_id': False,
                    'cost_sale_inventory': product_inventory_valuate and product_inventory_valuate.get('valuate',0.00),
                    'f_x': F_x,
                    'f_y': F_y
                }


            if provider_ids:
                self.search([('company_id', '=', self.env.company.id),('create_uid', '=', self.env.user.id),('partner_id','in',provider_ids)]).sudo().unlink()
            else:
                self.search(
                    [('company_id', '=', self.env.company.id),('create_uid', '=', self.env.user.id)]).sudo().unlink()
            self.env['ek.suggested.purchase.kit'].search([('company_id', '=', self.env.company.id)]).sudo().unlink()


            data_create = []

            (sale_related,detail_for_template) = self.get_sales_related(result_suggest_purchase)
            lines_suggest = self.env['ek.suggested.purchase']
            for line in result_suggest_purchase.values():
                product_kits = []

                if kits:
                    product_kits = kits.get(line.get('product_id'), [])
                    if product_kits:
                        KIT = self.env['ek.suggested.purchase.kit'].create({'name': line.get('name'), 'partner_id': line.get('partner_id',False)})
                        line.update({'product_base': True})
                        line.update({'kit_id': KIT.id})

                lines_suggest |= self.create(line)

                #TODO Creando productos addiciones para complementar la necesidad de kits
                #Todo data = {'product_id': [{'kit_id': 1,'weight': 0.2,'stock': 100, multiply: 5, 'maximum': 10, 'minimum': 50, 'cost': 1.29, 'name': 'Ejemplo', 'code': '0101010'},{'kit_id': 23,'weight': 0.5, 'stock': 5, multiply: 5, 'maximum': 10, 'minimum': 50, 'cost': 2.50, 'name': 'Ejemplo', 'code': '0101010'}]}
                for _kit in product_kits:
                    #TODO Buscando si el producto del kit se encuntra ya dentro del sugerido
                    kit_exist_in_suggest = result_suggest_purchase.get(_kit.get('kit_id',False),False)

                    if kit_exist_in_suggest:
                        c_kit = kit_exist_in_suggest.copy()

                        c_kit.update({
                            'product_base': False,
                            'qty_suggested': line.get('qty_suggested',0) * _kit.get('multiply',1),
                            'multiply': _kit.get('multiply',1)
                        })

                    else:
                        c_kit = line.copy()

                        c_kit.update({
                            'product_base': False,
                            'qty_stock' : _kit.get('stock',0),
                            'product_id': _kit.get('kit_id',False),
                            'qty_suggested': line.get('qty_suggested',0) * _kit.get('multiply',1),
                            'qty_pending_deliver': 0,
                            'sales_ytd': 0,
                            'sales_month': 0,
                            'sales_esp': 0,
                            'sales_year_old': 0,
                            'sales_year_old_month': 0,
                            'cost_sale_inventory': 0,
                            'last_date': False,
                            'purchase_local': 0,
                            'transit': 0,
                            'day_not_stock': 0,
                            'maximum': _kit.get('maximum',0),
                            'minimum': _kit.get('minimum',0),
                            'cost': _kit.get('cost',0),
                            'weight': _kit.get('weight',0),
                            'name': _kit.get('name',''),
                            'default_code': _kit.get('code',''),
                            'multiply': _kit.get('multiply', 1)
                        })
                    self.create(c_kit)


            #Todo Calulate suggest
            lines_suggest.calculate_master_suggest(round_type=round_type,precision_digits=precision_digits)