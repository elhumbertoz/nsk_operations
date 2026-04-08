# -*- coding: utf-8 -*-
from datetime import datetime

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError


class EkOperationRequest(models.Model):
  _inherit = 'ek.operation.request'

  # AI Extraction fields are now in ek.boats.information (Container)
  # Keeping related fields for visibility or transitional purposes if needed
  ai_extraction_status = fields.Selection(related="container_id.ai_extraction_status", string="Estado Extracción IA", readonly=True, store=False)
  ai_extraction_status_bl = fields.Selection(related="container_id.ai_extraction_status_bl", string="Estado BL", readonly=True, store=False)
  ai_extraction_status_fc = fields.Selection(related="container_id.ai_extraction_status_fc", string="Estado Facturas", readonly=True, store=False)
  ai_extraction_status_np = fields.Selection(related="container_id.ai_extraction_status_np", string="Estado Nota Pedido", readonly=True, store=False)
  ai_extraction_log = fields.Html(related="container_id.ai_extraction_log", string="Log Extracción IA", readonly=True, store=False)

  # Related attachment fields from container for email notifications
  # NOTA: Estos campos solo funcionan cuando container_id está poblado
  bl_attachment_ids = fields.Many2many(related="container_id.bl_attachment_ids", string="Bill of Lading (Rel)", readonly=True, store=False)
  invoice_attachment_ids = fields.Many2many(related="container_id.invoice_attachment_ids", string="Facturas (Rel)", readonly=True, store=False)
  purchase_order_attachment_ids = fields.Many2many(related="container_id.purchase_order_attachment_ids", string="Nota de Pedido (Rel)", readonly=True, store=False)
  purchase_order_data = fields.Text(related="container_id.purchase_order_data", string="Datos Nota de Pedido (Rel)", readonly=True, store=False)


  use_in_regimen_60 = fields.Boolean(
    related='type_id.use_in_regimen_60',
  )
  ek_table_regimen_60_ids = fields.One2many(
    comodel_name='table.regimen.60',
    inverse_name='ek_operation_request_id',
    string='Regimen 60',
  )
  id_bl_70 = fields.Many2one(
    'id.bl.70', string='ID BL 70', domain="[('id', 'in', id_bl_70_ids)]"
  )

  container_id = fields.Many2one('ek.boats.information', string='Container')

  # Relación directa con productos consumibles Régimen 70 (compartidos con el contenedor)
  # NOTA: NO usar "product_ids" porque ya existe en el modelo base para One2many con ek.product.purchase.ship
  regime_70_product_ids = fields.Many2many(
    'product.product',
    'ek_operation_request_regime70_product_rel',
    'request_id',
    'product_id',
    string='Productos Consumibles Régimen 70',
    domain=[('type', '=', 'consu'), ('purchase_ok', '=', True)],
    help='Productos consumibles de Régimen 70 para esta solicitud'
  )

  id_bl = fields.Char(string='ID BL')

  id_bl_70_ids = fields.Many2many(
    'id.bl.70', relation='ek_operation_request_id_bl_70_rel', string='ID BL  70'
  )

  regime = fields.Selection(
    related='type_id.regime',
  )

  stage_sequence = fields.Integer(related='stage_id.sequence', string='Stage Sequence', store=False)
  stage_fold = fields.Boolean(related='stage_id.fold', string='Stage Fold', store=False)

  movement_date = fields.Datetime(string='Movement Date')
  max_regime_date = fields.Datetime(string='Max Regime Date')

  # Campos computados para totales de paquetes y mercancías
  total_quantity = fields.Float(
    string='Total Quantity',
    compute='_compute_packages_goods_totals',
    store=True,
    help='Total quantity of all packages and goods',
  )

  total_gross_weight = fields.Float(
    string='Total Gross Weight',
    compute='_compute_packages_goods_totals',
    store=True,
    help='Total gross weight of all packages and goods',
  )

  total_fob = fields.Float(
    string='Total FOB',
    compute='_compute_packages_goods_totals',
    store=True,
    help='Total FOB value of all packages and goods',
  )

  total_total_fob = fields.Float(
    string='Total Total FOB',
    compute='_compute_packages_goods_totals',
    store=True,
    help='Total of total FOB values of all packages and goods',
  )

  total_lines = fields.Integer(
    string='Total Lines',
    compute='_compute_packages_goods_totals',
    store=True,
    help='Total number of lines in packages and goods table',
  )

  total_packages_count = fields.Integer(
    string='Total Packages',
    compute='_compute_packages_goods_totals',
    store=True,
    help='Total number of packages/bultos',
  )

  # ============================================================
  # CAMPOS NUEVOS REQ-008: Régimen 70 - Contenedores
  # ============================================================

  # AUTORIZACIÓN Y DOCUMENTACIÓN
  authorization_number = fields.Char(
    string="# Autorización",
    default="M-",
    help="Solicitud previa N° otorgado por almacenera (ej: M-3711)",
    tracking=True
  )

  shipping_line_id = fields.Many2one(
    'res.partner',
    string="Línea Naviera",
    domain="[('is_company', '=', True)]",
    help="Línea naviera comercial (diferente del buque)",
    tracking=True
  )

  # FECHAS ADICIONALES
  container_return_date = fields.Date(
    string="Fecha Devolución Contenedor",
    tracking=True
  )

  # NUEVOS CAMPOS LOGÍSTICOS (REQ-008B)
  bl_number = fields.Char(related="number_bl", string="Número BL", readonly=False, store=True)
  booking_number = fields.Char("Booking Number", tracking=True)
  seal_number = fields.Char("Seal Number", tracking=True)
  consignee_id = fields.Many2one("res.partner", string="Consignatario", tracking=True)
  on_board_date = fields.Date("On Board Date", tracking=True)
  type_move_fcl_lcl = fields.Selection([
      ('fcl_fcl', 'FCL/FCL'),
      ('fcl_lcl', 'FCL/LCL'),
      ('lcl_lcl', 'LCL/LCL'),
      ('lcl_fcl', 'LCL/FCL'),
  ], string="Tipo Movimiento (FCL/LCL)", tracking=True)

  transfer_date = fields.Datetime(
    string="Fecha de Traslado",
    help="Fecha de traslado al depósito aduanero",
    tracking=True
  )

  # DETALLES DE MERCANCÍA
  supplies_detail = fields.Char(
    string="Detalle de Suministros o Repuestos",
    default="CONTENEDOR #",
    help="Descripción breve de la carga"
  )

  deposit_description = fields.Char(
    string="# Matrícula Depósito",
    default="MA-00",
    help="Número de matrícula asignado por almacenera",
    tracking=True
  )

  # INFORMACIÓN DE TRASLADO
  transfer_explanation = fields.Text(
    string="Información del Traslado",
    help="Datos del transportista: Chofer, Cédula, Placas, Cooperativa"
  )

  # CLIENTE Y FACTURACIÓN
  client_partner_id = fields.Many2one(
    'res.partner',
    string="Cliente (Dueño del Barco)",
    help="Cliente externo que solicita servicio de reparación",
    tracking=True
  )

  client_vessel_name = fields.Char(
    string="Nombre del Barco del Cliente",
    help="Nombre de la embarcación del cliente"
  )

  # ORDEN DE VENTA Y FACTURACIÓN
  sale_order_id = fields.Many2one(
    'sale.order',
    string="Orden de Venta",
    help="Orden de venta generada para facturación al cliente",
    readonly=True,
    tracking=True
  )

  invoice_validated = fields.Boolean(
    string="Factura Validada",
    default=False,
    help="Indica si la factura fue validada contra Nota de Pedido",
    tracking=True
  )

  # ============================================================
  # ESTADO DE NOTIFICACIONES (REQ-011 a REQ-015)
  # ============================================================

  # REQ-011: Solicitud a Agente de Aduanas
  mail_sent_customs_agent = fields.Boolean(
    string="Email Agente Enviado",
    default=False,
    help="Indica si se envió la solicitud al agente de aduanas",
    tracking=True
  )
  mail_sent_customs_agent_date = fields.Datetime(
    string="Fecha Envío Agente",
    readonly=True,
    help="Fecha y hora en que se envió el email al agente de aduanas"
  )

  # REQ-012: Solicitud a Almacenera
  mail_sent_warehouse = fields.Boolean(
    string="Email Almacenera Enviado",
    default=False,
    help="Indica si se envió la solicitud a la almacenera",
    tracking=True
  )
  mail_sent_warehouse_date = fields.Datetime(
    string="Fecha Envío Almacenera",
    readonly=True,
    help="Fecha y hora en que se envió el email a la almacenera"
  )

  # REQ-013: Datos de Chofer
  mail_sent_driver_info = fields.Boolean(
    string="Email Chofer Enviado",
    default=False,
    help="Indica si se enviaron los datos del chofer",
    tracking=True
  )
  mail_sent_driver_info_date = fields.Datetime(
    string="Fecha Envío Chofer",
    readonly=True,
    help="Fecha y hora en que se enviaron los datos del chofer"
  )

  # REQ-014: Solicitud de Custodia
  mail_sent_custody = fields.Boolean(
    string="Email Custodia Enviado",
    default=False,
    help="Indica si se envió la solicitud de custodia",
    tracking=True
  )
  mail_sent_custody_date = fields.Datetime(
    string="Fecha Envío Custodia",
    readonly=True,
    help="Fecha y hora en que se envió la solicitud de custodia"
  )

  # REQ-015: Aplicación de Póliza
  mail_sent_insurance = fields.Boolean(
    string="Email Póliza Enviado",
    default=False,
    help="Indica si se envió la aplicación de póliza",
    tracking=True
  )
  mail_sent_insurance_date = fields.Datetime(
    string="Fecha Envío Póliza",
    readonly=True,
    help="Fecha y hora en que se envió la aplicación de póliza"
  )

  # ============================================================
  # PLANTILLAS CONFIGURABLES (OBLIGATORIAS PARA RÉGIMEN 70)
  # ============================================================

  mail_template_customs_agent = fields.Many2one(
    'mail.template',
    string="Plantilla Agente Aduanas",
    domain="[('model', '=', 'ek.operation.request')]",
    default=lambda self: self.env.ref('ek_l10n_shipping_operations_charging_regimes.mail_template_regime_70_customs_agent', raise_if_not_found=False),
    help="Plantilla configurable para solicitud al agente de aduanas."
  )

  mail_template_warehouse = fields.Many2one(
    'mail.template',
    string="Plantilla Almacenera",
    domain="[('model', '=', 'ek.operation.request')]",
    default=lambda self: self.env.ref('ek_l10n_shipping_operations_charging_regimes.mail_template_regime_70_warehouse', raise_if_not_found=False),
    help="Plantilla configurable para solicitud a almacenera."
  )

  mail_template_driver_info = fields.Many2one(
    'mail.template',
    string="Plantilla Datos Chofer",
    domain="[('model', '=', 'ek.operation.request')]",
    default=lambda self: self.env.ref('ek_l10n_shipping_operations_charging_regimes.mail_template_regime_70_driver_info', raise_if_not_found=False),
    help="Plantilla configurable para datos de chofer."
  )

  mail_template_custody = fields.Many2one(
    'mail.template',
    string="Plantilla Custodia",
    domain="[('model', '=', 'ek.operation.request')]",
    default=lambda self: self.env.ref('ek_l10n_shipping_operations_charging_regimes.mail_template_regime_70_custody', raise_if_not_found=False),
    help="Plantilla configurable para solicitud de custodia."
  )

  mail_template_insurance = fields.Many2one(
    'mail.template',
    string="Plantilla Póliza",
    domain="[('model', '=', 'ek.operation.request')]",
    default=lambda self: self.env.ref('ek_l10n_shipping_operations_charging_regimes.mail_template_regime_70_insurance', raise_if_not_found=False),
    help="Plantilla configurable para aplicación de póliza."
  )

  # RESUMEN DE BULTOS POR BUQUE (REQ-010)
  total_packages_by_vessel = fields.Text(
    string="Resumen de Bultos por Buque",
    compute="_compute_packages_summary",
    store=True,
    help="Resumen automático de bultos agrupados por buque"
  )

  @api.depends(
    'ek_produc_packages_goods_ids.quantity',
    'ek_produc_packages_goods_ids.gross_weight',
    'ek_produc_packages_goods_ids.fob',
    'ek_produc_packages_goods_ids.total_fob',
    'ek_produc_packages_goods_ids.packages_count',
  )
  def _compute_packages_goods_totals(self):
    for record in self:
      packages_goods = record.ek_produc_packages_goods_ids
      record.total_quantity = sum(packages_goods.mapped('quantity'))
      record.total_gross_weight = sum(packages_goods.mapped('gross_weight'))
      record.total_fob = sum(packages_goods.mapped('fob'))
      record.total_total_fob = sum(packages_goods.mapped('total_fob'))
      record.total_lines = len(packages_goods)

      # Suma segura de bultos (campo Char)
      total_p = 0
      for pg in packages_goods:
        try:
          total_p += int(float(pg.packages_count or 0))
        except (ValueError, TypeError):
          pass
      record.total_packages_count = total_p

  @api.depends(
    'ek_produc_packages_goods_ids.ship_id',
    'ek_produc_packages_goods_ids.packages_count'
  )
  def _compute_packages_summary(self):
    """
    Calcula resumen de bultos agrupados por buque
    REQ-010: Cálculo de Bultos por Buque
    """
    for record in self:
      if not record.ek_produc_packages_goods_ids:
        record.total_packages_by_vessel = ""
        continue

      # Agrupar por buque
      summary = {}
      total_packages = 0

      for line in record.ek_produc_packages_goods_ids:
        ship_name = line.ship_id.name if line.ship_id else "Stock General"
        try:
          packages = int(float(line.packages_count or 0))
        except (ValueError, TypeError):
          packages = 0

        if ship_name not in summary:
          summary[ship_name] = {'packages': 0, 'products': 0}

        summary[ship_name]['packages'] += packages
        summary[ship_name]['products'] += 1
        total_packages += packages

      # Generar texto formateado
      lines = []
      for ship_name in sorted(summary.keys()):
        data = summary[ship_name]
        lines.append(f"• {ship_name}: {data['packages']} bultos ({data['products']} productos)")

      lines.append(f"\nBULTOS TOTALES: {total_packages}")

      record.total_packages_by_vessel = "\n".join(lines)

  def action_generate_sale_order(self):
    """
    Generar orden de venta para Régimen 70
    REQ-025, REQ-027: Generación de Orden de Venta
    """
    self.ensure_one()

    # Validaciones
    if not self.client_partner_id:
      raise UserError(_('Debe especificar un cliente (dueño del barco) antes de generar la orden de venta'))

    if self.sale_order_id:
      raise UserError(_('Ya existe una orden de venta asociada: %s') % self.sale_order_id.name)

    if not self.ek_produc_packages_goods_ids:
      raise UserError(_('No hay productos para incluir en la orden de venta'))

    # Obtener markup del cliente (campo nuevo en res.partner)
    markup_percent = self.client_partner_id.maritime_service_markup or 20.0

    # Crear orden de venta
    sale_vals = {
      'partner_id': self.client_partner_id.id,
      'date_order': fields.Datetime.now(),
      'origin': self.name or '',
      'note': _(
        'Orden de venta generada automáticamente para Régimen 70\n'
        'Contenedor: %s\n'
        'Barco Cliente: %s\n'
        'Markup aplicado: %s%%'
      ) % (
        self.number_container or 'N/A',
        self.client_vessel_name or 'N/A',
        markup_percent
      ),
    }

    # Crear orden
    sale_order = self.env['sale.order'].create(sale_vals)

    # Crear líneas de orden de venta
    for goods_line in self.ek_produc_packages_goods_ids:
      if not goods_line.product_id:
        continue

      # Calcular precio con markup
      cost_price = goods_line.product_id.standard_price or goods_line.fob or 0
      sale_price = cost_price * (1 + markup_percent / 100)

      line_vals = {
        'order_id': sale_order.id,
        'product_id': goods_line.product_id.id,
        'name': goods_line.product_id.display_name or goods_line.name or '',
        'product_uom_qty': goods_line.quantity or 1,
        'price_unit': sale_price,
        'tax_id': [(6, 0, goods_line.product_id.taxes_id.ids)],
      }

      self.env['sale.order.line'].create(line_vals)

    # Vincular orden con solicitud
    self.sale_order_id = sale_order.id

    # Log en chatter
    self.message_post(
      body=_('Orden de venta %s creada con %s líneas. Markup: %s%%') % (
        sale_order.name,
        len(sale_order.order_line),
        markup_percent
      )
    )

    # Abrir orden de venta
    return {
      'type': 'ir.actions.act_window',
      'name': _('Orden de Venta Generada'),
      'res_model': 'sale.order',
      'view_mode': 'form',
      'res_id': sale_order.id,
      'target': 'current',
    }

  # DEFINIR COMO HACER ESTO
  # def _get_object_validation_model_config(self):
  #     res = super(EkOperationRequest, self)._get_object_validation_model_config()
  #     return {
  #         self._name: {
  #             "_inherit_dinamic_view": "ek_operation_request_form_reandoly",
  #             "_inherit_position_view": "after",
  #             "_inherit_xpath_view": "//group[@name='dinamic_view']",
  #             "_module_dinamic_name": "ek_l10n_shipping_operations_charging_regimes",
  #             "_inherit_dinamic_fields_position": [{
  #                 "name": "date_end",
  #                 "xpath": "//field[@name='create_date']",
  #                 "position": "after",
  #             },{
  #                 "name": "date_start",
  #                 "xpath": "//field[@name='create_date']",
  #                 "position": "before",
  #             },{
  #                 "name": "date_end_request",
  #                 "xpath": "//field[@name='create_date']",
  #                 "position": "after",
  #             },{
  #                 "name": "date_emition_request",
  #                 "xpath": "//field[@name='create_date']",
  #                 "position": "after",
  #             },{
  #                 "name": "ek_operation_request_id",
  #                 "xpath": "//field[@name='type_id']",
  #                 "position": "after",
  #             }],
  #         }
  #     }

  def open_search_modal_60(self):
    return {
      'name': 'Search Items',
      'type': 'ir.actions.act_window',
      'res_model': 'table.regimen.60',
      'view_mode': 'tree',
      'view_id': self.env.ref(
        'ek_l10n_shipping_operations_charging_regimes.table_regimen_60_tree'
      ).id,
      'target': 'new',
      'domain': [('id', 'in', self.ek_table_regimen_60_ids.ids)],
      'context': {
        'create': False,
        'edit': True,
        'delete': True,
      },
    }

  def action_open_readonly_edit(self):
    self.ensure_one()
    return {
      'type': 'ir.actions.act_window',
      'name': 'Edit',
      'res_model': 'ek.operation.request',
      'view_mode': 'form',
      'res_id': self.id,
      'view_id': self.env.ref(
        'ek_l10n_shipping_operations_charging_regimes.ek_operation_request_form_reandoly'
      ).id,
      'target': 'new',
    }

  @api.onchange('container_id')
  def _compute_id_bl_70_ids(self):
    for rec in self:
      value = self.env['id.bl.70'].search(
        [('journey_crew_id', '=', self.container_id.id)]
      )
      if value:
        rec.id_bl_70_ids = value
      else:
        rec.id_bl_70_ids = False
        rec.id_bl_70 = False

  def onchange_type_id_regimen_60(self, context=None):
    if (
      self.type_id
      and self.type_id.use_in_regimen_60
      and self.container_id
      and self.container_id.ek_produc_packages_goods_ids
    ):
      new_lines = []
      for line in self.container_id.ek_produc_packages_goods_ids.filtered(
        lambda x: x.id_bl.id == self.id_bl_70.id
      ):
        if line.quantity_hand <= 0:
          continue
        new_lines.append(
          (
            0,
            0,
            {
              'ek_product_packagens_goods_id': line.id,
            },
          )
        )
      if not context:
        self.ek_table_regimen_60_ids.unlink()
        self.ek_table_regimen_60_ids = new_lines
      if not new_lines:
        raise ValidationError(
          _("You can't use this type of operation with this container.")
        )
      return new_lines
    else:
      raise ValidationError(
        _("You can't use this type of operation with this container.")
      )

  # def action_cancel(self):
  #     res = super().action_cancel()
  #     for rec in self:
  #         if rec.bl_import_export_id :
  #                 rec.bl_import_export_id.in_use = False
  #         elif rec.bl_import_export_id2:
  #                 rec.bl_import_export_id2.in_use = False
  #     return res

  def action_confirm(self):
    res = super().action_confirm()
    for rec in self:
      # pending update the state for stage
      # if rec.journey_crew_id and rec.type_id and rec.type_id.change_state_travel_after_confirm:
      #     update_values.update({"state": rec.type_id.change_state_travel_after_confirm})

      if rec.journey_crew_id and rec.type_id and rec.type_id.use_in_regimen_70:
        if not self.ek_produc_packages_goods_ids:
          raise ValidationError(_('upload file before continuing.'))
        travel = rec.journey_crew_id
        # travel.ek_produc_packages_goods_ids.unlink()
        bl = self.env['id.bl.70'].create(
          {'name': rec.id_bl, 'journey_crew_id': rec.journey_crew_id.id}
        )
        new_lines = []
        for line in rec.ek_produc_packages_goods_ids:
          new_lines.append(
            (
              0,
              0,
              {
                'tariff_item': line.tariff_item,
                'ek_requerid_burden_inter_nac_id': line.ek_requerid_burden_inter_nac_id.id,
                'quantity': line.quantity,
                'gross_weight': line.gross_weight,
                'product_weight_in_lbs': line.product_weight_in_lbs,
                'fob': line.fob,
                'invoice_number': line.invoice_number,
                'supplier': line.supplier,
                'ek_boats_information_id': travel.id,
                'id_bl': bl.id,
                'id_hs_copmt_cd': line.id_hs_copmt_cd,
                'id_hs_spmt_cd': line.id_hs_spmt_cd,
                'date_request': rec.create_date,
                'max_regime_date': rec.max_regime_date,
                'number_dai': rec.number_dai,
              },
            )
          )
        rec.journey_crew_id.ek_produc_packages_goods_ids = new_lines

      if rec.type_id and rec.type_id.use_in_regimen_60 and rec.journey_crew_id:
        data = []
        for line in rec.ek_table_regimen_60_ids:
          dilivery_product = (
            line.quantity + line.ek_product_packagens_goods_id.delivery_product
          )
          if line.ek_product_packagens_goods_id.quantity >= dilivery_product:
            line.ek_product_packagens_goods_id.write(
              {'delivery_product': dilivery_product}
            )
          else:
            data.append(line.ek_requerid_burden_inter_nac_id.name)
        rec.movement_date = datetime.now()
        if data:
          raise UserError(
            _('Quantity can not be less than quantity hand for %s') % (data)
          )
      if rec.bl_import_export_id:
        rec.bl_import_export_id.in_use = True
      if rec.bl_import_export_id2:
        rec.bl_import_export_id2.in_use = True

    return res

  @api.constrains('ek_table_regimen_60_ids', 'container_id')
  def error_ek_table_regimen_60_ids(self):
    if self.ek_table_regimen_60_ids and self.use_in_regimen_60:
      data_qty_hand = []
      for line in self.ek_table_regimen_60_ids:
        if line.quantity > line.quantity_hand:
          data_qty_hand.append(line.ek_requerid_burden_inter_nac_id.name)

      if data_qty_hand:
        raise ValidationError(
          _('Quantity can not be less than quantity hand for %s')
          % (data_qty_hand)
        )

  def action_fill_everything(self):
    for rec in self:
      if rec.ek_table_regimen_60_ids and rec.use_in_regimen_60:
        for line in rec.ek_table_regimen_60_ids:
          line.quantity = line.quantity_hand

  def refresh_regimen_60(self):
    update_lines = self.onchange_type_id_regimen_60(True)
    table = self.ek_table_regimen_60_ids
    existing_line_ids = table.mapped('ek_product_packagens_goods_id.id')
    new_lines = [
      line
      for line in update_lines
      if line[2].get('ek_product_packagens_goods_id') not in existing_line_ids
    ]
    self.ek_table_regimen_60_ids = new_lines
    records_to_unlink = self.ek_table_regimen_60_ids.filtered(
      lambda rec: rec.ek_product_packagens_goods_id
      and rec.ek_product_packagens_goods_id.quantity_hand <= 0
    )
    records_to_unlink.unlink()

  def action_clear_packages_goods(self):
    """Clear all lines from packages and goods table"""
    # Verificar si hay datos para eliminar
    total_records = sum(
      len(record.ek_produc_packages_goods_ids) for record in self
    )

    if total_records == 0:
      return {
        'type': 'ir.actions.client',
        'tag': 'display_notification',
        'params': {
          'title': _('Información'),
          'message': _('No hay paquetes y mercancías para eliminar.'),
          'type': 'info',
          'sticky': False,
        },
      }

    # Mostrar wizard de confirmación
    return {
      'name': _('Confirmar eliminación'),
      'type': 'ir.actions.act_window',
      'res_model': 'ek.packages.goods.clear.wizard',
      'view_mode': 'form',
      'target': 'new',
      'context': {
        'default_operation_request_ids': [(6, 0, self.ids)],
        'default_total_records': total_records,
      },
    }

  def action_clear_packages_goods_confirmed(self):
    """Método interno para eliminar paquetes y mercancías tras confirmación"""
    for record in self:
      if record.ek_produc_packages_goods_ids:
        record.ek_produc_packages_goods_ids.unlink()
        # Actualizar mapeo de facturas después de eliminar líneas
        if record.regime == '70':
          record._update_invoice_ship_map()

    return {
      'type': 'ir.actions.client',
      'tag': 'display_notification',
      'params': {
        'title': _('Éxito'),
        'message': _(
          'Los paquetes y mercancías han sido eliminados correctamente.'
        ),
        'type': 'success',
        'sticky': False,
      },
    }

  def refresh_invoice_ship_map(self):
    """Método público para actualizar el mapeo de facturas manualmente"""
    for record in self:
      if record.regime == '70':
        record._update_invoice_ship_map()
    return True

  def action_clear_customs_data(self):
    """Limpiar todos los datos de aduanas"""
    # Verificar si hay datos para eliminar
    total_records = sum(len(record.customs_agent_data_ids) for record in self)

    if total_records == 0:
      return {
        'type': 'ir.actions.client',
        'tag': 'display_notification',
        'params': {
          'title': _('Información'),
          'message': _('No hay datos de aduanas para eliminar.'),
          'type': 'info',
          'sticky': False,
        },
      }

    # Mostrar wizard de confirmación
    return {
      'name': _('Confirmar eliminación'),
      'type': 'ir.actions.act_window',
      'res_model': 'ek.customs.data.clear.wizard',
      'view_mode': 'form',
      'target': 'new',
      'context': {
        'default_operation_request_ids': [(6, 0, self.ids)],
        'default_total_records': total_records,
      },
    }

  def action_clear_customs_data_confirmed(self):
    """Método interno para eliminar los datos tras confirmación"""
    for record in self:
      if record.customs_agent_data_ids:
        record.customs_agent_data_ids.unlink()

    return {
      'type': 'ir.actions.client',
      'tag': 'display_notification',
      'params': {
        'title': _('Éxito'),
        'message': _('Los datos de aduanas han sido eliminados correctamente.'),
        'type': 'success',
        'sticky': False,
      },
    }

  def action_export_final_list(self):
    """Exportar listado final a Excel"""
    # TODO: Implementar en el siguiente paso
    return {
      'type': 'ir.actions.client',
      'tag': 'display_notification',
      'params': {
        'title': _('Próximamente'),
        'message': 'Funcionalidad de exportación será implementada en el siguiente paso.',
        'type': 'info',
        'sticky': False,
      },
    }

  # Note: AI extraction methods will be added via mixin composition
  # See ek_operation_request_mixin.py

  bl_import_export_id = fields.Many2one('bl.import.export', string='BL Export')
  bl_import_export_id2 = fields.Many2one('bl.import.export', string='BL Import')

  @api.depends('type_id', 'name', 'bl_import_export_id', 'bl_import_export_id2')
  def _compute_display_name(self):
    for record in self:
      if (
        record.type_id
        and record.type_id.name
        and record.name
        and not record.bl_import_export_id
        and not record.bl_import_export_id2
      ):
        record.display_name = record.name + '-' + record.type_id.name
      elif (
        record.type_id
        and record.type_id.name
        and record.name
        and record.bl_import_export_id
        and not record.bl_import_export_id2
      ):
        record.display_name = (
          record.name
          + '-'
          + record.bl_import_export_id.name
          + '-'
          + record.type_id.name
        )
      elif (
        record.type_id
        and record.type_id.name
        and record.name
        and record.bl_import_export_id2
        and not record.bl_import_export_id
      ):
        record.display_name = (
          record.name
          + '-'
          + record.bl_import_export_id2.name
          + '-'
          + record.type_id.name
        )
      else:
        record.display_name = record.name

  domain_bl_import_export = fields.Char(
    compute='_compute_domain_bl_import_export', default="[('type', '=', 'xxx')]"
  )

  has_bl_import = fields.Boolean(
    related='type_id.has_bl_import',
  )
  has_bl_export = fields.Boolean(
    related='type_id.has_bl_export',
  )

  def _compute_domain_bl_import_export(self):
    for record in self:
      if (
        record.has_bl_import
        and record.ek_ship_registration_id
        and record.journey_crew_id
      ):
        record.domain_bl_import_export = (
          "[('ship_name_id', '=', %s), ('type', '=', 'import'), ('journey_crew_id', '=', %s), ('in_use', '=',  %s)]"
          % (
            record.ek_ship_registration_id.id,
            record.journey_crew_id.id,
            False,
          )
        )

      elif (
        record.has_bl_export
        and record.ek_ship_registration_id
        and record.journey_crew_id
      ):
        record.domain_bl_import_export = (
          "[('ship_name_id', '=', %s), ('type', '=', 'export'), ('journey_crew_id', '=', %s), ('in_use', '=',  %s)]"
          % (
            record.ek_ship_registration_id.id,
            record.journey_crew_id.id,
            False,
          )
        )

      else:
        record.domain_bl_import_export = "[('type', '=', 'xxx')]"

  def generate_sequence_bl_import(self):
    sequence = self.type_id.sequence_bl_import.next_by_id()
    return self.generate_sequence_bl_ie('import', sequence)

  def generate_sequence_bl_export(self):
    sequence = self.type_id.sequence_bl_export.next_by_id()
    return self.generate_sequence_bl_ie('export', sequence)

  def generate_sequence_bl_ie(self, type=None, sequence=None):
    for record in self:
      value = {
        'name': sequence,
        'ship_name_id': record.ek_ship_registration_id.id,
        'journey_crew_id': record.journey_crew_id.id,
        'type': type,
      }
      if not record.bl_import_export_id2 and type == 'import':
        record.bl_import_export_id2 = self.env['bl.import.export'].create(value)
      # value_name =record.name  + "-" + record.bl_import_export_id2.name
      # record.update({"name": value_name})
      #   record.display_name = value_name
      elif not record.bl_import_export_id and type == 'export':
        record.bl_import_export_id = self.env['bl.import.export'].create(value)
      # value_name = record.name +  "-" + record.bl_import_export_id.name
      # record.update({"name": value_name})
      # record.display_name = value_name
      else:
        raise UserError(
          _('leave the field without data to generate the sequence')
        )

  # @api.depends('type_id', 'name','bl_import_export_id','bl_import_export_id2')
  # def _compute_display_name(self):
  #     for record in self:
  #         if record.type_id and record.type_id.name and record.name:
  #             record.display_name =  record.name + '-' + record.type_id.name + '-' + (record.bl_import_export_id.name or record.bl_import_export_id2.name or ' ')
  #         else:
  #             record.display_name = record.name

  invoice_ship_map_ids = fields.One2many(
    'ek.invoice.ship.map', 'operation_request_id', string='Mapeo de Facturas'
  )

  customs_agent_data_ids = fields.One2many(
    'ek.customs.agent.data',
    'operation_request_id',
    string='Datos de Aduanas',
  )

  def _update_invoice_ship_map(self):
    """Actualiza la tabla de mapeo de facturas basada en los paquetes y mercancías"""

    for record in self:
      if record.regime == '70':
        # Obtener combinaciones únicas de factura/proveedor
        unique_invoices = {}
        for line in record.ek_produc_packages_goods_ids:
          if line.invoice_number and line.supplier:
            key = (line.invoice_number, line.supplier)
            unique_invoices[key] = True

        # Crear o actualizar registros en invoice_ship_map_ids
        existing_maps = {
          (m.invoice_number, m.supplier): m for m in record.invoice_ship_map_ids
        }

        # Crear nuevos mapeos
        new_maps = []
        for invoice_number, supplier in unique_invoices.keys():
          if (invoice_number, supplier) not in existing_maps:
            new_maps.append(
              (
                0,
                0,
                {
                  'invoice_number': invoice_number,
                  'supplier': supplier,
                },
              )
            )

        # Eliminar mapeos que ya no existen
        to_delete = []
        for map_record in record.invoice_ship_map_ids:
          if (
            map_record.invoice_number,
            map_record.supplier,
          ) not in unique_invoices:
            to_delete.append((2, map_record.id, 0))

        if new_maps or to_delete:
          # Usar context para evitar recursión infinita
          record.with_context(skip_invoice_map_update=True).write(
            {'invoice_ship_map_ids': new_maps + to_delete}
          )

  @api.model
  def create(self, vals):
    record = super().create(vals)
    # Actualizar mapeo de facturas si es régimen 70 y tiene paquetes y mercancías
    if record.regime == '70' and record.ek_produc_packages_goods_ids:
      record._update_invoice_ship_map()
    return record

  def write(self, vals):
    res = super().write(vals)

    # Verificar si necesitamos actualizar el mapeo de facturas
    for record in self:
      if record.regime == '70' and not self._context.get(
        'skip_invoice_map_update'
      ):
        should_update = False

        # Detectar cambios en paquetes y mercancías
        if 'ek_produc_packages_goods_ids' in vals:
          should_update = True

        # También actualizar después de importaciones de Excel
        # (cuando se crean/modifican registros de paquetes y mercancías)
        if should_update or (
          record.ek_produc_packages_goods_ids
          and len(record.ek_produc_packages_goods_ids) > 0
        ):
          record._update_invoice_ship_map()
          break

    return res

  # ============================================================================
  # FASE CRISTHIAN: Campos computados para detección de etapas (simplificado)
  # Usados solo para visibilidad de botones de notificación
  # ============================================================================

  is_stage_draft = fields.Boolean(compute='_compute_regime_70_stage_flags', store=False)
  is_stage_notification = fields.Boolean(compute='_compute_regime_70_stage_flags', store=False)
  is_stage_arrival = fields.Boolean(compute='_compute_regime_70_stage_flags', store=False)
  is_stage_transfer = fields.Boolean(compute='_compute_regime_70_stage_flags', store=False)
  is_stage_deposit = fields.Boolean(compute='_compute_regime_70_stage_flags', store=False)
  is_stage_closure = fields.Boolean(compute='_compute_regime_70_stage_flags', store=False)
  is_stage_generate_so = fields.Boolean(compute='_compute_regime_70_stage_flags', store=False)
  is_stage_done = fields.Boolean(compute='_compute_regime_70_stage_flags', store=False)
  is_stage_cancelled = fields.Boolean(compute='_compute_regime_70_stage_flags', store=False)

  @api.depends('stage_id', 'regime')
  def _compute_regime_70_stage_flags(self):
    """Detecta etapa actual para Régimen 70 (solo para botones de notificación)"""
    for record in self:
      # Por defecto todos en False
      record.is_stage_draft = False
      record.is_stage_notification = False
      record.is_stage_arrival = False
      record.is_stage_transfer = False
      record.is_stage_deposit = False
      record.is_stage_closure = False
      record.is_stage_generate_so = False
      record.is_stage_done = False
      record.is_stage_cancelled = False

      # Solo calcular si es Régimen 70 y tiene etapa
      if record.regime != '70' or not record.stage_id:
        continue

      # Comparar por nombre de etapa (más confiable que por ID)
      stage_name = record.stage_id.name
      if stage_name == 'Borrador':
        record.is_stage_draft = True
      elif stage_name == 'Notificación':
        record.is_stage_notification = True
      elif stage_name == 'Arribo':
        record.is_stage_arrival = True
      elif stage_name == 'Traslado':
        record.is_stage_transfer = True
      elif stage_name == 'Ingreso a Depósito':
        record.is_stage_deposit = True
      elif stage_name == 'Cierre':
        record.is_stage_closure = True
      elif stage_name == 'Generar Orden de Venta':
        record.is_stage_generate_so = True
      elif stage_name == 'Realizado':
        record.is_stage_done = True
      elif stage_name == 'Cancelado':
        record.is_stage_cancelled = True

  # ============================================================================
  # FASE CRISTHIAN: Métodos de envío de correos automáticos
  # ============================================================================

  def action_send_mail_customs_agent(self):
    """REQ-011: Enviar correo a agente de aduanas (Etapa: NOTIFICACIÓN)"""
    self.ensure_one()

    # Validaciones de datos requeridos
    if not self.agent_customs_id:
      raise UserError(_("Debe asignar un Agente de Aduanas antes de enviar el correo."))

    if not self.container_id:
      raise UserError(_("La solicitud debe estar vinculada a un contenedor."))

    if not self.number_bl:
      raise UserError(_("Debe especificar el número de BL (Bill of Lading)."))

    if not self.ek_produc_packages_goods_ids:
      raise UserError(_(
        "No hay productos/mercancías para notificar.\n"
        "La solicitud debe tener productos migrados del contenedor."
      ))

    # Usar plantilla configurable
    if not self.mail_template_customs_agent:
      raise UserError(_("Debe seleccionar una plantilla de correo para el agente de aduanas."))

    template = self.mail_template_customs_agent

    attachment_ids = []
    if self.bl_attachment_ids:
      attachment_ids.extend(self.bl_attachment_ids.ids)
    if self.invoice_attachment_ids:
      attachment_ids.extend(self.invoice_attachment_ids.ids)

    template.send_mail(self.id, force_send=True, email_values={'attachment_ids': [(6, 0, attachment_ids)]} if attachment_ids else {})

    # Marcar como enviado
    self.write({
      'mail_sent_customs_agent': True,
      'mail_sent_customs_agent_date': fields.Datetime.now()
    })

    self.message_post(body=_("📧 Correo enviado al agente de aduanas: %s") % self.agent_customs_id.name)

    return {'type': 'ir.actions.client', 'tag': 'display_notification', 'params': {
      'title': _('Correo Enviado'),
      'message': _('Se envió correo a %s con %d adjuntos') % (self.agent_customs_id.name, len(attachment_ids)),
      'type': 'success',
    }}

  def action_send_mail_warehouse(self):
    """REQ-012: Enviar correo a almacenera (Etapa: ARRIBO)"""
    self.ensure_one()

    # Validaciones de datos requeridos
    if not self.res_partner_id:
      raise UserError(_("Debe asignar una Almacenera antes de enviar el correo."))

    if not self.authorization_number or self.authorization_number == 'M-':
      raise UserError(_(
        "Debe completar el Número de Autorización (M-XXXX).\n"
        "Este número es otorgado por la almacenera en la solicitud previa."
      ))

    if not self.ek_produc_packages_goods_ids:
      raise UserError(_("No hay productos/mercancías para enviar a la almacenera."))

    # Usar plantilla configurable
    if not self.mail_template_warehouse:
      raise UserError(_("Debe seleccionar una plantilla de correo para la almacenera."))

    template = self.mail_template_warehouse

    attachment_ids = []
    if self.purchase_order_attachment_ids:
      attachment_ids.extend(self.purchase_order_attachment_ids.ids)
    if self.bl_attachment_ids:
      attachment_ids.extend(self.bl_attachment_ids.ids)
    if self.invoice_attachment_ids:
      attachment_ids.extend(self.invoice_attachment_ids.ids)

    template.send_mail(self.id, force_send=True, email_values={'attachment_ids': [(6, 0, attachment_ids)]} if attachment_ids else {})

    # Marcar como enviado
    self.write({
      'mail_sent_warehouse': True,
      'mail_sent_warehouse_date': fields.Datetime.now()
    })

    self.message_post(body=_("📧 Correo enviado a almacenera: %s") % self.res_partner_id.name)

    return {'type': 'ir.actions.client', 'tag': 'display_notification', 'params': {
      'title': _('Correo Enviado'),
      'message': _('Se envió correo a %s') % self.res_partner_id.name,
      'type': 'success',
    }}

  def action_send_mail_driver_info(self):
    """REQ-013: Enviar datos de chofer (Etapa: TRASLADO)"""
    self.ensure_one()

    # Validaciones de datos requeridos
    if not self.res_partner_id:
      raise UserError(_("Debe asignar una Almacenera antes de enviar el correo."))

    if not self.transfer_explanation:
      raise UserError(_(
        "Debe completar la información del transportista.\n"
        "Incluya: Nombre del chofer, Cédula, Placas del vehículo, Cooperativa."
      ))

    if not self.transfer_date:
      raise UserError(_("Debe especificar la fecha de traslado."))

    # Usar plantilla configurable
    if not self.mail_template_driver_info:
      raise UserError(_("Debe seleccionar una plantilla de correo para datos de chofer."))

    template = self.mail_template_driver_info

    template.send_mail(self.id, force_send=True)

    # Marcar como enviado
    self.write({
      'mail_sent_driver_info': True,
      'mail_sent_driver_info_date': fields.Datetime.now()
    })

    self.message_post(body=_("📧 Información de chofer enviada"))

    return {'type': 'ir.actions.client', 'tag': 'display_notification', 'params': {
      'title': _('Correo Enviado'), 'message': _('Datos del chofer enviados'), 'type': 'success',
    }}

  def action_send_mail_custody(self):
    """REQ-014: Solicitar custodia (Etapa: TRASLADO)"""
    self.ensure_one()

    # Validaciones de datos requeridos
    if not self.deposit_description or self.deposit_description == 'MA-00':
      raise UserError(_(
        "Debe completar el Número de Matrícula del Depósito (MA-XX).\n"
        "Este número es asignado por la almacenera al ingresar la mercancía."
      ))

    if not self.ek_produc_packages_goods_ids:
      raise UserError(_("No hay productos/mercancías para solicitar custodia."))

    # Usar plantilla configurable
    if not self.mail_template_custody:
      raise UserError(_("Debe seleccionar una plantilla de correo para solicitud de custodia."))

    template = self.mail_template_custody

    template.send_mail(self.id, force_send=True)

    # Marcar como enviado
    self.write({
      'mail_sent_custody': True,
      'mail_sent_custody_date': fields.Datetime.now()
    })

    self.message_post(body=_("🚨 Solicitud de custodia enviada"))

    return {'type': 'ir.actions.client', 'tag': 'display_notification', 'params': {
      'title': _('Correo Enviado'), 'message': _('Solicitud de custodia enviada'), 'type': 'success',
    }}

  def action_send_mail_insurance(self):
    """REQ-015: Enviar aplicación de póliza (Etapa: CIERRE)"""
    self.ensure_one()

    # Validaciones de datos requeridos
    if not self.number_mrn:
      raise UserError(_("Debe ingresar el número de póliza (MRN)."))

    if not self.sale_order_id:
      raise UserError(_(
        "Debe generar la Orden de Venta antes de aplicar la póliza.\n"
        "La póliza se aplica sobre los consumos facturados."
      ))

    if not self.invoice_validated:
      raise UserError(_(
        "Debe validar la factura contra la Nota de Pedido antes de aplicar la póliza."
      ))

    # Usar plantilla configurable
    if not self.mail_template_insurance:
      raise UserError(_("Debe seleccionar una plantilla de correo para aplicación de póliza."))

    template = self.mail_template_insurance

    template.send_mail(self.id, force_send=True)

    # Marcar como enviado
    self.write({
      'mail_sent_insurance': True,
      'mail_sent_insurance_date': fields.Datetime.now()
    })

    self.message_post(body=_("📋 Aplicación de póliza enviada (MRN: %s)") % self.number_mrn)

    return {'type': 'ir.actions.client', 'tag': 'display_notification', 'params': {
      'title': _('Correo Enviado'), 'message': _('Póliza MRN: %s enviada') % self.number_mrn, 'type': 'success',
    }}

  def action_requeired_stage_fields(self, stage):
    """Override para agregar validaciones de notificación en etapas de Régimen 70."""
    errors = super().action_requeired_stage_fields(stage)

    if self.regime != '70' or not stage:
      return errors

    seq = stage.sequence

    # Al salir de Notificación (seq 11) → debe haberse enviado correo al agente
    if seq == 11 and not self.mail_sent_customs_agent:
      errors.append(_('Régimen 70: Debe enviar la notificación al Agente de Aduanas antes de avanzar.'))

    # Al salir de Arribo (seq 13) → debe haberse enviado correo a la almacenera
    if seq == 13 and not self.mail_sent_warehouse:
      errors.append(_('Régimen 70: Debe enviar la notificación a la Almacenera antes de avanzar.'))

    # Al salir de Traslado (seq 22) → datos de chofer y custodia
    if seq == 22 and not self.mail_sent_driver_info:
      errors.append(_('Régimen 70: Debe enviar los Datos del Chofer antes de avanzar.'))
    if seq == 22 and not self.mail_sent_custody:
      errors.append(_('Régimen 70: Debe enviar la Solicitud de Custodia antes de avanzar.'))

    return errors


