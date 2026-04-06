from odoo import _, api, fields, models,Command
from odoo.exceptions import UserError

class EkL10nTypeNotifyStageModelMixin(models.Model):
    _name = 'ek.l10n.type.notify.stage.model.mixin'
    _description = _("Type Nofification Model")

    stage_id = fields.Many2one(comodel_name='ek.l10n.stages.mixin', string="Stage", domain="[('type_ids', '=', type_id)]", required=True)
    user_ids = fields.Many2many(comodel_name='res.users', string="Users", domain="[('id', 'in', member_ids)]", required=True)
    activity_id = fields.Many2one(comodel_name='mail.activity.type', string="Activity", required=True)
    delay_count = fields.Integer(string="Delay  ", default=1)
    note = fields.Text(string="Note")
    type_id = fields.Many2one(comodel_name='ek.l10n.type.model.mixin', string="Type")
    member_ids = fields.Many2many('res.users', related="type_id.member_ids")

    @api.constrains('delay_count')
    def _check_delay_count(self):
        if self.delay_count < 0:
            raise UserError(_("Delay Count must be positive"))


    _sql_constraints = [
        ('stage_id_uniq', 'unique (stage_id,type_id)', _('Stage must be unique!')),
    ]
