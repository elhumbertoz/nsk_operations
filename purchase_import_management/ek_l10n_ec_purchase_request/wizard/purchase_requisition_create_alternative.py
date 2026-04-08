from odoo import fields, models, api,Command

class PurchaseRequisitionCreateAlternative(models.TransientModel):
    _inherit = 'purchase.requisition.create.alternative'

    @api.model
    def _get_alternative_line_value(self, order_line):
        res_line = super()._get_alternative_line_value(order_line)
        if order_line.purchase_request_lines:
            res_line['purchase_request_lines'] = [(4,request_line.id) for request_line in order_line.purchase_request_lines if request_line.request_state == 'approved']
        if order_line.purchase_request_allocation_ids:
            res_line['purchase_request_allocation_ids'] = [Command.create(self._create_request_allocation_alternative(allocation)) for allocation in order_line.purchase_request_allocation_ids]


        return res_line

    def _create_request_allocation_alternative(self,allocation):
        return {
            'purchase_request_line_id': allocation.purchase_request_line_id.id,
            'product_id': allocation.product_id.id,
            'allocated_product_qty': allocation.allocated_product_qty,
            'requested_product_uom_qty': allocation.requested_product_uom_qty
        }
