from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class EkOperationRequestNotification(models.Model):
  """Modelo para manejar notificaciones de usuarios en solicitudes de operación"""

  _name = 'ek.operation.request.notification'
  _description = 'Notificaciones de Solicitud de Operación'
  _order = 'sequence, user_id'

  # Campos principales
  user_id = fields.Many2one('res.users', string='Usuario', required=True)
  user_image = fields.Image(
    related='user_id.image_1920', string='Foto del Usuario', readonly=True
  )
  notify = fields.Boolean(
    string='Notificar',
    default=True,
    help='Marcar para enviar notificación a este usuario en la etapa actual',
  )
  create_activity = fields.Boolean(
    string='Crear Actividad',
    default=False,
    help='Marcar para crear una actividad al pasar a la siguiente etapa',
  )
  sequence = fields.Integer(string='Secuencia', default=10)

  # Relaciones
  request_id = fields.Many2one(
    'ek.operation.request',
    string='Solicitud',
    required=True,
    ondelete='cascade',
  )

  # Campos informativos
  name = fields.Char(string='Nombre', compute='_compute_name', store=True)

  @api.depends('user_id', 'request_id')
  def _compute_name(self):
    """Genera el nombre basado en el usuario y la solicitud"""
    for record in self:
      if record.user_id and record.request_id:
        record.name = f'{record.user_id.name} - {record.request_id.name}'
      else:
        record.name = ''

  @api.constrains('notify', 'create_activity')
  def _check_exclusive_fields(self):
    """Valida que notify y create_activity sean mutuamente excluyentes"""
    for record in self:
      if record.notify and record.create_activity:
        raise ValidationError(
          _(
            'Un usuario no puede tener marcado tanto "Notificar" como "Crear Actividad" al mismo tiempo. '
            'Debe elegir solo una opción.'
          )
        )

  def write(self, vals):
    """Implementa lógica de exclusión mutua en write"""
    # Si se está marcando notify=True, desmarcar create_activity
    if vals.get('notify') and vals.get('create_activity') is not False:
      vals['create_activity'] = False

    # Si se está marcando create_activity=True, desmarcar notify
    if vals.get('create_activity') and vals.get('notify') is not False:
      vals['notify'] = False

    return super().write(vals)
