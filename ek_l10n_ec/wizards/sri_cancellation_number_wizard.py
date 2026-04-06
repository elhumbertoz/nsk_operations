# © 2016 Akretion (<https://www.akretion.com>)
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).

from odoo import models, fields, _
from odoo.exceptions import UserError
from markupsafe import Markup

class sri_cancellation_number_wizard(models.TransientModel):
    _name = "sri.cancellation.number.wizard"
    _description = "Anulacion de documentos eletronicos"

    move_id = fields.Many2one(
        comodel_name='account.move',
        string='Move',
        required=False)

    code = fields.Char(
        string="Código de Anulación",
        size=11,
        required=True)

    def button_cancel_posted_moves(self):
        self.ensure_one()

        if not self.move_id:
            invocies = self.env["account.move"].browse(self._context["active_ids"])
        else:
            invocies = self.move_id

        if invocies.filtered(lambda a: a.state != 'posted'):
            raise UserError("Solo es posible anular documentos publicados")

        invocies.write({'l10n_ec_sri_cancellation_number': self.code})
        body = _("Código: %s",self.code)

        invocies.message_post(
            body=body,
            subject='Anulación de Documento Electrónico',
            message_type='comment',
            subtype_xmlid='mail.mt_comment')

        invocies.with_context(code_anulation_skip=True).button_cancel_posted_moves()
        invocies.button_process_edi_web_services()

