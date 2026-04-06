from odoo import fields, models


class L10nLatamIdentificationType(models.Model):
    _inherit = "l10n_latam.identification.type"

    code_ats_sales = fields.Char(
        string="Código ATS Ventas",
    )
    code_ats_purchase = fields.Char(
        string="Código ATS Compras",
    )


class L10nLatamDocumentType(models.Model):
    _inherit = "l10n_latam.document.type"

    ats_declare = fields.Boolean(
        string="Declarado en ATS",
        default=True
    )
    required_tax = fields.Boolean(
        string="Impuestos requeridos",
        default=False
    )
