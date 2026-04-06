from odoo import api, fields, models
from odoo.tools.translate import _
from odoo.exceptions import ValidationError


class ResPartner(models.Model):
    _inherit = "res.partner"

    withholding_issues = fields.Boolean(
        string="Emite retenciones",
        required=False,
        help="Si el contacto tiene esta marca, el sistema verificará si tiene retenciones pendientes de emitir.\n"
             "Esta marca se coloca de forma automática cuando el contacto realiza la primera retención, o puede\n"
             "decidir colocarlo de forma manual en cualquier momento."
    )
    l10n_latam_document_sustento = fields.Many2one(
        string="Sustento tributario",
        comodel_name="account.ats.sustento",
        required=False,
        ondelete="restrict"
    )
    l10n_ec_sri_payment_id = fields.Many2one(
        string="Método de pago (SRI)",
        comodel_name="l10n_ec.sri.payment",
    )

    l10n_ec_max_day_for_receipt_invoices = fields.Integer(
        string='Máximo día de Facturación',
        default=0,
        help="Es el máximo dia dentro del mes que se le puede generar una factura a este cliente. Dejar en cero si no se necesita esta restricción",
        required=False)

    supplier_payment_mode_id = fields.Many2one(
        comodel_name="account.payment.mode",
        company_dependent=True,
        check_company=True,
        domain="[('payment_type', '=', 'outbound'),"
               "('company_id', '=', current_company_id)]",
        help="Select the default payment mode for this supplier.",
    )
    customer_payment_mode_id = fields.Many2one(
        comodel_name="account.payment.mode",
        company_dependent=True,
        check_company=True,
        domain="[('payment_type', '=', 'inbound'),"
               "('company_id', '=', current_company_id)]",
        help="Select the default payment mode for this customer.",
    )

    @api.model
    def _commercial_fields(self):
        res = super()._commercial_fields()
        res += ["supplier_payment_mode_id", "customer_payment_mode_id"]
        return res

    @api.constrains("l10n_ec_max_day_for_receipt_invoices")
    def check_l10n_ec_max_day_for_receipt_invoices(self):
        for rec in self:
            if rec.l10n_ec_max_day_for_receipt_invoices < 0 or rec.l10n_ec_max_day_for_receipt_invoices > 31:
                raise ValidationError("El máximo día de facturación no puede ser menor a 0 ni mayor que 31")

    @api.constrains("withholding_issues", "l10n_latam_identification_type_id")
    def check_withholding_issues(self):
        ruc_ref = self.env.ref("l10n_ec.ec_ruc", False)
        if ruc_ref and not self.env.context.get('validation_skip'):
            for rec in self:
                if rec.withholding_issues and not rec.l10n_latam_identification_type_id:
                    raise ValidationError(
                        "El contacto %s no puede emitir retenciones porque no tiene tipo de identificación" % rec.name)
                if rec.withholding_issues and rec.l10n_latam_identification_type_id != ruc_ref:
                    raise ValidationError(
                        "El contacto %s no puede emitir retenciones porque el tipo de identificación no es RUC." % rec.name)

    # No validar RUCs Sociedades Jurídicas (S.A.S.) ej: 1793189549001
    @api.constrains("vat", "country_id")
    def check_vat(self):
        partner_to_skip_validate = self.env["res.partner"]
        for partner in self:
            if (
                    partner.country_id.code == "EC"
                    and partner.vat
                    and len(partner.vat) == 13
                    and partner.vat[2] == "9"
            ):
                partner_to_skip_validate |= partner
        return super(ResPartner, self - partner_to_skip_validate).check_vat()

    def write(self, values):
        for partner in self:
            if (
                    partner.vat in ["9999999999", "9999999999999"]
                    and not self.env.is_system()
                    and (
                    "name" in values
                    or "vat" in values
                    or "active" in values
                    or "country_id" in values
            )
            ):
                raise ValidationError(_("No se puede modificar registro de consumidor final"))
        return super(ResPartner, self).write(values)

    def unlink(self):
        for partner in self:
            if partner.vat in ["9999999999", "9999999999999"]:
                raise ValidationError(_("No puede eliminar al Consumidor Final."))
        return super(ResPartner, self).unlink()
