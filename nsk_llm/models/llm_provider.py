from odoo import models, fields, api, _
from odoo.exceptions import UserError
import logging
import base64
import io
import json

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
