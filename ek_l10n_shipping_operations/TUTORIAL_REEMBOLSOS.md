# 📚 Tutorial: Sistema de Control de Reembolsos

## 🎯 Introducción

Este tutorial te guiará paso a paso para usar el **Sistema de Control de Reembolsos** en Odoo. Este sistema automatiza el seguimiento de todos los reembolsos que deben ser facturados al cliente, evitando pérdidas por error humano.

---

## 📋 Tabla de Contenidos

1. [Configuración Inicial](#configuración-inicial)
2. [Crear una Solicitud de Reembolso](#crear-una-solicitud-de-reembolso)
3. [Seguir el Flujo de Estados](#seguir-el-flujo-de-estados)
   - [Estados del Sistema](#31-estados-del-sistema)
   - [Cuándo se Asigna Cada Estado](#311-cuándo-se-asigna-cada-estado)
   - [Triggers Detallados](#312-triggers-detallados)
   - [Logs de Debugging por Estado](#313-logs-de-debugging-por-estado)
4. [Gestionar Pagos](#gestionar-pagos)
   - [Pago Completo](#411-pago-completo)
   - [Pago Parcial](#412-pago-parcial)
   - [Eliminar Solicitud](#44-eliminar-solicitud)
5. [Monitorear Reembolsos](#monitorear-reembolsos)
6. [Solución de Problemas](#solución-de-problemas)

---

## 1. 🔧 Configuración Inicial

### 1.1 Verificar Tipo de Solicitud

Antes de crear solicitudes, asegúrate de que el tipo de solicitud esté configurado correctamente:

1. Ve a **Operaciones / Configuración / Tipos de Solicitud**
2. Selecciona el tipo de reembolso (ej: "ARRIBO NACIONAL")
3. Verifica que:
   - ✅ `Es reembolso de servicio` esté marcado
   - ✅ Tenga productos configurados en `Productos de reembolso`

### 1.2 Configurar Productos de Reembolso

1. En el tipo de solicitud, ve a la pestaña **Productos de reembolso**
2. Agrega los productos que se facturarán al cliente:
   - **Código**: Ej. `RG49`
   - **Descripción**: Ej. `REEMBOLSO DE GASTOS: TASA CAPMAN`
   - **Proveedor**: El proveedor que emite la factura
   - **Monto**: Monto base del reembolso

---

## 2. 📝 Crear una Solicitud de Reembolso

### 2.1 Crear la Solicitud

1. Ve a **Operaciones / Solicitudes de Operación**
2. Clic en **Crear**
3. Completa los campos:
   - **Tipo**: Selecciona el tipo de reembolso configurado
   - **Buque**: Selecciona el buque
   - **Viaje**: Selecciona el viaje
   - **Otros campos**: Según sea necesario

### 2.2 Activar el Seguimiento

1. **Cambia la etapa** de la solicitud (ej: de "Borrador" a "En Proceso")
2. **¡Automáticamente se crearán** los registros de seguimiento para todos los productos configurados
3. Verifica en la pestaña **Reembolsos** que aparezcan los registros

> **⚠️ Importante**: Los registros de seguimiento se crean **automáticamente** y **no se pueden crear o eliminar manualmente**. Solo el sistema puede gestionarlos.

---

## 3. 🔄 Seguir el Flujo de Estados

### 3.1 Estados del Sistema

El sistema sigue este flujo automáticamente:

```
Borrador → OC Pendiente → OC Confirmada → Factura Pendiente → Factura Recibida → Fac. Cliente Borrador → Fac. Cliente Enviada → Recuperado
```

### 3.1.1 Cuándo se Asigna Cada Estado

| Estado | Cuándo se Asigna | Trigger |
|--------|------------------|---------|
| **`Borrador`** | Al crear el registro automáticamente | Cambio de etapa en solicitud |
| **`OC Pendiente`** | Al crear orden de compra en estado borrador | Crear PO con solicitud asignada |
| **`OC Confirmada`** | Al confirmar la orden de compra | Confirmar PO |
| **`Factura Pendiente`** | Al crear factura de proveedor en borrador | Crear factura in_invoice con solicitud |
| **`Factura Recibida`** | Al confirmar factura de proveedor | Confirmar factura in_invoice |
| **`Fac. Cliente Borrador`** | Al crear factura de cliente en borrador | Crear factura out_invoice con solicitud |
| **`Fac. Cliente Enviada`** | Al confirmar factura de cliente | Confirmar factura out_invoice |
| **`Recuperado`** | Al pagar la factura de cliente (completa o parcial) | Pago conciliado en factura |
| **`Cancelado`** | Al cancelar PO o factura | Cancelar documento |

### 3.1.2 Triggers Detallados

#### 🔄 **Estados de Orden de Compra**
- **`OC Pendiente`**: Se asigna cuando se crea una PO con `operation_request_id` asignado y estado `draft`
- **`OC Confirmada`**: Se asigna cuando la PO cambia a estado `purchase` (confirmada)
- **`Cancelado`**: Se asigna cuando la PO se cancela

#### 📄 **Estados de Factura de Proveedor**
- **`Factura Pendiente`**: Se asigna cuando se crea una factura `in_invoice` con `operation_request_id` y estado `draft`
- **`Factura Recibida`**: Se asigna cuando la factura `in_invoice` se confirma (`posted`)
- **`Cancelado`**: Se asigna cuando la factura `in_invoice` se cancela

#### 💰 **Estados de Factura de Cliente**
- **`Fac. Cliente Borrador`**: Se asigna cuando se crea una factura `out_invoice` con `operation_request_id` y estado `draft`
- **`Fac. Cliente Enviada`**: Se asigna cuando la factura `out_invoice` se confirma (`posted`)
- **`Recuperado`**: Se asigna cuando la factura `out_invoice` se marca como pagada (`payment_state = 'paid'` o `'partial'`)
- **`Fac. Cliente Enviada`** (revertido): Se asigna cuando se rompe la conciliación de pago

### 3.1.3 Logs de Debugging por Estado

Para monitorear los cambios de estado, revisa los logs del servidor:

| Estado | Log a Buscar | Información |
|--------|--------------|-------------|
| **`OC Pendiente/Confirmada`** | `TRACKING_DEBUG` | Actualización desde PO |
| **`Factura Pendiente/Recibida`** | `TRACKING_DEBUG` | Actualización desde factura proveedor |
| **`Fac. Cliente Borrador/Enviada`** | `TRACKING_DEBUG` | Actualización desde factura cliente |
| **`Recuperado`** | `PAYMENT_DEBUG` | Pago conciliado (completo o parcial) |
| **`Fac. Cliente Enviada`** (revertido) | `UNPAYMENT_DEBUG` | Conciliación rota |

### 3.2 Crear Orden de Compra

1. **Crea una orden de compra** desde la solicitud
2. **Agrega los productos** de reembolso
3. **¡Automáticamente!** El campo "Recibido" se llena con la cantidad especificada en el tipo de solicitud
4. **Confirma la orden** → Los registros cambian a `PO Confirmada`

> **💡 Nota**: El sistema automáticamente establece la cantidad recibida igual a la cantidad solicitada, facilitando el proceso de confirmación de recepción.

### 3.3 Recibir Factura del Proveedor

1. **Crea una factura de proveedor** (`in_invoice`)
2. **Asigna la solicitud** en el campo `Solicitud de Operación`
3. **Confirma la factura** → Los registros cambian a `Factura Recibida`

### 3.4 Facturar al Cliente

1. **Crea una factura de cliente** (`out_invoice`)
2. **Asigna la solicitud** en el campo `Solicitud de Operación`
3. **Agrega los productos** de reembolso
4. **Confirma la factura** → Los registros cambian a `Fac. Cliente Enviada`

---

## 4. 💰 Gestionar Pagos

### 4.1 Pagar Factura de Cliente

#### 4.1.1 Pago Completo

1. **Ve a la factura de cliente**
2. **Asigna un pago** usando el botón "Registrar Pago"
3. **Ingresa el monto completo** de la factura
4. **¡Automáticamente!** Los registros cambian a `Recuperado`

#### 4.1.2 Pago Parcial

1. **Ve a la factura de cliente**
2. **Asigna un pago** usando el botón "Registrar Pago"
3. **Ingresa un monto menor** al total de la factura
4. **¡Automáticamente!** Los registros también cambian a `Recuperado`

> **💡 Nota**: El sistema considera **cualquier pago** (completo o parcial) como suficiente para marcar el reembolso como `Recuperado`. Esto es porque desde el punto de vista del reembolso, cualquier pago del cliente indica que el proceso de recuperación ha comenzado.

### 4.2 Romper Conciliación

Si necesitas revertir un pago:

1. **Ve a la factura de cliente**
2. **Clic en "Romper conciliación"**
3. **¡Automáticamente!** Los registros revierten a `Fac. Cliente Enviada`

### 4.3 Verificar Estados

- **En la solicitud**: Ve a la pestaña "Reembolsos"
- **En el menú principal**: Ve a **Operaciones / Flota / Reembolsos**
- **En el viaje**: Ve a la pestaña "Reembolsos" del buque

### 4.4 Eliminar Solicitud

Si necesitas eliminar una solicitud de reembolso:

1. **Ve a la solicitud** que quieres eliminar
2. **Elimina la solicitud** usando el botón de eliminar
3. **¡Automáticamente!** Se eliminan todos los registros de seguimiento asociados
4. **Mensaje de confirmación**: Aparecerá un mensaje indicando cuántos registros se eliminaron

> **💡 Nota**: Los registros de seguimiento se eliminan automáticamente cuando eliminas la solicitud. No necesitas eliminarlos manualmente.

---

## 5. 📊 Monitorear Reembolsos

### 5.1 Vista Principal de Reembolsos

1. Ve a **Operaciones / Flota / Reembolsos**
2. **Filtra por**:
   - Viaje específico
   - Estado del reembolso
   - Proveedor
   - Fechas

### 5.2 Métricas en Viajes

En la vista de viajes (`ek.boats.information`):

1. Ve a la pestaña **"Reembolsos"**
2. Verás:
   - **Total**: Monto total de reembolsos
   - **Pendientes**: Monto pendiente de recuperar
   - **Recuperados**: Monto ya recuperado
   - **Decoraciones**: Verde (OK), Amarillo (atención), Rojo (urgente)

### 5.3 Acciones Disponibles

- **Recalcular días**: Actualiza días pendientes
- **Ignorar reembolso**: Marca como ignorado (requiere razón)
- **Ver detalles**: Clic en cualquier registro

---

## 6. 🛠️ Solución de Problemas

### 6.1 Estados No Actualizan

**Problema**: Los estados no cambian automáticamente

**Solución**:
1. Verifica que la factura tenga asignada la `Solicitud de Operación`
2. Verifica que los productos en la factura coincidan con los de reembolso
3. Revisa los logs del servidor (busca `PAYMENT_DEBUG` o `TRACKING_DEBUG`)

### 6.2 Productos No Aparecen

**Problema**: Los productos de reembolso no se crean automáticamente

**Solución**:
1. Verifica que el tipo de solicitud tenga `Es reembolso de servicio = True`
2. Verifica que tenga productos configurados
3. Cambia la etapa de la solicitud para activar la creación

### 6.3 No Se Puede Crear o Eliminar Registros Manualmente

**Problema**: Aparece error al intentar crear o eliminar un registro manualmente

**Solución**:
- **Esto es normal**: Los registros se crean y eliminan automáticamente
- **No intentes crear** registros manualmente
- **No intentes eliminar** registros manualmente
- **Usa el flujo normal**: 
  - **Crear**: Crea solicitud → Cambia etapa → Se crean automáticamente
  - **Eliminar**: Elimina solicitud → Se eliminan automáticamente

### 6.4 Pagos No Se Registran

**Problema**: Al pagar, el estado no cambia a `Recuperado`

**Solución**:
1. Verifica que la factura esté confirmada (`posted`)
2. Verifica que el pago esté conciliado
3. Revisa los logs del servidor (busca `PAYMENT_DEBUG`)

### 6.4 Logs de Debugging

Para problemas técnicos, revisa los logs del servidor:

- **`TRACKING_DEBUG`**: Actualizaciones de estado generales
- **`PAYMENT_DEBUG`**: Procesos de pago
- **`UNPAYMENT_DEBUG`**: Procesos de desconciliación
- **`WRITE_DEBUG`**: Cambios en facturas

---

## 7. 📞 Soporte

### 7.1 Información de Contacto

- **Desarrollador**: Equipo de Desarrollo
- **Módulo**: `ek_l10n_shipping_operations`
- **Versión**: 2.1

### 7.2 Información para Soporte

Si necesitas ayuda, proporciona:

1. **ID de la solicitud** problemática
2. **ID de la factura** (si aplica)
3. **Logs del servidor** (últimas 50 líneas)
4. **Descripción detallada** del problema
5. **Pasos para reproducir** el error

---

## 8. 🎯 Mejores Prácticas

### 8.1 Flujo Recomendado

1. **Configura primero** los tipos de solicitud y productos
2. **Crea la solicitud** y cambia de etapa inmediatamente
3. **Crea órdenes de compra** - el campo "Recibido" se llena automáticamente
4. **Usa el mismo proveedor** en PO y factura de proveedor
5. **Verifica productos** antes de confirmar facturas
6. **Monitorea regularmente** el estado de reembolsos

### 8.2 Mantenimiento

- **Revisa semanalmente** los reembolsos pendientes
- **Ignora solo cuando sea necesario** (con razón clara)
- **Mantén actualizados** los montos de productos
- **Verifica logs** en caso de problemas

---

## 9. 📈 Reportes y Análisis

### 9.1 Filtros Útiles

- **Por estado**: `Recuperado`, `Pendiente`, `Cancelado`
- **Por proveedor**: Agrupa por proveedor
- **Por viaje**: Análisis por viaje específico
- **Por fechas**: Análisis temporal

### 9.2 Métricas Clave

- **Tiempo promedio** de recuperación
- **Monto total** de reembolsos por período
- **Eficiencia** de recuperación (% recuperado)
- **Proveedores** con más reembolsos

---

**¡Felicidades!** 🎉 Ahora conoces cómo usar el Sistema de Control de Reembolsos. Este sistema te ayudará a mantener un control preciso de todos los reembolsos y evitar pérdidas por error humano.

---

**Versión del Tutorial**: 1.0  
**Fecha**: Septiembre 2025  
**Compatibilidad**: Odoo 17
