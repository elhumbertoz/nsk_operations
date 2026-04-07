from odoo import models, fields, api, _
from odoo.exceptions import UserError
import logging
import base64
import io
import json
import subprocess
import tempfile
import os

_logger = logging.getLogger(__name__)

try:
    import litellm
except ImportError:
    litellm = None
    _logger.warning("litellm library not installed. Please install it using: pip install litellm")

try:
    import pypdfium2 as _pdfium
    _PDFIUM_AVAILABLE = True
except ImportError:
    _pdfium = None
    _PDFIUM_AVAILABLE = False
    _logger.warning(
        "pypdfium2 library not installed. PDF pages will not be converted to images. "
        "Install with: pip install pypdfium2"
    )

class LLMProvider(models.Model):
    _name = 'nsk.llm.provider'
    _description = 'LLM Configuration Provider'
    
    name = fields.Char(string='Name', required=True)
    active = fields.Boolean(default=True)
    provider_type = fields.Selection([
        ('openai', 'OpenAI'),
        ('anthropic', 'Anthropic (Claude)'),
        ('gemini', 'Google Gemini'),
        ('ollama', 'Local (Ollama)'),
        ('other', 'Other (LiteLLM Format)'),
    ], string='Provider Type', required=True, default='openai')
    
    model_name = fields.Char(string='Model Name', required=True, help="e.g., gpt-4o, claude-3-5-sonnet-20240620, gemini/gemini-1.5-pro")
    api_key = fields.Char(string='API Key')
    api_base = fields.Char(string='API Base URL', help="Optional. Useful for Ollama or custom endpoints.")
    
    def _pdf_to_image_parts(self, att, dpi=150):
        """
        Convierte cada página de un PDF en una imagen JPEG y la devuelve
        como bloque image_url con data URI base64.

        Usa pypdfium2 (PDFium, motor de Chrome) — no requiere poppler ni
        dependencias de sistema.

        :param att: ir.attachment con mimetype application/pdf
        :param dpi: resolución de renderizado (150 dpi: buen balance calidad/tamaño)
        :returns: lista de bloques image_url listos para litellm
        """
        if not _PDFIUM_AVAILABLE:
            _logger.error(
                "pypdfium2 no está instalado. No se puede convertir '%s' a imágenes. "
                "Instalar con: pip install pypdfium2",
                att.name
            )
            return []

        try:
            pdf_bytes = base64.b64decode(att.datas)
            doc = _pdfium.PdfDocument(pdf_bytes)
        except Exception as e:
            _logger.error("Error al abrir PDF '%s': %s", att.name, str(e))
            return []

        scale = dpi / 72.0  # PDFium trabaja en puntos (72 pt = 1 pulgada)
        parts = []

        try:
            for page_num in range(len(doc)):
                page = doc[page_num]
                bitmap = page.render(scale=scale)
                pil_img = bitmap.to_pil()

                buffer = io.BytesIO()
                pil_img.save(buffer, format='JPEG', quality=85, optimize=True)
                img_b64 = base64.b64encode(buffer.getvalue()).decode()

                parts.append({
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:image/jpeg;base64,{img_b64}"
                    }
                })
                _logger.debug(
                    "PDF '%s' página %s/%s → JPEG %dx%d px.",
                    att.name, page_num + 1, len(doc),
                    pil_img.width, pil_img.height
                )
        finally:
            doc.close()

        _logger.info(
            "PDF '%s' convertido: %s página(s) como imágenes JPEG (dpi=%s).",
            att.name, len(parts), dpi
        )
        return parts

    def _excel_to_image_parts(self, att):
        """
        Convierte un archivo Excel (.xlsx, .xls) a imágenes JPEG (una por hoja)
        para que los modelos de visión de la IA puedan procesar el contenido tabular.
        
        Requiere: pandas, openpyxl y wkhtmltoimage (en el sistema).
        """
        try:
            import pandas as pd
        except ImportError:
            _logger.error("Pandas no instalado. No se puede convertir Excel.")
            return []

        file_data = base64.b64decode(att.datas)
        parts = []
        
        with tempfile.TemporaryDirectory() as tmpdir:
            excel_path = os.path.join(tmpdir, "input_file")
            # Determinar extensión para que pandas no se confunda
            ext = ".xlsx" if att.name.lower().endswith(".xlsx") else ".xls"
            if not att.name.lower().endswith((".xlsx", ".xls")):
                ext = ".xlsx" # Default
            
            local_path = excel_path + ext
            with open(local_path, 'wb') as f:
                f.write(file_data)
            
            try:
                # Usar pd.ExcelFile para detectar hojas
                excel_file = pd.ExcelFile(local_path)
                
                for sheet_name in excel_file.sheet_names:
                    # Leer hoja (limitar filas para no crear imágenes gigantes)
                    df = pd.read_excel(local_path, sheet_name=sheet_name).head(100)
                    if df.empty:
                        continue
                    
                    # Convertir a HTML con estilos mínimos
                    html_table = df.to_html(index=False, border=1)
                    full_html = f"""
                    <html>
                    <head>
                        <meta charset="utf-8">
                        <style>
                            body {{ font-family: 'Helvetica', 'Arial', sans-serif; padding: 20px; background: white; }}
                            table {{ border-collapse: collapse; width: 100%; font-size: 12px; }}
                            th, td {{ border: 1px solid #ccc; padding: 6px; text-align: left; }}
                            th {{ background-color: #f1f1f1; font-weight: bold; }}
                            h2 {{ color: #333; border-bottom: 2px solid #555; padding-bottom: 5px; }}
                        </style>
                    </head>
                    <body>
                        <h2>Hoja: {sheet_name}</h2>
                        {html_table}
                    </body>
                    </html>
                    """
                    
                    html_file = os.path.join(tmpdir, f"sheet.html")
                    img_file = os.path.join(tmpdir, f"sheet.jpg")
                    
                    with open(html_file, 'w', encoding='utf-8') as f:
                        f.write(full_html)
                    
                    # Llamar a wkhtmltoimage
                    try:
                        subprocess.run([
                            'wkhtmltoimage',
                            '--quiet',
                            '--quality', '90',
                            '--encoding', 'utf-8',
                            html_file, img_file
                        ], check=True, timeout=30)
                        
                        if os.path.exists(img_file):
                            with open(img_file, 'rb') as f:
                                img_data = base64.b64encode(f.read()).decode()
                            
                            parts.append({
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/jpeg;base64,{img_data}"
                                }
                            })
                            _logger.info("Hoja '%s' convertida a imagen.", sheet_name)
                    except Exception as e:
                        _logger.warning("Error ejecutando wkhtmltoimage para hoja %s: %s", sheet_name, e)
            except Exception as e:
                _logger.error("Error procesando Excel '%s': %s", att.name, e)
                
        return parts

    def _prepare_attachment_content(self, attachments):
        """
        Prepara los adjuntos para enviarlos al LLM como bloques multimodal.

        - Imágenes nativas → image_url con URL pública.
        - PDFs → cada página convertida a JPEG y enviada como image_url base64
          (los modelos de visión interpretan mejor imágenes que archivos PDF crudos).
        - Otros formatos → referencia de texto como fallback.

        Returns: lista de content parts compatible con litellm.
        """
        if not attachments:
            return []

        base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url')
        attachment_parts = []
        text_links = []

        for att in attachments:
            mime_type = att.mimetype or ''

            if mime_type.startswith('image/'):
                # Imagen nativa: enviar como URL pública
                if not att.access_token:
                    att.generate_access_token()
                public_url = f"{base_url}/web/content/{att.id}?access_token={att.access_token}"
                attachment_parts.append({
                    "type": "image_url",
                    "image_url": {"url": public_url}
                })

            elif mime_type == 'application/pdf' or att.name.lower().endswith('.pdf'):
                # PDF → convertir páginas a imágenes y enviar como base64
                pdf_parts = self._pdf_to_image_parts(att)
                if pdf_parts:
                    # Añadir etiqueta de contexto antes de las imágenes del documento
                    attachment_parts.append({
                        "type": "text",
                        "text": f"[Documento: {att.name} — {len(pdf_parts)} página(s)]"
                    })
                    attachment_parts.extend(pdf_parts)
                else:
                    # Fallback si la conversión falló
                    if not att.access_token:
                        att.generate_access_token()
                    public_url = f"{base_url}/web/content/{att.id}?access_token={att.access_token}"
                    text_links.append(f"- {att.name}: {public_url} (PDF — conversión no disponible)")

            elif mime_type in ['application/vnd.openxmlformats-officedocument.spreadsheetml.sheet', 'application/vnd.ms-excel'] or att.name.lower().endswith(('.xlsx', '.xls')):
                # Excel -> Convertir hojas a imágenes usando Pandas + wkhtmltoimage
                _logger.info("Convirtiendo Excel '%s' a imágenes...", att.name)
                excel_parts = self._excel_to_image_parts(att)
                if excel_parts:
                    attachment_parts.append({
                        "type": "text",
                        "text": f"[Documento Excel: {att.name} — {len(excel_parts)} hoja(s)]"
                    })
                    attachment_parts.extend(excel_parts)
                else:
                    if not att.access_token:
                        att.generate_access_token()
                    public_url = f"{base_url}/web/content/{att.id}?access_token={att.access_token}"
                    text_links.append(f"- {att.name}: {public_url} (Excel — conversión a imagen falló)")

            else:
                # Otros formatos: referencia de texto
                if not att.access_token:
                    att.generate_access_token()
                public_url = f"{base_url}/web/content/{att.id}?access_token={att.access_token}"
                text_links.append(f"- {att.name}: {public_url} (Tipo: {mime_type})")

        if text_links:
            attachment_parts.append({
                "type": "text",
                "text": (
                    "Documentos de referencia adicionales:\n" + "\n".join(text_links)
                )
            })

        return attachment_parts

    @api.model
    def generate_completion(self, messages, tools=None, attachments=None, provider_id=None):
        """
        Main method to call an LLM. 
        :param messages: list of dicts [{"role": "user", "content": "..."}]
        :param tools: list of tool definitions (OpenAI tool calling format)
        :param attachments: ir.attachment recordset
        :param provider_id: specific nsk.llm.provider ID to use. If None, uses default from settings.
        :return: dict with response from LLM
        """
        if litellm is None:
            raise UserError(_("The 'litellm' python library is required. Install it using 'pip install litellm'"))
            
        if provider_id:
            provider = self.browse(provider_id)
        else:
            default_provider_id = int(self.env['ir.config_parameter'].sudo().get_param('nsk_llm.default_provider_id', 0))
            if not default_provider_id:
                raise UserError(_("No default LLM provider configured. Please set one in General Settings."))
            provider = self.browse(default_provider_id)
            if not provider.exists():
                raise UserError(_("The default LLM provider does not exist."))
                
        # Format messages to inject attachments
        formatted_messages = list(messages)
        if attachments:
            att_contents = self._prepare_attachment_content(attachments)
            if att_contents:
                # Inject to the last user message
                # Find last user message
                last_user_idx = -1
                for i in range(len(formatted_messages) - 1, -1, -1):
                    if formatted_messages[i].get('role') == 'user':
                        last_user_idx = i
                        break
                        
                if last_user_idx != -1:
                    original_content = formatted_messages[last_user_idx].get('content', '')
                    if isinstance(original_content, str):
                        content_list = [{"type": "text", "text": original_content}]
                    elif isinstance(original_content, list):
                        content_list = original_content
                    else:
                        content_list = []
                        
                    content_list.extend(att_contents)
                    formatted_messages[last_user_idx]['content'] = content_list

        try:
            kwargs = {
                "model": provider.model_name,
                "messages": formatted_messages,
            }
            if provider.api_key:
                kwargs["api_key"] = provider.api_key
            if provider.api_base:
                kwargs["api_base"] = provider.api_base
            if tools:
                kwargs["tools"] = tools

            _logger.info(f"Calling LLM provider: {provider.name} (Model: {provider.model_name})")
            response = litellm.completion(**kwargs)
            return response

        except Exception as e:
            _logger.error(f"Error calling LLM APIs: {str(e)}")
            raise UserError(_("Error communicating with LLM Provider:\n%s") % str(e))

    def action_test_connection(self):
        self.ensure_one()
        messages = [{"role": "user", "content": "Hello, this is a test. Reply precisely with 'Connection OK'."}]
        try:
            res = self.generate_completion(messages=messages, provider_id=self.id)
            content = res.get('choices', [{}])[0].get('message', {}).get('content', '')
            raise UserError(_("Connection Successful! LLM replied: \n%s") % content)
        except Exception as e:
            raise UserError(_("Connection failed:\n%s") % str(e))
