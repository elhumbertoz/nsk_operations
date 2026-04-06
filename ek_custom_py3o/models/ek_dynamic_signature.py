from odoo import _, api, fields, models
import base64

from odoo.exceptions import UserError, ValidationError


class ek_template_py3o(models.Model):
    _name = "ek.template.py3o"
    _description = "Template py3o"


    name = fields.Char(string="Nombre ")
    company_id = fields.Many2one('res.company',string="Compañia",default=lambda self: self.env.company.id, )
    ek_detail_template_items_ids = fields.One2many('ek.detail.template.items','ek_template_py3o_id', string="Item")
    action_report_id = fields.Many2one('ir.actions.report',string="Action Report")




class ek_detail_template_items(models.Model):
    _name = "ek.detail.template.items"
    _description = "Detail template items"

    ek_template_py3o_id = fields.Many2one( 'ek.template.py3o',string="Firma dinamica")
    type_id = fields.Many2one('sign.item.type', string="Tipo", required=True, ondelete='cascade')
    required = fields.Boolean(default=True, string='Obligado')
    responsible_id = fields.Many2one("sign.item.role", string="Responsable", ondelete="restrict")
    option_ids = fields.Many2many("sign.item.option", string="Selection options")
    name = fields.Char(string="Nombre")
    page = fields.Integer(string="Pagina", required=True, default=1)
    posX = fields.Float(digits=(4, 3), string="Posición X", required=True)
    posY = fields.Float(digits=(4, 3), string="Posición Y", required=True)
    width = fields.Float(digits=(4, 3), required=True , string="Ancho")
    height = fields.Float(digits=(4, 3), required=True, string="Alto")
    alignment = fields.Char(default="center", required=True)
    name_field = fields.Char("Campo de Registro")
    model_res_partner = fields.Boolean("Users")