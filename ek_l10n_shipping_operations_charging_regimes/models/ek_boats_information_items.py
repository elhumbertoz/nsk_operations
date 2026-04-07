# -*- coding: utf-8 -*-
from odoo import models, fields, api
from difflib import SequenceMatcher
import logging

_logger = logging.getLogger(__name__)


class ek_product_packagens_goods(models.Model):
  _inherit = 'ek.product.packagens.goods'

  # NUEVO: Vinculación a producto real del catálogo
  product_id = fields.Many2one(
    'product.product',
    string='Producto',
    required=False,
    domain=[('purchase_ok', '=', True)],
    help="Producto del catálogo de inventario. Se crea automáticamente si no existe."
  )

  # Campos relacionados del producto (lectura rápida)
  product_default_code = fields.Char(
    related='product_id.default_code',
    string='Código',
    store=True,
    readonly=True
  )

  # Nota: product.product no tiene hs_code por defecto
  # Usar tariff_item para código arancelario

  product_standard_price = fields.Float(
    related='product_id.standard_price',
    string='Costo Estándar',
    store=True,
    readonly=True
  )

  tariff_item = fields.Char(
    'Tariff Item',
  )
  id_hs_copmt_cd = fields.Char(
    'Complementary Code',
  )
  id_hs_spmt_cd = fields.Char(
    'Supplementary Code',
  )
  uom_id = fields.Many2one(
    'uom.uom',
    'Uom',
  )
  fob = fields.Float(
    'Fob',
  )
  total_fob = fields.Float('Total Fob', compute='_compute_total_fob')
  invoice_number = fields.Char('Invoice Number', required=False)
  supplier = fields.Char('Supplier', required=False)
  ek_ship_registration_id = fields.Many2one(
    'ek.ship.registration', 'Ship', copy=False
  )
  ek_boats_information_id = fields.Many2one(
    'ek.boats.information', 'Container', copy=False
  )
  date_request = fields.Datetime('Date Request', required=False)
  delivery_product = fields.Float(
    'Delivery Product',
    required=False,
  )
  quantity_hand = fields.Float(
    'Quantity Hand', required=False, compute='_get_quantiy_for_consume'
  )
  max_regime_date = fields.Datetime('Max Regime Date', required=False)
  number_dai = fields.Char('Number Dai', required=False)
  # assigned_regimen_70 = fields.Boolean(related="ek_boats_information_id.assigned_regimen_70")

  # ============================================================
  # CAMPOS NUEVOS REQ-009, REQ-006A, REQ-006B
  # ============================================================

  # REQ-009: Campos adicionales
  packages_count = fields.Integer(
    string="Bultos",
    default=0,
    help="Número de bultos/paquetes"
  )

  commercial_unit = fields.Char(
    string="Unidad Comercial",
    help="Unidad de medida comercial"
  )

  observation = fields.Text(
    string="Observaciones",
    help="Observaciones adicionales sobre el producto"
  )

  # REQ-006A: Buque Destino
  ship_id = fields.Many2one(
    'ek.ship.registration',
    string="Buque Destino",
    help="Buque para el cual está destinado este producto/repuesto"
  )

  # REQ-006B: Validación contra Nota de Pedido
  is_validated = fields.Boolean(
    string="Validado",
    default=False,
    help="Indica si esta línea fue validada contra Nota de Pedido"
  )

  validation_status = fields.Selection([
    ('pending', 'Pendiente'),
    ('match', 'Coincide'),
    ('mismatch', 'No Coincide'),
    ('manual', 'Validado Manualmente')
  ], string="Estado Validación", default='pending',
     help="Estado de validación contra Nota de Pedido del agente aduanero")

  validation_notes = fields.Text(
    string="Notas de Validación",
    help="Diferencias encontradas entre factura y Nota de Pedido"
  )

  po_line_reference = fields.Char(
    string="Ref. Nota de Pedido",
    help="Número de ítem/línea en la Nota de Pedido"
  )

  @api.depends('quantity', 'fob')
  def _compute_total_fob(self):
    for rec in self:
      rec.total_fob = rec.quantity * rec.fob

  @api.depends('quantity', 'delivery_product')
  def _get_quantiy_for_consume(self):
    for rec in self:
      rec.quantity_hand = rec.quantity - rec.delivery_product

  @api.onchange('product_id')
  def _onchange_product_id(self):
    """Auto-llenar campos desde producto"""
    if self.product_id:
      self.name = self.product_id.name

      # Auto-llenar default_code como referencia si no hay tariff_item
      if self.product_id.default_code and not self.tariff_item:
        # Intentar extraer código arancelario del código de producto si existe
        # (esto es opcional, depende de la estructura de default_code)
        pass

  @api.model
  def _find_or_create_product(self, vals):
    """
    Buscar producto existente o crear automáticamente

    Búsqueda en este orden:
    1. Búsqueda exacta por nombre
    2. Búsqueda por código arancelario (HS code)
    3. Búsqueda por similitud (fuzzy matching > 85%)
    4. Si no existe → Crear automáticamente

    Args:
        vals: Dict con 'name', 'tariff_item', 'fob', 'quantity'

    Returns:
        int: ID del producto encontrado/creado o False
    """
    description = vals.get('name', '').strip()
    hs_code = vals.get('tariff_item', '') or vals.get('id_hs_copmt_cd', '')
    fob = vals.get('fob') or 0.0
    quantity = vals.get('quantity') or 1.0
    fob_unit = fob / quantity if quantity else fob

    if not description:
      return False

    # 1. Búsqueda exacta por nombre
    product = self.env['product.product'].search([
      ('name', '=ilike', description)
    ], limit=1)

    if product:
      return product.id

    # 2. Búsqueda por código arancelario (coincidencia exacta + verificación de nombre)
    # Nota: product.product estándar no tiene hs_code; usamos default_code REG70-{hs_code}
    if hs_code:
      product = self.env['product.product'].search([
        ('default_code', '=like', f'REG70-{hs_code}%')
      ], limit=50)

      # Si hay candidatos, verificar similitud de nombre antes de confirmar
      best_hs_match = None
      best_hs_score = 0
      for prod in product:
        similarity = SequenceMatcher(
          None, prod.name.upper(), description.upper()
        ).ratio()
        if similarity > best_hs_score:
          best_hs_score = similarity
          best_hs_match = prod

      # Umbral permisivo: mismo HS + nombre medianamente parecido
      if best_hs_match and best_hs_score > 0.60:
        return best_hs_match.id

    # 3. Búsqueda por similitud (fuzzy matching) en todos los productos REG70
    category = self.env.ref(
      'ek_l10n_shipping_operations_charging_regimes.product_category_regime_70',
      raise_if_not_found=False
    )

    search_domain = [('categ_id', '=', category.id)] if category else []
    products = self.env['product.product'].search(search_domain, limit=200)

    best_match = None
    best_score = 0

    for prod in products:
      similarity = SequenceMatcher(
        None,
        prod.name.upper(),
        description.upper()
      ).ratio()

      if similarity > best_score:
        best_score = similarity
        best_match = prod

    # Si similitud > 85%, usar ese producto
    if best_score > 0.85:
      return best_match.id

    # Zona gris: advertir posible duplicado pero crear nuevo
    if 0.70 < best_score <= 0.85 and best_match:
      _logger.warning(
        "Producto '%s' tiene similitud %.0f%% con '%s' (id=%s). "
        "Se crea nuevo producto. Revisar si es duplicado.",
        description, best_score * 100, best_match.name, best_match.id
      )

    # 4. NO ENCONTRADO → Crear automáticamente
    return self._create_product_auto(description, hs_code, fob_unit)

  @api.model
  def _create_product_auto(self, description, hs_code, fob_unit):
    """Crear producto automáticamente como CONSUMIBLE (no stockeable)"""

    # Obtener categoría Régimen 70
    category = self.env.ref(
      'ek_l10n_shipping_operations_charging_regimes.product_category_regime_70',
      raise_if_not_found=False
    )

    if not category:
      # Si no existe la categoría, usar categoría por defecto
      category = self.env.ref('product.product_category_all')

    # Tag Régimen 70
    tag = self.env.ref(
      'ek_l10n_shipping_operations_charging_regimes.product_tag_regime_70',
      raise_if_not_found=False
    )

    # Crear producto CONSUMIBLE (no afecta inventario contable)
    product_vals = {
      'name': description[:255],  # Limitar longitud
      'categ_id': category.id,
      'type': 'consu',  # CONSUMIBLE - NO stockeable
      'detailed_type': 'consu',
      'purchase_ok': True,
      'sale_ok': True,
      'standard_price': fob_unit,
      'list_price': fob_unit * 1.2,  # 20% markup por defecto
      'uom_id': self.env.ref('uom.product_uom_unit').id,
      'uom_po_id': self.env.ref('uom.product_uom_unit').id,
    }

    # Agregar HS code al default_code garantizando unicidad
    # Nota: product.product estándar no tiene campo hs_code nativo
    if hs_code:
      base_code = f'REG70-{hs_code}'
      existing = self.env['product.product'].search([
        ('default_code', '=like', f'{base_code}%')
      ], limit=50)
      if not existing:
        product_vals['default_code'] = base_code
      else:
        product_vals['default_code'] = f'{base_code}-{len(existing) + 1:02d}'
    else:
      # Generar código secuencial
      seq = self.env['ir.sequence'].next_by_code('product.product') or '001'
      product_vals['default_code'] = f'REG70-{seq}'

    product = self.env['product.product'].create(product_vals)

    # Agregar tag
    if tag:
      product.product_tag_ids = [(4, tag.id)]

    return product.id

  @api.model
  def create(self, vals):
    """Override create para búsqueda/creación automática de producto"""

    # Si no viene product_id pero sí viene descripción (name)
    if not vals.get('product_id') and vals.get('name'):
      product_id = self._find_or_create_product(vals)
      if product_id:
        vals['product_id'] = product_id

    return super().create(vals)
