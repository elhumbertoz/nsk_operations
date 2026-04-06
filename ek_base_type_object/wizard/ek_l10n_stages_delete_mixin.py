# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

import ast

from odoo import api, fields, models, _


class EkL10nStagesDeleteMixin(models.TransientModel):
    _name = 'ek.l10n.stages.delete.mixin.wizard'
    _description = 'Object Stage Delete Wizard'

    stage_ids = fields.Many2many('ek.l10n.stages.mixin', string='Stages To Delete')
    object_count = fields.Integer('Number of Tickets', compute='_compute_object_count')
    type_ids = fields.Many2many('ek.l10n.type.object.mixin', domain="['|', ('active', '=', False), ('active', '=', True)]", string='Types of Objects')
    stages_active = fields.Boolean(compute='_compute_stages_active')

    def _compute_object_count(self):
        ObjectRequest = self.with_context(active_test=False).env['ek.l10n.model.mixin']
        for wizard in self:
            wizard.object_count = ObjectRequest.search_count([('stage_id', 'in', wizard.stage_ids.ids)])

    @api.depends('stage_ids')
    def _compute_stages_active(self):
        for wizard in self:
            wizard.stages_active = all(wizard.stage_ids.mapped('active'))

    def action_archive(self):
        if len(self.type_ids) <= 1:
            return self.action_confirm()
        return {
            'name': _('Confirmation'),
            'view_mode': 'form',
            'res_model': 'ek.l10n.stages.delete.mixin.wizard',
            'views': [(self.env.ref('ek_base_type_object.view_ek_l10n_stages_delete_confirmation_mixin_wizard').id, 'form')],
            'type': 'ir.actions.act_window',
            'res_id': self.id,
            'target': 'new',
            'context': self.env.context,
        }
        

    def action_confirm(self):
        objects = self.with_context(active_test=False).env['ek.l10n.model.mixin'].search([('stage_id', 'in', self.stage_ids.ids)])
        objects.write({'active': False})
        self.stage_ids.write({'active': False})
        return self._get_action()

    def action_unarchive_objects(self):
        objects = self.env['ek.l10n.model.mixin'].with_context(active_test=False).search([('stage_id', 'in', self.stage_ids.ids)])
        objects.action_unarchive()

    def action_unlink(self):
        self.stage_ids.unlink()
        return self._get_action()

    def _get_action(self):
        action = True
        # if self.env.context.get('stage_view'):
        #     action = self.env["ir.actions.actions"]._for_xml_id('helpdesk.helpdesk_stage_action')
        # else:
        #     action = self.env["ir.actions.actions"]._for_xml_id('helpdesk.helpdesk_ticket_action_main_tree')

        # context = dict(ast.literal_eval(action.get('context')), active_test=True)
        # action['context'] = context
        # action['target'] = 'main'
        return action
