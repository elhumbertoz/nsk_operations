from odoo import fields, models, api, _
from ast import literal_eval

class ek_purchase_adjustment_factor(models.Model):
    _name = 'ek.purchase.adjustment.factor'
    _description = _('Purchase Adjustment Factor')
    _order = 'sequence, id'

    name = fields.Char('Code')
    factor = fields.Float(
        string='Factor', 
        required=False)

    month_security = fields.Integer(
        string='Meses de Seguridad',
        required=False)

    filter = fields.Char(string="Filter")
    
    sequence = fields.Integer(
        string='Sequence', 
        required=False, default=10)

    def get_factor(self, stock, date_first_sale,date_last_sale, sale_actual_month, sale_last_month):
        for rec in self:
            factror = 0
            code = ''

            
    def evaluate_factor(self,exclude=[]):
        factor =self
        if factor.filter:
            domain = literal_eval(factor.filter)
            if exclude:
                domain.append(('id','not in',exclude))

            return self.env['ek.suggested.purchase'].search_read(domain, ['id'])
        else:
            return False

    def list_suggeted_by_factors(self):
        result = {}
        exclude_suggested = []
        for rec in self.search([]):
            if rec.filter:
                suggest = rec.evaluate_factor(exclude_suggested)
                ids = [s.get('id',0) for s in suggest]
                for s in ids:
                    result[s] = rec
                exclude_suggested.extend(ids)

        return result