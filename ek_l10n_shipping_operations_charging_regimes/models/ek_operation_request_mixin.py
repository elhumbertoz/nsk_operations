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

    # Delegate to AI mixin methods by calling them directly
    def action_extract_bl_with_ai(self):
        """Extrae datos del Bill of Lading usando IA"""
        from . import ek_ai_extraction_mixin
        # Create a temporary mixin instance with our context
        mixin_methods = ek_ai_extraction_mixin.EkAIExtractionMixin()
        # Bind to our instance
        return mixin_methods.action_extract_bl_with_ai.__get__(self, type(self))()

    def action_extract_invoices_with_ai(self):
        """Extrae datos de facturas comerciales usando IA"""
        from . import ek_ai_extraction_mixin
        mixin_methods = ek_ai_extraction_mixin.EkAIExtractionMixin()
        return mixin_methods.action_extract_invoices_with_ai.__get__(self, type(self))()

    def action_extract_po_and_compare(self):
        """Extrae Nota de Pedido y compara con factura usando IA"""
        from . import ek_ai_extraction_mixin
        mixin_methods = ek_ai_extraction_mixin.EkAIExtractionMixin()
        return mixin_methods.action_extract_po_and_compare.__get__(self, type(self))()
