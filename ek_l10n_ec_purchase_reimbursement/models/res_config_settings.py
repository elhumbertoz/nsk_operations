# -*- coding: utf-8 -*-
import logging

from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError

_logger = logging.getLogger(__name__)

class ResCompany(models.Model):
    _inherit = "res.company"

    l10n_ec_reimbursement_journal_ids = fields.Many2many(
        "account.journal",
        "l10n_ec_reimbursement_journal_rel",
        "company_id",
        "journal_id",
        "Reimbursement Journals",
    )

    l10n_ec_ats_sustento_ids = fields.Many2many(
        "account.ats.sustento",
        "l10n_ec_ats_sustento_rel",
        "company_id",
        "journal_id",
        "ATS Sustento",
    )

    l10n_ec_assumed_retention_account_prefix = fields.Char(
        string='Prefijo Cta. Retención Asumida',
        default='52022',
        help='Prefijo de la cuenta contable para identificar retenciones asumidas (ej: 52022)'
    )

class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    l10n_ec_reimbursement_journal_ids = fields.Many2many(
        related='company_id.l10n_ec_reimbursement_journal_ids',
        readonly=False
    )

    l10n_ec_ats_sustento_ids = fields.Many2many(
        related='company_id.l10n_ec_ats_sustento_ids',
        readonly=False
    )

    l10n_ec_assumed_retention_account_prefix = fields.Char(
        related='company_id.l10n_ec_assumed_retention_account_prefix',
        readonly=False,
    )