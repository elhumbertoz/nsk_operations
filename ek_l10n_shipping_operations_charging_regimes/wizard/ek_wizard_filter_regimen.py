from odoo import _, fields, models, api
from odoo.exceptions import UserError

class ek_wizard_filter_regimen(models.TransientModel):
    _name = "ek.wizard.filter.regimen"
    _description = "Wizard: Filter Regimen"

    ek_regimen_table_id = fields.Many2one("ek.ship.registration", string="Regimen",domain="[('assigned_regimen_70', '=', True)]")
    ek_container_ids = fields.Many2many("ek.boats.information","ek_boats_information_id","ek_wizard_filter_regimen", string="Container",domain="[('ship_name_id', '=', ek_regimen_table_id)]")
    ek_id_bls = fields.Many2many("id.bl.70","ek_id_bl_70","ek_wizard_filter_regimen" ,string="ID BL",domain="[('journey_crew_id', 'in', ek_container_ids)]"  ) #fields.Char(string="ID BL") domain="[('id', 'in', id_bl_ids)]"
   
    @api.onchange('ek_regimen_table_id')
    def _onchange_ek_regimen_table_id(self):
        if self.ek_regimen_table_id:
            self.ek_container_ids = self.ek_regimen_table_id.ek_boats_information_ids.ids
        else:
            self.ek_container_ids = False

    @api.onchange('ek_container_ids')
    def _onchange_ek_container_id(self):
        if self.ek_container_ids:
            self.ek_id_bls = self.env["id.bl.70"].search([('journey_crew_id', 'in', self.ek_container_ids.ids)])
        else:
            self.ek_id_bls = False


    def generate_data_kardex(self):

        if not self.ek_regimen_table_id:
            raise UserError(_("You must select a regimen"))
        if not self.ek_container_ids:
             raise UserError(_("You must select at least one container"))
        data = []
        containers =    self.env["ek.boats.information"].search([('id', 'in', self.ek_container_ids.ids)])
        for container in containers:
            if self.ek_id_bls:
                filter_bl = container.ek_produc_packages_goods_ids.filtered(lambda x: x.id_bl.id in self.ek_id_bls.ids)
            else:
                filter_bl = container.ek_produc_packages_goods_ids
            for item in filter_bl:
                data.append({
                    'date_request': item.date_request,
                    'movement_date': item.create_date,
                    #'container_id': container.id,
                    'regimen': "70",
                    'ship_registration_id': item.ek_ship_registration_id.id,
                    'boats_information_id': item.ek_boats_information_id.id,
                    'related_document' : item.id_bl.id,
                    'tariff_item': (item.tariff_item or "") + (item.id_hs_copmt_cd or "") + (item.id_hs_spmt_cd or "") ,
                    'product_description': item.ek_requerid_burden_inter_nac_id.id,
                    'max_regime_date': item.max_regime_date, #agrega esta fecha
                    'unds' : item.quantity,
                    'unit_cost' : item.fob,
                    'customs_document' : item.number_dai,

                })
        if self.ek_container_ids:
            domain = [
                ('ek_operation_request_id.container_id', 'in', self.ek_container_ids.ids),
                ('ek_operation_request_id.has_confirmed_type', '=', True),
                ('ek_operation_request_id.use_in_regimen_60', '=', True),
                ('ek_operation_request_id.canceled_stage', '!=', True),
                ]
            if self.ek_id_bls:
                domain.append(('ek_operation_request_id.id_bl_70', 'in', self.ek_id_bls.ids))
            salida =  self.env["table.regimen.60"].search(domain)
            for item in salida:
                data.append({
                    'date_request': item.ek_operation_request_id.create_date,
                    'movement_date': item.ek_operation_request_id.movement_date,
                    'regimen': "60",
                    'ship_registration_id': item.ek_operation_request_id.ek_ship_registration_id.id,
                    'boats_information_id': item.ek_operation_request_id.journey_crew_id.id,
                    'related_document' : item.ek_operation_request_id.id_bl_70.id,
                    'tariff_item': (item.tariff_item or "") + (item.id_hs_copmt_cd or "") + (item.id_hs_spmt_cd or "") ,
                    'product_description': item.ek_requerid_burden_inter_nac_id.id,
                    'max_regime_date': item.ek_operation_request_id.max_regime_date, #agrega esta fecha
                    'unds' : -abs(item.quantity) ,
                    'unit_cost' : item.fob,
                    'customs_document' : item.ek_operation_request_id.number_dae,
                })

        return data

    def create_wizard_charging(self):

        data = self.generate_data_kardex()
        self.env["ek.wizard.charging.data"].search([]).unlink()
        self.env["ek.wizard.charging.data"].with_context(tracking_disable=True, validation_skip=True).create(data)
        return {
            'type': 'ir.actions.act_window',
            'name': 'Filter Regimen',
            'res_model': 'ek.wizard.charging.data',
            'view_mode': 'tree',
            "view_id": self.env.ref("ek_l10n_shipping_operations_charging_regimes.ek_wizard_charging_data_form").id,
            'target': 'new',
            "context": {
                "create": False,
                "edit": False,
                "delete": False,
            },
        }


    