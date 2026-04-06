from odoo import models, fields, api
from odoo.exceptions import UserError
import base64


class WizardUpdateLinesNsk(models.TransientModel):
    _name = 'wizard.update.lines.nsk'
    _description = 'Wizard para actualizar registros'

    ship_name_id = fields.Many2one('ek.ship.registration', string="Buque",readonly=True)
    new_ship_name_id = fields.Many2one('ek.ship.registration',string="Nuevo Buque")

    journey_crew_id = fields.Many2one('ek.boats.information',string="Journey",readonly=True)
    new_journey_crew_id = fields.Many2one('ek.boats.information',string="Nuevo Journey",domain="[('ship_name_id','=',new_ship_name_id),('state','in',['draft','process','done'])]")

    def action_update_lines(self):
        for line in self.env['account.move.line'].browse(self._context.get('active_ids')):
            line.ship_name_id = self.new_ship_name_id
            line.journey_crew_id = self.new_journey_crew_id


