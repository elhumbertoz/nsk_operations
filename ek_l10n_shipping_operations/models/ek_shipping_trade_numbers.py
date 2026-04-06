from odoo import _, api, fields, models

class EkShippingTradeNumbers(models.Model):
    _name = "ek.shipping.trade.numbers"
    _description = "Shipping Trade Numbers"

    nunmer_print = fields.Boolean(string="Number Print", required=False)
    name = fields.Char(string="Sequence", required=True,copy=False)
    ship_registration_id = fields.Many2one("ek.ship.registration", string="Ship Registration", required=False)
    boats_information_id = fields.Many2one("ek.boats.information", string="Journey", required=False)
    request_id = fields.Many2one("ek.operation.request", string="Operation Request", required=False)
    type_id = fields.Many2one("ek.l10n.type.model.mixin", string="Type", required=False)
    stage_id = fields.Many2one("ek.l10n.stages.mixin", string="Stages", required=False)
    user_id = fields.Many2one("res.users", string="User", required=False)
    date = fields.Date(string="Date", required=False, default=fields.Date.today)
    note = fields.Char(string="Note", required=False)
    company_id = fields.Many2one("res.company", string="Company" , required=False, default=lambda self: self.env.user.company_id)




    def generate_shipping_trade_numbers(self):
        wizard = self.env.ref("ek_l10n_shipping_operations.view_ek_generate_shipping_trade_numbers_form_related")
        return {
            "name": _("Generate Trade Number"),
            "type": "ir.actions.act_window",
            "res_model": "ek.generate.shipping.trade.numbers.wizard",
            "view_mode": "form",
            "view_id": wizard.id,
                "views": [(wizard.id, "form")],
            "target": "new",
        }
    


class EkL10nStagesMixin(models.Model):
    _inherit = "ek.l10n.stages.mixin"

    genetate_automatic_shipping_trade_numbers = fields.Boolean(string="Has Automatic Trade Number", default=False)
    readonly_mass = fields.Boolean(string="Readonly")

    