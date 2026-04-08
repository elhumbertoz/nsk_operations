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
                        "booking_number": {
                            "type": "string",
                            "description": "Número de Reserva o Booking"
                        },
                        "seal_number": {
                            "type": "string",
                            "description": "Número de Sello o Seal (ej: L6701305)"
                        },
                        "consignee": {
                            "type": "string",
                            "description": "Nombre del Consignatario (Consignee)"
                        },
                        "port_of_loading": {
                            "type": "string",
                            "description": "Nombre del puerto de carga (ej: VIGO)"
                        },
                        "port_of_discharge": {
                            "type": "string",
                            "description": "Nombre del puerto de descarga (ej: GUAYAQUIL)"
                        },
                        "type_move": {
                            "type": "string",
                            "enum": ["fcl_fcl", "fcl_lcl", "lcl_lcl", "lcl_fcl"],
                            "description": "Tipo de movimiento (ej: FCL/FCL)"
                        },
                        "on_board_date": {
                            "type": "string",
                            "description": "Fecha de carga a bordo (formato YYYY-MM-DD)"
                        }
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
                                            "Descripción original del producto exactamente como aparece en el documento. "
                                            "NO truncar ni parafrasear — preservar el texto original completo para fines de auditoría."
                                        )
                                    },
                                    "product_name": {
                                        "type": "string",
                                        "description": (
                                            "Nombre de producto normalizado y legible siguiendo el patrón: "
                                            "[Tipo de Producto] [Marca] [Modelo] [Especificaciones Clave]. "
                                            "Reglas: (1) Ser conciso — máx ~60 caracteres. "
                                            "(2) Omitir texto legal extenso, números de parte complejos, direcciones y palabras genéricas de relleno. "
                                            "(3) Preservar la marca y el modelo cuando estén presentes — son los atributos más identificables. "
                                            "(4) Incluir solo la especificación más discriminante (ej: potencia, tamaño, voltaje). "
                                            "Ejemplos: 'Motor Eléctrico WEG W22 7.5HP 4P', 'Bomba Hidráulica Bosch Rexroth A10V 45cc', "
                                            "'Rodamiento SKF 6205-2RS'."
                                        )
                                    },
                                    "hs_code": {
                                        "type": "string",
                                        "description": "Código arancelario (HS Code) para clasificación aduanera."
                                    },
                                    "is_palletized": {
                                        "type": "boolean",
                                        "description": (
                                            "TRUE si el proveedor agrupó/paletizó múltiples unidades en bultos (BULTOS/BALES/PALLETS). "
                                            "En este caso, la factura muestra una columna distinta de BULTOS vs PAÑOS/UNIDADES/SHEETS. "
                                            "FALSE si cada línea corresponde a unidades individuales sin agrupación en bultos."
                                        )
                                    },
                                    "bales_count": {
                                        "type": "integer",
                                        "description": (
                                            "Número de bultos/fardos/pallets físicos (columna BULTOS, BALES, PALLETS o similar). "
                                            "Solo completar si is_palletized=true. "
                                            "Este es el número que se usará como 'quantity' para la declaración aduanera."
                                        )
                                    },
                                    "units_per_bale": {
                                        "type": "number",
                                        "description": (
                                            "Cantidad de unidades/piezas físicas dentro de cada bulto (columna PAÑOS, SHEETS, PCS, UNITS o similar). "
                                            "Solo completar si is_palletized=true. Informativo, no se usa para el cálculo FOB."
                                        )
                                    },
                                    "quantity": {
                                        "type": "number",
                                        "description": (
                                            "CANTIDAD PARA LA DECLARACIÓN ADUANERA. "
                                            "Si is_palletized=TRUE: usar bales_count (número de bultos). "
                                            "Si is_palletized=FALSE: usar la cantidad de unidades individuales de la línea."
                                        )
                                    },
                                    "unit_price_fob": {
                                        "type": "number",
                                        "description": (
                                            "PRECIO FOB UNITARIO PARA LA DECLARACIÓN ADUANERA. "
                                            "Si is_palletized=TRUE: calcular como total_fob / bales_count (FOB por bulto). "
                                            "Si is_palletized=FALSE: usar el precio unitario por pieza que aparece en la factura."
                                        )
                                    },
                                    "total_fob": {
                                        "type": "number",
                                        "description": (
                                            "Valor FOB TOTAL de la línea. Siempre copiar el importe/amount total tal como "
                                            "aparece en la factura (IMPORTE, AMOUNT, TOTAL). No recalcular."
                                        )
                                    },
                                    "weight_kg": {"type": "number"},
                                    "packages_count": {
                                        "type": "integer",
                                        "description": (
                                            "Número de paquetes/bultos para registrar en el sistema. "
                                            "Si is_palletized=TRUE: igual a bales_count. "
                                            "Si is_palletized=FALSE: igual a quantity."
                                        )
                                    },
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
                                "required": ["description", "quantity", "total_fob", "is_palletized"]
                            },
                            "description": (
                                "Lista de productos/items en la factura. "
                                "CRÍTICO: detectar si los productos están paletizados/agrupados en bultos "
                                "para calcular correctamente el FOB unitario por bulto."
                            )
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
                    "content": f"""Eres un experto analista senior de aduanas y logística marítima con más de 20 años de experiencia interpretando Bill of Ladings (BL).
                    
Tu objetivo es extraer con total precisión los datos logísticos y de transporte del documento adjunto.

REGLAS DE EXTRACCIÓN CRÍTICAS:
1. **Identificación de Contenedor y Sello**: Busca en la sección 'Particulars Furnished by Shipper' o 'Marks and Nos'. El sello suele estar precedido por 'SEAL'.
2. **Booking vs BL**: El número de Booking es distinto al número de BL. Extráelos por separado.
3. **Puertos**: Identifica claramente el Port of Loading (Origen) y Port of Discharge (Destino).
4. **Tipo de Movimiento**: Identifica si es FCL/FCL, FCL/LCL, etc. Si no se especifica, usa el contexto.
5. **Fechas**: La fecha 'On Board' es la fecha real en que la mercancía subió al buque.
6. **Consignatario**: Es la entidad local que recibe la carga.
7. **NO EXTRACCIÓN DE PRODUCTOS**: Ignora la lista detallada de bultos individuales, solo extrae el PESO BRUTO total y la CANTIDAD TOTAL de bultos.

Llama siempre a `extract_bl_data` para devolver los resultados estructurados."""
                },
                {
                    "role": "user",
                    "content": """Analiza el Bill of Lading adjunto y extrae:
- Número de BL y de Booking.
- Número de Contenedor y de Sello (Seal).
- Buque y puertos de carga/descarga.
- Consignatario y Exportador.
- Pesos totales, cantidad de bultos y tipo de movimiento (FCL/LCL).
- Fechas estimadas (ETA/ETD) y fecha de carga a bordo (On Board).
- Descripción resumida de la carga.

El documento PDF está adjunto."""
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
            html_log = f"""
                <div class="alert alert-success" role="alert">
                    <h4 class="alert-heading">Extracción de BL Completada</h4>
                    <p>Se procesó el documento <strong>{attachment.name}</strong> con éxito.</p>
                    <hr>
                    <div class="row">
                        <div class="col-6">
                            <table class="table table-sm table-borderless mb-0">
                                <tr><td><strong>BL#:</strong></td><td>{extracted_data.get('id_bl', 'N/A')}</td></tr>
                                <tr><td><strong>Booking:</strong></td><td>{extracted_data.get('booking_number', 'N/A')}</td></tr>
                                <tr><td><strong>Contenedor:</strong></td><td>{getattr(self, 'number_container', extracted_data.get('number_container', 'N/A'))}</td></tr>
                                <tr><td><strong>Sello:</strong></td><td>{extracted_data.get('seal_number', 'N/A')}</td></tr>
                                <tr><td><strong>Buque:</strong></td><td>{extracted_data.get('shipping_line', 'N/A')}</td></tr>
                            </table>
                        </div>
                        <div class="col-6">
                            <table class="table table-sm table-borderless mb-0">
                                <tr><td><strong>Peso Bruto:</strong></td><td>{extracted_data.get('total_weight', 0)} kg</td></tr>
                                <tr><td><strong>Bultos:</strong></td><td>{extracted_data.get('total_packages', 0)}</td></tr>
                                <tr><td><strong>Movimiento:</strong></td><td>{extracted_data.get('type_move', 'N/A').upper()}</td></tr>
                                <tr><td><strong>Puerto Carga:</strong></td><td>{extracted_data.get('port_of_loading', 'N/A')}</td></tr>
                                <tr><td><strong>Puerto Descarga:</strong></td><td>{extracted_data.get('port_of_discharge', 'N/A')}</td></tr>
                            </table>
                        </div>
                    </div>
                    <hr>
                    <p class="mb-0"><strong>Descripción:</strong> {extracted_data.get('supplies_detail', 'N/A')}</p>
                </div>
            """
            
            self.ai_extraction_log = html_log

            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Extracción Completada'),
                    'message': _('Se extrajeron los datos logísticos del BL'),
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

        # === NUEVOS CAMPOS LOGÍSTICOS ===
        if extracted_data.get('booking_number'):
            self.booking_number = extracted_data['booking_number']

        if extracted_data.get('seal_number'):
            self.seal_number = extracted_data['seal_number']

        if extracted_data.get('type_move'):
            self.type_move_fcl_lcl = extracted_data['type_move']

        if extracted_data.get('total_weight'):
            self.total_gross_weight = extracted_data['total_weight']

        if extracted_data.get('total_packages'):
            self.total_packages_count = extracted_data['total_packages']

        if extracted_data.get('on_board_date'):
            try:
                self.on_board_date = extracted_data['on_board_date']
            except:
                _logger.warning("No se pudo aplicar on_board_date: %s", extracted_data['on_board_date'])

        # Buscar Consignatario
        if extracted_data.get('consignee'):
            consignee = self.env['res.partner'].search([
                ('name', 'ilike', extracted_data['consignee']),
                ('is_company', '=', True)
            ], limit=1)
            if consignee:
                self.consignee_id = consignee.id

        # Buscar Puertos (Mapeo a maestros de Odoo)
        if extracted_data.get('port_of_loading'):
            port_l = self.env['ek.res.world.seaports'].search([
                ('name', 'ilike', extracted_data['port_of_loading'])
            ], limit=1)
            if port_l and hasattr(self, 'ek_res_world_seaports_id'):
                self.ek_res_world_seaports_id = port_l.id

        if extracted_data.get('port_of_discharge'):
            port_d = self.env['ek.res.world.seaports'].search([
                ('name', 'ilike', extracted_data['port_of_discharge'])
            ], limit=1)
            if port_d and hasattr(self, 'ek_res_world_seaports_d_id'):
                self.ek_res_world_seaports_d_id = port_d.id

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

        # Log en chatter
        attachment_name = self.bl_attachment_ids[0].name if self.bl_attachment_ids else 'N/A'
        self.message_post(
            body=Markup(_(
                '<strong>Extracción de BL completada con IA</strong><br/>'
                'Documento: %s<br/>'
                'BL#: %s<br/>'
                'Contenedor: %s'
            ) % (
                attachment_name,
                self.id_bl or 'N/A',
                self.number_container or 'N/A'
            ))
        )

        # Actualizar catálogo de productos en el padre
        self._sync_parent_product_ids()




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
            for invoice_att in sorted(self.invoice_attachment_ids, key=lambda a: (a.name or '').lower()):
                _logger.info(f"Extrayendo datos de factura: {invoice_att.name}")

                messages = [
                    {
                        "role": "system",
                        "content": f"""Eres un experto analista de facturas comerciales y especialista en inventarios para el comercio marítimo internacional.

Tu trabajo tiene dos partes:
1. **Extraer** cada item de línea de la factura comercial adjunta con total precisión.
2. **Vincular** cada item con el catálogo de productos de Régimen 70 proporcionado a continuación.

## CATÁLOGO DE PRODUCTOS
{self._get_regime_70_catalog_prompt()}

## REGLAS DE VINCULACIÓN
- Utiliza el nombre del producto, el contexto y el código HS en conjunto para encontrar la mejor coincidencia en el catálogo.
- Solo asigna `product_id` cuando la confianza supere el 70% — nunca fuerces una vinculación.
- Asigna `match_confidence` entre 0.0 y 1.0 (ej: 0.95 = casi exacto, 0.75 = razonable).
- `description`: copia el texto original de la línea exactamente como está impreso en la factura (para auditoría).
- `product_name`: genera un nombre normalizado y conciso usando el patrón: [Tipo] [Marca] [Modelo] [Especificación Clave].
- IDIOMA: IMPORTANTE — El nombre del producto debe estar en el idioma del documento de origen. Si el documento está en español, el nombre debe estar en español.
  - Máximo ~60 caracteres. Omitir números de serie, especificaciones largas, texto legal y direcciones.
  - Conservar la marca y el modelo — son los identificadores más valiosos.
  - Incluir solo la especificación más discriminante (potencia, tamaño, capacidad, voltaje, etc.).
  - EJEMPLO (Español): "Motor Eléctrico WEG W22 7.5HP 4P"
  - EJEMPLO (Inglés): "Electric Motor WEG W22 7.5HP 4P"

## REGLAS DE PALETIZACIÓN Y AGRUPACIÓN EN BULTOS (MUY IMPORTANTE)
Algunas facturas agrupan las unidades físicas en BULTOS, FARDOS, BALES o PALLETS. Esto es crítico para la declaración aduanera:

**CASO A — Productos NO paletizados (líneas individuales):**
- La factura NO tiene una columna separada de BULTOS o BALES.
- Cada línea = 1 tipo de producto con su cantidad y precio unitario directos.
- `is_palletized` = false
- `quantity` = cantidad de unidades de la línea
- `unit_price_fob` = precio por unidad tal como aparece en la factura
- EJEMPLO: 10 unidades × $50 c/u = $500 total → quantity=10, unit_price_fob=50, total_fob=500

**CASO B — Productos paletizados/agrupados en BULTOS:**
- La factura tiene columnas SEPARADAS: BULTOS/BALES/PALLETS (agrupa físicamente) y PAÑOS/SHEETS/PCS/UNIDADES (contenido).
- El precio INDIVIDUAL por unidad NO coincidirá con el total si divides por unidades — debes dividir por BULTOS.
- `is_palletized` = true
- `bales_count` = valor de la columna BULTOS/BALES (= cantidad de unidades físicas despachables)
- `units_per_bale` = valor de la columna PAÑOS/SHEETS/PCS (informativo)
- `quantity` = bales_count (número de BULTOS, NO de unidades internas)
- `unit_price_fob` = total_fob / bales_count (FOB distribuido entre los bultos)
- `total_fob` = el importe/amount total de la línea tal como aparece en la factura
- `packages_count` = bales_count
- EJEMPLO: 3 BULTOS × 5 PAÑOS c/u, importe total $1,500 → quantity=3, unit_price_fob=500, total_fob=1500, bales_count=3, units_per_bale=5

**CÓMO DETECTAR agrupación en bultos:**
- Busca columnas con encabezados como: BULTOS, BALES, PALLETS, FARDOS, CAJAS, PACKAGES (acompañadas de otra columna PAÑOS, SHEETS, PCS, UNITS, QTY).
- Si el precio por unidad × cantidad de unidades NO da el total, es señal de agrupación en bultos.
- Si hay una columna de unidades internas (PAÑOS/SHEETS) distinta de la de bultos, aplica CASO B.

## REGLAS DE EXTRACCIÓN GENERALES
- Extrae todos los items con sus cantidades y precios FOB exactos.
- IMPORTANTE: NO extraigas items con precio cero (0.00). Si un item no tiene precio o es cero, ignóralo.
- Si el documento menciona explícitamente un buque destino (ej: "FOR VESSEL ATÚN I", "PARA BUQUE TXOPITUNA"), captúralo en `ship_name`.
- `total_fob` SIEMPRE debe ser el importe total de la línea tal como aparece; nunca lo recalcules.

Llama siempre a `extract_invoice_data` para devolver los resultados estructurados."""
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
        Crea líneas de mercancía desde items extraídos de facturas.
        Maneja correctamente la paletización/agrupación en bultos:
        - Si is_palletized=True: quantity=bales_count, unit_price_fob=total_fob/bales_count
        - Si is_palletized=False: quantity y unit_price_fob directamente de la factura
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

            # ── LÓGICA DE PALETIZACIÓN ──────────────────────────────────────────
            # La IA devuelve is_palletized=True cuando el proveedor agrupa unidades
            # en bultos (BULTOS/BALES). En ese caso:
            #   - quantity = número de bultos (bales_count)
            #   - unit_price_fob = total_fob / bales_count  (FOB por bulto)
            # Cuando is_palletized=False, se usan los valores directos de la factura.
            is_palletized = item.get('is_palletized', False)
            bales_count = item.get('bales_count') or 0

            if is_palletized and bales_count > 0:
                # CASO B: productos agrupados en bultos
                final_quantity = bales_count
                final_unit_fob = round(total_price / bales_count, 6) if total_price else 0
                final_packages = bales_count
                _logger.info(
                    "Item PALETIZADO '%s': %d bultos, FOB/bulto=%.2f (total=%.2f)",
                    display_name, bales_count, final_unit_fob, total_price
                )
            else:
                # CASO A: unidades individuales — usar valores directos de la IA
                final_quantity = item.get('quantity') or 0
                final_unit_fob = item.get('unit_price_fob') or 0
                final_packages = item.get('packages_count') or 0

                # Heurística de seguridad: si la IA no marcó is_palletized pero los
                # números no cuadran (unit_price × qty ≠ total con margen > 5%),
                # recalculamos unit_price desde el total para evitar inconsistencias.
                if final_quantity > 0 and total_price > 0:
                    calculated_total = round(final_unit_fob * final_quantity, 2)
                    variance = abs(calculated_total - total_price) / total_price
                    if variance > 0.05:
                        original_fob = final_unit_fob
                        final_unit_fob = round(total_price / final_quantity, 6)
                        _logger.warning(
                            "Item '%s': precio unitario inconsistente (%.2f × %s = %.2f ≠ total %.2f). "
                            "Recalculando unit_fob=%.4f desde total.",
                            display_name, original_fob, final_quantity,
                            calculated_total, total_price, final_unit_fob
                        )

            line_vals = {
                parent_field: self.id,
                'name': display_name,
                'extracted_name': raw_description,  # Original supplier text for audit trail
                'quantity': final_quantity,
                'fob': final_unit_fob,
                'total_fob': total_price,
                'gross_weight': item.get('weight_kg') or 0,
                'packages_count': final_packages,
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
                    "content": """Eres un especialista senior en despacho de aduanas con amplia experiencia en la lectura de Notas de Pedido y declaraciones aduaneras emitidas por agentes de aduana.

Extrae TODOS los items listados en la Nota de Pedido adjunta con total precisión.

Reglas clave de extracción:
- Captura cada número de item exactamente como aparece listado.
- Los códigos HS son críticos — extráelos con precisión, preservando todos los dígitos.
- Incluye cantidades, pesos netos/brutos y valores FOB por línea.
- `description`: texto original del documento (verbatim, para fines de auditoría).
- No combines ni dividas items — una línea del documento = un item extraído.

Llama siempre a `extract_purchase_order_data` para devolver los resultados estructurados."""
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
