# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    date_init_sales = fields.Datetime(string="Sales start date",
                                                  config_parameter='suggest.history_date_init_sales',)
