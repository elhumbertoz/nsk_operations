# -*- coding: utf-8 -*-
import xlrd
import base64
import tempfile
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class NotFoundDataImport(models.TransientModel):
    _name = "not.found.data.import"
    _description = "Lines no importadas"

    line = fields.Integer(
        string=_("# Línea"),
        required=False,
    )
    name = fields.Char(
        string="Código",
    )
    error = fields.Char(
        string=_("Error"),
    )
    product_qty = fields.Float(
        string=_("Cantidad"),
    )
    price = fields.Float(
        string=_("Precio"),
    )
    wizard_id = fields.Many2one(
        string=_("Generar Facturas"),
        comodel_name="ek.import.generate.invoice",
        required=False,
    )


class EkImportGenerateInvoice(models.TransientModel):
    """Asociar regalias a viaje"""
    _name = "ek.import.generate.invoice"
    _description = "Generar facturas desde órdenes de importación"

    is_grouping = fields.Boolean(
        string=_("¿Agrupar Facturas?"),
        default=True,
    )
    name = fields.Char(
        string=_("Número"),
    )
    source = fields.Selection(
        string=_("Origen"),
        selection=[
            ("line", _("Líneas")),
            ("xlsx", _("Plantilla")),
        ],
        required=False,
    )
    errors_ids = fields.One2many(
        string=_("Errores"),
        comodel_name="not.found.data.import",
        inverse_name="wizard_id",
        required=False,
    )
    date = fields.Date(
        string=_("Fecha"),
        required=False,
    )
    reference = fields.Char(
        string=_("Referencia"),
        required=False,
    )
    partner_id = fields.Many2one(
        string=_("Proveedor"),
        comodel_name="res.partner",
        required=False,
    )
    note = fields.Text(
        string=_("Notas"),
        required=False,
    )
    import_liquidation_id = fields.Many2one(
        string=_("Importación"),
        comodel_name="ek.import.liquidation",
        required=False,
    )
    journal_id = fields.Many2one(
        string=_("Diario"),
        comodel_name="account.journal",
        required=False,
    )
    l10n_latam_document_type_id = fields.Many2one(
        string=_("Tipo de Documento"),
        comodel_name="l10n_latam.document.type",
    )
    template_xlsx = fields.Binary(
        string=_("Plantilla"),
    )
    template_xlsx_name = fields.Char(
        string=_("Nombre de plantilla"),
    )
    free_import = fields.Boolean(
        string=_("Subida libre"),
        required=False,
        help=_("Permite la subida de información sin validación de cantidades ni productos."),
    )

    def action_confirm(self):
        active_ids = self.env.context.get('active_ids')
        objects = self.env['ek.import.liquidation'].browse(active_ids).filtered(lambda x: x.state in ['draft', 'calculate'])
        obj_invoice = self.env['account.move']
        data_invoice = {}

        for rec in objects:
            date_due = fields.Date.context_today(self)
            for line in rec.order_line.filtered(lambda x: not x.invoice_id):
                partner = line.purchase_line_id.order_id.partner_id or rec.partner_id


                if line.product_id:
                    account_id = line.product_id.product_tmpl_id._get_product_accounts()['import']
                else:
                    account_id = self.env['ir.property']._get('property_stock_account_import_cost_id', 'product.category')

                if not account_id:
                    account_id = line.product_id.property_account_expense_id and line.product_id.property_account_expense_id or False

                if not account_id:
                    account_id = line.product_id.categ_id and line.product_id.categ_id.property_account_expense_categ_id or False

                _line = {
                    'product_id': line.product_id.id,
                    'name': line.name,
                    'account_id': account_id and account_id.id or False,
                    'analytic_distribution': line.purchase_line_id and line.purchase_line_id.analytic_distribution or False,
                    'quantity': line.product_qty,
                    'price_unit': line.price_unit,
                    'tax_ids': (line.purchase_line_id and line.purchase_line_id.taxes_id) and [(6, 0, line.purchase_line_id.taxes_id.ids)] or [],
                    'price_subtotal': line.price_subtotal,
                    'liquidation_line_id': line.id,
                    'purchase_line_id': line.purchase_line_id.id,
                    'discount': line.discount or 0.00
                }
                if self.is_grouping:
                    key = "PAR-%s" % partner.id
                else:
                    key = "OC-%s" % line.purchase_line_id.order_id.name
                if key not in data_invoice:
                    data_invoice[key] = {
                        'partner_id': partner.id,
                        'invoice_payment_term_id': rec.partner_id.property_supplier_payment_term_id and rec.partner_id.property_supplier_payment_term_id.id or None,
                        'invoice_date': self.date,
                        'invoice_date_due': date_due,
                        'state': 'draft',
                        'posted_before': False,
                        'move_type': 'in_invoice',
                        'ref': self.reference,
                        'narration': self.note,
                        'invoice_liquidation_id': rec.id,
                        'journal_id': self.journal_id.id,
                        'l10n_latam_document_type_id': self.l10n_latam_document_type_id.id,
                        'l10n_latam_document_number': self.name,
                        'purchase_id': line.purchase_line_id.order_id.id,
                        'invoice_line_ids': []
                    }
                data_invoice[key]['invoice_line_ids'].append( (0,0, _line))
            invoice_created = []
            if len(data_invoice) > 0:
                for key, data in data_invoice.items():
                    inv = obj_invoice.create(data)
                    for line in inv.invoice_line_ids:
                        line.liquidation_line_id.write({'invoice_id': inv.id})
                    invoice_created.append(inv.id)
            else:
                # CREAR FACTURA VACÍA
                inv = obj_invoice.create({
                    'partner_id': rec.partner.id,
                    'invoice_payment_term_id': rec.partner_id.property_supplier_payment_term_id and rec.partner_id.property_supplier_payment_term_id.id or None,
                    'invoice_date': self.date,
                    'invoice_date_due': date_due,
                    'state': 'draft',
                    'move_type': 'in_invoice',
                    'ref': self.reference,
                    'narration': self.note,
                    'invoice_liquidation_id': rec.id,
                    'journal_id': self.journal_id.id,
                    'l10n_latam_document_type_id': self.l10n_latam_document_type_id.id,
                    'l10n_latam_document_number': self.name,
                    'purchase_id': self.import_liquidation_id.purchase_id.id
                })
                invoice_created.append(inv.id)
            if len(invoice_created) > 0:
                if len(rec.invoice_ids.ids) > 0:
                    invoice_created.extend(rec.invoice_ids.ids)
                rec.write({'invoice_ids': [(6, 0, invoice_created)]})

    def action_confirm_import(self):
        obj_invoice = self.env['account.move']
        data_invoice = {}
        active_ids = self.env.context.get('active_ids')
        objects = self.env['ek.import.liquidation'].browse(active_ids).filtered(
            lambda x: x.state in ['draft', 'calculate'])
        for rec in objects:
            try:
                tmp_file = tempfile.NamedTemporaryFile(delete=False)
                tmp_file.write(base64.b64decode(self.template_xlsx and self.template_xlsx or 'Archivo no valido'))
                tmp_file.close()
                wb = xlrd.open_workbook(tmp_file.name)
            except Exception as ex:
                raise ValidationError("No es posible importar la plantilla seleccionada, revise que sea un archivo excel [%s]." % ex.__str__())

            sheet = wb.sheet_by_index(0)
            product_codes = []
            prepare_data = {}
            # Nota: Se considera que la primera fila es la cabecera del listado a importar,
            # por ello se trabaja desde la segunda fila (row en posición [1])
            if sheet.nrows <= 1:
                raise ValidationError("No es posible importar una plantilla vacía.")

            for row in range(sheet.nrows):
                if row >= 1:
                    row_vals = sheet.row_values(row)
                    code = str(row_vals[0]).strip()
                    product_codes.append(code)

            lines = self.env['ek.import.liquidation.line'].search([('product_id.default_code', 'in', product_codes), ('order_id', '=', rec.id)])
            for data in lines:
                if data.product_id.default_code not in prepare_data:
                    prepare_data[data.product_id.default_code] = {'product_qty': 0, 'line': data}

                prepare_data[data.product_id.default_code]['product_qty'] += data.product_qty
            not_found = []

            for row in range(sheet.nrows):
                # Nota: Se considera que la primera fila es la cabecera del listado a importar,
                # por ello se trabaja desde la segunda fila (row en posición [1])
                if row >= 1:
                    row_vals = sheet.row_values(row)
                    code = str(row_vals[0]).strip()
                    product_qty = row_vals[1]
                    if code in prepare_data:
                        line = prepare_data[code]['line']
                        price = len(row_vals) > 2 and row_vals[2] or line.price_unit
                        if product_qty > prepare_data[code]['product_qty']:
                            not_found.append((0, 0, {
                                'line': (row + 1),
                                'name': code,
                                'product_qty': product_qty,
                                'price': price,
                                'wizard_id': self.id,
                                'error': u'La cantidad ingresada es mayor que la linea de la importación'
                            }))
                            continue
                        partner = line.purchase_line_id.order_id.partner_id or rec.partner_id

                        if line.product_id:
                            account_id = line.product_id.product_tmpl_id._get_product_accounts()['import']
                        else:
                            account_id = self.env['ir.property']._get('property_stock_account_import_cost_id',
                                                                      'product.category')

                        if not account_id:
                            account_id = line.product_id.property_account_expense_id and line.product_id.property_account_expense_id.id or False

                        if not account_id:
                            account_id = line.product_id.categ_id and line.product_id.categ_id.property_account_expense_categ_id.id or False


                        _line = {
                            'product_id': line.product_id.id,
                            'name': line.name,
                            'account_id': account_id and account_id.id or False,
                            'analytic_account_id': line.account_analytic_id and line.account_analytic_id.id or False,
                            'quantity': product_qty,
                            'price_unit': price or line.price_unit,
                            'tax_ids': [],
                            'price_subtotal': product_qty * (price or line.price_unit),
                            'liquidation_line_id': line.id,
                            'purchase_line_id': line.purchase_line_id.id
                        }
                        if self.is_grouping:
                            key = "PAR-%s" % partner.id
                        else:
                            key = "OC-%s" % line.purchase_line_id.order_id.name
                        if key not in data_invoice:
                            data_invoice[key] = {
                                'partner_id': partner.id,
                                'invoice_payment_term_id': partner.property_supplier_payment_term_id and partner.property_supplier_payment_term_id.id or None,
                                'invoice_date': self.date,
                                'invoice_date_due': self.date,
                                'state': 'draft',
                                'posted_before': False,
                                'move_type': 'in_invoice',
                                'ref': self.reference,
                                'narration': self.note,
                                'invoice_liquidation_id': rec.id,
                                'journal_id': self.journal_id.id,
                                'l10n_latam_document_type_id': self.l10n_latam_document_type_id.id,
                                'l10n_latam_document_number': self.name,
                                'purchase_id': line.purchase_line_id.order_id.id,
                                'invoice_line_ids': []
                            }
                        data_invoice[key]['invoice_line_ids'].append((0, 0, _line))
                    else:
                        # TODO: Cuando venga por el else, line no existirá debido a que se crea dentro del if
                        price = len(row_vals) > 2 and row_vals[2] or line.price_unit
                        not_found.append((0, 0, {
                            'line': (row + 1),
                            'name': code,
                            'product_qty': product_qty,
                            'price': price,
                            'wizard_id': self.id,
                            'error': "Item no encontrado en la importación"
                        }))

            if len(not_found) == 0:
                invoice_created = []
                if len(data_invoice) > 0:
                    for key, data in data_invoice.items():
                        inv = obj_invoice.create(data)
                        for line in inv.invoice_line_ids:
                            line.liquidation_line_id.write({'invoice_id': inv.id})
                        invoice_created.append(inv.id)
                if len(invoice_created) > 0:
                    if len(rec.invoice_ids.ids) > 0:
                        invoice_created.extend(rec.invoice_ids.ids)
                    rec.write({'invoice_ids': [(6, 0, invoice_created)]})
            else:
                self.update({
                    "errors_ids": not_found
                })

                return {
                    'name': "Generar Factura desde Importación",
                    'view_mode': 'form',
                    'res_id': self.id,
                    'res_model': 'ek.import.generate.invoice',
                    'type': 'ir.actions.act_window',
                    'target': 'new',
                    'context': self.env.context,
                    'nodestroy': True,
                }
