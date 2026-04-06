from odoo import fields, models, api, _
from odoo.exceptions import ValidationError
import ast

class AccountPayment(models.Model):
    _inherit = 'account.payment'
    is_advance = fields.Boolean(
        string='Anticipo',
        required=False)

    l10n_ec_acquiring_bank_id = fields.Many2one(comodel_name="res.bank", string="Banco Adquiriente", required=False,
                              help=u"Remite la respuesta de la autorización al merchant.", tracking=True)
    l10n_ec_lot = fields.Char(string="Lote", required=False, tracking=True)
    l10n_ec_credit_auth = fields.Char(string=u"Autorización", required=False, tracking=True)
    l10n_ec_credit_card_number = fields.Char('No. Tarjeta', size=16, help="Basta con los ultimos 4 digitos", tracking=True)
    l10n_ec_credit_card_ref = fields.Char('Referencia', tracking=True)
    l10n_ec_credit_valid_card = fields.Char('Validez', help=u"Debe Indicar hasta cuando es válida la tarjeta. Ejemplo: 02/2020",
                             size=7, tracking=True)

    l10n_ec_credit_card_type = fields.Selection(string=u"Tipo de Transacción",
                                 selection=[('dif', 'Diferido'), ('normal', 'Corriente'), ], required=False,
                                 default="normal", tracking=True)

    l10n_ec_credit_card_deferred_id = fields.Many2one(
        comodel_name='ek.types.deferred.credit.card',
        string='Meses de Diferido', ondelete='restrict',
        required=False, tracking=True)

    advance_amount_residual = fields.Monetary(
        string='Pendiente de Cruce',
        store=True,
        compute="_compute_advance_amount_residual",
        required=False)

    @api.depends(
        'move_id.line_ids.matched_debit_ids.debit_move_id.move_id.payment_id.is_matched',
        'move_id.line_ids.matched_debit_ids.debit_move_id.move_id.line_ids.amount_residual',
        'move_id.line_ids.matched_debit_ids.debit_move_id.move_id.line_ids.amount_residual_currency',
        'move_id.line_ids.matched_credit_ids.credit_move_id.move_id.payment_id.is_matched',
        'move_id.line_ids.matched_credit_ids.credit_move_id.move_id.line_ids.amount_residual',
        'move_id.line_ids.matched_credit_ids.credit_move_id.move_id.line_ids.amount_residual_currency',
        'move_id.line_ids.balance',
        'move_id.line_ids.full_reconcile_id',
        'state','amount','is_advance')
    def _compute_advance_amount_residual(self):
        """ """
        for pay in self:
            move = pay.move_id
            advance_amount_residual = 0
            if pay.is_advance:
                if pay.partner_type == 'customer':
                    advance_account = pay.company_id.l10n_ec_advance_account_receivable_id
                    if pay.partner_id.country_code != 'EC' and pay.company_id.l10n_ec_advance_account_foreign_receivable_id:
                        advance_account = pay.company_id.l10n_ec_advance_account_foreign_receivable_id
                else:
                    advance_account = pay.company_id.l10n_ec_advance_account_payable_id
                    if pay.partner_id.country_code != 'EC' and pay.company_id.l10n_ec_advance_account_foreign_payable_id:
                        advance_account = pay.company_id.l10n_ec_advance_account_foreign_payable_id

                for line in move.line_ids:

                    if line.account_id == advance_account and not line.reconciled:
                        advance_amount_residual += line.amount_residual

            pay.advance_amount_residual = abs(advance_amount_residual)


    def _prepare_move_line_default_vals(self, write_off_line_vals=None, force_balance=None):
        for rec in self:
            lines = super(AccountPayment, rec)._prepare_move_line_default_vals(
                write_off_line_vals=write_off_line_vals,
                force_balance=force_balance)
            for line in lines:
                line.update({
                    'l10n_ec_acquiring_bank_id': rec.l10n_ec_acquiring_bank_id and rec.l10n_ec_acquiring_bank_id.id or False,
                    'l10n_ec_lot': rec.l10n_ec_lot,
                    'l10n_ec_credit_auth': rec.l10n_ec_credit_auth,
                    'l10n_ec_credit_card_number': rec.l10n_ec_credit_card_number,
                    'l10n_ec_credit_card_ref': rec.l10n_ec_credit_card_ref,
                    'l10n_ec_credit_valid_card': rec.l10n_ec_credit_valid_card,
                    'l10n_ec_credit_card_type': rec.l10n_ec_credit_card_type,
                    'l10n_ec_credit_card_deferred_id': rec.l10n_ec_credit_card_deferred_id and rec.l10n_ec_credit_card_deferred_id.id or False
                })

            return lines

    @api.depends('journal_id', 'partner_id', 'partner_type', 'is_internal_transfer', 'destination_journal_id',
                 'is_advance')
    def _compute_destination_account_id(self):
        for pay in self:
            advance_account = False
            if pay.is_advance and not pay.is_internal_transfer and pay.partner_id:
                if pay.partner_type == 'customer':
                    advance_account = pay.company_id.l10n_ec_advance_account_receivable_id
                    if pay.partner_id.country_code != 'EC' and pay.company_id.l10n_ec_advance_account_foreign_receivable_id:
                        advance_account = pay.company_id.l10n_ec_advance_account_foreign_receivable_id
                else:
                    advance_account = pay.company_id.l10n_ec_advance_account_payable_id
                    if pay.partner_id.country_code != 'EC' and pay.company_id.l10n_ec_advance_account_foreign_payable_id:
                        advance_account = pay.company_id.l10n_ec_advance_account_foreign_payable_id

            if advance_account and pay.is_advance:
                pay.destination_account_id = advance_account
                #pay.is_internal_transfer = False
            else:
                #pay.is_advance = False
                super(AccountPayment, pay)._compute_destination_account_id()

    def _synchronize_from_moves(self, changed_fields):
        # EXTENDS account
        for rec in self:
            if rec.is_advance:
                # Constraints bypass when entry is linked to an expense.
                # Context is not enough, as we want to be able to delete
                # and update those entries later on.
                return
        super()._synchronize_from_moves(changed_fields)

    @api.onchange('is_internal_transfer')
    def _onchange_for_advance_is_internal_transfer(self):
        for rec in self:
            if rec.is_internal_transfer:
                rec.is_advance = False

    # @api.onchange('partner_id')
    # def _onchange_for_advance_partner_id(self):
    #     for rec in self:
    #         if not rec.partner_id:
    #             rec.is_advance = False

    @api.onchange('payment_type')
    def _onchange_for_advance_payment_type(self):
        for rec in self:
            if (rec.partner_type == 'customer' and rec.payment_type != 'inbound') or (rec.partner_type == 'supplier' and rec.payment_type != 'outbound'):
                rec.is_advance = False

    def action_post(self):
        # Do not allow to post if the account is required but not trusted
        for payment in self:
            if payment.is_internal_transfer and payment.is_advance:
                raise ValidationError(_('Una transfenrecia interna no puede ser marcada como anticipo'))
            if payment.is_advance and not payment.partner_id:
                raise ValidationError(_('No es posible definir un anticipo si indentificar el Cliente/Proveedor al que '
                                        'pertence.\n Por favor seleccionelo antes de confirimar'))
            if payment.is_advance and payment.amount <= 0:
                raise ValidationError(_('No es posible definir un anticipo con valor menor o igual a cero.'))


        return super().action_post()

    def action_open_manual_reconciliation_widget(self):
        self.ensure_one()
        if self.is_advance:
            action_values = self.env['ir.actions.act_window']._for_xml_id(
                'ek_l10n_ec.ek_account_invoice_for_payment_reconcile_action')
            if self.partner_id:
                context = ast.literal_eval(action_values['context'])
                context.update({'default_advance_payment_id': self.id})
                action_values['context'] = context
            return action_values
        else:
            return super().action_open_manual_reconciliation_widget()

    def has_check(self):
        return self.payment_method_id and self.payment_method_id.code in ['check_printing','new_third_party_checks','in_third_party_checks','out_third_party_checks']

    def amount_to_text(self, amount):
            """Convierte un número a texto en español"""
            UNIDADES = ['', 'uno', 'dos', 'tres', 'cuatro', 'cinco', 'seis', 'siete', 'ocho', 'nueve']
            DECENAS = ['', 'diez', 'veinte', 'treinta', 'cuarenta', 'cincuenta', 'sesenta', 'setenta', 'ochenta', 'noventa']
            DIEZ_A_VEINTE = ['diez', 'once', 'doce', 'trece', 'catorce', 'quince', 'dieciséis', 'diecisiete', 'dieciocho', 'diecinueve']
            CENTENAS = ['', 'ciento', 'doscientos', 'trescientos', 'cuatrocientos', 'quinientos', 'seiscientos', 'setecientos', 'ochocientos', 'novecientos']
            
            def _convert_number(n):
                if n == 0:
                    return 'cero'
                elif n < 10:
                    return UNIDADES[n]
                elif n < 20:
                    return DIEZ_A_VEINTE[n - 10]
                elif n < 100:
                    unidad = n % 10
                    decena = n // 10
                    if unidad == 0:
                        return DECENAS[decena]
                    else:
                        return DECENAS[decena] + ' y ' + UNIDADES[unidad]
                elif n < 1000:
                    centena = n // 100
                    resto = n % 100
                    if centena == 1 and resto == 0:
                        return 'cien'
                    elif resto == 0:
                        return CENTENAS[centena]
                    else:
                        return CENTENAS[centena] + ' ' + _convert_number(resto)
                elif n < 1000000:
                    miles = n // 1000
                    resto = n % 1000
                    if miles == 1:
                        text = 'mil'
                    else:
                        text = _convert_number(miles) + ' mil'
                    if resto > 0:
                        text += ' ' + _convert_number(resto)
                    return text
                
            # Separar parte entera y decimal
            amount_int = int(amount)
            decimal_part = int(round((amount - amount_int) * 100))
            
            # Convertir parte entera a texto
            text = _convert_number(amount_int)
            
            # Agregar parte decimal
            if decimal_part > 0:
                text += ' con %02d/100' % decimal_part
            else:
                text += ' con 00/100'
                
            return text.capitalize()
