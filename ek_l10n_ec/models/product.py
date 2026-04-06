
from odoo import fields, models


class ProductTemplate(models.Model):
    _inherit = 'product.template'
   
    l10n_ec_auxiliary_code = fields.Char(
        string='Auxiliary Code',
        help='Ecuador: add an optional code for electronic documents under <codigoAuxiliar> for all products, including construction products as listed in Table 31 of the technical data sheet for 2024.',
    )