# Solución para Ancho Mínimo en Vista Kanban - Odoo 17

## Problema
El `min-width: 500px` en estilos inline no funcionaba en las tarjetas kanban porque Odoo 17 utiliza variables CSS específicas del sistema para controlar el ancho de las tarjetas.

## Solución Implementada

### 1. Archivo SCSS Personalizado
Se creó el archivo `ek_ship_registration_kanban.scss` que utiliza las variables CSS oficiales de Odoo 17:

```scss
.o_kanban_view.ek_ship_registration_kanban .o_kanban_renderer {
    // Establecer el ancho mínimo de las tarjetas kanban
    --KanbanRecord-width: 500px;
    
    // Para vistas agrupadas, ajustar el ancho de las columnas
    &.o_kanban_grouped {
        --KanbanGroup-width: calc(500px + (2 * var(--KanbanGroup-padding-h)));
    }
}
```

### 2. Clase CSS Personalizada
Se agregó la clase `ek_ship_registration_kanban` al elemento `<kanban>` en la vista XML.

### 3. Configuración del Manifiesto
Se incluyó el archivo SCSS en la sección de assets del manifiesto:

```python
"assets": {
    "web.assets_backend": [
        # ... otros assets
        "ek_l10n_shipping_operations/static/src/scss/*.scss",
    ],
},
```

## Variables CSS de Odoo 17 para Kanban

### Principales:
- `--KanbanRecord-width`: Ancho de las tarjetas kanban
- `--KanbanRecord--small-width`: Ancho para tarjetas pequeñas
- `--KanbanGroup-width`: Ancho de las columnas en vistas agrupadas

### Valores por defecto:
- `--KanbanRecord-width`: 320px
- `--KanbanRecord--small-width`: 300px

## Ventajas de esta Solución

1. **Compatibilidad**: Utiliza el sistema oficial de variables CSS de Odoo 17
2. **Responsive**: Se adapta automáticamente a diferentes tamaños de pantalla
3. **Mantenible**: Los estilos están centralizados en archivos SCSS
4. **Escalable**: Fácil de modificar y extender para otros módulos

## Notas Importantes

- **NUNCA** usar `min-width` en estilos inline para tarjetas kanban
- **SIEMPRE** usar las variables CSS oficiales de Odoo 17
- Los estilos SCSS se compilan automáticamente al actualizar el módulo
- La clase CSS personalizada debe ser única para evitar conflictos


