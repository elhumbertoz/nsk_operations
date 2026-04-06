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
#

from odoo import fields, models, api,_
from odoo.exceptions import ValidationError,UserError


class EkResCountryCity(models.Model):
    _name = "ek.res.country.city"
    #_inherits = {'res.city': 'city_id'}
    _order = "name ASC"
    _description = "Country City"

    name = fields.Char(
       string="Nombre",
       size=64,
       required=True,
    )

    # city_id = fields.Many2one(
    #     string="Ciudad",
    #     comodel_name="res.city",
    #     #index='btree_not_null',
    #     #readonly=True, 
    #     ondelete='cascade',
    # )
        
    code = fields.Char(
        string="Código",
        size=6,
        required=True,
    )
    country_id = fields.Many2one(
       string="País",
       comodel_name="res.country",
       required=False,
    )
    state_id = fields.Many2one(
       string="Estado/Provincia",
       comodel_name="res.country.state",
       domain="[('country_id', '=', country_id)]",
       required=False,
    )


class EkResRoute(models.Model):
    _name = "ek.res.route"
    _description = "Rutas"
    _order = "name ASC"

    code = fields.Char(
        string="Código",
        size=6,
        required=True,
    )
    name = fields.Char(
        string="Nombre",
        size=64,
        required=True,
    )

    # TODO: Se agrega campo name a ser evaluado en el constrain
    @api.constrains("name", "code")
    def _check_route_uniqueness(self):
        for rec in self:
            res_route= self.search([
                ('id', '!=', rec.id),
                ('name', '=', rec.name),
                ('code', '=', rec.code),
            ], limit=1)
            if res_route:
                raise ValidationError("Las rutas deben ser únicas.")


class EkResStateZone(models.Model):
    _name = "ek.res.state.zone"
    _description = "Zonas"
    _order = "name ASC"

    name = fields.Char(
        string="Nombre",
        size=64,
        required=True,
    )
    code = fields.Char(
        string="Código",
        size=6,
        required=True,
    )
    city_id = fields.Many2one(
        string="Ciudad",
        comodel_name="ek.res.country.city",
        domain="['|', ('state_id', '=', False), ('state_id', '=', state_id)]",
        required=False,
    )
    state_id = fields.Many2one(
        string="Estado/Provincia",
        comodel_name="res.country.state",
        domain="[('country_id', '=', country_id)]",
        required=False,
    )
    country_id = fields.Many2one(
        string="País",
        comodel_name="res.country",
        required=False,
    )
    channel_id = fields.Many2one(
        string="Canal",
        comodel_name="ek.res.channel",
        required=False,
    )
    route_dst_id = fields.Many2one(
        string="Ruta",
        comodel_name="ek.res.route",
        required=False,
    )

    @api.constrains("name", "code", "state_id")
    def _check_state_zone_uniqueness(self):
        for rec in self:
            state_zone= self.search([
                ('id', '!=', rec.id),
                ('name', '=', rec.name),
                ('code', '=', rec.code),
                ('state_id', '=', rec.state_id.id),
            ], limit=1)
            if state_zone:
                raise ValidationError("Las zonas deben ser únicas.")


class EkResRegion(models.Model):
    _name = "ek.res.region"
    _description = "Regiones"
    _order = "name ASC"

    name = fields.Char(
        string="Nombre",
        size=64,
        required=True,
    )
    code = fields.Char(
        string="Código",
        size=6,
        required=True,
    )
    country_id = fields.Many2one(
        string="País",
        comodel_name="res.country",
        required=False,
    )

    @api.constrains("name", "code", "country_id")
    def _check_region_uniqueness(self):
        for rec in self:
            region = self.search([
                ('id', '!=', rec.id),
                ('name', '=', rec.name),
                ('code', '=', rec.code),
                ('country_id', '=', rec.country_id.id),
            ], limit=1)
            if region:
                raise ValidationError("Las regiones deben ser únicas.")


class EkResSector(models.Model):
    _name = "ek.res.sector"
    _description = "Sectores"
    _order = "name ASC"

    name = fields.Char(
        string="Nombre",
        size=64,
        required=True,
    )
    code = fields.Char(
        string="Código",
        size=6,
        required=True,
    )
    zone_id = fields.Many2one(
        string="Zona",
        comodel_name="ek.res.state.zone",
        required=False,
    )

    @api.constrains("name", "code")
    def _check_sector_uniqueness(self):
        for rec in self:
            sector = self.search([
                ('id', '!=', rec.id),
                ('name', '=', rec.name),
                ('code', '=', rec.code),
            ], limit=1)
            if sector:
                raise ValidationError("Los sectores deben ser únicos.")


# TODO: A esta entidad le vi dos nombres: Parroquia y Cantón, pero revisando la información lo correcto es Parroquia
class EkResCountryCanton(models.Model):
    _name = "ek.res.country.canton"
    _description = "Parroquias"
    _order = "name ASC"

    name = fields.Char(
        string="Nombre",
        size=64,
        required=True,
    )
    code = fields.Char(
        string="Código",
        size=6,
        required=True,
    )
    city_id = fields.Many2one(
        string="Ciudad",
        comodel_name="ek.res.country.city",
        required=False,
    )

    @api.constrains("name", "code", "city_id")
    def _check_country_canton_uniqueness(self):
        for rec in self:
            country_canton = self.search([
                ('id', '!=', rec.id),
                ('name', '=', rec.name),
                ('code', '=', rec.code),
                ('city_id', '=', rec.city_id.id),
            ], limit=1)
            if country_canton:
                raise ValidationError("Las parroquias deben ser únicas.")


