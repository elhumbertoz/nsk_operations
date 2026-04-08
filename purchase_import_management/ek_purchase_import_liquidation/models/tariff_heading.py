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

from odoo import api, fields, models
from odoo.tools.translate import _
from odoo.exceptions import UserError, ValidationError
from odoo.tools.safe_eval import safe_eval as eval


class EkTariffRuleCategory(models.Model):
    _name = "ek.tariff.rule.category"
    _description = "Categoría de regla arancelaria"

    name = fields.Char(
        string=_("Nombre"),
        required=True,
        readonly=False,
    )
    code = fields.Char(
        string=_("Código"),
        size=64,
        required=True,
        readonly=False,
    )
    parent_id = fields.Many2one(
        string=_("Padre"),
        comodel_name="ek.tariff.rule.category",
        help=_("La vinculación de una categoría de tarifa a su principal se usa solo para el propósito de informar."),
    )
    children_ids = fields.One2many(
        string=_("Hijos"),
        comodel_name="ek.tariff.rule.category",
        inverse_name="parent_id",
    )
    note = fields.Text(
        string="Descripción",
    )


class EkTariffRule(models.Model):
    _name = "ek.tariff.rule"
    _description = "Reglas de tarifas arancelarias"
    _order = "sequence"

    tariff_heading_ids = fields.Many2many(
        string=_("Partidas"),
        comodel_name="ek.tariff.heading",
        relation="ek_tariff_heading_rule_rel",
        column2="tariff_id",
        column1="rule_id",
        copy=False,
    )
    name = fields.Char(
        string=_("Nombre"),
        required=True,
        readonly=False,
    )
    code = fields.Char(
        string="Código",
        size=64,
        required=True,
        help=_(
            "El código de las reglas de tarifas se puede usar como referencia en el cálculo de otras reglas.\n"
            "Sensible a mayúsculas y minúsculas."
        ),
    )
    sequence = fields.Integer(
        string=_("Secuencia"),
        required=True,
        default=5,
        help=_("Permite organizar la secuencia de cálculo"),
    )
    quantity = fields.Char(
        string=_("Cantidad"),
        default="1.0",
        help=_("Se usa en el cálculo por porcentaje y cantidad fija."),
    )
    category_id = fields.Many2one(
        string=_("Categoría"),
        comodel_name="ek.tariff.rule.category",
        required=True,
    )
    active = fields.Boolean(
        string=_("Activo"),
        default=True,
        help=_("Si el campo activo está configurado en falso, le permitirá ocultar la regla de tarifa sin eliminarla."),
    )
    condition_select = fields.Selection(
        string=_("Condición basada en"),
        selection=[
            ("none", _("Siempre verdadero")),
            ("range", _("Intervalo")),
            ("python", _("Expresión de Python"))
        ],
        required=True,
        default="none",
    )
    condition_range = fields.Char(
        string=_("Intervalo basado en"),
        readonly=False,
        default="contract.wage",
        help=_(
            "Esto se usará para calcular los valores de % de los campos; en general es básico, pero también\n"
            "puede usar campos de códigos de categorías en minúsculas como nombres de variables (hra, ma, lta, etc.)\n"
            "y la variable básica."
        ),
    )
    condition_python = fields.Text(
        string=_("Condición python"),
        required=False,
        readonly=False,
        help=_("Aplica esta regla para el cálculo si la condición es verdadera. Puede especificar condiciones como basic > 1000."),
    )
    condition_range_min = fields.Float(
        string=_("Intervalo mínimo"),
        required=False,
        help=_("El monto mínimo, aplicado para esta regla."),
    )
    condition_range_max = fields.Float(
        string=_("Intervalo máximo"),
        required=False,
        help=_("La cantidad máxima, aplicada para esta regla."),
    )
    product_field_id = fields.Many2one(
        string=_("Campo del producto"),
        comodel_name="ir.model.fields",
        domain="[('store', '=', True), ('model_id.model', '=', 'product.product'), ('ttype', 'in', ['float','monetary'])]",
        help=_("Campo del producto a actualizar cuando se confirme la liquidación"),
    )
    amount_select = fields.Selection(
        string=_("Tipo de importe"),
        selection=[
            ("percentage", _("Porcentaje (%)")),
            ("fix", _("Importe Fijo")),
            ("code", _("Código Python"))
        ],
        required=True,
        default="fix",
        help=_("El método de cálculo para la cantidad de regla."),
    )
    amount_fix = fields.Float(
        string=_("Importe fijo"),
        digits="Account",
        default=0.00,
    )
    amount_percentage = fields.Float(
        string=_("Porcentaje (%)"),
        digits="Account",
        default=0.00,
        help=_("Por ejemplo, ingrese 50.0 para aplicar un porcentaje del 50%"),
    )
    amount_percentage_base = fields.Char(
        string=_("Porcentaje basado en"),
        required=False,
        readonly=False,
        help=_("El resultado se verá afectado por una variable"),
    )
    note = fields.Text(
        string=_("Descripción"),
    )
    param = fields.Boolean(
        string=_("Parámetro"),
        # TODO: ¿Demás qué? ¿Reglas?
        help=_("Indica que esta regla será usada para el cálculo de las demás y no se tendrá en cuenta en la suma del total"),
    )
    terms_id = fields.Many2one(
        string=_("Aplicar a"),
        comodel_name="ek.incoterms.terms",
        required=False,
    )
    not_cost_tariff = fields.Boolean(
        string=_("Excluir del costo"),
        required=False,
        help=_("Si este campo está marcado no se tendrá en cuenta para el calculo del costo de tributos"),
    )
    amount_python_compute = fields.Text(
        string=_("Código python"),
        default='''
            # Available variables:
            #----------------------
            #tariff.get_data_by_country(line.order_id.country_id)
            #tariff.get_unit_control_type_by_country(line.order_id.country_id)
            #tariff.get_unit_control_by_country(line.order_id.country_id)
            #tariff.get_tariff_amount_by_country(line.order_id.country_id)
            #tariff.get_tariff_percent_by_country(line.order_id.country_id)
            #tariff.get_tariff_by_country(line.order_id.country_id)
            # tariff: Partida arancelaria
            # employee: hr.employee object
            # contract: hr.contract object
            # rules: object containing the rules code (previously computed)
            # categories: object containing the computed salary rule categories (sum of amount of all rules belonging to that category).
            # worked_days: object containing the computed worked days.
            # inputs: object containing the computed inputs.
            
            # Note: returned value have to be set in the variable 'result'
            
            result = contract.wage * 0.10,
                    'condition_python':
            
            # Available variables:
            #----------------------
            # payslip: object containing the payslips
            # employee: hr.employee object
            # contract: hr.contract object
            # rules: object containing the rules code (previously computed)
            # categories: object containing the computed salary rule categories (sum of amount of all rules belonging to that category).
            # worked_days: object containing the computed worked days
            # inputs: object containing the computed inputs
            
            # Note: returned value have to be set in the variable 'result'
            
            result = rules.NET > categories.NET * 0.10
        '''
    )

    @api.model
    def _recursive_search_of_rules(self, cr, uid, rule_ids, context=None):
        """
        @param rule_ids: list of browse record
        @return: returns a list of tuple (id, sequence) which are all the children of the passed rule_ids
        """
        children_rules = []
        for rule in rule_ids:
            if rule.child_ids:
                children_rules += self._recursive_search_of_rules(cr, uid, rule.child_ids, context=context)
        return [(r.id, r.sequence) for r in rule_ids] + children_rules

    # TODO should add some checks on the type of result (should be Float)
    def compute_rule(self, localdict):
        """
        :param rule_id: id of rule to compute
        :param localdict: dictionary containing the environment in which to compute the rule
        :return: returns a tuple build as the base/amount computed, the quantity and the rate
        :rtype: (Float, Float, Float)
        """
        rule = self
        if rule.amount_select == 'fix':
            try:
                return rule.amount_fix, float(eval(rule.quantity, localdict)), 100.0
            except Exception:
                raise UserError(_("Cantidad incorrecta definida para la regla de tarifa %s (%s).") % (rule.name, rule.code))
        elif rule.amount_select == 'percentage':
            try:
                return (float(eval(rule.amount_percentage_base, localdict)),
                        float(eval(rule.quantity, localdict)),
                        rule.amount_percentage)
            except Exception:
                raise UserError(_("Porcentaje incorrecto de base o cantidad definida para la regla %s (%s).") % (rule.name, rule.code))
        else:
            try:
                eval(rule.amount_python_compute, localdict, mode='exec', nocopy=True)
                return float(localdict['result']), 'result_qty' in localdict and localdict['result_qty'] or 1.0, 'result_rate' in localdict and localdict['result_rate'] or 100.0
            except Exception:
                raise UserError(_("Código python incorrecto definido para la regla %s (%s).") % (rule.name, rule.code))

    def satisfy_condition(self, localdict):
        """
        @param rule_id: id of hr.salary.rule to be tested
        @param contract_id: id of hr.contract to be tested
        @return: returns True if the given rule match the condition for the given contract. Return False otherwise.
        """
        if self.condition_select == 'none':
            return True
        elif self.condition_select == 'range':
            try:
                result = eval(self.condition_range, localdict)
                return self.condition_range_min <= result <= self.condition_range_max or False
            except Exception:
                raise UserError(_("Condición de rango incorrecto definida para la regla %s (%s).")% (self.name, self.code))
        else:  # python code
            try:
                eval(self.condition_python, localdict, mode='exec', nocopy=True)
                return 'result' in localdict and localdict['result'] or False
            except Exception:
                raise UserError(_("Código python incorrecto definido para la regla %s (%s).") % (self.name, self.code))


