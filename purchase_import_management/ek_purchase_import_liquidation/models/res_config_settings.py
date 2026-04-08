from odoo import fields, models, api

class ResCompany(models.Model):
    _inherit = 'res.company'

    number_of_month_for_pm = fields.Integer(
        string='Meses para tiempo promedio',
        default=3,
        required=False)

    manual_share_import_cost = fields.Boolean(
        string='Factor de importación manual (%)',
        default=False   
    )

class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    property_stock_account_import_cost_id = fields.Many2one(
        'account.account', 'Cuenta de Importaciones',
        domain="[('deprecated', '=', False)]", check_company=True,
        help="""Esta cuenta se utilizará como contrapartida de en los documentos de importación.""",
        compute= '_compute_property_stock_account',
        inverse= '_set_property_stock_account_import_cost_id'
    )

    number_of_month_for_pm = fields.Integer(
        related="company_id.number_of_month_for_pm",
        readonly=False)

    manual_share_import_cost = fields.Boolean(
        related="company_id.manual_share_import_cost",
        readonly=False
    )

    @api.depends('company_id')
    def _compute_property_stock_account(self):
        for record in self:
            record._set_property('property_stock_account_import_cost_id')


    @api.model
    def _get_account_stock_properties_names(self):
        return super()._get_account_stock_properties_names() + [
            'property_stock_account_import_cost_id',
        ]

    def _set_property_stock_account_import_cost_id(self):
        for record in self:
            record._set_property('property_stock_account_import_cost_id')