from odoo import fields, models
import pytz

class AccountReport(models.Model):
    _inherit = 'account.report'

    show_user = fields.Boolean(string="Mostrar Usuario", help="Mostrar Usuario que imprime el reporte")
    show_date = fields.Boolean(string="Mostrar Fecha", help="Mostrar fecha en la que se imprime el reporte")

    show_footer = fields.Boolean(string="Pie de Firma", help="Mostrar pie de firma")

    show_general_manager = fields.Boolean(string="Firma para Gerente General")
    show_auditor = fields.Boolean(string="Firma para Auditor")
    show_controller = fields.Boolean(string="Firma para Contralor")
    show_counter = fields.Boolean(string="Firma para Contador")

    # ####################################################
    # OPTIONS: ALL ENTRIES
    ####################################################
    def _init_options_print_user(self, options, previous_options=None):
        if self.show_user:
            options['print_user'] = self.env.user.name
        else:
            options['print_user'] = False

        if self.show_date:
            user_tz = self.env.user.tz or pytz.utc.zone
            local = pytz.timezone(user_tz)
            date = fields.Datetime.now()
            options['print_date'] = fields.Datetime.to_string(pytz.utc.localize(date).astimezone(local))
        else:
            options['print_date'] = False

        options['print_footer'] = self.show_footer
        options['show_general_manager'] = self.show_general_manager
        options['show_auditor'] = self.show_auditor
        options['show_controller'] = self.show_controller
        options['show_counter'] = self.show_counter



    def _init_options_all_entries(self, options, previous_options=None):
        super()._init_options_all_entries(options, previous_options)
        self._init_options_print_user(options, previous_options)