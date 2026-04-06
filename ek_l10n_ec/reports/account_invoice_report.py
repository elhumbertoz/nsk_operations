
from odoo import fields, models


class AccountInvoiceReport(models.Model):
    _inherit = "account.invoice.report"

    l10n_latam_document_sustento = fields.Many2one(
        string="Sustento tributario",
        comodel_name="account.ats.sustento",
        readonly=True
    )
    l10n_latam_amount_untaxed_zero = fields.Float(
        string="Base 0%", readonly=True,

    )
    l10n_latam_amount_untaxed_not_charged_vat = fields.Float(
        string="No objeto de IVA", readonly=True,

    )
    l10n_latam_amount_untaxed_exempt_vat = fields.Float(
        string="Exento de IVA", readonly=True,

    )
    l10n_latam_amount_untaxed_not_zero = fields.Float(
        string="Base distinta de 0%", readonly=True,

    )
    l10n_latam_amount_vat = fields.Float(
        string="IVA", readonly=True,

    )

    l10n_ec_credit_days = fields.Integer(
        string="Días de Crédito",
        readonly=True,
    )

    payment_mode_id = fields.Many2one(
        comodel_name="account.payment.mode",
        string="Payment mode",
        readonly=True,
    )

    discount = fields.Float('Discount', readonly=True,
                            help="Specify the discount.")

    l10n_ec_city_id = fields.Many2one(
        string="Ciudad",
        comodel_name="ek.res.country.city",
        required=False,
    )
    l10n_ec_canton_id = fields.Many2one(
        string="Parroquia",
        comodel_name="ek.res.country.canton",
        required=False,
    )
    l10n_ec_sector_id = fields.Many2one(
        string="Sector",
        comodel_name="ek.res.sector",
        required=False,
    )
    l10n_ec_region_id = fields.Many2one(
        string="Región",
        comodel_name="ek.res.region",
        required=False,
    )
    l10n_ec_zone_id = fields.Many2one(
        string="Zona",
        comodel_name="ek.res.state.zone",
        required=False,
    )
    l10n_ec_route_dst_id = fields.Many2one(
        string="Ruta",
        comodel_name="ek.res.route",
        required=False,
    )
    l10n_ec_classification_id = fields.Many2one(
        string="Clasificación",
        comodel_name="ek.classification",
        required=False,
    )
    l10n_ec_channel_id = fields.Many2one(
        string="Canal",
        comodel_name="ek.res.channel",
        required=False,
    )
    l10n_ec_rank_id = fields.Many2one(
        string="Ranking",
        comodel_name="ek.res.customer.rank",
        required=False,
    )
    def _select(self):
        select_str = super()._select()
        select_str += """
            , move.l10n_latam_document_sustento as l10n_latam_document_sustento
            , move.l10n_latam_amount_untaxed_zero as l10n_latam_amount_untaxed_zero
            , move.l10n_latam_amount_untaxed_not_charged_vat as l10n_latam_amount_untaxed_not_charged_vat
            , move.l10n_latam_amount_untaxed_exempt_vat as l10n_latam_amount_untaxed_exempt_vat
            , move.l10n_latam_amount_untaxed_not_zero as l10n_latam_amount_untaxed_not_zero
            , move.l10n_latam_amount_vat as l10n_latam_amount_vat
            , move.l10n_ec_credit_days as l10n_ec_credit_days            
            , move.payment_mode_id AS payment_mode_id
            , line.discount AS discount 
            , partner.l10n_ec_city_id AS l10n_ec_city_id
            , partner.l10n_ec_canton_id AS l10n_ec_canton_id
            , partner.l10n_ec_sector_id AS l10n_ec_sector_id
            , partner.l10n_ec_region_id AS l10n_ec_region_id
            , partner.l10n_ec_zone_id AS l10n_ec_zone_id
            , partner.l10n_ec_route_dst_id AS l10n_ec_route_dst_id
            , partner.l10n_ec_classification_id AS l10n_ec_classification_id
            , partner.l10n_ec_channel_id AS l10n_ec_channel_id
            , partner.l10n_ec_rank_id AS l10n_ec_rank_id"""
        return select_str
