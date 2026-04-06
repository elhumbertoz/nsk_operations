# -*- coding: utf-8 -*-
import logging

from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError

_logger = logging.getLogger(__name__)


class PurchaseOrder(models.Model):
    _inherit = 'purchase.order'

    is_reimbursement = fields.Boolean('Reimbursement', copy=False)
    invoice_reimbursement_id = fields.Many2one(
        'account.move',
        string='Factura Reembolso',
    )

    def action_create_reimbursement(self, invoice):
        self.ensure_one()
        for cinvoice in self.invoice_ids:
            partner = cinvoice.partner_id
            tax = cinvoice.mapped('invoice_line_ids.tax_ids')

            series = str(cinvoice.l10n_latam_document_number).split("-")
            if len(series) == 3:
                se = series[0]
                pe = series[1]
                sec = str(series[2]).rjust(9, "0")
            else:
                se = cinvoice.l10n_latam_document_number[0:3]
                pe = cinvoice.l10n_latam_document_number[3:6]
                sec = cinvoice.l10n_latam_document_number[6:15]

            if not se:
                se = '000'
            if not pe:
                pe = '000'
            if not sec:
                sec = '999'

            self.env['account.reimbursement.document'].create({
                'purchase_order_id': self.id,
                'invoice_id': invoice.id,
                'partner_id': partner.id,
                'document_type_id': cinvoice.l10n_latam_document_type_id.id,
                'identification_type_id': partner.l10n_latam_identification_type_id.id,
                'identification_id': partner.vat,
                'serie_entidad': se,
                'serie_emision': pe,
                'num_secuencial': sec,
                'link_move_id': cinvoice.id,
                'autorizacionReemb': cinvoice.l10n_ec_authorization_number or '999',
                'fechaEmisionReemb': cinvoice.invoice_date or cinvoice.date,
                'baseImponibleReemb': abs(cinvoice.l10n_latam_amount_untaxed_zero), #Base Imponible tarifa 0% IVA Reembolso
                'baseImpGravReemb': abs(cinvoice.l10n_latam_amount_untaxed_not_zero), #Base Imponible tarifa IVA diferente de 0% Reembolso
                'montoIceRemb': 0.00, #Monto ICE Reembolso
                'montoIvaRemb': abs(cinvoice.l10n_latam_amount_vat), #Monto IVA Reembolso
                'baseImpExeReemb': abs(cinvoice.l10n_latam_amount_untaxed_exempt_vat), #Base imponible exenta de IVA Reembolso
                'baseNoGraIvaReemb': abs(cinvoice.l10n_latam_amount_untaxed_not_charged_vat), #Base Imponible no objeto de IVA - REEMBOLSO
                'tax_id': tax and tax[0].id or False,
            })
            cinvoice.sudo().write({"reimbursed_move_id": invoice.id})

        self.write({
            'invoice_reimbursement_id': invoice.id,
            'is_reimbursement': True
        })

    def clear_reimbursement(self):
        self.write({
            'invoice_reimbursement_id': False,
            'is_reimbursement': False
        })

    def button_cancel(self):
        for rec in self:
            if rec.invoice_reimbursement_id and rec.invoice_reimbursement_id.state != 'cancel':
                raise UserError(_("No es posible cancelar un pedido de compra asociado a una factura de reembolso activa.\n"
                                  "Antes anule esta factura de reembolso %s" % rec.invoice_reimbursement_id.name))
        return super(PurchaseOrder, self).button_cancel()
