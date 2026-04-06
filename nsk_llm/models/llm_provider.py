from odoo import models, fields, api, _
from odoo.exceptions import UserError
import logging
import base64
import json

_logger = logging.getLogger(__name__)

try:
    import litellm
except ImportError:
    litellm = None
    _logger.warning("litellm library not installed. Please install it using: pip install litellm")

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
    
    def _prepare_attachment_content(self, attachments):
        """
        Prepares attachments to be sent to the LLM.
        Generates public share URLs to avoid large payloads.
        Returns a list of content parts blocks compatible with litellm.
        """
        if not attachments:
            return []
            
        base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url')
        attachment_parts = []
        text_links = []
        
        for att in attachments:
            # Ensure access token exists
            if not att.access_token:
                att.generate_access_token()
                
            public_url = f"{base_url}/web/content/{att.id}?access_token={att.access_token}"
            mime_type = att.mimetype or ''
            
            if mime_type.startswith('image/'):
                # Send as image_url for multimodal models
                attachment_parts.append({
                    "type": "image_url",
                    "image_url": {
                        "url": public_url
                    }
                })
            else:
                # Add link to text references for the model to download/view
                text_links.append(f"- {att.name}: {public_url} (Type: {mime_type})")
                
        if text_links:
            attachment_parts.append({
                "type": "text",
                "text": "Se adjuntan los siguientes documentos de referencia (favor leer su contenido mediante las URLs):\n" + "\n".join(text_links)
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
