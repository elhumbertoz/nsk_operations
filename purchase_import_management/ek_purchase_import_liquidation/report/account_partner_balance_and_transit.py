# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import models, api, fields, _
from odoo.tools.misc import format_date

from dateutil.relativedelta import relativedelta
from itertools import chain


class EkReportAccountAgedPayableAndTransit(models.Model):
    _name = "ek.account.aged.payable.transit"
    _description = "Cuentas por Pagar"
    _inherit = "account.aged.partner"
    #filter_journals = False
    #filter_partner = False
    _auto = False

    period0 = fields.Monetary(string='Al: ')
    period1 = fields.Monetary(string='1 - 30')
    period2 = fields.Monetary(string='31 - 60')
    period3 = fields.Monetary(string='61 - 90')
    period4 = fields.Monetary(string='Más antiguos')
    transit = fields.Monetary(string='Transito')
    invoice_date = fields.Date(string='Fecha')
    report_date = fields.Date(group_operator='max', string='Vencimiento')
    move_ref = fields.Char(
        string='Ref.',
        required=False)

    def _get_options(self, previous_options=None):
        # OVERRIDE
        options = super(EkReportAccountAgedPayableAndTransit, self)._get_options(previous_options=previous_options)
        options['filter_account_type'] = 'payable'
        return options

    @api.model
    def _get_report_name(self):
        return _("Cuentas por Pagar + Pedidos en Transito")

    @api.model
    def _get_templates(self):
        # OVERRIDE
        templates = super(EkReportAccountAgedPayableAndTransit, self)._get_templates()
        templates['line_template'] = 'account_reports.line_template_aged_payable_report'
        return templates

        ####################################################
        # COLUMNS/LINES
        ####################################################

    @api.model
    def _get_column_details(self, options):
        obj = self.env['account.move']

        columns = [
            self._header_column(),

            self._field_column('invoice_date', name=_("Fecha")),
            self._field_column('report_date'),
            self._field_column('account_name', name=_("Account"), ellipsis=True),
            self._field_column('move_ref', name=_("Ref."), ellipsis=True),

            self._field_column('transit'),
            # self._field_column('period5', sortable=True),
            self._field_column('period0', name=_("As of: %s", format_date(self.env, options['date']['date_to']))),
            self._field_column('period1', sortable=True),
            self._field_column('period2', sortable=True),
            self._field_column('period3', sortable=True),
            self._field_column('period4', sortable=True),
            self._custom_column(  # Avoid doing twice the sub-select in the view
                name=_('Total'),
                classes=['number'],
                formatter=self.format_value,
                getter=(
                    lambda v: v['period0'] + v['period1'] + v['period2'] + v['period3'] + v['period4']),
                sortable=True,
            ),
        ]

        if self.user_has_groups('base.group_multi_currency'):
            columns[2:2] = [
                self._field_column('amount_currency'),
                self._field_column('currency_id'),
            ]
        return columns

    ####################################################
    # QUERIES
    ####################################################

    @api.model
    def _get_query_period_table(self, options):
        ''' Compute the periods to handle in the report.
        E.g. Suppose date = '2019-01-09', the computed periods will be:

        Name                | Start         | Stop
        --------------------------------------------
        As of 2019-01-09    | 2019-01-09    |
        1 - 30              | 2018-12-10    | 2019-01-08
        31 - 60             | 2018-11-10    | 2018-12-09
        61 - 90             | 2018-10-11    | 2018-11-09
        91 - 120            | 2018-09-11    | 2018-10-10
        Older               |               | 2018-09-10

        Then, return the values as an sql floating table to use it directly in queries.

        :return: A floating sql query representing the report's periods.
        '''
        def maximum_days(date_obj, days):
            return fields.Date.to_string(date_obj + relativedelta(days=days))

        date_str = options['date']['date_to']
        date = fields.Date.from_string(date_str)
        period_values = [
            (False,                  date_str),
            (maximum_days(date, 1),    maximum_days(date, 30)),
            (maximum_days(date, 31),   maximum_days(date, 60)),
            (maximum_days(date, 61),   maximum_days(date, 90)),
            (maximum_days(date, 91),  maximum_days(date, 365)),
            (maximum_days(date, 366),  False),
        ]

        period_table = ('(VALUES %s) AS period_table(date_start, date_stop, period_index)' %
                        ','.join("(%s, %s, %s)" for i, period in enumerate(period_values)))

        params = list(chain.from_iterable(
            (period[0] or None, period[1] or None, i)
            for i, period in enumerate(period_values)
        ))
        return self.env.cr.mogrify(period_table, params).decode(self.env.cr.connection.encoding)

    @api.model
    def _get_sql(self):
        options = self.env.context['report_options']
        obj = self.env['account.move']


        query = ("""
            (
                  SELECT 
                    PO.id,
                    66293 as move_id,
                    PO.name, 
                    NULL as account_id,
                    NULL as journal_id,
                    PO.company_id,
                    NULL as currency_id,
                    NULL as analytic_account_id,
                    NULL as display_type,
                    PO.date_order as date,
                    0 as debit,
                    (PO.amount_total - amove_purchase.amount_total) as credit,
                    (PO.amount_total - amove_purchase.amount_total) as balance,  
                    0 as amount_currency,
                    PO.partner_id, 
                    RP.name as partner_name,
                    (PO.amount_total - amove_purchase.amount_total) as transit,
                    'normal' as partner_trust,
                    NULL as report_currency_id,
                    NULL as payment_id,
                    PO.date_order as report_date,
                    NULL as expected_pay_date,
                    PO.date_order as invoice_date,
                    'entry' as move_type,
                    PO.name as move_name, 
                    COALESCE(PO.partner_ref,PO.name) as move_ref,
                    NULL as account_name,
                    NULL as account_code,
                    (PO.amount_total - amove_purchase.amount_total) as period0,
                    0 as period1,
                    0 as period2,
                    0 as period3,
                    0 as period4,
                    0 as period5  
                    FROM purchase_order PO
                    JOIN res_partner RP on RP.id = PO.partner_id
                    JOIN (
                        SELECT distinct amove.amount_total, order_line.order_id 
                        FROM purchase_order_line order_line
                        JOIN account_move_line move_line
                        ON move_line.purchase_line_id = order_line.id
                        JOIN account_move amove 
                        ON amove.id = move_line.move_id
                    ) amove_purchase ON amove_purchase.order_id = PO.id
                    WHERE PO.is_import = true
                    AND PO.state = 'purchase'
                    AND PO.invoice_status != 'invoiced'
                    AND (PO.amount_total - amove_purchase.amount_total) > 0
                   )
                UNION ALL
                SELECT
                    {move_line_fields},
                    account_move_line.amount_currency as amount_currency,
                    account_move_line.partner_id AS partner_id,
                    partner.name AS partner_name,
                    0 as transit,
                    COALESCE(trust_property.value_text, 'normal') AS partner_trust,
                    COALESCE(account_move_line.currency_id, journal.currency_id) AS report_currency_id,
                    account_move_line.payment_id AS payment_id,
                    COALESCE(account_move_line.date_maturity, account_move_line.date) AS report_date,
                    account_move_line.expected_pay_date AS expected_pay_date,
                    COALESCE(move.invoice_date, account_move_line.date) AS invoice_date,
                    move.move_type AS move_type,
                    move.name AS move_name,
                    move.ref AS move_ref,
                    account.code || ' ' || account.name AS account_name,
                    account.code AS account_code,""" + ','.join([("""
                    CASE WHEN period_table.period_index = {i}
                    THEN %(sign)s * ROUND((
                        account_move_line.balance - COALESCE(SUM(part_debit.amount), 0) + COALESCE(SUM(part_credit.amount), 0)
                    ) * currency_table.rate, currency_table.precision)
                    ELSE 0 END AS period{i}""").format(i=i) for i in range(6)]) + """
                FROM account_move_line
                JOIN account_move move ON account_move_line.move_id = move.id
                JOIN account_journal journal ON journal.id = account_move_line.journal_id
                JOIN account_account account ON account.id = account_move_line.account_id
                LEFT JOIN res_partner partner ON partner.id = account_move_line.partner_id
                LEFT JOIN ir_property trust_property ON (
                    trust_property.res_id = 'res.partner,'|| account_move_line.partner_id
                    AND trust_property.name = 'trust'
                    AND trust_property.company_id = account_move_line.company_id
                )
                JOIN {currency_table} ON currency_table.company_id = account_move_line.company_id
                LEFT JOIN LATERAL (
                    SELECT part.amount, part.debit_move_id
                    FROM account_partial_reconcile part
                    WHERE part.max_date <= %(date)s
                ) part_debit ON part_debit.debit_move_id = account_move_line.id
                LEFT JOIN LATERAL (
                    SELECT part.amount, part.credit_move_id
                    FROM account_partial_reconcile part
                    WHERE part.max_date <= %(date)s
                ) part_credit ON part_credit.credit_move_id = account_move_line.id
                JOIN {period_table} ON (
                    period_table.date_start IS NULL
                    OR COALESCE(account_move_line.date_maturity, account_move_line.date) >= DATE(period_table.date_start)
                )
                AND (
                    period_table.date_stop IS NULL
                    OR COALESCE(account_move_line.date_maturity, account_move_line.date) <= DATE(period_table.date_stop)
                )
                WHERE account.internal_type = %(account_type)s
                AND account.exclude_from_aged_reports IS NOT TRUE
                GROUP BY account_move_line.id, partner.id, trust_property.id, journal.id, move.id, account.id,
                         period_table.period_index, currency_table.rate, currency_table.precision
                HAVING ROUND(account_move_line.balance - COALESCE(SUM(part_debit.amount), 0) + COALESCE(SUM(part_credit.amount), 0), currency_table.precision) != 0
                
            """).format(
            move_line_fields=self._get_move_line_fields('account_move_line'),
            currency_table=self.env['res.currency']._get_query_currency_table(options),
            period_table=self._get_query_period_table(options),
        )
        params = {
            'account_type': options['filter_account_type'],
            'sign': 1 if options['filter_account_type'] == 'receivable' else -1,
            'date': options['date']['date_to'],
        }
        return self.env.cr.mogrify(query, params).decode(self.env.cr.connection.encoding)
