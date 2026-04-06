from odoo import models


class AccountPayment(models.Model):
    _inherit = "account.payment"

    def has_check(self):
        return False
