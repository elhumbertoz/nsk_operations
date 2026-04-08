# -*- coding: utf-8 -*-
from odoo import _, api, fields, models
from odoo.exceptions import UserError


class EkWizardRegime70Report(models.TransientModel):
    _name = 'ek.wizard.regime70.report'
    _description = 'Wizard: Reportes Régimen 70 / 60 / Pólizas'

    report_type = fields.Selection([
        ('regime_70', 'Régimen 70 - Cargas en Depósito'),
        ('regime_60', 'Régimen 60 - Salidas'),
        ('insurance', 'Pólizas de Transporte'),
    ], string='Tipo de Reporte', required=True, default='regime_70')

    ship_id = fields.Many2one(
        'ek.ship.registration',
        string='Buque / Regimen',
        domain="[('assigned_regimen_70', '=', True)]"
    )

    container_ids = fields.Many2many(
        'ek.boats.information',
        'ek_wizard_r70_report_container_rel',
        'wizard_id', 'container_id',
        string='Contenedores',
        domain="[('ship_name_id', '=', ship_id)]"
    )

    date_from = fields.Date(string='Fecha Desde')
    date_to = fields.Date(string='Fecha Hasta')

    stage_ids = fields.Many2many(
        'ek.l10n.stages.mixin',
        'ek_wizard_r70_report_stage_rel',
        'wizard_id', 'stage_id',
        string='Estados'
    )

    @api.onchange('ship_id')
    def _onchange_ship_id(self):
        if self.ship_id:
            self.container_ids = self.ship_id.ek_boats_information_ids.ids
        else:
            self.container_ids = False

    def _get_regime70_domain(self):
        domain = [('regime', '=', '70')]
        if self.container_ids:
            domain.append(('container_id', 'in', self.container_ids.ids))
        elif self.ship_id:
            domain.append(('ek_ship_registration_id', '=', self.ship_id.id))
        if self.date_from:
            domain.append(('transfer_date', '>=', self.date_from))
        if self.date_to:
            domain.append(('transfer_date', '<=', self.date_to))
        if self.stage_ids:
            domain.append(('stage_id', 'in', self.stage_ids.ids))
        domain.append(('canceled_stage', '!=', True))
        return domain

    def _get_regime60_domain(self):
        domain = [('use_in_regimen_60', '=', True), ('has_confirmed_type', '=', True)]
        if self.container_ids:
            domain.append(('container_id', 'in', self.container_ids.ids))
        elif self.ship_id:
            domain.append(('ek_ship_registration_id', '=', self.ship_id.id))
        if self.date_from:
            domain.append(('movement_date', '>=', self.date_from))
        if self.date_to:
            domain.append(('movement_date', '<=', self.date_to))
        if self.stage_ids:
            domain.append(('stage_id', 'in', self.stage_ids.ids))
        domain.append(('canceled_stage', '!=', True))
        return domain

    def _get_insurance_domain(self):
        domain = [('regime', '=', '70'), ('mail_sent_insurance', '=', True)]
        if self.container_ids:
            domain.append(('container_id', 'in', self.container_ids.ids))
        elif self.ship_id:
            domain.append(('ek_ship_registration_id', '=', self.ship_id.id))
        if self.date_from:
            domain.append(('transfer_date', '>=', self.date_from))
        if self.date_to:
            domain.append(('transfer_date', '<=', self.date_to))
        if self.stage_ids:
            domain.append(('stage_id', 'in', self.stage_ids.ids))
        return domain

    def action_generate_report(self):
        self.ensure_one()

        if self.report_type == 'regime_70':
            records = self.env['ek.operation.request'].search(self._get_regime70_domain())
            if not records:
                raise UserError(_('No se encontraron solicitudes de Régimen 70 con los filtros seleccionados.'))
            return self.env.ref(
                'ek_l10n_shipping_operations_charging_regimes.action_report_regime_70_deposit_cargo'
            ).report_action(records)

        elif self.report_type == 'regime_60':
            records = self.env['ek.operation.request'].search(self._get_regime60_domain())
            if not records:
                raise UserError(_('No se encontraron solicitudes de Régimen 60 con los filtros seleccionados.'))
            return self.env.ref(
                'ek_l10n_shipping_operations_charging_regimes.action_report_regime_60_exits'
            ).report_action(records)

        elif self.report_type == 'insurance':
            records = self.env['ek.operation.request'].search(self._get_insurance_domain())
            if not records:
                raise UserError(_('No se encontraron solicitudes con pólizas enviadas con los filtros seleccionados.'))
            return self.env.ref(
                'ek_l10n_shipping_operations_charging_regimes.action_report_regime_70_insurance_applications'
            ).report_action(records)
