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

from odoo import fields, models
from odoo.tools.translate import _


class StockMove(models.Model):
    _inherit = "stock.move"

    liquidation_line_id = fields.Many2one(
        string=_("Linea de importación"),
        comodel_name="ek.import.liquidation.line",
        required=False,
    )

    def _get_price_unit(self):
        """Returns the unit price for the move"""
        self.ensure_one()
        if self.liquidation_line_id and self.product_id.id == self.liquidation_line_id.product_id.id:
            line = self.liquidation_line_id
            order = line.order_id.purchase_id
            price_unit = line.unit_cost

            if line.product_uom.id != line.product_id.uom_id.id:
                price_unit *= line.product_uom.factor / line.product_id.uom_id.factor
            if order.currency_id != order.company_id.currency_id:
                price_unit = order.currency_id._convert(
                    price_unit, order.company_id.currency_id, order.company_id, fields.Date.context_today(self),
                    round=False)
            return price_unit
        return super(StockMove, self)._get_price_unit()

    def _get_src_account(self, accounts_data):
        if self._is_import_liquidation():
            return self.location_id.valuation_out_account_id.id or accounts_data['import'].id or accounts_data['stock_input'].id
        return super()._get_src_account(accounts_data)


    def _is_import_liquidation(self):
        self.ensure_one()
        return self.liquidation_line_id