class EkClassification(models.Model):
    _name = "ek.classification"
    _description = "Clasificaciones"
    _parent_name = "parent_id"
    _parent_store = True
    _rec_name = 'complete_name'
    _order = 'complete_name'

    name = fields.Char(
        string="Nombre",
        size=64,
        required=True,
    )

    active = fields.Boolean(
        string='Activa',
        required=False, default=True)

    complete_name = fields.Char(
        'Nombre Completo', compute='_compute_complete_name', recursive=True,
        store=True)
    parent_id = fields.Many2one('ek.classification', 'Clasificación Padre', index=True, ondelete='cascade')
    parent_path = fields.Char(index=True, unaccent=False)
    child_id = fields.One2many('ek.classification', 'parent_id', 'Clasificaciones Hijas')

    def action_archive(self):
        res = super().action_archive()
        for rec in self:
            if rec.child_id and rec.child_id.active:
                rec.child_id.sudo().write({'parent_id': rec.parent_id and rec.parent_id.id or False})

        return res

    @api.depends('name', 'parent_id.complete_name')
    def _compute_complete_name(self):
        for classification in self:
            if classification.parent_id:
                classification.complete_name = '%s / %s' % (classification.parent_id.complete_name, classification.name)
            else:
                classification.complete_name = classification.name

    @api.constrains('parent_id')
    def _check_category_recursion(self):
        if not self._check_recursion():
            raise ValidationError(_('No se pueden crear clasificaciones recursivas.'))

    @api.model
    def name_create(self, name):
        classification = self.create({'name': name})
        return classification.id, classification.display_name

    @api.depends_context('hierarchical_naming')
    def _compute_display_name(self):
        if self.env.context.get('hierarchical_naming', True):
            return super()._compute_display_name()
        for record in self:
            record.display_name = record.name

    _sql_constraints = [
        ('model_unique',
         'unique(name)',
         u'Las clasificaciones deben ser únicas.'),
    ]


class EkResChannel(models.Model):
    _name = "ek.res.channel"
    _description = "Canales"
    _parent_name = "parent_id"
    _parent_store = True
    _rec_name = 'complete_name'
    _order = 'complete_name'

    name = fields.Char(
        string="Nombre",
        size=64,
        required=True,
    )
    code = fields.Char(
        string="Código",
        size=6,
        required=True,
    )

    active = fields.Boolean(
        string='Activo',
        required=False, default=True)

    complete_name = fields.Char(
        'Nombre Completo', compute='_compute_complete_name', recursive=True,
        store=True)
    parent_id = fields.Many2one('ek.res.channel', 'Canal Padre', index=True, ondelete='cascade')
    parent_path = fields.Char(index=True, unaccent=False)
    child_id = fields.One2many('ek.res.channel', 'parent_id', 'Canales Hijos')

    def action_archive(self):
        res = super().action_archive()
        for rec in self:
            if rec.child_id and rec.child_id.active:
                rec.child_id.sudo().write({'parent_id': rec.parent_id and rec.parent_id.id or False})

        return res

    @api.depends('name', 'parent_id.complete_name')
    def _compute_complete_name(self):
        for channel in self:
            if channel.parent_id:
                channel.complete_name = '%s / %s' % (channel.parent_id.complete_name, channel.name)
            else:
                channel.complete_name = "%s" % (channel.name)

    @api.constrains('parent_id')
    def _check_category_recursion(self):
        if not self._check_recursion():
            raise ValidationError(_('No se pueden crear canales recursivos.'))

    @api.model
    def name_create(self, name):
        channel = self.create({'name': name})
        return channel.id, channel.display_name

    @api.depends_context('hierarchical_naming')
    def _compute_display_name(self):
        if self.env.context.get('hierarchical_naming', True):
            return super()._compute_display_name()
        for record in self:
            record.display_name = record.name

    _sql_constraints = [
        ('model_unique',
         'unique(code,name)',
         u'Los canales deben ser únicos.'),
    ]

class ek_res_visit_frequency(models.Model):
    _name = 'ek.res.visit.frequency'
    _description = "Frecuencia de Visita"
    _order = 'code'

    code = fields.Integer(
        string='Código',
        required=False)

    name = fields.Char(
        string='Frecuencia',
        required=False)

    _sql_constraints = [
        ('model_unique',
         'unique(code)',
         u'Las frecuencia de visita deben ser únicas.'),
    ]

class CustomerRank(models.Model):
    _name = 'ek.res.customer.rank'
    _description = "Rango de Cliente"
    _order = 'code'

    code = fields.Integer(
        string='Código',
        required=False)

    name = fields.Char(
        string='Descripción',
        required=False)

    _sql_constraints = [
        ('model_unique',
         'unique(code)',
         u'Los rangos de cliente deben ser únicos.'),
    ]


class ResCountry(models.Model):
    _inherit = 'res.country'

    @api.constrains('address_format')
    def _check_address_format(self):
        for record in self:
            if record.address_format:
                address_fields = self.env['res.partner']._formatting_address_fields() + ['state_code', 'state_name', 'country_code', 'country_name', 'company_name'] + ['business_name','city_id_name', 'canton_id_name', 'sector_id_name', 'classification_id_name', 'region_id_name', 'zone_id_name', 'route_dst_id_name', 'channel_id_name', 'rank_id_name']
                try:
                    record.address_format % {i: 1 for i in address_fields}
                except (ValueError, KeyError):
                    raise UserError(_('The layout contains an invalid format key'))