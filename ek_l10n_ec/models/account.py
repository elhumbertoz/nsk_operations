# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl)

from odoo import api, fields, models
from odoo.tools.translate import _
from odoo.exceptions import ValidationError


class AccountAccount(models.Model):
    _inherit = "account.account"

    analytic_policy = fields.Selection(
        string="Policy for analytic account",
        selection=[
            ("optional", "Optional"),
            ("always", "Always"),
            ("posted", "Posted moves"),
            ("never", "Never"),
        ],
        default="optional",
        company_dependent=True,
        help=(
            "Sets the policy for analytic accounts.\n"
            "If you select:\n"
            "- Optional: The accountant is free to put an analytic account "
            "on an account move line with this type of account.\n"
            "- Always: The accountant will get an error message if "
            "there is no analytic account.\n"
            "- Posted moves: The accountant will get an error message if no "
            "analytic account is defined when the move is posted.\n"
            "- Never: The accountant will get an error message if an analytic "
            "account is present.\n\n"
            "This field is company dependent."
        ),
    )

    def _get_analytic_policy(self):
        """Extension point to obtain analytic policy for an account"""
        self.ensure_one()
        return self.analytic_policy



