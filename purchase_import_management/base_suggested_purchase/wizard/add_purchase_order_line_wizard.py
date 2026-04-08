from odoo import fields, models, api,_
from odoo.exceptions import ValidationError


class add_purchase_order_line_wizard(models.TransientModel):
    _name = 'ek.suggest.add.purchase.order.line.wizard'
    _description = _('Agregar linea de sugerido a pedido de compra')

    kit_id = fields.Many2one(
        comodel_name='ek.suggested.purchase.kit',
        string=_('Kit'),
        required=False)

    partner_id = fields.Many2one(
        comodel_name='res.partner',
        string=_('Proveedor'),
        required=False)

    order_id = fields.Many2one(
        comodel_name='purchase.order',
        string=_('Pedido de Compra'),
        required=False)

    delete_suggest_line = fields.Boolean(
        string=_('Eliminar lineas del sugerido'),
        required=False, default=True)

    date_order = fields.Datetime(
        string=_('Fecha límite de pedido'),
        required=False)
    type = fields.Selection(
        string=_('Acción'),
        selection=[('one', _('Generar orden de compra')),
                   ('multi', _('Generar ordenes masivas')),
                   ('add', _('Asignar a orden existente'))],
        required=False, default='multi')
        


    def action_add_purchase(self):
        for rec in self:
            MethodWanted = 'generate_order_%s' % rec.type
            active_model = self._context.get('active_model')

            if active_model == 'ek.suggested.purchase.kit':
                if rec.kit_id:
                    lines = rec.kit_id.line_ids.filtered(lambda a: a.qty_suggested > 0)
                else:
                    raise ValidationError(_("No ha seleccionado un kit para la generación de la orden de compra"))
            elif active_model == 'res.partner':
                if rec.partner_id:
                    lines = self.env['ek.suggested.purchase'].search([('partner_id','=',rec.partner_id.id), ('qty_suggested','>',0)])
                else:
                    raise ValidationError(_("No ha seleccionado un proveedor para la generación de la orden de compra"))
            elif active_model == 'ek.suggested.purchase':
                active_ids = self._context.get('active_ids')
                lines = self.env['ek.suggested.purchase'].search([('id', 'in', active_ids), ('qty_suggested','>',0)])

            if not lines:
                raise ValidationError(_("No ha seleccionado ninguna linea de sugerido para asignar/generar ordenes de comrpa o las líneas seleccionadas no poseen valor sugerido"))

            order_ids = getattr(rec, MethodWanted)(lines)

            if order_ids and rec.delete_suggest_line:
                lines.sudo().unlink()

            if self._context.get('open_purchase', False):
                return self.action_view_purchase(order_ids)
            return {'type': 'ir.actions.act_window_close'}



    def generate_order_one(self,lines):
        self.ensure_one()
        orden_ids = []
        if not self.partner_id:
            raise ValidationError(_("Debe seleccionar el proveedor para generar la orden de compra"))

        order = self.env['purchase.order'].create({
            'partner_id': self.partner_id.id,
            'date_order': self.order_id and self.order_id.date_order or self.date_order,
            'order_line': self._prerare_consolidate_items_line(lines)
        })
        if order:
            orden_ids.append(order.id)
        return orden_ids and orden_ids or False

    def generate_order_multi(self,lines):
        lines = lines.filtered(lambda a: a.partner_id != False)
        self.ensure_one()
        orden_ids = []
        provider_grouping = {}
        for line in lines:
            if line.partner_id.id not in provider_grouping:
                provider_grouping[line.partner_id.id] = []

            provider_grouping[line.partner_id.id].append(line)

        for partner_id, xlines in provider_grouping.items():
            order = self.env['purchase.order'].create({
                'partner_id': partner_id,
                'date_order': self.date_order,
                'order_line': self._prerare_consolidate_items_line(xlines)
            })

            if order:
                orden_ids.append(order.id)

        return orden_ids and orden_ids or False

    def generate_order_add(self,lines):
        self.ensure_one()
        orden_ids = []
        if not self.order_id:
            raise ValidationError(_("Debe seleccionar la orden de compra para agregar los items sugeridos"))


        items = self._prepare_exist_consolidate_line(lines, self.order_id.order_line)
        if items:
            self.order_id.update({
                'order_line': items
            })

        if self.order_id:
            orden_ids.append(self.order_id.id)
        return orden_ids and orden_ids or False


    def _prerare_consolidate_items_line(self, lines):
        _items = []
        inter_line = {}
        for line in lines:
             if not line.product_id.id in inter_line:
                 inter_line[line.product_id.id] = {
                     'product_id': line.product_id.id,
                     'product_uom': line.product_id.uom_po_id.id,
                     'price_unit': line.cost,
                     'product_qty': 0
                 }

             inter_line[line.product_id.id]['product_qty'] += line.qty_suggested

        for key, value in inter_line.items():
            _items.append((0,0,value))

        return _items

    def _prepare_exist_consolidate_line(self, lines, order_lines):
        for line in lines:
            _unique_lines = []
            po_line = order_lines.filtered(lambda a: a.product_id.id == line.product_id.id)
            if po_line:
                po_line = po_line[0]
                po_line.update({
                    'product_qty': po_line.product_qty + line.qty_suggested
                })
            else:
                _unique_lines.append(line)

        return self._prerare_consolidate_items_line(_unique_lines)


    def action_view_purchase(self,order_ids):
        action = self.env["ir.actions.actions"]._for_xml_id("purchase.purchase_rfq")
        if len(order_ids) > 1:
            action['domain'] = [('id', 'in', order_ids)]
        elif len(order_ids) == 1:
            form_view = [(self.env.ref('purchase.purchase_order_form').id, 'form')]
            if 'views' in action:
                action['views'] = form_view + [(state,view) for state,view in action['views'] if view != 'form']
            else:
                action['views'] = form_view
            action['res_id'] = order_ids[0]
        else:
            action = {'type': 'ir.actions.act_window_close'}

        return action
