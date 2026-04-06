# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import models, fields


# TODO: Ahora account.chart.template es un modelo abstracto
class AccountChartTemplate(models.AbstractModel):
    _inherit = "account.chart.template"

    def generate_journals(self, acc_template_ref, company, journals_dict=None):
        # EXTENDS account, creates journals for purchase liquidation, sale withholds, purchase withhold
        res = super(AccountChartTemplate, self).generate_journals(acc_template_ref, company, journals_dict=journals_dict)
        self._l10n_ec_configure_ecuadorian_ekuasoft_journals(company)
        self._l10n_ec_configure_l10n_ec_withhold_pending(company)
        return res

    def _l10n_ec_configure_ecuadorian_ekuasoft_journals(self, companies):
        for company in companies.filtered(lambda r: r.account_fiscal_country_id.code == 'EC'):
            ekuasoft_new_journals_values = [
                {
                    'name': "001-001 Notas de Crédito",
                    'code': 'NC',
                    'type': 'sale',
                    'l10n_ec_entity': '001',
                    'l10n_ec_emission': '002',
                    'l10n_latam_use_documents': True,
                    'l10n_ec_is_purchase_liquidation': False,
                    'l10n_ec_emission_address_id': company.partner_id.id
                }, {
                    'name': "001-001 Notas de Débito",
                    'code': 'ND',
                    'type': 'sale',
                    'l10n_ec_entity': '001',
                    'l10n_ec_emission': '003',
                    'l10n_latam_use_documents': True,
                    'l10n_ec_is_purchase_liquidation': False,
                    'l10n_ec_emission_address_id': company.partner_id.id
                }, {
                    'name': "Notas de Crédito de Compra",
                    'code': 'NCCO',
                    'type': 'purchase',
                    'l10n_ec_withhold_type': False,
                    'l10n_ec_is_purchase_liquidation': False,
                    'l10n_latam_use_documents': True,
                    'l10n_latam_document_auth_required': True,
                    'l10n_latam_document_sustento_required': True,
                    'l10n_ec_emission_address_id': False
                }, {
                    'name': "Notas de Débito de Compra",
                    'code': 'NDCO',
                    'type': 'purchase',
                    'l10n_ec_withhold_type': False,
                    'l10n_ec_is_purchase_liquidation': False,
                    'l10n_latam_document_auth_required': True,
                    'l10n_latam_document_sustento_required': True,
                    'l10n_latam_use_documents': True,
                    'l10n_ec_emission_address_id': False
                }, {
                    'name': "Cruce de Anticipos (Proveedores)",
                    'code': 'CAP',
                    'type': 'general',
                    'l10n_ec_withhold_type': False,
                    'l10n_ec_is_purchase_liquidation': False,
                    'l10n_latam_document_auth_required': True,
                    'l10n_latam_document_sustento_required': False,
                    'l10n_latam_use_documents': False,
                    'l10n_ec_emission_address_id': False
                }, {
                    'name': "Cruce de Anticipos (Clientes)",
                    'code': 'CAC',
                    'type': 'general',
                    'l10n_ec_withhold_type': False,
                    'l10n_ec_is_purchase_liquidation': False,
                    'l10n_latam_document_auth_required': True,
                    'l10n_latam_document_sustento_required': False,
                    'l10n_latam_use_documents': False,
                    'l10n_ec_emission_address_id': False
                }
            ]
            for new_values in ekuasoft_new_journals_values:
                journal = self.env['account.journal'].search([
                    ('code', '=', new_values['code']),
                    ('company_id', '=', company.id)])
                if not journal:
                    self.env['account.journal'].create({
                        **new_values,
                        'company_id': company.id,
                        'show_on_dashboard': False,
                    })
                else:
                    self.env['account.journal'].write(new_values)

    def _l10n_ec_configure_l10n_ec_withhold_pending(self, companies):
        template = self.env.ref("ek_l10n_ec.email_template_withhold_pending")
        if template:
            for company in companies.filtered(lambda r: r.account_fiscal_country_id.code == 'EC'):
                if not company.l10n_ec_withhold_pending_mail_tempalte_id:
                    company.write({
                        'l10n_ec_withhold_pending_mail_tempalte_id': template.id,
                        'l10n_ec_withhold_pending_mail_send': False,
                        'l10n_ec_withhold_start_date': fields.Date.today()
                    })
