# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError
from difflib import SequenceMatcher
import json
import logging

_logger = logging.getLogger(__name__)


class EkInvoiceValidationWizard(models.TransientModel):
    """
    Wizard para validar productos de la factura contra la Nota de Pedido del agente aduanero
    REQ-015A: Wizard de Validación de Factura vs Nota de Pedido
    """
    _name = 'ek.invoice.validation.wizard'
    _description = 'Wizard de Validación Factura vs Nota de Pedido'

    operation_request_id = fields.Many2one(
        'ek.operation.request',
        string='Solicitud',
        required=True,
        readonly=True
    )

    invoice_data = fields.Text(
        string='Datos Factura',
        readonly=True,
        help="Datos extraídos de la factura"
    )

    po_data = fields.Text(
        string='Datos Nota Pedido',
        readonly=True,
        help="Datos extraídos de la Nota de Pedido"
    )

    validation_line_ids = fields.One2many(
        'ek.invoice.validation.line.wizard',
        'wizard_id',
        string="Líneas de Validación"
    )

    # Contadores de resumen
    total_lines = fields.Integer(
        string="Total Líneas",
        compute='_compute_summary',
        store=False
    )

    exact_matches = fields.Integer(
        string="Coincidencias Exactas",
        compute='_compute_summary',
        store=False
    )

    minor_diff = fields.Integer(
        string="Diferencias Menores",
        compute='_compute_summary',
        store=False
    )

    major_diff = fields.Integer(
        string="Diferencias Significativas",
        compute='_compute_summary',
        store=False
    )

    missing_in_po = fields.Integer(
        string="No en Nota Pedido",
        compute='_compute_summary',
        store=False
    )

    @api.depends('validation_line_ids.validation_status')
    def _compute_summary(self):
        """Calcular resumen de estados de validación"""
        for wizard in self:
            wizard.total_lines = len(wizard.validation_line_ids)
            wizard.exact_matches = len(wizard.validation_line_ids.filtered(lambda l: l.validation_status == 'match'))
            wizard.minor_diff = len(wizard.validation_line_ids.filtered(lambda l: l.validation_status == 'minor'))
            wizard.major_diff = len(wizard.validation_line_ids.filtered(lambda l: l.validation_status == 'major'))
            wizard.missing_in_po = len(wizard.validation_line_ids.filtered(lambda l: l.validation_status == 'missing'))

    @api.model
    def default_get(self, fields_list):
        """Cargar datos al abrir el wizard"""
        res = super().default_get(fields_list)

        # Obtener solicitud desde contexto
        operation_id = self.env.context.get('active_id')
        if not operation_id:
            raise UserError(_('No se encontró la solicitud'))

        operation = self.env['ek.operation.request'].browse(operation_id)

        # Validar que exista nota de pedido
        if not operation.purchase_order_data:
            raise UserError(_('Debe cargar y procesar la Nota de Pedido primero'))

        res['operation_request_id'] = operation_id

        return res

    def action_compare_documents(self):
        """Comparar factura vs Nota de Pedido automáticamente"""
        self.ensure_one()

        # Limpiar líneas anteriores
        self.validation_line_ids.unlink()

        # Obtener líneas de productos de la factura
        goods_lines = self.operation_request_id.ek_produc_packages_goods_ids

        if not goods_lines:
            raise UserError(_('No hay productos en la factura para validar'))

        # TODO: Parsear JSON de purchase_order_data cuando esté implementado
        # Por ahora, crear líneas de validación sin datos de PO
        validation_lines = []

        for line in goods_lines:
            # Crear línea de validación
            val_line = {
                'goods_line_id': line.id,
                'invoice_description': line.name or '',
                'invoice_quantity': line.quantity or 0,
                'invoice_weight': line.gross_weight or 0,
                'invoice_fob': line.total_fob or 0,
                'validation_status': 'pending',
                'differences': 'Pendiente de comparación',
            }

            validation_lines.append((0, 0, val_line))

        self.validation_line_ids = validation_lines

        return {
            'type': 'ir.actions.act_window',
            'res_model': 'ek.invoice.validation.wizard',
            'view_mode': 'form',
            'res_id': self.id,
            'target': 'new',
            'context': self.env.context,
        }

    def action_validate_matches(self):
        """Validar solo líneas con coincidencias exactas"""
        self.ensure_one()

        lines_to_validate = self.validation_line_ids.filtered(lambda l: l.validation_status == 'match')

        if not lines_to_validate:
            raise UserError(_('No hay líneas con coincidencias exactas'))

        self._validate_lines(lines_to_validate)

        return self._close_wizard_with_message(
            _('Se validaron %s líneas con coincidencias exactas') % len(lines_to_validate)
        )

    def action_validate_with_minor_diff(self):
        """Validar coincidencias exactas + diferencias menores"""
        self.ensure_one()

        lines_to_validate = self.validation_line_ids.filtered(
            lambda l: l.validation_status in ('match', 'minor')
        )

        if not lines_to_validate:
            raise UserError(_('No hay líneas para validar'))

        self._validate_lines(lines_to_validate)

        return self._close_wizard_with_message(
            _('Se validaron %s líneas (coincidencias + diferencias menores)') % len(lines_to_validate)
        )

    def action_validate_all(self):
        """Validar todas las líneas (requiere confirmación)"""
        self.ensure_one()

        # Confirmar si hay diferencias significativas
        if self.major_diff > 0:
            raise UserError(_(
                'Hay %s líneas con diferencias significativas. '
                'Debe validarlas individualmente o usar "Validar Seleccionadas".'
            ) % self.major_diff)

        self._validate_lines(self.validation_line_ids)

        return self._close_wizard_with_message(
            _('Se validaron todas las %s líneas') % len(self.validation_line_ids)
        )

    def action_validate_selected(self):
        """Validar solo líneas marcadas con validate_anyway"""
        self.ensure_one()

        lines_to_validate = self.validation_line_ids.filtered(lambda l: l.validate_anyway)

        if not lines_to_validate:
            raise UserError(_('Debe marcar al menos una línea para validar'))

        self._validate_lines(lines_to_validate)

        return self._close_wizard_with_message(
            _('Se validaron %s líneas seleccionadas') % len(lines_to_validate)
        )

    def _validate_lines(self, lines):
        """Actualizar estados de validación en líneas de productos"""
        for line in lines:
            if line.goods_line_id:
                line.goods_line_id.write({
                    'is_validated': True,
                    'validation_status': 'match' if line.validation_status in ('match', 'minor') else 'manual',
                    'validation_notes': line.differences or '',
                    'po_line_reference': line.po_item_number or '',
                })

        # Verificar si todas las líneas están validadas
        all_lines = self.operation_request_id.ek_produc_packages_goods_ids
        all_validated = all(line.is_validated for line in all_lines)

        if all_validated:
            self.operation_request_id.invoice_validated = True

        # Log en chatter
        self.operation_request_id.message_post(
            body=_(
                'Validación completada: %s coincidencias, %s diferencias menores, %s diferencias mayores'
            ) % (self.exact_matches, self.minor_diff, self.major_diff)
        )

    def _compare_with_ai(self, po_data):
        """
        Compara productos de factura vs Nota de Pedido usando IA
        REQ-005, REQ-006: Comparación inteligente con matching
        """
        self.ensure_one()

        # Obtener productos de la factura
        invoice_lines = self.operation_request_id.ek_produc_packages_goods_ids

        if not invoice_lines:
            raise UserError(_('No hay productos en la factura para validar'))

        # Preparar datos para la IA
        invoice_data = []
        for line in invoice_lines:
            invoice_data.append({
                'id': line.id,
                'description': line.name or '',
                'quantity': line.quantity or 0,
                'weight_kg': line.gross_weight or 0,
                'fob': line.total_fob or 0,
                'hs_code': line.tariff_item or '',
            })

        po_items = po_data.get('items', [])

        # Llamar a IA para matching inteligente
        try:
            llm = self.env['nsk.llm.provider']

            messages = [
                {
                    "role": "system",
                    "content": """Eres un experto en documentación aduanera. Compara productos de FACTURA vs NOTA DE PEDIDO.

CRITERIOS:
- MATCH: Coincidencia ≥98% en valores
- MINOR: Diferencias ≤5%
- MAJOR: Diferencias >5%
- MISSING: No encontrado en PO

Usa fuzzy matching para descripciones."""
                },
                {
                    "role": "user",
                    "content": f"""Compara:

FACTURA: {json.dumps(invoice_data, indent=2, ensure_ascii=False)}

NOTA PEDIDO: {json.dumps(po_items, indent=2, ensure_ascii=False)}

Devuelve JSON array con: invoice_id, po_match_index, status, differences, confidence"""
                }
            ]

            response = llm.generate_completion(messages=messages)
            content = response.choices[0].message.content

            # Parsear JSON
            if '```json' in content:
                json_str = content.split('```json')[1].split('```')[0].strip()
            elif '```' in content:
                json_str = content.split('```')[1].split('```')[0].strip()
            else:
                json_str = content.strip()

            comparisons = json.loads(json_str)

            # Crear líneas
            validation_lines = []
            for comp in comparisons:
                invoice_id = comp.get('invoice_id')
                po_match_idx = comp.get('po_match_index', -1)
                status = comp.get('status', 'missing')

                invoice_line = invoice_lines.filtered(lambda l: l.id == invoice_id)
                if not invoice_line:
                    continue

                po_item = None
                if po_match_idx >= 0 and po_match_idx < len(po_items):
                    po_item = po_items[po_match_idx]

                val_line = {
                    'goods_line_id': invoice_line.id,
                    'invoice_description': invoice_line.name or '',
                    'invoice_quantity': invoice_line.quantity or 0,
                    'invoice_weight': invoice_line.gross_weight or 0,
                    'invoice_fob': invoice_line.total_fob or 0,
                    'validation_status': status,
                    'differences': comp.get('differences', ''),
                }

                if po_item:
                    val_line.update({
                        'po_item_number': po_item.get('item_number', ''),
                        'po_description': po_item.get('description', ''),
                        'po_quantity': po_item.get('quantity', 0),
                        'po_weight': po_item.get('weight_kg', 0),
                        'po_fob': po_item.get('fob_value', 0),
                    })

                validation_lines.append((0, 0, val_line))

            self.validation_line_ids = validation_lines
            _logger.info(f"Comparación IA: {len(comparisons)} productos")

        except Exception as e:
            _logger.error(f"Error comparación IA: {str(e)}")
            # Fallback manual
            self._fallback_manual_comparison(invoice_lines, po_items)

    def _fallback_manual_comparison(self, invoice_lines, po_items):
        """Comparación básica sin IA (fallback)"""
        validation_lines = []

        for inv_line in invoice_lines:
            best_match = None
            best_ratio = 0

            for idx, po_item in enumerate(po_items):
                ratio = SequenceMatcher(
                    None,
                    inv_line.name.lower() if inv_line.name else '',
                    po_item.get('description', '').lower()
                ).ratio()

                if ratio > best_ratio:
                    best_ratio = ratio
                    best_match = (idx, po_item)

            if best_ratio > 0.85:
                status = 'match'
            elif best_ratio > 0.70:
                status = 'minor'
            else:
                status = 'missing'

            val_line = {
                'goods_line_id': inv_line.id,
                'invoice_description': inv_line.name or '',
                'invoice_quantity': inv_line.quantity or 0,
                'invoice_weight': inv_line.gross_weight or 0,
                'invoice_fob': inv_line.total_fob or 0,
                'validation_status': status,
                'differences': f'Similitud: {best_ratio*100:.0f}%',
            }

            if best_match:
                po_item = best_match[1]
                val_line.update({
                    'po_item_number': po_item.get('item_number', ''),
                    'po_description': po_item.get('description', ''),
                    'po_quantity': po_item.get('quantity', 0),
                    'po_weight': po_item.get('weight_kg', 0),
                    'po_fob': po_item.get('fob_value', 0),
                })

            validation_lines.append((0, 0, val_line))

        self.validation_line_ids = validation_lines

    def _close_wizard_with_message(self, message):
        """Cerrar wizard y mostrar mensaje"""
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Validación Completada'),
                'message': message,
                'type': 'success',
                'sticky': False,
            }
        }


