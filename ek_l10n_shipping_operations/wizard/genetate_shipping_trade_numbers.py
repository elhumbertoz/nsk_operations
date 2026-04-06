from odoo import _, fields, models, api
from odoo.exceptions import UserError

class GenerateShippingTradeNumbersWizard(models.TransientModel):
    _name = "ek.generate.shipping.trade.numbers.wizard"
    _description = "Wizard Generate Shipping Trade Numbers"

    note = fields.Char(string="Note")

    operation_request_id = fields.Many2one(
        comodel_name="ek.operation.request",
        string="Request"
    )
    link_request = fields.Boolean(string="Link Request")

   
     
    def generate_shipping_trade_numbers(self):
        if self.operation_request_id and not self.link_request:
            self.operation_request_id.generate_shipping_trade_numbers(self.note)
            return {"type": "ir.actions.act_window_close"}
        
        else:
            self.generate_shipping_trade_numbers_external()
            return {
                'type': 'ir.actions.client',
                'tag': 'reload',
            }
        
    def generate_shipping_trade_numbers_external(self):
        ObjectTrade = self.env["ek.shipping.trade.numbers"]
        company = self.env.user.company_id
        if self.link_request and self.operation_request_id:
             ObjectTrade.create({
                "note": self.note,
                "user_id": self.env.user.id,
                "date": fields.Date.today(),
                "name": company.trade_sequence_id.next_by_id(),
                "company_id": company.id,
                "request_id": self.operation_request_id.id,
                "ship_registration_id": self.operation_request_id.ek_ship_registration_id.id,
                "boats_information_id": self.operation_request_id.journey_crew_id.id,
                "type_id": self.operation_request_id.type_id.id,

            })
        else:
            ObjectTrade.create({
                "note": self.note,
                "user_id": self.env.user.id,
                "date": fields.Date.today(),
                "name": company.trade_sequence_id.next_by_id(),
                "company_id": company.id
            })
       



        