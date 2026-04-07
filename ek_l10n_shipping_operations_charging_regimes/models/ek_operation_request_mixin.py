# -*- coding: utf-8 -*-
"""
Mixin composition for ek.operation.request + AI extraction

This file exists separately to avoid Many2many field registration conflicts
that occur when list-style inheritance includes both a concrete model and a mixin.
"""
from odoo import api, fields, models


class EkOperationRequestMixinComposition(models.Model):
    """
    Composes ek.operation.request with ek.ai.extraction.mixin

    By doing this in a separate class definition, we avoid the TypeError:
    "Many2many fields ... use the same table and columns"
    """
    _inherit = 'ek.operation.request'

    # Delegate to the container methods if available
    def action_extract_bl_with_ai(self):
        """Redirige extracción al contenedor vinculado"""
        self.ensure_one()
        if self.container_id:
            return self.container_id.action_extract_bl_with_ai()
        raise UserError(_("Debe vincular un contenedor primero para realizar la extracción."))

    def action_extract_invoices_with_ai(self):
        """Redirige extracción al contenedor vinculado"""
        self.ensure_one()
        if self.container_id:
            return self.container_id.action_extract_invoices_with_ai()
        raise UserError(_("Debe vincular un contenedor primero para realizar la extracción."))

    def action_extract_po_and_compare(self):
        """Redirige validación al contenedor vinculado"""
        self.ensure_one()
        if self.container_id:
            return self.container_id.action_extract_po_and_compare()
        raise UserError(_("Debe vincular un contenedor primero para realizar la validación."))
