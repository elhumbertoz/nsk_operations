from odoo import fields, models, api,_
from odoo.exceptions import ValidationError
from datetime import timedelta, time

class generate_purchase_suggest_wizard(models.TransientModel):
    _name = 'ek.generate.purchase.suggest.wizard'
    _description = _('Generar Sugerido de compras')

    partner_id = fields.Many2one(
        comodel_name='res.partner',
        string=_('Proveedor'),
        required=False)

    categ_ids = fields.Many2many(
        comodel_name='product.category',
        string=_('Categorías'),
        required=False)

    product_out_of_stock = fields.Boolean(#OK
        string=_('Productos sin stock'),
        required=False)

    product_with_last_date = fields.Boolean(#OK
        string=_('Productos con movimientos'),
        required=False)
    
    day_with_last_date = fields.Integer(
        string=_('Dias de movimiento'),
        required=False, default=365)

    all_product = fields.Boolean(#OK
        string=_('Todos los productos'),
        required=False)

    product_with_suggested = fields.Boolean(#OK
        string=_('Productos Sugeridos'),
        required=False)

    date = fields.Date(#OK
        string=_('Fecha de Corte'),
        required=False, default=fields.Date.today())

    date_order = fields.Date(#OK
        string=_('Fecha de Pedido'),
        required=False, default=fields.Date.to_date(fields.Date.today() + timedelta(days=15)))

    warehouse_ids = fields.Many2many(#OK
        comodel_name='stock.warehouse',
        string=_('Almacenes'))

    method = fields.Selection(#OK
        string=_('Clasificación de proveedores'),
        selection=[('cost', _('Menor Costo')),
                   ('time', _('Menor Tiempo')),
                   ('balanced', _('Ponderado')),
                   ],
        required=False, default='cost')

    type = fields.Selection(  # OK
        string=_('Tipo de Sugerido'),
        selection=[('sale', _('Basado en Ventas')),
                   ],
        required=False, default='sale')

    type_sale_qty = fields.Selection(  # OK
        string=_('Cantidad a considerar'),
        selection=[('product_uom_qty', _('Basado en cantidad ordenada')),
                   ('qty_delivered', _('Basado en cantidad despachada')),
                   ('qty_invoiced', _('Basado en cantidad facturada')),
                   ],
        required=False, default='product_uom_qty')

    round_type = fields.Selection(
        string='Tipo de Redondeo',
        selection=[('HALF-UP', 'A LA MITAD'),
                   ('UP', 'EXCESO'),
                   ('DOWN', 'POR DEFECTO'),],
        required=False, default='UP')

    precision_digits = fields.Integer(
        string='Dígitos de Precisión',
        required=False, default=0)

    only_partner = fields.Boolean(
        string='Proveedor Estricto',
        required=False, help="Solo se mostraran los productos que tengan seleccionada en la variante "
                             "el proveedor seleccionado y/o cualquiera de sus contactos relacionados")
    based_in_liquidation = fields.Boolean(
        string='Transito basado en Importaciones',
        required=False, help="Revisa los pedidos en transito que sean solamente importaciones y obtiene los valores pendientes.")

    @api.onchange('all_product')
    def onchange_all_product(self):
        for rec in self:
            rec.update({
                'product_out_of_stock': False,
                'product_with_last_date': False,
                'product_with_suggested': False,
            })


    def action_create_suggest(self):
        for rec in self:
            #
            self.env['ir.config_parameter'].sudo().set_param('suggest.default_year_c%s' % self.env.company.id, rec.date.year)
            self.env['ir.config_parameter'].sudo().set_param('suggest.default_month_c%s' % self.env.company.id, rec.date.month)
            self.env['ir.config_parameter'].sudo().set_param('suggest.default_date_order_c%s' % self.env.company.id, rec.date_order)
            self.env['ir.config_parameter'].sudo().set_param('suggest.default_type_c%s' % self.env.company.id, rec.type)
            self.env['ir.config_parameter'].sudo().set_param('suggest.default_round_type_c%s' % self.env.company.id,rec.round_type)
            self.env['ir.config_parameter'].sudo().set_param('suggest.default_precision_digits_c%s' % self.env.company.id,
                                                             rec.precision_digits)
            provider_ids = []
            if self.partner_id:
                provider_ids.append(self.partner_id.id)
                provider_ids.extend(self.partner_id.child_ids.ids)
                #if self.partner_id.child_ids:
                #    for partner in self.partner_id.child_ids:
                #        provider_ids.append(partner)

            self.env['ek.suggested.purchase'].generate_suggest_purchase(
                warehouse=rec.warehouse_ids,
                aditional_sale_or_cosume_products={},
                provider_ids=provider_ids,
                method=rec.method,
                date_order=rec.date_order,
                date_filter=rec.date,
                only_suggest=rec.product_with_suggested,
                day_with_last_date=rec.day_with_last_date,
                product_with_last_date=rec.product_with_last_date,
                product_out_of_stock=rec.product_out_of_stock,
                categ_ids=rec.categ_ids,
                type=rec.type,
                date=rec.date,
                round_type=rec.round_type,
                precision_digits=rec.precision_digits,
                only_partner=rec.only_partner,
                based_in_liquidation=rec.based_in_liquidation,
                type_sale_qty=rec.type_sale_qty)

            return self.env["ir.actions.actions"]._for_xml_id("base_suggested_purchase.action_ek_purchase_suggested_report_act_id")
            #return {'type': 'ir.actions.act_window_close'}


