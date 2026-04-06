# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models
from odoo.tools.translate import _
from odoo.exceptions import ValidationError



class ResPartnerBank(models.Model):
    _inherit = "res.partner.bank"
    
    _ACCOUNT_TYPE = [
        ("savings", "Cuenta de ahorros"),
        ("checking", "Cuenta corriente"),
        ("credit_card", "Tarjeta de crédito"),
    ]
    
    l10n_ec_account_type = fields.Selection(
        selection=_ACCOUNT_TYPE,
        string="Tipo",
        default="checking",
        help="Seleccione el tipo de cuenta.",
    )

    l10n_ec_account_valid = fields.Char("Mes/Año", size=7,)

    l10n_ec_bank_authorized_network = fields.Many2many(
        comodel_name='res.bank',
        column1="partner_bank_id",
        column2="bank_id",
        relation="res_partner_bank_authorized_network_rel",
        string='Red Autorizada',
        required=False, help='Banco autorizado para realizar los débitos automáticos, dejar en blanco si todos los '
                             'bancos se encuentran autorizados o no se requiere autorización')

    @api.depends("acc_number")
    def _compute_acc_type(self):
        for bank in self:
            if bank.company_id.country_code == 'EC':
                bank.acc_type = bank.l10n_ec_account_type
            else:
                super(ResPartnerBank, self)._compute_acc_type()
    
    @api.model
    def _get_supported_account_types(self):
        rslt = super(ResPartnerBank, self)._get_supported_account_types()
        rslt.append(('savings', _("Cuenta de ahorros")))
        rslt.append(('checking', _("Cuenta Corriente")))
        rslt.append(('credit_card', _('Tarjeta de Crédito')))
        return rslt

    def get_monthyear(self):
        if self.l10n_ec_account_valid:
            month, year = self.l10n_ec_account_valid.split('/')

            return "%s%s" % (year,month)
        else:
            return ''

    @api.constrains("l10n_ec_account_type","l10n_ec_account_valid")
    def is_valid_credit_card(self):
        for rec in self:
            try:
                if rec.l10n_ec_account_type == 'credit_card' and rec.l10n_ec_account_valid:
                    month, year = rec.l10n_ec_account_valid.split('/')
                    if not month or not year:
                        raise ValidationError("El formato de la fecha de vencimiento no es correcto")
                    else:
                        _month = int(month)
                        _year = int(year)
                        str_date = "%s-%s-01" % (_year, _month)
                        credit_date = fields.Date.end_of(fields.Date.from_string(str_date), 'month')
                        today_date = fields.Date.today()
                        if credit_date <= today_date:
                            raise ValidationError("La fecha de vencimiento %s de la tarjeta de crédito es menor a la fecha de hoy" % fields.Date.to_string(credit_date))
            except:
                raise ValidationError("El formato de la fecha de vencimiento no es correcto")
