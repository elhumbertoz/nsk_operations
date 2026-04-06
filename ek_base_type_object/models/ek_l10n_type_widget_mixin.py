from odoo import _, api, fields, models

class EkL10nTypeWidgetMixin(models.Model):
    _name = 'ek.l10n.type.widget.mixin'
    _description = _("Type Generic Widget for Fields")
    _rec_name = 'widget'

    ttype = fields.Selection(
        selection=[
            ('char', 'Char'),
            ('date', 'Date'),
            ('datetime', 'Datetime'),
            ('float', 'Float'),
            ('integer', 'Integer'),
            ('many2one', 'Many2one'),
            ('many2many', 'Many2many'),
            ('one2many', 'One2many'),
            ('selection', 'Selection'),
            ('boolean', 'Boolean'),
        ],
        required=True)

    value = fields.Char(string='Value')
    widget = fields.Char(string='Widget')
