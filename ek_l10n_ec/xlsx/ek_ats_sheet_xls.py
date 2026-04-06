import json
from odoo import fields, models, api
from odoo.addons.report_xlsx_helper.report.report_xlsx_format import FORMATS


class EkAtsSheetXls(models.AbstractModel):
    _name = "report.ek_l10n_ec.sheet_report_xls"
    _description = "Impresión de ATS en XLSX"
    _inherit = "report.report_xlsx.abstract"

    def det_compras(self, wizard):
        tax_group_obj = self.env['account.tax.group']
        compras = []
        inv_obj = self.env['account.move']

        companies = [wizard.company_id.id]

        if wizard.company_id.sudo().child_ids:
            companies.extend(wizard.company_id.sudo().child_ids.ids)

        # Facturas de Compra con retenciones
        inv_ids = inv_obj.sudo().search([
            ('state', 'in', ['posted']),
            ('invoice_date', '>=', str(wizard.date_start)),
            ('invoice_date', '<=', str(wizard.date_end)),
            ('journal_id.code', 'not in', ['CXP', 'cxp']),
            ('l10n_latam_document_type_id.ats_declare', '=', True),
            ('company_id', 'in', companies),
            ('move_type', 'in', ['in_invoice', 'liq_purchase', 'in_refund'])
        ])

        sumarizado = 0
        for inv in inv_ids:
            line = {}
            auth = False

            se = inv.l10n_latam_document_number[0:3]
            pe = inv.l10n_latam_document_number[4:7]
            sec = inv.l10n_latam_document_number[-9:]

            if hasattr(inv, "authorisation_id"):
                auth = inv.authorisation_id.name

            if not auth:
                auth = inv.l10n_ec_authorization_number or ''

            valRetBien10, valRetServ20, valorRetBienes, valorRetServicios, valRetServ50, valorRetServ100 = wizard._get_ret_iva(
                inv)

            amount_ice = 0
            amount_vat = 0
            amount_novat = abs(inv.l10n_latam_amount_untaxed_not_charged_vat)
            base_not_cero = 0
            line_cero = abs(inv.l10n_latam_amount_untaxed_zero)
            line_exempt = abs(inv.l10n_latam_amount_untaxed_exempt_vat)
            invoice_totals = inv.tax_totals
            for amount_by_group_list in invoice_totals['groups_by_subtotal'].values():
                for amount_by_group in amount_by_group_list:
                    tax_group = tax_group_obj.browse(amount_by_group.get('tax_group_id', 0))

                    base = amount_by_group.get('tax_group_base_amount', 0.00)
                    amount = amount_by_group.get('tax_group_amount', 0.00)

                    # if tax_group.l10n_ec_type == 'zero_vat':
                    #    data_for_document_type[key]['base0'] += base
                    if tax_group and tax_group.l10n_ec_type == 'ice':
                        amount_ice += amount
                    # if tax_group.l10n_ec_type in ['not_charged_vat','exempt_vat']:
                    #    data_for_document_type[key]['novat'] += base
                    if tax_group and tax_group.l10n_ec_type in ['vat05', 'vat08', 'vat12', 'vat13', 'vat14', 'vat15']:
                        amount_vat += amount
                        base_not_cero += base

            tpIdCliente = inv.partner_id.l10n_latam_identification_type_id.code_ats_purchase
            if not tpIdCliente and hasattr(inv.partner_id.l10n_latam_identification_type_id, "electronic_code"):
                tpIdCliente = inv.partner_id.l10n_latam_identification_type_id.electronic_code

            line["1"] = inv.l10n_latam_document_number
            line["2"] = inv.journal_id.code
            line["3"] = "P/R FAC. # %s-%s-%s %s" % (se, pe, sec, (inv.ref and inv.ref or ""))
            line["4"] = "%s %s" % (
                inv.l10n_latam_document_sustento.code or '', inv.l10n_latam_document_sustento.type or '')
            line["5"] = tpIdCliente or ''
            line["6"] = inv.partner_id.vat
            line["7"] = inv.partner_id.name
            line["8"] = inv.l10n_latam_document_type_id and inv.l10n_latam_document_type_id.code or '03'
            line["9"] = inv.invoice_date and inv.invoice_date.strftime('%d-%m-%Y') or ''
            line["10"] = se
            line["11"] = pe
            line["12"] = sec
            line["13"] = inv.invoice_date and inv.invoice_date.strftime('%d-%m-%Y') or ''
            line["14"] = auth
            line["15"] = amount_novat == 0 and 0.00 or round(amount_novat, 2)
            line["16"] = round(float(line_cero), 2)
            line["17"] = round(float(base_not_cero), 2)
            line["18"] = round(float(line_exempt), 2)  # line_cero
            line["19"] = round(float(amount_ice), 2)
            line["20"] = round(float(amount_vat), 2)
            line["21"] = round(float(valRetBien10), 2)
            line["22"] = round(float(valRetServ20), 2)
            line["23"] = round(float(valorRetBienes), 2)
            line["24"] = round(float(valRetServ50), 2)
            line["25"] = round(float(valorRetServicios), 2)
            line["26"] = round(float(valorRetServ100), 2)
            line["27"] = "=SUM(M3:P3)"
            line["28"] = '01'  # Forma de pago
            line["29"] = '593'
            line["30"] = 'NO'
            line["31"] = 'NA'
            # retencion
            autRetencion1 = ''
            estabRetencion1 = ''
            ptoEmiRetencion1 = ''
            secRetencion1 = ''
            fechaEmiRet1 = ''
            retentions = inv.l10n_ec_withhold_ids.filtered(lambda a: a.state == 'posted')
            if retentions:
                withhold_id = retentions[0]
                autRetencion1 = withhold_id.l10n_ec_authorization_number
                estabRetencion1 = withhold_id.l10n_latam_document_number[0:3]
                ptoEmiRetencion1 = withhold_id.l10n_latam_document_number[4:7]
                secRetencion1 = withhold_id.l10n_latam_document_number[-9:]

                fechaEmiRet1 = withhold_id.invoice_date and withhold_id.invoice_date.strftime('%d-%m-%Y') or ''

            line["32"] = fechaEmiRet1
            line["33"] = estabRetencion1
            line["34"] = ptoEmiRetencion1
            line["35"] = secRetencion1
            line["36"] = autRetencion1
            # nota de credito, debito
            fechaEmi = ''
            codTipDoc = ''
            estab = ''
            ptoEmi = ''
            secn = ''
            authc = ''
            factura_origen = False

            factura_origen = inv.reversed_entry_id or inv.debit_origin_id

            if factura_origen:
                auth_doc_ref = factura_origen.l10n_ec_authorization_number

                fechaEmi = factura_origen.invoice_date

                codTipDoc = factura_origen.l10n_latam_document_type_id.code or '01'

                estab = factura_origen.l10n_latam_document_number[0:3]
                ptoEmi = factura_origen.l10n_latam_document_number[4:7]
                secn = factura_origen.l10n_latam_document_number[-9:]
                authc = factura_origen.l10n_ec_authorization_number

            line["37"] = fechaEmi
            line["38"] = codTipDoc
            line["39"] = estab
            line["40"] = ptoEmi
            line["41"] = secn
            line["42"] = authc

            line["43"] = 'Publicado'
            compras.append(line)

        return compras

    def add_purchase_sheet(self, workbook, data, title_format, wizard):
        sheet = workbook.add_worksheet("Compras Detalladas")

        today = fields.Date.context_today(self).strftime("%Y-%m-%d")
        sheet.merge_range('A1:AQ1', 'EMPRESA: ' + data['company'], title_format)
        sheet.merge_range('A2:AQ2', 'FECHA DEL INFORME: ' + str(today),
                          title_format)
        sheet.merge_range('A3:AQ3', 'Compras Detalladas', title_format)

        encabezado = workbook.add_format(
            {'font_size': 11, 'align': 'center', 'right': True, 'left': True, 'bottom': True, 'top': True, 'bold': True,
             'bg_color': "#002060", 'color': "#FFFFFF", 'align': 'vcenter'})
        encabezado.set_text_wrap()
        encabezado.set_border_color("#FFFFFF")
        # encabezado.set_border(2)
        sheet.set_row(4, 70)
        sheet.set_tab_color('#002060')  # Orange

        sheet.write(4, 0, u'Código de compra', encabezado)
        sheet.write(4, 1, u'Tipo de diario', encabezado)
        sheet.write(4, 2, u'Descripción', encabezado)
        sheet.write(4, 3, u'Código de Sustento', encabezado)
        sheet.write(4, 4, u'Tipo Identificación del Proveedor', encabezado)
        sheet.write(4, 5, u'Número de Identificación del Proveedor', encabezado)
        sheet.write(4, 6, u'Nombre del Proveedor', encabezado)
        sheet.write(4, 7, u'Código del Tipo de Comprobante', encabezado)
        sheet.write(4, 8, u'Fecha Registro', encabezado)
        sheet.write(4, 9, u'Establecimiento', encabezado)
        sheet.write(4, 10, u'Punto Emisión', encabezado)
        sheet.write(4, 11, u'Secuencial', encabezado)
        sheet.write(4, 12, u'Fecha Emisión', encabezado)
        sheet.write(4, 13, u'Número de autorización', encabezado)
        sheet.write(4, 14, u'Base Imponible no objeto de IVA', encabezado)
        sheet.write(4, 15, u'Base Imponible tarifa 0% de IVA', encabezado)
        sheet.write(4, 16, u'Base Imponible gravada', encabezado)
        sheet.write(4, 17, u'Base Exenta', encabezado)
        sheet.write(4, 18, u'Monto ICE', encabezado)
        sheet.write(4, 19, u'Monto IVA', encabezado)
        sheet.write(4, 20, u'Retención Bienes 10%', encabezado)
        sheet.write(4, 21, u'Retención Servicios 20 %', encabezado)
        sheet.write(4, 22, u'Retención de IVA 30% bienes', encabezado)
        sheet.write(4, 23, u'Retención IVA 50%', encabezado)
        sheet.write(4, 24, u'Retención de IVA 70% servicios', encabezado)
        sheet.write(4, 25, u'100% Retención de IVA', encabezado)
        sheet.write(4, 26, u'Total Bases Imponibles', encabezado)
        sheet.write(4, 27, u'Forma de pago', encabezado)
        sheet.write(4, 28, u'País al que se efectúa el pago', encabezado)
        sheet.write(4, 29, u'¿Aplica convenio de doble tributación?', encabezado)
        sheet.write(4, 30, u'¿Pago al exterior en aplicación a la Normativa Legal?', encabezado)
        sheet.write(4, 31, u'Fecha de emisión', encabezado)
        sheet.write(4, 32, u'Establecimiento2', encabezado)
        sheet.write(4, 33, u'Punto de emisión', encabezado)
        sheet.write(4, 34, u'Secuencial', encabezado)
        sheet.write(4, 35, u'Número de Autorización2', encabezado)
        sheet.write(4, 36, u'Fecha de emisión', encabezado)
        sheet.write(4, 37, u'Código del tipo de documento', encabezado)
        sheet.write(4, 38, u'Establecimiento', encabezado)
        sheet.write(4, 39, u'Punto de emisión', encabezado)
        sheet.write(4, 40, u'Secuencial 2', encabezado)
        sheet.write(4, 41, u'Autorización', encabezado)
        sheet.write(4, 42, u'Estado', encabezado)

        encabezado.set_align('center')
        sheet.merge_range("AF4:AJ4", u"Información Comprobante de Retención (Sólo llenar si aplica)", encabezado)
        sheet.merge_range("AK4:AP4",
                          u"Sólo llenar en caso de notas de crédito y débito (Información documento modificado)",
                          encabezado)
        # Column Size
        sheet.set_column(6, 6, 50)
        sheet.set_column(2, 2, 65)
        sheet.set_column(13, 13, 50)
        sheet.set_column(35, 35, 50)
        sheet.set_column('A:AQ', 20)
        sheet.autofilter('A5:AQ5')
        sheet.freeze_panes('A6')
        row = 5

        lines = self.det_compras(wizard)
        font_size_9 = workbook.add_format({'bottom': True, 'top': True, 'right': True, 'left': True, 'font_size': 9})
        for line in lines:
            for i in range(0, 43):
                pos = i + 1
                if i == 26:
                    sheet.write(row, i, "=SUM(O" + str(row + 1) + ":R" + str(row + 1) + ")", font_size_9)
                else:
                    sheet.write(row, i, line.get(str(pos), ""), font_size_9)
            row += 1

    def add_refunds_sheet(self, workbook, data, title_format, wizard):
        sheet = workbook.add_worksheet("Documentos de Reembolsos")
        today = fields.Date.context_today(self).strftime("%Y-%m-%d")
        sheet.merge_range('A1:O1', 'EMPRESA: ' + data['company'], title_format)
        sheet.merge_range('A2:O2', 'FECHA DEL INFORME: ' + str(today),
                          title_format)
        sheet.merge_range('A3:O3', 'Detalle de Reembolsos', title_format)
        sheet.merge_range('A4:O4', '', title_format)
        encabezado = workbook.add_format(
            {'font_size': 11, 'align': 'center', 'right': True, 'left': True, 'bottom': True, 'top': True, 'bold': True,
             'bg_color': "#002060", 'color': "#FFFFFF", 'align': 'vcenter'})
        encabezado.set_text_wrap()
        encabezado.set_border_color("#FFFFFF")

        sheet.set_row(4, 70)
        sheet.write(4, 0, u'No. Documento', encabezado)
        sheet.write(4, 1, u'No. Documento', encabezado)
        sheet.write(4, 2, u'Tipo de comprobante de reembolso', encabezado)
        sheet.write(4, 3, u'Tipo Identificación del Proveedor', encabezado)
        sheet.write(4, 4, u'Número de Identificación del Proveedor', encabezado)
        sheet.write(4, 5, u'Establecimiento', encabezado)
        sheet.write(4, 6, u'Punto de emisión', encabezado)
        sheet.write(4, 7, u'Secuencial', encabezado)
        sheet.write(4, 8, u'Fecha de emisión', encabezado)
        sheet.write(4, 9, u'Autorización', encabezado)
        sheet.write(4, 10, u'Base imponible gravada', encabezado)
        sheet.write(4, 11, u'Tarifa IVA diferente de 0%', encabezado)
        sheet.write(4, 12, u'Base no gravada IVA', encabezado)
        sheet.write(4, 13, u'Base Exenta', encabezado)
        sheet.write(4, 14, u'Monto ICE', encabezado)
        sheet.write(4, 15, u'Monto retención IVA', encabezado)

        sheet.set_tab_color('#002060')  # Orange
        sheet.set_column(9, 9, 50)
        encabezado.set_align('center')

        # Column Size

        font_size_9 = workbook.add_format({'bottom': True, 'top': True, 'right': True, 'left': True, 'font_size': 9})

        row = 5
        companies = [wizard.company_id.id]

        if wizard.company_id.sudo().child_ids:
            companies.extend(wizard.company_id.sudo().child_ids.ids)

        reimbursement_docs = self.env['account.reimbursement.document'].sudo().search(
            [('invoice_id.state', 'in', ['posted']),
             ('invoice_id.invoice_date', '>=', str(wizard.date_start)),
             ('invoice_id.invoice_date', '<=', str(wizard.date_end)),
             ('invoice_id.ats_declare', '=', False),
             # ('invoice_id.move_type', 'in', ['out_invoice']),
             ('invoice_id.company_id', 'in', companies)])  # noqa
        move_types = {
            'entry': 'Diario',
            'out_invoice': 'Factura de Cliente',
            'out_refund': 'Nota de Crédito de Cliente',
            'in_invoice': 'Factura de Proveedor',
            'in_refund': 'Nota de Crédito de Proveedor',
            'out_receipt': 'Recibo de Venta',
            'in_receipt': 'Recibo de Compra',
        }

        for line in reimbursement_docs:
            identification_type_code = line.identification_type_id.code_ats_purchase
            if not identification_type_code and hasattr(line.identification_type_id, 'electronic_code'):
                identification_type_code = line.identification_type_id.electronic_code

            sheet.write(row, 0, move_types.get(line.invoice_id.move_type, ''), font_size_9)
            sheet.write(row, 1, line.invoice_id.l10n_latam_document_number, font_size_9)
            sheet.write(row, 2, line.document_type_id.code, font_size_9)
            sheet.write(row, 3, identification_type_code, font_size_9)
            sheet.write(row, 4, line.identification_id, font_size_9)
            sheet.write(row, 5, line.serie_entidad, font_size_9)
            sheet.write(row, 6, line.serie_emision, font_size_9)
            sheet.write(row, 7, line.num_secuencial, font_size_9)
            sheet.write(row, 8, line.fechaEmisionReemb and line.fechaEmisionReemb.strftime('%d-%m-%Y') or '',
                        font_size_9)
            sheet.write(row, 9, line.autorizacionReemb, font_size_9)
            sheet.write_number(row, 10, line.baseImponibleReemb, font_size_9)
            sheet.write_number(row, 11, line.baseImpGravReemb, font_size_9)
            sheet.write_number(row, 12, line.baseNoGraIvaReemb, font_size_9)
            sheet.write_number(row, 13, line.baseImpExeReemb, font_size_9)
            sheet.write_number(row, 14, line.montoIceRemb, font_size_9)
            sheet.write_number(row, 15, line.montoIvaRemb, font_size_9)
            row += 1

        sheet.set_column('A:O', 20)
        sheet.autofilter('A5:O5')
        sheet.freeze_panes('A6')

    def add_retention_sheet(self, workbook, data, title_format, wizard):

        sheet = workbook.add_worksheet("Compras Retenciones")
        today = fields.Date.context_today(self).strftime("%Y-%m-%d")
        sheet.merge_range('A1:I1', 'EMPRESA: ' + data['company'], title_format)
        sheet.merge_range('A2:I2', 'FECHA DEL INFORME: ' + str(today),
                          title_format)
        sheet.merge_range('A3:I3', 'Detalle de Retenciones en Compras', title_format)
        sheet.merge_range('A4:I4', '', title_format)
        encabezado = workbook.add_format(
            {'font_size': 11, 'align': 'center', 'right': True, 'left': True, 'bottom': True, 'top': True, 'bold': True,
             'bg_color': "#002060", 'color': "#FFFFFF", 'align': 'vcenter'})
        encabezado.set_text_wrap()
        encabezado.set_border_color("#FFFFFF")
        encabezado.set_align('center')
        sheet.set_row(4, 60)

        sheet.write(4, 0, u'No. Retención', encabezado)
        sheet.write(4, 1, u'Código de compra', encabezado)
        sheet.write(4, 2, u'Nombre del Proveedor', encabezado)
        sheet.write(4, 3, u'Número de Identificación del Proveedor', encabezado)
        sheet.write(4, 4, u'Descripción', encabezado)
        sheet.write(4, 5, u'Código de retención', encabezado)
        sheet.write(4, 6, u'Base imponible', encabezado)
        sheet.write(4, 7, u'Porcentaje de retención', encabezado)
        sheet.write(4, 8, u'Valor retenido', encabezado)

        sheet.set_tab_color('#002060')  # Orange

        font_size_9 = workbook.add_format({'bottom': True, 'top': True, 'right': True, 'left': True, 'font_size': 9})

        row = 5
        companies = [wizard.company_id.id]

        if wizard.company_id.sudo().child_ids:
            companies.extend(wizard.company_id.sudo().child_ids.ids)
        moves = self.env['account.move'].sudo().search([('state', 'in', ['posted']),
                                                        ('date', '>=', str(wizard.date_start)),
                                                        ('date', '<=', str(wizard.date_end)),
                                                        ('company_id', 'in', companies),
                                                        ('move_type', 'in',
                                                         ['entry', 'in_invoice', 'liq_purchase'])
                                                        ])
        for withhold in moves:
            total = 0
            total_currency = 0
            ret_lines = self.env['account.move.line'].sudo().search(
                [('move_id', 'in', withhold.ids),
                 ('tax_ids.type_tax_use', 'in', ('none', 'purchase')),
                 '|',
                 ('move_id.l10n_ec_withhold_type', 'in', ['in_withhold']),
                 ('tax_ids.l10n_ec_code_base', '=', '332')])
            for line in ret_lines:
                if not line.tax_ids:
                    continue

                if line.l10n_ec_withhold_invoice_id:
                    if line.l10n_ec_withhold_invoice_id and line.l10n_ec_withhold_invoice_id.l10n_latam_document_number:
                        descripcion = 'P/R FACT. # ' + line.l10n_ec_withhold_invoice_id.l10n_latam_document_number + ' ' + (
                                line.l10n_ec_withhold_invoice_id.ref or '')
                    else:
                        descripcion = 'P/R FACT. # ' + line.l10n_ec_withhold_invoice_id.ref
                else:
                    descripcion = 'P/R FACT. # ' + line.move_id.l10n_latam_document_number + ' ' + (
                            line.move_id.ref or '')

                sheet.write(row, 0, line.move_id.name or '', font_size_9)

                if line.l10n_ec_withhold_invoice_id:
                    sheet.write(row, 1,
                                line.l10n_ec_withhold_invoice_id.l10n_latam_document_number or line.l10n_ec_withhold_invoice_id.name,
                                font_size_9)
                    sheet.write(row, 2, line.l10n_ec_withhold_invoice_id.partner_id.name, font_size_9)
                    sheet.write(row, 3, line.l10n_ec_withhold_invoice_id.partner_id.vat, font_size_9)

                    try:
                        if line.id == 35327:
                            lines = line.with_context(norecompute=True, recompute=False).l10n_ec_withhold_tax_amount
                        if isinstance(line.l10n_ec_withhold_tax_amount, float):
                            sheet.write_number(row, 8, line.l10n_ec_withhold_tax_amount, font_size_9)
                        else:
                            print('entro aqui')
                    except Exception as e:
                        raise Exception('get_pre_parameterized_values({}): Exception occurred: {}'
                                        .format(str(line), str(e)))


                else:
                    # 332
                    sheet.write(row, 1,
                                line.move_id.l10n_latam_document_number or line.move_id.name,
                                font_size_9)
                    sheet.write(row, 2, line.move_id.partner_id.name, font_size_9)
                    sheet.write(row, 3, line.move_id.partner_id.vat, font_size_9)
                    sheet.write_number(row, 8, 0, font_size_9)

                sheet.write(row, 4, descripcion, font_size_9)

                percent = "|".join([str(abs(int(tax.amount))) for tax in line.tax_ids])
                tax_name = "|".join([tax.name for tax in line.tax_ids])
                sheet.write(row, 5, tax_name, font_size_9)
                sheet.write_number(row, 6, (line.balance), font_size_9)
                sheet.write(row, 7, percent, font_size_9)

                row += 1
            # for line in withhold.l10n_ec_withhold_line_ids:
            #     total += line.l10n_ec_withhold_tax_amount
            #     total_currency += line.l10n_ec_withhold_tax_amount
            # for line2 in withhold.l10n_ec_related_withhold_line_ids:
            #     total += line2.l10n_ec_withhold_tax_amount
            #     total_currency += line2.l10n_ec_withhold_tax_amount

        sheet.set_column('A:I', 20)
        sheet.set_column(2, 2, 50)
        sheet.set_column(4, 4, 65)
        sheet.set_column(5, 5, 65)
        sheet.autofilter('A5:I5')
        sheet.freeze_panes('A6')

    def add_sales_sheet(self, workbook, data, title_format, wizard):
        sheet = workbook.add_worksheet("Ventas Cliente")
        today = fields.Date.context_today(self).strftime("%Y-%m-%d")
        sheet.merge_range('A1:S1', 'EMPRESA: ' + data['company'], title_format)
        sheet.merge_range('A2:S2', 'FECHA DEL INFORME: ' + str(today),
                          title_format)
        sheet.merge_range('A3:S3', 'Detalle de Ventas', title_format)
        sheet.merge_range('A4:S4', '', title_format)
        encabezado = workbook.add_format(
            {'font_size': 11, 'align': 'center', 'right': True, 'left': True, 'bottom': True, 'top': True, 'bold': True,
             'bg_color': "#FFBF00", 'color': "#000000", 'align': 'vcenter'})
        encabezado.set_text_wrap()

        sheet.set_tab_color('#e37471')  # Orange

        encabezado.set_align('center')

        sheet.set_row(4, 60)
        #
        sheet.write(4, 0, u'Tipo de Venta', encabezado)
        sheet.write(4, 1, u'Tipo de Identificación del Cliente', encabezado)
        sheet.write(4, 2, u'No. de Identificación del Cliente', encabezado)
        sheet.write(4, 3, u'Razón o denominación social del cliente', encabezado)
        sheet.write(4, 4, u'Código tipo de comprobante', encabezado)
        sheet.write(4, 5, u'Tipo de Emisión', encabezado)
        sheet.write(4, 6, u'No. de Factura', encabezado)
        sheet.write(4, 7, u'Subtotal Sin Impuestos', encabezado)
        sheet.write(4, 8, u'Base Imponible No objeto de IVA', encabezado)
        sheet.write(4, 9, u'Base Imponible tarifa 0% IVA', encabezado)
        sheet.write(4, 10, u'Base Imponible tarifa IVA diferente de 0%', encabezado)
        sheet.write(4, 11, u'Monto IVA', encabezado)
        sheet.write(4, 12, u'Monto ICE', encabezado)
        sheet.write(4, 13, u'Valor de IVA que le han retenido', encabezado)
        sheet.write(4, 14, u'Valor de Renta que le han retenido', encabezado)
        sheet.write(4, 15, u'Formas de cobro', encabezado)
        sheet.write(4, 16, u'Autorización Comprobante', encabezado)
        sheet.write(4, 18, u'Autorización Retención', encabezado)
        sheet.write(4, 17, u'No. de Retención', encabezado)
        sheet.write(4, 19, u'Estado', encabezado)

        lines = wizard.get_details_ventas_object()
        font_size_9 = workbook.add_format({'bottom': True, 'top': True, 'right': True, 'left': True, 'font_size': 9})
        row = 5

        for line in lines:
            sheet.write(row, 0, line.get('tipoEmisionText', ''), font_size_9)
            sheet.write(row, 1, line.get('tpIdCliente', ''), font_size_9)
            sheet.write(row, 2, line.get('idCliente', ''), font_size_9)
            sheet.write(row, 3, line.get('denoCli', ''), font_size_9)
            sheet.write(row, 4, line.get('tipoComprobante', ''), font_size_9)
            sheet.write(row, 5, line.get('tipoEmision', ''), font_size_9)
            sheet.write(row, 6, line.get('noFactura', ""), font_size_9)
            sheet.write_number(row, 7, line.get('amount_untaxed', 0.00), font_size_9)
            sheet.write_number(row, 8, line.get('basenoGraIva', 0.00), font_size_9)
            sheet.write_number(row, 9, line.get('baseImponible', 0.00), font_size_9)
            sheet.write_number(row, 10, line.get('baseImpGrav', 0.00), font_size_9)
            sheet.write_number(row, 11, line.get('montoIva', 0.00), font_size_9)
            sheet.write_number(row, 12, line.get('montoIce', 0.00), font_size_9)
            sheet.write_number(row, 13, line.get('valorRetIva', 0.00), font_size_9)
            sheet.write_number(row, 14, line.get('valorRetRenta', 0.00), font_size_9)
            sheet.write(row, 15, line.get('formaPago', ''), font_size_9)
            sheet.write(row, 16, line.get('auth', ''), font_size_9)
            sheet.write(row, 17, line.get('retNumber', ''), font_size_9)
            sheet.write(row, 18, line.get('retAuthorizacion', ''), font_size_9)
            sheet.write(row, 19, line.get('estado', ''), font_size_9)

            row += 1
        sheet.set_column(3, 3, 65)
        sheet.set_column(16, 16, 45)
        sheet.set_column(18, 18, 45)
        sheet.set_column('A:S', 20)
        sheet.autofilter('A5:S5')
        sheet.freeze_panes('A6')

    def _prepare_invoice_data_summary_sheet(self, wizard):
        inv_obj = self.env['account.move']
        tax_group_obj = self.env['account.tax.group']
        companies = [wizard.company_id.id]

        if wizard.company_id.sudo().child_ids:
            companies.extend(wizard.company_id.sudo().child_ids.ids)
        nv_ids = inv_obj.sudo().search([
            ('state', 'in', ['posted']),
            ('invoice_date', '>=', str(wizard.date_start)),
            ('invoice_date', '<=', str(wizard.date_end)),
            ('l10n_latam_document_type_id.ats_declare', '=', True),
            ('company_id', 'in', companies),
            ('move_type', 'in', ['in_invoice', 'in_refund', 'out_invoice', 'out_refund'])])

        data_for_document_type = {}
        for inv in nv_ids:
            ttype = inv.move_type in ['out_invoice', 'out_refund'] and 'sale' or 'purchase'
            sufix = inv.move_type in ['out_invoice', 'out_refund'] and '(V) - ' or '(C) - '
            key = "%s%s" % (sufix, inv.l10n_latam_document_type_id.name)
            if not key in data_for_document_type:
                data_for_document_type[key] = {
                    'name': inv.l10n_latam_document_type_id.name,
                    'type': inv.move_type,
                    'ttype': ttype,
                    'base12': 0,
                    'base0': 0,
                    'novat': 0,
                    'ice': 0,
                    'iva': 0,
                    'total': 0

                }

            invoice_totals = inv.tax_totals
            for amount_by_group_list in invoice_totals['groups_by_subtotal'].values():
                for amount_by_group in amount_by_group_list:
                    tax_group = tax_group_obj.browse(amount_by_group.get('tax_group_id', 0))

                    base = amount_by_group.get('tax_group_base_amount', 0.00)
                    amount = amount_by_group.get('tax_group_amount', 0.00)

                    # if tax_group.l10n_ec_type == 'zero_vat':
                    #    data_for_document_type[key]['base0'] += base
                    if tax_group and tax_group.l10n_ec_type == 'ice':
                        data_for_document_type[key]['ice'] += amount
                    # if tax_group.l10n_ec_type in ['not_charged_vat','exempt_vat']:
                    #    data_for_document_type[key]['novat'] += base
                    if tax_group and tax_group.l10n_ec_type in ['vat05', 'vat08', 'vat12', 'vat13', 'vat14', 'vat15']:
                        data_for_document_type[key]['iva'] += amount
                        data_for_document_type[key]['base12'] += base

            data_for_document_type[key]['novat'] += abs(inv.l10n_latam_amount_untaxed_not_charged_vat)
            data_for_document_type[key]['base0'] += abs(
                inv.l10n_latam_amount_untaxed_zero + inv.l10n_latam_amount_untaxed_exempt_vat)
            data_for_document_type[key]['total'] += inv.amount_total

        return data_for_document_type

    def _prepare_retention_data_summary_sheet(self, wizard):
        companies = [wizard.company_id.id]

        if wizard.company_id.sudo().child_ids:
            companies.extend(wizard.company_id.sudo().child_ids.ids)
        ret_lines = self.env['account.move.line'].sudo().search(
            [('move_id.state', 'in', ['posted']),
             ('move_id.date', '>=', str(wizard.date_start)),
             ('move_id.date', '<=', str(wizard.date_end)),
             ('move_id.l10n_ec_withhold_type', 'in', ['in_withhold']),
             ('move_id.company_id', 'in', companies)])

        data_for_taxt_name = {}
        for line in ret_lines:

            for tax in line.tax_ids:
                key = tax.name
                if not key in data_for_taxt_name:
                    data_for_taxt_name[key] = {
                        'name': key,
                        'base_amount': 0,
                        'percent': abs(int(tax.amount)),
                        'amount': 0
                    }

                data_for_taxt_name[key]['base_amount'] += (line.balance)
                data_for_taxt_name[key]['amount'] += line.l10n_ec_withhold_tax_amount

        return data_for_taxt_name

    def add_summary_sheet(self, workbook, data, title_format, wizard):
        sheet = workbook.add_worksheet("Resumen")
        sheet.write('A1:A1', 'EMPRESA: ' + data['company'], title_format)
        sheet.merge_range('B1:D1', u'PERIODO: ' + data['period'], title_format)

        encabezado = workbook.add_format(
            {'font_size': 11, 'align': 'center', 'right': True, 'left': True, 'bottom': True, 'top': True, 'bold': True,
             'bg_color': "#002060", 'color': "#FFFFFF", 'align': 'vcenter'})
        encabezado.set_text_wrap()

        encabezado.set_align('center')
        # sheet.set_row(4, 60)

        sheet.set_tab_color('#b71111')  # Orange
        purchase = []
        sale = []
        sheet.set_column("A:A", 65)
        sheet.set_column('B:G', 15)

        for line in self._prepare_invoice_data_summary_sheet(wizard).values():

            if line.get('type', 'in_invoice') in ['in_refund', 'out_refund']:

                in_arr = [
                    line.get('name', ''),
                    line.get('base12', 0.0) * -1,
                    line.get('base0', 0.0) * -1,
                    line.get('novat', 0.0) * -1,
                    line.get('ice', 0.0) * -1,
                    line.get('iva', 0.0) * -1,
                    line.get('total', 0.0) * -1,
                ]
            else:
                in_arr = [
                    line.get('name', ''),
                    line.get('base12', 0.0),
                    line.get('base0', 0.0),
                    line.get('novat', 0.0),
                    line.get('ice', 0.0),
                    line.get('iva', 0.0),
                    line.get('total', 0.0),
                ]

            if line.get('ttype', 'purchase') == 'purchase':
                purchase.append(in_arr)
            else:
                sale.append(in_arr)

        row_init = 3
        row = 10
        if len(purchase) > 0:
            count = len(purchase)
            if count > 5:
                row = count + 10

            sheet.merge_range('A' + str(row_init - 1) + ':G' + str(row_init - 1), 'Resumen de Compras', encabezado)
            sheet.add_table('A' + str(row_init) + ':G' + str(row + 1), {'data': purchase, 'total_row': 1, 'columns': [
                {'header': 'Tipo de documento',
                 'total_string': 'Totales'},
                {'header': 'Base 12',
                 'total_function': 'sum'},
                {'header': 'Base 0',
                 'total_function': 'sum'},
                {'header': 'No objeto de IVA',
                 'total_function': 'sum'},
                {'header': 'ICE',
                 'total_function': 'sum'},
                {'header': 'IVA',
                 'total_function': 'sum'},
                {'header': 'Total',
                 'total_function': 'sum'},
            ]})
            row_init = row + 5  # Fin más cinco líneas
            row = row_init + 7

        if len(sale) > 0:
            count = len(sale)
            if count > 5:
                row = row + 10
            sheet.merge_range('A' + str(row_init - 1) + ':G' + str(row_init - 1), 'Resumen de Ventas', encabezado)
            sheet.add_table('A' + str(row_init) + ':G' + str(row), {'data': sale, 'total_row': 1, 'columns': [
                {'header': 'Tipo de documento',
                 'total_string': 'Totales'},
                {'header': 'Base 12',
                 'total_function': 'sum'},
                {'header': 'Base 0',
                 'total_function': 'sum'},
                {'header': 'No objeto de IVA',
                 'total_function': 'sum'},
                {'header': 'ICE',
                 'total_function': 'sum'},
                {'header': 'IVA',
                 'total_function': 'sum'},
                {'header': 'Total',
                 'total_function': 'sum'},
            ]})
            row_init = row + 5  # Fin más cinco líneas
            row = row_init + 7

        tax = []
        for line in self._prepare_retention_data_summary_sheet(wizard).values():
            in_arr = [
                line.get('name', ''),
                line.get('base_amount', 0.0),
                line.get('percent', 0.0),
                line.get('amount', 0.0),
            ]
            tax.append(in_arr)
        if len(tax) > 0:
            count = len(tax)
            if count > 5:
                row = row + 22
            sheet.merge_range('A' + str(row_init - 1) + ':D' + str(row_init - 1), 'Resumen de Retenciones', encabezado)
            sheet.add_table('A' + str(row_init) + ':D' + str(row), {'data': tax, 'total_row': 1, 'columns': [
                {'header': u'Código',
                 'total_string': 'Totales'},
                {'header': 'Base Imponible',
                 'total_function': 'sum'},
                {'header': '%', },
                {'header': 'Valor Retenido',
                 'total_function': 'sum'},
            ]})

            chart1 = workbook.add_chart({'type': 'column'})

            # Configure the first series.
            chart1.add_series({
                'name': u'Código',
                'categories': '=Resumen!$A$' + str(row_init + 1) + ':$A$' + str(row_init + count),
                'values': '=Resumen!$D$' + str(row_init + 1) + ':$D$' + str(row_init + count)
            })

            # Add a chart title and some axis labels.
            chart1.set_title({'name': 'Resumen de Retenciones'})

            # Set an Excel chart style.
            chart1.set_style(11)
            # Insert the chart into the worksheet (with an offset).
            sheet.insert_chart('A' + str(row + 5), chart1, {'x_offset': 80, 'y_offset': 10})

    def add_canceled_documents(self, workbook, data, title_format, wizard):
        today = fields.Date.context_today(self).strftime("%Y-%m-%d")
        sheet = workbook.add_worksheet("Comprobantes Anulados")

        sheet.merge_range('A1:G1', 'EMPRESA: ' + data['company'], title_format)
        sheet.merge_range('A2:G2', 'FECHA DEL INFORME: ' + str(today),
                          title_format)
        sheet.merge_range('A3:G3', 'Detalle de Comprobantes Anulados', title_format)
        sheet.merge_range('A4:G4', '', title_format)
        encabezado = workbook.add_format(
            {'font_size': 11, 'align': 'center', 'right': True, 'left': True, 'bottom': True, 'top': True, 'bold': True,
             'bg_color': "#002060", 'color': "#FFFFFF", 'align': 'vcenter'})
        encabezado.set_text_wrap()
        encabezado.set_border_color("#FFFFFF")
        encabezado.set_align('center')
        sheet.set_row(4, 60)
        inv_obj = self.env['account.move']
        # sheet.set_row(4, 60)
        company_id = data['form'].get('company_id', 1)
        date_start = data['form'].get('date_start', False)
        date_end = data['form'].get('date_end', False)

        # Tipo de Venta Tipo de Comprobante est pto secu auth

        sheet.write(4, 0, u'Forma de Comprobante', encabezado)
        sheet.write(4, 1, u'Tipo de Comprobante', encabezado)
        sheet.write(4, 2, u'Establecimiento', encabezado)
        sheet.write(4, 3, u'Punto de Emisión', encabezado)
        sheet.write(4, 4, u'Secuencial', encabezado)
        sheet.write(4, 5, u'Autorización', encabezado)
        sheet.write(4, 6, u'Estado', encabezado)

        sheet.set_tab_color('#b71111')  # Orange

        font_size_9 = workbook.add_format({'bottom': True, 'top': True, 'right': True, 'left': True, 'font_size': 9})

        row = 5
        inv_ids = inv_obj.search([('state', 'in', ['cancel']),
                                  ('invoice_date', '>=', str(date_start)),
                                  ('invoice_date', '<=', str(date_end)),
                                  ('l10n_latam_document_type_id.ats_declare', '=', True),
                                  ('move_type', 'in', ['out_invoice']),
                                  ('company_id', '=', company_id)])
        authorization = False

        for inv in inv_ids:
            if hasattr(inv, "l10n_ec_authorization_number"):
                authorization = inv.l10n_ec_authorization_number

            if not authorization:
                authorization = '9999'

            se = inv.l10n_latam_document_number and inv.l10n_latam_document_number[0:3] or '000'
            pe = inv.l10n_latam_document_number and inv.l10n_latam_document_number[4:7] or '000'
            sec = inv.l10n_latam_document_number and inv.l10n_latam_document_number[-9:] or '000000000'

            sheet.write(row, 0, u'Electrcónica', font_size_9)
            sheet.write(row, 1, inv.l10n_latam_document_type_id.name, font_size_9)
            sheet.write(row, 2, se, font_size_9)
            sheet.write(row, 3, pe, font_size_9)
            sheet.write(row, 4, sec, font_size_9)
            sheet.write(row, 5, authorization, font_size_9)
            sheet.write(row, 6, 'Anulado', font_size_9)
            row += 1

        sheet.set_column('A:G', 20)
        sheet.set_column(5, 5, 65)
        sheet.autofilter('A5:G5')
        sheet.freeze_panes('A6')

    def add_export_sales_sheet(self, workbook, data, title_format, wizard):
        inv_obj = self.env['account.move']
        sheet = workbook.add_worksheet("Listado de Exportaciones")
        today = fields.Date.context_today(self).strftime("%Y-%m-%d")
        sheet.merge_range('A1:I1', 'NOMBRE / RAZÓN SOCIAL DEL BENEFICIARIO: ' + data['company'], title_format)
        sheet.merge_range('A2:I2', 'NÚMERO DE RUC: ' + data['ruc'], title_format)
        sheet.merge_range('A3:I3', 'FECHA DEL INFORME: ' + str(today), title_format)
        sheet.merge_range('A4:I4', '', title_format)
        encabezado = workbook.add_format(
            {'font_size': 11, 'align': 'center', 'right': True, 'left': True, 'bottom': True, 'top': True, 'bold': True,
             'bg_color': "#FFBF00", 'color': "#000000", 'align': 'vcenter'})
        font_size_9_header = workbook.add_format(
            {'bottom': True, 'top': True, 'right': True, 'left': True, 'font_size': 9})
        encabezado.set_text_wrap()

        sheet.set_tab_color('#e37471')  # Orange

        encabezado.set_align('center')

        sheet.merge_range('A5:I5',
                          'NOTA: No se mostrará la información de los clientes que no tienen indentificado el país en su ficha',
                          font_size_9_header)
        sheet.merge_range('A6:I6', 'DETALLE DE COMPROBANTES DE FACTURAS Y DOCUMENTOS DE EXPORTACIÓN', encabezado)
        sheet.write(6, 0, u'No.', encabezado)
        sheet.write(6, 1, u'DOCUMENTO DE EXPORTACIÓN (# de refrendo)', encabezado)
        sheet.write(6, 2, u'FECHA DOCUMENTO DE EXPORTACIÓN', encabezado)
        sheet.write(6, 3, u'SERIE', encabezado)
        sheet.write(6, 4, u'SECUENCIA', encabezado)
        sheet.write(6, 5, u'AUTORIZACIÓN (comprobantes físicos)', encabezado)
        sheet.write(6, 6, u'CLAVE DE ACCESO (comprobantes electrónicos)', encabezado)
        sheet.write(6, 7, u'VALOR FACTURA USD', encabezado)
        sheet.write(6, 8, u'VALOR FOB USD', encabezado)

        font_size_9 = workbook.add_format({'bottom': True, 'top': True, 'right': True, 'left': True, 'font_size': 9})
        row = 7

        inv_ids = inv_obj.search([('state', 'in', ['posted']),
                                  ('invoice_date', '>=', str(wizard.date_start)),
                                  ('invoice_date', '<=', str(wizard.date_end)),
                                  ('l10n_latam_document_type_id.ats_declare', '=', True),
                                  ('journal_id.code', 'not in', ['CXC', 'cxc']),
                                  ('partner_id.country_id', 'not in', (False, self.env.ref('base.ec').id)),
                                  ('move_type', 'in', ['out_invoice', 'out_refund']),
                                  ('company_id', '=', wizard.company_id.id)])  # noqa

        i = 0
        for inv in inv_ids:
            i += 1
            is_eletronic = (inv.l10n_ec_authorization_number and len(
                inv.l10n_ec_authorization_number) > 40) and True or False
            sheet.write(row, 0, i, font_size_9)
            sheet.write(row, 1, "", font_size_9)  # inv.get_dae_ats() or
            sheet.write(row, 2, inv.invoice_date.strftime('%d-%m-%Y'), font_size_9)
            sheet.write(row, 3, str(inv.l10n_latam_document_number).replace("-", "")[0:6], font_size_9)
            sheet.write(row, 4, str(inv.l10n_latam_document_number).replace("-", "")[-9:], font_size_9)
            sheet.write(row, 5, is_eletronic and ' ' or inv.l10n_ec_authorization_number, font_size_9)
            sheet.write(row, 6, is_eletronic and inv.l10n_ec_authorization_number or ' ', font_size_9)
            sheet.write_number(row, 7, inv.amount_total_signed, font_size_9)
            sheet.write_number(row, 8, inv.amount_total_signed, font_size_9)

            row += 1

        sheet.set_column(0, 0, 5)
        sheet.set_column(1, 4, 20)
        sheet.set_column(5, 6, 45)
        sheet.set_column(7, 8, 20)
        sheet.autofilter('A7:I7')
        sheet.freeze_panes('A8')

    def add_export_sales_certificate_sheet(self, workbook, data, title_format, wizard):
        inv_obj = self.env['account.move']
        mesesDic = {
            1: 'Enero',
            2: 'Febrero',
            3: 'Marzo',
            4: 'Abril',
            5: 'Mayo',
            6: 'Junio',
            7: 'Julio',
            8: 'Agosto',
            9: 'Septiembre',
            10: 'Octubre',
            11: 'Noviembre',
            12: 'Diciembre'
        }
        sheet = workbook.add_worksheet("Certificación de Exportaciones")
        today = fields.Date.context_today(self).strftime("%Y-%m-%d")
        sheet.merge_range('A1:I1', 'NOMBRE / RAZÓN SOCIAL DEL BENEFICIARIO: ' + data['company'], title_format)
        sheet.merge_range('A2:I2', 'NÚMERO DE RUC: ' + data['ruc'], title_format)
        sheet.merge_range('A3:I3', 'FECHA DEL INFORME: ' + str(today), title_format)
        sheet.merge_range('A4:I4', '', title_format)
        encabezado = workbook.add_format(
            {'font_size': 11, 'align': 'center', 'right': True, 'left': True, 'bottom': True, 'top': True, 'bold': True,
             'bg_color': "#FFBF00", 'color': "#000000", 'align': 'vcenter'})
        font_size_9_header = workbook.add_format(
            {'bottom': True, 'top': True, 'right': True, 'left': True, 'font_size': 9})
        encabezado.set_text_wrap()

        sheet.set_tab_color('#e37471')  # Orange

        encabezado.set_align('center')

        sheet.merge_range('A6:G6', 'FACTURA DE EXPORTACION', encabezado)
        sheet.merge_range('H6:L6', 'FACTURA DE COMPRA EMITIDA POR EL PROVEEDOR', encabezado)
        sheet.write(6, 0, u'No. DE FACTURA', encabezado)
        sheet.write(6, 1, u'FECHA', encabezado)
        sheet.write(6, 2, u'PERIODO DE DECLARACION', encabezado)
        sheet.write(6, 3, u'NO. DE REFERENDO', encabezado)
        sheet.write(6, 4, u'FECHA DE REGULARIZACION EN EL SISTEMA ECUAPAS', encabezado)
        sheet.write(6, 5, u'TOTAL CANTIDAD EXPORTADA', encabezado)
        sheet.write(6, 6, u'VALOR TOTAL DE FACTURA', encabezado)
        sheet.write(6, 7, u'NO. DE FACTURA', encabezado)
        sheet.write(6, 8, u'FECHA', encabezado)
        sheet.write(6, 9, u'CANTIDAD', encabezado)
        sheet.write(6, 10, u'VALOR', encabezado)
        sheet.write(6, 11, u'WK', encabezado)

        font_size_9 = workbook.add_format({'bottom': True, 'top': True, 'right': True, 'left': True, 'font_size': 9})
        row = 7
        companies = [wizard.company_id.id]

        if wizard.company_id.sudo().child_ids:
            companies.extend(wizard.company_id.sudo().child_ids.ids)
        inv_ids = inv_obj.sudo().search([('state', 'in', ['posted']),
                                         ('invoice_date', '>=', str(wizard.date_start)),
                                         ('invoice_date', '<=', str(wizard.date_end)),
                                         ('l10n_latam_document_type_id.ats_declare', '=', True),
                                         ('journal_id.code', 'not in', ['CXC', 'cxc']),
                                         ('partner_id.country_id', 'not in', (False, self.env.ref('base.ec').id)),
                                         ('move_type', 'in', ['out_invoice', 'out_refund']),
                                         ('company_id', 'in', companies)])  # noqa

        i = 0
        for inv in inv_ids:
            i += 1
            mes = inv.invoice_date.month
            sheet.write(row, 0, str(inv.l10n_latam_document_number), font_size_9)
            sheet.write(row, 1, inv.invoice_date.strftime('%d-%m-%Y'), font_size_9)
            sheet.write(row, 2, mesesDic.get(mes, ''), font_size_9)
            sheet.write(row, 3, "", font_size_9)  # inv.get_dae_ats()
            sheet.write(row, 4, inv.invoice_date.strftime('%d-%m-%Y'), font_size_9)
            sheet.write_number(row, 5, sum(inv.invoice_line_ids.mapped('quantity')), font_size_9)
            sheet.write_number(row, 6, inv.amount_total_signed, font_size_9)
            sheet.write(row, 7, '', font_size_9)
            sheet.write(row, 8, '', font_size_9)
            sheet.write(row, 9, '', font_size_9)
            sheet.write(row, 10, '', font_size_9)

            if (hasattr(inv, "week_id")) and inv.week_id:
                sheet.write(row, 11, inv.week_id.name, font_size_9)
            else:
                sheet.write(row, 11, "", font_size_9)

            row += 1

        sheet.set_column(0, 8, 20)
        sheet.autofilter('A7:L7')
        sheet.freeze_panes('A8')

    def add_export_vat_refund_sheet(self, workbook, data, title_format, wizard):
        inv_obj = self.env['account.move']
        sheet = workbook.add_worksheet("Listado de adquiciciones")
        today = fields.Date.context_today(self).strftime("%Y-%m-%d")
        sheet.merge_range('A1:M1', 'NOMBRE / RAZÓN SOCIAL DEL BENEFICIARIO: ' + data['company'], title_format)
        sheet.merge_range('A2:M2', 'NÚMERO DE RUC: ' + data['ruc'], title_format)
        sheet.merge_range('A3:M3', 'FECHA DEL INFORME: ' + str(today), title_format)
        sheet.merge_range('A4:M4', '', title_format)
        encabezado = workbook.add_format(
            {'font_size': 11, 'align': 'center', 'right': True, 'left': True, 'bottom': True, 'top': True, 'bold': True,
             'bg_color': "#FFBF00", 'color': "#000000", 'align': 'vcenter'})
        font_size_9_header = workbook.add_format(
            {'bottom': True, 'top': True, 'right': True, 'left': True, 'font_size': 9})
        encabezado.set_text_wrap()

        sheet.set_tab_color('#e37471')  # Orangecd
        encabezado.set_align('center')

        sheet.merge_range('A5:M5', 'LISTADO DE ADQUISICIONES PARA DEVOLUCIÓN DEL IVA A EXPORTADORES DE BIENES',
                          encabezado)
        sheet.merge_range('A6:M6', 'DETALLE DE COMPROBANTES DE ADQUISICIONES LOCALES E IMPORTACIONES', encabezado)
        sheet.write(6, 0, u'No.', encabezado)
        sheet.write(6, 1, u'RUC DEL PROVEEDOR', encabezado)
        sheet.write(6, 2, u'RAZÓN SOCIAL DEL PROVEEDOR', encabezado)
        sheet.write(6, 3, u'FECHA DE EMISIÓN (a)', encabezado)
        sheet.write(6, 4, u'SERIE', encabezado)
        sheet.write(6, 5, u'SECUENCIA (b)', encabezado)
        sheet.write(6, 6, u'AUTORIZACIÓN (comprobantes físicos)', encabezado)
        sheet.write(6, 7, u'CLAVE DE ACCESO (comprobantes electrónicos)', encabezado)
        sheet.write(6, 8, u'BASE IMPONIBLE', encabezado)
        sheet.write(6, 9, u'IVA', encabezado)
        sheet.write(6, 10, u'CLAVE DE ACCESO COMPROBANTES DE RETENCIÓN ELECTRÓNICOS (c)', encabezado)
        sheet.write(6, 11, u'ESPECIFICAR SI SE TRATA DE ACTIVO FIJO', encabezado)
        sheet.write(6, 12, u'ESPECIFICAR SI SE TRATA DE REEMBOLSO DE GASTOS', encabezado)

        font_size_9 = workbook.add_format({'bottom': True, 'top': True, 'right': True, 'left': True, 'font_size': 9})
        row = 7
        companies = [wizard.company_id.id]

        if wizard.company_id.sudo().child_ids:
            companies.extend(wizard.company_id.sudo().child_ids.ids)
        inv_ids = inv_obj.sudo().search([('state', 'in', ['posted']),
                                         ('invoice_date', '>=', str(wizard.date_start)),
                                         ('invoice_date', '<=', str(wizard.date_end)),
                                         ('l10n_latam_document_type_id.ats_declare', '=', True),
                                         ('journal_id.code', 'not in', ['CXP', 'cxp']),
                                         ('move_type', 'in', ['in_invoice', 'in_refund']),
                                         ('company_id', 'in', companies)])  # noqa

        i = 0
        for inv in inv_ids:
            i += 1
            is_eletronic = (inv.l10n_ec_authorization_number and len(
                inv.l10n_ec_authorization_number) > 40) and True or False
            sheet.write(row, 0, i, font_size_9)
            sheet.write(row, 1, inv.partner_id.vat or "", font_size_9)
            sheet.write(row, 2, inv.partner_id.name or "", font_size_9)
            sheet.write(row, 3, inv.invoice_date.strftime('%d-%m-%Y'), font_size_9)
            sheet.write(row, 4, str(inv.l10n_latam_document_number).replace("-", "")[0:6], font_size_9)
            sheet.write(row, 5, str(inv.l10n_latam_document_number).replace("-", "")[-9:], font_size_9)
            sheet.write(row, 6, is_eletronic and ' ' or inv.l10n_ec_authorization_number, font_size_9)
            sheet.write(row, 7, is_eletronic and inv.l10n_ec_authorization_number or ' ', font_size_9)
            sheet.write_number(row, 8, inv.amount_untaxed_signed * -1, font_size_9)
            sheet.write_number(row, 9, inv.l10n_latam_amount_vat * -1, font_size_9)
            sheet.write(row, 10, '', font_size_9)
            sheet.write(row, 11, (inv.l10n_latam_document_sustento and inv.l10n_latam_document_sustento.code in ['03',
                                                                                                                 '04']) and 'SI' or '',
                        font_size_9)
            sheet.write(row, 12, inv.is_reimbursement_invoice and 'SI' or ' ', font_size_9)
            row += 1

        sheet.write(row, 7, 'TOTAL', encabezado)
        sheet.write(row, 8, "=SUM(I8:I%s)" % (row - 1), font_size_9)
        sheet.write(row, 9, "=SUM(J8:J%s)" % (row - 1), font_size_9)

        sheet.set_column(0, 0, 5)
        sheet.set_column(1, 1, 20)
        sheet.set_column(2, 2, 60)
        sheet.set_column(3, 6, 20)
        sheet.set_column(7, 7, 45)
        sheet.set_column(8, 9, 20)
        sheet.set_column(10, 10, 45)
        sheet.set_column(11, 12, 20)
        sheet.autofilter('A7:M7')
        sheet.freeze_panes('A8')

    def generate_xlsx_report(self, workbook, data, objects):

        title_format = workbook.add_format(
            {'font_size': 14, 'bottom': True, 'right': True, 'left': True, 'top': True, 'align': 'vcenter',
             'bold': True})
        title_format.set_align('left')

        wizard = self.env['wizard.ats'].browse(data['form']['id'])
        self.add_summary_sheet(workbook, data, title_format, wizard)
        self.add_purchase_sheet(workbook, data, title_format, wizard)
        self.add_refunds_sheet(workbook, data, title_format, wizard)
        self.add_retention_sheet(workbook, data, title_format, wizard)
        self.add_sales_sheet(workbook, data, title_format, wizard)
        self.add_export_sales_sheet(workbook, data, title_format, wizard)
        self.add_export_sales_certificate_sheet(workbook, data, title_format, wizard)
        self.add_export_vat_refund_sheet(workbook, data, title_format, wizard)
        self.add_canceled_documents(workbook, data, title_format, wizard)
