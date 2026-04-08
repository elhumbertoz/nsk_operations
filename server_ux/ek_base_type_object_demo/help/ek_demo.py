from odoo import _, api, fields, models



class EkDemo(models.Model):
    _name = "ek.demo"
    _inherit = "ek.l10n.model.mixin"
    _description = "ek.demo"

    name = fields.Char(string='Nombre')
    number = fields.Char(string='No.')

    select = fields.Selection(selection=[("1","A"),("2","B"),("3","AB")])
    other = fields.Char(string='Other')
    partner_id = fields.Many2one(
        string=_('Partner'),
        comodel_name='res.partner',
    )

    
    
    def _get_object_validation_model_config(self):
        
        return {
            self._name: {
                "_inherit_dinamic_view": "view_ek_l10n_model_mixin_form",
                "_inherit_position_view": "after",
                "_inherit_xpath_view": "//group[last()]",
                "_module_dinamic_name": self._module or "ek_base_type_object",
            }
        }