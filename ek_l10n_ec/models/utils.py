# -*- coding: utf-8 -*-

import requests


tipoDocumento = {
    '01': '01',
    '04': '04',
    '03': '03',
    '05': '05',
    '06': '06',
    '07': '07',
    '18': '01',
    False: '01'
}

tipoIdentificacion = {
    'ruc': '04',
    'cedula': '05',
    'pasaporte': '06',
    'venta_consumidor_final': '07',
    'identificacion_exterior': '08',
    'placa': '09',
    '04': '04',
    '05': '05',
    '06': '06',
    '07': '07',
    '08': '08',
    '09': '09',
}

codigoImpuesto = {
    'vat': '2',
    'vat0': '2',
    'ice': '3',
    'other': '5',
    'irbpnr': '5'
}

codigoImpuestoRetencion = {
    'ret_ir': '1',
    'ret_vat_b': '2',
    'ret_vat_srv': '2',
    'ice': '3',
}

tarifaImpuesto = {
    'vat0': '0',
    'vat': '2',
    'novat': '6',
    'other': '7',
}

monedas = {
    'USD': 'DOLAR',
    'EUR': 'EURO'
}
