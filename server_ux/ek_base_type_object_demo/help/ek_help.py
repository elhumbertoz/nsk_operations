from odoo import _, api, fields, models



class EkHelp(models.Model):
    _name = "ek.help"
    _inherit = "ek.l10n.model.mixin"
    _description = "ek.help"
    name = fields.Char(string='Nombre')
    number = fields.Char(string='No.')

    select = fields.Selection(selection=[("1","A"),("2","B"),("3","AB")])
    other = fields.Char(string='Other')
    partner_id = fields.Many2one(
        string=_('Partner'),
        comodel_name='res.partner',
    )

    partner_id2 = fields.Many2one(
        string=_('Partner2'),
        comodel_name='res.partner',
    )

    partner_id3 = fields.Many2one(
        string=_('Partner3'),
        comodel_name='res.partner',
    )
    partner_id4 = fields.Many2one(
        string=_('Partner4'),
        comodel_name='res.partner',
    )
    partner_id5 = fields.Many2one(
        string=_('Partner5'),
        comodel_name='res.partner',
    )

    
    
    def _get_object_validation_model_config(self):
        
        return {
            self._name: {
                "_inherit_dinamic_view": "ek_base_dinamic_view",
                "_inherit_position_view": "after",
                "_inherit_xpath_view": "//group[last()]",
                "_module_dinamic_name": self._module or "ek_base_type_object",
            }
        }