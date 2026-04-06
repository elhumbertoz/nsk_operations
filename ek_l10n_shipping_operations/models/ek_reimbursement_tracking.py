from odoo import _, api, fields, models
from odoo.exceptions import ValidationError
from datetime import date


class EkReimbursementTracking(models.Model):
    _name = 'ek.reimbursement.tracking'
    _description = 'Reimbursement Products Tracking'
    _order = 'journey_crew_id, request_id, sequence'
    _rec_name = 'product_default_name'
    _check_company_auto = True

    # Campos básicos
    sequence = fields.Integer('Secuencia', default=10)
    request_id = fields.Many2one(
        'ek.operation.request', 
        string='Solicitud de Operación', 
        required=True,
        ondelete='cascade'
    )
    journey_crew_id = fields.Many2one(
        'ek.boats.information', 
        string='Viaje', 
        required=True,
        ondelete='cascade'
    )
    product_default_name = fields.Char(
        'Descripción del Producto', 
        required=True
    )
    product_id = fields.Many2one(
        'product.template',
        string='Producto',
        help="Referencia al producto para búsqueda exacta"
    )
    supplier_id = fields.Many2one(
        'res.partner', 
        string='Proveedor',
        domain="[('is_company', '=', True)]"
    )
    amount = fields.Float('Monto', digits='Product Price')
    currency_id = fields.Many2one(
        'res.currency', 
        string='Moneda',
        default=lambda self: self.env.company.currency_id
    )
    
    # Estados del seguimiento
    state = fields.Selection([
        ('draft', 'Borrador'),
        ('purchase_pending', 'OC Borrador'),
        ('purchase_confirmed', 'OC Confirmada'),
        ('invoice_pending', 'Factura Borrador'),
        ('invoice_received', 'Factura Recibida'),
        ('client_invoice_pending', 'Fac. Cliente Borrador'),
        ('client_invoice_sent', 'Fac. Cliente Enviada'),
        ('recovered', 'Recuperado'),
        ('cancelled', 'Cancelado'),
        ('ignored', 'Ignorado')
    ], string='Estado', default='draft', required=True)
    
    # Enlaces automáticos
    purchase_order_id = fields.Many2one(
        'purchase.order', 
        string='Orden de Compra',
        readonly=True
    )
    purchase_order_state = fields.Selection(
        related='purchase_order_id.state',
        string='Estado PO',
        readonly=True
    )
    invoice_id = fields.Many2one(
        'account.move', 
        string='Factura',
        readonly=True
    )
    invoice_state = fields.Selection(
        related='invoice_id.state',
        string='Estado Factura',
        readonly=True
    )
    
    # Control manual - Campos para ignorar
    ignored = fields.Boolean(
        'Ignorar', 
        default=False,
        help="Marcar si este reembolso no se cobrará al cliente"
    )
    reason_ignored = fields.Text(
        'Razón para Ignorar',
        help="Explicar por qué no se cobrará este reembolso"
    )
    
    # Fechas y control de tiempo
    date_created = fields.Datetime(
        'Fecha de Creación', 
        default=fields.Datetime.now,
        readonly=True
    )
    date_expected_invoice = fields.Date('Fecha Esperada de Facturación')
    days_pending = fields.Integer(
        'Días Pendientes', 
        compute='_compute_days_pending', 
        store=True,
        help="Días transcurridos desde la creación"
    )
    days_range = fields.Selection([
        ('1_5', '1-5 días'),
        ('6_15', '6-15 días'),
        ('15_plus', 'Más de 15 días')
    ], string='Rango de Días', compute='_compute_days_range', store=True)
    
    # Responsables
    responsible_user_id = fields.Many2one(
        'res.users', 
        string='Responsable',
        default=lambda self: self.env.user
    )
    
    # Campos relacionados para búsquedas
    ship_id = fields.Many2one(
        'ek.ship.registration',
        related='journey_crew_id.ship_name_id',
        string='Buque',
        store=True,
        readonly=True
    )
    customer_id = fields.Many2one(
        'res.partner',
        related='request_id.res_partner_id',
        string='Cliente',
        store=True,
        readonly=True
    )
    
    # Nuevos campos para control de stages
    request_stage = fields.Many2one(
        'ek.l10n.stages.mixin',
        related='request_id.stage_id',
        string='Estado Actual de la Solicitud',
        store=True,
        readonly=True
    )
    stage_to_trigger = fields.Many2one(
        'ek.l10n.stages.mixin',
        string='Estado para Crear PO',
        help="Estado en el que se debe crear la orden de compra"
    )
    product_stage_ids = fields.Many2many(
        'ek.l10n.stages.mixin',
        'ek_l10n_stages_mixin_ek_reimbursement_tracking_rel',
        string='Estados Configurados del Producto',
        help="Etapa siguiente configurada en el producto para crear PO",
        store=True
    )

    def _update_product_stage_ids(self):
        """Actualizar la etapa siguiente del producto basado en la etapa actual de la solicitud
        
        Muestra la etapa siguiente (secuencia + 1) para indicar cuándo se van a crear
        las órdenes de compra, solo si el producto tiene configurada la etapa actual.
        """
        for record in self:
            
            if record.request_id and record.request_id.stage_id and record.product_default_name:
                # Buscar el producto por nombre (extraer el nombre sin el prefijo [RGXX])
                product_name = record.product_default_name
                if '] ' in product_name:
                    # Extraer el nombre después del prefijo [RGXX]
                    product_name = product_name.split('] ', 1)[1]
                
                # Buscar el producto por nombre
                product = self.env['product.template'].search([
                    ('name', 'ilike', product_name)
                ], limit=1)
                
                if product:
                    # Buscar las etapas configuradas para este producto en el tipo de solicitud
                    product_stages = self._get_product_stages_from_request_type(record.request_id.type_id, product)
                    
                    if product_stages:
                        # Obtener la etapa siguiente (cuando se creará la PO)
                        next_stage = self._get_next_stages_for_product_stages(product_stages, record.request_id.stage_id, record.request_id.type_id.id)
                        record.product_stage_ids = next_stage
                    else:
                        record.product_stage_ids = self.env['ek.l10n.stages.mixin']
                else:
                    record.product_stage_ids = self.env['ek.l10n.stages.mixin']
            else:
                record.product_stage_ids = self.env['ek.l10n.stages.mixin']

    @api.depends('date_created')
    def _compute_days_pending(self):
        """Calcular días transcurridos desde la creación"""
        today = date.today()
        for record in self:
            if record.date_created:
                created_date = record.date_created.date()
                record.days_pending = (today - created_date).days
            else:
                record.days_pending = 0

    @api.depends('days_pending')
    def _compute_days_range(self):
        """Calcular rango de días para agrupación"""
        for record in self:
            if record.days_pending <= 5:
                record.days_range = '1_5'
            elif record.days_pending <= 15:
                record.days_range = '6_15'
            else:
                record.days_range = '15_plus'

    @api.constrains('ignored', 'reason_ignored')
    def _check_ignored_reason(self):
        """Validar que si se marca como ignorado, se proporcione una razón"""
        for record in self:
            if record.ignored and not record.reason_ignored:
                raise ValidationError(
                    _('Debe proporcionar una razón si marca el reembolso como ignorado.')
                )

    def action_recalculate_days(self):
        """Botón para recalcular días pendientes manualmente"""
        for record in self:
            record._compute_days_pending()
            record._compute_days_range()
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Actualización Completa'),
                'message': _('Días pendientes recalculados correctamente.'),
                'type': 'success',
            }
        }

    def action_recalculate_all_days(self):
        """Acción para recalcular todos los registros (desde botón de acción)"""
        all_records = self.search([])
        all_records.action_recalculate_days()
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Actualización Masiva'),
                'message': _('Todos los días pendientes han sido recalculados.'),
                'type': 'success',
            }
        }

    def action_update_product_stages(self):
        """Botón para actualizar las etapas de productos manualmente"""
        for record in self:
            record._update_product_stage_ids()
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Actualización de Etapas'),
                'message': _('Etapas de productos actualizadas correctamente.'),
                'type': 'success',
            }
        }

    @api.model
    def update_all_product_stages(self):
        """Método para actualizar todas las etapas de productos existentes"""
        all_records = self.search([])
        all_records._update_product_stage_ids()
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Actualización Masiva de Etapas'),
                'message': _('Se actualizaron %d registros de seguimiento.') % len(all_records),
                'type': 'success',
            }
        }

    def write(self, vals):
        """Override write para validaciones de seguridad en campo ignored"""
        # Verificar permisos para campo ignored
        if 'ignored' in vals or 'reason_ignored' in vals:
            if not (self.env.user.has_group('account.group_account_manager') or 
                    self.env.user == self.responsible_user_id):
                raise ValidationError(
                    _('Solo el responsable o miembros del grupo Contabilidad/Administrador pueden modificar el estado de ignorado.')
                )
        
        return super().write(vals)

    @api.model
    def create_from_operation_request(self, operation_request):
        """Método para crear registros de seguimiento desde una solicitud de operación"""
        if not operation_request.type_id.is_service_refunf:
            return
            
        if not operation_request.product_ids:
            return
            
        tracking_vals = []
        for product_line in operation_request.product_ids:
            vals = {
                'request_id': operation_request.id,
                'journey_crew_id': operation_request.journey_crew_id.id,
                'product_default_name': product_line.name or product_line.product_id.name,
                'product_id': product_line.product_id.id if product_line.product_id else False,
                'supplier_id': product_line.supplier_id.id if product_line.supplier_id else False,
                'amount': product_line.price_unit * product_line.product_qty,
                'currency_id': operation_request.journey_crew_id.ek_ship_registration_id.company_id.currency_id.id,
                'responsible_user_id': operation_request.agent_user_id.id or self.env.user.id,
                'state': 'draft'
            }
            tracking_vals.append(vals)
        
        if tracking_vals:
            records = self.create(tracking_vals)
            # Actualizar el campo product_stage_ids después de crear los registros
            records._update_product_stage_ids()
            return records

    def _get_tracking_state_from_stage(self, stage):
        """Mapear etapa a estado de seguimiento basado en propiedades reales de la etapa"""
        if not stage:
            return 'draft'
        
        # Etapas especiales
        if stage.canceled_stage:
            return 'cancelled'
        
        if stage.fold:
            return 'recovered'  # Etapas plegadas = finalizadas
        
        # Etapas de confirmación - solo para etapas específicas que requieren confirmación de compra
        # La etapa "Confirmado" (secuencia 3) NO debe mapear a purchase_confirmed
        # Solo etapas de facturación (secuencia >= 28) con confirm_stage = True
        if stage.confirm_stage and stage.sequence >= 28:  # Solo para etapas de facturación
            return 'purchase_confirmed'
        
        # Mapeo por secuencia para etapas normales
        sequence_mapping = {
            0: 'draft',                    # Borrador
            1: 'purchase_pending',         # Solicitar pago para CAPMAN
            2: 'purchase_pending',         # Solicitar pago para MIGRACIÓN
            3: 'purchase_pending',         # Confirmado
            4: 'purchase_pending',         # Confirmado (M)
            5: 'purchase_pending',         # Confirmado (A)
            28: 'invoice_pending',         # Concluir/Liquidar
            29: 'invoice_received',        # Transmisión
            30: 'client_invoice_pending',  # Aprobada/ Utilizada
            31: 'client_invoice_sent',     # Concluida/ Inactiva
        }
        
        return sequence_mapping.get(stage.sequence, 'draft')

    @api.model
    def _normalize_product_name(self, product_name):
        """Normalizar nombre de producto para comparación (remover prefijos como [RG50])"""
        if not product_name:
            return ''
        
        # Remover prefijos como [RG50], [RG22], etc.
        import re
        normalized = re.sub(r'^\[RG\d+\]\s*', '', product_name.strip())
        return normalized

    @api.model
    def _find_tracking_by_product_id(self, request_id, supplier_id, product_ids):
        """Buscar registros de seguimiento por product_id (método más confiable)"""
        if not product_ids:
            return self.browse([])
        
        tracking_records = self.search([
            ('request_id', '=', request_id),
            ('supplier_id', '=', supplier_id),
            ('product_id', 'in', product_ids)
        ])
        
        return tracking_records

    @api.model
    def _find_tracking_by_product_name(self, request_id, supplier_id, product_names):
        """Buscar registros de seguimiento por nombres de productos normalizados (método fallback)"""
        tracking_records = self.search([
            ('request_id', '=', request_id),
            ('supplier_id', '=', supplier_id),
            ('ignored', '=', False)
        ])
        
        # Normalizar nombres de productos de entrada
        normalized_product_names = [self._normalize_product_name(name) for name in product_names]
        
        # Filtrar por coincidencia de nombres normalizados
        matching_records = []
        for tracking_record in tracking_records:
            normalized_tracking_name = self._normalize_product_name(tracking_record.product_default_name)
            
            if normalized_tracking_name in normalized_product_names:
                matching_records.append(tracking_record)
        
        final_records = self.browse([r.id for r in matching_records])
        
        return final_records

    @api.model
    def update_from_stage_change(self, operation_request):
        """Actualizar registros de seguimiento cuando cambie el stage de la solicitud"""
        if not operation_request.type_id.is_service_refunf:
            return
            
        # Buscar registros existentes para esta solicitud
        existing_records = self.search([('request_id', '=', operation_request.id)])
        
        # Obtener TODOS los productos del tipo de solicitud
        # Los registros de seguimiento se crean desde borrador para pronosticar compras
        all_products = operation_request.type_id.ek_product_request_service_purchase_ids
        
        # SIEMPRE procesar TODOS los productos para crear registros de seguimiento
        # Esto permite pronosticar compras desde el inicio
        product_lines = all_products
        
        if not product_lines:
            return
            
        # Crear nuevos registros para productos que no existen
        for product_line in product_lines:
            product_name = product_line.product_id.display_name if product_line.product_id else product_line.name
            
            existing_record = existing_records.filtered(
                lambda r: r.product_default_name == (product_line.product_id.display_name if product_line.product_id else (product_line.name or 'Sin nombre'))
            )
            
            if not existing_record:
                # Usar el nuevo método para mapear etapa a estado
                tracking_state = self._get_tracking_state_from_stage(operation_request.stage_id)
                
                # Crear nuevo registro
                vals = {
                    'request_id': operation_request.id,
                    'journey_crew_id': operation_request.journey_crew_id.id,
                    'product_default_name': product_line.product_id.display_name if product_line.product_id else (product_line.name or 'Sin nombre'),
                    'product_id': product_line.product_id.id if product_line.product_id else False,
                    'supplier_id': product_line.supplier_id.id if product_line.supplier_id else False,
                    'amount': product_line.price_unit * product_line.product_qty,
                    'currency_id': operation_request.journey_crew_id.ship_name_id.company_id.id,
                    'responsible_user_id': operation_request.agent_user_id.id or self.env.user.id,
                    'state': tracking_state,
                    'stage_to_trigger': operation_request.stage_id.id
                }
                new_record = self.with_context(allow_manual_creation=True).create(vals)
                # Actualizar el campo product_stage_ids
                new_record._update_product_stage_ids()
            else:
                # CORRECCIÓN: Solo actualizar stage_to_trigger, NO el state
                # El state debe cambiar solo por eventos específicos (creación/confirmación de POs y facturas)
                current_stage = operation_request.stage_id
                
                # Solo actualizar stage_to_trigger, mantener el estado actual
                existing_record.write({
                    'stage_to_trigger': operation_request.stage_id.id
                })
                # No actualizar product_stage_ids en cambios de etapa
                # Este campo es informativo y solo se calcula una vez al crear la solicitud

    @api.model
    def _get_product_stages_from_request_type(self, request_type, product):
        """Obtener las etapas configuradas para un producto en un tipo de solicitud"""
        # Buscar el producto en la configuración del tipo de solicitud
        product_config = self.env['ek.product.request.service.purchase'].search([
            ('ek_type_request', '=', request_type.id),
            ('product_id', '=', product.id)
        ], limit=1)
        
        if not product_config:
            return self.env['ek.l10n.stages.mixin']
        
        # Para productos de reembolso, las etapas están en ek.product.request.service.purchase
        # Buscar si tiene etapas configuradas directamente
        try:
            stages = product_config.stage_ids
            return stages
        except Exception as e:
            return self.env['ek.l10n.stages.mixin']
        
        # Si no tiene etapas directas, buscar en ek.product.request.service.stage
        stage_relations = self.env['ek.product.request.service.stage'].search([
            ('product_request_service_id', '=', product_config.id)
        ])
        
        if stage_relations:
            stages = stage_relations.mapped('ek_l10n_stages_mixin_id')
            return stages
        
        return self.env['ek.l10n.stages.mixin']

    @api.model
    def _get_next_stages_for_product_stages(self, product_stages, current_stage, request_type_id=None):
        """Obtener la etapa siguiente para un producto basado en las etapas configuradas"""
        if not product_stages or not current_stage:
            return self.env['ek.l10n.stages.mixin']
        
        # Buscar la etapa configurada con la menor secuencia (la más próxima)
        configured_stage = min(product_stages, key=lambda s: s.sequence)
        
        # Crear array con las etapas del flujo real (ignorando etapas especiales)
        flow_stages = self._get_flow_stages_array(request_type_id)
        
        if not flow_stages:
            return self.env['ek.l10n.stages.mixin']
        
        # Buscar la etapa configurada en el array del flujo
        configured_index = None
        for i, stage in enumerate(flow_stages):
            if stage.id == configured_stage.id:
                configured_index = i
                break
        
        if configured_index is None:
            return self.env['ek.l10n.stages.mixin']
        
        # Obtener la siguiente etapa en el flujo
        next_index = configured_index + 1
        if next_index < len(flow_stages):
            next_stage = flow_stages[next_index]
            return next_stage
        else:
            return self.env['ek.l10n.stages.mixin']
    
    @api.model
    def _get_flow_stages_array(self, request_type_id):
        """Obtener array con las etapas del flujo real, ignorando etapas especiales"""
        if not request_type_id:
            return []
        
        # Obtener todas las etapas del tipo de solicitud
        all_stages = self.env['ek.l10n.stages.mixin'].search([
            ('type_ids', 'in', [request_type_id])
        ], order='sequence ASC')
        
        # Filtrar etapas especiales que no forman parte del flujo normal
        flow_stages = []
        for stage in all_stages:
            # Ignorar etapas canceladas
            if stage.canceled_stage:
                continue
            
            # Ignorar etapas especiales como "Editar" (secuencia muy alta)
            if stage.sequence > 35:  # Etapas especiales suelen tener secuencia > 35
                continue
            
            # Incluir todas las etapas del flujo normal, incluyendo "Realizado"
            flow_stages.append(stage)
        
        return flow_stages

    @api.model
    def _get_next_stages_for_product(self, product_line, current_stage):
        """Obtener la etapa siguiente para un producto basado en la etapa actual
        
        Las órdenes de compra se crean al SALIR de la etapa configurada en el producto,
        por lo que mostramos la etapa SIGUIENTE (secuencia + 1) para indicar cuándo
        se van a crear las órdenes de compra.
        """
        if not product_line.stage_ids or not current_stage:
            return self.env['ek.l10n.stages.mixin']
        
        # Buscar la etapa configurada en el producto que coincida con la etapa actual
        configured_stage = product_line.stage_ids.filtered(
            lambda stage: stage.sequence == current_stage.sequence and 
                         not stage.canceled_stage and 
                         not stage.fold
        )
        
        if not configured_stage:
            # Si no hay etapa configurada para la etapa actual, no mostrar nada
            return self.env['ek.l10n.stages.mixin']
        
        # Buscar la etapa siguiente (secuencia + 1) para mostrar cuándo se creará la PO
        next_stage = self.env['ek.l10n.stages.mixin'].search([
            ('sequence', '=', current_stage.sequence + 1),
            ('canceled_stage', '=', False),
            ('fold', '=', False)
        ], limit=1)
        
        return next_stage if next_stage else self.env['ek.l10n.stages.mixin']

    @api.model
    def delete_from_operation_request(self, operation_request):
        """Eliminar registros de seguimiento cuando se elimina o cancela la solicitud"""
        if not operation_request.type_id.is_service_refunf:
            return
            
        # Buscar y eliminar todos los registros de seguimiento para esta solicitud
        tracking_records = self.search([('request_id', '=', operation_request.id)])
        if tracking_records:
            # Usar contexto que permite eliminación del sistema
            tracking_records.with_context(allow_manual_deletion=True).unlink()
            operation_request.message_post(
                body=_('Se eliminaron %d registros de seguimiento de reembolsos.') % len(tracking_records),
                message_type='notification'
            )

    @api.model
    def cancel_from_operation_request(self, operation_request):
        """Marcar registros de seguimiento como cancelados cuando se cancela la solicitud"""
        if not operation_request.type_id.is_service_refunf:
            return
            
        # Buscar y marcar como cancelados todos los registros de seguimiento para esta solicitud
        tracking_records = self.search([
            ('request_id', '=', operation_request.id),
            ('state', '!=', 'cancelled')
        ])
        if tracking_records:
            tracking_records.write({'state': 'cancelled'})
            operation_request.message_post(
                body=_('Se cancelaron %d registros de seguimiento de reembolsos.') % len(tracking_records),
                message_type='notification'
            )

    def name_get(self):
        """Personalizar el nombre mostrado"""
        result = []
        for record in self:
            name = f"[{record.journey_crew_id.name}] {record.product_default_name}"
            if record.amount:
                name += f" - {record.currency_id.symbol or ''}{record.amount:,.2f}"
            result.append((record.id, name))
        return result

    def action_view_purchase_order(self):
        """Abrir la orden de compra relacionada"""
        self.ensure_one()
        if not self.purchase_order_id:
            return {'type': 'ir.actions.act_window_close'}
        
        return {
            'name': _('Orden de Compra'),
            'type': 'ir.actions.act_window',
            'res_model': 'purchase.order',
            'view_mode': 'form',
            'res_id': self.purchase_order_id.id,
            'target': 'current',
        }

    def action_view_invoice(self):
        """Abrir la factura relacionada"""
        self.ensure_one()
        if not self.invoice_id:
            return {'type': 'ir.actions.act_window_close'}
        
        return {
            'name': _('Factura'),
            'type': 'ir.actions.act_window',
            'res_model': 'account.move',
            'view_mode': 'form',
            'res_id': self.invoice_id.id,
            'target': 'current',
        }

    def action_ignore(self):
        """Abrir wizard para ignorar producto"""
        return {
            'type': 'ir.actions.act_window',
            'name': 'Ignorar Producto de Reembolso',
            'res_model': 'ignore.reimbursement.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'active_id': self.id}
        }

    def action_unignore(self):
        """Desmarcar producto como ignorado y restaurar estado apropiado"""
        # Determinar el estado correcto basado en las condiciones actuales
        correct_state = self._determine_correct_state()
        
        self.write({
            'state': correct_state,
            'ignored': False,
            'reason_ignored': False
        })
        return True

    def _determine_correct_state(self):
        """Determinar el estado correcto basado en las condiciones actuales (del final hacia el inicio)"""
        self.ensure_one()
        
        # 1. PRIMERO: Verificar si tiene factura de cliente y está pagada (estado final)
        if self.request_id:
            client_invoices = self.env['account.move'].search([
                ('operation_request_id', '=', self.request_id.id),
                ('move_type', '=', 'out_invoice'),
                ('invoice_line_ids.product_id', '=', self.product_id.id)
            ])
            
            if client_invoices:
                for invoice in client_invoices:
                    if invoice.payment_state == 'paid':
                        return 'recovered'  # Estado final - no necesita más verificación
                    elif invoice.state == 'posted':
                        return 'client_invoice_sent'
                    elif invoice.state == 'draft':
                        return 'client_invoice_pending'
        
        # 2. SEGUNDO: Verificar si tiene factura de proveedor
        if self.invoice_id:
            invoice_state = self.invoice_id.state
            if invoice_state == 'posted':
                return 'invoice_received'
            elif invoice_state == 'draft':
                return 'invoice_pending'
        
        # 3. TERCERO: Verificar si tiene orden de compra
        if self.purchase_order_id:
            po_state = self.purchase_order_id.state
            if po_state in ['purchase', 'done']:
                return 'purchase_confirmed'
            elif po_state == 'draft':
                return 'purchase_pending'
        
        # 4. CUARTO: Estado basado en la etapa de la solicitud
        if self.request_id and self.request_id.stage_id:
            return self._get_tracking_state_from_stage(self.request_id.stage_id)
        
        # 5. QUINTO: Estado por defecto
        return 'draft'

    def _determine_correct_state_with_reversal(self, removed_document_type=None, removed_document_id=None):
        """
        Determinar el estado correcto considerando la reversión de documentos eliminados
        
        Args:
            removed_document_type: Tipo de documento eliminado ('purchase_order', 'invoice', 'client_invoice')
            removed_document_id: ID del documento eliminado
        """
        import logging
        _logger = logging.getLogger(__name__)
        _logger.info(f'REVERSAL_DEBUG: Determining correct state for tracking {self.id} after removing {removed_document_type} {removed_document_id}')
        
        # 1. PRIMERO: Verificar si tiene factura de cliente y está pagada (excluir si se eliminó)
        if self.request_id:
            client_invoices = self.env['account.move'].search([
                ('operation_request_id', '=', self.request_id.id),
                ('move_type', '=', 'out_invoice'),
                ('invoice_line_ids.product_id', '=', self.product_id.id)
            ])
            
            if client_invoices:
                for invoice in client_invoices:
                    # Excluir la factura eliminada
                    if removed_document_type == 'client_invoice' and invoice.id == removed_document_id:
                        continue
                        
                    if invoice.payment_state == 'paid':
                        _logger.info(f'REVERSAL_DEBUG: Found paid client invoice {invoice.id}, returning recovered')
                        return 'recovered'  # Estado final - no necesita más verificación
                    elif invoice.state == 'posted':
                        _logger.info(f'REVERSAL_DEBUG: Found posted client invoice {invoice.id}, returning client_invoice_sent')
                        return 'client_invoice_sent'
                    elif invoice.state == 'draft':
                        _logger.info(f'REVERSAL_DEBUG: Found draft client invoice {invoice.id}, returning client_invoice_pending')
                        return 'client_invoice_pending'
        
        # 2. SEGUNDO: Verificar si tiene factura de proveedor (excluir si se eliminó)
        if self.invoice_id and not (removed_document_type == 'invoice' and self.invoice_id.id == removed_document_id):
            invoice_state = self.invoice_id.state
            if invoice_state == 'posted':
                _logger.info(f'REVERSAL_DEBUG: Found posted vendor invoice {self.invoice_id.id}, returning invoice_received')
                return 'invoice_received'
            elif invoice_state == 'draft':
                _logger.info(f'REVERSAL_DEBUG: Found draft vendor invoice {self.invoice_id.id}, returning invoice_pending')
                return 'invoice_pending'
        
        # 3. TERCERO: Verificar si tiene orden de compra (excluir si se eliminó)
        if self.purchase_order_id and not (removed_document_type == 'purchase_order' and self.purchase_order_id.id == removed_document_id):
            po_state = self.purchase_order_id.state
            if po_state in ['purchase', 'done']:
                _logger.info(f'REVERSAL_DEBUG: Found confirmed purchase order {self.purchase_order_id.id}, returning purchase_confirmed')
                return 'purchase_confirmed'
            elif po_state == 'draft':
                _logger.info(f'REVERSAL_DEBUG: Found draft purchase order {self.purchase_order_id.id}, returning purchase_pending')
                return 'purchase_pending'
        
        # 4. CUARTO: Estado basado en la etapa de la solicitud
        if self.request_id and self.request_id.stage_id:
            default_state = self._get_tracking_state_from_stage(self.request_id.stage_id)
            _logger.info(f'REVERSAL_DEBUG: No documents found, returning default state from stage: {default_state}')
            return default_state
        
        # 5. QUINTO: Estado por defecto
        _logger.info(f'REVERSAL_DEBUG: No conditions met, returning draft')
        return 'draft'

    @api.constrains('state', 'reason_ignored')
    def _check_ignored_reason(self):
        """Validar que el estado ignorado tenga razón obligatoria"""
        for record in self:
            if record.state == 'ignored' and not record.reason_ignored:
                raise ValidationError(_('Debe proporcionar una razón cuando el estado es "Ignorado".'))

    @api.model
    def create(self, vals):
        """Restringir creación manual - solo permitir creación automática"""
        # Verificar si viene de un contexto que permite creación (sistema interno)
        if not self.env.context.get('allow_manual_creation', False):
            # Solo permitir creación si viene de una solicitud de operación
            if not vals.get('request_id'):
                raise ValidationError(_(
                    'Los registros de seguimiento de reembolsos se crean automáticamente. '
                    'No se pueden crear manualmente.'
                ))
            # Verificar que la solicitud existe y es de tipo reembolso
            if vals.get('request_id'):
                request = self.env['ek.operation.request'].browse(vals['request_id'])
                if not request.exists() or not request.type_id.is_service_refunf:
                    raise ValidationError(_(
                        'Los registros de seguimiento de reembolsos solo se pueden crear '
                        'para solicitudes de tipo reembolso.'
                    ))
        return super().create(vals)

    def unlink(self):
        """Restringir eliminación manual - solo permitir eliminación del sistema"""
        # Verificar si viene de un contexto que permite eliminación (sistema interno)
        if not self.env.context.get('allow_manual_deletion', False):
            raise ValidationError(_(
                'Los registros de seguimiento de reembolsos no se pueden eliminar manualmente. '
                'Se eliminan automáticamente cuando se elimina la solicitud de operación.'
            ))
        return super().unlink()

    def action_create_customer_reimbursement_invoice(self):
        """Crear factura de reembolso de cliente desde las líneas de seguimiento seleccionadas"""
        if not self:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Error'),
                    'message': _('No hay líneas seleccionadas.'),
                    'type': 'danger',
                },
            }

        # Validar que todas las líneas estén en estado invoice_received
        invalid_lines = self.filtered(lambda r: r.state != 'invoice_received')
        if invalid_lines:
            raise ValidationError(_(
                'Solo se pueden seleccionar líneas en estado "Factura Recibida". '
                'Líneas inválidas: %s'
            ) % ', '.join(invalid_lines.mapped('product_default_name')))

        # Verificar que las líneas tengan facturas de proveedor asociadas
        # Buscar facturas que contengan estas líneas de seguimiento
        supplier_invoices = self.env['account.move'].search([
            ('invoice_line_ids.reimbursement_tracking_id', 'in', self.ids),
            ('move_type', '=', 'in_invoice'),
            ('state', '=', 'posted')
        ])
        
        if not supplier_invoices:
            raise ValidationError(_('No se encontraron facturas de proveedor asociadas a las líneas seleccionadas.'))

        # Verificar que todas las líneas seleccionadas tengan facturas asociadas
        lines_with_invoices = self.env['account.move.line'].search([
            ('reimbursement_tracking_id', 'in', self.ids),
            ('move_id', 'in', supplier_invoices.ids)
        ])
        lines_without_invoice = self - lines_with_invoices.mapped('reimbursement_tracking_id')
        
        if lines_without_invoice:
            raise ValidationError(_(
                'Algunas líneas no tienen factura de proveedor asociada: %s'
            ) % ', '.join(lines_without_invoice.mapped('product_default_name')))

        # Verificar que todas las líneas pertenezcan al mismo viaje
        journey_crews = self.mapped('journey_crew_id')
        if len(journey_crews) > 1:
            raise ValidationError(_(
                'Todas las líneas seleccionadas deben pertenecer al mismo viaje. '
                'Viajes encontrados: %s'
            ) % ', '.join(journey_crews.mapped('name')))

        # Obtener información común de las líneas
        first_line = self[0]
        customer = first_line.customer_id
        journey_crew = first_line.journey_crew_id
        ship = first_line.ship_id

        if not customer:
            raise ValidationError(_('No se pudo determinar el cliente para la factura.'))

        # Obtener información del puerto y fechas del viaje
        port_name = journey_crew.ek_res_world_seaports_d_id.name if journey_crew and journey_crew.ek_res_world_seaports_d_id else "N/A"
        ata_date = journey_crew.ata.strftime('%d/%m/%Y') if journey_crew and journey_crew.ata else "N/A"
        etd_date = journey_crew.etd.strftime('%d/%m/%Y') if journey_crew and journey_crew.etd else "N/A"
        atd_date = journey_crew.atd.strftime('%d/%m/%Y') if journey_crew and journey_crew.atd else "N/A"
        
        # Crear referencia y payment_reference con el formato requerido
        ref_text = f"REEMBOLSO DE GASTOS - AGENCIAMIENTO.- DURANTE ESTADÍA EN EL PUERTO DE {port_name} - ATA: [{ata_date}] - ETD: [{etd_date}] - ATD: [{atd_date}]"
        
        # Obtener valores por defecto de la configuración de la empresa
        company = self.env.company
        default_vals = {}
        
        if company.reimbursement_journal_id:
            default_vals['journal_id'] = company.reimbursement_journal_id.id
        if company.reimbursement_document_type_id:
            default_vals['l10n_latam_document_type_id'] = company.reimbursement_document_type_id.id
        if company.reimbursement_document_sustento:
            default_vals['l10n_latam_document_sustento'] = company.reimbursement_document_sustento.id
        if company.reimbursement_payment_method_id:
            default_vals['l10n_ec_sri_payment_id'] = company.reimbursement_payment_method_id.id

        # Crear factura de reembolso de cliente
        invoice_vals = {
            'move_type': 'out_invoice',
            'partner_id': customer.id,
            'journey_crew_id': journey_crew.id if journey_crew else False,
            'ship_name_id': ship.id if ship else False,
            'invoice_date': fields.Date.today(),
            'invoice_date_due': fields.Date.today(),
            'ref': ref_text,
            'payment_reference': ref_text,
            'narration': f'Factura de reembolso generada desde líneas de seguimiento. '
                        f'Viaje: {journey_crew.name if journey_crew else "N/A"}, '
                        f'Buque: {ship.name if ship else "N/A"}, '
                        f'Líneas seleccionadas: {len(self)}',
            'currency_id': first_line.currency_id.id,
            'company_id': company.id,
        }
        
        # Agregar valores por defecto configurados
        invoice_vals.update(default_vals)

        # Crear la factura
        reimbursement_invoice = self.env['account.move'].create(invoice_vals)

        # Usar el wizard existente para importar las facturas de proveedor
        wizard_vals = {
            'partner_id': customer.id,
            'invoice_id': reimbursement_invoice.id,
            'move_ids': [(6, 0, supplier_invoices.ids)],
        }

        wizard = self.env['ek.account.move.reimbursement.wizard'].create(wizard_vals)
        
        # Ejecutar la importación
        result = wizard.action_import_from_move()

        # Actualizar el estado de las líneas de seguimiento
        self.write({'state': 'client_invoice_pending'})

        # Abrir la factura creada
        return {
            'type': 'ir.actions.act_window',
            'name': _('Factura de Reembolso Creada'),
            'res_model': 'account.move',
            'res_id': reimbursement_invoice.id,
            'view_mode': 'form',
            'target': 'current',
            'context': {
                'default_move_type': 'out_invoice',
                'create': False,
            },
        }
