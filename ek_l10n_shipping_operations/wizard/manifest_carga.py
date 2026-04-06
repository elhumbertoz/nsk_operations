from odoo import models, fields, api
from odoo.exceptions import UserError
import base64


class ManifestCargaWizard(models.TransientModel):
    _name = 'manifest.carga.wizard'
    _description = 'Wizard para seleccionar varios registros'
    _inherit = ['common.fields.mixin']    


    action_report_id = fields.Many2one('ir.actions.report', string="Action Report", required=True,domain=[('model','=','manifest.carga.wizard')])
    item_ids = fields.Many2many('ek.operation.request', string="Items seleccionados")
    
    context_active_model = fields.Char(
        store=False, compute="_compute_active_context_model"
    )

    ship_name_id = fields.Many2one("ek.ship.registration", string="Barco")
    journey_crew_id = fields.Many2one(
        "ek.boats.information",
        string="Journey",
        domain="[('ship_name_id','=',ship_name_id)]",
    )
    ek_manifest_record_id = fields.Many2one("ek.bl.manifest.record", string="Manifest")
    arrival = fields.Date(string="Llegada")
    exit = fields.Date(string="Salida")
    shipowner = fields.Many2one("res.partner", string="Armador")
    captain = fields.Many2one("res.partner", string="Capitan")
    agent = fields.Many2one("res.partner", string="Agente")
    nationality = fields.Many2one("res.country", string="Nacionalidad")
    port_emision = fields.Many2one("ek.res.world.seaports", string="Puerto Emision")
    port_embarque = fields.Many2one("ek.boat.location", string="Puerto Embarque")
    destin_final = fields.Many2one("ek.boat.location", string="Destino Final")
    embarque = fields.Many2one("res.partner", string="Embarcador")
    consignat = fields.Many2one("res.partner", string="Consignatario")
    description = fields.Text(string="Description")










    @api.model
    def default_get(self, fields):
        res = super().default_get(fields)
        active_model = self.env.context.get("active_model", False)
        active_ids = self.env.context.get("active_ids", False)
        if active_model and active_ids:
            operation = self.env[active_model].browse(active_ids[-1])
            res["item_ids"] = [(4, item_id) for item_id in active_ids]
            res["ship_name_id"] = operation.ek_ship_registration_id.id
            res["journey_crew_id"] = operation.journey_crew_id.id
            res["ek_manifest_record_id"] = operation.ek_manifest_record_id.id
            res["arrival"] = operation.journey_crew_id.eta
            res["exit"] = operation.journey_crew_id.etd
            res["shipowner"] = operation.journey_crew_id.bussiness_name_id.id
            res["captain"] = operation.ek_ship_registration_id.capital_name_id.id
          #  res["agent"] = operation.agent.id
            res["nationality"] = operation.ek_ship_registration_id.ship_flag_id.id
            res["port_emision"] = operation.port_of_discharge.id
            res["port_embarque"] = operation.ek_boat_location_id.id
            res["destin_final"] = operation.ek_boat_location_id.id
            res['embarque'] = operation.shipper_res_partner_id.id
            res['consignat'] = operation.consignee_res_partner_id.id


        return res
    
    def _compute_active_context_model(self):
        self.context_active_model = self.env.context.get("active_model")

    def action_print_manifest(self):
        report = self.action_report_id._render_py3o(self.action_report_id.id, self.ids, {})
        pdf_base64 = base64.b64encode(report[0])
        attachment_id = self.env['ir.attachment'].create({
            'name': self.action_report_id.name ,
            'type': 'binary',
            'datas': pdf_base64,
            'store_fname': self.action_report_id.name,
            'res_model': self._name,
            'res_id': self.id,
        })

        action = {
                'type': 'ir.actions.act_url',
                'url': f'/web/content/{attachment_id.id}?download=true',
                'target': 'self',
                'close_on_report_download': True,

                }

        return action
