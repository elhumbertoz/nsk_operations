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


class ProcurementOrder(models.Model):
    _inherit = "procurement.group"

    liquidation_line_id = fields.Many2one(
        string=_("Línea de Importación"),
        comodel_name="ek.import.liquidation.line",
        required=False,
    )
    liquidation_id = fields.Many2one(
        string=_("Liquidación"),
        comodel_name="ek.import.liquidation",
        required=False,
    )


class StockPicking(models.Model):
    _inherit = "stock.picking"

    liquidation_id = fields.Many2one(
        string=_("Importación"),
        comodel_name="ek.import.liquidation",
        required=False,
    )
