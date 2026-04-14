# -*- coding: utf-8 -*-
from odoo import models, fields, api, _

class EkAIExtractionProgressWizard(models.TransientModel):
    _name = 'ek.ai.extraction.progress.wizard'
    _description = 'AI Extraction Progress Wizard'

    res_model = fields.Char('Source Model')
    res_id = fields.Integer('Source ID')
    
    # We display these fields which will be updated by the record
    progress = fields.Integer(string='Progreso', compute='_compute_fields')
    message = fields.Char(string='Mensaje', compute='_compute_fields')
    status = fields.Char(string='Estado', compute='_compute_fields')

    @api.depends('res_id', 'res_model')
    def _compute_fields(self):
        for rec in self:
            if rec.res_model and rec.res_id:
                source = self.env[rec.res_model].browse(rec.res_id)
                # Determinamos cual estado mostrar (el que esté activo)
                status = source.ai_extraction_status_fc or source.ai_extraction_status_bl or source.ai_extraction_status_np or 'pending'
                
                rec.progress = source.ai_extraction_progress
                rec.message = source.ai_extraction_message
                rec.status = status
            else:
                rec.progress = 0
                rec.message = ''
                rec.status = 'pending'

    def action_refresh(self):
        # Dummy action to force refresh if needed, but the JS should handle it
        return {
            'type': 'ir.actions.act_window',
            'res_model': self._name,
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
        }
