# Scripts de Debugging para Delivery Report Fields

## Scripts para ejecutar en la consola del navegador

### 1. Verificar que el módulo JavaScript se cargó
```javascript
window.debugDeliveryFields.checkModuleLoaded()
```
**Resultado esperado:** Debe mostrar "✓ Módulo ek_button_js.js cargado correctamente"

### 2. Verificar que la acción está registrada
```javascript
window.debugDeliveryFields.checkActionRegistered()
```
**Resultado esperado:** Debe mostrar instrucciones para verificar la acción

### 3. Verificar la acción directamente (más completo)
```javascript
// Obtener el registry de acciones
const registry = odoo.loader.modules.get("@web/core/registry");
const actions = registry.category("actions");
const action = actions.get("refresh_delivery_fields");
console.log("Acción registrada:", !!action);
console.log("Acción:", action);
```

### 4. Verificar servicios disponibles
```javascript
// Acceder a los servicios del entorno actual
const actionService = odoo.__DEBUG__.services?.action;
const notificationService = odoo.__DEBUG__.services?.notification;
console.log("Action service:", !!actionService);
console.log("Notification service:", !!notificationService);
```

### 5. Verificar controladores activos
```javascript
const actionService = odoo.__DEBUG__.services?.action;
if (actionService) {
  console.log("Controladores activos:", actionService.activeControllers);
  console.log("Controlador actual:", actionService.currentController);
}
```

### 6. Probar la acción manualmente
```javascript
// Obtener el ID del registro actual desde la URL o el formulario
const urlParams = new URLSearchParams(window.location.search);
const resId = urlParams.get('id') || prompt('Ingrese el ID del registro:');

// Ejecutar la acción
const registry = odoo.loader.modules.get("@web/core/registry");
const actions = registry.category("actions");
const action = actions.get("refresh_delivery_fields");
const env = odoo.__DEBUG__.services;

if (action && env) {
  action(env, {
    params: {
      message: "Test de recarga",
      parent_model: "ek.operation.request",
      parent_id: parseInt(resId),
    }
  });
}
```

### 7. Verificar si hay errores en la consola
```javascript
// Revisar errores recientes
console.log("Últimos errores:", window.console._errors || []);
```

### 8. Verificar que los campos se actualizaron
```javascript
// En el formulario de la solicitud, verificar los valores de los campos
const formView = document.querySelector('.o_form_view');
if (formView) {
  const sequenceField = formView.querySelector('[name="delivery_report_sequence_code"]');
  const hasSequenceField = formView.querySelector('[name="delivery_report_has_sequence"]');
  console.log("Campo sequence_code:", sequenceField?.value);
  console.log("Campo has_sequence:", hasSequenceField?.checked);
}
```

## Troubleshooting

### Si el módulo no se carga:
1. Verifica que el archivo está en `static/src/js/ek_button_js.js`
2. Verifica que está incluido en `__manifest__.py` en la sección `assets`
3. Recarga el navegador con Ctrl+F5 (hard refresh)
4. Verifica la consola del navegador para errores de JavaScript

### Si la acción no está registrada:
1. Verifica que el código JavaScript se ejecutó sin errores
2. Verifica que `registry.category("actions").add("refresh_delivery_fields", ...)` se ejecutó
3. Intenta recargar el módulo desde el modo desarrollador

### Si la vista no se recarga:
1. Verifica que `parent_model` y `parent_id` se están pasando correctamente
2. Verifica que el servicio `action` está disponible
3. Revisa la consola para errores de JavaScript

