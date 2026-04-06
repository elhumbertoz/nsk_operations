from odoo import _, api, fields, models,Command
from odoo.exceptions import UserError
import base64

class EkL10nGroupTypeModelMixin(models.Model):
    _name = 'ek.l10n.group.type.model.mixin'
    _description = _("Group Type Generic Model")

        
    code = fields.Char(string="Code",required=True,copy=True)
    name = fields.Char(string="Name" , required=True,copy=True)

    type_ids = fields.One2many(
        string=_('Types'),
        comodel_name='ek.l10n.type.model.mixin',
        inverse_name='group_id', copy=True
    )

    @api.depends("code", "name")
    def _compute_display_name(self):
        for rec in self:
            rec.display_name = "%s - %s" % (rec.code, rec.name)


    _sql_constraints = [
        ('code_uniq', 'unique (code, name)', 'Code and Name must be unique!'),
    ]