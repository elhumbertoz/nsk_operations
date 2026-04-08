# -*- coding: utf-8 -*-
import io
import base64
from datetime import datetime, date
from odoo import _, fields, models, api
from odoo.exceptions import UserError


class ek_wizard_filter_regimen(models.TransientModel):
    _name = "ek.wizard.filter.regimen"
    _description = "Wizard: Filter Regimen"

    ek_regimen_table_id = fields.Many2one(
        "ek.ship.registration",
        string="Regimen",
        domain="[('assigned_regimen_70', '=', True)]"
    )
    ek_container_ids = fields.Many2many(
        "ek.boats.information",
        "ek_boats_information_id",
        "ek_wizard_filter_regimen",
        string="Container",
        domain="[('ship_name_id', '=', ek_regimen_table_id)]"
    )
    ek_id_bls = fields.Many2many(
        "id.bl.70",
        "ek_id_bl_70",
        "ek_wizard_filter_regimen",
        string="ID BL",
        domain="[('journey_crew_id', 'in', ek_container_ids)]"
    )
    date_from = fields.Date(string="Fecha Desde")
    date_to = fields.Date(string="Fecha Hasta")
    stage_ids = fields.Many2many(
        'ek.l10n.stages.mixin',
        'ek_wizard_filter_regimen_stage_rel',
        'wizard_id', 'stage_id',
        string="Estados"
    )

    @api.onchange('ek_regimen_table_id')
    def _onchange_ek_regimen_table_id(self):
        # Solo limpia las selecciones dependientes, NO auto-puebla
        self.ek_container_ids = False
        self.ek_id_bls = False

    @api.onchange('ek_container_ids')
    def _onchange_ek_container_id(self):
        # Solo limpia los BLs dependientes, NO auto-puebla
        self.ek_id_bls = False

    def _get_effective_containers(self):
        """Vacío = todos los contenedores del régimen seleccionado."""
        if self.ek_container_ids:
            return self.ek_container_ids
        if self.ek_regimen_table_id:
            return self.ek_regimen_table_id.ek_boats_information_ids
        return self.env['ek.boats.information'].browse()

    def generate_data_kardex(self):
        if not self.ek_regimen_table_id:
            raise UserError(_("Debe seleccionar un régimen."))

        containers = self._get_effective_containers()
        data = []

        # ── Régimen 70: entradas ─────────────────────────────────────────────
        for container in containers:
            items = container.ek_produc_packages_goods_ids
            if self.ek_id_bls:
                bl_ids = self.ek_id_bls.ids
                items = items.filtered(lambda x: x.id_bl.id in bl_ids)
            if self.date_from:
                date_from = self.date_from
                items = items.filtered(
                    lambda x: x.date_request and x.date_request.date() >= date_from
                )
            if self.date_to:
                date_to = self.date_to
                items = items.filtered(
                    lambda x: x.date_request and x.date_request.date() <= date_to
                )
            for item in items:
                data.append({
                    'date_request': item.date_request,
                    'movement_date': item.create_date,
                    'regimen': "70",
                    'ship_registration_id': item.ek_ship_registration_id.id,
                    'boats_information_id': item.ek_boats_information_id.id,
                    'related_document': item.id_bl.id,
                    'tariff_item': (item.tariff_item or "") + (item.id_hs_copmt_cd or "") + (item.id_hs_spmt_cd or ""),
                    'product_description': item.ek_requerid_burden_inter_nac_id.id,
                    'max_regime_date': item.max_regime_date,
                    'unds_in': abs(item.quantity or 0),
                    'unds_out': 0.0,
                    'unit_cost': item.fob,
                    'customs_document': item.number_dai,
                })

        # ── Régimen 60: salidas ──────────────────────────────────────────────
        container_ids = containers.ids
        if container_ids:
            domain = [
                ('ek_operation_request_id.container_id', 'in', container_ids),
                ('ek_operation_request_id.has_confirmed_type', '=', True),
                ('ek_operation_request_id.use_in_regimen_60', '=', True),
                ('ek_operation_request_id.canceled_stage', '!=', True),
            ]
            if self.ek_id_bls:
                domain.append(('ek_operation_request_id.id_bl_70', 'in', self.ek_id_bls.ids))
            if self.date_from:
                domain.append(('ek_operation_request_id.movement_date', '>=', self.date_from))
            if self.date_to:
                domain.append(('ek_operation_request_id.movement_date', '<=', self.date_to))
            if self.stage_ids:
                domain.append(('ek_operation_request_id.stage_id', 'in', self.stage_ids.ids))

            for item in self.env["table.regimen.60"].search(domain):
                req = item.ek_operation_request_id
                data.append({
                    'date_request': req.create_date,
                    'movement_date': req.movement_date,
                    'regimen': "60",
                    'ship_registration_id': req.ek_ship_registration_id.id,
                    'boats_information_id': req.journey_crew_id.id,
                    'related_document': req.id_bl_70.id,
                    'tariff_item': (item.tariff_item or "") + (item.id_hs_copmt_cd or "") + (item.id_hs_spmt_cd or ""),
                    'product_description': item.ek_requerid_burden_inter_nac_id.id,
                    'max_regime_date': req.max_regime_date,
                    'unds_in': 0.0,
                    'unds_out': abs(item.quantity or 0),
                    'unit_cost': item.fob,
                    'customs_document': req.number_dae,
                })

        return self._process_kardex_balance(data)

    def _process_kardex_balance(self, raw_data):
        """Agrupa por contenedor, ordena cronológicamente y calcula el
        saldo corrido por (subpartida, descripción) dentro de cada contenedor.

        El resultado queda ordenado: primero todos los movimientos del
        contenedor A, luego del B, etc. — dentro de cada uno, por fecha.
        """
        def _to_dt(val):
            if val is None:
                return datetime.min
            if isinstance(val, datetime):
                return val
            if isinstance(val, date):
                return datetime.combine(val, datetime.min.time())
            return datetime.min

        # Agrupar por contenedor
        by_container = {}
        for mv in raw_data:
            cid = mv.get('boats_information_id') or 0
            by_container.setdefault(cid, []).append(mv)

        # Orden estable de contenedores (por nombre)
        container_order = sorted(
            by_container.keys(),
            key=lambda cid: (
                self.env['ek.boats.information'].browse(cid).name or ''
                if cid else ''
            )
        )

        result = []
        for cid in container_order:
            movements = by_container[cid]
            # Ordenar cronológicamente por fecha de movimiento (tiebreak: date_request)
            movements.sort(key=lambda m: (
                _to_dt(m.get('movement_date')),
                _to_dt(m.get('date_request')),
                0 if m.get('regimen') == '70' else 1,  # entradas antes que salidas en misma fecha
            ))

            # Saldo por clave (subpartida + descripción)
            balances = {}
            for mv in movements:
                key = (mv.get('tariff_item') or '', mv.get('product_description') or 0)
                prev = balances.get(key, 0.0)
                new_bal = prev + (mv.get('unds_in') or 0) - (mv.get('unds_out') or 0)
                balances[key] = new_bal
                mv['balance'] = new_bal
                result.append(mv)

        return result

    def _create_charging_records(self):
        data = self.generate_data_kardex()
        if not data:
            raise UserError(_("No se encontraron datos con los filtros seleccionados."))
        self.env["ek.wizard.charging.data"].search([]).unlink()
        return self.env["ek.wizard.charging.data"].with_context(
            tracking_disable=True, validation_skip=True
        ).create(data)

    def create_wizard_charging(self):
        """Abre la tabla interactiva para revisión."""
        self._create_charging_records()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Kardex Régimen 70 / 60',
            'res_model': 'ek.wizard.charging.data',
            'view_mode': 'tree',
            'view_id': self.env.ref(
                "ek_l10n_shipping_operations_charging_regimes.ek_wizard_charging_data_form"
            ).id,
            'target': 'new',
            'context': {'create': False, 'edit': False, 'delete': False},
        }

    def create_wizard_charging_pdf(self):
        """Genera el PDF del kardex directamente."""
        records = self._create_charging_records()
        return self.env.ref(
            'ek_l10n_shipping_operations_charging_regimes.action_report_kardex_70_60'
        ).report_action(records)

    def create_wizard_charging_xlsx(self):
        """Genera y descarga un archivo Excel del kardex."""
        from openpyxl import Workbook
        from openpyxl.styles import Font, Alignment, PatternFill, Border, Side

        data = self.generate_data_kardex()
        if not data:
            raise UserError(_("No se encontraron datos con los filtros seleccionados."))

        wb = Workbook()
        ws = wb.active
        ws.title = "Kardex 70-60"

        # ── Estilos ──────────────────────────────────────────────────────────
        thin = Side(style='thin')
        border = Border(left=thin, right=thin, top=thin, bottom=thin)
        hdr_font = Font(bold=True, color="FFFFFF", size=9)
        hdr_fill = PatternFill("solid", fgColor="1F4E79")
        hdr_align = Alignment(horizontal="center", vertical="center", wrap_text=True)
        center = Alignment(horizontal="center", vertical="center")
        left = Alignment(horizontal="left", vertical="center")
        r70_fill = PatternFill("solid", fgColor="DEEAF1")
        r60_fill = PatternFill("solid", fgColor="FCE4D6")

        # ── Cabecera ─────────────────────────────────────────────────────────
        headers = [
            ("Fecha Mov.", 13),
            ("Rég.", 6),
            ("BL", 16),
            ("Subpartida", 16),
            ("Descripción", 30),
            ("F. Max Rég.", 13),
            ("Entrada", 11),
            ("Salida", 11),
            ("Saldo", 11),
            ("FOB Unit.", 11),
            ("Total FOB", 12),
            ("Doc. Aduanas", 16),
        ]
        for col, (header, width) in enumerate(headers, 1):
            cell = ws.cell(row=1, column=col, value=header)
            cell.font = hdr_font
            cell.fill = hdr_fill
            cell.alignment = hdr_align
            cell.border = border
            ws.column_dimensions[cell.column_letter].width = width
        ws.row_dimensions[1].height = 28

        # ── Datos con separadores por contenedor ─────────────────────────────
        def fmt_date(val):
            if not val:
                return ''
            try:
                return val.strftime('%d/%m/%Y')
            except Exception:
                return str(val)[:10]

        grp_font = Font(bold=True, color="FFFFFF", size=10)
        grp_fill = PatternFill("solid", fgColor="404040")
        ncols = len(headers)

        current_row = 2
        current_container = None
        grand_in = grand_out = grand_total = 0.0

        for row in data:
            cid = row.get('boats_information_id') or 0

            # Nuevo grupo de contenedor → fila separadora
            if cid != current_container:
                container = self.env['ek.boats.information'].browse(cid)
                ship = self.env['ek.ship.registration'].browse(row.get('ship_registration_id') or 0)
                label = f"CONTENEDOR: {container.name or 'Sin contenedor'}"
                if ship.id:
                    label += f"   |   BUQUE: {ship.name or ''}"
                ws.merge_cells(start_row=current_row, start_column=1,
                               end_row=current_row, end_column=ncols)
                gcell = ws.cell(row=current_row, column=1, value=label)
                gcell.font = grp_font
                gcell.fill = grp_fill
                gcell.alignment = left
                ws.row_dimensions[current_row].height = 20
                current_row += 1
                current_container = cid

            fill = r60_fill if row.get('regimen') == '60' else r70_fill
            doc = self.env['id.bl.70'].browse(row.get('related_document') or 0)
            desc = self.env['ek.requerid.burden.inter.nac'].browse(row.get('product_description') or 0)

            unds_in = row.get('unds_in') or 0
            unds_out = row.get('unds_out') or 0
            unit = row.get('unit_cost') or 0
            total = (unds_in - unds_out) * unit

            grand_in += unds_in
            grand_out += unds_out
            grand_total += total

            values = [
                fmt_date(row.get('movement_date')),
                row.get('regimen', ''),
                doc.name if doc.id else '',
                row.get('tariff_item', ''),
                desc.name if desc.id else '',
                fmt_date(row.get('max_regime_date')),
                unds_in or '',
                unds_out or '',
                row.get('balance') or 0,
                unit,
                total,
                row.get('customs_document', ''),
            ]
            for col, val in enumerate(values, 1):
                cell = ws.cell(row=current_row, column=col, value=val)
                cell.fill = fill
                cell.border = border
                cell.alignment = center if col not in (3, 4, 5) else left
            current_row += 1

        # Totales generales
        totals_row = current_row + 1
        ws.cell(row=totals_row, column=1, value="TOTALES GENERALES").font = Font(bold=True)
        tot_cells = {
            7: grand_in,
            8: grand_out,
            11: grand_total,
        }
        for col, val in tot_cells.items():
            c = ws.cell(row=totals_row, column=col, value=val)
            c.font = Font(bold=True)
            c.fill = PatternFill("solid", fgColor="FFE699")
            c.border = border
            c.alignment = center

        # ── Guardar y descargar ──────────────────────────────────────────────
        buf = io.BytesIO()
        wb.save(buf)
        xlsx_b64 = base64.b64encode(buf.getvalue()).decode()

        ship_name = self.ek_regimen_table_id.name or 'kardex'
        attachment = self.env['ir.attachment'].create({
            'name': f"Kardex_70_60_{ship_name}.xlsx",
            'type': 'binary',
            'datas': xlsx_b64,
            'mimetype': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            'res_model': self._name,
            'res_id': self.id,
        })
        return {
            'type': 'ir.actions.act_url',
            'url': f'/web/content/{attachment.id}?download=true',
            'target': 'new',
        }
