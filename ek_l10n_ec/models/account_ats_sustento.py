from odoo import fields, models, api


class AccountAtsSustento(models.Model):
    _name = "account.ats.sustento"
    _description = "Sustento del Comprobante"

    # TODO: He comentado este método porque no me funcionaba, seguía presentando en diplay_name un valor similar a account.ats.sustento, 1
    #  En su lugar, he hecho override al método _compute_display_name()
    # def name_get(self):
    #  return [(record.id, '%s - %s' % (record.code, record.type)) for record in self]

    code = fields.Char(
        string="Código",
        size=2,
        required=True,
    )
    type = fields.Char(
        string="Tipo de sustento",
        size=150,
        required=True,
    )
    account_ats_doc_ids = fields.Many2many(
        string="Tipos de comprobantes",
        comodel_name="l10n_latam.document.type",
        relation="account_ats_doc_rel",
        column1="account_ats_sustento_id",
        column2="account_ats_doc_id",
    )

    @api.depends("code", "type")
    def _compute_display_name(self):
        for rec in self:
            rec.display_name = "%s - %s" % (rec.code, rec.type)
