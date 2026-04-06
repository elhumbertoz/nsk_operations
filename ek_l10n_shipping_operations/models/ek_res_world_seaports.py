from odoo import fields, models, api, _


class ek_res_world_seaports(models.Model):
    _name = "ek.res.world.seaports"
    _description = "Create Seaport that exist at world level"

    name = fields.Char(string="Name", copy=False)
    code = fields.Char(string="Code")
    res_country_id = fields.Many2one("res.country", string="Country")
    res_country_state_id = fields.Many2one("res.country.state", string="State")
