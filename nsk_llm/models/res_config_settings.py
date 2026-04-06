from odoo import models, fields

class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    nsk_default_llm_provider_id = fields.Many2one(
        'nsk.llm.provider',
        string='Default LLM Provider',
        config_parameter='nsk_llm.default_provider_id',
        help='The default Artificial Intelligence model to use globally.'
    )
