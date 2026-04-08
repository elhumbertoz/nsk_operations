# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

import ast
import copy
import datetime
import io
import json
import logging
import markupsafe
from collections import defaultdict
from math import copysign, inf

import lxml.html
from babel.dates import get_quarter_names
from dateutil.relativedelta import relativedelta
from markupsafe import Markup

from odoo import models, fields, api, _
from odoo.addons.web.controllers.main import clean_action
from odoo.exceptions import RedirectWarning
from odoo.osv import expression
from odoo.tools import config, date_utils, get_lang
from odoo.tools.misc import formatLang, format_date
from odoo.tools.misc import xlsxwriter

_logger = logging.getLogger(__name__)



class AccountGeneralsuggestedReport(models.AbstractModel):
    _inherit = 'account.report'
    _name = "account.general.suggested"
    _description = "General suggested Report"
    #filter_partner = True
    #filter_multi_company = True  # Actually disabled by default, can be activated by config parameter (see _get_options)
    #filter_date = {'mode': 'range', 'filter': 'last_month'}
    #filter_all_entries = False
    #filter_comparison = {'date_from': '', 'date_to': '', 'filter': 'no_comparison', 'number_period': 1}
    #filter_tax_report = None

    ####################################################
    # MAIN METHODS
    ####################################################
    # product_id = fields.Many2one('product.product', string="Product")
    # partner_id = fields.Many2one('res.partner', string="Supplier")
    # qty_stock = fields.Float(string='Stock', required=True, copy=False, default='0', readonly=True)
    # sales_ytd = fields.Float(string='Sales YTD', required=True, copy=False, default='0', readonly=True)
    # sales_esp = fields.Float(string='Sales ESP', required=True, copy=False, default='0', readonly=True)
    # sales_year_old = fields.Float(string='Sales year Old', required=True, copy=False, default='0', readonly=True)
    # last_date = fields.Date(string="Last Date", tracking=True)
    # purchase_local = fields.Float(string='Purchase local', required=True, copy=False, default='0', readonly=True)
    # transit = fields.Float(string='Transit', required=True, copy=False, default='0', readonly=True)
    # day_not_stock = fields.Integer(string='Day not stock', required=True, copy=False, default='0', readonly=True)
    # minimum = fields.Float(string='Minimo', required=True, copy=False, default='0', readonly=True)
    # maximum = fields.Float(string='Maximum', required=True, copy=False, default='0', readonly=True)
    # day_transit = fields.Integer(string='Day transit', required=True, copy=False, default='0', readonly=True)
    # qty_suggested = fields.Float(string='Suggested', required=True, copy=False, default='0', readonly=True)
    # arrival_date = fields.Date(string="Arrival Date", tracking=True)
    # cost = fields.Float(string='Cost', required=True, copy=False, default='0', readonly=True)
    # peso = fields.Float(string='Peso', required=True, copy=False, default='0', readonly=True)
    # investment = fields.Float(string='Investment', required=True, copy=False, default='0', readonly=True)
    # peso_total = fields.Float(string='Peso total', required=True, copy=False, default='0', readonly=True)


    @api.model
    def _get_report_name(self):
        return _('Reporte de Sugerido')


    def _get_templates(self):
        # Overridden to add an option to the tax report to display it grouped by tax grid.
        #templates = super()._get_templates()
        templates = super(AccountGeneralsuggestedReport, self)._get_templates()
        templates['search_template'] = 'base_suggested_purchase.search_template_generic_suggested_report'
        templates['main_template'] = 'base_suggested_purchase.template_suggested_report'
        return templates


    @api.model
    def _query_get(self, options, domain=None):
        domain = [('company_id', 'in', self.get_report_company_ids(options))]
        self.env['ek.suggested.purchase'].check_access_rights('read')
        query = self.env['ek.suggested.purchase']._where_calc(domain)
        self.env['ek.suggested.purchase']._apply_ir_rules(query)
        return query.get_sql()


    def _get_columns_name(self, options):
        columns = [
            {},
            {'name': _('Codigo')},
            {'name': _('Producto')},
            {'name': _('Stock'), 'class': 'number'},
            {'name': _('Por Entregar'), 'class': 'number'},
            {'name': _('Ventas YTD Mes'), 'class': 'number'},
            {'name': _('Ventas YTD'), 'class': 'number'},
            {'name': _('VENTAS AÑO PASADO Mes'), 'class': 'number'},
            {'name': _('VENTAS AÑO PASADO'), 'class': 'number'},
            {'name': _('Última venta'), 'class': 'date'},
            {'name': _('COMPA LOCAL'), 'class': 'number'},
            {'name': _('TRANSITO'), 'class': 'number'},
            {'name': _('DIAS SIN STOCK'), 'class': 'number'},
            {'name': _('MIN'), 'class': 'number'},
            {'name': _('MAX'), 'class': 'number'},
            {'name': _('Dias de transito'), 'class': 'number'},
            {'name': _('Proveedor')},
            {'name': _('Sugerido'), 'class': 'number'},
            {'name': _('Fecha Aproximada de llegada'), 'class': 'date'},
            {'name': _('Costo'), 'class': 'number'},
            {'name': _('Peso'), 'class': 'number'},
            {'name': _('Inversión'), 'class': 'number'},
            {'name': _('Peso Total'), 'class': 'number'},

            ]
        # if self.user_has_groups('base.group_multi_currency'):
        #    columns.append({'name': _('Amount Currency'), 'class': 'number'})
        # columns.append({'name': _('Balance'), 'class': 'number'})
        return columns


    @api.model
    def _get_lines(self, options, line_id=None):
        self.flush()
        #if self._is_generic_layout(options):
        return self._get_lines_default_suggested_report(options , line_id)
        #data = self._compute_tax_report_data(options)
        #return self._get_lines_by_grid(options, line_id, data)


    @api.model
    def _get_query_amls(self, options, expanded_partner=None, offset=None, limit=None):
        ''' Construct a query retrieving the account.move.lines when expanding a report line with or without the load
        more.
        :param options:             The report options.
        :param expanded_partner:    The res.partner record corresponding to the expanded line.
        :param offset:              The offset of the query (used by the load more).
        :param limit:               The limit of the query (used by the load more).
        :return:                    (query, params)
        '''
        unfold_all = options.get('unfold_all') or (self._context.get('print_mode') and not options['unfolded_lines'])

        # Get sums for the account move lines.
        # period: [('date' <= options['date_to']), ('date', '>=', options['date_from'])]
        domain = []
        if expanded_partner is not None:
            domain = [('partner_id', '=', expanded_partner.id)]
        #elif unfold_all:
        elif options['unfolded_lines']:
            domain = [('partner_id', 'in', [int(line[8:]) for line in options['unfolded_lines']])]

        #new_options = self._get_options_sum_balance(options)
        tables, where_clause, where_params = self._query_get(options, domain=domain)

        query = '''
            SELECT
                
                default_code,
                product_id,    
                qty_stock,
                qty_pending_deliver,
                sales_month,
                sales_ytd,
                sales_year_old_month,
                sales_year_old,
                last_date,
                purchase_local,
                transit,
                day_not_stock,
                minimum,
                maximum,
                day_transit,
                partner_id,
                qty_suggested,
                arrival_date,
                cost,
                weight,
                investment,
                total_weight,
                id
            FROM %s 
            WHERE %s
            ORDER BY id
        ''' % (tables, where_clause)

        if offset:
            query += ' OFFSET %s '
            where_params.append(offset)
        if limit:
            query += ' LIMIT %s '
            where_params.append(limit)

        return query, where_params


    @api.model
    def _get_lines_default_suggested_report(self, options , line_id):
        ''' Get lines for the whole report or for a specific line.
        :param options: The report options.
        :return:        A list of lines, each one represented by a dictionary.
        '''
        lines = []

        expanded_partner = line_id and self.env['res.partner'].browse(int(line_id[8:]))
        query, params = self._get_query_amls(options, expanded_partner=expanded_partner, offset=None, limit=None)

        self._cr.execute(query, params)

        COL_LIST = self._get_columns_name(options)
        COL_LIST.pop(0)
        results = self._cr.dictfetchall()
        for res in results:
            DATA_TMP = []
            ID_control = res.get('id')
            del res['id']
            cont = 0
            for indice in res:
                if indice == 'product_id':
                    dt_var = self.env['product.product'].browse(int(res[indice])).name
                elif indice == 'partner_id':
                    if res.get(indice, False):
                        dt_var = self.env['res.partner'].browse(int(res.get(indice,0))).name
                    else:
                        dt_var = ""
                else:
                    dt_var = res[indice]

                dic_tmp = COL_LIST[cont].copy()
                dic_tmp['name'] = dt_var
                DATA_TMP.append(dic_tmp)
                cont += 1


            res.update({'columns': DATA_TMP,'id':ID_control})
            lines.append(res)
        return lines

    #@api.model
    def _get_lines_order_list(self, indice , columns , data):
        columns[indice]['name'] = data.get(data.keys()[indice])
        return columns


    def get_report_informations(self, options):
        #print(options)
        '''
        return a dictionary of informations that will be needed by the js widget, manager_id, footnotes, html of report and searchview, ...
        '''
        options = self._get_options(options)
        self = self.with_context(self._set_context(options)) # For multicompany, when allowed companies are changed by options (such as aggregare_tax_unit)

        searchview_dict = {'options': options, 'context': self.env.context}
        # Check if report needs analytic
        #if options.get('analytic_accounts') is not None:
        #    options['selected_analytic_account_names'] = [self.env['account.analytic.account'].browse(int(account)).name for account in options['analytic_accounts']]
        #if options.get('analytic_tags') is not None:
        #    options['selected_analytic_tag_names'] = [self.env['account.analytic.tag'].browse(int(tag)).name for tag in options['analytic_tags']]
        #if options.get('partner'):
        #    options['selected_partner_ids'] = [self.env['res.partner'].browse(int(partner)).name for partner in options['partner_ids']]
        #    options['selected_partner_categories'] = [self.env['res.partner.category'].browse(int(category)).name for category in (options.get('partner_categories') or [])]

        # Check whether there are unposted entries for the selected period or not (if the report allows it)
        #if options.get('date') and options.get('all_entries') is not None:
        #    date_to = options['date'].get('date_to') or options['date'].get('date') or fields.Date.today()
        #    period_domain = [('state', '=', 'draft'), ('date', '<=', date_to)]
        #    options['unposted_in_period'] = bool(self.env['account.move'].search_count(period_domain))

        report_manager = self._get_report_manager(options)
        info = {'options': options,
                'context': self.env.context,
                'report_manager_id': report_manager.id,
                'footnotes': [{'id': f.id, 'line': f.line, 'text': f.text} for f in report_manager.footnotes_ids],
                'buttons': self._get_reports_buttons_in_sequence(options),
                'main_html': self.get_html(options),
                'searchview_html': self.env['ir.ui.view']._render_template(self._get_templates().get('search_suggested_template', 'base_suggested_purchase.search_suggested_template'), values=searchview_dict),
                }
        print(info)
        return info

    def get_html_footnotes(self, footnotes):
        template = self._get_templates().get('footnotes_template', 'base_suggested_purchase.suggested_reports_footnotes_template')
        rcontext = {'footnotes': footnotes, 'context': self.env.context}
        html = self.env['ir.ui.view']._render_template(template, values=rcontext)
        return html




