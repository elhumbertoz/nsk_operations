from odoo import fields, models, api,_
from odoo.exceptions import ValidationError


class SuggestedPurchaseHistoryMaster(models.Model):
    _name = 'ek.suggested.purchase.history.master'
    _description = _('Suggested Purchase History Master')
    
    sales_year = fields.Integer(
        string=_('Sale Year'),
        required=True, default=fields.Date.today().year)
    product_id = fields.Many2one(
        comodel_name='product.product',
        string=_('Product'),
        required=True, domain="[('allow_suggested','=',True),('purchase_ok','=',True),('detailed_type','=','product')]")

    sale_1 = fields.Float(string=_('Sale_01'),required=True, default=0)
    sale_2 = fields.Float(string=_('Sale_02'), required=True, default=0)
    sale_3 = fields.Float(string=_('Sale_03'), required=True, default=0)
    sale_4 = fields.Float(string=_('Sale_04'), required=True, default=0)
    sale_5 = fields.Float(string=_('Sale_05'), required=True, default=0)
    sale_6 = fields.Float(string=_('Sale_06'), required=True, default=0)
    sale_7 = fields.Float(string=_('Sale_07'), required=True, default=0)
    sale_8 = fields.Float(string=_('Sale_08'), required=True, default=0)
    sale_9 = fields.Float(string=_('Sale_09'), required=True, default=0)
    sale_10 = fields.Float(string=_('Sale_10'), required=True, default=0)
    sale_11 = fields.Float(string=_('Sale_11'), required=True, default=0)
    sale_12 = fields.Float(string=_('Sale_12'), required=True, default=0)
    sale_total = fields.Float(string=_('Total Sale'), required=False, readonly=True,compute="_compute_sales_total")

    @api.model
    def _get_depends_fields(self):
        dp = []
        for i in range(1,13):
            dp.append('sale_%s' % i)
        return dp

    @api.depends(lambda self: self._get_depends_fields())
    def _compute_sales_total(self):
        for rec in self:
            total_sale = 0
            for i in range(1, 13):
                attrib = 'sale_%s' % i
                if hasattr(rec, attrib):
                    total_sale += getattr(rec,attrib)

            rec.update({'sale_total': total_sale})

    # @api.constrains(lambda self: self._get_depends_fields())
    # def _compute_check_values(self):
    #     for rec in self:
    #         for i in range(1, 13):
    #             attrib = 'sale_%s' % i
    #             if hasattr(rec, attrib):
    #                 sale = getattr(rec, attrib)
    #                 if sale < 0:
    #                     raise ValidationError("No puede establecer valores negativos en ventas")

    def get_total_up_to_specific_month(self, month):
        self.ensure_one()
        rec = self
        total_sale = 0
        month+=1
        for i in range(1, month):
            attrib = 'sale_%s' % i
            if hasattr(rec, attrib):
                total_sale += getattr(rec, attrib)

        return total_sale

    def get_total_specific_month(self, fisth_month,end_month):
        self.ensure_one()
        rec = self
        total_sale = 0
        end_month+=1
        for i in range(fisth_month, end_month):
            attrib = 'sale_%s' % i
            if hasattr(rec, attrib):
                total_sale += getattr(rec, attrib)

        return total_sale


    _sql_constraints = [
        ('model_unique',
         'unique(sales_year,product_id)',
         u'No es posible detallar las ventas de un productos más de una vez en el mismo año.'),
        ('year_conditional_required',
         "CHECK( sales_year > 2000 )",
         u"El año no está correcto, debe ser mayor a 2000."),
    ]