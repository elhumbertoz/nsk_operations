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

from odoo import api, fields, models, _


class EkIncotermsTerms(models.Model):
    _name = "ek.incoterms.terms"
    _description = "Rubros de Incoterms"
    _order = "sequence"

    name = fields.Char(
        string=_("Rubro"),
        required=True,
        readonly=False,
    )
    code = fields.Char(
        string=_("Código"),
        size=64,
        required=True,
        readonly=False,
    )
    sequence = fields.Integer(
        string=_("Orden"),
        default=1,
        required=True,
        help=_("Permite organizar la secuencia de cálculo."),
    )
    note = fields.Text(
        string=_("Descripción"),
    )
    type = fields.Selection(
        string=_("Tipo"),
        default="other",
        selection=[
            ("freight", _("Flete")),
            ("insurance", _("Seguro")),
            ("expense", _("Gasto")),
            ("calculate", _("Cálculo de aduana")),
            ("other", _("Otros")),
            ("liquidation", _("Otros - Liquidación")),
            ("simulation", _("Otros - Simulación")),
        ],
        required=True,
    )
    is_considered_total = fields.Boolean(
        string=_("¿Considerado en el total?"),
        default=True,
        help=_("Indica que este rubro sera considerado en el total de la importación"),
    )
    is_provider_assumed = fields.Boolean(
        string=_("¿Valor asumido por el proveedor?"),
        help=_("Si esta casilla está marcada este solo sera usado para el calculo de los tributos"),
    )


class StockIncotermsTerms(models.Model):
    _name = "ek.stock.incoterms.terms"
    _description = "Términos de Incoterms"
    _order = "sequence"

    terms_id = fields.Many2one(
        string=_("Término"),
        comodel_name="ek.incoterms.terms",
        required=True,
    )
    code = fields.Char(
        string=_("Código"),
        size=64,
        required=False,
        readonly=False,
        related="terms_id.code",
        store=True,
    )
    type = fields.Selection(
        string=_("Tipo"),
        related="terms_id.type",
    )
    sequence = fields.Integer(
        string=_("Orden"),
        store=True,
        related="terms_id.sequence",
        help=_("Permite organizar la secuencia de cálculo."),
    )
    is_required = fields.Boolean(
        string=_("¿Requerido?"),
        default=False,
        help=_("Permite indicar si el rubro debe ser requerido."),
    )
    incoterm_id = fields.Many2one(
        string=_("Incoterm"),
        comodel_name="account.incoterms",
        required=False,
    )


class StockIncoterms(models.Model):
    _inherit = "account.incoterms"

    incoterms_terms_ids = fields.One2many(
        string=_("Rubros"),
        comodel_name="ek.stock.incoterms.terms", inverse_name="incoterm_id",  required=False)
