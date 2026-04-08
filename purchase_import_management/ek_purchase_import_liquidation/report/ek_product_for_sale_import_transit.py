from odoo import fields, models, api,tools


class ek_product_for_sale_import_transit(models.Model):
    _name = "ek.product.for.sale.import.transit"
    _description = "Capacidad de endeudamiento"
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

    partner_ref = fields.Char(
        string='Ref. Proveedor',
        required=False)

    order_id = fields.Many2one(
        comodel_name='purchase.order',
        string='Orden',
        readonly=True)

    line_id = fields.Many2one(
        comodel_name='purchase.order.line',
        string='Linea',
        readonly=True)

    liquidation_order_id = fields.Many2one(
        comodel_name='ek.import.liquidation',
        string='Importación',
        readonly=True)

    picking_type_id = fields.Many2one(
        comodel_name='stock.picking.type',
        string='Recibir en',
        readonly=True)

    product_id = fields.Many2one(
        comodel_name='product.product',
        string='Producto',
        readonly=True)

    product_tmpl_id = fields.Many2one(
        comodel_name='product.template',
        string='Plantilla Producto',
        readonly=True)

    date_approve = fields.Date('Fecha Pedido', readonly=True)
    arrival_date = fields.Date('Fecha Aprox. de Llegada', readonly=True)

    product_qty = fields.Float('Ctdad. Pedida', readonly=True)
    qty_received = fields.Float('Ctdad. Recibida', readonly=True)
    qty_pending = fields.Float('Ctdad. Pendiente', readonly=True)
    qty_in_transit = fields.Float('Ctdad. Transito', readonly=True)

    days_late = fields.Integer('Dias de Atraso', readonly=True)

    company_id = fields.Many2one(
        comodel_name='res.company',
        string='Compañía',
        required=False,readonly=True)

    def _select(self, fields=None):
        if not fields:
            fields = {}
        select_ = """
                ROW_NUMBER () OVER (ORDER BY pol.id) AS  id,
                po.name,
                po.partner_id,
                po.company_id,
                po.partner_ref,
                pol.order_id,
                pol.id as line_id,
                po.picking_type_id, --Lugar de recepcion
                po.date_approve::date, --Fecha de pedido
                pol.product_id,
                pp.product_tmpl_id,
                pol.product_qty, --Cantidad pedida
                pol.qty_received, -- Cantidad recibida en bodega
                (pol.product_qty - pol.qty_received) as qty_pending, --Cantidad Pendiente
                coalesce(ill.product_qty,0) as qty_in_transit, --Cantidad en transito
                coalesce(ill.arrival_date,pol.date_planned)::date as arrival_date, --Fecha de llegada
                ill.liquidation_order_id,
                (CASE 
                  WHEN ill.arrival_date IS NOT NULL AND date_part('day', age(now(),ill.arrival_date)) > 0 THEN date_part('day', age(now(),ill.arrival_date))
                  WHEN pol.date_planned IS NOT NULL AND date_part('day', age(now(),pol.date_planned)) > 0 THEN date_part('day', age(now(),pol.date_planned))
                  ELSE 0 
                 END) AS days_late               
            """

        for field in fields.values():
            select_ += field
        return select_

    def _from(self, from_clause=''):
        from_ = """
                     purchase_order_line pol
                      JOIN purchase_order po ON po.id = pol.order_id
                      JOIN product_product pp ON pol.product_id = pp.id
                      JOIN product_template pt ON pp.product_tmpl_id = pt.id
                      LEFT JOIN (
                            SELECT 
                                ill.purchase_line_id, 
                                ill.product_qty, 
                                ill.product_id, 
                                il.arrival_date,
                                il.id as liquidation_order_id            
                               FROM  ek_import_liquidation_line ill
                               JOIN ek_import_liquidation il ON ill.order_id = il.id
                               LEFT JOIN stock_picking sp ON il.id = sp.liquidation_id AND sp.state != 'cancel'
                               WHERE (sp.state IS NULL OR sp.state != 'done') AND il.state not in ('draft','cancel')
                      ) ill ON ill.purchase_line_id = pol.id                  
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
        return "%s (SELECT %s FROM %s WHERE po.is_import = true AND pt.sale_ok = true AND pol.qty_received < pol.product_qty AND po.state in ('purchase'))" % \
               (with_, self._select(fields), self._from(from_clause))

    def init(self):
        # self._table = sale_report
        tools.drop_view_if_exists(self.env.cr, self._table)
        self.env.cr.execute("""CREATE or REPLACE VIEW %s as (%s)""" % (self._table, self._query()))