class bl_import_export(models.Model):
  _name = 'bl.import.export'
  _description = 'BL'

  name = fields.Char(string='BL')
  journey_crew_id = fields.Many2one(
    'ek.boats.information', string='Journey Crew'
  )
  ship_name_id = fields.Many2one('ek.ship.registration', string='Ship Name')
  type = fields.Selection(
    [('import', 'Import'), ('export', 'Export')], string='Type'
  )
  in_use = fields.Boolean(string='Use')


class id_bl_70(models.Model):
  _name = 'id.bl.70'
  _description = 'id bl'

  name = fields.Char(string='ID BL')
  journey_crew_id = fields.Many2one(
    'ek.boats.information', string='Journey Crew'
  )


class table_regimen_60(models.Model):
  _name = 'table.regimen.60'
  _description = 'Table Regimen 60'
  _order = 'ek_requerid_burden_inter_nac_id asc'

  ek_operation_request_id = fields.Many2one(
    comodel_name='ek.operation.request',
    string='Operation Request',
  )

  tariff_item = fields.Char(related='ek_product_packagens_goods_id.tariff_item')
  name = fields.Text(related='ek_product_packagens_goods_id.name')
  id_hs_copmt_cd = fields.Char(
    related='ek_product_packagens_goods_id.id_hs_copmt_cd'
  )
  id_hs_spmt_cd = fields.Char(
    related='ek_product_packagens_goods_id.id_hs_spmt_cd'
  )
  ek_requerid_burden_inter_nac_id = fields.Many2one(
    related='ek_product_packagens_goods_id.ek_requerid_burden_inter_nac_id',
    store=True,
  )
  quantity = fields.Float(string='Quantity')
  gross_weight = fields.Float(
    related='ek_product_packagens_goods_id.gross_weight'
  )
  product_weight_in_lbs = fields.Selection(
    related='ek_product_packagens_goods_id.product_weight_in_lbs'
  )
  ek_product_packagens_goods_id = fields.Many2one(
    'ek.product.packagens.goods', 'Container'
  )
  quantity_hand = fields.Float(
    related='ek_product_packagens_goods_id.quantity_hand'
  )
  invoice_number = fields.Char(
    related='ek_product_packagens_goods_id.invoice_number'
  )
  supplier = fields.Char(related='ek_product_packagens_goods_id.supplier')

  fob = fields.Float(related='ek_product_packagens_goods_id.fob')
  total_fob = fields.Float(related='ek_product_packagens_goods_id.total_fob')

  def delete_table_60(self):
    records = self.browse(self.env.context.get('active_ids'))
    if records:
      records.unlink()


