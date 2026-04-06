import base64
import io
import logging

from odoo import _, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

try:
  import pandas as pd
except ImportError:
  _logger.warning('Pandas library not available. Excel import will not work.')
  pd = None


class EkCustomsImportWizard(models.TransientModel):
  _name = 'ek.customs.import.wizard'
  _description = 'Wizard: Importar Datos de Aduanas desde Excel'

  operation_request_id = fields.Many2one(
    'ek.operation.request',
    string='Operación',
    required=True,
    default=lambda self: self.env.context.get('active_id'),
  )

  excel_file = fields.Binary(
    string='Archivo Excel',
    required=True,
    help='Archivo Excel con los datos de Aduanas',
  )

  filename = fields.Char(string='Nombre del archivo')

  # Estadísticas de importación
  total_lines = fields.Integer(string='Total de líneas', readonly=True)
  imported_lines = fields.Integer(string='Líneas importadas', readonly=True)
  error_lines = fields.Integer(string='Líneas con error', readonly=True)

  import_log = fields.Text(string='Log de importación', readonly=True)

  def _safe_string(self, value, default=''):
    """Convierte valor a string de forma segura"""
    if pd.isna(value) or value is None:
      return default
    return str(value).strip()

  def _safe_float(self, value, default=0.0):
    """Convierte valor a float de forma segura"""
    if pd.isna(value) or value is None:
      return default
    try:
      return float(value)
    except (ValueError, TypeError):
      return default

  def _validate_excel_file(self, excel_data):
    """Valida que el archivo sea un Excel válido y no esté vacío"""
    try:
      excel_buffer = io.BytesIO(excel_data)

      # Intentar leer como Excel
      df = pd.read_excel(excel_buffer, engine='openpyxl')

      # Validar que no esté vacío
      if df.empty:
        raise UserError(
          _('El archivo Excel está vacío o no contiene datos válidos.')
        )

      return df

    except Exception as e:
      if 'not a valid Excel file' in str(e) or 'BadZipFile' in str(e):
        raise UserError(
          _(
            'El archivo seleccionado no es un archivo Excel válido (.xlsx). Asegúrese de seleccionar un archivo Excel en formato .xlsx'
          )
        )
      elif 'empty' in str(e).lower():
        raise UserError(
          _('El archivo Excel está vacío o no contiene datos válidos.')
        )
      else:
        raise UserError(_('Error al leer el archivo Excel: %s') % str(e))

  def import_excel_data(self):
    """Importar datos desde Excel"""
    if not pd:
      raise UserError(
        _(
          'La librería pandas no está disponible. Instale pandas para usar esta funcionalidad.'
        )
      )

    if not self.excel_file:
      raise UserError(_('Debe seleccionar un archivo Excel.'))

    try:
      # Decodificar el archivo
      excel_data = base64.b64decode(self.excel_file)

      # Validar archivo Excel
      df = self._validate_excel_file(excel_data)

      # Validar que las columnas requeridas existan (solo las 4 principales)
      required_columns = [
        'icl_pvdr_nm_01',  # H35. Proveedor ss
        'icl_item_inv_no',  # H34. Factura ss
        'icl_gds_desc_cn',  # H06. Descripción ss
        'icl_phsc_pck_ut_co',  # H18. Cantidad ss
      ]

      missing_columns = [
        col for col in required_columns if col not in df.columns
      ]
      if missing_columns:
        raise UserError(
          _('Faltan las siguientes columnas requeridas en el archivo Excel: %s')
          % ', '.join(missing_columns)
        )

      # Procesar datos
      log_messages = []
      imported_count = 0
      error_count = 0

      # Limpiar datos existentes si los hay
      existing_records = self.operation_request_id.customs_agent_data_ids
      if existing_records:
        existing_records.unlink()
        log_messages.append(
          f'Eliminados {len(existing_records)} registros existentes.'
        )

      # Procesar cada fila
      for index, row in df.iterrows():
        try:
          # Validar datos requeridos
          provider = self._safe_string(row.get('icl_pvdr_nm_01'))
          invoice = self._safe_string(row.get('icl_item_inv_no'))
          description = self._safe_string(row.get('icl_gds_desc_cn'))
          quantity = self._safe_float(row.get('icl_phsc_pck_ut_co'))

          # Validar que los campos requeridos no estén vacíos
          if not provider:
            raise ValueError('Proveedor (icl_pvdr_nm_01) es requerido')
          if not invoice:
            raise ValueError('Factura (icl_item_inv_no) es requerida')
          if not description:
            raise ValueError('Descripción (icl_gds_desc_cn) es requerida')
          if quantity <= 0:
            raise ValueError('Cantidad (icl_phsc_pck_ut_co) debe ser mayor a 0')

          # Crear registro con validaciones de tipo
          values = {
            'operation_request_id': self.operation_request_id.id,
            'icl_pvdr_nm_01': provider,
            'icl_item_inv_no': invoice,
            'icl_gds_desc_cn': description,
            'icl_phsc_pck_ut_co': quantity,
            # Campos opcionales - solo incluir si existen en el Excel
            'icl_hs_part_cd': self._safe_string(row.get('icl_hs_part_cd', ''))
            if 'icl_hs_part_cd' in df.columns
            else '',
            'icl_item_fobv_pr': self._safe_float(row.get('icl_item_fobv_pr', 0))
            if 'icl_item_fobv_pr' in df.columns
            else 0.0,
          }

          self.env['ek.customs.agent.data'].create(values)
          imported_count += 1

        except ValueError as ve:
          error_count += 1
          log_messages.append(
            f'Error de validación en fila {index + 2}: {str(ve)}'
          )
          _logger.warning(f'Error de validación en fila {index + 2}: {str(ve)}')
        except Exception as e:
          error_count += 1
          log_messages.append(f'Error en fila {index + 2}: {str(e)}')
          _logger.error(f'Error procesando fila {index + 2}: {str(e)}')

      # Actualizar estadísticas
      self.write(
        {
          'total_lines': len(df),
          'imported_lines': imported_count,
          'error_lines': error_count,
          'import_log': '\n'.join(log_messages)
          if log_messages
          else 'Importación completada sin errores.',
        }
      )

      # Mostrar mensaje de éxito
      message = f'Importación completada:\n- Total de líneas: {len(df)}\n- Importadas: {imported_count}\n- Errores: {error_count}. Cargando...'

      if error_count == 0:
        # Mostrar notificación de éxito y cerrar el wizard
        return {
          'type': 'ir.actions.client',
          'tag': 'display_notification',
          'params': {
            'title': _('Importación Exitosa'),
            'message': message,
            'type': 'success',
            'sticky': False,
            'next': {'type': 'ir.actions.act_window_close'},
          },
        }
      else:
        # Si hay errores, mostrar el wizard con los logs
        return {
          'type': 'ir.actions.act_window',
          'name': _('Resultado de la Importación'),
          'res_model': 'ek.customs.import.wizard',
          'view_mode': 'form',
          'res_id': self.id,
          'target': 'new',
          'context': self.env.context,
        }

    except Exception as e:
      _logger.error(f'Error en importación: {str(e)}')
      raise UserError(_('Error al procesar el archivo Excel: %s') % str(e))

  def action_clear_customs_data(self):
    """Limpiar todos los datos de aduanas"""
    existing_records = self.operation_request_id.customs_agent_data_ids
    if existing_records:
      existing_records.unlink()
      return {
        'type': 'ir.actions.client',
        'tag': 'display_notification',
        'params': {
          'title': _('Datos Eliminados'),
          'message': f'Se eliminaron {len(existing_records)} registros.',
          'type': 'success',
          'sticky': False,
        },
      }
    else:
      return {
        'type': 'ir.actions.client',
        'tag': 'display_notification',
        'params': {
          'title': _('Sin Datos'),
          'message': 'No hay datos para eliminar.',
          'type': 'info',
          'sticky': False,
        },
      }
