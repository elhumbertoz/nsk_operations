from odoo import api, fields, models, _

class SignSendRequest(models.TransientModel):
    _inherit = "sign.send.request"

    ek_operation_request_id = fields.Many2one("ek.operation.request", string="Request")

    def create_request(self):
        sign_request  = super(SignSendRequest, self).create_request()
        if self.ek_operation_request_id:
            sign_request .ek_operation_request_id = self.ek_operation_request_id
        return sign_request 
class SignRequest(models.Model):
    _inherit = "sign.request"

    ek_operation_request_id = fields.Many2one("ek.operation.request", string="Request")
