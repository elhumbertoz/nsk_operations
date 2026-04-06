from odoo import fields, models


class ResCompany(models.Model):
    _inherit = "res.company"

    l10n_ec_canton_id = fields.Many2one(
        string="Cantón",
        comodel_name="ek.res.country.canton",
        related="partner_id.l10n_ec_canton_id",
        ondelete="restrict",
        readonly=False,
    )