class EkInvoiceShipMap(models.Model):
  _name = 'ek.invoice.ship.map'
  _description = 'Mapeo Factura-Buque'
  _rec_name = 'invoice_number'

  invoice_number = fields.Char('Factura', required=True)
  supplier = fields.Char('Proveedor', required=True)
  ship_id = fields.Many2one('ek.ship.registration', string='Buque')
  operation_request_id = fields.Many2one(
    'ek.operation.request',
    string='Operación',
    required=True,
    ondelete='cascade',
  )


class CustomsAgentData(models.Model):
  _name = 'ek.customs.agent.data'
  _description = 'Datos de Agencia Aduanal'

  operation_request_id = fields.Many2one(
    'ek.operation.request',
    string='Operación',
    required=True,
  )

  # Campos de importación de Excel (H35, H34, H02, H06, H25, H18)
  icl_pvdr_nm_01 = fields.Char(
    string='Proveedor'
  )  # H35. Nombre/razón social del proveedor
  icl_item_inv_no = fields.Char(string='Factura')  # H34. Número de factura
  icl_hs_part_cd = fields.Char(string='Subpartida')  # H02. Subpartida
  icl_gds_desc_cn = fields.Char(string='Descripción')  # H06. Descripción
  icl_item_fobv_pr = fields.Float(string='FOB Item')  # H25. FOB - item
  icl_phsc_pck_ut_co = fields.Float(
    string='Cantidad'
  )  # H18. Cantidad de unidades físicas

  # Campos de compatibilidad (mantener los existentes)
  supplier = fields.Char(
    string='Proveedor', compute='_compute_supplier', store=True
  )
  invoice_number = fields.Char(
    string='Factura', compute='_compute_invoice_number', store=True
  )
  product_name = fields.Char(
    string='Producto', compute='_compute_product_name', store=True
  )
  ship_name_id = fields.Many2one('ek.ship.registration', string='Buque')

  # Estado de matching
  match_status = fields.Selection(
    [
      ('exact', 'Exacto'),
      ('fuzzy', 'Tolerante'),
      ('no_match', 'Sin Match'),
      ('pending', 'Pendiente'),
    ],
    string='Estado Match',
    default='pending',
  )

  match_percentage = fields.Float(string='% Similitud')
  matched_product_id = fields.Many2one(
    'ek.product.packagens.goods', string='Producto Matched'
  )

  @api.depends('icl_pvdr_nm_01')
  def _compute_supplier(self):
    for record in self:
      record.supplier = record.icl_pvdr_nm_01

  @api.depends('icl_item_inv_no')
  def _compute_invoice_number(self):
    for record in self:
      record.invoice_number = record.icl_item_inv_no

  @api.depends('icl_gds_desc_cn')
  def _compute_product_name(self):
    for record in self:
      record.product_name = record.icl_gds_desc_cn
