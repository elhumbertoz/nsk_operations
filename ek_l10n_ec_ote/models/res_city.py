# -*- coding: utf-8 -*-
import logging

from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError

_logger = logging.getLogger(__name__)


class ResCity(models.Model):
    _inherit = 'res.city'

    l10n_ec_code = fields.Char('Code', help='This code will help with the '
                               'identification of each city in Ecuador.')
