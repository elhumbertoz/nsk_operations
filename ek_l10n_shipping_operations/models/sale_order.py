from odoo import fields, models, api
import base64


class SaleOrder(models.Model):
    _inherit = "sale.order"

    ek_ship_registration_id = fields.Many2one("ek.ship.registration",     tracking=True,
string="Shipper")
    journey_crew_id = fields.Many2one(
        "ek.boats.information",
        string="Journey",
            tracking=True,
        domain="[('ship_name_id','=',ek_ship_registration_id),('state','in',['draft','process','done'])]",
    )
    operation_request_id = fields.Many2one("ek.operation.request",    tracking=True)


    processing_status= fields.Many2one(
        related='operation_request_id.stage_id', string="Processing Status")
    
    creation_status = fields.Many2one(
        "ek.l10n.stages.mixin", string="Creation Status")


    purchase_order_id = fields.Many2one("purchase.order", string="Purchase Order")



    def _prepare_invoice(self):
        res = super(SaleOrder, self)._prepare_invoice()
        res.update(
            {
                "journey_crew_id": self.journey_crew_id.id,
                "ship_name_id": self.ek_ship_registration_id.id,
                "operation_request_id": self.operation_request_id.id,
            }
        )
        return res


class SaleOrderLine(models.Model):
    _inherit = "sale.order.line"

    # Campo para seguimiento de reembolsos
    reimbursement_tracking_id = fields.Many2one(
        'ek.reimbursement.tracking', 
        string='Seguimiento de Reembolso'
    )

    def _prepare_invoice_line(self, **optional_values):
        values = super(SaleOrderLine, self)._prepare_invoice_line(**optional_values)
        values.update(
            {
                "journey_crew_id": self.order_id.journey_crew_id.id,
                "ship_name_id": self.order_id.ek_ship_registration_id.id,
                "reimbursement_tracking_id": self.reimbursement_tracking_id.id if self.reimbursement_tracking_id else False,
            }
        )

        return values

class PurchaseOrderLine(models.Model):
    _inherit = 'purchase.order.line'

    # Campo para seguimiento de reembolsos
    reimbursement_tracking_id = fields.Many2one(
        'ek.reimbursement.tracking', 
        string='Seguimiento de Reembolso'
    )

    @api.model_create_multi
    def create(self, vals_list):
        """Override create para actualizar seguimiento cuando se crean líneas con operation_request_id"""
        lines = super().create(vals_list)
        
        # Verificar si alguna línea pertenece a una PO con operation_request_id
        pos_to_update = set()
        for line in lines:
            if line.order_id.operation_request_id:
                pos_to_update.add(line.order_id)
        
        # Actualizar seguimiento para cada PO única
        for po in pos_to_update:
            po._update_reimbursement_tracking()
        
        return lines


class PurchaseOrder(models.Model):
    _inherit = "purchase.order"

    journey_crew_id = fields.Many2one(
        "ek.boats.information",
        string="Journey",
            tracking=True,

        domain="[('ship_name_id','=',ek_ship_registration_id),('state','in',['draft','process','done'])]",
        
    )

    
    operation_request_id = fields.Many2one("ek.operation.request",
        tracking=True, string="Operation Request")

    ek_ship_registration_id = fields.Many2one("ek.ship.registration", 
        tracking=True,string="Shipper")

    
    processing_status= fields.Many2one(
        related='operation_request_id.stage_id', string="Processing Status")
    
    creation_status = fields.Many2one(
    "ek.l10n.stages.mixin", string="Creation Status")

    sale_order_id = fields.Many2one("sale.order", string="Sale Order")
        

    def _prepare_invoice(self):
        invoice_vals = super(PurchaseOrder, self)._prepare_invoice()
        
        invoice_vals.update({
            'operation_request_id': self.operation_request_id.id,
            'journey_crew_id': self.journey_crew_id.id,
            'ship_name_id': self.ek_ship_registration_id.id,
        })
        
        return invoice_vals

    @api.model_create_multi
    def create(self, vals_list):
        """Override create para actualizar seguimiento cuando se crea PO con solicitud"""
        orders = super().create(vals_list)
        
        for order in orders:
            if order.operation_request_id:
                order._update_reimbursement_tracking()
        
        return orders

    def write(self, vals):
        """Override write para actualizar seguimiento de reembolsos"""
        res = super().write(vals)
        if self.operation_request_id:
            # Actualizar cuando cambia el estado
            if 'state' in vals:
                self._update_reimbursement_tracking()
            # También actualizar cuando se agregan líneas de productos
            elif 'order_line' in vals:
                self._update_reimbursement_tracking()
        return res

    def unlink(self):
        """Override unlink para actualizar seguimiento cuando se elimina PO"""
        if self.operation_request_id:
            # Actualizar seguimiento antes de eliminar
            self._update_reimbursement_tracking_on_deletion()
        return super().unlink()

    def _update_reimbursement_tracking(self):
        """Actualizar estado de seguimiento de reembolsos según estado de PO"""
        # Obtener líneas con seguimiento de reembolso
        lines_with_tracking = self.order_line.filtered('reimbursement_tracking_id')
        
        if not lines_with_tracking:
            return
        
        for line in lines_with_tracking:
            tracking = line.reimbursement_tracking_id
            if self.state == 'purchase':
                tracking.sudo().write({
                    'state': 'purchase_confirmed',
                    'purchase_order_id': self.id
                })
            elif self.state == 'draft':
                tracking.sudo().write({
                    'state': 'purchase_pending',
                    'purchase_order_id': self.id
                })
            elif self.state == 'cancel':
                tracking.sudo().write({
                    'state': 'cancelled',
                    'purchase_order_id': False
                })

    def _update_reimbursement_tracking_on_deletion(self):
        """Actualizar seguimiento cuando se elimina la orden de compra"""
        import logging
        _logger = logging.getLogger(__name__)
        _logger.info(f'PO_DELETION_DEBUG: Updating tracking for deleted PO {self.id}')
        
        # Obtener líneas con seguimiento de reembolso
        lines_with_tracking = self.order_line.filtered('reimbursement_tracking_id')
        
        for line in lines_with_tracking:
            tracking = line.reimbursement_tracking_id
            _logger.info(f'PO_DELETION_DEBUG: Updating tracking {tracking.id} - current state: {tracking.state}')
            
            # Usar el método de reversión para determinar el estado correcto
            correct_state = tracking._determine_correct_state_with_reversal(
                removed_document_type='purchase_order',
                removed_document_id=self.id
            )
            
            _logger.info(f'PO_DELETION_DEBUG: Correct state for tracking {tracking.id}: {correct_state}')
            
            if correct_state != tracking.state:
                _logger.info(f'PO_DELETION_DEBUG: Updating tracking {tracking.id} from {tracking.state} to {correct_state}')
                tracking.sudo().write({
                    'state': correct_state,
                    'purchase_order_id': False
                })
            else:
                _logger.info(f'PO_DELETION_DEBUG: Tracking {tracking.id} already in correct state: {correct_state}')


class PurchaseOrderLine(models.Model):
    _inherit = 'purchase.order.line'


    def _prepare_account_move_line(self, move=False):
        aml_vals = super(PurchaseOrderLine, self)._prepare_account_move_line(move)
        
        aml_vals.update({
                "journey_crew_id": self.order_id.journey_crew_id.id,
                "ship_name_id": self.order_id.ek_ship_registration_id.id,
                "reimbursement_tracking_id": self.reimbursement_tracking_id.id if self.reimbursement_tracking_id else False,
        })
        
        return aml_vals