class EkInvoiceValidationLineWizard(models.TransientModel):
    """
    Líneas de validación individual para comparación
    REQ-015A: Modelo de Líneas de Validación
    """
    _name = 'ek.invoice.validation.line.wizard'
    _description = 'Línea de Validación Factura vs Nota Pedido'

    wizard_id = fields.Many2one(
        'ek.invoice.validation.wizard',
        required=True,
        ondelete='cascade'
    )

    goods_line_id = fields.Many2one(
        'ek.product.packagens.goods',
        string='Línea de Mercancía',
        readonly=True
    )

    # Datos de factura
    invoice_description = fields.Char(
        string='Descripción Factura',
        readonly=True
    )

    invoice_quantity = fields.Float(
        string='Cantidad Factura',
        readonly=True
    )

    invoice_weight = fields.Float(
        string='Peso Factura',
        readonly=True
    )

    invoice_fob = fields.Float(
        string='FOB Factura',
        readonly=True
    )

    # Datos de Nota de Pedido
    po_item_number = fields.Char(
        string='# Ítem PO',
        readonly=True
    )

    po_description = fields.Char(
        string='Descripción PO',
        readonly=True
    )

    po_quantity = fields.Float(
        string='Cantidad PO',
        readonly=True
    )

    po_weight = fields.Float(
        string='Peso PO',
        readonly=True
    )

    po_fob = fields.Float(
        string='FOB PO',
        readonly=True
    )

    # Resultado de validación
    validation_status = fields.Selection([
        ('match', 'Coincide'),
        ('minor', 'Diferencia Menor'),
        ('major', 'Diferencia Significativa'),
        ('missing', 'No en Nota Pedido')
    ], string='Estado', readonly=True, default='match')

    differences = fields.Text(
        string='Diferencias',
        readonly=True
    )

    validate_anyway = fields.Boolean(
        string='Validar de todos modos',
        help='Marque para validar esta línea incluso con diferencias'
    )
