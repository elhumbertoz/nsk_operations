from odoo import _, api, fields, models
from odoo.tools.misc import unique
class EkL10nStagesMixin(models.Model):
    _name = 'ek.l10n.stages.mixin'
    _description = _("Type Generic Stages")
    _order = 'sequence, id'

    def _default_type_ids(self):
        type_id = self.env.context.get('default_type_id')
        if type_id:
            return [(4, type_id, 0)]

    active = fields.Boolean(default=True)
    name = fields.Char(required=True, translate=True)
    description = fields.Text(translate=True)
    sequence = fields.Integer('Sequence', default=10)
    
    fold = fields.Boolean(
        'Folded in Kanban',
        help='Objects in a folded stage are considered as closed or ended Flow.')

    confirm_stage = fields.Boolean(
        'Confirm Flow',
        help='Objects in a confirmed stage are considered as confirmed Flow.')
    
    canceled_stage = fields.Boolean(
        'Canceled Flow',
        help='Objects in a canceled stage are considered as cancelled Flow.')
    
    show_canceled_button = fields.Boolean(
        'Show Canceled Button',
        help='Display a button to cancel the stage in the kanban view.')
    
    show_close_button = fields.Boolean(
        'Show Close Button',
        help='Display a button to close the stage in the kanban view.')

    show_back_button = fields.Boolean(
        'Show Back Button',
        help='Display a button to go back to the previous stage in the kanban view.')

    type_ids = fields.Many2many(
        'ek.l10n.type.model.mixin', relation='ek_l10n_type_model_stage_rel', string='Types of Objects',
        required=False)

    template_id = fields.Many2one(
        'mail.template', 'Email Template',
        domain="[('model', '=', 'ek.l10n.model.mixin')]",
        help="Email automatically sent to the customer when the type reaches this stage.\n"
             "By default, the email will be sent from the email alias of the type.\n"
             "Otherwise it will be sent from the company's email address, or from the catchall (as defined in the System Parameters).")
    
    report_id = fields.Many2one("ir.actions.report", string="Report", domain="[('model_id.model', '=', 'ek.l10n.model.mixin')]")
    # legend_blocked = fields.Char(
    #     'Red Kanban Label', default=lambda s: _('Blocked'), translate=True, required=True)
    # legend_done = fields.Char(
    #     'Green Kanban Label', default=lambda s: _('Ready'), translate=True, required=True)
    # legend_normal = fields.Char(
    #     'Grey Kanban Label', default=lambda s: _('In Progress'), translate=True, required=True)
    object_count = fields.Integer(compute='_compute_objec_count')

    def _compute_objec_count(self):
        # res = self.env['ek.l10n.model.mixin']._read_group(
        #     [('stage_id', 'in', self.ids)],
        #     ['stage_id'], ['__count'])
        # stage_data = {stage.id: count for stage, count in res}
        # for stage in self:
        #     stage.object_count = stage_data.get(stage.id, 0)

        self.object_count = 0

    def write(self, vals):
        if 'active' in vals and not vals['active']:
            self.env['ek.l10n.model.mixin'].search([('stage_id', 'in', self.ids)]).write({'active': False})
        return super(EkL10nStagesMixin, self).write(vals)

    def toggle_active(self):
        res = super().toggle_active()
        stage_active = self.filtered('active')
        if stage_active and sum(stage_active.with_context(active_test=False).mapped('object_count')) > 0:
            wizard = self.env['ek.l10n.stages.delete.mixin.wizard'].create({
                'stage_ids': stage_active.ids,
            })

            return {
                'name': _('Unarchive Request'),
                'view_mode': 'form',
                'res_model': 'ek.l10n.stages.delete.mixin.wizard',
                'views': [(self.env.ref('ek_base_type_object.view_ek_l10n_stage_unarchive_wizard').id, 'form')],
                'type': 'ir.actions.act_window',
                'res_id': wizard.id,
                'target': 'new',
            }
        return res

    def action_unlink_wizard(self, stage_view=False):
        self = self.with_context(active_test=False)
        # retrieves all the teams with a least 1 ticket in that stage
        # a ticket can be in a stage even if the team is not assigned to the stage
        readgroup = self.with_context(active_test=False).env['ek.l10n.model.mixin']._read_group(
            [('stage_id', 'in', self.ids), ('type_id', '!=', False)],
            ['type_id'])
        type_ids = list(unique([type_id.id for [type_id] in readgroup] + self.type_ids.ids))

        wizard = self.env['ek.l10n.stages.delete.mixin.wizard'].create({
            'stage_ids': self.ids,
            'type_ids': type_ids
        })

        context = dict(self.env.context)
        context['stage_view'] = stage_view
        return {
            'name': _('Delete Stage'),
            'view_mode': 'form',
            'res_model': 'ek.l10n.stages.delete.mixin.wizard',
            'views': [(self.env.ref('ek_base_type_object.view_ek_l10n_stages_delete_mixin_wizard').id, 'form')],
            'type': 'ir.actions.act_window',
            'res_id': wizard.id,
            'target': 'new',
            'context': context,
        }

    def action_open_objects(self):
        self.ensure_one()
        action = self.env["ir.actions.actions"]._for_xml_id("ek_base_type_object.helpdesk_ticket_action_main_tree")
        action.update({
            'domain': [('stage_id', 'in', self.ids)],
            'context': {
                'default_stage_id': self.id,
            },
        })
        return action


    # _sql_constraints = [
    #     ('unique_field_type_id', 'unique(field_id,type_model_id)', _('Field and Type Model must be unique')),
    # ]