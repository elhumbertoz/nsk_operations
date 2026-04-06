from odoo import _, fields, models, api
from odoo.exceptions import UserError

class GenerateCorrectionDocument(models.TransientModel):
    _name = "ek.generate.correction.document"
    _description = "Generate Correction Document"

    type_id = fields.Many2one(
        comodel_name="ek.l10n.type.model.mixin",
        string="Type",
        domain=[("is_correction_request", "=", True),('ir_form_view','!=',False)],
    )

    operation_request_id = fields.Many2one(
        comodel_name="ek.operation.request",
        string="Request"
    )
    



    def copy_request_self(self):
        self.env.context = self.env.context.copy()
        self.env.context['copy_request_self'] = True
        new_object = self.operation_request_id.copy()
        value = {
            "parent_id": self.operation_request_id.id,
            "type_id": self.type_id.id,
            "validate_correction_request": True,
            "has_confirmed_type": False,
            
        }
        if new_object and not (self.type_id.has_internal_sequence or self.type_id.internal_sequence) :
            #value_text_conta = new_object.compute_concatenated_field_date()
            #new_object.text_self_calculate = (new_object.need_extend_hours_text or '') + ' - ' + value_text_conta
            seq = self.env['ir.sequence'].search([('code', '=', 'ek.operation.request.sequence')], limit=1)
            new_object.name = seq.next_by_id()
        if new_object and self.type_id.has_internal_sequence and self.type_id.internal_sequence:
            value['name'] = self.type_id.internal_sequence.next_by_id()
        new_object.write(value)
        new_object.action_fill_pov_line(new_object.type_id, new_object.stage_id, "service")
        new_object.action_fill_pov_line(new_object.type_id, new_object.stage_id,'purchase')
        return {
            "name": _("Generate Correction Document"),
            "type": "ir.actions.act_window",
            "res_model": "ek.operation.request",
            "view_mode": "form",
            'res_id': new_object.id,
            "view_id": self.env.ref("ek_l10n_shipping_operations.ek_operation_request_form").id,
            #"target": "new",
        }
        

        