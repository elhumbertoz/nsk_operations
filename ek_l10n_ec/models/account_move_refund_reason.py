from odoo import fields, models


class AccountMoveRefundReason(models.Model):
    _name = "account.move.refund.reason"
    _description = "Account Move Refund Reason"

    name = fields.Char(required=True, translate=True)
    active = fields.Boolean(default=True)
    description = fields.Char()