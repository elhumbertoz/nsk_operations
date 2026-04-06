import pytz
import calendar
from odoo import api, fields, models, http
from odoo.tools.translate import _
from datetime import datetime
from dateutil.relativedelta import relativedelta
import base64
from io import StringIO


class DinardapSuperciasWizard(models.TransientModel):
    _name = "dinardap.supercias.wizard"
    _description = "Informe de Dinardap y SuperCias"

    @api.model
    def default_get(self, fields):
        rec = super(DinardapSuperciasWizard, self).default_get(fields)
        user_tz = pytz.timezone(http.request.env.context.get('tz') or http.request.env.user.tz or 'UTC')
        date_tz = datetime.today().astimezone(user_tz)
        rec.update({
            'start_date': date_tz.replace(day=1).date(),
            'end_date': date_tz.replace(day=(calendar.monthrange(date_tz.year, date_tz.month)[1])).date(),
            'company_id': self.env.company and self.env.company.id or None,
        })
        return rec

    fcname = fields.Char(
        string=_("Nombre de archivo"),
        required=False,
        size=50,
        readonly=True,
    )
    data = fields.Binary(
        string=_("Archivo TXT"),
    )
    show_file = fields.Boolean(
        string=_("Mostrar archivo"),
        required=False,
    )
    company_id = fields.Many2one(
        string=_("Compañía"),
        comodel_name="res.company",
        required=True,
    )
    start_date = fields.Date(
        string=_("Desde"),
    )
    end_date = fields.Date(
        string=_("Hasta"),
        required=True,
    )
    type = fields.Selection(
        string=_("Tipo"),
        selection=[
            ('cut_off_date', _("Por fecha de corte")),
            ('date_range', _("Por rango de fechas")),
        ],
        default='cut_off_date',
        required=True,
    )

    def action_print_xlsx_report(self):
        params = {
            'company_id': self.company_id.id,
            'start_date': fields.Date.to_string(self.start_date),
            'end_date': fields.Date.to_string(self.end_date),
            'type': self.type,
        }
        data_dict = self.data_dict_invoice(params)

        params.update({'data_dict': data_dict})

        report_action = self.env.ref('ek_l10n_ec.dinardap_supercias_xlsx').report_action(self, params)
        report_action['close_on_report_download'] = True
        return report_action

    def action_print_txt_report(self):
        wiz = self
        params = {
            'company_id': self.company_id.id,
            'start_date': fields.Date.to_string(self.start_date),
            'end_date': fields.Date.to_string(self.end_date),
            'type': self.type,

        }
        data_dict = self.data_dict_invoice(params)
        _dfile = ''
        for rec_txt in data_dict:
            list_v = list(rec_txt.values())
            _dfile += "%s\n" % ("|".join(map(str,list_v[9:])))

        month = wiz.start_date.month <= 9 and "0%s" % wiz.start_date.month or str(wiz.start_date.month)
        year = str(wiz.start_date.year)

        buf = StringIO()
        buf.write(_dfile)
        out = base64.b64encode(buf.getvalue().encode())
        buf.close()
        name = "%s%s%s.txt" % (
            "DINARDAP",
            year,
            month
        )

        wiz.write({
            'show_file': True,
            'data': out,
            'fcname': name
        })

        return {
            'name': "Informe de Dirnardap y SuperCias (TXT)",
            'view_mode': 'form',
            'res_id': wiz.id,
            'res_model': 'dinardap.supercias.wizard',
            'type': 'ir.actions.act_window',
            'target': 'new',
            'context': self.env.context,
            'nodestroy': True,
        }

    def get_invoice_data(self, params, company=False):
        if not company:
            company = self.env['res.company'].browse(params.get('company_id'))

        companies = [self.company_id.id]

        if self.company_id.sudo().child_ids:
            companies.extend(self.company_id.sudo().child_ids.ids)

        date_filter = "AND invoice_date <= '%s'" % params.get('end_date')
        if params.get('type') == 'date_range':
            date_filter = "AND invoice_date between '%s' AND '%s'" % (params.get('start_date'), params.get('end_date'))
        query = """
            SELECT id AS invoice_id
            FROM account_move
            WHERE move_type = 'out_invoice'
            AND company_id IN %s
            %s;
        """ % (tuple(companies), date_filter)
        # print(query)
        self.env.cr.execute(query)
        data = self.env.cr.dictfetchall()
        return data

    def data_dict_invoice(self,params):
        company = self.env['res.company'].browse(params.get('company_id'))
        AccountPayment = self.env['account.payment']
        identification_type_ruc = self.env.ref('l10n_ec.ec_ruc')
        identification_type_dni = self.env.ref('l10n_ec.ec_dni')

        invoice_data = self.get_invoice_data(params,company)
        invoice_ids = [item.get('invoice_id') for item in invoice_data]
        invoice_list = self.env['account.move'].sudo().browse(invoice_ids)
        data_list = []

        for invoice in invoice_list:
            partner = invoice.partner_id or None
            cutoff_date = datetime.strptime(params['end_date'], '%Y-%m-%d')

            partner_payments = AccountPayment.sudo().search([
                ('partner_id', '=', invoice.partner_id.id),
            ])
            invoice_payments = partner_payments.filtered(lambda p: invoice.id in p.reconciled_invoice_ids.ids)
            last_payment = not invoice.amount_residual and invoice_payments and \
                           sorted(invoice_payments, key=lambda p: p.id)[-1] or None
            most_significant_payment = not invoice.amount_residual and invoice_payments and \
                                       sorted(invoice_payments, key=lambda p: p.amount)[-1] or None
            payment_method_char = ''
            if most_significant_payment and most_significant_payment.payment_method_line_id:
                if most_significant_payment.payment_method_line_id.code in ['new_third_party_checks', 'in_third_party_checks']:
                    payment_method_char = 'C'
                elif most_significant_payment.payment_method_line_id.code in ['credit_card']:
                    payment_method_char = 'T'
                else:
                    payment_method_char = 'E'

            operation_term = invoice.invoice_date_due - invoice.invoice_date
            default_time = cutoff_date.date() - invoice.invoice_date_due

            identification_type = partner.l10n_latam_identification_type_id or None
            identification_type_char = ''
            if identification_type:
                if identification_type == identification_type_ruc:
                    identification_type_char = 'R'
                elif identification_type == identification_type_dni:
                    identification_type_char = 'C'
                else:
                    identification_type_char = 'E'
            province = partner.state_id or None
            city = partner.l10n_ec_city_id or partner.city_id or None
            parish = partner.l10n_ec_canton_id or None
            data = {
                # Elementos para campos relacionales
                'company_id': company.id,
                'invoice_id': invoice.id,
                'partner_id': partner and partner.id or 0,
                'identification_type_id': identification_type and identification_type.id or 0,
                'province_id': province and province.id or 0,
                'city_id': city and city.id or 0,
                'parish_id': parish and parish.id or 0,
                'last_payment_id': last_payment and last_payment.id or 0,
                'most_significant_payment': most_significant_payment and most_significant_payment.id or None,

                # Elementos para campos de registros
                'entity_code': invoice.partner_id.ref or '',
                'data_date': datetime.strptime(params.get('end_date'), "%Y-%m-%d").strftime("%d/%m/%Y"),
                'identification_type_char': identification_type_char,
                'identification_number': partner and partner.vat or '',
                'partner_name': partner and partner.name or '',
                'partner_class': 'J' if partner.is_company else 'N',
                'province_code': province and "%s%s" % (province.code[-2], province.code[-1]) or '',
                'city_code': city and "%s%s" % (city.code[-2], city.code[-1]) or '',
                'parish_code': parish and "%s%s" % (parish.code[-2], parish.code[-1]) or '',
                'gender': '',
                'marital_status': '',
                'income_origin': '',
                'operation_number': invoice.l10n_latam_document_number,
                'operation_amount': invoice.amount_total,
                'operation_residual': invoice.amount_residual,
                'grant_date': invoice.invoice_date.strftime("%d/%m/%Y"),
                'due_date': invoice.invoice_date_due.strftime("%d/%m/%Y"),
                'required_payment_date': invoice.invoice_date_due.strftime("%d/%m/%Y"),
                'operation_term': operation_term.days,
                'payment_periodicity': invoice.invoice_payment_term_id.periodicity,
                'default_days': invoice.amount_residual and (
                    abs(default_time.days) if cutoff_date.date() > invoice.invoice_date_due else 0) or 0,
                'default_amount': sum(
                    invoice.line_ids.filtered(
                        lambda
                            line: line.amount_residual and
                                  ((line.date_maturity and line.date_maturity < cutoff_date.date())
                                  or not line.date_maturity)
                    ).mapped('amount_residual')
                ),
                'default_rate_amount': 0.0,  # TODO: Está pendiente de que confirme Génesis una vez que averigüe bien
                'amount_to_become_due_001_030': sum(
                    invoice.line_ids.filtered(
                        lambda line: line.amount_residual and
                                     line.date_maturity
                                     and cutoff_date.date() < line.date_maturity <= (cutoff_date.date() + relativedelta(days=30))
                    ).mapped('amount_residual')
                ),
                'amount_to_become_due_031_090': sum(
                    invoice.line_ids.filtered(
                        lambda line: line.amount_residual and
                                     line.date_maturity and (
                                    cutoff_date.date() + relativedelta(days=30)) < line.date_maturity <= (
                                                 cutoff_date.date() + relativedelta(days=90))
                    ).mapped('amount_residual')
                ),
                'amount_to_become_due_091_180': sum(
                    invoice.line_ids.filtered(
                        lambda line: line.amount_residual and
                                     line.date_maturity and (
                                    cutoff_date.date() + relativedelta(days=90)) < line.date_maturity <= (
                                                 cutoff_date.date() + relativedelta(days=180))
                    ).mapped('amount_residual')
                ),
                'amount_to_become_due_181_360': sum(
                    invoice.line_ids.filtered(
                        lambda line: line.amount_residual and
                                     line.date_maturity and (
                                    cutoff_date.date() + relativedelta(days=180)) < line.date_maturity <= (
                                                 cutoff_date.date() + relativedelta(days=360))
                    ).mapped('amount_residual')
                ),
                'amount_to_become_due_361': sum(
                    invoice.line_ids.filtered(
                        lambda line: line.amount_residual and
                                     line.date_maturity and line.date_maturity > (
                                    cutoff_date.date() + relativedelta(days=360))
                    ).mapped('amount_residual')
                ),
                'due_amount_001_030': sum(
                    invoice.line_ids.filtered(
                        lambda line: line.amount_residual and
                                     line.date_maturity and (cutoff_date.date() - relativedelta(
                            days=30) <= line.date_maturity < cutoff_date.date())
                    ).mapped('amount_residual')
                ),
                'due_amount_031_090': sum(
                    invoice.line_ids.filtered(
                        lambda line: line.amount_residual and
                                     line.date_maturity and (
                                    cutoff_date.date() - relativedelta(days=90) <= line.date_maturity < (
                                        cutoff_date.date() - relativedelta(days=30)))
                    ).mapped('amount_residual')
                ),
                'due_amount_091_180': sum(
                    invoice.line_ids.filtered(
                        lambda line: line.amount_residual and
                                     line.date_maturity and (
                                    cutoff_date.date() - relativedelta(days=180) <= line.date_maturity < (
                                        cutoff_date.date() - relativedelta(days=90)))
                    ).mapped('amount_residual')
                ),
                'due_amount_181_360': sum(
                    invoice.line_ids.filtered(
                        lambda line: line.amount_residual and
                                     line.date_maturity and (
                                    cutoff_date.date() - relativedelta(days=360) <= line.date_maturity < (
                                        cutoff_date.date() - relativedelta(days=180)))
                    ).mapped('amount_residual')
                ),
                'due_amount_361': sum(
                    invoice.line_ids.filtered(
                        lambda line: line.amount_residual and
                                     line.date_maturity and line.date_maturity < (
                                    cutoff_date.date() - relativedelta(days=360))
                    ).mapped('amount_residual')
                ),
                'lawsuit_amount': 0.0,
                'punished_portfolio': 0.0,
                'credit_quota_amount': invoice.amount_residual,
                'last_payment_date': last_payment and last_payment.move_id and last_payment.move_id.date.strftime("%d/%m/%Y") or '',
                'payment_method_char': payment_method_char,
            }
            data_list.append(data)
        return data_list
