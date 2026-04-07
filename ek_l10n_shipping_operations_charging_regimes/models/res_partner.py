# -*- coding: utf-8 -*-
from odoo import models, fields, api


class ResPartner(models.Model):
    """
    Extensión de res.partner para agregar campo de markup de servicios marítimos
    REQ-027: Campo maritime_service_markup
    """
    _inherit = 'res.partner'

    maritime_service_markup = fields.Float(
        string="Markup Servicios Marítimos (%)",
        default=20.0,
        help="Porcentaje de markup aplicado a repuestos y servicios marítimos en órdenes de venta (Régimen 70)"
    )
