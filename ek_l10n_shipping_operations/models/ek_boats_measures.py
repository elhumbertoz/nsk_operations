from odoo import fields, models, api, _
from odoo.exceptions import UserError


class ek_boats_measures(models.Model):
    _name = "ek.boats.measures"
    _description = "Create Measures"

    name = fields.Char(string="Acronym", copy=False)
    measures = fields.Char(string="Measures")

