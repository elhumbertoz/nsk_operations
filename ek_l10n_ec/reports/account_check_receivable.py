# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.


from odoo import models, fields, _
from dateutil.relativedelta import relativedelta
from itertools import chain


class EkReportAccountCheckReceivableBalance(models.AbstractModel):
    _name = "account.aged.check.receivable.balance.l10n_ec.report.handler"
    _description = "Cheques por cobrar"
    _inherit = "account.report.custom.handler"

    def _report_custom_engine_l10n_ec_check_receivable(
            self, expressions, options, date_scope, current_groupby, next_groupby, offset=0, limit=None,warnings=None
    ):
        return self._l10n_ec_aged_partner_report_custom_engine_common(
            options, 'asset_receivable', current_groupby, next_groupby, offset=offset, limit=limit
        )

    def _l10n_ec_aged_partner_report_custom_engine_common(
            self, options, internal_type, current_groupby, next_groupby, offset=0, limit=None
    ):
        report = self.env['account.report'].browse(options['report_id'])
        report._check_groupby_fields(
            (next_groupby.split(',') if next_groupby else []) + ([current_groupby] if current_groupby else [])
        )

        def maximum_days(date_obj, days):
            return fields.Date.to_string(date_obj + relativedelta(days=days))

        date_to = fields.Date.from_string(options['date']['date_to'])
        periods = [
            (False, fields.Date.to_string(date_to)),
            (maximum_days(date_to, 1), maximum_days(date_to, 30)),
            (maximum_days(date_to, 31), maximum_days(date_to, 60)),
            (maximum_days(date_to, 61), maximum_days(date_to, 90)),
            (maximum_days(date_to, 91), maximum_days(date_to, 120)),
            (maximum_days(date_to, 121), False),
        ]

        def build_result_dict(report, query_res_lines):
            rslt = {f'period{i}': 0 for i in range(len(periods))}

            for query_res in query_res_lines:
                for i in range(len(periods)):
                    period_key = f'period{i}'
                    rslt[period_key] += query_res[period_key]

            if current_groupby == 'id':
                query_res = query_res_lines[
                    0]  # We're grouping by id, so there is only 1 element in query_res_lines anyway
                currency = self.env['res.currency'].browse(query_res['currency_id'][0]) if len(
                    query_res['currency_id']) == 1 else None

                due_date = query_res['due_date'][0] if len(query_res['due_date']) == 1 else fields.Date.today()

                diff_days = due_date - date_to

                rslt.update({
                    'due_date': query_res['due_date'][0] if len(query_res['due_date']) == 1 else None,
                    'invoice_date': query_res['date'][0] if len(query_res['date']) == 1 else None,
                    'due_days': abs(int(diff_days.days)) if diff_days.days < 0 else 0,
                    'amount_currency': query_res['amount_currency'],
                    'nmero': query_res['nmero'],
                    'currency_id': query_res['currency_id'][0] if len(query_res['currency_id']) == 1 else None,
                    'currency': currency.display_name if currency else None,
                    'account_name': query_res['account_name'][0] if len(query_res['account_name']) == 1 else None,
                    'expected_date': query_res['expected_date'][0] if len(query_res['expected_date']) == 1 else None,
                    'total': None,
                    'has_sublines': query_res['aml_count'] > 0,

                    # Needed by the custom_unfold_all_batch_data_generator, to speed-up unfold_all
                    'partner_id': query_res['partner_id'][0] if query_res['partner_id'] else None,
                })
            else:
                rslt.update({
                    'due_date': None,
                    'invoice_date': None,
                    'due_days': 0,
                    'nmero': 0,
                    'amount_currency': None,
                    'currency_id': None,
                    'currency': None,
                    'account_name': None,
                    'expected_date': None,
                    'total': sum(rslt[f'period{i}'] for i in range(len(periods))),
                    'has_sublines': False,
                })
            return rslt

        # Build period table
        period_table_format = ('(VALUES %s)' % ','.join("(%s, %s, %s)" for period in periods))
        params = list(chain.from_iterable(
            (period[0] or None, period[1] or None, i)
            for i, period in enumerate(periods)
        ))
        period_table = self.env.cr.mogrify(period_table_format, params).decode(self.env.cr.connection.encoding)

        # Build query
        tables, where_clause, where_params = report._query_get(options, 'strict_range', domain=[('account_id.account_type', '=', internal_type)])

        currency_table = self.env['account.report']._get_query_currency_table(options)
        always_present_groupby = "period_table.period_index, currency_table.rate, currency_table.precision"
        if current_groupby:
            select_from_groupby = f"account_move_line.{current_groupby} AS grouping_key,"
            groupby_clause = f"account_move_line.{current_groupby}, {always_present_groupby}"
        else:
            select_from_groupby = ''
            groupby_clause = always_present_groupby
        select_period_query = ','.join(
            f"""
                CASE WHEN period_table.period_index = {i}
                THEN %s * (
                    SUM(ROUND(account_move_line.balance * currency_table.rate, currency_table.precision))                    
                )
                ELSE 0 END AS period{i}
            """
            for i in range(len(periods))
        )

        tail_query, tail_params = report._get_engine_query_tail(offset, limit)
        query = f"""
            WITH period_table(date_start, date_stop, period_index) AS ({period_table})

            SELECT
                {select_from_groupby}
                %s * 1 AS amount_currency,
                ARRAY_AGG(DISTINCT account_move_line.partner_id) AS partner_id,
                ARRAY_AGG(account_move_line.payment_id) AS payment_id,
                ARRAY_AGG(DISTINCT COALESCE(payment.l10n_latam_check_payment_date, account_move_line.date)) AS report_date,
                ARRAY_AGG(DISTINCT payment.l10n_latam_check_payment_date) AS expected_date,
                ARRAY_AGG(DISTINCT account.code) AS account_name,
                ARRAY_AGG(DISTINCT payment.check_number) as nmero,
                ARRAY_AGG(DISTINCT COALESCE(payment.l10n_latam_check_payment_date, account_move_line.date)) AS due_date,
                ARRAY_AGG(DISTINCT COALESCE(account_move_line.date, account_move_line.invoice_date)) AS date,                
                ARRAY_AGG(DISTINCT account_move_line.currency_id) AS currency_id,
                COUNT(account_move_line.id) AS aml_count,
                ARRAY_AGG(account.code) AS account_code,
                {select_period_query}

            FROM {tables}

            JOIN account_journal journal ON journal.id = account_move_line.journal_id
            JOIN account_account account ON account.id = account_move_line.account_id
            JOIN account_payment payment ON 
               payment.l10n_latam_check_bank_id is not null
               AND payment.payment_type = 'inbound' 
               AND payment.move_id = account_move_line.move_id
            JOIN {currency_table} ON currency_table.company_id = account_move_line.company_id           

            JOIN period_table ON
                (
                    period_table.date_start IS NULL
                    OR COALESCE(payment.l10n_latam_check_payment_date, account_move_line.date) >= DATE(period_table.date_start)
                )
                AND
                (
                    period_table.date_stop IS NULL
                    OR COALESCE(payment.l10n_latam_check_payment_date, account_move_line.date) <= DATE(period_table.date_stop)
                )

            WHERE {where_clause}
                AND payment.amount > 0 AND payment.is_matched != True
            GROUP BY {groupby_clause}
        """

        multiplicator = 1 if internal_type == 'liability_payable' else -1
        params = [
            multiplicator,
            *([multiplicator] * len(periods)),
            *where_params,
            *tail_params,
        ]
        self._cr.execute(query, params)
        query_res_lines = self._cr.dictfetchall()

        if not current_groupby:
            return build_result_dict(report, query_res_lines)
        else:
            rslt = []

            all_res_per_grouping_key = {}
            for query_res in query_res_lines:
                grouping_key = query_res['grouping_key']
                all_res_per_grouping_key.setdefault(grouping_key, []).append(query_res)

            for grouping_key, query_res_lines in all_res_per_grouping_key.items():
                rslt.append((grouping_key, build_result_dict(report, query_res_lines)))

            return rslt

    def open_journal_items(self, options, params):
        params['view_ref'] = 'account.view_move_line_tree_grouped_partner'
        options_for_audit = {**options, 'date': {**options['date'], 'date_from': None}}
        action = self.env['account.report'].open_journal_items(options=options_for_audit, params=params)
        action.get('context', {}).update({'search_default_group_by_account': 0, 'search_default_group_by_partner': 1})
        return action

    def _common_custom_unfold_all_batch_data_generator(self, internal_type, report, options, lines_to_expand_by_function):
        rslt = {} # In the form {full_sub_groupby_key: all_column_group_expression_totals for this groupby computation}
        report_periods = 6 # The report has 6 periods

        for expand_function_name, lines_to_expand in lines_to_expand_by_function.items():
            for line_to_expand in lines_to_expand: # In standard, this loop will execute only once
                if expand_function_name == '_report_expand_unfoldable_line_with_groupby':
                    report_line_id = report._get_res_id_from_line_id(line_to_expand['id'], 'account.report.line')
                    expressions_to_evaluate = report.line_ids.expression_ids.filtered(
                        lambda x: x.report_line_id.id == report_line_id and x.engine == 'custom'
                    )

                    if not expressions_to_evaluate:
                        continue

                    for column_group_key, column_group_options in report._split_options_per_column_group(options).items():
                        # Get all aml results by partner
                        aml_data_by_partner = {}
                        for aml_id, aml_result in self._l10n_ec_aged_partner_report_custom_engine_common(
                                column_group_options, internal_type, 'id', None
                        ):
                            aml_result['aml_id'] = aml_id
                            aml_data_by_partner.setdefault(aml_result['partner_id'], []).append(aml_result)

                        # Iterate on results by partner to generate the content of the column group
                        partner_expression_totals = rslt.setdefault(f"[{report_line_id}]=>partner_id", {}).setdefault(
                            column_group_key, {expression: {'value': []} for expression in expressions_to_evaluate}
                        )
                        for partner_id, aml_data_list in aml_data_by_partner.items():
                            partner_values = self._prepare_partner_values()
                            for i in range(report_periods):
                                partner_values[f'period{i}'] = 0

                            # Build expression totals under the right key
                            partner_aml_expression_totals = rslt.setdefault(f"[{report_line_id}]partner_id:{partner_id}=>id", {}).setdefault(
                                column_group_key, {expression: {'value': []} for expression in expressions_to_evaluate}
                            )
                            for aml_data in aml_data_list:
                                for i in range(report_periods):
                                    period_value = aml_data[f'period{i}']
                                    partner_values[f'period{i}'] += period_value
                                    partner_values['total'] += period_value

                                for expression in expressions_to_evaluate:
                                    partner_aml_expression_totals[expression]['value'].append(
                                        (aml_data['aml_id'], aml_data[expression.subformula])
                                    )

                            for expression in expressions_to_evaluate:
                                partner_expression_totals[expression]['value'].append(
                                    (partner_id, partner_values[expression.subformula])
                                )

        return rslt

    def _prepare_partner_values(self):
        partner_values = {
            'due_date': None,
            'invoice_date': None,
            'due_days': 0,
            'nmero': None,
            'amount_currency': None,
            'currency_id': None,
            'currency': None,
            'account_name': None,
            'expected_date': None,
            'total': 0,
        }

        return partner_values


