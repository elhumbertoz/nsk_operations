from odoo import fields, models
from odoo.tools.translate import _


class AccountPaymentTerm(models.Model):
    _inherit = "account.payment.term"

    periodicity = fields.Integer(
        string=_("Periodicidad"),
        help=_("Campo informativo que representa a la cantidad de días cada cual se debe realizar el pago."),
    )
