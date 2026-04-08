# -*- coding: utf-8 -*-
from odoo import models, fields, api


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    # Categoría por defecto para productos Régimen 70
    regime_70_product_category_id = fields.Many2one(
        'product.category',
        string='Categoría Productos Régimen 70',
        config_parameter='ek_l10n_shipping_operations_charging_regimes.regime_70_product_category_id',
        default=lambda self: self.env.ref(
            'ek_l10n_shipping_operations_charging_regimes.product_category_regime_70',
            raise_if_not_found=False
        ),
        help='Categoría que se asignará automáticamente a los productos creados en operaciones de Régimen 70'
    )

    # Tipo de producto por defecto (consumible)
    regime_70_product_type = fields.Selection([
        ('consu', 'Consumible'),
        ('product', 'Almacenable'),
        ('service', 'Servicio'),
    ],
        string='Tipo Producto Régimen 70',
        default='consu',
        config_parameter='ek_l10n_shipping_operations_charging_regimes.regime_70_product_type',
        help='Tipo de producto por defecto para Régimen 70. Recomendado: Consumible (no afecta inventario)'
    )

    # Auto-crear productos
    regime_70_auto_create_products = fields.Boolean(
        string='Auto-crear Productos',
        default=True,
        config_parameter='ek_l10n_shipping_operations_charging_regimes.regime_70_auto_create_products',
        help='Si está activo, se crearán automáticamente productos cuando no existan en el catálogo'
    )

    # Umbral de similitud para matching
    regime_70_similarity_threshold = fields.Float(
        string='Umbral Similitud (%)',
        default=85.0,
        config_parameter='ek_l10n_shipping_operations_charging_regimes.regime_70_similarity_threshold',
        help='Porcentaje mínimo de similitud para considerar un producto como coincidencia (0-100)'
    )

    # Markup por defecto
    regime_70_default_markup = fields.Float(
        string='Markup por Defecto (%)',
        default=20.0,
        config_parameter='ek_l10n_shipping_operations_charging_regimes.regime_70_default_markup',
        help='Porcentaje de markup aplicado al costo para calcular precio de venta'
    )