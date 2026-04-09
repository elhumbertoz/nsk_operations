# -*- coding: utf-8 -*-
from odoo import fields, models


class MailComposeMessage(models.TransientModel):
    _inherit = 'mail.compose.message'

    def _action_send_mail(self, auto_commit=False):
        """Después del envío real, si el contexto trae mark_sent_field, marca
        el flag correspondiente en el record de origen (ek.operation.request).
        Esto permite que los botones de notificación Régimen 70 oculten el
        botón una vez enviado, aun cuando el usuario envía vía el composer."""
        result = super()._action_send_mail(auto_commit=auto_commit)

        ctx = self.env.context
        mark_sent_field = ctx.get('mark_sent_field')
        mark_sent_model = ctx.get('mark_sent_model')
        mark_sent_res_id = ctx.get('mark_sent_res_id')
        chatter_body = ctx.get('mark_sent_chatter_body')

        if mark_sent_field and mark_sent_model and mark_sent_res_id:
            record = self.env[mark_sent_model].browse(mark_sent_res_id)
            if record.exists():
                vals = {mark_sent_field: True}
                date_field = f'{mark_sent_field}_date'
                if date_field in record._fields:
                    vals[date_field] = fields.Datetime.now()
                record.write(vals)
                if chatter_body:
                    record.message_post(body=chatter_body)

        return result
