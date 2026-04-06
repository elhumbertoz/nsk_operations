# -*- coding: utf-8 -*-
from odoo import _, api, fields, models
from odoo.exceptions import UserError


class ChangeJournalWizard(models.TransientModel):
    _name = 'change.journal.wizard'
    _description = 'Wizard para Cambiar Diario de Facturas'

    journal_id = fields.Many2one(
        'account.journal',
        string='Diario',
        required=True,
        domain=[('type', 'in', ['purchase', 'general'])],
        help='Seleccione el diario que se asignará a las facturas seleccionadas'
    )

    def action_change_journal(self):
        """Cambia el diario de las facturas seleccionadas usando sudo()"""
        self.ensure_one()
        
        if not self.journal_id:
            raise UserError(_('Debe seleccionar un diario.'))
        
        # Obtener las facturas desde el contexto
        active_ids = self.env.context.get('active_ids', [])
        if not active_ids:
            raise UserError(_('No se seleccionaron facturas.'))
        
        moves = self.env['account.move'].browse(active_ids)
        
        results = {
            'updated': [],
            'skipped': [],
            'errors': []
        }
        
        for move in moves:
            try:
                # Verificar que es una factura válida
                if move.state == 'cancel':
                    results['skipped'].append({
                        'id': move.id,
                        'name': move.name or f'ID {move.id}',
                        'reason': _('La factura está cancelada')
                    })
                    continue
                
                # Guardar valores anteriores
                old_journal_id = move.journal_id.id if move.journal_id else None
                old_journal_name = move.journal_id.name if move.journal_id else _('Sin diario')
                
                # Si ya tiene el diario correcto, saltar
                if old_journal_id == self.journal_id.id:
                    results['skipped'].append({
                        'id': move.id,
                        'name': move.name or f'ID {move.id}',
                        'reason': _('Ya tiene el diario %s') % self.journal_id.name
                    })
                    continue
                
                # ⚠️ CLAVE: Usar SQL directo para evitar la validación de Odoo
                # La validación "No puede editar el diario si se ha publicado" está en el método write()
                # Por eso necesitamos usar SQL directo para evitar esa restricción
                self.env.cr.execute(
                    """
                    UPDATE account_move
                    SET journal_id = %s,
                        write_uid = %s,
                        write_date = NOW()
                    WHERE id = %s
                    """,
                    (self.journal_id.id, self.env.user.id, move.id)
                )
                
                # Actualizar también el journal_id de las líneas del asiento contable
                # Aunque es un campo relacionado, al usar SQL directo debemos actualizarlo también
                self.env.cr.execute(
                    """
                    UPDATE account_move_line
                    SET journal_id = %s,
                        write_uid = %s,
                        write_date = NOW()
                    WHERE move_id = %s
                    """,
                    (self.journal_id.id, self.env.user.id, move.id)
                )
                
                # Invalidar caché y recargar el registro
                move.invalidate_recordset(['journal_id', 'l10n_ec_to_be_reimbursed'])
                # Invalidar también las líneas
                move.line_ids.invalidate_recordset(['journal_id'])
                updated_move = self.env['account.move'].browse(move.id)
                
                # Forzar recálculo del campo de reembolso si existe
                if hasattr(updated_move, '_compute_l10n_ec_to_be_reimbursed'):
                    updated_move.sudo()._compute_l10n_ec_to_be_reimbursed()
                
                results['updated'].append({
                    'id': move.id,
                    'name': move.name or f'ID {move.id}',
                    'old_journal': old_journal_name,
                    'new_journal': self.journal_id.name
                })
                
            except Exception as e:
                results['errors'].append({
                    'id': move.id,
                    'name': move.name or f'ID {move.id}',
                    'error': str(e)
                })
        
        # Construir mensaje para el usuario
        messages = []
        
        if results['updated']:
            count = len(results['updated'])
            messages.append(_('✅ Se actualizaron %d factura(s).\n\n') % count)
            messages.append(_('Detalles de cambios:\n'))
            for item in results['updated']:
                messages.append(
                    _('  • %s: %s → %s\n') % (
                        item['name'],
                        item['old_journal'],
                        item['new_journal']
                    )
                )
        
        if results['skipped']:
            count = len(results['skipped'])
            messages.append(_('\n⏭️  Se omitieron %d factura(s):\n') % count)
            for item in results['skipped']:
                messages.append(
                    _('  • %s: %s\n') % (item['name'], item['reason'])
                )
        
        if results['errors']:
            messages.append(_('\n❌ Errores encontrados (%d):\n') % len(results['errors']))
            for item in results['errors']:
                messages.append(
                    _('  • %s: %s\n') % (item['name'], item['error'])
                )
        
        # Mostrar mensaje final
        message = ''.join(messages) if messages else _('No se procesaron facturas.')
        has_errors = bool(results['errors'])
        action = {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Cambio de Diario Completado') if not has_errors else _('Cambio de Diario con Advertencias'),
                'message': message,
                'type': 'warning' if has_errors else 'info',
                'sticky': has_errors,
                'next': {
                    'type': 'ir.actions.act_window_close'
                }
            }
        }
        return action

