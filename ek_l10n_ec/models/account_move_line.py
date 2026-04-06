# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import models, api, fields, _
from odoo.exceptions import ValidationError
from odoo.tools import frozendict


class AccountMoveLine(models.Model):
    _inherit = 'account.move.line'

    l10n_latam_document_type_id = fields.Many2one(
        related="move_id.l10n_latam_document_type_id",
        auto_join=True,
        store=True,
        index=True,
    )
    l10n_latam_price_unit = fields.Monetary(
        compute="compute_l10n_latam_prices_and_taxes",
    )
    l10n_latam_price_subtotal = fields.Monetary(
        compute="compute_l10n_latam_prices_and_taxes",
    )
    l10n_latam_price_net = fields.Monetary(
        compute="compute_l10n_latam_prices_and_taxes",
    )
    l10n_latam_tax_ids = fields.One2many(
        compute="compute_l10n_latam_prices_and_taxes",
        comodel_name="account.tax",
    )
    purchase_price = fields.Float(
        string="Costo",
        compute="_compute_purchase_price",
        groups="ek_l10n_ec.group_account_move_cost_security",
        store=True,
        readonly=False,
        digits="Product Price",
    )

    payment_mode_id = fields.Many2one(
        comodel_name="account.payment.mode",
        compute="_compute_payment_mode",
        store=True,
        ondelete="restrict",
        index=True,
        readonly=False,
    )

    invoice_user_id = fields.Many2one(
        related="move_id.invoice_user_id",
        auto_join=True,
        store=True,
        index=True,
    )

    l10n_ec_channel_id = fields.Many2one(
        string="Canal",
        comodel_name="ek.res.channel",
        auto_join=True,
        store=True,
        index=True,
        compute="_compute_l10n_ec_classification",
        readonly=False,

    )

    l10n_ec_classification_id = fields.Many2one(
        string="Clasificación",
        auto_join=True,
        store=True,
        index=True,
        compute="_compute_l10n_ec_classification",
        readonly=False,
        comodel_name="ek.classification",
    )

    l10n_ec_acquiring_bank_id = fields.Many2one(comodel_name="res.bank", string="Banco Adquiriente", required=False,
                                                help=u"Remite la respuesta de la autorización al merchant.",
                                                tracking=True)
    l10n_ec_lot = fields.Char(string="Lote", required=False, tracking=True)
    l10n_ec_credit_auth = fields.Char(string=u"Autorización", required=False, tracking=True)
    l10n_ec_credit_card_number = fields.Char('No. Tarjeta', size=16, help="Basta con los ultimos 4 digitos",
                                             tracking=True)
    l10n_ec_credit_card_ref = fields.Char('Referencia', tracking=True)
    l10n_ec_credit_valid_card = fields.Char('Validez',
                                            help=u"Debe Indicar hasta cuando es válida la tarjeta. Ejemplo: 02/2020",
                                            size=7, tracking=True)

    l10n_ec_credit_card_type = fields.Selection(string=u"Tipo de Transacción",
                                                selection=[('dif', 'Diferido'), ('normal', 'Corriente'), ],
                                                required=False,
                                                default="normal", tracking=True)

    l10n_ec_credit_card_deferred_id = fields.Many2one(
        comodel_name='ek.types.deferred.credit.card',
        string='Meses de Diferido', ondelete='restrict',
        required=False, tracking=True)

    @api.depends("move_id", "move_id.payment_mode_id")
    def _compute_payment_mode(self):
        for line in self:
            if line.move_id.is_invoice() and line.account_type in (
                    "asset_receivable",
                    "liability_payable",
            ):
                line.payment_mode_id = line.move_id.payment_mode_id
            else:
                line.payment_mode_id = False

    @api.depends("move_id", "move_id.partner_id")
    def _compute_l10n_ec_classification(self):
        for line in self:
            l10n_ec_classification = False
            l10n_ec_channel = False
            if line.partner_id:
                if line.partner_id.l10n_ec_classification_id:
                    l10n_ec_classification = line.partner_id.l10n_ec_classification_id.id
                if line.partner_id.l10n_ec_channel_id:
                    l10n_ec_channel = line.partner_id.l10n_ec_channel_id.id

            line.l10n_ec_classification_id = l10n_ec_classification
            line.l10n_ec_channel_id = l10n_ec_channel

    def write(self, vals):
        """Propagate up to the move the payment mode if applies."""
        if "payment_mode_id" in vals:
            for record in self:
                move = (
                        self.env["account.move"].browse(vals.get("move_id", 0))
                        or record.move_id
                )
                if (
                        move.payment_mode_id.id != vals["payment_mode_id"]
                        and move.is_invoice()
                ):
                    move.payment_mode_id = vals["payment_mode_id"]
        return super().write(vals)

    def _get_purchase_price(self):
        # Overwrite this function if you don't want to base your
        # purchase price on the product standard_price
        self.ensure_one()
        return self.product_id and self.product_id.standard_price or 0

    @api.depends("product_id", "product_uom_id")
    def _compute_purchase_price(self):
        for line in self:
            cost = 0.00
            if line.move_id.move_type in ["out_invoice", "out_refund"]:
                purchase_price = line._get_purchase_price()
                if line.product_uom_id != line.product_id.uom_id:
                    purchase_price = line.product_id.uom_id._compute_price(
                        purchase_price, line.product_uom_id
                    )
                move = line.move_id
                company = move.company_id or self.env.company
                cost = company.currency_id._convert(
                    purchase_price,
                    move.currency_id,
                    company,
                    move.invoice_date or fields.Date.today(),
                    round=False,
                )

            line.update({
                'purchase_price': cost
            })

    @api.depends('price_unit', 'price_subtotal', 'move_id.l10n_latam_document_type_id')
    def compute_l10n_latam_prices_and_taxes(self):
        for line in self:
            invoice = line.move_id
            included_taxes = \
                invoice.l10n_latam_document_type_id and invoice.l10n_latam_document_type_id._filter_taxes_included(
                    line.tax_ids)
            if not included_taxes:
                price_unit = line.tax_ids.with_context(round=False).compute_all(
                    line.price_unit, invoice.currency_id, 1.0, line.product_id, invoice.partner_id)
                l10n_latam_price_unit = price_unit['total_excluded']
                l10n_latam_price_subtotal = line.price_subtotal
                not_included_taxes = line.tax_ids
                l10n_latam_price_net = l10n_latam_price_unit * (1 - (line.discount or 0.0) / 100.0)
            else:
                not_included_taxes = line.tax_ids - included_taxes
                l10n_latam_price_unit = included_taxes.compute_all(
                    line.price_unit, invoice.currency_id, 1.0, line.product_id, invoice.partner_id)['total_included']
                l10n_latam_price_net = l10n_latam_price_unit * (1 - (line.discount or 0.0) / 100.0)
                price = line.price_unit * (1 - (line.discount or 0.0) / 100.0)
                l10n_latam_price_subtotal = included_taxes.compute_all(
                    price, invoice.currency_id, line.quantity, line.product_id,
                    invoice.partner_id)['total_included']

            line.l10n_latam_price_subtotal = l10n_latam_price_subtotal
            line.l10n_latam_price_unit = l10n_latam_price_unit
            line.l10n_latam_price_net = l10n_latam_price_net
            line.l10n_latam_tax_ids = not_included_taxes

    @api.constrains("analytic_distribution", "account_id", "debit", "credit")
    def _check_analytic_required(self):
        for rec in self:
            message = rec._check_analytic_required_msg()
            if message:
                raise ValidationError(message)

    def _check_analytic_required_msg(self):
        self.ensure_one()
        company_cur = self.company_currency_id
        if not company_cur or (company_cur.is_zero(self.debit) and company_cur.is_zero(self.credit)):
            return None
        analytic_policy = self.account_id._get_analytic_policy()
        if analytic_policy == "always" and not self.analytic_distribution:
            return _(
                "Analytic policy is set to 'Always' with account "
                "'%(account)s' but the analytic account is missing in "
                "the account move line with label '%(move)s'."
            ) % {
                "account": self.account_id.display_name,
                "move": self.name or "",
            }
        elif analytic_policy == "never" and (self.analytic_distribution):
            analytic_account = self.analytic_distribution
            analytic_acc_ids = [int(k) for k in analytic_account.keys()]
            analytic_accs = self.env["account.analytic.account"].browse(
                analytic_acc_ids
            )
            return _(
                "Analytic policy is set to 'Never' with account "
                "'%(account)s' but the account move line with label '%(move)s' "
                "has an analytic account '%(analytic_account)s'."
            ) % {
                "account": self.account_id.display_name,
                "move": self.name or "",
                "analytic_account": ", ".join(analytic_accs.mapped("name")),
            }
        elif (
                analytic_policy == "posted"
                and not self.analytic_distribution
                and self.move_id.state == "posted"
        ):
            return _(
                "Analytic policy is set to 'Posted moves' with "
                "account '%(account)s' but the analytic account is missing "
                "in the account move line with label '%(move)s'."
            ) % {
                "account": self.account_id.display_name,
                "move": self.name or "",
            }
        return None

    @api.depends('journal_id')
    def _compute_analytic_distribution(self):
        cache = {}
        for line in self:
            if line.display_type == 'product' or not line.move_id.is_invoice(include_receipts=True):
                if "journal_id" not in self.env['account.analytic.distribution.model']._fields:
                    super(AccountMoveLine, self)._compute_analytic_distribution()
                else:
                    arguments = frozendict({
                        "journal_id": line.journal_id.id,
                    })
                    
                    if arguments not in cache:
                        args_distribution = self.env['account.analytic.distribution.model']._get_distribution(arguments)
                        if not args_distribution:
                            super(AccountMoveLine, self)._compute_analytic_distribution()
                        cache[arguments] = args_distribution
                    line.analytic_distribution = cache[arguments] or line.analytic_distribution
