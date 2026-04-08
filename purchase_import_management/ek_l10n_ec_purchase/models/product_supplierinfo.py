from odoo import fields, models


class ProductSupplierinfo(models.Model):
    _inherit = "product.supplierinfo"

    # Index partner_id
    partner_id = fields.Many2one(index=True)