# -*- coding: utf-8 -*-
#
#    Sistema FINAMSYS
#    Copyright (C) 2016-Today Ekuasoft S.A All Rights Reserved
#    Ing. Yordany Oliva Mateos <yordanyoliva@ekuasoft.com>  
#    Ing. Wendy Alvarez Chavez <wendyalvarez@ekuasoft.com>
#    EkuaSoft Software Development Group Solution
#    http://www.ekuasoft.com
#    
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.

import logging
from odoo import api, fields, models, _

_logger = logging.getLogger(__name__)


class EkStockQuant(models.Model):
    _inherit = "stock.quant"

    def _create_account_move_line_analytic(self, cr, uid, quants, move, credit_account_id, debit_account_id, journal_id, context=None):
        # group quants by cost
        quant_cost_qty = {}
        for quant in quants:
            if quant_cost_qty.get(quant.cost):
                quant_cost_qty[quant.cost] += quant.qty
            else:
                quant_cost_qty[quant.cost] = quant.qty
            logging.info(quant)

        move_obj = self.pool.get('account.move')
        for cost, qty in quant_cost_qty.items():
            move_lines = self._prepare_account_move_line_analytic(cr, uid, move, qty, cost, credit_account_id, debit_account_id, context=context)
            period_id = context.get('force_period', self.pool.get('account.period').find(cr, uid, context=context)[0])
            # Añadir referencias si es producto terminado
            ref = move.picking_id and move.picking_id.name or ""
            if hasattr(move, "production_id") and move.production_id:
                ref = move.production_id.name
            elif hasattr(move, "raw_material_production_id") and move.raw_material_production_id:
                ref = move.raw_material_production_id.name

            move_obj.create(cr, uid, {
                'journal_id': journal_id,
                'line_id': move_lines,
                'period_id': period_id,
                'date': fields.date.context_today(self, cr, uid, context=context),
                'ref': ref
            }, context=context)
