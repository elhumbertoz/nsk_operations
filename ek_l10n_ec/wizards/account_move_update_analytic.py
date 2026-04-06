from odoo import fields, models, api,_


class AccountMoveUpdateAnalytic(models.TransientModel):
    _name = "account.move.update.analytic.wizard"
    _description = "Account Move Update Analytic Account Wizard"

    line_id = fields.Many2one(
        string="Invoice line",
        comodel_name="account.move.line",
    )
    product_id = fields.Many2one(
        related="line_id.product_id",
    )
    account_id = fields.Many2one(
        related="line_id.account_id",
    )
    move_type = fields.Selection(
        related="line_id.move_id.move_type",
    )
    analytic_precision = fields.Integer(
        related="line_id.analytic_precision",
    )
    current_analytic_distribution = fields.Json(
        string=_("Current Analytic Distribution"),
        related="line_id.analytic_distribution",
    )
    company_id = fields.Many2one(
        related="line_id.company_id",
    )
    analytic_distribution = fields.Json(
        string=_("New Analytic Distribution"),
    )

    @api.model
    def default_get(self, fields):
        rec = super().default_get(fields)
        active_id = self.env.context.get("active_id", False)
        aml = self.env["account.move.line"].browse(active_id)
        rec.update({
            "line_id": aml.id,
            "product_id": aml.product_id.id,
            "account_id": aml.account_id.id,
            "move_type": aml.move_id.move_type,
            "analytic_precision": aml.analytic_precision,
            "current_analytic_distribution": aml.analytic_distribution,
            "analytic_distribution": aml.analytic_distribution,
        })
        return rec

    def update_analytic_lines(self):
        self.ensure_one()
        self.line_id.analytic_distribution = self.analytic_distribution
