from odoo import models
from datetime import datetime
from dateutil.relativedelta import relativedelta


class DinardapSupercias(models.AbstractModel):
    _name = "report.ek_l10n_ec.dinardap_supercias"
    _inherit = 'report.report_xlsx.abstract'
    _description = "Dinardap y SuperCias"

    def generate_xlsx_report(self, workbook, params, partners=None):
        company = self.env['res.company'].browse(params.get('company_id'))

        headers = {
            'entity_code': "Código de entidad",
            'data_date': "Fecha de datos",
            'identification_type_char': "Tipo de identificación del sujeto",
            'identification_number': "Identificación del sujeto",
            'partner_name': "Nombre del sujeto",
            'partner_class': "Clase del sujeto",
            'province_code': "Provincia",
            'city_code': "Cantón",
            'parish_code': "Parroquia",
            'gender': "Sexo",
            'marital_status': "Estado civil",
            'income_origin': "Origen de ingresos",
            'operation_number': "Número de operación",
            'operation_amount': "Valor de la operación",
            'operation_residual': "Saldo operación",
            'grant_date': "Fecha de concesión",
            'due_date': "Fecha de vencimiento",
            'required_payment_date': "Fecha que es exigible",
            'operation_term': "Plazo operación",
            'payment_periodicity': "Periodicidad de pago",
            'default_days': "Días de morosidad",
            'default_amount': "Monto de morosidad",
            'default_rate_amount': "Monto de interés en mora",
            'amount_to_become_due_001_030': "Valor por vencer de 1 a 30 días",
            'amount_to_become_due_031_090': "Valor por vencer de 31 a 90 días",
            'amount_to_become_due_091_180': "Valor por vencer de 91 a 180 días",
            'amount_to_become_due_181_360': "Valor por vencer de 181 a 360 días",
            'amount_to_become_due_361': "Valor por vencer de más de 360 días",
            'due_amount_001_030': "Valor vencido de 1 a 30 días",
            'due_amount_031_090': "Valor vencido de 31 a 90 días",
            'due_amount_091_180': "Valor vencido de 91 a 180 días",
            'due_amount_181_360': "Valor vencido de 181 a 360 días",
            'due_amount_361': "Valor vencido de más de 360 días",
            'lawsuit_amount': "Valor en demanda judicial",
            'punished_portfolio': "Cartera castigada",
            'credit_quota_amount': "Cuota del crédito",
            'last_payment_date': "Fecha de cancelación",
            'payment_method_char': "Forma de cancelación",
        }

        workbook.formats[0].set_font_size(9)
        worksheet = workbook.add_worksheet(name="Ventas")
        worksheet.set_landscape()
        worksheet.center_horizontally()
        worksheet.set_paper(9)
        worksheet.set_margins(left=0.125, right=0.125, top=0.85, bottom=0.15)
        workbook.formats[0].set_font_size(9)

        # Tamaño de columnas
        worksheet.set_column('A:A', 12)
        worksheet.set_column('B:B', 11)
        worksheet.set_column('C:C', 6)
        worksheet.set_column('D:D', 20)
        worksheet.set_column('E:E', 24)
        worksheet.set_column('F:F', 6)
        worksheet.set_column('G:G', 6)
        worksheet.set_column('H:H', 6)
        worksheet.set_column('I:I', 6)
        worksheet.set_column('J:J', 6)
        worksheet.set_column('K:K', 6)
        worksheet.set_column('L:L', 6)
        worksheet.set_column('M:M', 20)
        worksheet.set_column('N:N', 10)
        worksheet.set_column('O:O', 10)
        worksheet.set_column('P:P', 11)
        worksheet.set_column('Q:Q', 11)
        worksheet.set_column('R:R', 11)
        worksheet.set_column('S:S', 8)
        worksheet.set_column('T:T', 8)
        worksheet.set_column('U:U', 8)
        worksheet.set_column('V:V', 10)
        worksheet.set_column('W:W', 10)
        worksheet.set_column('X:X', 10)
        worksheet.set_column('Y:Y', 10)
        worksheet.set_column('Z:Z', 10)
        worksheet.set_column('AA:AA', 10)
        worksheet.set_column('AB:AB', 10)
        worksheet.set_column('AC:AC', 10)
        worksheet.set_column('AD:AD', 10)
        worksheet.set_column('AE:AE', 10)
        worksheet.set_column('AF:AF', 10)
        worksheet.set_column('AG:AG', 10)
        worksheet.set_column('AH:AH', 10)
        worksheet.set_column('AI:AI', 10)
        worksheet.set_column('AJ:AJ', 10)
        worksheet.set_column('AK:AK', 11)
        worksheet.set_column('AL:AL', 10)

        # Filtros automáticos
        worksheet.autofilter('A5:AL5')

        # Formatos
        title_string = workbook.add_format({'num_format': '@', 'bold': True, 'font_size': 14, 'valign': 'top', 'align': 'center'})
        subtitle_string = workbook.add_format({'num_format': '@', 'bold': True, 'font_size': 11, 'valign': 'top', 'align': 'center'})
        header_string = workbook.add_format({'num_format': '@', 'bold': True, 'font_size': 10, 'top': 1, 'bottom': 1, 'valign': 'top'})
        content_datetime = workbook.add_format({'num_format': 'dd/mm/yyyy', 'font_size': 9, 'valign': 'top'})
        content_real_number = workbook.add_format({'num_format': '0.00', 'font_size': 9, 'valign': 'top'})
        content_integer_number = workbook.add_format({'num_format': '0', 'font_size': 9, 'valign': 'top'})
        content_string = workbook.add_format({'num_format': '@', 'font_size': 9, 'valign': 'top'})

        # Título
        row = 0
        worksheet.merge_range(row, 0, row, 37, company.name.upper(), title_string)
        row += 1
        worksheet.merge_range(row, 0, row, 37, "Informe Dinardap y SuperCias", subtitle_string)
        row += 1
        date_information = "Fecha de corte: %s" % datetime.strptime(params.get('end_date'), "%Y-%m-%d").strftime("%d/%m/%Y")
        if params.get('type') == 'date_range':
            date_information = "Desde: %s -  Hasta: %s" % (
                datetime.strptime(params.get('start_date'), "%Y-%m-%d").strftime("%d/%m/%Y"),
                datetime.strptime(params.get('end_date'), "%Y-%m-%d").strftime("%d/%m/%Y")
            )
        worksheet.merge_range(row, 0, row, 37, date_information, subtitle_string)

        # Cabeceras
        row += 2
        worksheet.write(row, 0, headers['entity_code'], header_string)
        worksheet.write(row, 1, headers['data_date'], header_string)
        worksheet.write(row, 2, headers['identification_type_char'], header_string)
        worksheet.write(row, 3, headers['identification_number'], header_string)
        worksheet.write(row, 4, headers['partner_name'], header_string)
        worksheet.write(row, 5, headers['partner_class'], header_string)
        worksheet.write(row, 6, headers['province_code'], header_string)
        worksheet.write(row, 7, headers['city_code'], header_string)
        worksheet.write(row, 8, headers['parish_code'], header_string)
        worksheet.write(row, 9, headers['gender'], header_string)
        worksheet.write(row, 10, headers['marital_status'], header_string)
        worksheet.write(row, 11, headers['income_origin'], header_string)
        worksheet.write(row, 12, headers['operation_number'], header_string)
        worksheet.write(row, 13, headers['operation_amount'], header_string)
        worksheet.write(row, 14, headers['operation_residual'], header_string)
        worksheet.write(row, 15, headers['grant_date'], header_string)
        worksheet.write(row, 16, headers['due_date'], header_string)
        worksheet.write(row, 17, headers['required_payment_date'], header_string)
        worksheet.write(row, 18, headers['operation_term'], header_string)
        worksheet.write(row, 19, headers['payment_periodicity'], header_string)
        worksheet.write(row, 20, headers['default_days'], header_string)
        worksheet.write(row, 21, headers['default_amount'], header_string)
        worksheet.write(row, 22, headers['default_rate_amount'], header_string)
        worksheet.write(row, 23, headers['amount_to_become_due_001_030'], header_string)
        worksheet.write(row, 24, headers['amount_to_become_due_031_090'], header_string)
        worksheet.write(row, 25, headers['amount_to_become_due_091_180'], header_string)
        worksheet.write(row, 26, headers['amount_to_become_due_181_360'], header_string)
        worksheet.write(row, 27, headers['amount_to_become_due_361'], header_string)
        worksheet.write(row, 28, headers['due_amount_001_030'], header_string)
        worksheet.write(row, 29, headers['due_amount_031_090'], header_string)
        worksheet.write(row, 30, headers['due_amount_091_180'], header_string)
        worksheet.write(row, 31, headers['due_amount_181_360'], header_string)
        worksheet.write(row, 32, headers['due_amount_361'], header_string)
        worksheet.write(row, 33, headers['lawsuit_amount'], header_string)
        worksheet.write(row, 34, headers['punished_portfolio'], header_string)
        worksheet.write(row, 35, headers['credit_quota_amount'], header_string)
        worksheet.write(row, 36, headers['last_payment_date'], header_string)
        worksheet.write(row, 37, headers['payment_method_char'], header_string)

        data_list = params.get('data_dict', [])
        # Contenido
        row += 1
        for item in data_list:
            worksheet.write(row, 0, item['entity_code'], content_string)
            worksheet.write(row, 1, item['data_date'], content_datetime)
            worksheet.write(row, 2, item['identification_type_char'], content_string)
            worksheet.write(row, 3, item['identification_number'], content_string)
            worksheet.write(row, 4, item['partner_name'], content_string)
            worksheet.write(row, 5, item['partner_class'], content_string)
            worksheet.write(row, 6, item['province_code'], content_string)
            worksheet.write(row, 7, item['city_code'], content_string)
            worksheet.write(row, 8, item['parish_code'], content_string)
            worksheet.write(row, 9, item['gender'], content_string)
            worksheet.write(row, 10, item['marital_status'], content_string)
            worksheet.write(row, 11, item['income_origin'], content_string)
            worksheet.write(row, 12, item['operation_number'], content_string)
            worksheet.write(row, 13, item['operation_amount'], content_real_number)
            worksheet.write(row, 14, item['operation_residual'], content_real_number)
            worksheet.write(row, 15, item['grant_date'], content_datetime)
            worksheet.write(row, 16, item['due_date'], content_datetime)
            worksheet.write(row, 17, item['required_payment_date'], content_datetime)
            worksheet.write(row, 18, item['operation_term'], content_integer_number)
            worksheet.write(row, 19, item['payment_periodicity'], content_integer_number)
            worksheet.write(row, 20, item['default_days'], content_integer_number)
            worksheet.write(row, 21, item['default_amount'], content_real_number)
            worksheet.write(row, 22, item['default_rate_amount'], content_real_number)
            worksheet.write(row, 23, item['amount_to_become_due_001_030'], content_real_number)
            worksheet.write(row, 24, item['amount_to_become_due_031_090'], content_real_number)
            worksheet.write(row, 25, item['amount_to_become_due_091_180'], content_real_number)
            worksheet.write(row, 26, item['amount_to_become_due_181_360'], content_real_number)
            worksheet.write(row, 27, item['amount_to_become_due_361'], content_real_number)
            worksheet.write(row, 28, item['due_amount_001_030'], content_real_number)
            worksheet.write(row, 29, item['due_amount_031_090'], content_real_number)
            worksheet.write(row, 30, item['due_amount_091_180'], content_real_number)
            worksheet.write(row, 31, item['due_amount_181_360'], content_real_number)
            worksheet.write(row, 32, item['due_amount_361'], content_real_number)
            worksheet.write(row, 33, item['lawsuit_amount'], content_real_number)
            worksheet.write(row, 34, item['punished_portfolio'], content_real_number)
            worksheet.write(row, 35, item['credit_quota_amount'], content_real_number)
            worksheet.write(row, 36, item['last_payment_date'], content_datetime)
            worksheet.write(row, 37, item['payment_method_char'], content_string)
            row += 1


