from odoo import fields, models, api,_
from datetime import datetime, timedelta
from odoo.tools import float_round
from odoo.exceptions import ValidationError
import calendar
_MONTH=['',_("Enero"),_('Febrero'),_('Marzo'),_('Abril'),_('Mayo'),_('Junio'),_('Julio'),_('Agosto'),_('Septiembre'),
        _('Octubre'),_('Noviembre'),_('Diciembre')]

class SuggestedPurchase(models.Model):
    _inherit = 'ek.suggested.purchase'


    #Todo [VAA] - Ventas del año actual (Todas las ventas del producto en cuestión en un año calendario
    # sean normales o especiales)
    #Todo [VAP] - Ventas del año pasado (Todas las ventas del producto en cuestión sean normales o especiales del año anterior)
    #Todo [VMP] - Ventas del mes a reponer del año pasado  (Todas las ventas del producto en cuestión sean normales o especiales
    # del mes del año anterior perteneciente al mes que se quiere reponer)
    def get_sale_yearly_and_monthly_old(self, products=False, year=False, month=False,type=False, external_data={}, date=False):
        _year = year
        _old_year = year - 1 #2022
        attrib = 'sale_%s' % month
        _year_init_sale = year+1
        _month_init_sale = 12
        date_init = self.env['ir.config_parameter'].sudo().get_param('suggest.history_date_init_sales', False)
        if date_init:
            date_init = fields.Date.to_date(date_init)
            #01/03/2023
            _year_init_sale = date_init.year #2023
            _month_init_sale = date_init.month #03

        month_1 = month - 1
        attrib_1 = 'sale_%s' % month_1
        for rec in self.env['ek.suggested.purchase.history.master'].search([('sales_year', '=', _old_year)]):
            if _year_init_sale and _old_year > _year_init_sale:
                continue

            _min_month_data = False
            _max_month_data = False
            product_id = rec.product_id.id
            if product_id not in external_data:
                external_data[product_id] = {
                    'yearly_qty': 0.00,
                    'previous_yearly_qty': 0.00,
                    'monthly_qty': 0.00,
                    'previous_monthly_qty': 0.00,
                    'last_date': False,
                    'previous_date': False,
                    'sales_1_month': 0.00
                }

            if _year_init_sale == _old_year:
                external_data[product_id]['previous_yearly_qty'] += rec.get_total_up_to_specific_month(_month_init_sale)
            elif _year_init_sale > _old_year:
                external_data[product_id]['previous_yearly_qty'] += rec.sale_total

            if month and hasattr(rec, attrib) and (_year_init_sale > _old_year or (_year_init_sale == _old_year and month <= _month_init_sale)):
                external_data[product_id]['previous_monthly_qty'] += getattr(rec, attrib)


            for i in range(1, 13):
                attrib = 'sale_%s' % i
                if hasattr(rec, attrib):
                    if getattr(rec, attrib) > 0:
                        if not _min_month_data:
                            _min_month_data = i
                        _max_month_data = i

            if _min_month_data:
                external_data[product_id].update({
                    'previous_date': fields.Date.to_date('%s-%s-01' % (_old_year,_min_month_data)),
                    'last_date': fields.Date.to_date('%s-%s-%s' % (_old_year,_max_month_data,calendar.monthrange(_old_year,_max_month_data)[1])),
                })

        for rec in self.env['ek.suggested.purchase.history.master'].search([('sales_year', '<=',_year)]):
            if _year_init_sale and _year > _year_init_sale:
                continue

            _min_month_data = False
            _max_month_data = False
            product_id = rec.product_id.id
            if product_id not in external_data:
                external_data[product_id] = {
                    'yearly_qty': 0.00,
                    'previous_yearly_qty': 0.00,
                    'monthly_qty': 0.00,
                    'previous_monthly_qty': 0.00,
                    'last_date': False,
                    'previous_date': False,
                    'sales_1_month': 0.00
                }

            if _year_init_sale == _year:
                external_data[product_id]['yearly_qty'] += rec.get_total_up_to_specific_month(_month_init_sale)
            elif _year_init_sale > _year:
                external_data[product_id]['yearly_qty'] += rec.sale_total

            if month and hasattr(rec, attrib) and (_year_init_sale > _year or (_year_init_sale == _year and month <= _month_init_sale)):
                external_data[product_id]['monthly_qty'] += getattr(rec, attrib)

            if month_1 and hasattr(rec, attrib_1) and (_year_init_sale > _year or (_year_init_sale == _year and month <= _month_init_sale)):
                external_data[product_id]['sales_1_month'] += getattr(rec, attrib_1)


            for i in range(1, 13):
                attrib = 'sale_%s' % i
                if hasattr(rec, attrib):
                    if getattr(rec, attrib) > 0:
                        if not _min_month_data:
                            _min_month_data = i
                        _max_month_data = i

            if _min_month_data:
                if not external_data[product_id].get('previous_date',False):
                    external_data[product_id]['previous_date'] = fields.Date.to_date('%s-%s-01' % (_year,_min_month_data))

                external_data[product_id].update({
                    'last_date': fields.Date.to_date('%s-%s-%s' % (_old_year,_max_month_data,calendar.monthrange(_year,_max_month_data)[1])),
                })
                    
        return super(SuggestedPurchase, self).get_sale_yearly_and_monthly(products=products, year=year, month=month,type=type, external_data=external_data, date=date)

        # Todo [VAA] - Ventas del año actual (Todas las ventas del producto en cuestión en un año calendario
        # sean normales o especiales)
        # Todo [VAP] - Ventas del año pasado (Todas las ventas del producto en cuestión sean normales o especiales del año anterior)
        # Todo [VMP] - Ventas del mes a reponer del año pasado  (Todas las ventas del producto en cuestión sean normales o especiales
        # del mes del año anterior perteneciente al mes que se quiere reponer)

    def get_sale_yearly_and_monthly(self, products=False, year=False, month=False, type=False, external_data={},
                                        date=False,type_sale_qty='product_uom_qty'):

        _init_master_date = (date - timedelta(days=365))
        _end_master_date = date
        _year = year
        _old_year = year - 1  # 2022
        attrib = 'sale_%s' % month
        _year_init_sale = year + 1
        _month_init_sale = 12
        date_init = self.env['ir.config_parameter'].sudo().get_param('suggest.history_date_init_sales', False)
        if date_init:
            date_init = fields.Date.to_date(date_init)
            # 01/03/2023
            _year_init_sale = date_init.year  # 2023
            _month_init_sale = date_init.month  # 03

        month_1 = month - 1
        attrib_1 = 'sale_%s' % month_1
        for rec in self.env['ek.suggested.purchase.history.master'].search([('sales_year', '=', _old_year)]):
            if _year_init_sale and _old_year > _year_init_sale:
                continue

            _min_month_data = False
            _max_month_data = False
            product_id = rec.product_id.id

            if product_id not in external_data:
                external_data[product_id] = {
                    'yearly_qty': 0.00,
                    'previous_yearly_qty': 0.00,
                    'monthly_qty': 0.00,
                    'previous_monthly_qty': 0.00,
                    'last_date': False,
                    'previous_date': False,
                    'sales_1_month': 0.00
                }

            if _year_init_sale == _old_year:
                external_data[product_id]['previous_yearly_qty'] += rec.get_total_up_to_specific_month(
                    _month_init_sale)
            elif _year_init_sale > _old_year:
                external_data[product_id]['previous_yearly_qty'] += rec.sale_total

            if month and hasattr(rec, attrib) and (
                    _year_init_sale > _old_year or (_year_init_sale == _old_year and month <= _month_init_sale)):
                external_data[product_id]['previous_monthly_qty'] += getattr(rec, attrib)

            for i in range(1, 13):
                attrib_range = 'sale_%s' % i
                if hasattr(rec, attrib_range):
                    if getattr(rec, attrib_range) > 0:
                        if not _min_month_data:
                            _min_month_data = i
                        _max_month_data = i

            if _min_month_data:
                external_data[product_id].update({
                    'previous_date': fields.Date.to_date('%s-%s-01' % (_old_year, _min_month_data)),
                    'last_date': fields.Date.to_date('%s-%s-%s' % (
                    _old_year, _max_month_data, calendar.monthrange(_old_year, _max_month_data)[1])),
                })

        for rec in self.env['ek.suggested.purchase.history.master'].search([('sales_year', 'in', [_init_master_date.year, _end_master_date.year])]):
            if _year_init_sale and _year > _year_init_sale:
                continue

            _min_month_data = False
            _max_month_data = False
            product_id = rec.product_id.id
            if product_id not in external_data:
                external_data[product_id] = {
                    'yearly_qty': 0.00,
                    'previous_yearly_qty': 0.00,
                    'monthly_qty': 0.00,
                    'previous_monthly_qty': 0.00,
                    'last_date': False,
                    'previous_date': False,
                    'sales_1_month': 0.00
                }

            if _init_master_date.year == _end_master_date.year:
                external_data[product_id]['yearly_qty'] += rec.sale_total
            else:
                if rec.sales_year == _init_master_date.year:
                    external_data[product_id]['yearly_qty'] += rec.get_total_specific_month(_init_master_date.month+1,12)
                elif rec.sales_year == _end_master_date.year:
                    external_data[product_id]['yearly_qty'] += rec.get_total_specific_month(1,_end_master_date.month)

            # if month and hasattr(rec, attrib) and (
            #         _year_init_sale > _year or (_year_init_sale == _year and month <= _month_init_sale)):
            #     external_data[product_id]['monthly_qty'] += getattr(rec, attrib)

            if month_1 and hasattr(rec, attrib_1) and (
                    _year_init_sale > _year or (_year_init_sale == _year and month <= _month_init_sale)):
                external_data[product_id]['sales_1_month'] += getattr(rec, attrib_1)

            for i in range(1, 13):
                attrib = 'sale_%s' % i
                if hasattr(rec, attrib):
                    if getattr(rec, attrib) > 0:
                        if not _min_month_data:
                            _min_month_data = i
                        _max_month_data = i

            if _min_month_data:
                if not external_data[product_id].get('previous_date', False):
                    external_data[product_id]['previous_date'] = fields.Date.to_date(
                        '%s-%s-01' % (_year, _min_month_data))

                external_data[product_id].update({
                    'last_date': fields.Date.to_date(
                        '%s-%s-%s' % (_old_year, _max_month_data, calendar.monthrange(_year, _max_month_data)[1])),
                })

        return super(SuggestedPurchase, self).get_sale_yearly_and_monthly(products=products, year=year, month=month,
                                                                              type=type, external_data=external_data,
                                                                      date=date,type_sale_qty=type_sale_qty)