# 🔧 Referencia Técnica: Sistema de Control de Reembolsos

## 📋 Información General

- **Módulo Principal**: `ek_l10n_shipping_operations`
- **Módulo Secundario**: `ek_l10n_ec_purchase_reimbursement`
- **Versión**: 2.1
- **Odoo**: 17.0

---

## 🏗️ Arquitectura del Sistema

### Modelos Principales

#### `ek.reimbursement.tracking`
```python
# Modelo principal de seguimiento
class EkReimbursementTracking(models.Model):
    _name = 'ek.reimbursement.tracking'
    _description = 'Seguimiento de Reembolsos'
    
    # Campos principales
    request_id = fields.Many2one('ek.operation.request')
    product_default_name = fields.Char()
    supplier_id = fields.Many2one('res.partner')
    state = fields.Selection([...])
    amount = fields.Float()
    ignored = fields.Boolean()
```

#### `account.move` (Heredado)
```python
# Gestión de pagos y facturas
class AccountMove(models.Model):
    _inherit = 'account.move'
    
    # Métodos clave
    def _compute_payment_state(self):
        # Intercepta cambios de payment_state
    
    def _update_reimbursement_tracking_for_payment(self):
        # Actualiza a 'recovered'
    
    def _update_reimbursement_tracking_for_unpayment(self):
        # Revierte a 'client_invoice_sent'
```

#### `purchase.order` (Heredado)
```python
# Gestión de órdenes de compra
class PurchaseOrder(models.Model):
    _inherit = 'purchase.order'
    
    def _update_reimbursement_tracking(self):
        # Actualiza estados de PO
```

---

## 🔄 Flujo de Estados

### Estados Disponibles
```python
STATES = [
    ('draft', 'Borrador'),
    ('purchase_pending', 'PO Pendiente'),
    ('purchase_confirmed', 'PO Confirmada'),
    ('invoice_pending', 'Factura Pendiente'),
    ('invoice_received', 'Factura Recibida'),
    ('client_invoice_pending', 'Fac. Cliente Pendiente'),
    ('client_invoice_sent', 'Fac. Cliente Enviada'),
    ('recovered', 'Recuperado'),
    ('cancelled', 'Cancelado'),
]
```

### Transiciones Automáticas

| **Trigger** | **Estado Anterior** | **Estado Nuevo** | **Método** |
|-------------|-------------------|------------------|------------|
| Crear PO | `draft` | `purchase_pending` | `_update_reimbursement_tracking` |
| Confirmar PO | `purchase_pending` | `purchase_confirmed` | `_update_reimbursement_tracking` |
| Crear Factura Proveedor | `purchase_confirmed` | `invoice_pending` | `_update_reimbursement_tracking` |
| Confirmar Factura Proveedor | `invoice_pending` | `invoice_received` | `_update_reimbursement_tracking` |
| Crear Factura Cliente | `invoice_received` | `client_invoice_pending` | `_update_reimbursement_tracking` |
| Confirmar Factura Cliente | `client_invoice_pending` | `client_invoice_sent` | `_update_reimbursement_tracking` |
| **Pagar Factura** | `client_invoice_sent` | `recovered` | `_update_reimbursement_tracking_for_payment` |
| **Romper Conciliación** | `recovered` | `client_invoice_sent` | `_update_reimbursement_tracking_for_unpayment` |

---

## 🎯 Métodos Clave

### `_compute_payment_state()`
```python
@api.depends('amount_residual', 'move_type', 'state', 'company_id')
def _compute_payment_state(self):
    """Override para interceptar cambios de payment_state"""
    # Guardar estado anterior
    previous_payment_states = {invoice.id: invoice.payment_state for invoice in self}
    
    # Llamar método original
    super()._compute_payment_state()
    
    # Interceptar cambios
    for invoice in self:
        if (invoice.move_type == 'out_invoice' and invoice.operation_request_id):
            previous_state = previous_payment_states.get(invoice.id)
            current_state = invoice.payment_state
            
            # Caso 1: Se paga
            if current_state == 'paid' and previous_state != 'paid':
                invoice._update_reimbursement_tracking_for_payment()
            
            # Caso 2: Se rompe conciliación
            elif previous_state == 'paid' and current_state != 'paid':
                invoice._update_reimbursement_tracking_for_unpayment()
```

### `_update_reimbursement_tracking_for_payment()`
```python
def _update_reimbursement_tracking_for_payment(self):
    """Actualizar seguimiento cuando se paga factura de cliente"""
    if self.move_type == 'out_invoice' and self.operation_request_id:
        # Obtener productos de la factura
        invoice_product_names = self.invoice_line_ids.mapped('product_id.display_name')
        
        # Buscar registros de seguimiento
        tracking_records = self.env['ek.reimbursement.tracking'].search([
            ('request_id', '=', self.operation_request_id.id),
            ('product_default_name', 'in', invoice_product_names)
        ])
        
        # Actualizar estado a 'recovered'
        for tracking in tracking_records.filtered(lambda t: not t.ignored):
            tracking.sudo().write({'state': 'recovered'})
```

### `_update_reimbursement_tracking_for_unpayment()`
```python
def _update_reimbursement_tracking_for_unpayment(self):
    """Actualizar seguimiento cuando se rompe conciliación"""
    if self.move_type == 'out_invoice' and self.operation_request_id:
        # Obtener productos de la factura
        invoice_product_names = self.invoice_line_ids.mapped('product_id.display_name')
        
        # Buscar registros de seguimiento
        tracking_records = self.env['ek.reimbursement.tracking'].search([
            ('request_id', '=', self.operation_request_id.id),
            ('product_default_name', 'in', invoice_product_names)
        ])
        
        # Revertir estado a 'client_invoice_sent'
        for tracking in tracking_records.filtered(lambda t: not t.ignored):
            tracking.sudo().write({'state': 'client_invoice_sent'})
```

