# -*- coding: utf-8 -*-
##############################################################################
#
#    Author :  Cristian Salamea cristian.salamea@gnuthink.com
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.
#

#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
##############################################################################

import time, calendar
import base64
from io import StringIO
from lxml import etree
from lxml.etree import DocumentInvalid
import os
import datetime
import logging
from odoo.exceptions import ValidationError
from odoo import api, fields, models
import json


# tpIdProv = {
#     'ruc': '01',
#     'cedula': '02',
#     'pasaporte': '03',
#     '05': '02',  # Cédula
#     '06': '03',  # Pasaporte
#     '08': '03',  # Identificación del Exterior
#     '04': '01'  # RUC
# }

# tpIdCliente = {
#     'ruc': '04',
#     'cedula': '05',
#     'pasaporte': '06',
#     '05': '05',
#     '06': '06',
#     '08': '06',  # Identificación del Exterior
#     '09': '19',  # Placa
#     '04': '04',
#     '07': '07'  # consumidor final
# }


class wizard_ats(models.TransientModel):
    _name = 'wizard.ats'
    _description = 'Anexo Transaccional Simplificado'
    __logger = logging.getLogger(_name)

    fcname = fields.Char(
        string='Nombre de Archivo',
        required=False,
        size=50,
        readonly=True,
    )
    date_start = fields.Date(
        string='Fecha Inicio',
        required=True,
        default=fields.Date.start_of(fields.Date.today(), 'month'),
    )
    date_end = fields.Date(
        string='Fecha Fin',
        required=True, default=fields.Date.end_of(fields.Date.today(), 'month'),
    )
    include_electronic_document = fields.Boolean(
        string="Incluir documentos electrónicos",
        default=True,
        help="Permite incluir los documentos electrónicos de ventas en la generación del ATS.",
    )
    company_id = fields.Many2one(
        string='Compañía',
        comodel_name='res.company',
        default=lambda self: self.env.company,
        required=True,
    )
    data = fields.Binary(
        string='Archivo XML',
    )
    no_validate = fields.Boolean(
        string='No Validar',
    )
    error_warning = fields.Html(
        string="Errores y Advertencias",
    )
    state = fields.Selection(
        string="Estado",
        selection=(
            ('choose', 'choose'),
            ('export', 'export'),
            ('warning', 'Advertencias'),
            ('errors', 'Errores')
        ),
        default='choose'
    )
    num_estab_ruc = fields.Char(
        string='Num. de Establecimiento',
        size=3,
        required=True,
        default='001',
    )

    def convertir_fecha(self, date):
        return date and date.strftime('%d/%m/%Y') or ""

    def _get_ventas(self, journal_id=False):

        sql_ventas = "SELECT move_type, sum(amount_untaxed) AS base \
                      FROM account_move am\
                      JOIN l10n_latam_document_type lld ON lld.id = am.l10n_latam_document_type_id\
                      WHERE move_type IN ('out_invoice', 'out_refund') \
                      AND state IN ('posted') \
                      AND lld.ats_declare = true \
                      AND invoice_date >= '%s' \
                      AND invoice_date <= '%s'" % (
            fields.Date.to_string(self.date_start), fields.Date.to_string(self.date_end))

        if journal_id:
            where = " AND journal_id=%s" % journal_id
            sql_ventas += where
        sql_ventas += " GROUP BY move_type"

        self._cr.execute(sql_ventas)
        res = self._cr.fetchall()
        resultado = sum(map(lambda x: x[0] == 'out_refund' and x[1] * -1 or x[1], res))  # noqa
        if resultado < 0:
            return 0
        return resultado

    def _get_ret_iva(self, invoice):
        """
        Return (valRetBien10, valRetServ20,
        valorRetBienes,
        valorRetServicios, valorRetServ100)
        """
        retBien10 = 0
        retServ20 = 0
        retServ50 = 0
        retBien = 0
        retServ = 0
        retServ100 = 0
        retentions = invoice.l10n_ec_withhold_ids.filtered(lambda a: a.state == 'posted')
        if retentions:
            for line in retentions.mapped("l10n_ec_withhold_line_ids"):
                for tax in line.tax_ids:
                    percent = abs(int(float(tax.amount)))
                    if tax.tax_group_id.l10n_ec_type in ['withhold_vat_purchase']:
                        if percent == 10:
                            retBien10 += abs(line.l10n_ec_withhold_tax_amount)
                        elif percent == 30:
                            retBien += abs(line.l10n_ec_withhold_tax_amount)
                        elif percent == 100:
                            retServ100 += abs(line.l10n_ec_withhold_tax_amount)
                        elif percent == 20:
                            retServ20 += abs(line.l10n_ec_withhold_tax_amount)
                        elif percent == 50:
                            retServ50 += abs(line.l10n_ec_withhold_tax_amount)
                        else:
                            retServ += abs(line.l10n_ec_withhold_tax_amount)

        return retBien10, retServ20, retBien, retServ, retServ50, retServ100

    def process_lines(self, invoice):
        """
        @temp: {'332': {baseImpAir: 0,}}
        @data_air: [{baseImpAir: 0, ...}]
        """
        data_air = []
        temp = {}
        retentions = invoice.l10n_ec_withhold_ids.filtered(lambda a: a.state == 'posted')
        if retentions:
            for line in retentions.mapped("l10n_ec_withhold_line_ids"):
                for tax in line.tax_ids:
                    tax_group = tax.tax_group_id.l10n_ec_type
                    percent = abs(float(tax.amount))  # int()
                    if tax_group in ['withhold_income_sale',
                                     'withhold_income_purchase']:  # 'withhold_income_sale'. withhold_income_tax
                        code = tax.l10n_ec_code_ats or tax.l10n_ec_code_base or tax.l10n_ec_code_applied
                        if not temp.get(code):
                            temp[code] = {
                                'baseImpAir': 0,
                                'valRetAir': 0,
                                'numCajBan': int(sum(l.quantity for l in invoice.invoice_line_ids)),
                                'precCajBan': sum(l.price_unit for l in invoice.invoice_line_ids) / len(
                                    invoice.invoice_line_ids),
                            }
                        temp[code]['baseImpAir'] += line.balance
                        temp[code]['codRetAir'] = code
                        temp[code]['porcentajeAir'] = percent or 0.00  # noqa
                        temp[code]['valRetAir'] += abs(line.l10n_ec_withhold_tax_amount)
        # 332 Tax
        invoice_332_line = invoice.invoice_line_ids.filtered(
            lambda a: len(a.tax_ids.filtered(lambda a: a.l10n_ec_code_base == '332')) > 0)
        if invoice_332_line:
            base_332 = sum(invoice_332_line.mapped("price_subtotal"))
            code = "332"
            temp[code] = {}
            temp[code]['baseImpAir'] = base_332
            temp[code]['codRetAir'] = code
            temp[code]['porcentajeAir'] = 0.00  # noqa
            temp[code]['valRetAir'] = 0

        for k, v in temp.items():
            data_air.append(v)
        return data_air

    def _get_details_ventas(self):
        inv_obj = self.env['account.move']
        wiz = self
        tax_group_obj = self.env['account.tax.group']
        companies = [self.company_id.id]

        if self.company_id.sudo().child_ids:
            companies.extend(self.company_id.sudo().child_ids.ids)

        # Facturas de Compra con retenciones
        inv_ids = inv_obj.sudo().search([
            ('state', 'in', ['posted']),
            ('invoice_date', '>=', fields.Date.to_string(self.date_start)),
            ('invoice_date', '<=', fields.Date.to_string(self.date_end)),
            ('l10n_latam_document_type_id.ats_declare', '=', True),
            ('journal_id.code', 'not in', ['CXC', 'cxc']),
            ('move_type', 'in', ['out_invoice', 'out_refund']),
            ('company_id', 'in', companies)
        ])  # noqa

        pdata = {}

        retention_ids = []
        for inv in inv_ids:
            # logging.info(inv)
            part_id = inv.partner_id.vat
            tipoComprobante = inv.l10n_latam_document_type_id.code
            # inv.partner_id.l10n_latam_identification_type_id and inv.partner_id.l10n_latam_identification_type_id.code_ats or '04'  # noqa
            formaPago = '01'
            tipoEmision = 'E'
            tpIdCliente = inv.partner_id.l10n_latam_identification_type_id.code_ats_sales
            if not tpIdCliente and hasattr(inv.partner_id.l10n_latam_identification_type_id, "electronic_code"):
                tpIdCliente = inv.partner_id.l10n_latam_identification_type_id.electronic_code

            if not wiz.include_electronic_document and tipoEmision == 'E':
                continue
            
            if tipoComprobante == '01':
                tipoComprobante = '18'

            keyp = '%s-%s-%s' % (part_id, tipoComprobante, tipoEmision)
            tipoCli = '01'
            
            partner_data = {
                keyp: {
                    'tipoEmisionText': u'Electrónica',
                    'tpIdCliente': tpIdCliente or '05',
                    'idCliente': inv.partner_id.vat or 'NO IDENTIFICACION',
                    'denoCli': inv.partner_id.name.replace('.', "").replace(u'ñ', "n").replace(u'Ñ', "N"),
                    'tipoCli': tipoCli,
                    'tipoEmision': tipoEmision,
                    'numeroComprobantes': 1,
                    'basenoGraIva': 0,
                    'baseImponible': 0,
                    'baseImpGrav': 0,
                    'montoIva': 0,
                    'valorRetRenta': 0,
                    'tipoComprobante': tipoComprobante,
                    'valorRetIva': 0,
                    'formaPago': formaPago,
                    'montoIce': 0
                }
            }
            if not pdata.get(keyp, False):
                pdata.update(partner_data)
            else:
                pdata[keyp]['numeroComprobantes'] += 1
            amount_ice = 0
            amount_vat = 0
            amount_novat = 0
            base_not_cero = 0
            base_cero = 0
            import json
            invoice_totals = inv.tax_totals
            for amount_by_group_list in invoice_totals['groups_by_subtotal'].values():
                for amount_by_group in amount_by_group_list:
                    tax_group = tax_group_obj.browse(amount_by_group.get('tax_group_id', 0))

                    base = amount_by_group.get('tax_group_base_amount', 0.00)
                    amount = amount_by_group.get('tax_group_amount', 0.00)

                    if tax_group.l10n_ec_type == 'zero_vat':
                        base_cero += base
                    if tax_group.l10n_ec_type == 'ice':
                        amount_ice += amount
                    if tax_group.l10n_ec_type in ['not_charged_vat', 'exempt_vat']:
                        amount_novat += base
                    if tax_group.l10n_ec_type in ['vat05', 'vat08', 'vat12', 'vat13', 'vat14', 'vat15']:
                        amount_vat += amount
                        base_not_cero += base

            pdata[keyp]['basenoGraIva'] += amount_novat
            pdata[keyp]['baseImponible'] += base_cero
            pdata[keyp]['baseImpGrav'] += base_not_cero
            pdata[keyp]['montoIva'] += amount_vat
            pdata[keyp]['montoIce'] += amount_ice
            retentions = inv.l10n_ec_withhold_ids.filtered(lambda a: a.state == 'posted')
            if retentions:
                data_air = retentions.mapped("l10n_ec_withhold_line_ids")
                retention_ids.append(retentions.ids)

                for line in data_air:
                    for tax in line.tax_ids:
                        tax_group = tax.tax_group_id.l10n_ec_type
                        if tax_group in ['withhold_income_tax']:
                            pdata[keyp]['valorRetRenta'] += line.l10n_ec_withhold_tax_amount
                        elif tax_group in ['withhold_vat_sale']:
                            pdata[keyp]['valorRetIva'] += line.l10n_ec_withhold_tax_amount  # noqa

        return pdata

    def get_details_ventas_object(self):
        inv_obj = self.env['account.move']
        wiz = self
        tax_group_obj = self.env['account.tax.group']
        companies = [self.company_id.id]

        if self.company_id.sudo().child_ids:
            companies.extend(self.company_id.sudo().child_ids.ids)
        # Facturas de Compra con retenciones
        inv_ids = inv_obj.sudo().search([
            ('state', 'in', ['posted']),
            ('invoice_date', '>=', fields.Date.to_string(self.date_start)),
            ('invoice_date', '<=', fields.Date.to_string(self.date_end)),
            ('l10n_latam_document_type_id.ats_declare', '=', True),
            ('journal_id.code', 'not in', ['CXC', 'cxc']),
            ('move_type', 'in', ['out_invoice', 'out_refund']),
            ('company_id', 'in', companies)
        ])  # noqa

        pdata = []

        for inv in inv_ids:
            # logging.info(inv)
            part_id = inv.partner_id.vat
            tipoComprobante = inv.l10n_latam_document_type_id.code
            formaPago = '01'
            tipoEmision = 'E'

            tpIdCliente = inv.partner_id.l10n_latam_identification_type_id.code_ats_sales
            if not tpIdCliente and hasattr(inv.partner_id.l10n_latam_identification_type_id, "electronic_code"):
                tpIdCliente = inv.partner_id.l10n_latam_identification_type_id.electronic_code

            keyp = '%s-%s-%s' % (part_id, tipoComprobante, tipoEmision)
            tipoCli = '01'

            data = {
                'tipoEmisionText': u'Electrónica',
                'tpIdCliente': tpIdCliente or '05',
                'idCliente': inv.partner_id.vat or 'NO IDENTIFICACION',
                'denoCli': inv.partner_id.name.replace('.', "").replace(u'ñ', "n").replace(u'Ñ', "N"),
                'tipoCli': tipoCli,
                'tipoEmision': tipoEmision,
                'noFactura': inv.l10n_latam_document_number,
                'auth': inv.l10n_ec_authorization_number,
                'basenoGraIva': 0,
                'baseImponible': 0,
                'baseImpGrav': 0,
                'montoIva': 0,
                'valorRetRenta': 0,
                'tipoComprobante': tipoComprobante,
                'valorRetIva': 0,
                'formaPago': formaPago,
                'estado': 'Publicado',
                'montoIce': 0,
                'amount_untaxed': inv.amount_untaxed
            }

            amount_ice = 0
            amount_vat = 0
            amount_novat = 0
            base_not_cero = 0
            base_cero = 0
            import json
            invoice_totals = inv.tax_totals
            for amount_by_group_list in invoice_totals['groups_by_subtotal'].values():
                for amount_by_group in amount_by_group_list:
                    tax_group = tax_group_obj.browse(amount_by_group.get('tax_group_id', 0))

                    base = amount_by_group.get('tax_group_base_amount', 0.00)
                    amount = amount_by_group.get('tax_group_amount', 0.00)

                    if tax_group.l10n_ec_type == 'zero_vat':
                        base_cero += base
                    if tax_group.l10n_ec_type == 'ice':
                        amount_ice += amount
                    if tax_group.l10n_ec_type in ['not_charged_vat', 'exempt_vat']:
                        amount_novat += base
                    if tax_group.l10n_ec_type in ['vat05', 'vat08', 'vat12', 'vat13', 'vat14', 'vat15']:
                        amount_vat += amount
                        base_not_cero += base

            data['basenoGraIva'] += amount_novat
            data['baseImponible'] += base_cero
            data['baseImpGrav'] += base_not_cero
            data['montoIva'] += amount_vat
            data['montoIce'] += amount_ice
            retentions = inv.l10n_ec_withhold_ids.filtered(lambda a: a.state == 'posted')
            if retentions:
                data_air = retentions.mapped("l10n_ec_withhold_line_ids")
                name = retentions.mapped("ref")[0]
                retAuthorizacion = retentions.mapped("l10n_ec_authorization_number")[0]
                data['retNumber'] = name and name.replace("-", "")[-15:] or retAuthorizacion
                data['retAuthorizacion'] = retAuthorizacion

                for line in data_air:
                    for tax in line.tax_ids:
                        tax_group = tax.tax_group_id.l10n_ec_type
                        if tax_group in ['withhold_income_sale']:
                            data['valorRetRenta'] += line.l10n_ec_withhold_tax_amount
                        elif tax_group in ['withhold_vat_sale']:
                            data['valorRetIva'] += line.l10n_ec_withhold_tax_amount  # noqa

            pdata.append(data)

        return pdata

    def det_comptas(self, compras, invoce_not_auth, error, msg):
        inv_obj = self.env['account.move']
        tax_group_obj = self.env['account.tax.group']
        # Facturas de Compra con retenciones
        companies = [self.company_id.id]

        if self.company_id.sudo().child_ids:
            companies.extend(self.company_id.sudo().child_ids.ids)
        inv_ids = inv_obj.sudo().search([
            ('state', 'in', ['posted']),
            ('invoice_date', '>=', fields.Date.to_string(self.date_start)),
            ('invoice_date', '<=', fields.Date.to_string(self.date_end)),
            ('l10n_latam_document_type_id.ats_declare', '=', True),
            ('journal_id.code', 'not in', ['CXP', 'cxp']),
            ('move_type', 'in', ['in_invoice', 'in_refund']),
            ('company_id', 'in', companies)
        ])  # noqa

        sumarizado = 0
        for inv in inv_ids:

            tcomp = inv.l10n_latam_document_type_id.code
            text_f = inv.l10n_latam_document_type_id.name
            detallecompras = etree.Element('detalleCompras')
            etree.SubElement(detallecompras,
                             'codSustento').text = inv.l10n_latam_document_sustento and inv.l10n_latam_document_sustento.code or ''  # noqa
            if not inv.partner_id.vat:
                error = True
                series = str(inv.l10n_latam_document_number).split("-")
                if len(series) == 3:
                    se = series[0]
                    pe = series[1]
                    sec = str(series[2]).rjust(9, "0")
                else:
                    se = inv.l10n_latam_document_number[0:3]
                    pe = inv.l10n_latam_document_number[3:6]
                    sec = inv.l10n_latam_document_number[6:15]

                msg += 'No ha ingresado toda los datos de %s' % inv.partner_id.name
                text_f = 'No ha ingresado toda los datos de %s' % inv.partner_id.name
                invoce_not_auth.append("%s: %s-%s-%s" % (text_f, str(se), str(pe), str(sec)))
                # raise ValidationError('No ha ingresado toda los datos de %s' % inv.partner_id.name)  # noqa
            etree.SubElement(detallecompras,
                             'tpIdProv').text = inv.partner_id.l10n_latam_identification_type_id and inv.partner_id.l10n_latam_identification_type_id.code_ats_purchase or '04'  # noqa
            etree.SubElement(detallecompras, 'idProv').text = inv.partner_id.vat or ''  # noqa

            if inv.partner_id.l10n_latam_identification_type_id and inv.partner_id.l10n_latam_identification_type_id.code_ats_purchase == "01" and inv.l10n_latam_document_type_id.code == '16':
                etree.SubElement(detallecompras, 'tipoComprobante').text = "01"
            else:
                etree.SubElement(detallecompras, 'tipoComprobante').text = inv.l10n_latam_document_type_id.code

            if inv.partner_id.l10n_latam_identification_type_id.code_ats_purchase == '03':
                etree.SubElement(detallecompras, 'tipoProv').text = inv.partner_id.is_company and '02' or '01'
                etree.SubElement(detallecompras, 'denoProv').text = inv.partner_id.name.replace('.', "").replace(Fr'ñ',
                                                                                                                 "n").replace(
                    u'Ñ', "N")
                etree.SubElement(detallecompras,
                                 'parteRel').text = inv.partner_id.l10n_ec_related_party and 'SI' or 'NO'
            else:
                etree.SubElement(detallecompras,
                                 'parteRel').text = inv.partner_id.l10n_ec_related_party and 'SI' or 'NO'

            date = self.convertir_fecha(inv.invoice_date)
            etree.SubElement(detallecompras, 'fechaRegistro').text = date
            auth = False
            if inv.move_type == 'in_invoice' or inv.move_type == 'in_refund':
                series = str(inv.l10n_latam_document_number).split("-")
                if len(series) == 3:
                    se = series[0]
                    pe = series[1]
                    sec = str(series[2]).rjust(9, "0")
                else:
                    se = inv.l10n_latam_document_number[0:3]
                    pe = inv.l10n_latam_document_number[3:6]
                    sec = inv.l10n_latam_document_number[6:15]

                if hasattr(inv, "l10n_ec_authorization_number"):
                    auth = inv.l10n_ec_authorization_number

            if not auth:
                invoce_not_auth.append("%s: %s-%s-%s" % (text_f, str(se), str(pe), str(sec)))
                error = True
                continue
            totbasesImpReemb = 0
            reembolsos = etree.Element('reembolsos')
            is_reembolso = False

            if inv.is_reimbursement_invoice and inv.l10n_latam_document_type_id and inv.l10n_latam_document_type_id.code != '03':

                for reem in inv.reimbursement_ids:
                    reembolso = etree.Element('reembolso')
                    etree.SubElement(reembolso, 'tipoComprobanteReemb').text = reem.document_type_id.code
                    etree.SubElement(reembolso,
                                     'tpIdProvReemb').text = reem.partner_id.l10n_latam_identification_type_id.code_ats_purchase
                    etree.SubElement(reembolso, 'idProvReemb').text = reem.partner_id.vat
                    etree.SubElement(reembolso, 'establecimientoReemb').text = reem.serie_entidad
                    etree.SubElement(reembolso, 'puntoEmisionReemb').text = reem.serie_emision
                    etree.SubElement(reembolso, 'secuencialReemb').text = reem.num_secuencial
                    etree.SubElement(reembolso, 'fechaEmisionReemb').text = self.convertir_fecha(reem.fechaEmisionReemb)
                    etree.SubElement(reembolso, 'autorizacionReemb').text = reem.autorizacionReemb
                    etree.SubElement(reembolso, 'baseImponibleReemb').text = '%.2f' % round(reem.baseImponibleReemb, 2)
                    etree.SubElement(reembolso, 'baseImpGravReemb').text = '%.2f' % round(reem.baseImpGravReemb, 2)
                    etree.SubElement(reembolso, 'baseNoGraIvaReemb').text = '%.2f' % round(reem.baseNoGraIvaReemb, 2)
                    etree.SubElement(reembolso, 'baseImpExeReemb').text = '%.2f' % round(reem.baseImpExeReemb, 2)
                    etree.SubElement(reembolso, 'montoIceRemb').text = '%.2f' % round(reem.montoIceRemb, 2)
                    etree.SubElement(reembolso, 'montoIvaRemb').text = '%.2f' % round(reem.montoIvaRemb, 2)
                    is_reembolso = True
                    totbasesImpReemb += reem.baseImpGravReemb + reem.baseImponibleReemb + reem.baseImpExeReemb
                    reembolsos.append(reembolso)
                    # noqa
            etree.SubElement(detallecompras, 'establecimiento').text = se
            etree.SubElement(detallecompras, 'puntoEmision').text = pe
            etree.SubElement(detallecompras, 'secuencial').text = sec

            amount_tax = 0.00
            amount_ice = 0
            amount_vat = 0
            # amount_exemvat = 0
            amount_novat = 0  # abs(inv.l10n_latam_amount_untaxed_not_charged_vat)

            line_cero = abs(inv.l10n_latam_amount_untaxed_zero + inv.l10n_latam_amount_untaxed_exempt_vat)
            # line_exempt = abs(inv.l10n_latam_amount_untaxed_exempt_vat)
            invoice_totals = inv.tax_totals
            for amount_by_group_list in invoice_totals['groups_by_subtotal'].values():
                for amount_by_group in amount_by_group_list:
                    tax_group = tax_group_obj.browse(amount_by_group.get('tax_group_id', 0))

                    base = amount_by_group.get('tax_group_base_amount', 0.00)
                    amount = amount_by_group.get('tax_group_amount', 0.00)

                    if tax_group.l10n_ec_type == 'ice':
                        amount_ice += amount
                    if tax_group.l10n_ec_type in ['not_charged_vat', 'exempt_vat']:
                        amount_novat += base
                    if tax_group.l10n_ec_type in ['vat05', 'vat08', 'vat12', 'vat13', 'vat14', 'vat15']:
                        amount_vat += amount
                        amount_tax += base

            amount_not_iva = amount_novat == 0 and '0.00' or '%.2f' % round(amount_novat, 2)
            amount_cero_bmp = amount_not_iva == '%.2f' % line_cero and '0.00' or '%.2f' % line_cero
            base_main = amount_novat + float(amount_cero_bmp) + amount_tax + amount_vat + amount_ice
            ##
            etree.SubElement(detallecompras, 'fechaEmision').text = date  # noqa
            etree.SubElement(detallecompras, 'autorizacion').text = auth
            etree.SubElement(detallecompras, 'baseNoGraIva').text = amount_not_iva
            etree.SubElement(detallecompras, 'baseImponible').text = amount_cero_bmp
            etree.SubElement(detallecompras, 'baseImpGrav').text = '%.2f' % amount_tax  # noqa
            etree.SubElement(detallecompras, 'baseImpExe').text = '0.00'
            etree.SubElement(detallecompras, 'montoIce').text = '%.2f' % round(amount_ice, 2)
            etree.SubElement(detallecompras, 'montoIva').text = '%.2f' % round(amount_vat, 2)  # noqa
            valRetBien10, valRetServ20, valorRetBienes, valorRetServicios, valRetServ50, valorRetServ100 = self._get_ret_iva(
                inv)  # noqa

            if inv.l10n_latam_document_type_id.code == '41':
                etree.SubElement(detallecompras, 'valRetBien10').text = '0.00'
                etree.SubElement(detallecompras, 'valRetServ20').text = '0.00'
                etree.SubElement(detallecompras, 'valorRetBienes').text = '0.00'
                etree.SubElement(detallecompras, 'valRetServ50').text = '0.00'
                etree.SubElement(detallecompras, 'valorRetServicios').text = '0.00'
                etree.SubElement(detallecompras, 'valRetServ100').text = '0.00'
            else:
                etree.SubElement(detallecompras, 'valRetBien10').text = '%.2f' % round(valRetBien10, 2)  # noqa
                etree.SubElement(detallecompras, 'valRetServ20').text = '%.2f' % round(valRetServ20, 2)  # noqa
                etree.SubElement(detallecompras, 'valorRetBienes').text = '%.2f' % round(valorRetBienes, 2)  # noqa
                etree.SubElement(detallecompras, 'valRetServ50').text = '%.2f' % round(valRetServ50, 2)  # noqa
                etree.SubElement(detallecompras, 'valorRetServicios').text = '%.2f' % round(valorRetServicios,
                                                                                            2)  # noqa
                etree.SubElement(detallecompras, 'valRetServ100').text = '%.2f' % round(valorRetServ100, 2)  # noqa

            etree.SubElement(detallecompras, 'totbasesImpReemb').text = '%.2f' % round(totbasesImpReemb, 2)
            pagoExterior = etree.Element('pagoExterior')
            etree.SubElement(pagoExterior, 'pagoLocExt').text = '01'
            etree.SubElement(pagoExterior, 'paisEfecPago').text = 'NA'
            etree.SubElement(pagoExterior, 'aplicConvDobTrib').text = 'NA'
            etree.SubElement(pagoExterior, 'pagExtSujRetNorLeg').text = 'NA'
            detallecompras.append(pagoExterior)

            if tcomp not in ['03', '04'] and self.act_condition_payment_tag(base_main):
                formasDePago = etree.Element('formasDePago')
                etree.SubElement(formasDePago,
                                 'formaPago').text = inv.l10n_ec_sri_payment_id and inv.l10n_ec_sri_payment_id.code or '20'
                detallecompras.append(formasDePago)

            retentions = inv.l10n_ec_withhold_ids.filtered(lambda a: a.state == 'posted')
            data_air = self.process_lines(inv)
            if (data_air):
                air = etree.Element('air')

                for da in data_air:
                    detalleAir = etree.Element('detalleAir')
                    etree.SubElement(detalleAir, 'codRetAir').text = da['codRetAir']  # noqa
                    etree.SubElement(detalleAir, 'baseImpAir').text = '%.2f' % da['baseImpAir']  # noqa
                    etree.SubElement(detalleAir, 'porcentajeAir').text = '%.2f' % da['porcentajeAir']  # noqa
                    etree.SubElement(detalleAir, 'valRetAir').text = '%.2f' % da['valRetAir']  # noqa
                    if da['codRetAir'] and str(da['codRetAir']) in ['338', '338A', '338B']:
                        etree.SubElement(detalleAir, 'numCajBan').text = '%s' % da['numCajBan']  # noqa
                        etree.SubElement(detalleAir, 'precCajBan').text = '%.2f' % da['precCajBan']  # noqa
                    air.append(detalleAir)
                detallecompras.append(air)

            if (inv.reversed_entry_id and inv.move_type == 'in_refund') or (
                    inv.debit_origin_id and inv.move_type == 'in_invoice'):

                factura_origen = inv.reversed_entry_id or inv.debit_origin_id

                if factura_origen:
                    series = str(factura_origen.l10n_latam_document_number).split("-")
                    if len(series) == 3:
                        se = series[0]
                        pe = series[1]
                        sec = str(series[2]).rjust(9, "0")
                    else:
                        se = factura_origen.l10n_latam_document_number[0:3]
                        pe = factura_origen.l10n_latam_document_number[4:7]
                        sec = factura_origen.l10n_latam_document_number[-9:]

                    if hasattr(factura_origen, "l10n_ec_authorization_number"):
                        auth = factura_origen.l10n_ec_authorization_number

                    etree.SubElement(detallecompras, 'docModificado').text = '01'
                    etree.SubElement(detallecompras, 'estabModificado').text = se
                    etree.SubElement(detallecompras, 'ptoEmiModificado').text = pe
                    etree.SubElement(detallecompras, 'secModificado').text = sec
                    etree.SubElement(detallecompras, 'autModificado').text = auth and auth or ''

            if retentions:
                autRetencion1 = False
                l10n_ec_authorization_number = retentions.mapped("l10n_ec_authorization_number")
                l10n_latam_document_number = retentions.mapped("l10n_latam_document_number")
                withhold_id_date = retentions.mapped("l10n_ec_withhold_date")
                if l10n_ec_authorization_number:
                    autRetencion1 = l10n_ec_authorization_number[0]

                if not autRetencion1:
                    text = "".join([u"Retención %s" % (ret.name) for ret in retentions])
                    invoce_not_auth.append(text)
                    error = True
                    continue

                if l10n_latam_document_number:
                    se = l10n_latam_document_number[0][0:3]
                    pe = l10n_latam_document_number[0][4:7]
                    sec = l10n_latam_document_number[0][-9:]
                else:
                    text = "".join([u"Retención %s" % (ret.name) for ret in retentions])
                    invoce_not_auth.append(text)
                    error = True
                    continue

                etree.SubElement(detallecompras, 'estabRetencion1').text = se
                etree.SubElement(detallecompras, 'ptoEmiRetencion1').text = pe
                etree.SubElement(detallecompras, 'secRetencion1').text = sec
                etree.SubElement(detallecompras, 'autRetencion1').text = autRetencion1
                etree.SubElement(detallecompras, 'fechaEmiRet1').text = self.convertir_fecha(withhold_id_date[0])

            if is_reembolso:
                detallecompras.append(reembolsos)
            compras.append(detallecompras)

        if len(invoce_not_auth) > 0:
            error = True
        return compras

    def act_condition_payment_tag(self, base):
        # Actualización Ats 21 - 01 - 2025
        # Dimm V 1.11.0 >
        return base > 500 and True or False

    def act_export_ats(self):
        for wiz in self:
            msg = ""
            error = False
            ruc = wiz.company_id.vat
            inv_obj = self.env['account.move']
            if not ruc:
                raise ValidationError(
                    u"""Debe configurar el ruc de la compañía.""")  # noqa

            # wiz.write({
            #    'state': 'errors',
            #    'error_warning': msg
            # })
            _ruc = len(ruc) == 15 and ruc[2:15] or ruc
            month = wiz.date_end.month <= 9 and "0%s" % wiz.date_end.month or str(wiz.date_end.month)
            year = str(wiz.date_end.year)
            ats = etree.Element('iva')
            etree.SubElement(ats, 'TipoIDInformante').text = 'R'
            etree.SubElement(ats, 'IdInformante').text = str(_ruc)
            etree.SubElement(ats, 'razonSocial').text = wiz.company_id.name.replace('.', "").replace(u'ñ', "n").replace(
                u'Ñ', "N")
            # TODO aqui revisar este tag con el anio mes
            etree.SubElement(ats, 'Anio').text = year  # noqa
            etree.SubElement(ats, 'Mes').text = month  # noqa
            etree.SubElement(ats, 'numEstabRuc').text = wiz.num_estab_ruc.zfill(3)

            total_ventas = wiz._get_ventas()

            # if float(total_ventas) < 0:
            total_ventas = 0.00  # Todas eletronicas
            etree.SubElement(ats, 'totalVentas').text = '%.2f' % total_ventas
            etree.SubElement(ats, 'codigoOperativo').text = 'IVA'
            compras = etree.Element('compras')
            invoce_not_auth = []
            compras = wiz.det_comptas(compras, invoce_not_auth, error, msg)
            ats.append(compras)

            if float(total_ventas) >= 0:
                # VENTAS DECLARADAS
                ventas = etree.Element('ventas')

                pdata = wiz._get_details_ventas()

                for k, v in pdata.items():
                    detalleVentas = etree.Element('detalleVentas')

                    etree.SubElement(detalleVentas, 'tpIdCliente').text = v['tpIdCliente']  # noqa
                    etree.SubElement(detalleVentas, 'idCliente').text = v['idCliente']  # noqa

                    if v['tpIdCliente'] != '07':
                        etree.SubElement(detalleVentas, 'parteRelVtas').text = 'NO'

                    if v['tpIdCliente'] == '06':
                        etree.SubElement(detalleVentas, 'tipoCliente').text = v['tipoCli']
                        etree.SubElement(detalleVentas, 'denoCli').text = v['denoCli'].replace(u'ñ', "n").replace(u'Ñ',
                                                                                                                  "N")

                    etree.SubElement(detalleVentas, 'tipoComprobante').text = v['tipoComprobante']  # noqa
                    etree.SubElement(detalleVentas, 'tipoEmision').text = v['tipoEmision']  # noqa
                    etree.SubElement(detalleVentas, 'numeroComprobantes').text = str(v['numeroComprobantes'])  # noqa
                    etree.SubElement(detalleVentas, 'baseNoGraIva').text = '%.2f' % v['basenoGraIva']  # noqa
                    etree.SubElement(detalleVentas, 'baseImponible').text = '%.2f' % v['baseImponible']  # noqa
                    etree.SubElement(detalleVentas, 'baseImpGrav').text = '%.2f' % v['baseImpGrav']  # noqa
                    etree.SubElement(detalleVentas, 'montoIva').text = '%.2f' % v['montoIva']  # noqa
                    etree.SubElement(detalleVentas, 'montoIce').text = '%.2f' % v['montoIce']  # noqa
                    etree.SubElement(detalleVentas, 'valorRetIva').text = '%.2f' % v['valorRetIva']  # noqa
                    etree.SubElement(detalleVentas, 'valorRetRenta').text = '%.2f' % v['valorRetRenta']  # noqa

                    if str(v['tipoComprobante']) != '04':
                        formasDePago = etree.Element('formasDePago')
                        etree.SubElement(formasDePago, 'formaPago').text = str(v['formaPago'])  # noqa
                        detalleVentas.append(formasDePago)

                    ventas.append(detalleVentas)
                ats.append(ventas)
                # Ventas establecimiento
                ventasEstablecimiento = etree.Element('ventasEstablecimiento')
                tventas = wiz._get_ventas()

                # if float(tventas) < 0:
                tventas = 0.00  # Todas eletronicas

                ventaEst = etree.Element('ventaEst')
                etree.SubElement(ventaEst, 'codEstab').text = wiz.num_estab_ruc  # noqa
                etree.SubElement(ventaEst, 'ventasEstab').text = '%.2f' % tventas  # noqa

                ventasEstablecimiento.append(ventaEst)

                if wiz.num_estab_ruc != '001':
                    ventaEst = etree.Element('ventaEst')
                    etree.SubElement(ventaEst, 'codEstab').text = '001'  # noqa
                    etree.SubElement(ventaEst, 'ventasEstab').text = "0.00"

                    ventasEstablecimiento.append(ventaEst)

                ats.append(ventasEstablecimiento)
            # Documentos Anulados
            anulados = etree.Element('anulados')
            companies = [self.company_id.id]

            if self.company_id.sudo().child_ids:
                companies.extend(self.company_id.sudo().child_ids.ids)

            inv_ids = inv_obj.sudo().search([
                ('state', 'in', ['cancel']),
                ('invoice_date', '>=', str(wiz.date_start)),
                ('invoice_date', '<=', str(wiz.date_end)),
                ('l10n_latam_document_type_id.ats_declare', '=', True),
                ('move_type', 'in', ['out_invoice']),
                ('company_id', 'in', companies)
            ])
            authorization = False
            for inv in inv_ids:
                if hasattr(inv, "l10n_ec_authorization_number"):
                    authorization = inv.l10n_ec_authorization_number

                if not authorization:
                    authorization = '9999'

                se = inv.l10n_latam_document_number and inv.l10n_latam_document_number[0:3] or '000'
                pe = inv.l10n_latam_document_number and inv.l10n_latam_document_number[4:7] or '000'
                sec = inv.l10n_latam_document_number and inv.l10n_latam_document_number[-9:] or '000000000'

                detalleAnulados = etree.Element('detalleAnulados')
                etree.SubElement(detalleAnulados, 'tipoComprobante').text = inv.l10n_latam_document_type_id.code  # noqa
                etree.SubElement(detalleAnulados, 'establecimiento').text = se  # noqa
                etree.SubElement(detalleAnulados, 'puntoEmision').text = pe  # noqa
                etree.SubElement(detalleAnulados, 'secuencialInicio').text = sec  # noqa
                etree.SubElement(detalleAnulados, 'secuencialFin').text = str(sec)
                etree.SubElement(detalleAnulados, 'autorizacion').text = authorization  # noqa
                anulados.append(detalleAnulados)

            ats.append(anulados)

            if wiz.no_validate or (not error and len(invoce_not_auth) == 0):
                file_path = os.path.join(os.path.dirname(__file__), 'XSD/ats_xsd_2016_ago_29.xsd')
                schema_file = open(file_path)
                file_ats = etree.tostring(ats, pretty_print=True, encoding='iso-8859-1')
                # validata schema
                # xmlschema_doc = etree.parse(schema_file)
                # xmlschema = etree.XMLSchema(xmlschema_doc)

                state = 'export'

                # if not wiz.no_validate:
                #    try:
                #        xmlschema.assertValid(ats)
                #    except DocumentInvalid as e:
                #        msg = e
                #        state = 'warning'

                buf = StringIO()
                buf.write(file_ats.decode('utf-8', errors='ignore'))
                out = base64.b64encode(buf.getvalue().encode())
                buf.close()
                name = "%s%s%s.XML" % (
                    "ATS",
                    year,
                    month
                )
                wiz.write({
                    'state': state,
                    'data': out,
                    'fcname': name,
                    'error_warning': msg
                })
            else:
                if not msg:
                    msg = ""

                msg += u"El(Los) siguientes documento(s) no contiene(n) un número de autorización válido. [%s] " % (
                    ",\n".join(invoce_not_auth))

                wiz.write({
                    'state': 'errors',
                    'error_warning': msg
                })

            return {
                'name': "Anexo Transaccional Simplificado (ATS)",
                'view_mode': 'form',
                'res_id': wiz.id,
                'res_model': 'wizard.ats',
                'type': 'ir.actions.act_window',
                'target': 'new',
                'context': self.env.context,
                'nodestroy': True,
            }

    def export_xls(self):
        self.ensure_one()
        context = self._context
        company = self.company_id
        data = {
            "model": 'account.move',
            "company": company.name,
            "ruc": company.vat,
            'period': '%s - %s' % (self.date_start.strftime('%d/%m/%Y'), self.date_end.strftime('%d/%m/%Y')),
            'form': self.read()[0]
        }

        for field in data['form'].keys():
            if isinstance(data['form'][field], tuple):
                data['form'][field] = data['form'][field][0]

        action = (self.env.ref("ek_l10n_ec.ats_sheet_xlsx"))
        return action.report_action(self, data=data)
