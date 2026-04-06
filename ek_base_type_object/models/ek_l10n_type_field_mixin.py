from odoo import _, api, fields, models
from odoo.exceptions import UserError

class EkL10nTypeFieldMixin(models.Model):
    _name = 'ek.l10n.type.field.mixin'
    _description = _("Type Generic Field")
    _order = 'sequence'

    @api.model
    def _selection_target_model(self):
        return [(model.model, model.name) for model in self.env['ir.model'].sudo().search([])]

    sequence = fields.Integer(string='Sequence')
    init_float = fields.Float(string='Default Float')
    init_integer = fields.Integer(string='Default Integer')
    init_selection = fields.Many2one(string='Default Selection',comodel_name="ir.model.fields.selection")
    
    init_text = fields.Char(string='Default Text')
    init_date = fields.Date(string='Default Date')
    init_datetime = fields.Datetime(string='Default Datetime')
    init_many2one = fields.Reference(string='Default Many2one',selection='_selection_target_model')
    apply_default = fields.Boolean(string='Apply Default Value')

    object_model_id  = fields.Char(related='type_model_id.model')

    field_id = fields.Many2one(
        'ir.model.fields',
        string=_('Field'),
        domain="[('readonly','=',False),('model_id.model', '=', object_model_id),('name', 'not in', ['l10n_ec_check_model_type','activity_ids','activity_summary','activity_type_id','campaign_id','medium_id','message_follower_ids','message_ids','message_partner_ids','rating_ids','source_id','type_id','website_message_ids','state_id','name','parent_id','child_ids','stage_id','user_id','assign_date','assign_hours','done_date','done_hours','confirmed_hours','active','company_id','date_last_stage_update','oldest_unanswered_customer_message_date','block_type'])]",
        ondelete='cascade',
        
        required=True)

    has_required = fields.Boolean(string="Required",default=False)

    dependecy_field = fields.Boolean(string="Required for Depandency",default=False)

    dependecy_field_id = fields.Many2one(
        'ir.model.fields',
        string=_('Dependency Field'),
        domain="[('readonly','=',False),('model_id.model', '=', object_model_id)]",
        ondelete='cascade',
        
        required=False)
    
    type_model_id = fields.Many2one(
        comodel_name='ek.l10n.type.model.mixin',
        string=_('Type Model'),   
        copy=True,     
        required=True)

    definition_domain = fields.Char("Definition Domain")

    model = fields.Char("Model", related="field_id.model_id.model")
    relation = fields.Char("Model", related="field_id.relation")
    ttype = fields.Selection("Model", related="field_id.ttype")

    group_name = fields.Char(string='Group')
    label = fields.Char(string='Label')
    help = fields.Char(string='Help')
    placeholder = fields.Char(string='Placeholder')
    widget_id = fields.Many2one(comodel_name="ek.l10n.type.widget.mixin", string="Widget", domain="[('ttype', '=', ttype)]")

    stage_ids = fields.Many2many(
        'ek.l10n.stages.mixin', relation='ek_l10n_type_field_mixin_stage_rel', string='Read Only For Stages',
        default=lambda self: self.type_model_id.stage_ids,
        domain="[('type_ids','in',type_model_id)]",
        help=_("Stages where this field is read only"))

    required_stage_ids = fields.Many2many(
        'ek.l10n.stages.mixin', relation='ek_l10n_type_field_mixin_required_stage_rel', string='Required For Stages',
        default=lambda self: self.type_model_id.stage_ids,
        domain="[('type_ids','in',type_model_id)]",
        help=_("Stages where this field is required"))

    invisible_stage_ids = fields.Many2many(
        'ek.l10n.stages.mixin', relation='ek_l10n_type_field_mixin_invisible_stage_rel', string='Invisible For Stages',
        default=lambda self: self.type_model_id.stage_ids,
        domain="[('type_ids','in',type_model_id)]",
        help=_("Stages where this field is invisible"))

    @api.onchange("field_id","apply_default")
    def onchange_field_id(self):
        for field in self:
            if field.apply_default:
                if field.field_id and field.field_id.ttype == 'many2one':
                    id = self.env[field.field_id.relation].sudo().search([],limit=1)
                    field.init_many2one = '%s,%s' % (field.field_id.relation, id and id.id or 0)
                else:
                    field.init_many2one = False
            else:
                for field_name in self._fields.keys():
                    if "init_" in field_name:
                        self[field_name] = False

    def duplicate(self, default=None):
        return super(EkL10nTypeFieldMixin, self.with_context(duplicating=True)).duplicate(default=default)

    @api.constrains('field_id', 'stage_ids', 'required_stage_ids', 'invisible_stage_ids')
    def _check_field_id(self):
        for record in self:
            if self.env.context.get('duplicating', True):
                continue
            if record.field_id and record.type_model_id and record.field_id.model_id.model != record.type_model_id.model:
                raise UserError(_("Field and Type Model must be of the same model"))
            if record.stage_ids and record.type_model_id and not record.type_model_id.stage_ids:
                raise UserError(_("Type Model must have stages"))
            if record.required_stage_ids and record.type_model_id and not record.type_model_id.stage_ids:
                raise UserError(_("Type Model must have required stages"))
            if record.invisible_stage_ids and record.type_model_id and not record.type_model_id.stage_ids:
                raise UserError(_("Type Model must have invisible stages"))
            
            if record.has_required and record.required_stage_ids:
                invisible_stages = set(record.invisible_stage_ids.ids)
                read_only_stages = set(record.stage_ids.ids)

                for stage in record.required_stage_ids:
                    if stage.id in invisible_stages or stage.id in read_only_stages:
                        raise UserError(_("Field %s can not be required for stage %s because it is invisible or read only for that stage") % (record.field_id.field_description, stage.name))
                
                


    _sql_constraints = [
        ('unique_field_type_id', 'unique(field_id,type_model_id)', _('Field and Type Model must be unique')),
    ]