# -*- coding: utf-8 -*-
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
    ], string='Estado Extracción IA', default='pending', tracking=True)

    ai_extraction_log = fields.Text(
        string='Log de Extracción IA',
        readonly=True,
        help='Registro de las extracciones realizadas con IA'
    )

    ai_confidence_score = fields.Float(
        string='Confidence Score',
        readonly=True,
        help='Nivel de confianza de la última extracción (0-1)'
    )

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
                            "description": "Descripción general de la carga o suministros"
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
                                    "supplier": {"type": "string"}
                                }
                            },
                            "description": "Lista detallada de productos/paquetes en el contenedor"
                        },
                        "confidence_score": {
                            "type": "number",
                            "description": "Nivel de confianza de la extracción (0.0 a 1.0)"
                        }
                    },
                    "required": ["id_bl", "confidence_score"]
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
                                    "description": {"type": "string"},
                                    "hs_code": {"type": "string"},
                                    "quantity": {"type": "number"},
                                    "unit_price_fob": {"type": "number"},
                                    "total_fob": {"type": "number"},
                                    "weight_kg": {"type": "number"},
                                    "packages_count": {"type": "integer"},
                                    "ship_name": {
                                        "type": "string",
                                        "description": (
                                            "Nombre del buque destino si se menciona en esta línea "
                                            "o en el encabezado/cuerpo de la factura para este ítem. "
                                            "Buscar patrones: 'FOR VESSEL ...', 'PARA BUQUE ...', "
                                            "'PARA BARCO ...', 'M/V ...', 'MV ...', 'VESSEL: ...'. "
                                            "Dejar vacío si no se menciona ningún buque."
                                        )
                                    }
                                },
                                "required": ["description", "quantity", "total_fob"]
                            },
                            "description": "Lista de productos/items en la factura"
                        },
                        "subtotal": {"type": "number"},
                        "total": {"type": "number"},
                        "confidence_score": {"type": "number"}
                    },
                    "required": ["invoice_number", "supplier", "items", "confidence_score"]
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
                        "confidence_score": {"type": "number"}
                    },
                    "required": ["items", "confidence_score"]
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
                    "content": """Eres un experto en documentos marítimos y aduaneros.

Tu tarea es leer el Bill of Lading (BL) adjunto y extraer TODA la información relevante.

IMPORTANTE:
- El documento puede estar en español o inglés
- Extrae TODOS los productos mencionados
- Si hay tablas, extrae cada fila
- Los códigos HS pueden tener formato: 1234.56.78.90 o similar
- El peso puede estar en KG o LBS (convierte a KG si es LBS: 1 LB = 0.453592 KG)
- Las fechas pueden tener varios formatos, normaliza a YYYY-MM-DD

Usa la función extract_bl_data para devolver los resultados estructurados."""
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

            _logger.info(f"Datos extraídos exitosamente. Confidence: {extracted_data.get('confidence_score', 0)}")

            # Aplicar datos extraídos
            self._apply_bl_data(extracted_data)

            # Actualizar estado
            self.ai_extraction_status = 'completed'
            self.ai_confidence_score = extracted_data.get('confidence_score', 0)

            # Log
            log_entry = f"\n=== Extracción BL - {fields.Datetime.now()} ===\n"
            log_entry += f"Documento: {attachment.name}\n"
            log_entry += f"Confidence Score: {self.ai_confidence_score:.2f}\n"
            log_entry += f"Productos extraídos: {len(extracted_data.get('packages', []))}\n"

            self.ai_extraction_log = (self.ai_extraction_log or '') + log_entry

            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('✅ Extracción Completada'),
                    'message': _('Se extrajeron %s productos del BL con confianza de %.0f%%') % (
                        len(extracted_data.get('packages', [])),
                        self.ai_confidence_score * 100
                    ),
                    'type': 'success',
                    'sticky': False,
                    'next': {'type': 'ir.actions.client', 'tag': 'reload'},
                }
            }

        except Exception as e:
            self.ai_extraction_status = 'error'
            error_msg = str(e)
            _logger.error(f"Error en extracción de BL: {error_msg}")

            self.ai_extraction_log = (self.ai_extraction_log or '') + f"\n=== ERROR - {fields.Datetime.now()} ===\n{error_msg}\n"

            raise UserError(_('Error al extraer datos del BL:\n\n%s\n\nVerifique:\n- Que nsk_llm esté configurado correctamente\n- Que el documento sea un PDF válido\n- Que el servidor tenga acceso a Internet') % error_msg)

    def _apply_bl_data(self, extracted_data):
        """
        Aplica los datos extraídos del BL al registro
        REQ-002: Aplicación de datos extraídos
        """
        # Actualizar campos del BL
        if extracted_data.get('id_bl'):
            self.id_bl = extracted_data['id_bl']

        if extracted_data.get('number_container'):
            # En ek.boats.information es container_number
            if hasattr(self, 'container_number'):
                self.container_number = extracted_data['number_container']
            # En ek.operation.request es id_bl (el contenedor se muestra como label ID CONTENEDOR)
            # Pero if el mixin tiene number_container, usarlo
            elif hasattr(self, 'number_container'):
                self.number_container = extracted_data['number_container']

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
            self.supplies_detail = extracted_data['supplies_detail']

        # Buscar línea naviera
        if extracted_data.get('shipping_line'):
            shipping_line = self.env['res.partner'].search([
                ('name', 'ilike', extracted_data['shipping_line']),
                ('is_company', '=', True)
            ], limit=1)

            if shipping_line:
                self.shipping_line_id = shipping_line.id
            else:
                _logger.info(f"Línea naviera no encontrada: {extracted_data['shipping_line']}")

        # Crear líneas de productos
        packages = extracted_data.get('packages', [])
        if packages:
            self._create_goods_lines_from_packages(packages)

        # Log en chatter
        self.message_post(
            body=_(
                '<strong>✅ Extracción de BL completada con IA</strong><br/>'
                'Documento: %s<br/>'
                'Confidence Score: %.0f%%<br/>'
                'Productos extraídos: %s<br/>'
                'BL#: %s<br/>'
                'Contenedor: %s'
            ) % (
                self.bl_attachment_id.name,
                extracted_data.get('confidence_score', 0) * 100,
                len(packages),
                self.id_bl or 'N/A',
                self.number_container or 'N/A'
            )
        )

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
            # Preparar valores
            line_vals = {
                parent_field: self.id,
                'name': pkg.get('description', ''),
                'quantity': pkg.get('quantity') or 0,
                'gross_weight': pkg.get('weight_kg') or 0,
                'invoice_number': pkg.get('invoice_number', ''),
                'supplier': pkg.get('supplier', ''),
            }

            # HS Code
            if pkg.get('hs_code'):
                line_vals['tariff_item'] = pkg['hs_code']

            # Crear línea (el sistema buscará/creará producto automáticamente)
            goods_model.create(line_vals)

    def action_extract_invoices_with_ai(self):
        """
        Extrae datos de facturas comerciales usando IA
        REQ-004: Extracción de Facturas
        """
        self.ensure_one()

        if not self.invoice_attachment_ids:
            raise UserError(_('Por favor adjunte al menos una factura comercial antes de continuar.'))

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
                        "content": """Eres un experto en facturas comerciales internacionales.

Extrae TODA la información de la factura adjunta, incluyendo:
- Todos los productos/items listados
- Cantidades exactas
- Precios FOB
- Códigos HS si están disponibles
- Pesos si están disponibles

IMPORTANTE:
- Si los precios están en otra moneda, indica cuál
- Extrae TODAS las líneas de la tabla de productos
- Si hay descuentos o cargos adicionales, inclúyelos
- El campo "line_number" debe ser el número de ítem en la factura
- Si el documento menciona un buque destino (ej: "FOR VESSEL ATÚN I",
  "PARA BARCO TXOPITUNA", "M/V CONTADORA", "VESSEL: TXOPITUNA DOS"),
  indica el nombre en el campo ship_name de cada línea afectada.
  Si aplica a todos los ítems, repite el nombre en cada uno.
  Si no se menciona ningún buque, deja ship_name vacío."""
                    },
                    {
                        "role": "user",
                        "content": f"Extrae todos los datos de esta factura comercial. El documento está adjunto."
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
            self.ai_extraction_status = 'completed'

            # Log
            log_entry = f"\n=== Extracción Facturas - {fields.Datetime.now()} ===\n"
            log_entry += f"Facturas procesadas: {invoices_processed}\n"
            log_entry += f"Items totales extraídos: {len(all_items)}\n"
            self.ai_extraction_log = (self.ai_extraction_log or '') + log_entry

            # Mensaje en chatter
            self.message_post(
                body=_(
                    '<strong>✅ Extracción de Facturas completada con IA</strong><br/>'
                    'Facturas procesadas: %s<br/>'
                    'Items totales: %s<br/>'
                ) % (invoices_processed, len(all_items))
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
            line_vals = {
                parent_field: self.id,
                'name': item.get('description', ''),
                'quantity': item.get('quantity') or 0,
                'fob': item.get('unit_price_fob') or 0,
                'total_fob': item.get('total_fob') or 0,
                'gross_weight': item.get('weight_kg') or 0,
                'packages_count': item.get('packages_count') or 0,
                'invoice_number': item.get('invoice_number', ''),
                'supplier': item.get('supplier', ''),
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

            goods_model.create(line_vals)

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

            messages = [
                {
                    "role": "system",
                    "content": """Eres un experto en documentos aduaneros.

Extrae TODOS los productos listados en la Nota de Pedido del agente aduanero.

IMPORTANTE:
- Extrae cada ítem con su número
- Incluye cantidades, pesos y valores FOB
- Los códigos HS son críticos para matching"""
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
            wizard = self.env['ek.invoice.validation.wizard'].create({
                'operation_request_id': self.id,
            })

            # 3. Comparar usando IA
            wizard._compare_with_ai(po_data)

            # Abrir wizard
            return {
                'type': 'ir.actions.act_window',
                'name': _('Validación: Factura vs Nota de Pedido'),
                'res_model': 'ek.invoice.validation.wizard',
                'view_mode': 'form',
                'res_id': wizard.id,
                'target': 'new',
            }

        except Exception as e:
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
