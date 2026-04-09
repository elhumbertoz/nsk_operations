# -*- coding: utf-8 -*-
from markupsafe import Markup
from odoo import models, fields, api, _
from odoo.exceptions import UserError
import json
import logging
import re

_logger = logging.getLogger(__name__)

class EkAIGoodsUpdateWizard(models.TransientModel):
    _name = 'ek.ai.goods.update.wizard'
    _description = 'Asistente IA para Actualización de Mercancías'

    operation_request_id = fields.Many2one(
        'ek.operation.request', 
        string='Solicitud de Operación',
        required=True,
        ondelete='cascade'
    )
    
    user_text = fields.Text(
        string='Instrucción para la IA',
        help='Describa los cambios que desea realizar (ej: "Actualiza el peso de la línea 42 a 15kg")'
    )
    
    attachment_ids = fields.Many2many(
        'ir.attachment',
        string='Documentos/Imágenes Adicionales',
        help='Adjunte fotos o PDFs para que la IA extraiga información'
    )
    
    ai_response_text = fields.Html(
        string='Respuesta de la IA',
        readonly=True
    )
    
    pending_changes_json = fields.Text(
        string='Cambios Pendientes (JSON)',
        readonly=True
    )
    
    ai_response_preview = fields.Html(
        string='Preview de Cambios',
        readonly=True
    )
    
    has_pending_changes = fields.Boolean(
        compute='_compute_has_pending_changes',
        string='Tiene Cambios Pendientes'
    )
    
    has_deletions = fields.Boolean(
        string='Contiene Eliminaciones',
        default=False
    )
    
    deletion_confirmed = fields.Boolean(
        string='Confirmo que deseo ELIMINAR las líneas marcadas',
        default=False
    )
    
    processing_status = fields.Selection([
        ('idle', 'Entrada'),
        ('response', 'Respuesta Informativa'),
        ('changes_ready', 'Cambios Propuestos'),
        ('applied', 'Aplicado')
    ], string='Estado', default='idle')

    history_json = fields.Text(string='Historial de Conversación', default='[]')
    
    chat_history_html = fields.Html(
        string='Muro de Conversación',
        readonly=True
    )

    @api.depends('pending_changes_json')
    def _compute_has_pending_changes(self):
        for wizard in self:
            wizard.has_pending_changes = bool(wizard.pending_changes_json)

    def _get_goods_update_tool_definition(self):
        """Define la herramienta que usará la IA para proponer cambios"""
        return {
            "type": "function",
            "function": {
                "name": "update_goods_lines",
                "description": "Actualiza, agrega o elimina líneas en la tabla de paquetes y mercancías",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "items": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "line_id": {
                                        "type": ["integer", "null"],
                                        "description": "ID de la línea existente (LINE_ID). null para líneas nuevas."
                                    },
                                    "action": {
                                        "type": "string",
                                        "enum": ["update", "delete", "add"],
                                        "description": "Acción a realizar en la línea"
                                    },
                                    "changes": {
                                        "type": "object",
                                        "description": "Solo para action=update. Campos que cambian.",
                                        "properties": {
                                            "name": {"type": "string"},
                                            "quantity": {"type": "number"},
                                            "fob": {"type": "number"},
                                            "gross_weight": {"type": "number"},
                                            "tariff_item": {"type": "string"},
                                            "id_hs_copmt_cd": {"type": "string"},
                                            "id_hs_spmt_cd": {"type": "string"},
                                            "invoice_number": {"type": "string"},
                                            "supplier": {"type": "string"},
                                            "packages_count": {"type": "string"},
                                            "observation": {"type": "string"}
                                        }
                                    },
                                    "name": {"type": "string", "description": "Para add: Nombre"},
                                    "quantity": {"type": "number", "description": "Para add: Cantidad"},
                                    "fob": {"type": "number", "description": "Para add: Precio unitario FOB"},
                                    "gross_weight": {"type": "number", "description": "Para add: Peso bruto"},
                                    "tariff_item": {"type": "string", "description": "Para add: Partida Arancelaria (10 dígitos)"},
                                    "id_hs_copmt_cd": {"type": "string", "description": "Para add: Código Complementario"},
                                    "id_hs_spmt_cd": {"type": "string", "description": "Para add: Código Suplementario"},
                                    "invoice_number": {"type": "string", "description": "Para add: Nro factura"},
                                    "supplier": {"type": "string", "description": "Para add: Proveedor"},
                                    "packages_count": {"type": "string", "description": "Para add: Cantidad de bultos"},
                                    "observation": {"type": "string", "description": "Para add: Observación"},
                                    "reason": {
                                        "type": "string", 
                                        "description": "Explicación breve de por qué se realiza este cambio (en español)"
                                    }
                                },
                                "required": ["action"]
                            }
                        },
                        "vessel_id": {
                            "type": "integer",
                            "description": "ID del nuevo buque a asignar a la solicitud (si el usuario pide cambiar el buque)"
                        },
                        "summary": {
                            "type": "string",
                            "description": "Resumen general de los cambios realizados en español"
                        }
                    },
                    "required": ["items"]
                }
            }
        }

    def _get_vessels_catalog_prompt(self):
        """Genera un catálogo de buques para el prompt de la IA"""
        vessels = self.env['ek.ship.registration'].search([])
        if not vessels:
            return "No hay buques registrados actualmente."
        
        lines = ["Catálogo de Buques (ID | Nombre):"]
        for v in vessels:
            lines.append(f"{v.id} | {v.name}")
        return "\n".join(lines)

    def _build_context_snapshot(self):
        """Genera una representación textual de la tabla actual para el prompt"""
        lines = self.operation_request_id.ek_produc_packages_goods_ids
        if not lines:
            return "La tabla de mercancías está actualmente VACÍA."

        headers = ["LINE_ID", "Nombre", "Cant", "FOB", "Peso", "Bultos", "Partida", "Comp.", "Supl."]
        rows = []
        for l in lines:
            rows.append(f"| {l.id} | {l.name or ''} | {l.quantity} | {l.fob} | {l.gross_weight} | {l.packages_count or ''} | {l.tariff_item or ''} | {l.id_hs_copmt_cd or ''} | {l.id_hs_spmt_cd or ''} |")
        
        md_table = "| " + " | ".join(headers) + " |\n"
        md_table += "|-" + "-|-".join(["-"*len(h) for h in headers]) + "-|\n"
        md_table += "\n".join(rows)

        return md_table

    def _markdown_to_html(self, text):
        """Conversión básica de Markdown a HTML para visualización"""
        if not text:
            return ""
        
        # Limpieza básica de etiquetas HTML previas si las hay
        text = str(text).replace('<', '&lt;').replace('>', '&gt;')
        
        # 1. Bold: **text** -> <strong>text</strong>
        text = re.sub(r'\*\*(.*?)\*\*', r'<strong>\1</strong>', text)
        
        # 2. Encabezados: ### Titulo -> <h3>Titulo</h3>
        text = re.sub(r'### (.*?)\n', r'<h3>\1</h3>', text)
        text = re.sub(r'## (.*?)\n', r'<h2>\1</h2>', text)
        
        # 3. Listas: * ítem -> <li>ítem</li>
        lines = text.split('\n')
        processed_lines = []
        in_list = False
        for line in lines:
            clean_line = line.strip()
            if clean_line.startswith(('* ', '- ')):
                if not in_list:
                    processed_lines.append('<ul class="pl-3">')
                    in_list = True
                content = clean_line[2:]
                processed_lines.append(f'<li>{content}</li>')
            else:
                if in_list:
                    processed_lines.append('</ul>')
                    in_list = False
                processed_lines.append(line)
        if in_list:
            processed_lines.append('</ul>')
        
        res = "\n".join(processed_lines)
        
        # 4. Saltos de línea
        res = res.replace('\n', '<br/>')
        
        return res

    def _update_chat_history_html(self, history):
        """Genera el HTML del hilo de conversación para el usuario"""
        html = ["<div class='ai_chat_thread' style='max-height: 400px; overflow-y: auto;'>"]
        
        for msg in history:
            role = msg.get('role')
            content = msg.get('content') or ""
            
            if role == 'system':
                continue
            
            # Estilo burbuja
            bg_color = "#f8f9fa" if role == 'user' else "#e7f3ff"
            align = "margin-right: 40px;" if role == 'user' else "margin-left: 40px;"
            label = "Tú" if role == 'user' else "IA"
            label_color = "#6c757d" if role == 'user' else "#007bff"
            
            html.append(f"""
                <div style='background: {bg_color}; padding: 10px; border-radius: 8px; margin-bottom: 10px; {align} border-left: 4px solid {label_color};'>
                    <small style='color: {label_color}; font-weight: bold;'>{label}</small><br/>
                    {self._markdown_to_html(content)}
                </div>
            """)
            
        html.append("</div>")
        self.chat_history_html = Markup("".join(html))

    def action_process(self):
        """Llama al LLM y procesa la respuesta"""
        self.ensure_one()
        if not self.user_text and not self.attachment_ids:
            raise UserError(_("Por favor proporcione una instrucción o adjunte un documento."))

        # 1. Preparar Contexto
        request = self.operation_request_id
        snapshot = self._build_context_snapshot()
        catalog_prompt = request._get_regime_70_catalog_prompt()

        system_prompt = f"""Eres un asistente experto en logística aduanera y comercio marítimo internacional.
Operas dentro del sistema de gestión de solicitudes navieras de la empresa.

## INFORMACIÓN DE LA SOLICITUD
- Solicitud Nro: {request.name}
- Tipo: {request.type_id.name}
- Régimen: {request.regime}
- Buque: {request.ek_ship_registration_id.name}
- BL: {request.id_bl or request.number_bl or 'N/A'}
- Contenedor: {request.number_container or 'N/A'}
- Sello: {request.seal_number or 'N/A'}

## TABLA ACTUAL DE MERCANCÍAS
OBLIGATORIO: Usa el LINE_ID para referenciar líneas existentes.

{snapshot}

## CATÁLOGO RÉGIMEN 70
{catalog_prompt}

## CATÁLOGO DE BUQUES
{self._get_vessels_catalog_prompt()}

## TU TAREA
Analiza la instrucción del usuario.
- Si es una pregunta o comentario: responde con texto.
- Si requiere cambios: llama al tool 'update_goods_lines'.

REGLAS DEL TOOL:
- update: requiere line_id y objeto 'changes' con solo lo que cambia.
- delete: requiere line_id y 'reason'.
- add: line_id debe ser null. Proporciona campos requeridos.
- Nombres: [Tipo] [Marca] [Modelo] [Especificación] (máx 60 chars).

## CLASIFICACIÓN ARANCELARIA (IMPORTANTE)
Cuando el usuario pida actualizar la "partida" o códigos de aduana, usa estos campos:
- tariff_item: Partida Arancelaria (Subpartida)
- id_hs_copmt_cd: Código Complementario (Comp.)
- id_hs_spmt_cd: Código Suplementario (Suplem.)

Responde siempre en español."""

        # 2. Llamada a LLM
        llm = self.env['nsk.llm.provider']
        
        # Cargar historial previo
        history = json.loads(self.history_json or '[]')
        
        # Añadir mensaje actual al historial (solo si hay texto o el historial está vacío)
        if self.user_text or not history:
            history.append({
                "role": "user", 
                "content": self.user_text or "Procesar archivos adjuntos para actualizar la tabla."
            })

        messages = [
            {"role": "system", "content": system_prompt}
        ] + history
        
        try:
            response = llm.generate_completion(
                messages=messages,
                attachments=self.attachment_ids,
                tools=[self._get_goods_update_tool_definition()]
            )

            # 3. Procesar Respuesta
            msg = response.choices[0].message
            
            # Guardar respuesta en el historial
            history.append({
                "role": "assistant",
                "content": msg.content or "(Acción técnica propuesta)"
            })
            self.history_json = json.dumps(history)
            self._update_chat_history_html(history)

            if msg.tool_calls:
                tool_call = msg.tool_calls[0]
                changes_data = json.loads(tool_call.function.arguments)
                
                self.pending_changes_json = json.dumps(changes_data)
                self.ai_response_preview = self._render_changes_preview(changes_data)
                self.processing_status = 'changes_ready'
                
                # Verificar si hay eliminaciones
                self.has_deletions = any(item.get('action') == 'delete' for item in changes_data.get('items', []))
            else:
                self.ai_response_text = self._markdown_to_html(msg.content)
                self.processing_status = 'response'
                self.user_text = False # Limpiar para permitir chat

        except Exception as e:
            _logger.error("Error en AI Goods Wizard: %s", str(e))
            raise UserError(_("Error al procesar con IA: %s") % str(e))

        return {
            'type': 'ir.actions.act_window',
            'res_model': self._name,
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
        }

    def _render_changes_preview(self, data):
        """Genera un HTML con el resumen de cambios para el usuario"""
        items = data.get('items', [])
        summary = data.get('summary', 'La IA propone los siguientes cambios:')
        vessel_id = data.get('vessel_id')
        
        html = f"<div class='ai_preview'><h4>{summary}</h4>"

        if vessel_id:
            vessel = self.env['ek.ship.registration'].browse(vessel_id)
            current_vessel = self.operation_request_id.ek_ship_registration_id.name or 'Ninguno'
            html += f"<div class='alert alert-info'><strong>🚢 CAMBIO DE BUQUE</strong><br/>{current_vessel} &rarr; <strong>{vessel.name}</strong></div>"
        
        # Agrupar acciones
        deletes = [i for i in items if i['action'] == 'delete']
        updates = [i for i in items if i['action'] == 'update']
        adds = [i for i in items if i['action'] == 'add']

        if deletes:
            html += "<div class='alert alert-danger'><strong>🔴 ELIMINAR</strong><ul class='mb-0'>"
            for d in deletes:
                line = self.env['ek.product.packagens.goods'].browse(d['line_id'])
                html += f"<li>ID {d['line_id']}: {line.name or 'Item'} - <em>{d.get('reason', '')}</em></li>"
            html += "</ul></div>"

        if updates:
            html += "<div class='alert alert-warning'><strong>🟡 ACTUALIZAR</strong><table class='table table-sm table-borderless mb-0'>"
            for u in updates:
                line = self.env['ek.product.packagens.goods'].browse(u['line_id'])
                html += f"<tr><td colspan='2'><strong>ID {u['line_id']}: {line.name}</strong></td></tr>"
                field_labels = {
                    'name': 'Nombre',
                    'quantity': 'Cantidad',
                    'fob': 'FOB',
                    'gross_weight': 'Peso',
                    'tariff_item': 'Partida',
                    'id_hs_copmt_cd': 'Comp.',
                    'id_hs_spmt_cd': 'Suplem.',
                    'invoice_number': 'Factura',
                    'supplier': 'Proveedor',
                    'packages_count': 'Bultos',
                    'observation': 'Obs.'
                }
                for field, val in u.get('changes', {}).items():
                    label = field_labels.get(field, field)
                    old_val = getattr(line, field, 'N/A')
                    html += f"<tr><td class='ps-3 text-muted'>{label}:</td><td>{old_val} &rarr; <strong>{val}</strong></td></tr>"
            html += "</table></div>"

        if adds:
            html += "<div class='alert alert-success'><strong>🟢 AGREGAR</strong><ul class='mb-0'>"
            for a in adds:
                html += f"<li>{a.get('name', 'Nuevo Item')} (Cant: {a.get('quantity', 1)}, FOB: {a.get('fob', 0)})</li>"
            html += "</ul></div>"

        html += "</div>"
        return html

    def action_apply_pending_changes(self):
        """Aplica los cambios del JSON a la base de datos"""
        self.ensure_one()
        if not self.pending_changes_json:
            return

        if self.has_deletions and not self.deletion_confirmed:
            raise UserError(_("Debe confirmar que desea eliminar las líneas marcadas en rojo."))

        # Lista de campos válidos en el modelo destino para evitar errores de 'Invalid field'
        VALID_FIELDS = [
            'name', 'quantity', 'fob', 'gross_weight', 'tariff_item', 
            'id_hs_copmt_cd', 'id_hs_spmt_cd', 'invoice_number', 
            'supplier', 'packages_count', 'observation', 'ship_id'
        ]

        try:
            data = json.loads(self.pending_changes_json)
            items = data.get('items', [])
            goods_model = self.env['ek.product.packagens.goods']
            
            applied_summary = []

            # Cambio de buque
            vessel_id = data.get('vessel_id')
            if vessel_id:
                vessel = self.env['ek.ship.registration'].browse(vessel_id)
                self.operation_request_id.ek_ship_registration_id = vessel.id
                applied_summary.append(f"<li>Buque actualizado a: <strong>{vessel.name}</strong></li>")

            for item in items:
                action = item['action']
                line_id = item.get('line_id')
                
                if action == 'delete' and line_id:
                    line = goods_model.browse(line_id)
                    name = line.name
                    line.unlink()
                    applied_summary.append(f"<li>Eliminado: {name} (ID {line_id})</li>")
                
                elif action == 'update' and line_id:
                    line = goods_model.browse(line_id)
                    changes = item.get('changes', {})
                    
                    # Limpiar cambios de campos inexistentes (como 'reason')
                    # Si viene 'reason' dentro de changes, lo movemos a 'observation' si este está vacío
                    if 'reason' in changes and 'observation' not in changes:
                        changes['observation'] = changes.pop('reason')
                    
                    filtered_changes = {k: v for k, v in changes.items() if k in VALID_FIELDS}
                    
                    if filtered_changes:
                        line.write(filtered_changes)
                        applied_summary.append(f"<li>Actualizado: {line.name} (ID {line_id})</li>")
                
                elif action == 'add':
                    # Preparar valores filtrando solo los válidos
                    raw_vals = {
                        'ek_operation_request_id': self.operation_request_id.id,
                        'name': item.get('name'),
                        'quantity': item.get('quantity', 0),
                        'fob': item.get('fob', 0),
                        'gross_weight': item.get('gross_weight', 0),
                        'tariff_item': item.get('tariff_item'),
                        'id_hs_copmt_cd': item.get('id_hs_copmt_cd'),
                        'id_hs_spmt_cd': item.get('id_hs_spmt_cd'),
                        'invoice_number': item.get('invoice_number'),
                        'supplier': item.get('supplier'),
                        'packages_count': item.get('packages_count'),
                        'observation': item.get('observation') or item.get('reason'),
                    }
                    filtered_vals = {k: v for k, v in raw_vals.items() if k in VALID_FIELDS or k == 'ek_operation_request_id'}
                    
                    new_line = goods_model.create(filtered_vals)
                    applied_summary.append(f"<li>Agregado: {new_line.name}</li>")

            # Log en Chatter
            log_body = f"<strong>IA: Actualización quirúrgica de mercancías</strong><ul>{''.join(applied_summary)}</ul>"
            self.operation_request_id.message_post(body=Markup(log_body))

            return {'type': 'ir.actions.client', 'tag': 'reload'}

        except Exception as e:
            raise UserError(_("Error al aplicar cambios: %s") % str(e))

    def action_back_to_input(self):
        self.processing_status = 'idle'
        self.pending_changes_json = False
        self.ai_response_preview = False
        return {
            'type': 'ir.actions.act_window',
            'res_model': self._name,
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
        }
