from odoo import api, models


class AccountMove(models.Model):
    _inherit = ["account.move", "supplied.product.mixin"]
    _name = "account.move"

    @api.onchange("invoice_vendor_bill_id")
    def _onchange_invoice_vendor_bill(self):
        if self.invoice_vendor_bill_id:
            self.use_only_supplied_product = (
                self.invoice_vendor_bill_id.use_only_supplied_product
            )
        return super()._onchange_invoice_vendor_bill()



class AccountMoveLine(models.Model):
    _inherit = "account.move.line"
    _name = "account.move.line"

    def _apply_price_difference(self):
        valued_lines = self.env['account.move.line'].sudo()
        
        for line in self:
            if not line.company_id.apply_taxes_cost:
                valued_lines |= line

        return super(AccountMoveLine, valued_lines)._apply_price_difference()