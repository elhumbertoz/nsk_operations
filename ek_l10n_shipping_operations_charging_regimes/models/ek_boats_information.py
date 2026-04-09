# -*- coding: utf-8 -*-
import logging

from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError

_logger = logging.getLogger(__name__)


class EkBoatsInformation(models.Model):
    _name = 'ek.boats.information'
    _inherit = ['ek.boats.information', 'ek.ai.extraction.mixin']





    ref_container = fields.Char("Ref. Container")

    # Líneas de detalle de productos/mercancías del contenedor
    ek_produc_packages_goods_ids = fields.One2many(
        "ek.product.packagens.goods",
        "ek_boats_information_id",
        string="Items en Contenedor",
        copy=True,
        help="Productos extraídos de facturas/BL con IA o ingresados manualmente"
    )

    value_of_container = fields.Float("Value of Container", compute="_compute_value_of_container", store=True, index=True, digits=(16, 2))

    @api.depends("ek_produc_packages_goods_ids", "ek_produc_packages_goods_ids.total_fob")
    def _compute_value_of_container(self):
        """Calcular valor total del contenedor basado en FOB de items"""
        for rec in self:
            # Sumar el FOB total de todas las líneas de productos
            rec.value_of_container = sum(rec.ek_produc_packages_goods_ids.mapped('total_fob')) 



    
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
    shipping_line_id = fields.Many2one(
        string="Shipping Line",
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
    number_container = fields.Char("Container Number", tracking=True)
    bl_number = fields.Char("# AWB O BL", tracking=True)
    
    supplier_ids = fields.Many2many(
        comodel_name='res.partner',
        string='Suppliers', relation="res_partner_ek_boats_information_rel",
        column1='partner_id', column2='ek_boats_information_id', tracking=True)

    type_container_id = fields.Many2one("ek.type.container", string="Type Container", tracking=True)

    notes = fields.Text("Notes", tracking=True)

    rcd = fields.Datetime(string="Return Container Date", copy=False, tracking=True)

    # Nuevos campos para extracción extendida de BL
    booking_number = fields.Char("Booking Number", tracking=True)
    seal_number = fields.Char("Seal Number", tracking=True)
    consignee_id = fields.Many2one("res.partner", string="Consignee", tracking=True)
    on_board_date = fields.Date("On Board Date", tracking=True)
    total_gross_weight = fields.Float("Total Gross Weight (BL)", tracking=True)
    total_packages_count = fields.Integer("Total Packages (BL)", tracking=True)
    type_move_fcl_lcl = fields.Selection([
        ('fcl_fcl', 'FCL/FCL'),
        ('fcl_lcl', 'FCL/LCL'),
        ('lcl_lcl', 'LCL/LCL'),
        ('lcl_fcl', 'LCL/FCL'),
    ], string="Type of Move (FCL/LCL)", tracking=True)
    
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


    @api.depends('bl_attachment_ids')
    def _compute_bl_attachment_filename(self):
        for record in self:
            record.bl_attachment_filename = record.bl_attachment_ids[0].name if record.bl_attachment_ids else False

    # ============================================================================
    # AI Extraction Status Fields (Redefinidos explícitamente para garantizar persistencia)
    # ============================================================================
    ai_extraction_status = fields.Selection([
        ('pending', 'Pendiente'),
        ('processing', 'Procesando'),
        ('completed', 'Completado'),
        ('error', 'Error')
    ], string='Estado Extracción IA', default='pending', tracking=True)

    ai_extraction_log = fields.Html(
        string='Resultado de Extracción',
        readonly=True,
        help='Muestra el resultado estructurado de la última operación de IA'
    )

    # Aliases de campos para compatibilidad con el Mixin
    id_bl = fields.Char(related="bl_number", readonly=False, store=True)

    def action_create_operation_request(self):
        """
        Crea una solicitud de operación (Régimen 70) a partir de los datos
        del contenedor (ya extraídos con IA).

        IMPORTANTE: Migra todos los productos/mercancías del contenedor a la solicitud.
        """
        self.ensure_one()

        # Validar que haya productos para migrar
        if not self.ek_produc_packages_goods_ids:
            raise UserError(_(
                'No hay productos/mercancías en el contenedor.\n'
                'Debe extraer datos con IA o agregar productos manualmente antes de crear la solicitud.'
            ))

        # Buscar tipo de operación predeterminado para Régimen 70
        operation_type = self.env['ek.l10n.type.model.mixin'].search([
            ('use_in_regimen_70', '=', True)
        ], limit=1)

        vals = {
            'container_id': self.id,
            'journey_crew_id': self.id, # El contenedor actúa como el "viaje" en este contexto
            'type_id': operation_type.id if operation_type else False,
            'ek_ship_registration_id': self.ship_name_id.id if self.ship_name_id else False,
            'res_partner_id': self.shipper_id.id if self.shipper_id else False,
            'shipping_lines': self.shipping_line_id.id if self.shipping_line_id else False,
            'number_container': self.number_container,
            'number_bl': self.bl_number,
            'agent_customs_id': self.custom_agent.id if self.custom_agent else False,
            'detail_supplies_spare_parts': self.supplies_detail or self.load_number,
            'date_return_container': self.rcd if self.rcd else False,
            'eta': self.eta,
            'booking_number': self.booking_number,
            'seal_number': self.seal_number,
            'consignee_id': self.consignee_id.id if self.consignee_id else False,
            'on_board_date': self.on_board_date,
            'type_move_fcl_lcl': self.type_move_fcl_lcl,
            'ek_res_world_seaport_id_origin': self.ek_res_world_seaports_id.id if self.ek_res_world_seaports_id else False,
            'ek_res_world_seaport_id_destination': self.ek_res_world_seaports_d_id.id if self.ek_res_world_seaports_d_id else False,
        }

        # Crear la solicitud
        request = self.env['ek.operation.request'].create(vals)

        # MIGRAR productos del contenedor a la solicitud
        # Solo se copian los productos que sí vinieron (is_not_dispatched = False)
        products_copied = 0
        for item in self.ek_produc_packages_goods_ids.filtered(lambda p: not p.is_not_dispatched):
            item.copy({
                'ek_operation_request_id': request.id,
                'ek_boats_information_id': False,
            })
            products_copied += 1

        # Mensaje de confirmación
        message = _('Solicitud creada exitosamente.\n%d producto(s) migrado(s) del contenedor.') % products_copied
        request.message_post(body=message, message_type='notification')

        return {
            'type': 'ir.actions.act_window',
            'name': _('Nueva Solicitud Generada'),
            'res_model': 'ek.operation.request',
            'view_mode': 'form',
            'res_id': request.id,
            'target': 'current',
        }


    def open_items_container(self):
        self.ensure_one()
        return {
            'name': _('Gestión de Items: %s') % (self.name or self.ref_container or ''),
            'type': 'ir.actions.act_window',
            'res_model': 'ek.product.packagens.goods',
            'view_mode': 'tree,form',
            'views': [
                (self.env.ref('ek_l10n_shipping_operations_charging_regimes.ek_product_packagens_goods_tree_items').id, 'tree'),
                (False, 'form'),
            ],
            'target': 'current',
            'domain': [('ek_boats_information_id', '=', self.id)],
            'context': {
                'default_ek_boats_information_id': self.id,
                'default_ek_ship_registration_id': self.ship_name_id.id,
                'search_default_ek_boats_information_id': self.id,
            },
        }




class ek_product_packagens_goods(models.Model):
    _inherit = "ek.product.packagens.goods"

    id_bl = fields.Many2one("id.bl.70", string="ID BL")

    def delete_table_70(self):
        records = self.browse(self.env.context.get('active_ids'))
        if records:
            records.unlink()
            