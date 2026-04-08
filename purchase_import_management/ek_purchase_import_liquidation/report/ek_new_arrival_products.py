from odoo import fields, models, api,tools


class ek_new_arrival_products(models.Model):
    _name = "ek.new.arrival.product"
    _description = "Productos llegados en los últimos 90 dias"
    _auto = False
    _rec_name = 'product_id'
    _order = 'product_id asc'

    name = fields.Char(
        string='Ref. Pedido',
        required=False)

    partner_id = fields.Many2one(
        comodel_name='res.partner',
        string='Proveedor',
        readonly=True)

    product_id = fields.Many2one(
        comodel_name='product.product',
        string='Producto',
        readonly=True)

    date_done = fields.Date('Fecha Llegada', readonly=True)
    qty_done = fields.Float('Cantidad. Importada', readonly=True)
    qty_stock = fields.Float('Cantidad a mano', readonly=True)
    reserved = fields.Float('Comprometido', readonly=True)
    available = fields.Float('Cantidad disponible', readonly=True)
    price = fields.Float('Precio de Venta', readonly=True, digits=(10,4))

    company_id = fields.Many2one(
        comodel_name='res.company',
        string='Compañía',
        required=False,readonly=True)

    def _select(self, fields=None):
        if not fields:
            fields = {}
        select_ = """
                ROW_NUMBER () OVER (ORDER BY tbl_arrival.id) AS  id,
                tbl_arrival.product_id,
                tbl_arrival.name,
                tbl_arrival.company_id,
                tbl_arrival.qty_done,
                tbl_arrival.date_done,
                tbl_arrival.partner_id,
                pt.list_price AS price,
                tbl_arrival.stock_before,
                sq.quantity as qty_stock,
                sq.reserved_quantity as reserved,
                (sq.quantity - sq.reserved_quantity) as available                           
            """

        for field in fields.values():
            select_ += field
        return select_

    def _from(self, from_clause=''):
        # TODO: Permisos pendientes:
        # payment_new_arrival_products_manager,ek.new.arrival.product,model_ek_new_arrival_product,sales_team.group_sale_manager,1,1,1,1
        # payment_new_arrival_products_salesman_all_leads,ek.new.arrival.product,model_ek_new_arrival_product,sales_team.group_sale_salesman_all_leads,1,1,1,1
        # payment_new_arrival_products_team_manager,ek.new.arrival.product,model_ek_new_arrival_product,sales_team.group_sale_salesman_all_leads,1,1,1,1
        # payment_new_arrival_products_sale_salesman,ek.new.arrival.product,model_ek_new_arrival_product,sales_team.group_sale_salesman,1,1,1,1

        # TODO: El campo sml.qty_done aún sigue en stock.move.line, pero ahora ya no es parte del modelo principal sino que se lo agrega en la herencia
        #  dentro del módulo stock_barcode por lo que no estoy seguro si sería correcto ahora agregar la dependencia en el __manifest__, es decir, hacer
        #  que dependa de otro módulo más solo por ese campo.
        from_ = """
                     (SELECT 
                        sp.origin as name,
                        sml.id,
                        sml.company_id,
                        sml.product_id,
                        sml.qty_done,
                        sp.date_done,
                        sp.partner_id,
                        pp.product_tmpl_id,
                        now()::date as today,
                        coalesce((
                           SELECT SUM(xsq.quantity) FROM stock_quant xsq,stock_location xsl 
                           WHERE xsq.product_id = sml.product_id 
                           AND xsq.in_date < (sp.date_done - INTERVAL '5 hours')
                           AND xsq.location_id = xsl.id 
                           AND xsq.company_id = sml.company_id 
                           AND xsl.usage = 'internal'),0) as stock_before
                       FROM 
                       stock_move_line sml 
                       JOIN stock_picking sp ON sml.picking_id = sp.id
                       JOIN product_product pp ON sml.product_id = pp.id
                       WHERE sp.liquidation_id IS NOT NULL  AND sp.state = 'done'
                       AND (sp.date_done + INTERVAL '90 days')::date >= now()::date --Solo movimientos arribos de los 90 dias
                     ) tbl_arrival
                     JOIN product_template pt ON tbl_arrival.product_tmpl_id = pt.id
                     LEFT JOIN   
                        (SELECT 
                           SUM(xsq.quantity) as quantity,
                           SUM(xsq.reserved_quantity) as reserved_quantity,
                           xsq.product_id,
                           xsq.company_id
                           FROM stock_quant xsq 
                            JOIN stock_location sl ON xsq.location_id = sl.id AND sl.usage = 'internal'
                            GROUP BY xsq.product_id,xsq.company_id
                        ) sq ON sq.product_id = tbl_arrival.product_id       
                                       
                    %s
            """ % from_clause
        return from_

    def _group_by(self, groupby=''):
        groupby_ = """
                
                %s
            """ % (groupby)
        return groupby_

    def _query(self, with_clause='', fields=None, groupby='', from_clause=''):
        if not fields:
            fields = {}
        with_ = ("WITH %s" % with_clause) if with_clause else ""
        return "%s (SELECT %s FROM %s WHERE tbl_arrival.stock_before <= 0 AND pt.sale_ok = true AND sq.company_id = tbl_arrival.company_id)" % \
               (with_, self._select(fields), self._from(from_clause))

    def init(self):
        # self._table = sale_report
        tools.drop_view_if_exists(self.env.cr, self._table)
        self.env.cr.execute("""CREATE or REPLACE VIEW %s as (%s)""" % (self._table, self._query()))