---

## 🐛 Debugging y Logs

### Prefijos de Logs
- **`TRACKING_DEBUG`**: Actualizaciones generales de estado
- **`PAYMENT_DEBUG`**: Procesos de pago
- **`UNPAYMENT_DEBUG`**: Procesos de desconciliación
- **`WRITE_DEBUG`**: Cambios en facturas

### Ejemplo de Logs
```
PAYMENT_DEBUG: ===== PAYMENT_STATE CAMBIADO =====
PAYMENT_DEBUG: Factura ID: 38726
PAYMENT_DEBUG: Estado anterior: not_paid
PAYMENT_DEBUG: Estado actual: paid
PAYMENT_DEBUG: amount_residual: 0.00
PAYMENT_DEBUG: Factura marcada como PAGADA - Actualizando a 'recovered'
```

### Verificar Logs
```bash
# En el servidor Odoo
tail -f /var/log/odoo/odoo.log | grep -E "(PAYMENT_DEBUG|UNPAYMENT_DEBUG|TRACKING_DEBUG)"
```

---

## 🔧 Configuración y Dependencias

### Dependencias del Módulo
```xml
<odoo>
    <data>
        <module name="base" />
        <module name="account" />
        <module name="purchase" />
        <module name="sale" />
        <module name="ek_l10n_shipping_operations" />
    </data>
</odoo>
```

### Campos Requeridos
- **Tipo de Solicitud**: `is_service_refund = True`
- **Productos**: Configurados en `ek_product_request_service_purchase_ids`
- **Factura Cliente**: Debe tener `operation_request_id` asignado

---

## 🚨 Solución de Problemas Comunes

### 1. Estados No Se Actualizan
**Causa**: Factura sin `operation_request_id` asignado
**Solución**: Asignar la solicitud en la factura

### 2. Pagos No Se Registran
**Causa**: `_compute_payment_state` no se ejecuta
**Solución**: Verificar que la factura esté confirmada y conciliada

### 3. Productos No Coinciden
**Causa**: Nombres de productos diferentes
**Solución**: Verificar `product_id.display_name` en factura vs reembolso

### 4. Herencia de Módulos
**Causa**: Conflicto entre módulos
**Solución**: Usar `hasattr()` para verificar métodos disponibles

---

## 📊 Consultas SQL Útiles

### Verificar Estados de Reembolsos
```sql
SELECT 
    rt.id,
    rt.product_default_name,
    rt.state,
    rt.request_id,
    rt.ignored,
    am.name as invoice_name,
    am.payment_state
FROM ek_reimbursement_tracking rt
LEFT JOIN account_move am ON am.id = rt.invoice_id
WHERE rt.request_id = 161
ORDER BY rt.id;
```

### Verificar Facturas de Cliente
```sql
SELECT 
    id,
    name,
    move_type,
    state,
    payment_state,
    amount_residual,
    operation_request_id
FROM account_move 
WHERE move_type = 'out_invoice' 
AND operation_request_id IS NOT NULL
ORDER BY id DESC
LIMIT 10;
```

### Verificar Conciliaciones
```sql
SELECT 
    aml.id,
    aml.move_id,
    aml.partner_id,
    aml.balance,
    aml.reconciled
FROM account_move_line aml
JOIN account_move am ON am.id = aml.move_id
WHERE am.move_type = 'out_invoice'
AND am.operation_request_id IS NOT NULL
AND aml.account_id.account_type = 'asset_receivable';
```

---

## 🔄 Herencia Segura Entre Módulos

### En `ek_l10n_ec_purchase_reimbursement`
```python
# Verificar si el método existe antes de llamarlo
if hasattr(self, 'update_reimbursement_tracking_from_products'):
    self.update_reimbursement_tracking_from_products()
```

### En `ek_l10n_shipping_operations`
```python
# Método público para otros módulos
def update_reimbursement_tracking_from_products(self):
    """Método público para actualizar seguimiento"""
    if self.operation_request_id and self.move_type == 'out_invoice':
        self._update_reimbursement_tracking()
```

---

## 📈 Métricas y Monitoreo

### KPIs Importantes
- **Tiempo promedio de recuperación**: Días desde creación hasta `recovered`
- **Tasa de recuperación**: % de reembolsos recuperados
- **Reembolsos pendientes**: Monto total pendiente
- **Eficiencia por proveedor**: Tiempo de recuperación por proveedor

### Consultas de Métricas
```sql
-- Tiempo promedio de recuperación
SELECT 
    AVG(EXTRACT(DAYS FROM (rt.write_date - rt.create_date))) as avg_days
FROM ek_reimbursement_tracking rt
WHERE rt.state = 'recovered';

-- Tasa de recuperación
SELECT 
    COUNT(CASE WHEN state = 'recovered' THEN 1 END) * 100.0 / COUNT(*) as recovery_rate
FROM ek_reimbursement_tracking;
```

---

## 🚀 Mejoras Futuras

### Funcionalidades Planificadas
- [ ] Notificaciones automáticas por email
- [ ] Dashboard de métricas en tiempo real
- [ ] Integración con sistemas de pago externos
- [ ] Reportes automáticos por período
- [ ] API REST para integraciones

### Optimizaciones Técnicas
- [ ] Cache de consultas frecuentes
- [ ] Índices de base de datos optimizados
- [ ] Procesamiento asíncrono de actualizaciones
- [ ] Logs estructurados (JSON)

---

**Versión**: 1.0  
**Fecha**: Septiembre 2025  
**Mantenido por**: Equipo de Desarrollo
