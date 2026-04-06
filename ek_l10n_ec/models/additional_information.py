from odoo import fields, models


class AdditionalInformation(models.Model):
    _name = "ek_l10n_ec.additional.information"
    _description = "Información adicional para documentos electrónicos"

    name = fields.Char(
        string="Atributo",
        required=True,
    )
    description = fields.Char(
        string="Valor",
        required=True,
    )
    move_id = fields.Many2one(
        string="Account Move",
        comodel_name="account.move",
        ondelete="cascade",
    )