class EkTariffHeading(models.Model):
    _name = "ek.tariff.heading"
    _description = "Partida arancelaria"

    type = fields.Selection(
        string=_("Tipo"),
        selection=[
            ("view", _("Vista")),
            ("regular", _("Regular")),
        ],
        required=True,
        default="regular",
    )
    code = fields.Char(
        string=_("Código"),
        required=True,
    )
    name = fields.Char(
        string=_("Descripción arancelaria"),
        required=True,
    )
    note = fields.Text(
        string=_("Observación"),
        required=False,
    )
    parent_id = fields.Many2one(
        string=_("Nivel superior"),
        comodel_name="ek.tariff.heading",
        ondelete="cascade",
        domain=[('type', '=', 'view')],
    )
    child_parent_ids = fields.One2many(
        string=_("Niveles inferiores"),
        comodel_name="ek.tariff.heading",
        inverse_name="parent_id",
    )
    active = fields.Boolean(
        string=_("Activo"),
        default=True,
        help=_("Si el campo activo está desmarcado, se ocultará la partida sin eliminarla."),
    )
    parent_left = fields.Integer(
        string="Parent Left",
    )
    parent_right = fields.Integer(
        string="Parent Right",
    )
    tariff_rule_ids = fields.Many2many(
        string=_("Reglas"),
        comodel_name="ek.tariff.rule",
        relation="ek_tariff_heading_rule_rel",
        column1="tariff_id",
        column2="rule_id",
    )
    tariff = fields.Float(
        string=_("Salvaguardia (%)"),
        required=False,
    )
    tariff_percent = fields.Float(
        string="Arancel (%)",
        required=False,
        digits="Importation Factor",
    )
    tariff_amount = fields.Float(
        string=_("Arancel fijo"),
        required=False,
        digits="Importation Factor",
    )
    unit_control = fields.Float(
        string=_("Unidad de control"),
        required=False,
        help=_("Unidad de control para trasa arancelaria"),
    )
    unit_control_type = fields.Selection(
        string=_("Tipo de unidad de control"),
        selection=[
            ("weight", _("Peso")),
            ("quantity", _("Cantidad")),
        ],
        required=False,
    )
    tariffs_by_origin_ids = fields.One2many(
        string=_("Aranceles por origen"),
        comodel_name="ek.tariffs.origin",
        inverse_name="tariffs_id",
        required=False,
    )

    # TODO: Confirmar este constrain por si lo he entendido mal
    # _constraints = [
    #     (_check_recursion, 'Error!\nNo puede crear partidas recursivas.', ['parent_id'])
    # ]
    @api.constrains("parent_id")
    def _check_parent_id_recursion(self):
        for rec in self:
            if not rec._check_recursion:
                raise ValidationError(_("No es posible crear partidas recursivas."))

    # _sql_constraints = [
    #     ('code_heading_uniq', 'unique(code)', 'El código de la partida debe ser único!')
    # ]
    @api.constrains("code")
    def _check_code_uniqueness(self):
        for rec in self:
            ek_tariff_heading = self.search(
                [('id', '!=', rec.id),
                ('code', '=', rec.code)]
            )
            if ek_tariff_heading:
                raise ValidationError(_("El código de la partida arancelaria debe ser único."))

    @api.model
    def name_search(self, name, args=None, operator='ilike', limit=100):
        args = args or []
        if name:
            domain = ['|', ('code', operator, name), ('name', operator, name)]
            args = domain + args
        srch_heading = self.search(args, limit=limit)
        return srch_heading and srch_heading.name_get() or []

    def _get_child_ids(self, cr, uid, ids, field_name, arg, context = None):
        result = {}
        for record in self.browse(cr, uid, ids, context=context):
            if record.child_parent_ids:
                result[record.id] = [x.id for x in record.child_parent_ids]
            else:
                result[record.id] = []
        return result

    def _check_recursion(self, cr, uid, ids, context=None):
        obj_self = self.browse(cr, uid, ids[0], context=context)
        p_id = obj_self.parent_id and obj_self.parent_id.id
        if (obj_self in obj_self.child_parent_ids) or (p_id and (p_id is obj_self.id)):
            return False
        return True

    def name_get(self):
        if not self._ids:
            return []
        reads = self.browse(self._ids)
        res = []
        for record in reads:
            name = record.name
            if record.code:
                name = record.code
            res.append((record.id, name))

        return res
        # return [(record.id, '%s - %s %s' % (record.code, record.tariff_percent, '%')) for record in self]

    def get_tariff_by_country(self, country_id):
        for rec in self:
            if not country_id:
                return rec.tariff

            match = rec.tariffs_by_origin_ids.filtered(lambda a: a.country_id == country_id)
            if match:
                return match[0].tariff
            return 0

    def get_tariff_percent_by_country(self, country_id):
        for rec in self:
            if not country_id:
                return rec.tariff_percent

            match = rec.tariffs_by_origin_ids.filtered(lambda a: a.country_id == country_id)
            if match:
                return match[0].tariff_percent
            return 0

    def get_tariff_amount_by_country(self, country_id):
        for rec in self:
            if not country_id:
                return rec.tariff_amount

            match = rec.tariffs_by_origin_ids.filtered(lambda a: a.country_id == country_id)
            if match:
                return match[0].tariff_amount
            return 0

    def get_unit_control_by_country(self, country_id):
        for rec in self:
            if not country_id:
                return rec.unit_control

            match = rec.tariffs_by_origin_ids.filtered(lambda a: a.country_id == country_id)
            if match:
                return match[0].unit_control
            return 0

    def get_unit_control_type_by_country(self, country_id):
        for rec in self:
            if not country_id:
                return rec.unit_control_type

            match = rec.tariffs_by_origin_ids.filtered(lambda a: a.country_id == country_id)
            if match:
                return match[0].unit_control_type
            return ''

    def get_data_by_country(self, country_id):
        for rec in self:
            # TODO: ¿Por qué a unit_control se le asignan dos veces datos que son distintos (un float y luego un selection)?
            data = {
                'tariff': rec.tariff,
                'tariff_percent': rec.tariff_percent,
                'tariff_amount': rec.tariff_amount,
                'unit_control': rec.unit_control,
                'unit_control': rec.unit_control_type,
            }
            if not country_id:
                return data

            match = rec.tariffs_by_origin_ids.filtered(lambda a: a.country_id == country_id)
            if match:
                _match = match[0]
                # TODO: ¿Por qué a unit_control se le asignan dos veces datos que son distintos (un float y luego un selection)?
                data.update({
                    'tariff': _match.tariff,
                    'tariff_percent': _match.tariff_percent,
                    'tariff_amount': _match.tariff_amount,
                    'unit_control': _match.unit_control,
                    'unit_control': _match.unit_control_type,
                })
            return data


class TariffsByOrigin(models.Model):
    _name = "ek.tariffs.origin"
    _description = "Aranceles por origen"

    country_id = fields.Many2one(
        string=_("País"),
        comodel_name="res.country",
        required=True,
    )
    tariff = fields.Float(
        string=_("Salvaguardia (%)"),
        required=False,
    )
    tariff_percent = fields.Float(
        string=_("Arancel (%)"),
        required=False,
        digits="Importation Factor",
    )
    tariff_amount = fields.Float(
        string=_("Arancel fijo"),
        required=False,
        digits="Importation Factor",
    )
    unit_control = fields.Float(
        string=_("Unidad de control"),
        required=False,
        help=_("Unidad de control para trasa arancelaria"),
    )
    tariffs_id = fields.Many2one(
        string=_("Partida"),
        comodel_name="ek.tariff.heading",
        required=False,
    )
    unit_control_type = fields.Selection(
        string=_("Tipo de unidad de control"),
        selection=[
            ("weight", _("Peso")),
            ("quantity", _("Cantidad")),
        ],
        required=False,
    )
