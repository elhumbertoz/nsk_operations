from odoo import fields, models, api


class AccountPaymentRegister(models.TransientModel):
    _inherit = "account.payment.register"


    l10n_ec_acquiring_bank_id = fields.Many2one(comodel_name="res.bank", string="Banco Adquiriente", required=False,
                              help=u"Remite la respuesta de la autorización al merchant.")
    l10n_ec_lot = fields.Char(string="Lote", required=False)
    l10n_ec_credit_auth = fields.Char(string=u"Autorización", required=False)
    l10n_ec_credit_card_number = fields.Char('No. Tarjeta', size=16, help="Basta con los ultimos 4 digitos")
    l10n_ec_credit_card_ref = fields.Char('Referencia')
    l10n_ec_credit_valid_card = fields.Char('Validez', help=u"Debe Indicar hasta cuando es válida la tarjeta. Ejemplo: 02/2020",
                             size=7)

    l10n_ec_credit_card_type = fields.Selection(string=u"Tipo de Transacción",
                                 selection=[('dif', 'Diferido'), ('normal', 'Corriente'), ], required=False,
                                 default="normal")

    l10n_ec_credit_card_deferred_id = fields.Many2one(
        comodel_name='ek.types.deferred.credit.card',
        string='Meses de Diferido', ondelete='restrict',
        required=False)

    def _create_payment_vals_from_wizard(self,batch_result):
        payment_vals = super()._create_payment_vals_from_wizard(batch_result)
        paiments = {
            'l10n_ec_acquiring_bank_id': self.l10n_ec_acquiring_bank_id and self.l10n_ec_acquiring_bank_id.id or False,
            'l10n_ec_lot': self.l10n_ec_lot,
            'l10n_ec_credit_auth': self.l10n_ec_credit_auth,
            'l10n_ec_credit_card_number': self.l10n_ec_credit_card_number,
            'l10n_ec_credit_card_ref': self.l10n_ec_credit_card_ref,
            'l10n_ec_credit_valid_card': self.l10n_ec_credit_valid_card,
            'l10n_ec_credit_card_type': self.l10n_ec_credit_card_type,
            'l10n_ec_credit_card_deferred_id': self.l10n_ec_credit_card_deferred_id and self.l10n_ec_credit_card_deferred_id.id or False
        }
        payment_vals.update(paiments)
        return payment_vals