{
    'name': 'NSK LLM Client',
    'version': '1.0.0',
    'category': 'Technical Settings',
    'summary': 'Multi-provider LLM client for Odoo using litellm',
    'description': """
        This module provides an abstraction layer to communicate with multiple
        LLM providers (OpenAI, Anthropic, Gemini, etc.) via the litellm library.
        It supports text prompts, conversational history, tool calling, and attachments
        (images via base64, files via shared URLs).
    """,
    'author': 'Naviera',
    'depends': ['base', 'mail'],
    'data': [
        'security/ir.model.access.csv',
        'views/llm_provider_views.xml',
        'views/res_config_settings_views.xml',
    ],
    'external_dependencies': {
        'python': ['litellm'],
    },
    'images': [
        'static/description/icon.png',
        'static/description/icon_menu.png'
    ],
    'installable': True,
    'application': False,
    'license': 'LGPL-3',
}
