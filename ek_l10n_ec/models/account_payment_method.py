
from odoo import api, fields, models


class AccountPaymentMethod(models.Model):
    _inherit = "account.payment.method"

    code = fields.Char(
        string="Code (Do Not Modify)",
        help="This code is used in the code of the Odoo module that handles "
        "this payment method. Therefore, if you change it, "
        "the generation of the payment file may fail.",
    )
    active = fields.Boolean(default=True)
    bank_account_required = fields.Boolean(
        help="Activate this option if this payment method requires you to "
        "know the bank account number of your customer or supplier."
    )
    payment_mode_ids = fields.One2many(
        comodel_name="account.payment.mode",
        inverse_name="payment_method_id",
        string="Payment modes",
    )

    @api.model
    def _get_payment_method_information(self):
        res = super()._get_payment_method_information()

        res['credit_card'] = {'mode': 'multi', 'domain': [('type', '=', 'cash')]}

        return res


    @api.depends("code", "name", "payment_type")
    def name_get(self):
        result = []
        for method in self:
            result.append(
                (
                    method.id,
                    f"[{method.code}] {method.name} ({method.payment_type})",
                )
            )
        return result