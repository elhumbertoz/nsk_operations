from odoo import fields, models, api


class ResCompany(models.Model):
    _inherit = 'res.company'

    apply_taxes_cost = fields.Boolean(
        string='Aplicar impuestos al costo',
        help="Aplica el valor de los impuestos al costo del producto, generalmente esta practica es usada por empresas \n"
             "que venden con iva 0% pero que sus compras de bienes son castigadas con el iva 12%. \n"
             "Existe una norma del SRI que permite esta figura y el sistema permite su aplicación.",
        required=False)

    procured_purchase_grouping = fields.Selection(
        [
            ("standard", "Standard grouping"),
            ("line", "No line grouping"),
            ("order", "No order grouping"),
            ("product_category", "Product category grouping"),
        ],
        default="standard",
        help="Select the behaviour for grouping procured purchases for the "
             "the products of this category:\n"
             "* Standard grouping: Procurements will generate "
             "purchase orders as always, grouping lines and orders when "
             "possible.\n"
             "* No line grouping: If there are any open purchase order for "
             "the same supplier, it will be reused, but lines won't be "
             "merged.\n"
             "* No order grouping: This option will prevent any kind of "
             "grouping.\n"
             "* <empty>: If no value is selected, system-wide default will be used.\n"
             "* Product category grouping: This option groups products in the "
             "same purchase order that belongs to the same product category.",
    )

class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    apply_taxes_cost = fields.Boolean(
        related="company_id.apply_taxes_cost",
        readonly=False)

    procured_purchase_grouping = fields.Selection(
        related="company_id.procured_purchase_grouping",
        readonly=False,
    )