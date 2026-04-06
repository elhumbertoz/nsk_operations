# -*- coding: utf-8 -*-
import logging

from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError

_logger = logging.getLogger(__name__)


class EkBoatsInformation(models.Model):
    _inherit = 'ek.boats.information'

    


    ref_container = fields.Char("Ref. Container")
    ek_produc_packages_goods_ids = fields.One2many("ek.product.packagens.goods","ek_boats_information_id", string="Product Packagens Goods", copy=True)

    value_of_container = fields.Float("Value of Container",compute="_compute_value_of_container",store=True, index=True)

    @api.depends("ek_produc_packages_goods_ids.quantity_hand","ek_produc_packages_goods_ids.delivery_product","ek_produc_packages_goods_ids")
    def _compute_value_of_container(self):
        for rec in self:
            rec.value_of_container = sum(rec.mapped("ek_produc_packages_goods_ids.quantity_hand")) 



    
    #Containers from regimens 70 and 60
    # state = fields.Selection(
    #     selection_add=[
    #         ("anotification", "Arrival Notification"),
    #         ("inspection", "Inspection/Capacity"),
    #         ("transfer", "Transfer"),
    #         ("desconsolidation", "Desconsolidation"),
    #         ("return", "Return Container"),
    #     ],
    #     ondelete={
    #         "draft": "cascade",
    #     }, tracking=True
    # )

    has_process_travel = fields.Boolean("Has Process Travel", default=False)

    type_move_container = fields.Selection(
        selection=[
            ("maritime", "Maritime"),
            ("aerial", "Aerial"),
            ("land", "Land"),
        ],
        string="Type of Transport", tracking=True
    )

    shipper_id = fields.Many2one(
        string="Shipper ",
        comodel_name="res.partner",
        required=False, tracking=True
    )
    shipping_company = fields.Many2one(
        string="Shipping Company",
        comodel_name="res.partner",
        required=False, tracking=True
    )
    custom_agent = fields.Many2one(
        string="Custom Agent",
        comodel_name="res.partner",
        required=False, tracking=True
    )

    load_number = fields.Char("Load Number", default=_("CONTAINER #"))
    supplies_detail = fields.Char("Supplies Detail", tracking=True)
    container_number = fields.Char("Container Number", tracking=True)
    bl_number = fields.Char("# AWB O BL", tracking=True)
    
    supplier_ids = fields.Many2many(
        comodel_name='res.partner',
        string='Suppliers', relation="res_partner_ek_boats_information_rel",
        column1='partner_id', column2='ek_boats_information_id', tracking=True)

    type_container_id = fields.Many2one("ek.type.container", string="Type Container", tracking=True)

    notes = fields.Text("Notes", tracking=True)

    rcd = fields.Datetime(string="Return Container Date", copy=False, tracking=True)


    def open_items_container(self):
            return {
                'name': 'Search Items',
                'type': 'ir.actions.act_window',
                'res_model': 'ek.product.packagens.goods',
                'view_mode': 'tree',
                'view_id': self.env.ref('ek_l10n_shipping_operations_charging_regimes.ek_product_packagens_goods_tree_items').id,
                'target': 'new',
                'domain': [('id', 'in', self.ek_produc_packages_goods_ids.ids)],
                "context": {
                    "create": False,
                    "edit": True,
                    "delete": True,
                    },
            }




class ek_product_packagens_goods(models.Model):
    _inherit = "ek.product.packagens.goods"

    id_bl = fields.Many2one("id.bl.70", string="ID BL")

    def delete_table_70(self):
        records = self.browse(self.env.context.get('active_ids'))
        if records:
            records.unlink()
            