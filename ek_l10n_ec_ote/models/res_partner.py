# Part of Odoo. See LICENSE file for full copyright and licensing details.

import logging

from odoo import api, models, _, fields
from odoo.exceptions import ValidationError
from odoo.tools import config

_logger = logging.getLogger(__name__)
import requests
import random
import string
import json
from hashlib import md5
from .utils import agent_list, hashes, URL_SRI_REQUEST


def verify_final_consumer(vat):
    all_number_9 = False
    try:
        all_number_9 = vat and all(int(number) == 9 for number in vat) or False
    except ValueError as e:
        _logger.debug("La identificación solo puede contener números %s.", e)
    return all_number_9 and len(vat) == 13


class ResPartner(models.Model):
    _inherit = "res.partner"

    l10n_ec_business_name = fields.Char(
        string="Nombre comercial",
        required=False,
        readonly=False,
    )
    l10n_ec_city_id = fields.Many2one(
        string="Ciudad",
        comodel_name="ek.res.country.city",
        required=False,
    )
    l10n_ec_canton_id = fields.Many2one(
        string="Parroquia",
        comodel_name="ek.res.country.canton",
        required=False,
    )
    l10n_ec_sector_id = fields.Many2one(
        string="Sector",
        comodel_name="ek.res.sector",
        required=False,
    )
    l10n_ec_region_id = fields.Many2one(
        string="Región",
        comodel_name="ek.res.region",
        required=False,
    )
    l10n_ec_zone_id = fields.Many2one(
        string="Zona",
        comodel_name="ek.res.state.zone",
        required=False,
    )
    l10n_ec_route_dst_id = fields.Many2one(
        string="Ruta",
        comodel_name="ek.res.route",
        required=False,
    )
    l10n_ec_classification_id = fields.Many2one(
        string="Clasificación",
        comodel_name="ek.classification",
        required=False,
    )
    l10n_ec_channel_id = fields.Many2one(
        string="Canal",
        comodel_name="ek.res.channel",
        required=False,
    )
    l10n_ec_rank_id = fields.Many2one(
        string="Ranking",
        comodel_name="ek.res.customer.rank",
        required=False,
    )
    l10n_ec_priority = fields.Integer(
        string="Prioridad",
        required=False,
    )
    vat = fields.Char(copy=False)

    l10n_ec_visit_frequency = fields.Many2many(
        comodel_name='ek.res.visit.frequency',
        string='Frecuencia de Visita', relation="res_partner_l10n_ec_visit_frequency_rel",
        column1='partner_id', column2='frequency_id')

    l10n_ec_delivery_frequency = fields.Many2many(
        comodel_name='ek.res.visit.frequency',
        string='Frecuencia de Entregas', relation="res_partner_l10n_ec_delivery_frequency_rel",
        column1='partner_id', column2='frequency_id')

    l10n_ec_delivery_frequency_start_hour = fields.Float(
        string='Hora Inicio de Entregas',
        required=False)

    l10n_ec_delivery_frequency_end_hour = fields.Float(
        string='Hora Fin de Entregas',
        required=False)

    l10n_ec_is_artisan = fields.Boolean(
        string='Artesano',
        required=False)

    l10n_ec_sex = fields.Selection(
        string='Sexo',
        selection=[('male', 'Masculino'),
                   ('female', 'Femenino'),
                   ('others', 'Otros'), ],
        required=False, )

    l10n_ec_gender = fields.Selection(
        string='Genero',
        selection=[('male', 'Masculino'),
                   ('female', 'Femenino'),
                   ('others', 'Otros'), ],
        required=False, )

    l10n_ec_civil_status = fields.Selection(
        string='Estado Civil',
        selection=[('S', 'Soltero/a'),
                   ('C', 'Casado/a'),
                   ('D', 'Divorciado/a'),
                   ('U', 'Unión Libre'),
                   ('V', 'Viudo/a'),
                   ('O', 'Otros'), ],
        required=False, )

    l10n_ec_birthdate = fields.Date(
        string='Fecha de Nacimiento',
        required=False)

    l10n_ec_main_economic_activity = fields.Text(
        string="Actividad económica principal",
        required=False)

    l10n_ec_vat_active = fields.Boolean(
        string='Ruc Activo?',
        required=False)

    l10n_ec_required_to_keep_accounting = fields.Boolean(
        string='Obligado a llevar contabilidad?',
        required=False)

    l10n_ec_retention_agent = fields.Boolean(
        string='Agente de retención?',
        required=False)

    l10n_ec_special_taxpayer = fields.Boolean(
        string='Contribuyente especial?',
        required=False)

    l10n_ec_legal_representative_vat = fields.Char(
        string='Identificación de Representate',
        required=False)

    l10n_ec_legal_representative_name = fields.Char(
        string='Nombre de Representate',
        required=False)

    l10n_ec_date_last_update_accounting_info = fields.Datetime(
        string='Ultima Actualización',
        required=False)

    advance_route_ids = fields.One2many(
        comodel_name='ek.res.partner.advance.route',
        inverse_name='partner_id',
        string='Rutas Avanzadas',
        required=False)

    advance_route_contact_ids = fields.One2many(
        comodel_name='ek.res.partner.advance.route',
        inverse_name='contact_id',
        string='Rutas de Contactos',
        required=False)

    @api.model
    def _name_search(self, name="", domain=None, operator="ilike", limit=100, order=None):
        res = super(ResPartner, self)._name_search(
            name, domain=domain, operator=operator, limit=limit, order=order
        )
        res_ids = list(res)
        domain = [('id', 'not in', res_ids), ('l10n_ec_business_name', operator, name)]
        partner_business_ids = list(
            self._search(domain, limit=limit)
        )
        res_ids.extend(partner_business_ids)
        return res_ids

    def get_route_by_date_and_user(self, date, user_id):
        date_visit = fields.Date.today()
        if date:
            date_visit = fields.Date.to_date(date)
            weekday = date_visit.weekday()
        else:
            weekday = date_visit.weekday()
        # Planificación de las rutas avanzadas
        routes = self.env['ek.res.partner.advance.route'].search([
            ('visit_frequency.code', '=', weekday),
            ('partner_id', 'in', self.ids)
        ])

        if routes:
            return routes[0]
        else:
            return False

    @api.constrains("vat", "parent_id")
    def _check_vat_unique(self):
        for record in self:
            if record.parent_id or not record.vat:
                continue
            test_condition = config["test_enable"] and not self.env.context.get(
                "test_vat"
            )
            if test_condition:
                continue
            # # Define the domain to filter partners
            # domain = [('vat', '=', record.vat), ('id', '!=', record.id)]
            # # Filter by company, either partners without a company or in the same company as the current user
            # domain += ['|', ('company_id', '=', False), ('company_id', '=', record.env.user.company_id.id)]
            # # Search for partners that match the criteria
            # duplicate = self.search(domain)
            # if not duplicate:
            #     return False
            if record.same_vat_partner_id:
                raise ValidationError(
                    _("The VAT %s already exists in another partner.") % record.vat
                )

    @api.onchange("l10n_ec_city_id")
    def onchange_city_id(self):
        for rec in self:
            if rec.l10n_ec_city_id:
                rec.city = rec.l10n_ec_city_id.name
            else:
                rec.city = ''

    def _get_complete_address(self):
        self.ensure_one()
        partner_id = self
        address = ""
        if partner_id.street:
            address += partner_id.street + ", "
        if partner_id.street2:
            address += partner_id.street2 + ", "
        if partner_id.city or partner_id.l10n_ec_city_id:
            address += (partner_id.city or partner_id.l10n_ec_city_id.name) + ", "
        if partner_id.state_id:
            address += partner_id.state_id.name + ", "
        if partner_id.zip:
            address += "(" + partner_id.zip + ") "
        if partner_id.country_id:
            address += partner_id.country_id.name
        return address

    # def _formatting_address_fields(self):
    #     """Returns the list of address fields that are synced from the parent."""
    #     return super()._formatting_address_fields() + ['business_name','city_id_name', 'canton_id_name', 'sector_id_name', 'classification_id_name', 'region_id_name', 'zone_id_name', 'route_dst_id_name', 'channel_id_name']

    def _prepare_display_address(self, without_company=False):
        # get the information that will be injected into the display format
        # get the address format
        address_format, args = super()._prepare_display_address(without_company=without_company)

        args['business_name'] = self.l10n_ec_business_name or ''
        args['city_id_name'] = self.city_id and self.city_id.name or ''
        args['canton_id_name'] = self.l10n_ec_canton_id and self.l10n_ec_canton_id.name or ''
        args['sector_id_name'] = self.l10n_ec_sector_id and self.l10n_ec_sector_id.name or ''
        args['classification_id_name'] = self.l10n_ec_classification_id and self.l10n_ec_classification_id.name or ''
        args['region_id_name'] = self.l10n_ec_region_id and self.l10n_ec_region_id.name or ''
        args['zone_id_name'] = self.l10n_ec_zone_id and self.l10n_ec_zone_id.name or ''
        args['route_dst_id_name'] = self.l10n_ec_route_dst_id and self.l10n_ec_route_dst_id.name or ''
        args['channel_id_name'] = self.l10n_ec_channel_id and self.l10n_ec_channel_id.name or ''
        args['rank_id_name'] = self.l10n_ec_rank_id and self.l10n_ec_rank_id.name or ''

        salesperson = ""
        if self.sudo().user_id:
            salesperson = self.sudo().user_id.partner_id.name
        elif self.sudo().parent_id.user_id:
            salesperson = self.sudo().parent_id.user_id.partner_id.name

        args['salesperson'] = salesperson
        # for field in self._formatting_address_fields():
        #     args[field] = self[field] or ''
        # if without_company:
        #     args['company_name'] = ''
        # elif self.commercial_company_name:
        #     address_format = '%(company_name)s\n' + address_format
        return address_format, args

    @api.constrains("l10n_ec_delivery_frequency_end_hour", "l10n_ec_delivery_frequency_start_hour")
    def check_l10n_ec_delivery_frequency_hours(self):
        for rec in self:
            if rec.l10n_ec_delivery_frequency_end_hour < 0 or rec.l10n_ec_delivery_frequency_start_hour < 0:
                raise ValidationError("Los horarios de entrega no pueden ser negativos")
            if rec.l10n_ec_delivery_frequency_end_hour > 0 and rec.l10n_ec_delivery_frequency_end_hour < rec.l10n_ec_delivery_frequency_start_hour:
                raise ValidationError("Los hora de inicio de entrega no puede ser mayor a la hora de fin")

    @api.model
    def autocomplete(self, query, timeout=15):
        country_code = self.env.company.country_code
        if country_code == 'EC':
            suggestions = []
            if query and query.isnumeric() and len(query) in [10, 13]:
                ULR_FIND = "%s/%s/?tipoPersona=N" % (URL_SRI_REQUEST, query)
                response = requests.request("GET", url=ULR_FIND, timeout=timeout)
                if response.status_code == 200:
                    data = response.json()
                    taxpayer = data.get('contribuyente', {})
                    if taxpayer:
                        identification_type_ruc = self.env.ref('l10n_ec.ec_ruc', False)
                        identification_type_dni = self.env.ref('l10n_ec.ec_dni', False)
                        identification = taxpayer.get('identificacion', query)
                        company_type = (taxpayer.get('clase', "") == 'PERSONA NATURAL' or len(
                            identification) == 10) and 'person' or 'company'
                        suggestions.append({
                            'name': taxpayer.get('nombreComercial', ''),
                            'l10n_ec_business_name': taxpayer.get('nombreComercial', ''),
                            'vat': identification,
                            'company_type': company_type,
                            'l10n_latam_identification_type_id': len(
                                identification) == 13 and identification_type_ruc.ids or identification_type_dni.ids
                        })
            if suggestions:
                results = []
                for suggestion in suggestions:
                    results.append(self._format_data_company(suggestion))
                return results
            else:
                return []

        return super().autocomplete(query, timeout=timeout)

    @api.model
    def enrich_company(self, company_domain, partner_gid, vat, timeout=15):
        country_code = self.env.company.country_code
        if country_code == 'EC':
            if vat and len(vat) == 13:
                return self.consult_by_ruc(vat)
            else:
                return {}

        return super().enrich_company(company_domain, partner_gid, vat, timeout=timeout)

    def consult_by_ruc(self, vat, manual=False):
        res = []
        errors = []
        url_base_sri = "https://srienlinea.sri.gob.ec/"
        startPath = "sri-captcha-servicio-internet/captcha/start/5?r="
        imagePath = "sri-captcha-servicio-internet/captcha/image/%s"
        url_catcha_valid = "sri-captcha-servicio-internet/rest/ValidacionCaptcha/validarCaptcha/%s?emitirToken=true"
        wsgi1_sri = "sri-catastro-sujeto-servicio-internet/rest/ConsolidadoContribuyente/obtenerPorNumerosRuc?&ruc=%s"
        wsgi2_sri = "sri-catastro-sujeto-servicio-internet/rest/Establecimiento/consultarPorNumeroRuc?numeroRuc=%s"
        wsgi_micro = "sri-catastro-sujeto-servicio-internet/rest/ClasificacionMipyme/consultarPorNumeroRuc?numeroRuc=%s"
        wsgi_existe = "sri-catastro-sujeto-servicio-internet/rest/ConsolidadoContribuyente/existePorNumeroRuc?numeroRuc=%s"

        randomstr = ''.join(random.SystemRandom().choice(string.ascii_uppercase + string.digits) for _ in range(10))
        useragent = random.choice(agent_list)
        headers = {
            "user-agent": useragent,
            "host": "srienlinea.sri.gob.ec",
            "referer": "https://srienlinea.sri.gob.ec/sri-en-linea/SriRucWeb/ConsultaRuc/Consultas/consultaRuc",
        }
        session = requests.Session()
        session.headers = headers
        urlexiste = "{host}{path}".format(host=url_base_sri, path=(wsgi_existe % (vat)))
        try:
            response_check_ruc = session.get(urlexiste)
            if response_check_ruc.status_code < 200 or response_check_ruc.status_code >= 300:
                return {}
        except Exception as e:
            return {}

        exist = json.loads(response_check_ruc.content.decode("utf-8"))
        if not exist:
            return {}

        ############## REQUEST AUTH SRI ######################
        urlStart = "{host}{path}".format(host=url_base_sri, path=(startPath + randomstr))
        data = json.loads(session.get(urlStart).content.decode("utf-8"))
        # TODO: OBTENGO CATCHA TO RESOLVE
        image_field_name = data['imageFieldName']
        their_image_name = data['imageName'].lower()
        values = data['values']
        ############## FIN  REQUEST AUTH SRI  ######################
        postdata = {}
        # TODO Rompiendo Seguridades
        for index in range(len(values)):
            url_img = "{host}{path}".format(host=url_base_sri, path=(imagePath % (index)))
            url_anterior = url_base_sri + (imagePath % (index))
            image_data = session.get(url_img).content[0:200]
            hash = md5(image_data).hexdigest()
            our_image_name = hashes[hash]
            # Encuentra backport
            if our_image_name == their_image_name:
                value = values[index]
                parse_log = "Passing %s => %s as POST value" % (image_field_name, value)
                postdata[image_field_name] = value
                break
        if postdata:
            result = session.get(url_base_sri + url_catcha_valid % (value), headers=headers)
            res_autentica_sri = json.loads(result.text)
            autentica_utf = res_autentica_sri['mensaje'].encode('utf-8', errors='strict')
            url_consult = url_base_sri + wsgi1_sri % (vat)
            url2_consult = url_base_sri + wsgi2_sri % (vat)
            url3_consult = url_base_sri + wsgi_micro % (vat)
            headers.update({
                "Authorization": autentica_utf,
                "type": "Content-Type: application/json"
            })
            result1 = session.get(url_consult, headers=headers)
            result2 = session.get(url2_consult, headers=headers)
            # result3 = session.get(url3_consult, headers=headers)

            try:
                data = {}
                primary = result1.json()
                secundary = result2.json()
                # result3.json()
                identification_type_ruc = self.env.ref('l10n_ec.ec_ruc', False)
                if primary and len(primary):
                    primary = primary[0]

                    company_type = (primary.get('tipoContribuyente', "") == 'PERSONA NATURAL' or len(
                        vat) == 10) and 'person' or 'company'

                    data.update({
                        'name': primary.get('razonSocial', ''),
                        'l10n_ec_business_name': primary.get('razonSocial', ''),
                        'vat': vat,
                        'company_type': company_type,
                        'l10n_latam_identification_type_id': identification_type_ruc.ids,
                        'l10n_ec_main_economic_activity': primary.get('actividadEconomicaPrincipal', False),
                        'l10n_ec_vat_active': primary.get('estadoContribuyenteRuc', '') == 'ACTIVO',
                        'l10n_ec_required_to_keep_accounting': primary.get('obligadoLlevarContabilidad', '') == 'SI',
                        'l10n_ec_retention_agent': primary.get('agenteRetencion', '') == 'SI',
                        'l10n_ec_special_taxpayer': primary.get('contribuyenteEspecial', '') == 'SI',

                    })

                    if primary.get('representantesLegales', None) != None and primary.get('representantesLegales',
                                                                                          False):
                        data.update({
                            'l10n_ec_legal_representative_vat': primary.get('representantesLegales', [{}])[0].get(
                                'identificacion', ''),
                            'l10n_ec_legal_representative_name': primary.get('representantesLegales', [{}])[0].get(
                                'nombre', ''),
                        })

                    if primary.get('contribuyenteEspecial', 'NO') != 'NO':
                        data.update({
                            'l10n_ec_taxpayer_type_id': self.env.ref('l10n_ec_edi.l10n_ec_taxpayer_type_02', False).ids
                        })
                    elif primary.get('regimen', '') == 'RIMPE':
                        data.update({
                            'l10n_ec_taxpayer_type_id': self.env.ref('l10n_ec_edi.l10n_ec_taxpayer_type_13', False).ids
                        })
                    elif primary.get('tipoContribuyente', '') == 'SOCIEDAD':
                        data.update({
                            'l10n_ec_taxpayer_type_id': self.env.ref('l10n_ec_edi.l10n_ec_taxpayer_type_01', False).ids
                        })
                    elif primary.get('tipoContribuyente', '') == 'PERSONA NATURAL':
                        if primary.get('obligadoLlevarContabilidad', 'NO') == 'NO':
                            data.update({
                                'l10n_ec_taxpayer_type_id': self.env.ref('l10n_ec_edi.l10n_ec_taxpayer_type_06',
                                                                         False).ids
                            })
                        else:
                            data.update({
                                'l10n_ec_taxpayer_type_id': self.env.ref('l10n_ec_edi.l10n_ec_taxpayer_type_04',
                                                                         False).ids
                            })

                if manual:
                    if 'l10n_ec_taxpayer_type_id' in data:
                        data.update({
                            'l10n_ec_taxpayer_type_id': data.get('l10n_ec_taxpayer_type_id', [False])[0]
                        })
                    data.update({
                        'l10n_latam_identification_type_id': identification_type_ruc.id,
                        'l10n_ec_date_last_update_accounting_info': fields.Datetime.now()
                    })

                if secundary and len(secundary):
                    secundary = secundary[0]
                    if secundary.get('direccionCompleta', False):
                        street = str(secundary.get('direccionCompleta', '')).split("/")
                        data.update({
                            'street': (street[-1]).strip(),
                        })
                    if secundary.get('nombreFantasiaComercial', False):
                        data.update({
                            'l10n_ec_business_name': secundary.get('nombreFantasiaComercial', False),
                        })

                return data
            except:
                return {}
        return {}

    def action_update_fiscal_info(self):
        for rec in self:
            country_code = rec.env.company.country_code
            if country_code == 'EC':
                if rec.vat and len(rec.vat) == 13:
                    data = rec.consult_by_ruc(rec.vat, True)
                    if data:
                        rec.write(data)
