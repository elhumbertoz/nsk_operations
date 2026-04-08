from odoo import fields, models, api

class PurchaseOrder(models.Model):
    _name = "purchase.order"
    _inherit = ["purchase.order", "tier.validation","supplied.product.mixin"]
    _state_from = ["draft", "sent", "to approve"]
    _state_to = ["purchase", "approved"]

    _tier_validation_manual_config = False

    force_invoiced = fields.Boolean(
        copy=False,
        tracking=True,
        help="When you set this field, the purchase order will be "
        "considered as fully billed, even when there may be ordered "
        "or delivered quantities pending to bill. To use this field, "
        "the order must be in 'Locked' state",
    )

    is_user_id_editable = fields.Boolean(
        compute="_compute_is_user_id_editable",
    )
    invoice_method = fields.Selection(
        lambda r: r.env["product.template"]._fields["purchase_method"].selection
    )

    @api.depends("force_invoiced")
    def _get_invoiced(self):
        res = super()._get_invoiced()
        for order in self.filtered(
            lambda po: po.force_invoiced and po.invoice_status == "to invoice"
        ):
            order.invoice_status = "invoiced"
        return res
        

    def _compute_is_user_id_editable(self):
        is_user_id_editable = self.env.user.has_group(
            "purchase.group_purchase_manager"
        ) or not self.env.user.has_group("purchase_security.group_purchase_own_orders")
        self.write({"is_user_id_editable": is_user_id_editable})

    def _get_under_validation_exceptions(self):
        """Extend for more field exceptions."""
        field = super()._get_under_validation_exceptions()
        return field + ["is_user_id_editable"]

    def _prepare_invoice(self):
        self.ensure_one()
        invoice_vals = super()._prepare_invoice()
        invoice_vals["use_only_supplied_product"] = self.use_only_supplied_product

        # Fallback to partner defaults if missing on PO
        if not invoice_vals.get('invoice_payment_term_id') and self.partner_id.property_supplier_payment_term_id:
             invoice_vals['invoice_payment_term_id'] = self.partner_id.property_supplier_payment_term_id.id

        if self.partner_id:
            if not invoice_vals.get('l10n_latam_document_sustento') and self.partner_id.l10n_latam_document_sustento:
                 invoice_vals['l10n_latam_document_sustento'] = self.partner_id.l10n_latam_document_sustento.id
            if not invoice_vals.get('l10n_ec_sri_payment_id') and self.partner_id.l10n_ec_sri_payment_id:
                 invoice_vals['l10n_ec_sri_payment_id'] = self.partner_id.l10n_ec_sri_payment_id.id

        # Dummy values to allow saving before XML import (will be overwritten by XML)
        if not invoice_vals.get('l10n_latam_document_number'):
            invoice_vals['l10n_latam_document_number'] = '000-000-000000001'
        if not invoice_vals.get('l10n_ec_authorization_number'):
            invoice_vals['l10n_ec_authorization_number'] = '9999999999'

        return invoice_vals


class PurchaseOrderLine(models.Model):
    _inherit = "purchase.order.line"

    @api.depends(
        "invoice_lines.move_id.state",
        "invoice_lines.quantity",
        "qty_received",
        "product_uom_qty",
        "order_id.state",
        "order_id.invoice_method",
    )
    def _compute_qty_invoiced(self):
        ret = super()._compute_qty_invoiced()
        for line in self.filtered(
                lambda r: r.order_id.invoice_method
                          and r.order_id.state in ["purchase", "done"]
        ):
            if line.order_id.invoice_method == "purchase":
                line.qty_to_invoice = line.product_qty - line.qty_invoiced
            elif line.order_id.invoice_method == "receive":
                line.qty_to_invoice = line.qty_received - line.qty_invoiced
        return ret

    def _find_candidate(
        self,
        product_id,
        product_qty,
        product_uom,
        location_id,
        name,
        origin,
        company_id,
        values,
    ):
        """If not grouping by line, we should make an exception when you update an
        existing sales order line, so we filter a bit more by procurement group.

        NOTE: This makes that if you manually assign the same procurement group to
        several different sales orders, the grouping will be done no matter the grouping
        criteria, but this is the only way to do it without having to put a lot of glue
        modules, and on standard operation mode, procurement groups are not reused
        between sales orders.
        """
        if values.get("grouping") == "line":
            self = self.filtered(
                lambda x: x.order_id.group_id == values.get("group_id")
            )
        return super()._find_candidate(
            product_id,
            product_qty,
            product_uom,
            location_id,
            name,
            origin,
            company_id,
            values,
        )