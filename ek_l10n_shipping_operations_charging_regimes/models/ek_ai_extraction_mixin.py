# -*- coding: utf-8 -*-
from markupsafe import Markup
from odoo import models, fields, api, _
from odoo.exceptions import UserError
import json
import logging

_logger = logging.getLogger(__name__)


class EkAIExtractionMixin(models.AbstractModel):
    """
    Mixin para extracción de datos de documentos usando IA (ChatGPT/Claude)
    REQ-001 a REQ-006: Integración con nsk_llm para extracción automática
    """
    _name = 'ek.ai.extraction.mixin'
    _description = 'AI Document Extraction Mixin'

    # Campo para adjuntar BL
    bl_attachment_ids = fields.Many2many(
        'ir.attachment',
        'ek_operation_bl_attachment_rel',
        'operation_id',
        'attachment_id',
        string='Bill of Lading (PDF)',
        help='Adjunte el documento BL para extracción automática con IA'
    )

    # Campo para adjuntar facturas
    invoice_attachment_ids = fields.Many2many(
        'ir.attachment',
        'ek_operation_invoice_attachment_rel',
        'operation_id',
        'attachment_id',
        string='Facturas Comerciales',
        help='Adjunte las facturas comerciales para extracción automática'
    )

    # Campos de control de extracción
    ai_extraction_status = fields.Selection([
        ('pending', 'Pendiente'),
        ('processing', 'Procesando'),
        ('completed', 'Completado'),
        ('error', 'Error')
    ], string='Estado Extracción IA (General)', default='pending', tracking=True)

    ai_extraction_status_bl = fields.Selection([
        ('pending', 'Pendiente'),
        ('processing', 'Procesando'),
        ('completed', 'Completado'),
        ('error', 'Error')
    ], string='Estado BL', default='pending', tracking=True)

    ai_extraction_status_fc = fields.Selection([
        ('pending', 'Pendiente'),
        ('processing', 'Procesando'),
        ('completed', 'Completado'),
        ('error', 'Error')
    ], string='Estado Facturas', default='pending', tracking=True)

    ai_extraction_status_np = fields.Selection([
        ('pending', 'Pendiente'),
        ('processing', 'Procesando'),
        ('completed', 'Completado'),
        ('error', 'Error')
    ], string='Estado Nota Pedido', default='pending', tracking=True)

    ai_extraction_log = fields.Html(
        string='Resultado de Extracción',
        readonly=True,
        help='Muestra el resultado estructurado de la última operación de IA'
    )

    def _get_regime_70_catalog_prompt(self):
        """
        Genera un string con el catálogo actual de productos Régimen 70 para el prompt de la IA
        """
        category = self.env.ref('ek_l10n_shipping_operations_charging_regimes.product_category_regime_70', raise_if_not_found=False)
        domain = [('categ_id', '=', category.id)] if category else []
        products = self.env['product.product'].search(domain)
        
        if not products:
            return "No hay productos registrados actualmente en el catálogo de Régimen 70."
            
        catalog_lines = [
            "A continuación se presenta el catálogo de REGIMEN 70 existente.",
            "Si el producto de la factura coincide con uno de estos, devuelve su ID.",
            "ID | CÓDIGO | NOMBRE"
        ]
        for p in products:
            code = p.default_code or 'S/N'
            catalog_lines.append(f"{p.id} | {code} | {p.name}")
            
        return "\n".join(catalog_lines)


    def _get_bl_extraction_tool_definition(self):
        """
        Define la herramienta (tool) para extracción de datos del BL
        REQ-001, REQ-002, REQ-003: Extracción de BL
        """
        return {
            "type": "function",
            "function": {
                "name": "extract_bl_data",
                "description": "Extrae datos estructurados de un Bill of Lading (BL) marítimo",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "id_bl": {
                            "type": "string",
                            "description": "Número del Bill of Lading o ID del contenedor"
                        },
                        "number_container": {
                            "type": "string",
                            "description": "Número del contenedor (formato: XXXX1234567)"
                        },
                        "shipping_line": {
                            "type": "string",
                            "description": "Nombre de la línea naviera (ej: Maersk, MSC, CMA CGM)"
                        },
                        "eta": {
                            "type": "string",
                            "description": "Estimated Time of Arrival (formato: YYYY-MM-DD)"
                        },
                        "etd": {
                            "type": "string",
                            "description": "Estimated Time of Departure (formato: YYYY-MM-DD)"
                        },
                        "supplies_detail": {
                            "type": "string",
                            "description": "Descripción generalizada de la carga (ej: 'Maquinaria industrial y repuestos', 'Electrodomésticos y accesorios'). NO listar productos individuales, resumir en una frase corta qué tipo de mercancía se transporta."
                        },
                        "total_weight": {
                            "type": "number",
                            "description": "Peso total en kilogramos"
                        },
                        "total_packages": {
                            "type": "integer",
                            "description": "Cantidad total de bultos/paquetes"
                        },
                        "invoice_numbers": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Lista de números de factura mencionados"
                        },
                        "packages": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "description": {"type": "string"},
                                    "hs_code": {"type": "string"},
                                    "quantity": {"type": "number"},
                                    "weight_kg": {"type": "number"},
                                    "invoice_number": {"type": "string"},
                                    "supplier": {"type": "string"},
                                    "product_id": {
                                        "type": "integer",
                                        "description": "ID del producto en el catálogo (similitud > 70%)."
                                    },
                                    "match_confidence": {
                                        "type": "number",
                                        "description": "Nivel de confianza del matching (0.0 a 1.0)."
                                    }
                                }
                            },
                            "description": "Lista detallada de productos/paquetes en el contenedor"
                        },
                    },
                    "required": ["id_bl"]
                }
            }
        }

    def _get_invoice_extraction_tool_definition(self):
        """
        Define la herramienta para extracción de datos de facturas
        REQ-004: Extracción de Factura Comercial
        """
        return {
            "type": "function",
            "function": {
                "name": "extract_invoice_data",
                "description": "Extrae datos estructurados de una factura comercial",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "invoice_number": {
                            "type": "string",
                            "description": "Número de factura"
                        },
                        "invoice_date": {
                            "type": "string",
                            "description": "Fecha de la factura (YYYY-MM-DD)"
                        },
                        "supplier": {
                            "type": "string",
                            "description": "Nombre del proveedor/vendedor"
                        },
                        "currency": {
                            "type": "string",
                            "description": "Moneda (USD, EUR, etc.)"
                        },
                        "items": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "line_number": {"type": "integer"},
                                    "description": {
                                        "type": "string",
                                        "description": (
                                            "Raw product description exactly as it appears in the document. "
                                            "Do NOT truncate or rephrase — preserve the full original text for audit purposes."
                                        )
                                    },
                                    "product_name": {
                                        "type": "string",
                                        "description": (
                                            "Normalized, human-readable product name following the pattern: "
                                            "[Product Type] [Brand] [Model] [Key Spec]. "
                                            "Rules: (1) Be concise — max ~60 chars. "
                                            "(2) Omit verbose legal text, part numbers, addresses, and generic filler words. "
                                            "(3) Preserve the brand and model when present — they are the most identifying attributes. "
                                            "(4) Include only the single most discriminating specification (e.g., power rating, size, voltage). "
                                            "Examples: 'Electric Motor WEG W22 7.5HP 4P', 'Hydraulic Pump Bosch Rexroth A10V 45cc', "
                                            "'Spare Part SKF Bearing 6205-2RS'."
                                        )
                                    },
                                    "hs_code": {
                                        "type": "string",
                                        "description": "Código arancelario (HS Code) para clasificación aduanera."
                                    },
                                    "quantity": {"type": "number"},
                                    "unit_price_fob": {"type": "number"},
                                    "total_fob": {"type": "number"},
                                    "weight_kg": {"type": "number"},
                                    "packages_count": {"type": "integer"},
                                    "ship_name": {
                                        "type": "string",
                                        "description": (
                                            "Nombre del buque destino si se menciona explícitamente "
                                            "(ej: 'FOR VESSEL ...', 'PARA BUQUE ...')."
                                        )
                                    },
                                    "product_id": {
                                        "type": "integer",
                                        "description": "ID del producto en el catálogo si se encontró una coincidencia razonable (similitud > 70%)."
                                    },
                                    "match_confidence": {
                                        "type": "number",
                                        "description": "Nivel de confianza del matching con el catálogo proporcionado (0.0 a 1.0)."
                                    }
                                },
                                "required": ["description", "quantity", "total_fob"]
                            },
                            "description": "Lista de productos/items en la factura. Es CRÍTICO extraer la descripción completa para el matching de catálogo."
                        },
                        "subtotal": {"type": "number"},
                        "total": {"type": "number"},
                    },
                    "required": ["invoice_number", "supplier", "items"]
                }
            }
        }


    def _get_po_extraction_tool_definition(self):
        """
        Define la herramienta para extracción de Nota de Pedido del agente aduanero
        REQ-005, REQ-006: Extracción de Nota de Pedido
        """
        return {
            "type": "function",
            "function": {
                "name": "extract_purchase_order_data",
                "description": "Extrae datos de la Nota de Pedido del agente aduanero",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "po_number": {
                            "type": "string",
                            "description": "Número de la Nota de Pedido"
                        },
                        "po_date": {
                            "type": "string",
                            "description": "Fecha de la Nota de Pedido"
                        },
                        "customs_agent": {
                            "type": "string",
                            "description": "Nombre del agente aduanero"
                        },
                        "items": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "item_number": {"type": "string"},
                                    "description": {"type": "string"},
                                    "hs_code": {"type": "string"},
                                    "quantity": {"type": "number"},
                                    "weight_kg": {"type": "number"},
                                    "fob_value": {"type": "number"}
                                },
                                "required": ["description", "quantity"]
                            }
                        },
                    },
                    "required": ["items"]
                }
            }
        }

    def action_extract_bl_with_ai(self):
        """
        Extrae datos del Bill of Lading usando IA (ChatGPT/Claude)
        REQ-001, REQ-002, REQ-003
        """
        self.ensure_one()

        if not self.bl_attachment_ids:
            raise UserError(_('Por favor adjunte el documento Bill of Lading (BL) antes de continuar.'))

        attachment = self.bl_attachment_ids[0]

        # Actualizar estado
        self.ai_extraction_status_bl = 'processing'
        self.ai_extraction_status = 'processing'

        try:
            # Obtener servicio de LLM
            llm = self.env['nsk.llm.provider']

            # Definir herramienta de extracción
            tools = [self._get_bl_extraction_tool_definition()]

            # Mensajes para el LLM
            messages = [
                {
                    "role": "system",
                    "content": f"""You are a senior maritime customs and logistics analyst with 20+ years of experience reading Bills of Lading, commercial invoices, and customs declarations.

Your task is to extract structured data from the attached Bill of Lading (BL) and, when possible, match each cargo item against the existing product catalog provided below.

## CATALOG MATCHING
{self._get_regime_70_catalog_prompt()}

Matching rules:
- If an item clearly corresponds to a catalog entry (confidence > 70%), return its `product_id`.
- If no clear match exists, omit `product_id` — never guess.
- `description`: copy the raw text verbatim from the BL (for audit trail).
- `product_name`: generate a normalized name following [Type] [Brand] [Model] [Key Spec].
- LANGUAGE: IMPORTANT — Keep the product name in the language of the source document. If the document is in Spanish, the name must be in Spanish.
  - Example (Spanish): "Motor Eléctrico WEG W22 7.5HP"
  - Example (English): "Electric Motor WEG W22 7.5HP"
  - Keep it under 60 characters and omit legal boilerplate and filler text.

Always call `extract_bl_data` to return structured results."""
                },
                {
                    "role": "user",
                    "content": """Por favor, extrae la siguiente información del Bill of Lading adjunto:

1. Número de BL / Contenedor
2. Línea naviera
3. Fechas ETA y ETD
4. Descripción general de la carga
5. TODOS los productos detallados con:
   - Descripción completa
   - Código HS (si existe)
   - Cantidad
   - Peso
   - Número de factura
   - Proveedor

El documento PDF está adjunto a este mensaje."""
                }
            ]

            _logger.info(f"Extrayendo datos de BL {attachment.name} usando IA...")

            response = llm.generate_completion(
                messages=messages,
                attachments=attachment,
                tools=tools
            )

            # Procesar respuesta con tool calling
            if not response.choices or not response.choices[0].message.tool_calls:
                raise UserError(_('La IA no pudo extraer datos del documento. Verifique que sea un BL válido.'))

            tool_call = response.choices[0].message.tool_calls[0]
            extracted_data = json.loads(tool_call.function.arguments)

            _logger.info(f"Datos extraídos exitosamente.")

            # Aplicar datos extraídos
            self._apply_bl_data(extracted_data, attachment)

            # Actualizar estado
            self.ai_extraction_status_bl = 'completed'
            self.ai_extraction_status = 'completed'

            # Log Elegante (HTML)
            packages = extracted_data.get('packages', [])
            html_log = f"""
                <div class="alert alert-success" role="alert">
                    <h4 class="alert-heading">Extracción de BL Completada</h4>
                    <p>Se procesó el documento <strong>{attachment.name}</strong>.</p>
                    <hr>
                    <table class="table table-sm table-borderless mb-0">
                        <tr><td><strong>BL#:</strong> {getattr(self, 'id_bl', 'N/A') or 'N/A'}</td><td><strong>Contenedor:</strong> {getattr(self, 'number_container', getattr(self, 'container_number', 'N/A')) or 'N/A'}</td></tr>
                        <tr><td><strong>Línea:</strong> {self.shipping_line_id.name if hasattr(self, 'shipping_line_id') and self.shipping_line_id else (self.shipping_company.name if hasattr(self, 'shipping_company') and self.shipping_company else 'No encontrada')}</td><td><strong>Productos:</strong> {len(packages)}</td></tr>
                    </table>
                </div>
                <div class="mt-3">
                    <h6>Detalle de Productos Extraídos:</h6>
                    <table class="table table-striped table-sm">
                        <thead>
                            <tr>
                                <th>Descripción</th>
                                <th>Cód. HS</th>
                                <th class="text-end">Cant.</th>
                                <th class="text-end">Peso (kg)</th>
                            </tr>
                        </thead>
                        <tbody>
            """
            for pkg in packages[:15]: # Limitar a 15 para no saturar
                html_log += f"""
                    <tr>
                        <td>{pkg.get('description', '')}</td>
                        <td><span class="badge bg-secondary">{pkg.get('hs_code', '')}</span></td>
                        <td class="text-end">{pkg.get('quantity') or 0}</td>
                        <td class="text-end">{pkg.get('weight_kg') or 0}</td>
                    </tr>
                """
            if len(packages) > 15:
                html_log += f'<tr><td colspan="4" class="text-center text-muted">... y {len(packages) - 15} productos más</td></tr>'
            
            html_log += "</tbody></table></div>"
            
            self.ai_extraction_log = html_log

            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Extracción Completada'),
                    'message': _('Se extrajeron %s productos del BL') % (
                        len(extracted_data.get('packages', []))
                    ),
                    'type': 'success',
                    'sticky': False,
                    'next': {'type': 'ir.actions.client', 'tag': 'reload'},
                }
            }

        except Exception as e:
            self.ai_extraction_status_bl = 'error'
            self.ai_extraction_status = 'error'
            error_msg = str(e)
            _logger.error(f"Error en extracción de BL: {error_msg}")

            self.ai_extraction_log = (self.ai_extraction_log or '') + f"\n=== ERROR - {fields.Datetime.now()} ===\n{error_msg}\n"

            raise UserError(_('Error al extraer datos del BL:\n\n%s\n\nVerifique:\n- Que nsk_llm esté configurado correctamente\n- Que el documento sea un PDF válido\n- Que el servidor tenga acceso a Internet') % error_msg)

    def _apply_bl_data(self, extracted_data, attachment):
        """
        Aplica los datos extraídos del BL al registro
        REQ-002: Aplicación de datos extraídos
        """
        # Actualizar campos del BL
        if extracted_data.get('id_bl'):
            self.id_bl = extracted_data['id_bl']

        if extracted_data.get('number_container'):
            if hasattr(self, 'number_container'):
                self.number_container = extracted_data['number_container']
            elif hasattr(self, 'container_number'):
                self.container_number = extracted_data['number_container']

        if extracted_data.get('eta'):
            try:
                # Odoo Datetime fields need string or datetime object. 
                # extracted_data['eta'] is likely a string YYYY-MM-DD
                self.eta = extracted_data['eta']
            except:
                _logger.warning(f"No se pudo parsear fecha ETA: {extracted_data['eta']}")

        if extracted_data.get('etd'):
            try:
                self.etd = fields.Date.from_string(extracted_data['etd'])
            except:
                _logger.warning(f"No se pudo parsear fecha ETD: {extracted_data['etd']}")

        if extracted_data.get('supplies_detail'):
            self.message_post(
                body=Markup(_('<strong>Descripción de carga:</strong> %s')) % extracted_data['supplies_detail'],
                message_type='comment',
                subtype_xmlid='mail.mt_note',
            )

        # Buscar línea naviera
        if extracted_data.get('shipping_line'):
            shipping_line = self.env['res.partner'].search([
                ('name', 'ilike', extracted_data['shipping_line']),
                ('is_company', '=', True)
            ], limit=1)

            if shipping_line:
                if hasattr(self, 'shipping_line_id'):
                    self.shipping_line_id = shipping_line.id
                elif hasattr(self, 'shipping_company'):
                    self.shipping_company = shipping_line.id
            else:
                _logger.info(f"Línea naviera no encontrada: {extracted_data['shipping_line']}")

        # Crear líneas de productos
        packages = extracted_data.get('packages', [])
        if packages:
            self._create_goods_lines_from_packages(packages)

        # Log en chatter
        attachment_name = self.bl_attachment_ids[0].name if self.bl_attachment_ids else 'N/A'
        self.message_post(
            body=Markup(_(
                '<strong>Extracción de BL completada con IA</strong><br/>'
                'Documento: %s<br/>'
                'Productos procesados: %s<br/>'
                'BL#: %s<br/>'
                'Contenedor: %s'
            ) % (
                attachment_name,
                len(packages),
                self.id_bl or 'N/A',
                self.number_container or 'N/A'
            ))
        )

        # Actualizar catálogo de productos en el padre
        self._sync_parent_product_ids()


    def _create_goods_lines_from_packages(self, packages):
        """
        Crea líneas de productos/mercancías desde datos extraídos
        REQ-003: Creación automática de líneas
        """
        goods_model = self.env['ek.product.packagens.goods']

        # Determinar modelo y campo padre
        is_request = self._name == 'ek.operation.request'
        parent_field = 'ek_operation_request_id' if is_request else 'ek_boats_information_id'

        for pkg in packages:
            # Use normalized product_name for display; keep raw description as audit trail
            raw_description = pkg.get('description', '')
            display_name = pkg.get('product_name') or raw_description
            line_vals = {
                parent_field: self.id,
                'name': display_name,
                'extracted_name': raw_description,
                'quantity': pkg.get('quantity') or 0,
                'gross_weight': pkg.get('weight_kg') or 0,
                'invoice_number': pkg.get('invoice_number', ''),
                'supplier': pkg.get('supplier', ''),
                'product_id': pkg.get('product_id'),
                'match_confidence': (pkg.get('match_confidence') or 0.0) * 100,
            }

            # HS Code
            if pkg.get('hs_code'):
                line_vals['tariff_item'] = pkg['hs_code']

            # Crear línea (el sistema buscará/creará producto automáticamente vía create override)
            goods_model.create(line_vals)


    def action_extract_invoices_with_ai(self):
        """
        Extrae datos de facturas comerciales usando IA
        REQ-004: Extracción de Facturas
        """
        self.ensure_one()

        if not self.invoice_attachment_ids:
            raise UserError(_('Por favor adjunte al menos una factura comercial antes de continuar.'))

        self.ai_extraction_status_fc = 'processing'
        self.ai_extraction_status = 'processing'

        try:
            llm = self.env['nsk.llm.provider']
            tools = [self._get_invoice_extraction_tool_definition()]

            all_items = []
            invoices_processed = 0

            # Procesar cada factura
            for invoice_att in self.invoice_attachment_ids:
                _logger.info(f"Extrayendo datos de factura: {invoice_att.name}")

                messages = [
                    {
                        "role": "system",
                        "content": f"""You are an expert commercial invoice analyst and inventory specialist for international maritime trade.

Your job has two parts:
1. **Extract** every line item from the attached commercial invoice with full precision.
2. **Match** each item against the existing Régimen 70 product catalog below.

## PRODUCT CATALOG
{self._get_regime_70_catalog_prompt()}

## MATCHING RULES
- Use the product name, context, and HS code together to find the best catalog match.
- Only set `product_id` when confidence exceeds 70% — never force a match.
- Set `match_confidence` between 0.0 and 1.0 (e.g., 0.95 = near-exact, 0.75 = reasonable).
- `description`: copy the raw line-item text exactly as printed in the invoice (for audit).
- `product_name`: generate a concise, normalized name using the pattern [Type] [Brand] [Model] [Key Spec].
- LANGUAGE: IMPORTANT — Keep the product name in the language of the source document. If the document is in Spanish, the name must be in Spanish.
  - Max ~60 characters. Omit serial numbers, lengthy specs, legal text, and addresses.
  - Retain brand and model — they are the most valuable identifiers.
  - Include only the single most discriminating spec (power, size, capacity, voltage, etc.).
  - EXAMPLE (Spanish): "Motor Eléctrico WEG W22 7.5HP 4P"
  - EXAMPLE (English): "Electric Motor WEG W22 7.5HP 4P"

## EXTRACTION RULES
- Extract all line items, quantities, and exact FOB prices.
- IMPORTANT: Do NOT extract items with zero price (0.00). If an item has no price or it is zero, skip it entirely.
- If the document explicitly mentions a destination vessel (e.g., "FOR VESSEL ATÚN I", "PARA BUQUE TXOPITUNA"), capture it in `ship_name`.

Always call `extract_invoice_data` to return structured results."""
                    },
                    {
                        "role": "user",
                        "content": "Extrae los datos de la factura comercial y realiza el matching con el catálogo proporcionado. El documento está adjunto."
                    }
                ]

                response = llm.generate_completion(
                    messages=messages,
                    attachments=invoice_att,
                    tools=tools
                )

                if response.choices and response.choices[0].message.tool_calls:
                    tool_call = response.choices[0].message.tool_calls[0]
                    invoice_data = json.loads(tool_call.function.arguments)

                    # Agregar items de esta factura
                    for item in invoice_data.get('items', []):
                        item['invoice_number'] = invoice_data.get('invoice_number', invoice_att.name)
                        item['supplier'] = invoice_data.get('supplier', '')
                        all_items.append(item)

                    invoices_processed += 1
                    _logger.info(f"Factura {invoice_att.name} procesada: {len(invoice_data.get('items', []))} items")

            # Crear líneas de productos
            if all_items:
                self._create_goods_lines_from_invoice_items(all_items)

            # Actualizar estado
            self.ai_extraction_status_fc = 'completed'
            self.ai_extraction_status = 'completed'

            # Log Elegante (HTML) con info de productos
            html_log = f"""
                <div class="alert alert-success" role="alert">
                    <h4 class="alert-heading">Extracción de Facturas Completada</h4>
                    <p>Se procesaron <strong>{invoices_processed}</strong> facturas. Los productos han sido sincronizados con el catálogo unificado de Régimen 70.</p>
                    <hr>
                    <table class="table table-sm table-borderless mb-0">
                        <tr><td><strong>Total Items:</strong> {len(all_items)}</td><td><strong>Estado:</strong> <span class="badge bg-success">Catálogo Sincronizado</span></td></tr>
                    </table>
                </div>
                <div class="mt-3">
                    <table class="table table-hover table-sm">
                        <thead class="table-light">
                            <tr>
                                <th>Descripción Extracción</th>
                                <th>Producto Catálogo</th>
                                <th class="text-end">Cant.</th>
                                <th class="text-end">FOB Total</th>
                            </tr>
                        </thead>
                        <tbody>
            """
            # Obtener las últimas líneas creadas para mostrar el matching real
            parent_field = 'ek_operation_request_id' if self._name == 'ek.operation.request' else 'ek_boats_information_id'
            recent_lines = self.env['ek.product.packagens.goods'].search([
                (parent_field, '=', self.id)
            ], order='id desc', limit=20)

            for line in recent_lines:
                html_log += f"""
                    <tr>
                        <td><small>{line.name[:50]}</small></td>
                        <td><span class="badge {"bg-info" if line.product_id else "bg-warning"}">{line.product_id.name if line.product_id else 'No vinculado'}</span></td>
                        <td class="text-end">{line.quantity or 0}</td>
                        <td class="text-end"><strong>{line.total_fob or 0:,.2f}</strong></td>
                    </tr>
                """
            if len(all_items) > 20:
                html_log += f'<tr><td colspan="4" class="text-center text-muted">... y {len(all_items) - 20} productos más</td></tr>'
            
            html_log += "</tbody></table></div>"
            self.ai_extraction_log = html_log


            # Mensaje en chatter
            self.message_post(
                body=Markup(_(
                    '<strong>✅ Extracción de Facturas completada con IA</strong><br/>'
                    'Facturas procesadas: %s<br/>'
                    'Items totales: %s<br/>'
                )) % (invoices_processed, len(all_items))
            )

            _logger.info("Extracción de facturas finalizada para %s", self.name)

            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('✅ Extracción Completada'),
                    'message': _('Se procesaron %s facturas con %s productos totales extraídos.') % (
                        invoices_processed,
                        len(all_items)
                    ),
                    'type': 'success',
                    'sticky': False,
                    'next': {'type': 'ir.actions.client', 'tag': 'reload'},
                }
            }

        except Exception as e:
            self.ai_extraction_status_fc = 'error'
            self.ai_extraction_status = 'error'
            error_msg = str(e)
            _logger.error(f"Error en extracción de facturas: {error_msg}")
            self.ai_extraction_log = (self.ai_extraction_log or '') + f"\n=== ERROR - {fields.Datetime.now()} ===\n{error_msg}\n"
            raise UserError(_('Error al extraer datos de las facturas:\n\n%s') % error_msg)

    def _create_goods_lines_from_invoice_items(self, items):
        """
        Crea líneas de mercancía desde items extraídos de facturas
        """
        goods_model = self.env['ek.product.packagens.goods']

        is_request = self._name == 'ek.operation.request'
        parent_field = 'ek_operation_request_id' if is_request else 'ek_boats_information_id'

        for item in items:
            # Use normalized product_name for display; keep raw description as audit trail
            raw_description = item.get('description', '')
            display_name = item.get('product_name') or raw_description

            # REQ: No agregar productos con precio en cero
            unit_price = item.get('unit_price_fob') or 0
            total_price = item.get('total_fob') or 0
            if unit_price <= 0 and total_price <= 0:
                _logger.info("Saltando item con precio en cero: %s", display_name)
                continue

            line_vals = {
                parent_field: self.id,
                'name': display_name,
                'extracted_name': raw_description,  # Original supplier text for audit trail
                'quantity': item.get('quantity') or 0,
                'fob': item.get('unit_price_fob') or 0,
                'total_fob': item.get('total_fob') or 0,
                'gross_weight': item.get('weight_kg') or 0,
                'packages_count': item.get('packages_count') or 0,
                'invoice_number': item.get('invoice_number', ''),
                'supplier': item.get('supplier', ''),
                'product_id': item.get('product_id'),
                'match_confidence': (item.get('match_confidence') or 0.0) * 100, # Convertir a porcentaje 0-100
            }

            if item.get('hs_code'):
                line_vals['tariff_item'] = item['hs_code']

            # REQ-006A: Vincular buque destino si la IA lo detectó
            ship_name = (item.get('ship_name') or '').strip()
            if ship_name:
                ship = self.env['ek.ship.registration'].search([
                    ('name', 'ilike', ship_name)
                ], limit=1)
                if ship:
                    line_vals['ship_id'] = ship.id
                else:
                    _logger.warning(
                        "Buque '%s' mencionado en factura no encontrado en maestros.",
                        ship_name
                    )

            # Crear línea (el sistema buscará/creará producto automáticamente vía create override)
            goods_model.create(line_vals)

        # Sincronizar catálogo Many2many del padre
        self._sync_parent_product_ids()

    def _sync_parent_product_ids(self):
        """
        DEPRECADO: Ya no se usa, los productos están directamente en ek_produc_packages_goods_ids
        Mantenido por compatibilidad con código existente.
        """
        # Ya no es necesario sincronizar, los productos están en las líneas
        pass


    def action_extract_po_and_compare(self):
        """
        Extrae Nota de Pedido y compara con factura usando IA
        REQ-005, REQ-006: Extracción y comparación de PO
        """
        self.ensure_one()

        if not self.purchase_order_attachment_ids:
            raise UserError(_('Por favor adjunte la Nota de Pedido del agente aduanero.'))

        attachment = self.purchase_order_attachment_ids[0]

        if not self.ek_produc_packages_goods_ids:
            raise UserError(_('Debe tener productos de la factura para comparar.\nPrimero extraiga las facturas.'))

        try:
            llm = self.env['nsk.llm.provider']
            tools = [self._get_po_extraction_tool_definition()]

            # 1. Extraer datos de Nota de Pedido
            _logger.info("Extrayendo datos de Nota de Pedido...")
            self.ai_extraction_status_np = 'processing'
            self.ai_extraction_status = 'processing'

            messages = [
                {
                    "role": "system",
                    "content": """You are a senior customs clearance specialist with deep expertise in reading purchase orders and customs declarations (Nota de Pedido) issued by customs brokers.

Extract ALL items listed in the attached Nota de Pedido with full accuracy.

Key extraction rules:
- Capture every item number exactly as listed.
- HS codes are critical — extract them precisely, preserving all digits.
- Include quantities, net/gross weights, and FOB values per line.
- `description`: raw text from the document (verbatim, for audit purposes).
- Do not merge or split items — one document line = one extracted item.

Always call `extract_purchase_order_data` to return structured results."""
                },
                {
                    "role": "user",
                    "content": "Extrae todos los productos de la Nota de Pedido adjunta."
                }
            ]

            response = llm.generate_completion(
                messages=messages,
                attachments=attachment,
                tools=tools
            )

            if not response.choices or not response.choices[0].message.tool_calls:
                raise UserError(_('No se pudieron extraer datos de la Nota de Pedido'))

            tool_call = response.choices[0].message.tool_calls[0]
            po_data = json.loads(tool_call.function.arguments)

            # Guardar datos de PO
            self.purchase_order_data = json.dumps(po_data, indent=2)

            # 2. Abrir wizard de validación para comparación
            wizard_vals = {}
            if self._name == 'ek.operation.request':
                wizard_vals['operation_request_id'] = self.id
            else:
                wizard_vals['container_id'] = self.id

            wizard = self.env['ek.invoice.validation.wizard'].create(wizard_vals)

            # 3. Comparar usando IA
            wizard._compare_with_ai(po_data)

            # Abrir wizard
            self.ai_extraction_status_np = 'completed'
            self.ai_extraction_status = 'completed'
            return {
                'type': 'ir.actions.act_window',
                'name': _('Validación: Factura vs Nota de Pedido'),
                'res_model': 'ek.invoice.validation.wizard',
                'view_mode': 'form',
                'res_id': wizard.id,
                'target': 'new',
                'context': self.env.context,
            }

        except Exception as e:
            self.ai_extraction_status_np = 'error'
            self.ai_extraction_status = 'error'
            error_msg = str(e)
            _logger.error(f"Error en extracción/comparación de PO: {error_msg}")
            raise UserError(_('Error al procesar Nota de Pedido:\n\n%s') % error_msg)

    # ============================================================
    # REQ-002: Identificación automática del tipo de documento
    # ============================================================

    def _detect_document_type(self, attachment):
        """
        Detecta si un PDF es BL, Factura Comercial o Nota de Pedido.
        Devuelve: 'bl' | 'invoice' | 'purchase_order' | 'unknown'
        REQ-002
        """
        llm = self.env['nsk.llm.provider']
        messages = [
            {
                "role": "system",
                "content": (
                    "Eres un experto en documentos aduaneros marítimos. "
                    "Analiza el PDF adjunto y responde ÚNICAMENTE con una de estas palabras, "
                    "sin puntuación ni explicación adicional: "
                    "bl, invoice, purchase_order, unknown"
                )
            },
            {
                "role": "user",
                "content": (
                    "¿Qué tipo de documento es este PDF?\n"
                    "- bl: Bill of Lading / Conocimiento de Embarque\n"
                    "- invoice: Factura Comercial\n"
                    "- purchase_order: Nota de Pedido del agente aduanero\n"
                    "- unknown: No se puede determinar\n\n"
                    "Responde solo con la palabra clave."
                )
            }
        ]

        try:
            response = llm.generate_completion(
                messages=messages,
                attachments=attachment
            )
            raw = response.choices[0].message.content.strip().lower()
            _logger.info("Tipo de documento detectado para '%s': %s", attachment.name, raw)
            if raw in ('bl', 'invoice', 'purchase_order'):
                return raw
        except Exception as e:
            _logger.warning("Error en detección de tipo de documento: %s", str(e))

        return 'unknown'

    def action_auto_detect_and_extract(self):
        """
        Detecta automáticamente el tipo de documento adjunto y enruta
        a la extracción correspondiente.
        REQ-002: Identificación automática del tipo de documento
        """
        self.ensure_one()

        # Si ya hay tipo definido en el registro, usar ese
        doc_type = getattr(self, 'document_type', None)

        # Determinar qué adjunto analizar
        attachment = (self.bl_attachment_ids[0] if self.bl_attachment_ids else None) or (
            self.invoice_attachment_ids[0] if self.invoice_attachment_ids else None
        )

        if not attachment:
            raise UserError(_(
                'Por favor adjunte un documento PDF antes de continuar.'
            ))

        if not doc_type:
            # No sabemos cual es todavia, pero la operacion general esta en proceso
            self.ai_extraction_status = 'processing'
            doc_type = self._detect_document_type(attachment)

        if doc_type == 'bl':
            return self.action_extract_bl_with_ai()
        elif doc_type == 'invoice':
            return self.action_extract_invoices_with_ai()
        elif doc_type == 'purchase_order':
            return self.action_extract_po_and_compare()
        else:
            self.ai_extraction_status = 'error'
            raise UserError(_(
                'No se pudo identificar automáticamente el tipo de documento "%s".\n\n'
                'Por favor use los botones específicos:\n'
                '- "Extraer BL con IA"\n'
                '- "Extraer Facturas con IA"\n'
                '- "Extraer Nota de Pedido con IA"'
            ) % attachment.name)
