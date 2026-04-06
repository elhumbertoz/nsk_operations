from odoo import fields, models, api
from odoo.exceptions import ValidationError

class TypesDeferredCreditCard(models.Model):
    _name = "ek.types.deferred.credit.card"
    _description = "Tipos de diferidos"
    _order = 'sequence asc'

    sequence = fields.Integer('Secuencia', default=10)
    name = fields.Integer(
        string='Meses',
        required=False)
    interest_applies = fields.Boolean(
        string='Aplica Interés',
        required=False)

    interest_percent = fields.Float(
        string='% Interés',
        required=False)

    active = fields.Boolean(
        string='Activo?',
        required=False, default=True)

    @api.depends("name")
    def _compute_display_name(self):
        for rec in self:
            name = "(%s) %s" % (rec.name, rec.name > 1 and 'meses' or 'mes')
            if rec.interest_applies:
                name += ' con interés'
            else:
                name += ' sin interés'

            rec.display_name = name

    @api.constrains('interest_applies', 'interest_percent')
    def check_interest_percent(self):
        for rec in self:
            if rec.interest_percent < 0 or rec.interest_percent > 100:
                raise ValidationError("El porcentaje de interés no puede ser menor a 0 ni mayor a 100")

    @api.constrains('name')
    def check_name(self):
        for rec in self:
            if rec.name < 0:
                raise ValidationError("Los meses de interés deben ser mayor a cero")

    _sql_constraints = [
        ('unique_types', 'unique(name,interest_applies)',
         'No es posible repetir los meses y la aplicación de intereses, consulte si tienes alguna línea archivada!'),
    ]