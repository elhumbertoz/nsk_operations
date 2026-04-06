# NSK LLM - Centralized LLM Provider for Odoo

Este módulo proporciona una capa de abstracción única para interactuar con diversos modelos de lenguaje (OpenAI, Anthropic, Gemini, Ollama, etc.) dentro de Odoo, utilizando la librería `litellm`.

## Características Principales

- **Configuración Centralizada**: Administra múltiples proveedores y API Keys desde un solo lugar.
- **Multimodal**: Soporte nativo para adjuntar documentos e imágenes (`ir.attachment`) en las solicitudes.
- **Function Calling (Tools)**: Compatible con la definición de herramientas para obtener respuestas JSON estructuradas.
- **Proveedor por Defecto**: Permite configurar un modelo global para que otros módulos lo usen sin configuración adicional.

## Instalación

1. Asegúrate de tener instalada la librería `litellm`:
   ```bash
   pip install litellm
   ```
2. Instala el módulo `nsk_llm` en Odoo.
3. Ve a **Ajustes Generales > LLM Settings** para configurar tu proveedor predeterminado.

---

## Uso de `generate_completion`

El método principal para interactuar con la IA es `generate_completion`:

```python
response = self.env['nsk.llm.provider'].generate_completion(
    messages=list_of_messages,
    tools=list_of_tools,        # Opcional
    attachments=recordset,      # Opcional (ir.attachment)
    provider_id=id              # Opcional (usa el default si no se envía)
)
```

### Parámetros:

- **`messages`**: Lista de diccionarios con el formato estándar de OpenAI (ej: `[{"role": "user", "content": "..."}]`).
- **`tools`**: Lista de definiciones de funciones (herramientas) en formato JSON schema.
- **`attachments`**: Recordset de Odoo (`ir.attachment`). Las imágenes se envían como `image_url` (multimodal) y otros archivos se incluyen como referencias de texto.
- **`provider_id`**: ID de un registro `nsk.llm.provider` específico si no quieres usar el predeterminado.

---

## Formato de Retorno

El método retorna un objeto de respuesta compatible con el estándar de OpenAI (vía `litellm.ModelResponse`).

### Estructura típica de éxito:

```python
{
  "id": "chatcmpl-...",
  "object": "chat.completion",
  "created": 1712437000,
  "model": "gpt-4o",
  "choices": [
    {
      "index": 0,
      "message": {
        "role": "assistant",
        "content": "...",           # Texto de respuesta (si no se usaron tools)
        "tool_calls": [            # Presente si el modelo invocó una herramienta
          {
            "id": "call_...",
            "type": "function",
            "function": {
              "name": "getDocumentInformation",
              "arguments": "{\"header\": {...}, \"items\": [...]}"
            }
          }
        ]
      },
      "finish_reason": "tool_calls"
    }
  ],
  "usage": {
    "prompt_tokens": 1200,
    "completion_tokens": 400,
    "total_tokens": 1600
  }
}
```

### Ejemplo de extracción de datos:

```python
if response.choices[0].message.tool_calls:
    tool_call = response.choices[0].message.tool_calls[0]
    data = json.loads(tool_call.function.arguments)
    print(data['header']['number'])
```

---

## Errores Comunes

- **"No default LLM provider configured"**: Debes ir a Ajustes y seleccionar un proveedor activo como predeterminado.
- **"litellm library not installed"**: Ejecuta `pip install litellm` en el entorno donde corre Odoo.
- **"Error communicating with LLM Provider"**: Revisa tu conexión a internet o la validez de tu API Key en la configuración del proveedor.
