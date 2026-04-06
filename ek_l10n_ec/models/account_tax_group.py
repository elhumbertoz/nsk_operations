from odoo import fields, models
from odoo.addons.l10n_ec.models.account_tax_group import _TYPE_EC

_SBTYPE = {
    'vat05': ("vat05", "VAT 5%"),
    'vat08': ("vat08", "VAT 8%"),
    'vat13': ("vat13", "VAT 13%"),
    'vat14': ("vat14", "VAT 14%"),
    'vat15': ("vat15", "VAT 15%"),
}

for type in _TYPE_EC:
    if type[0] in _SBTYPE:
        _SBTYPE.pop(type[0])

for _type in _SBTYPE.values():
    _TYPE_EC.append(_type)


class AccountTaxGroup(models.Model):
    _inherit = "account.tax.group"

    l10n_ec_type = fields.Selection(
        _TYPE_EC, string="Type Ecuadorian Tax", help="Ecuadorian taxes subtype"
    )