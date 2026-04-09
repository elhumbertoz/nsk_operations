# -*- coding: utf-8 -*-
from markupsafe import Markup
from odoo import models, fields, api, _
from odoo.exceptions import UserError
import json
import logging
import threading
from odoo.modules.registry import Registry

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

    ai_extraction_progress = fields.Integer(
        string='Progreso Extracción',
        default=0,
        help='Porcentaje de progreso de la extracción actual'
    )

    ai_extraction_message = fields.Char(
        string='Mensaje de Estado',
        readonly=True
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
                                            "Nombre comercial del producto. REGLA CRÍTICA: Debe ser lo más fiel posible al nombre/descripción "
                                            "que aparece en la factura, pero formateado de forma limpia (sin direcciones, texto legal o "
                                            "números de serie excesivamente largos). "
                                            "Patrón sugerido: [Tipo de Producto] [Marca] [Modelo] [Especificaciones]. "
                                            "Ejemplo: 'RODAMIENTO SKF 6205-2RS', 'MOTOR WEG 7.5HP W22'."
                                        )
                                    },
                                    "hs_code": {
                                        "type": "string",
                                        "description": "Código arancelario (HS Code) para clasificación aduanera (Partida)."
                                    },
                                    "complementary_code": {
                                        "type": "string",
                                        "description": "Código complementario aduanero de 4 dígitos (si está presente)."
                                    },
                                    "supplementary_code": {
                                        "type": "string",
                                        "description": "Código suplementario aduanero de 4 dígitos (si está presente)."
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
                                        "description": "Precio unitario TAL CUAL APARECE IMPRESO en la factura. No lo calcules tú."
                                    },
                                    "total_fob": {
                                        "type": "number",
                                        "description": "VALOR TOTAL (Importe/Amount) de la línea tal como aparece en la factura. Es el campo principal para el cálculo."
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

        if self.ai_extraction_status_fc == 'processing':
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Proceso en curso'),
                    'message': _('Ya se está ejecutando una extracción para este registro.'),
                    'type': 'warning',
                    'sticky': False,
                }
            }

        self.ai_extraction_status_fc = 'processing'
        self.ai_extraction_status = 'processing'
        self.ai_extraction_progress = 0
        self.ai_extraction_message = _('Iniciando extracción asíncrona...')

        # Forzar commit para liberar el bloqueo del registro antes de lanzar el hilo
        # Esto evita el error "could not serialize access due to concurrent update"
        self.env.cr.commit()

        # Lanzar hilo en segundo plano
        # Pasamos el ID, el nombre del modelo, el ID de la base de datos y el UID del usuario
        threaded_extraction = threading.Thread(
            target=self._run_invoice_extraction_async,
            args=(self.id, self._name, self.env.cr.dbname, self.env.uid)
        )
        threaded_extraction.start()

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Extracción Iniciada'),
                'message': _('El proceso de extracción de facturas se ha iniciado en segundo plano. Puede seguir trabajando.'),
                'type': 'info',
                'sticky': False,
                'next': {'type': 'ir.actions.client', 'tag': 'reload'},
            }
        }

    def _notify_ui_update(self):
        """
        Envía una notificación al bus para que la UI sepa que debe refrescarse
        """
        self.env['bus.bus']._sendone('ai_extraction_update', 'ai_extraction_update', {
            'id': self.id,
            'model': self._name,
            'progress': self.ai_extraction_progress,
            'status': self.ai_extraction_status_fc,
            'message': self.ai_extraction_message
        })

    def _run_invoice_extraction_async(self, record_id, model_name, db_name, uid):
        """
        Método ejecutado en un hilo separado para procesar las facturas
        """
        # Crear un nuevo registro/cursor para el hilo
        with Registry(db_name).cursor() as new_cr:
            # En Odoo 17, es mejor usar odoo.api.Environment
            env = api.Environment(new_cr, uid, {})
            record = env[model_name].browse(record_id)
            
            try:
                record._do_invoice_extraction_logic()
            except Exception as e:
                new_cr.rollback()
                _logger.error("Error en extracción asíncrona: %s", str(e))
                record.write({
                    'ai_extraction_status_fc': 'error',
                    'ai_extraction_status': 'error',
                    'ai_extraction_message': str(e)
                })
            finally:
                # El commit se hace automáticamente al salir del contexto del cursor si no hay error
                # pero podemos forzarlo si queremos actualizaciones parciales (dentro de la lógica)
                pass

    def _do_invoice_extraction_logic(self):
        """
        Lógica real de extracción, separada para poder ser llamada asíncronamente
        """
        self.ensure_one()
        try:
            llm = self.env['nsk.llm.provider']
            tools = [self._get_invoice_extraction_tool_definition()]

            all_items = []
            invoices_processed = 0
            failed_invoices = []

            # Ordenar adjuntos alfabéticamente
            sorted_attachments = sorted(self.invoice_attachment_ids, key=lambda a: (a.name or '').lower())
            total_attachments = len(sorted_attachments)
            
            _logger.info("Iniciando extracción asíncrona de %d facturas", total_attachments)

            for i, attachment in enumerate(sorted_attachments):
                progress_val = int((i / total_attachments) * 100)
                self.write({
                    'ai_extraction_progress': progress_val,
                    'ai_extraction_message': _('Procesando factura %d de %d: %s') % (i + 1, total_attachments, attachment.name)
                })
                # Commit parcial para que la UI vea el progreso
                self.env.cr.commit()
                # Notificar vía bus
                self._notify_ui_update()

                _logger.info("Procesando factura %d/%d: %s", i + 1, total_attachments, attachment.name)

                # Procesar una por una (o podrías seguir usando lotes, pero una por una da mejor feeling de progreso)
                batch_items, batch_ok, batch_failed = self._process_invoice_batch(
                    [attachment], llm, tools
                )

                if batch_items:
                    self._create_goods_lines_from_invoice_items(batch_items)
                    all_items.extend(batch_items)
                
                invoices_processed += batch_ok
                failed_invoices.extend(batch_failed)

            # Finalizar
            self.write({
                'ai_extraction_status_fc': 'completed',
                'ai_extraction_status': 'completed',
                'ai_extraction_progress': 100,
                'ai_extraction_message': _('Completado: %d facturas exitosas') % invoices_processed
            })

            # Generar el log HTML (reutilizando lógica existente)
            failed_html = ""
            if failed_invoices:
                failed_html = f"""
                    <div class="alert alert-warning mt-2" role="alert">
                        <strong>Atención:</strong> No se pudieron procesar {len(failed_invoices)} archivos:
                        <ul class="mb-0">
                            {"".join([f"<li>{name}</li>" for name in failed_invoices])}
                        </ul>
                    </div>
                """

            html_log = f"""
                <div class="alert alert-success" role="alert">
                    <h4 class="alert-heading">Extracción de Facturas Completada</h4>
                    <p>Se procesaron <strong>{invoices_processed}</strong> facturas exitosamente.</p>
                    {failed_html}
                    <hr>
                    <table class="table table-sm table-borderless mb-0">
                        <tr><td><strong>Total Items:</strong> {len(all_items)}</td><td><strong>Estado:</strong> <span class="badge bg-success">Catálogo Sincronizado</span></td></tr>
                    </table>
                </div>
            """
            # Agregar tabla de resumen (limitada)
            parent_field = 'ek_operation_request_id' if self._name == 'ek.operation.request' else 'ek_boats_information_id'
            recent_lines = self.env['ek.product.packagens.goods'].search([
                (parent_field, '=', self.id)
            ], order='id desc', limit=20)

            html_log += '<div class="mt-3"><table class="table table-hover table-sm"><thead class="table-light"><tr><th>Descripción</th><th>Producto</th><th class="text-end">Cant.</th><th class="text-end">FOB</th></tr></thead><tbody>'
            for line in recent_lines:
                html_log += f"""
                    <tr>
                        <td><small>{line.name[:50]}</small></td>
                        <td><span class="badge {"bg-info" if line.product_id else "bg-warning"}">{line.product_id.name if line.product_id else 'No vinculado'}</span></td>
                        <td class="text-end">{line.quantity or 0}</td>
                        <td class="text-end"><strong>{line.total_fob or 0:,.2f}</strong></td>
                    </tr>
                """
            html_log += "</tbody></table></div>"
            
            self.write({
                'ai_extraction_status_fc': 'completed',
                'ai_extraction_status': 'completed',
                'ai_extraction_progress': 100,
                'ai_extraction_message': _('Extracción completada con éxito.'),
                'ai_extraction_log': html_log
            })
            self._notify_ui_update()
            
            # Mensaje en chatter
            self.message_post(
                body=Markup(_(
                    '<strong>Extracción de Facturas completada (Async)</strong><br/>'
                    'Facturas procesadas: %s<br/>'
                    'Items totales: %s<br/>'
                )) % (invoices_processed, len(all_items))
            )
            self.env.cr.commit()

        except Exception as e:
            error_msg = str(e)
            _logger.error(f"Error en extracción asíncrona: {error_msg}")
            self.write({
                'ai_extraction_status_fc': 'error',
                'ai_extraction_status': 'error',
                'ai_extraction_message': error_msg,
                'ai_extraction_log': (self.ai_extraction_log or '') + f"\n=== ERROR ASYNC - {fields.Datetime.now()} ===\n{error_msg}\n"
            })
            self._notify_ui_update()
            self.env.cr.commit()

    def _process_invoice_batch(self, batch_attachments, llm, tools):
        """
        Procesa un lote de hasta 5 facturas PDF contra el LLM.

        Cada archivo se envía por separado al LLM para preservar la calidad de extracción,
        pero el lote agrupa los resultados antes del commit a DB, reduciendo la carga
        de transacciones y evitando timeouts en cargas masivas.

        Returns:
            (items: list, ok_count: int, failed_names: list[str])
        """
        catalog_prompt = self._get_regime_70_catalog_prompt()
        system_prompt = f"""Eres un experto analista de facturas comerciales y especialista en inventarios para el comercio marítimo internacional.

Tu trabajo tiene dos partes:
1. **Extraer** cada item de línea de la factura comercial adjunta con total precisión.
2. **Vincular** cada item con el catálogo de productos de Régimen 70 proporcionado a continuación.

## CATÁLOGO DE PRODUCTOS
{catalog_prompt}

## REGLAS DE VINCULACIÓN
- Utiliza el nombre del producto, el contexto y el código HS en conjunto para encontrar la mejor coincidencia en el catálogo.
- Solo asigna `product_id` cuando la confianza supere el 70% — nunca fuerces una vinculación.
- Asigna `match_confidence` entre 0.0 y 1.0 (ej: 0.95 = casi exacto, 0.75 = razonable).
- `description`: copia el texto original de la línea exactamente como está impreso en la factura (para auditoría).
- `product_name`: nombre comercial del producto, respetando fielmente el nombre de la factura pero eliminando ruido innecesario (direcciones, avisos legales, etc.).
- IDIOMA: Debe estar en el mismo idioma de la factura (Español -> Español, Inglés -> Inglés).
- REGLA DE ORO: Si el producto tiene una marca (Brand) o modelo (Model) específico en la factura, debe aparecer obligatoriamente en `product_name`.
- Máximo ~80 caracteres para `product_name`.
- No inventes códigos si no están en el catálogo.
- Si el producto NO está en el catálogo, `product_name` se usará para crear el nuevo producto en el sistema, por lo que debe ser descriptivo y fiel al documento original.

## REGLA DE ORO DE VINCULACIÓN — "EL NÚMERO MANDA"
Los identificadores numéricos, sufijos de modelo y calibres son IDENTIFICADORES ÚNICOS Y NO NEGOCIABLES. 

**PROHIBICIÓN ESTRICTA DE "AUTOCORRECCIÓN":** 
Si en el documento PDF lees un número (ej: #168) y en el catálogo ves algo parecido pero con otro número (ej: #96), **NO VINCULES**. 
- Extrae el texto EXACTAMENTE como lo ves en el PDF (#168).
- NUNCA cambies un número del documento por uno del catálogo.
- La fidelidad al documento es prioritaria sobre la vinculación al catálogo.

**BLOQUEADORES ABSOLUTOS DE MATCH** — Confianza 0% y NO asignar `product_id` si difieren:
1. **Calibres/Grosor con `#`**: `#96` ≠ `#168` ≠ `#210`. Un cambio de número tras el `#` indica un producto técnico distinto (redes, hilos, mallas).
2. **Modelos Alfanuméricos**: `W22` ≠ `W21`, `6205` ≠ `6206`.
3. **Especificaciones de Capacidad/Potencia**: `7.5HP` ≠ `10HP`, `3/4"` ≠ `1/2"`, `220V` ≠ `110V`.

**EJEMPLOS DE FALLOS CRÍTICOS (PROHIBIDO):**
- ❌ Factura dice: "RED NYLON #168" -> Catálogo tiene: "RED NYLON #96" -> **RESULTADO**: `product_id`: null, `product_name`: "RED NYLON #168", `match_confidence`: 0.0. (NUNCA VINCULAR).
- ❌ Factura dice: "MOTOR 10HP" -> Catálogo tiene: "MOTOR 7.5HP" -> **RESULTADO**: `product_id`: null, `match_confidence`: 0.0.

**REGLA FINAL**: Ante la más mínima diferencia numérica o técnica, es OBLIGATORIO marcar como NO encontrado (product_id: null). Es preferible que el usuario cree un producto nuevo a que el sistema asocie uno incorrecto que cause errores en la declaración aduanera.

## REGLAS DE PALETIZACIÓN Y AGRUPACIÓN EN BULTOS (MUY IMPORTANTE)
Algunas facturas agrupan las unidades físicas en BULTOS, FARDOS, BALES o PALLETS. Esto es crítico para la declaración aduanera:

**PROHIBICIÓN DE CÁLCULO**: No realices ninguna operación matemática (divisiones o multiplicaciones). Limítate a extraer los números exactos del documento. El sistema Odoo hará los cálculos.

**CASO A — Productos NO paletizados (líneas individuales):**
- La factura NO tiene una columna separada de BULTOS o BALES.
- Cada línea = 1 tipo de producto con su cantidad y precio unitario directos.
- `is_palletized` = false
- `quantity` = cantidad de unidades de la línea
- `total_fob` = el valor total/importe/amount de la línea.

**CASO B — Productos paletizados/agrupados en BULTOS:**
- La factura tiene columnas SEPARADAS: BULTOS/BALES/PALLETS (agrupa físicamente) y PAÑOS/SHEETS/PCS/UNIDADES (contenido).
- `is_palletized` = true
- `bales_count` = valor de la columna BULTOS/BALES.
- `units_per_bale` = valor de la columna PAÑOS/SHEETS/PCS (contenido interno).
- `quantity` = bales_count (número de BULTOS).
- `total_fob` = el importe/amount total de la línea.

**CÓMO DETECTAR agrupación en bultos:**
- Busca columnas con encabezados como: BULTOS, BALES, PALLETS, FARDOS, CAJAS, PACKAGES junto a otra columna de contenido (PAÑOS, SHEETS, PCS, UNITS, QTY).
- Si existe una columna de bultos separada de la de piezas, ES PALETIZACIÓN (Caso B).

## REGLAS DE EXTRACCIÓN GENERALES
- **NO CALCULES NADA**: Extrae los valores tal cual están escritos.
- **TOTAL FOB**: Siempre extrae el importe total de la línea (Total, Amount, Extension).
- **items con precio cero**: Ignora items sin precio.
- **Buque destino**: Captura nombres de buques en `ship_name` si se mencionan.

Llama siempre a `extract_invoice_data` para devolver los resultados estructurados."""

        batch_items = []
        ok_count = 0
        failed_names = []

        for invoice_att in batch_attachments:
            _logger.info("Extrayendo factura: %s", invoice_att.name)
            try:
                messages = [
                    {"role": "system", "content": system_prompt},
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

                    items_in_invoice = invoice_data.get('items', [])
                    for item in items_in_invoice:
                        item['invoice_number'] = invoice_data.get('invoice_number', invoice_att.name)
                        item['supplier'] = invoice_data.get('supplier', '')
                        batch_items.append(item)

                    ok_count += 1
                    _logger.info(
                        "Factura '%s' OK — %d items extraídos.",
                        invoice_att.name, len(items_in_invoice)
                    )
                else:
                    _logger.warning(
                        "Factura '%s' — el LLM no devolvió tool_call. Se omite.",
                        invoice_att.name
                    )
                    failed_names.append(invoice_att.name)

            except Exception as exc:
                _logger.error(
                    "Error procesando factura '%s': %s. Se continúa con el lote.",
                    invoice_att.name, exc
                )
                failed_names.append(invoice_att.name)

        return batch_items, ok_count, failed_names

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
            # PRIORIDAD: Respetar el nombre de la factura para la creación y visualización.
            # description contiene el texto original verbatim.
            # product_name contiene el nombre comercial extraído por la IA.
            raw_description = item.get('description', '').strip()
            ai_product_name = item.get('product_name', '').strip()
            
            # Usamos el nombre comercial de la IA como nombre principal si es descriptivo,
            # de lo contrario el raw. Pero para cumplir con "respetar el nombre de la factura",
            # nos aseguramos de que no sea alterado drásticamente.
            display_name = ai_product_name or raw_description or "Producto sin nombre"

            # REQ: No agregar productos con precio en cero
            unit_price = item.get('unit_price_fob') or 0
            total_price = item.get('total_fob') or 0
            if unit_price <= 0 and total_price <= 0:
                _logger.info("Saltando item con precio en cero: %s", display_name)
                continue

            # ── LÓGICA DE VALORES Y PRECIOS (MATEMÁTICA EN PYTHON) ──────────────
            # La IA solo extrae los valores impresos sin calcular.
            # Delegamos el cálculo del precio unitario FOB al sistema Odoo
            # para asegurar máxima precisión y consistencia.
            is_palletized = item.get('is_palletized', False)
            bales_count = item.get('bales_count') or 0
            raw_quantity = item.get('quantity') or 0

            # 1. Determinar Cantidad Aduanera
            # Si está paletizado, la cantidad es el nº de bultos.
            final_quantity = bales_count if (is_palletized and bales_count > 0) else raw_quantity

            # 2. Calcular FOB Unitario (Total / Cantidad)
            # Siempre calculamos desde el Total para evitar errores de redondeo del proveedor
            if final_quantity > 0 and total_price > 0:
                final_unit_fob = round(total_price / final_quantity, 6)
            else:
                final_unit_fob = item.get('unit_price_fob') or 0

            # 3. Paquetes
            final_packages = bales_count if (is_palletized and bales_count > 0) else final_quantity

            if is_palletized:
                _logger.info(
                    "Item PALETIZADO '%s': %d bultos. Calculado unit_fob: %.2f / %d = %.4f",
                    display_name, bales_count, total_price, final_quantity, final_unit_fob
                )
            else:
                _logger.info(
                    "Item NORMAL '%s': %s unidades. Calculado unit_fob: %.2f / %s = %.4f",
                    display_name, final_quantity, total_price, final_quantity, final_unit_fob
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
            if item.get('complementary_code'):
                line_vals['id_hs_copmt_cd'] = item['complementary_code']
            if item.get('supplementary_code'):
                line_vals['id_hs_spmt_cd'] = item['supplementary_code']

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
