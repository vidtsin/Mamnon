# -*- coding: utf-8 -*-
##############################################################################
#
# OdooBro - odoobro.contact@gmail.com
#
##############################################################################

from datetime import datetime, timedelta
from odoo import api, fields, models, _
from odoo.addons import decimal_precision as dp
from odoo.tools import DEFAULT_SERVER_DATE_FORMAT as DF
from odoo.exceptions import Warning
from odoo.tools.translate import _


class CardBox(models.Model):
    _name = 'card.box'
    _description = 'Card Box'

    name = fields.Char('name')
    code = fields.Char('Code')

class CardCard(models.Model):
    _name = 'card.card'
    _inherit = ['portal.mixin', 'mail.thread', 'mail.activity.mixin']
    _description = 'Loyalty Card'
    _order = 'name'

    name = fields.Char(string='Card Number', default='/', track_visibility='always')
    type_id = fields.Many2one('card.type', 'Type', inverse='_update_pricelist_discount',
        required=1, track_visibility='always')
    type = fields.Selection([('physical','Physical'),('virtual','Virtual')], string="Card Type")
    partner_id = fields.Many2one('res.partner', 'Customer', track_visibility='always')
    creation_date = fields.Date('Creation Date', track_visibility='always')
    activate_date = fields.Date('Activated Date', track_visibility='always')
    expiry_date = fields.Date('Expiry Date', track_visibility='always')
    point_in_period = fields.Float('Points in Period', digits=dp.get_precision('Discount'), track_visibility='always')
    upgrade_type_id = fields.Many2one(
        string='Upgrade Card Type',
        comodel_name='card.type',
        compute="_check_upgrade",
        store=True, track_visibility='always')
    total_point = fields.Float(
        string='Total Points',
        digits=dp.get_precision('Discount'), track_visibility='always')
    last_period_total_point = fields.Float(
        string='Last Period Total Points',
        compute="_get_last_period_total_point",
        digits=dp.get_precision('Discount'), track_visibility='always')
    is_expired = fields.Boolean(
        string='Expired?',
        compute='_is_expired', track_visibility='always')
    noupdate_card = fields.Boolean(
        string='Noupdate Card?', track_visibility='always')
    state = fields.Selection([('draft','Draft'),
                            ('sent_to_printing','Sent to Printing'),
                            ('available_to_distribution','Available'),
                            ('at_merchants','At Merchants'),
                            ('active','Active'),
                            ('terminated','Terminated'),
                            ('lost_or_stolen','Lost Or Stolen'),
                            ('replaced','Replaced')], default='draft', track_visibility='always', index=True)
    card_expected_date = fields.Date(
        string='Expected Date (for receiving Hard Card)', track_visibility='always',)
    history_ids = fields.One2many(
        string='History',
        comodel_name='card.history',
        inverse_name='card_id')
    pricelist_id = fields.Many2one(
        comodel_name='product.pricelist',
        string='Pricelist',
        readonly=True, 
        help="Pricelist for the customer of this card.", track_visibility='always',)

    barcode = fields.Char(
        string='Barcode', track_visibility='always',)

    merchant_id = fields.Many2one('res.partner',string="Merchant", track_visibility='always')
    membership_id = fields.Many2one('card.membership',string="Membership", track_visibility='always')
    box_id = fields.Many2one('card.box',string="Card Box", track_visibility='always')
    purchase_id = fields.Many2one('purchase.order',string="Purchase", track_visibility='always')    
    #Linked the card to move line to manage serial no tracking
    move_line_id = fields.Many2one('stock.move.line', track_visibility='always')
    ref_name = fields.Char(string='Ref. Name',)

    _sql_constraints = [
        ('barcode', 'unique(barcode)', _('Barcode must be unique.')),
        ('partner_uniuq', 'unique (partner_id)', "Customer must be unique"),
    ]

    @api.model
    def create(self, val):
        rec = super(CardCard, self).create(val)
        if rec.ref_name == False:
            rec.ref_name = self.env['ir.sequence'].next_by_code('card.card') or _('New')
        return rec
    
    @api.multi
    def action_quotation_view(self):
        return {
                'name': _('Card Quotation'),
                'view_type': 'form',
                'view_mode': 'form',
                'res_model': 'purchase.order',
                'res_id':self.purchase_id.id,
                'type': 'ir.actions.act_window',
                }

    @api.model
    def name_search(self, name='', args=None, operator='ilike', limit=100):
        args = list(args or [])
        if not (name == '' and operator == 'ilike'):
            args += ['|', ('barcode', operator, name)]
        return super(CardCard, self).name_search(name, args, operator, limit)

    @api.multi
    @api.depends('point_in_period')
    def _check_upgrade(self, points=None):
        CardType = self.env['card.type']
        for r in self:
            if not points:
                points = r.point_in_period
            args = [('categ_id', '=', r.type_id.categ_id.id)]
            type = CardType.search(args, limit=1)
            if type:
                r.upgrade_type_id = type.id

    @api.multi
    def _get_last_period_total_point(self):
        for record in self:
            if record.history_ids:
                record.last_period_total_point = \
                    record.history_ids[0].total_point
            else:
                record.last_period_total_point = 0.00

    @api.multi
    def _is_expired(self):
        tday = fields.Date.context_today(self)
        for record in self:
            is_expired = False
            if not record.expiry_date:
                continue
            if tday > record.expiry_date:
                is_expired = True
            record.is_expired = is_expired

    @api.multi
    def action_sent_print(self):
        self.write({'state':'sent_to_printing'})

    @api.multi
    def action_available_distribution(self):
        self.write({'state':'available_to_distribution'})

    @api.multi
    def action_merchants(self):
        self.write({'state':'at_merchants'})

    @api.multi
    def action_active(self):
        for r in self:
            if not r.upgrade_type_id:
                continue
            r.type_id = r.upgrade_type_id.id
            active_date = fields.Date.context_today(r)
            expiry_date = \
                r.upgrade_type_id.period_id.get_period_end_date(active_date)
            vals = {'activate_date': active_date,
                'expiry_date': expiry_date,
                'point_in_period': 0.00,
                'state':'active'}
            r.write(vals)
            r.add_history()

    @api.multi
    def action_terminated(self):
        self.write({'state':'terminated'})
        self.add_history()

    @api.multi
    def action_lost_or_stolen(self):
        self.write({'state':'lost_or_stolen'})
        self.add_history()


    @api.multi
    def add_history(self, status=None):
        self.ensure_one()
        end_date = fields.Date.context_today(self)
        if self.expiry_date and end_date > self.expiry_date:
            end_date = self.expiry_date
        vals = {
            'card_id': self.id,
            'start_date': self.activate_date,
            'end_date': end_date,
            'point_in_period': self.point_in_period,
            'total_point': self.total_point,
            'user_id': self.env.uid,
            'type_id': self.type_id.id,
            'status': self.state
        }
        return self.env['card.history'].create(vals)

    @api.multi
    def _update_pricelist_discount(self):
        for card in self:
            if not card.pricelist_id or not card.type_id:
                continue
            for item in card.pricelist_id.item_ids:
                item.price_discount = card.type_id.discount

    @api.multi
    def create_pricelist(self):
        self.ensure_one()
        Pricelist = self.env['product.pricelist']
        fs = dict(Pricelist._fields)
        vals = Pricelist.default_get(fs)
        vals.update({
            'name': u'Public Pricelist ({})'.format(self.partner_id.name)
        })
        pricelist = Pricelist.new(vals)
        for item in pricelist.item_ids:
            item.price_discount = self.type_id.discount
        vals = Pricelist._convert_to_write(pricelist._cache)
        pricelist = Pricelist.create(vals)
        return pricelist.id

    @api.multi
    def btn_renew(self, check_basic_points=True):
        for r in self:
            r.add_history()
        self.btn_active(check_basic_points)

    @api.multi
    def btn_force_renew(self):
        self.btn_renew(check_basic_points=False)

    @api.multi
    def btn_force_active(self):
        self.btn_active(check_basic_points=False)

    @api.multi
    def btn_active(self, check_basic_points=True):
        for r in self:
            if not r.partner_id:
                raise Warning(_('''
                Error! Empty customer!
                '''))
            r.check_existed()
            if check_basic_points:
                r.check_basic_points()
            active_date = r.activate_date
            if not active_date:
                active_date = fields.Date.context_today(r)
            expiry_date = r.type_id.period_id.get_period_end_date(active_date)
            vals = {'state': 'active',
                    'activate_date': active_date,
                    'expiry_date': expiry_date,
                    'point_in_period': 0.00}
            # Add pricelist when activating card
            if not r.pricelist_id:
                pricelist_id = r.create_pricelist()
                if pricelist_id:
                    vals.update({'pricelist_id': pricelist_id})
            r.write(vals)

    @api.multi
    def btn_cancel(self):
        print ("this")

    @api.multi
    def btn_reset(self):
        print ("this")

    @api.multi
    def btn_lock(self):
        print ("this")

    @api.multi
    def btn_unlock(self):
        print ("this")

    @api.multi
    def check_basic_points(self):
        self.ensure_one()
        if not self.partner_id:
            return True
        points = 0.00
        basic_points = self.type_id.basic_point
        force_btn = _(u'Force Activate')
        if self.state == 'In Use':
            points = self.point_in_period or 0.00
            force_btn = _(u'Force Re-Activate')
            basic_points = self.type_id.point_per_period
        else:
            args = [('partner_id', '=', self.partner_id.id),
                    ('state', '=', 'done')]
            SaleOrder = self.env['sale.order']
            orders = SaleOrder.search(args)
            points = sum([r.amount_total for r in orders if r.amount_total])
            points = self.convert_amount_to_point(points)
        if basic_points and (not points or points < basic_points):
            raise Warning(_(u'''
            Error! The customer {} needs at least {:,} points,
            he/she has only {:,} points now.
            Click on the button `{}` if you want to do this action anyway.
            '''.format(self.partner_id.name, basic_points, points, force_btn)
            ))

    @api.model
    def convert_amount_to_point(self, amount):
        prate = self.env.user.company_id.lc_point_exchange_rate or 1
        if not amount or prate < 0:
            return 0.00
        res = float(amount)/float(prate)
        return int(res)

    @api.model
    def convert_point_to_amount(self, point):
        prate = self.env.user.company_id.lc_point_exchange_rate or 1
        if not point or prate < 0:
            return 0.00
        amount = round(float(point) * float(prate),2)
        return amount

    @api.model
    def default_get(self, fields_list):
        res = super(CardCard, self).default_get(fields_list)
        res.update({'creation_date': fields.Date.context_today(self)})
        return res

    # @api.model
    # def create(self, vals):
        
    #     return super(CardCard, self).create(vals)

    @api.model
    def _get_card(self, partner_id, state='In Use'):
        args = [('partner_id', '=', partner_id),
                ('state', '=', state)]
        card = self.search(args, limit=1)
        return card

    @api.model
    def _get_valid_card(self, partner_id):
        card = self._get_card(partner_id)
        if card.is_expired:
            return None
        return card


class ResConfigSettings(models.TransientModel):
    
    _inherit = 'res.config.settings'
    
    def _get_default_setup(self):
        return True

    group_stock_multi_warehouses = fields.Boolean('Multi-Warehouses', implied_group='stock.group_stock_multi_warehouses', default=lambda self:self._get_default_setup())
