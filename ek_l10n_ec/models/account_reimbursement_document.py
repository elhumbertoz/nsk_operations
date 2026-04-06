from odoo import fields, models, api
from odoo.exceptions import ValidationError


class AccountReimbursementDocument(models.Model):
    _name = "account.reimbursement.document"
    _description = "Documento de reembolso de gastos"

    invoice_id = fields.Many2one(
        string="Factura relacionada",
        comodel_name="account.move",
        required=False,
    )
    document_type_id = fields.Many2one(
        string="Tipo de comprobante",
        comodel_name="l10n_latam.document.type",
        required=True,
    )
    partner_id = fields.Many2one(
        string="Proveedor de Reembolso",
        comodel_name="res.partner",
        required=False,
    )
    tax_id = fields.Many2one(
        string="Impuesto Tarifa",
        comodel_name="account.tax",
        help="Impuesto Tarifa",
    )
    identification_type_id = fields.Many2one(
        string="Tipo de identificación",
        comodel_name="l10n_latam.identification.type",
        required=False,
    )
    # tpIdProvReemb = fields.Selection(string="Tipo de Identificación",required=True, selection=[('01', 'RUC'), ('02', 'CEDULA'),('03','PASAPORTE / IDENTIFICACIÓN TRIBUTARIA DEL EXTERIOR') ])
    identification_id = fields.Char(
        string="Identificación",
        size=13,
        required=False,
        help="Identificación o Registro Único de Contribuyentes (Cédula, Pasaporte, RUC, Identificación del Exterior)",
    )
    serie_entidad = fields.Char(
        string="Código de establecimiento",
        size=3,
        required=True,
    )
    serie_emision = fields.Char(
        string="Punto de emisión",
        size=3,
        required=True,
    )
    autorizacionReemb = fields.Char(
        string="Autorización",
        size=49,
        required=True,
    )
    num_secuencial = fields.Char(
        string="Secuencial",
        required=True,
        size=9,
    )
    fechaEmisionReemb = fields.Date(
        string="Fecha de emisión",
        required=True,
    )
    baseImponibleReemb = fields.Float(
        string="Tarifa 0% IVA",
        digits="Account",
        help="Base Imponible tarifa 0% IVA Reembolso ",
        required=True,
    )
    baseImpGravReemb = fields.Float(
        string="Tarifa IVA diferente de 0%",
        digits="Account",
        help="Base Imponible tarifa IVA diferente de 0% Reembolso",
        required=True,
    )
    baseNoGraIvaReemb = fields.Float(
        string="No objeto de IVA",
        digits="Account",
        help="Base Imponible no objeto de IVA - REEMBOLSO",
        required=True,
    )
    baseImpExeReemb = fields.Float(
        string="Exenta de IVA",
        digits="Account",
        help="Base imponible exenta de IVA Reembolso",
        required=True,
    )
    montoIceRemb = fields.Float(
        string="ICE",
        digits="Account",
        help="Monto ICE Reembolso",
        required=True,
    )
    montoIvaRemb = fields.Float(
        string="IVA",
        digits="Account",
        help="Monto IVA Reembolso",
        required=True,
    )

    @api.constrains("serie_entidad", "serie_emision", "num_secuencial")
    def _check_document_number(self):
        if not self._check_number_doc():
            raise ValidationError("El número del comprobante es incorrecto.")

    @api.onchange('num_secuencial')
    def check_num_secuencial(self):
        if self.num_secuencial and len(self.num_secuencial) != 9:  # noqa
            self.num_secuencial = self.num_secuencial.zfill(9)  # noqa

    @api.onchange('partner_id')
    def _onchange_partner_id(self):
        if self.partner_id:
            self.identification_id = self.partner_id.vat
            self.identification_type_id = self.partner_id.l10n_latam_identification_type_id

    # TODO: Consideré ponerle el nombre en inglés, pero no estaba seguro si se usa en otros lados o se llama desde alguna API
    def __validar_ced_ruc(self, nro, tipo):
        total = 0
        # TODO: He agregado d_ver = 0, base = 1, multip = () porque si el tipo no es 0, 1 ni 2, estos campos no existirían provocando un error.
        d_ver = 0
        base = 1
        multip = ()
        if tipo == 0:  # Cédula y RUC de persona natural
            base = 10
            d_ver = int(nro[9])  # Dígito verificador
            multip = (2, 1, 2, 1, 2, 1, 2, 1, 2)
        elif tipo == 1:  # RUC público
            base = 11
            d_ver = int(nro[8])
            multip = (3, 2, 7, 6, 5, 4, 3, 2)
        elif tipo == 2:  # RUC jurídico y extranjeros sin cédula
            base = 11
            d_ver = int(nro[9])
            multip = (4, 3, 2, 7, 6, 5, 4, 3, 2)
        for i in range(0, len(multip)):
            p = int(nro[i]) * multip[i]
            if tipo == 0:
                total += p if p < 10 else int(str(p)[0]) + int(str(p)[1])
            else:
                total += p
        mod = total % base
        val = base - mod if mod != 0 else 0
        return val == d_ver

    # TODO: Consideré ponerle el nombre en inglés, pero no estaba seguro si se usa en otros lados o se llama desde alguna API
    def verificar(self, nro):
        l = len(nro)
        if l == 10 or l == 13:  # Verificar longitud correcta
            cp = int(nro[0:2])
            cp_nuevas = int(nro[0:1])
            if 1 <= cp <= 22 or 1 <= cp_nuevas <= 22:  # Verificar código de provincia
                tercer_dig = int(nro[2])
                if 0 <= tercer_dig < 6:  # Números enteros 0 y 6
                    if l == 10:
                        valid = self.__validar_ced_ruc(nro, 0)
                        if not valid:
                            raise ValidationError(
                                "El número de identificación [%s] no es correcto o no coincide con el tipo de identificación seleccionado." % nro
                            )
                        return True
                    elif l == 13:
                        valid = self.__validar_ced_ruc(nro, 0) and nro[10:13] != '000'  # Verificar que últimos números no sean 000
                        if not valid:
                            raise ValidationError(
                                "El número de identificación [%s] no es correcto o no coincide con el tipo de identificación seleccionado." % nro
                            )
                        return True
                elif tercer_dig == 6:
                    valid = self.__validar_ced_ruc(nro, 1)  # Sociedades públicas
                    if not valid:
                        raise ValidationError(
                            "El número de identificación [%s] no es correcto o no coincide con el tipo de identificación seleccionado." % nro
                        )
                    return True
                elif tercer_dig == 9:  # si es ruc
                    valid = self.__validar_ced_ruc(nro, 2)  # Sociedades privadas
                    if not valid:
                        raise ValidationError(
                            "El número de identificación [%s] no es correcto o no coincide con el tipo de identificación seleccionado." % nro
                        )
                    return True
                else:
                    raise ValidationError("Tercer digito inválido.")
            else:
                raise ValidationError("Código de provincia incorrecto.")
        else:
            raise ValidationError("Longitud incorrecta del número ingresado.")

    def _check_identification_id(self, cr, uid, ids):
        reimbursements = self.browse(cr, uid, ids)
        for reimbursement in reimbursements:
            if not reimbursement.identification_id or (reimbursement.tpIdProvReemb != "01" and reimbursement.tpIdProvReemb != "02"):
                return True
            if reimbursement.tpIdProvReemb == "01" and len(reimbursement.identification_id) != 13:
                raise ValidationError(
                    "El número de identificación [%s] no es correcto o no coincide con el tipo de identificación seleccionado." %
                    reimbursement.identification_id
                )
            if reimbursement.tpIdProvReemb == "02" and len(reimbursement.identification_id) != 10:
                raise ValidationError(
                    "El número de identificación [%s] no es correcto o no coincide con el tipo de identificación seleccionado." %
                    reimbursement.identification_id
                )
            return self.verificar(reimbursement.identification_id)

    def _check_number_doc(self):
        for reimbursement in self:
            if len(reimbursement.serie_entidad) != 3 or len(reimbursement.serie_emision) != 3 or len(reimbursement.num_secuencial) != 9:
                return False
        return True
