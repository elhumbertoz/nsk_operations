import pytz
from num2words import num2words
from odoo import api, fields, models


class CommonFieldsMixin(models.AbstractModel):
  _name = 'common.fields.mixin'
  _description = 'Common Fields Mixin'

  date_today = fields.Date(string='Date Today', compute='_compute_date_today')

  @api.depends('date_today')
  def _compute_date_today(self):
    for record in self:
      record.date_today = fields.Date.context_today(self)

  @api.model
  def update_date_today(self):
    models_to_update = [
      'ek.operation.request',
      'ek.management.document',
      'trip.details.days',
      'ek.academic.courses',
      'ek.ship.document.certificate',
    ]
    today_date = fields.Date.context_today(self)
    for model_name in models_to_update:
      self.env[model_name].search([]).write({'date_today': today_date})

  def get_data_m2m_data_return(self, m2m_field=None):
    """
    Creates a list of m2m data of reporting .
    :param m2m_field: A list of data that you have values in m2m .
    :return: List form data used for reports that need data in an orderly fashion ex. 1,2,3 a,b,c
    """
    if m2m_field:
      names = m2m_field.mapped('name')
      all_partner_names = ', '.join(names)
      return all_partner_names
    return 'N/A'

  def truncate_string(self, text, max_length):
    """
    Indicate the size of the field used for reporting.
    :param text: Set the object or field to be limited
    :param max_length: number of charactres needed for the Integer field.
    :return: The Field truncated with the characters specified in the parameter.
    """
    if not text:
      return ''
    if len(text) > max_length:
      return text[:max_length]
    else:
      return text

  def trade_report_number(self):
    records = self.shipping_trade_numbers_ids.filtered(lambda r: r.nunmer_print)
    if records:
      return records[-1].name
    else:
      return ''

  def date_return_today(self, tipo='datetime'):
    user_tz = pytz.timezone(
      self.env.context.get('tz') or self.env.user.tz or 'UTC'
    )
    if tipo == 'date':
      return str(fields.Date.today().strftime('%Y-%m-%d'))
    elif tipo == 'datetime':
      now_utc = fields.Datetime.now()
      now_user_tz = pytz.utc.localize(now_utc).astimezone(user_tz)

      return str(now_user_tz.strftime('%d/%m/%Y %H:%M:%S'))

  def format_dates_to_string(
    self, fecha_field=None, formato='dd-mmm-yyyy', tipo='date'
  ):
    """
    Indicate the size of the field used for reporting.
    :param fecha_field: Fecha field used for reporting.
    :param formato: formato used for reporting ex dd-mm-yyyy , ds-dd-mm-yyyy.
    :tipo: date or datetime
    :return: The Field fecha returned formated with the characters specified in the parameter.
    """
    user_tz = pytz.timezone(
      self.env.context.get('tz') or self.env.user.tz or 'UTC'
    )

    fecha = ''
    if self.date_start:
      fecha_field = self.date_start

    if not fecha_field:
      if tipo == 'date':
        fecha_field = fields.Date.today()
      elif tipo == 'datetime':
        fecha_field = fields.Datetime.now(tz=user_tz)

    dias_semana = [
      'Domingo',
      'Lunes',
      'Martes',
      'Miércoles',
      'Jueves',
      'Viernes',
      'Sábado',
    ]
    meses = [
      'Enero',
      'Febrero',
      'Marzo',
      'Abril',
      'Mayo',
      'Junio',
      'Julio',
      'Agosto',
      'Septiembre',
      'Octubre',
      'Noviembre',
      'Diciembre',
    ]
    if tipo == 'date':
      formatos = {
        'ds-dd-mm-yyyy': '{dia_semana}, {dia} de {mes} del {año}',
        'dd-mmm-yyyy': '{dia} de {mes} del {año}',
        'dd-mmm-yyyy-manual': '{dia} de {mes} del {año}',
        # agregar más formatos aquí
      }
      if formato not in formatos:
        return f"Formato '{formato}' no válido"

      dia_semana = dias_semana[fecha_field.weekday()]
      dia = fecha_field.day
      mes = meses[fecha_field.month - 1]
      año = fecha_field.year

      # Verificar si el campo manual_day existe y está activo
      if (
        hasattr(self, 'manual_day')
        and self.manual_day
        and formato in ['dd-mmm-yyyy', 'dd-mmm-yyyy-manual']
      ):
        dia = '_____'
      elif formato == 'dd-mmm-yyyy-manual':
        # Si no existe el campo manual_day, usar formato normal
        formato = 'dd-mmm-yyyy'

      return formatos[formato].format(
        dia_semana=dia_semana,
        dia=dia,
        mes=mes,
        año=año,
      )

    elif tipo == 'datetime':
      fecha = fecha_field.replace(tzinfo=pytz.utc).astimezone(user_tz)
      formatos = {
        'ds-dd-mm-yyyy-hh-mm': '{dia_semana}, {dia} de {mes} del {año} - {hora}H{min}',
        # agregar más formatos aquí
      }
      if formato not in formatos:
        return f"Formato '{formato}' no válido"

      dia_semana = dias_semana[fecha.weekday()]
      dia = fecha.day
      mes = meses[fecha.month - 1]
      año = fecha.year
      hora = fecha.hour
      min = str(fecha.minute).zfill(2)

      return formatos[formato].format(
        dia_semana=dia_semana, dia=dia, mes=mes, año=año, hora=hora, min=min
      )

  def update_field_values(
    self, object_model_id, fields_relation_id, fields_change_id, field_id
  ):
    target_model = object_model_id
    related_obj = getattr(object_model_id, fields_relation_id.name, None)
    related_records = getattr(related_obj, fields_change_id.name, None)

    if field_id.ttype == 'many2one':
      target_model.write({field_id.name: related_records.id})
    elif field_id.ttype == 'many2many':
      target_model.write({field_id.name: [(6, 0, related_records.ids)]})
    else:
      target_model.write({field_id.name: related_records})

  def datetime_false_return(self, date):
    if not date:
      return '-'
    return date.strftime('%d/%m/%Y  %H:%M:%S')

  def date_false_return(self, date):
    if not date:
      return '-'
    return date.strftime('%d/%m/%Y')

  def float_to_words(self, number):
    integer_part = int(number)
    decimal_part = round((number - integer_part) * 100)
    integer_words = num2words(integer_part, lang='es').upper()
    decimal_words = f'{decimal_part:02d}/100'
    result = f'{integer_words} CON {decimal_words}'
    return result
