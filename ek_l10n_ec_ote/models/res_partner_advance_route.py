from odoo import fields, models, api


class ResPartnerAdvanceRoute(models.Model):
    _name = 'ek.res.partner.advance.route'
    _description = 'Rutas Avanzadas'

    partner_id = fields.Many2one(
        comodel_name='res.partner',
        string='Cliente',
        required=True)

    contact_id = fields.Many2one(
        comodel_name='res.partner',
        string='Sucursal',
        required=True, domain="['|',('parent_id','=',partner_id),('id','=',partner_id)]")

    zone_id = fields.Many2one(
        comodel_name='ek.res.state.zone',
        string='Zona',
        required=True)

    channel_id = fields.Many2one(
        comodel_name='ek.res.channel',
        string='Canal',
        required=True)

    route_id = fields.Many2one(
        comodel_name='ek.res.route',
        string='Ruta',
        required=True)

    sector_id = fields.Many2one(
        comodel_name='ek.res.sector',
        string='Sector',
        required=False)

    user_id = fields.Many2one(
        comodel_name='res.users',
        string='Vendedor',
        required=False, domain="[('share','=',False)]")

    supervisor_id = fields.Many2one(
        comodel_name='res.users',
        string='Supervisor',
        required=False, domain="[('share','=',False)]")

    supervisor_chanel_id = fields.Many2one(
        comodel_name='res.users',
        string='Supervisor de Canal',
        required=False, domain="[('share','=',False)]")

    supervisor_sector_id = fields.Many2one(
        comodel_name='res.users',
        string='Supervisor de Sector',
        required=False, domain="[('share','=',False)]")

    supervisor_route_id = fields.Many2one(
        comodel_name='res.users',
        string='Supervisor de Ruta',
        required=False, domain="[('share','=',False)]")

    visit_frequency = fields.Many2many(
        comodel_name='ek.res.visit.frequency',
        string='Frecuencia de Visita', relation="res_partner_contact_visit_frequency_rel",
        column1='partner_id', column2='frequency_id')