class EkReportAccountCheckReceivableHandler(models.AbstractModel):
    _name = 'account.aged.check.balance.l10n_ec.report.handler'
    _inherit = 'account.aged.check.receivable.balance.l10n_ec.report.handler'
    _description = 'Aged Payable Custom Handler'

    def _custom_options_initializer(self, report, options, previous_options=None):
        super()._custom_options_initializer(report, options, previous_options=previous_options)
        if options.get('account_type'):
            options['account_type'] = [
                account_type for account_type in options['account_type'] if
                account_type['id'] not in ('trade_payable', 'non_trade_payable')
            ]

    def open_journal_items(self, options, params):
        receivable_account_type = {'id': 'trade_receivable', 'name': _("Receivable"), 'selected': True}
        if 'account_type' in options:
            options['account_type'].append(receivable_account_type)
        else:
            options['account_type'] = [receivable_account_type]

        return super().open_journal_items(options, params)

    def _custom_unfold_all_batch_data_generator(self, report, options, lines_to_expand_by_function):
        # We only optimize to unfold all if the groupby value of the report has not been customized. Else, we'll just run the full computation
        if self.env.ref('ek_l10n_ec.aged_receivable_check_line').groupby.replace(' ', '') == 'partner_id,id':
            return self._common_custom_unfold_all_batch_data_generator('asset_receivable', report, options,
                                                                       lines_to_expand_by_function)
        return {}

    def _group_by_account(self, report, lines, options):
        """
        This function adds the grouping lines on top of each group of account.asset
        It iterates over the lines, change the line_id of each line to include the account.account.id and the
        account.asset.id.
        """
        if not lines:
            return lines

        line_vals_per_account_id = {}
        for line in lines:
            parent_account_id = line.get('assets_account_id')

            model, res_id = report._get_model_info_from_id(line['id'])
            assert model == 'account.asset'

            # replace the line['id'] to add the account.account.id
            line['id'] = report._build_line_id([
                (None, 'account.account', parent_account_id),
                (None, 'account.asset', res_id)
            ])

            line_vals_per_account_id.setdefault(parent_account_id, {
                # We don't assign a name to the line yet, so that we can batch the browsing of account.account objects
                'id': report._build_line_id([(None, 'account.account', parent_account_id)]),
                'columns': [],  # Filled later
                'unfoldable': True,
                'unfolded': options.get('unfold_all', False),
                'level': 1,

                # This value is stored here for convenience; it will be removed from the result
                'group_lines': [],
            })['group_lines'].append(line)

        # Generate the result
        idx_monetary_columns = [idx_col for idx_col, col in enumerate(options['columns']) if
                                col['figure_type'] == 'monetary']
        accounts = self.env['account.account'].browse(line_vals_per_account_id.keys())
        rslt_lines = []
        for account in accounts:
            account_line_vals = line_vals_per_account_id[account.id]
            account_line_vals['name'] = f"{account.code} {account.name}"

            rslt_lines.append(account_line_vals)

            group_totals = {column_index: 0 for column_index in idx_monetary_columns}
            group_lines = report._regroup_lines_by_name_prefix(
                options,
                account_line_vals.pop('group_lines'),
                '_report_expand_unfoldable_line_assets_report_prefix_group',
                account_line_vals['level'],
                parent_line_dict_id=account_line_vals['id'],
            )

            for account_subline in group_lines:
                # Add this line to the group totals
                for column_index in idx_monetary_columns:
                    group_totals[column_index] += account_subline['columns'][column_index].get('no_format', 0)

                # Setup the parent and add the line to the result
                account_subline['parent_id'] = account_line_vals['id']
                rslt_lines.append(account_subline)

            # Add totals (columns) to the account line
            for column_index in range(len(options['columns'])):
                account_line_vals['columns'].append(report._build_column_dict(
                    group_totals.get(column_index, ''),
                    options['columns'][column_index],
                    options=options,
                ))

        return rslt_lines
