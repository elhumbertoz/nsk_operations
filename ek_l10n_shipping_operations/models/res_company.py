from odoo import fields, models, api


class res_company(models.Model):
    _inherit = "res.company"

    image_1_header_report = fields.Binary(string="Image 1 Header Report")
    image_2_header_report = fields.Binary(string="Image 2 Header Report")
    trade_sequence_id = fields.Many2one("ir.sequence", string="Sequence Trade", copy=False, help="Sequence for generate trade number")
    
    # Configuración para facturas de reembolso
    reimbursement_journal_id = fields.Many2one(
        'account.journal', 
        string='Diario para Reembolsos',
        domain="[('type', '=', 'sale')]",
        help="Diario por defecto para facturas de reembolso de cliente"
    )
    reimbursement_document_type_id = fields.Many2one(
        'l10n_latam.document.type',
        string='Tipo de Documento para Reembolsos',
        help="Tipo de documento por defecto para facturas de reembolso"
    )
    reimbursement_document_sustento = fields.Many2one('account.ats.sustento',
        string='Sustento Tributario para Reembolsos',
        help="Sustento tributario por defecto para facturas de reembolso"
    )
    reimbursement_payment_method_id = fields.Many2one(
        'l10n_ec.sri.payment',
        string='Forma de Pago para Reembolsos',
        help="Forma de pago por defecto para facturas de reembolso"
    )