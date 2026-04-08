# -*- coding: utf-8 -*-
from odoo import models, fields, api


class ProductProduct(models.Model):
    _inherit = 'product.product'

    @api.model
    def create(self, vals):
        """
        Override create para asignar código automático a productos de Régimen 70
        si no tienen default_code y pertenecen a la categoría Régimen 70
        """
        # Obtener categoría Régimen 70
        regime_70_category = self.env.ref(
            'ek_l10n_shipping_operations_charging_regimes.product_category_regime_70',
            raise_if_not_found=False
        )

        # Si no tiene código y es categoría Régimen 70, generar uno automático
        if not vals.get('default_code') and regime_70_category:
            categ_id = vals.get('categ_id')

            # Verificar si es categoría Régimen 70
            if categ_id == regime_70_category.id:
                # Generar código secuencial REG70-XXXX
                vals['default_code'] = self.env['ir.sequence'].next_by_code('product.regime.70') or 'REG70-0001'

        return super(ProductProduct, self).create(vals)
