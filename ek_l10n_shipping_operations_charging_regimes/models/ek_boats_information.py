# -*- coding: utf-8 -*-
import logging

from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError

_logger = logging.getLogger(__name__)


class EkBoatsInformation(models.Model):
    _name = 'ek.boats.information'
    _inherit = ['ek.boats.information', 'ek.ai.extraction.mixin']

    


    ref_container = fields.Char("Ref. Container")
    ek_produc_packages_goods_ids = fields.One2many("ek.product.packagens.goods","ek_boats_information_id", string="Product Packagens Goods", copy=True)

    value_of_container = fields.Float("Value of Container",compute="_compute_value_of_container",store=True, index=True)

    @api.depends("ek_produc_packages_goods_ids.quantity_hand","ek_produc_packages_goods_ids.delivery_product","ek_produc_packages_goods_ids")
    def _compute_value_of_container(self):
        for rec in self:
            rec.value_of_container = sum(rec.mapped("ek_produc_packages_goods_ids.quantity_hand")) 



    
    #Containers from regimens 70 and 60
    # state = fields.Selection(
    #     selection_add=[
    #         ("anotification", "Arrival Notification"),
    #         ("inspection", "Inspection/Capacity"),
    #         ("transfer", "Transfer"),
    #         ("desconsolidation", "Desconsolidation"),
    #         ("return", "Return Container"),
    #     ],
    #     ondelete={
    #         "draft": "cascade",
    #     }, tracking=True
    # )

    has_process_travel = fields.Boolean("Has Process Travel", default=False)

    type_move_container = fields.Selection(
        selection=[
            ("maritime", "Maritime"),
            ("aerial", "Aerial"),
            ("land", "Land"),
        ],
        string="Type of Transport", tracking=True
    )

    shipper_id = fields.Many2one(
        string="Shipper ",
        comodel_name="res.partner",
        required=False, tracking=True
    )
    shipping_company = fields.Many2one(
        string="Shipping Company",
        comodel_name="res.partner",
        required=False, tracking=True
    )
    custom_agent = fields.Many2one(
        string="Custom Agent",
        comodel_name="res.partner",
        required=False, tracking=True
    )

    load_number = fields.Char("Load Number", default=_("CONTAINER #"))
    supplies_detail = fields.Char("Supplies Detail", tracking=True)
    container_number = fields.Char("Container Number", tracking=True)
    bl_number = fields.Char("# AWB O BL", tracking=True)
    
    supplier_ids = fields.Many2many(
        comodel_name='res.partner',
        string='Suppliers', relation="res_partner_ek_boats_information_rel",
        column1='partner_id', column2='ek_boats_information_id', tracking=True)

    type_container_id = fields.Many2one("ek.type.container", string="Type Container", tracking=True)

    notes = fields.Text("Notes", tracking=True)

    rcd = fields.Datetime(string="Return Container Date", copy=False, tracking=True)

    # Campos de IA (Redefinidos para evitar conflictos de M2M y asegurar persistencia)
    bl_attachment_ids = fields.Many2many(
        'ir.attachment',
        'ek_container_bl_attachment_rel', # Tabla única para este modelo
        'container_id',
        'attachment_id',
        string='Bill of Lading (PDF)',
        help='Adjunte el documento BL para extracción automática con IA'
    )

    bl_attachment_filename = fields.Char(
        string="Nombre del archivo BL",
        compute='_compute_bl_attachment_filename'
    )

    invoice_attachment_ids = fields.Many2many(
        'ir.attachment',
        'ek_container_invoice_attachment_rel', # Tabla única para este modelo
        'container_id',
        'attachment_id',
        string='Facturas Comerciales',
        help='Adjunte las facturas comerciales para extracción automática'
    )

    purchase_order_attachment_ids = fields.Many2many(
        'ir.attachment',
        'ek_container_po_attachment_rel', # Tabla única para este modelo
        'container_id',
        'attachment_id',
        string="Nota de Pedido (PO)",
        help="Documento proporcionado por el agente aduanero para validación"
    )

    purchase_order_data = fields.Text(
        string="Datos Nota de Pedido",
        help="JSON con datos extraídos de la Nota de Pedido"
    )

    @api.depends('bl_attachment_ids')
    def _compute_bl_attachment_filename(self):
        for record in self:
            record.bl_attachment_filename = record.bl_attachment_ids[0].name if record.bl_attachment_ids else False

    # Aliases de campos para compatibilidad con el Mixin
    id_bl = fields.Char(related="bl_number", readonly=False, store=True)

    def action_create_operation_request(self):
        """
        Crea una solicitud de operación (Régimen 70) a partir de los datos 
        del contenedor (ya extraídos con IA).
        """
        self.ensure_one()
        
        # Buscar tipo de operación predeterminado para Régimen 70
        operation_type = self.env['ek.operation.request.type'].search([
            ('regime', '=', '70'),
            ('use_in_regimen_70', '=', True)
        ], limit=1)

        vals = {
            'container_id': self.id,
            'journey_crew_id': self.id, # El contenedor actúa como el "viaje" en este contexto
            'type_id': operation_type.id if operation_type else False,
            'ek_ship_registration_id': self.ship_name_id.id if self.ship_name_id else False,
            'res_partner_id': self.shipper_id.id if self.shipper_id else False,
            'shipping_line_id': self.shipping_company.id if self.shipping_company else False,
            'supplies_detail': self.supplies_detail or self.load_number,
        }

        # Crear la solicitud
        request = self.env['ek.operation.request'].create(vals)

        # Traspasar líneas de productos/paquetes si existen
        if self.ek_produc_packages_goods_ids:
            # En ek.operation.request las líneas se vinculan vía ek_operation_request_id
            for line in self.ek_produc_packages_goods_ids:
                line.write({'ek_operation_request_id': request.id})

        return {
            'type': 'ir.actions.act_window',
            'name': _('Nueva Solicitud Generada'),
            'res_model': 'ek.operation.request',
            'view_mode': 'form',
            'res_id': request.id,
            'target': 'current',
        }


    def open_items_container(self):
            return {
                'name': 'Search Items',
                'type': 'ir.actions.act_window',
                'res_model': 'ek.product.packagens.goods',
                'view_mode': 'tree',
                'view_id': self.env.ref('ek_l10n_shipping_operations_charging_regimes.ek_product_packagens_goods_tree_items').id,
                'target': 'new',
                'domain': [('id', 'in', self.ek_produc_packages_goods_ids.ids)],
                "context": {
                    "create": False,
                    "edit": True,
                    "delete": True,
                    },
            }




class ek_product_packagens_goods(models.Model):
    _inherit = "ek.product.packagens.goods"

    id_bl = fields.Many2one("id.bl.70", string="ID BL")

    def delete_table_70(self):
        records = self.browse(self.env.context.get('active_ids'))
        if records:
            records.unlink()
            