# -*- coding: utf-8 -*-
##############################################################################
#    Sistema FINAMSYS
#    Copyright (C) 2019-Today Ekuasoft S.A All Rights Reserved
#
#    Collaborators of this module:
#    Coded by: Cristhian Luzon <@cristhian_70>
#    Planifyied by: Yordany Oliva
#   This project is mantained by Ekuasoft Group Solutions
##############################################################################
from odoo import fields, models, api
from datetime import datetime as dt,datetime
from datetime import timedelta
from dateutil.relativedelta import relativedelta


class import_sheet_parser(models.AbstractModel):
    _name = "ek.base.tools"
    _description = "base tools"

    def replace_fix_chars(self,texto):
        code = texto
        special = [[u'%', ' '], [u'º', ' '], [u'°', ' '],
                   [u'Ñ', 'NN'], [u'ñ', 'nn'], [u'&', '&amp;'],
                   [u'á', 'a'], [u'é', 'e'],
                   [u'í', 'i'],
                   [u'ó', 'o'],
                   [u'ú', 'u'],
                   [u'Á', 'A'],
                   [u'É', 'E'],
                   [u'Í', 'I'],
                   [u'Ó', 'O'],
                   [u'Ú', 'U'],
                   [u'Ü', 'U'],
                   [u'ü', 'u'],
                   [u'Ü', 'U'],
                   [u'"', ' '],
                   [u"'", ' '],
                   [u"\n", ''],
                   [u"\\n", ''],
                   [u"\a", ''],
                   ["-", ''],
                   [",", ''],
                   [".", ''],
                   [u"\a", ''],
                   [u"\b", ''],
                   [u"\f", ''],
                   [u"\r", ''],
                   [u"\t", ''],
                   [u"\v", ''],
                   [u"", ''],
                   [u"", ''],
                   [u'á', 'a'], [u'à', 'a'], [u'ä', 'a'], [u'â', 'a'], [u'Á', 'A'], [u'À', 'A'],
                   [u'Ä', 'A'], [u'Â', 'A'],
                   [u'é', 'e'], [u'è', 'e'], [u'ë', 'e'], [u'ê', 'e'], [u'É', 'E'], [u'È', 'E'],
                   [u'Ë', 'E'], [u'Ê', 'E'],
                   [u'í', 'i'], [u'ì', 'i'], [u'ï', 'i'], [u'î', 'i'], [u'Í', 'I'], [u'Ì', 'I'],
                   [u'Ï', 'I'], [u'Î', 'I'],
                   [u'ó', 'o'], [u'ò', 'o'], [u'ö', 'o'], [u'ô', 'o'], [u'Ó', 'O'], [u'Ò', 'O'],
                   [u'Ö', 'O'], [u'Ô', 'O'],
                   [u'ú', 'u'], [u'ù', 'u'], [u'ü', 'u'], [u'û', 'u'], [u'Ú', 'U'], [u'Ù', 'U'],
                   [u'Ü', 'U'], [u'Û', 'U'],
                   [u'ñ', 'n'], [u'Ñ', 'N'], [u'/', '-'], [u'º', ''], [u'´', '']
                   ]
        if code:
            for f, r in special:
                code = code.replace(f, r)


        return code

    def generate_msj_log(self,name_proceso,logs):
        head = "PROCESO: %s" % (name_proceso)
        mensaje = "<b>" + head + "</b><ul>"
        for tt in logs:
            mensaje += "[%s]" % (tt)
        mensaje += "</ul>"
        return mensaje

    def get_pre_parameterized_values(self, values):
        """Converts a list of variables into comma-separated question marks, used for parameterization

        Args:
            values (list): Any list

        Returns:
            str: Example: '?, ?, ?, ?' etc
        """
        try:
            return ', '.join(list(map(lambda x: x, values)))
        except Exception as e:
            raise Exception('get_pre_parameterized_values({}): Exception occurred: {}'
                            .format(str(values), str(e)))

    def to_float(self, value):
        '''
        convierte a float si el dato
        :param value: campo a convertir
        :return: si todo es ok devuelve valor convertido si existe error devuelve 0
        '''
        try:
            a = float(value)
            return a
        except:
            return 0

    def to_integer(self, value):
        '''
        convierte a int si el dato
        :param value: campo a convertir
        :return: si todo es ok devuelve valor convertido si existe error devuelve 0
        '''
        try:
            a = int(value)
            return a
        except:
            return 0

    def to_datetime(self,value,formato):
        try:
            return dt.strptime(value, formato)
        except ValueError:
            return False

    def get_header(self, data):
        # we ensure that we do not try to encode none or bool
        list_head = []
        for c, val_c in sorted(data.items(), key=lambda kv: kv[0].isdigit() and int(kv[0]) or kv[0]):
            list_head.append(val_c['name'])
        return list_head

    def get_data(self, field, data):
        '''
        Desde un diccionario obtiene los valores de un field_model odoo
        :param field: campo odoo
        :param data: diccionario con campo field=nombre en odoo
        :return: diccionario convertido a values
        '''
        res_data = {}
        for c, val_c in sorted(data.items(), key=lambda kv: kv[0].isdigit() and int(kv[0]) or kv[0]):
            field_name = val_c['field']
            field_type = field._fields[field_name].type
            if field_type == 'many2one':
                value = getattr(field, field_name).display_name or ''
            if field_type == 'char':
                value = getattr(field, field_name) or ''
            if field_type == 'selection':
                value = getattr(field, field_name)
            res_data.update({field_name: value,
                             })
        return res_data

    def convert_datetime_iso8589(self,date_in):
        '''
        COnversion de Fecha a Formato ISO
        :param date_in: Fecha en formato DateTime
        :return: FORMATO: YYYYMMDDHH24MISS
        '''
        timestamp = date_in
        return timestamp.replace('-', '').replace(' ', '').replace(':', '')

    def convert_iso8589_date(self,date_in):
        '''
        COnversion de Fecha a Formato ISO
        :param date_in: Fecha en formato DateTime
        :return: FORMATO: YYYYMMDD
        '''

        val = date_in[0:4]+'-'+date_in[4:6]+'-'+date_in[6:]
        return val


    def convert_amount_iso8589(self,amount_in):
        '''
        Valor que el abonado cancela en el momento de pagar su factura, de los cuales los 2 últimos dígitos
        son los decimales
        Pago: 23.36

        :param amount_in: Formato Float con dos decimales
        :return: FORMATO: 000000002336
        '''
        amount_in = "{0:.2f}".format(amount_in)
        return str(amount_in).replace('.','').zfill(12)

    def convert_iso8589_amount(self,amount_in,len_value=False):
        '''
        Valor que el abonado cancela en el momento de pagar su factura, de los cuales los 2 últimos dígitos
        son los decimales

        :param amount_in: 000000002336
        :param len_value: Longitud del campo, si es false el sistema calcula la logitud de variable amount_in
        :return: FORMATO: Formato Float con dos decimales
        '''
        if not len_value:
            len_value = len(amount_in)
        val = float(amount_in[:len_value - 2] + '.' + amount_in[-2:])
        return val

    def convert_string_iso8589(self,value,fill):
        '''
        Son completados con espacios a la derecha hasta completar la longitud X
        :param value: Valor string a convertir
        :param fill: Número de espacios a rellenar
        :return: FORMATO: "CRISTHIAN       "
        '''
        res = value.ljust(fill)
        return res
