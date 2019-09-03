# -*- coding: utf-8 -*-

import uuid
from random import randint
import pyotp
import datetime
from twilio.rest import Client
from odoo import models, fields, api, _
from odoo.exceptions import Warning


class LoyaltyPointsHistoryRedeemLinesConfirm(models.TransientModel):
    
    _name = "loyalty.points.history.purchase.redeem.lines.confirm"

    def _group_settlements(self, active_settlements):
        res = {}
        for settlement in active_settlements: #using Comprehensions to reduce execution time
            key = settlement.reward_merchant_id
            if key not in res:
                res[key] = []
            if not settlement.is_settled:
                res[key].append(settlement)
        return res


    @api.multi
    def confirm_settlement(self):
        """
        This methods confirms settlement
        """
        active_settlements = self.env['loyalty.points.history.purchase.redeem.lines'].browse(self.env.context.get('active_ids'))
        grouped_settlements = self._group_settlements(active_settlements)

        for merchant, settlements in grouped_settlements.items():
            [settlement.write({'is_settled':True, 'date_settle':datetime.datetime.now()}) for settlement in settlements] #write to true as the grouping method does the filtering 
            merchant_admin = [x.user_ids[0] for x in merchant.child_ids if x.user_ids[0].has_group('loyalty.group_merchant_admin')]
            
            if merchant_admin:
                merchant.notify(notify_type='settlement', email=True, data={'settlements':settlements, 'merchant_admin':merchant_admin[0], 'merchant':merchant, 'current_merchant':self.env.user.partner_id.parent_id}) #Notify Other Merchant of the Settlement regarding this.
        return 


    @api.multi
    def reject_settlement(self):
        """
        This methods confirms settlement
        """
        active_settlements = self.env['loyalty.points.history.purchase.redeem.lines'].browse(self.env.context.get('active_ids'))
        
        for settlement in active_settlements: #using Comprehensions to reduce execution time
            settlement.write({'is_settled':False})
        return 


class LoyaltyPointsHistoryRedeemLines(models.Model):

    _name = 'loyalty.points.history.purchase.redeem.lines'

    merchant_point_history_purchase_id = fields.Many2one('loyalty.points.history.purchase.lines', string='Merchant Points History Reference', required=True, ondelete='cascade', index=True, copy=False, readonly=True)
    reward_merchant_id = fields.Many2one('res.partner', domain=[('supplier','=', True)], required=True)
    redeem_merchant_id = fields.Many2one('res.partner', domain=[('supplier','=', True)], required=True)
    redeem_point = fields.Integer('Points Redeem', required=True)
    is_settled = fields.Boolean('Is Settled', default=False)
    date_settle = fields.Datetime('Settlement Date')

    def name_get(self):
        result = []
        for rl in self:
            name = 'Redemption of %s points by %s of %s' % (rl.redeem_point, rl.redeem_merchant_id.name, rl.reward_merchant_id.name) 
            result.append((rl.id, name))
        return result

    
    @api.model
    def search_read(self, domain=None, fields=None, offset=0, limit=None, order=None):
        """
        Override Method to filter Records
        based on access groups
        """

        res = super(LoyaltyPointsHistoryRedeemLines, self).search_read(domain=domain, fields=fields, offset=offset, limit=limit, order=order)
        
        if self.env.context.get('is_parent_view'):

            record_ids = [record.get('id') for record in res]
            records = self.env[self._name].browse(record_ids)
            current_merchant = self.env.user.partner_id.parent_id

            # If user is Active Merchant.
            if self.env.user.has_group('loyalty.group_merchant_admin') or self.env.user.has_group('loyalty.group_merchant_user'):
                res = []

                for record in records:
                    # Check if redeem merchant id is current merchant and reward merchant is not current merchant 
                    # This is done because a particular merchant will only settle other merchant's transaction 
                    # not own settlements of redemption
                    if record.redeem_merchant_id.id == current_merchant.id and record.reward_merchant_id.id != current_merchant.id:
                        
                        record_data = { # Format data for list view
                            'id':record.id,
                            'reward_merchant_id':(record.reward_merchant_id.id, record.reward_merchant_id.name),
                            'redeem_merchant_id':(record.redeem_merchant_id.id, record.redeem_merchant_id.name),
                            'redeem_point':record.redeem_point, 
                            'is_settled':record.is_settled,
                        }
                        
                        res.append(record_data)

            # If user is Operation Team or Admin.
            elif self.env.user.has_group('base.group_system') or self.env.user.has_group('loyalty.group_operation'):
                pass

            else: #No record if user not belong to either groups above.
                res = []

        return res

class PointHistory(models.Model):

    _name = 'loyalty.points.history.purchase.lines'
    _order = "create_date desc"

    def name_get(self):
        return [(purchase.id, 'Purchase by %s of %s %s' % (purchase.customer_id.name, purchase.purchase_amount, purchase.currency_id.symbol)) for purchase in self]

    @api.depends('merchant_point_history_id.merchant_id', 'merchant_point_history_id.customer_id')
    def _get_data_from_history(self):
        for purchase_line in self:
            if purchase_line.merchant_point_history_id.customer_id:
                purchase_line.update({
                        'customer_id':purchase_line.merchant_point_history_id.customer_id.id,
                    })

            if purchase_line.merchant_point_history_id.merchant_id:
                purchase_line.update({
                        'merchant_id':purchase_line.merchant_point_history_id.merchant_id.id,
                    })

    @api.model
    def search_read(self, domain=None, fields=None, offset=0, limit=None, order=None):
        """
        Override Search Read Method
        """
        res = super(PointHistory, self).search_read(domain=domain, fields=fields, offset=offset, limit=limit, order=order)
        tx_history_ids = [record.get('id') for record in res]
        tx_histories = self.env[self._name].browse(tx_history_ids)
        
        if self.env.user.has_group('loyalty.group_merchant_admin') or self.env.user.has_group('loyalty.group_merchant_user'):
            
            # Get Own Txns
            merchant_tx_ids = self.search([('merchant_id','=', self.env.user.partner_id.parent_id.id)]).ids

            # Get Merchant Partners
            merchant_groups_partner_ids = self.env['loyalty.group']._get_merchants_group_partners(merchant=self.env.user.partner_id.parent_id)
            
            # Get partners grouped transactions
            partner_group_tx_ids = self.search([('merchant_id','in', merchant_groups_partner_ids), ('is_group','=', True)]).ids
            domain = ['|', ('id','in',merchant_tx_ids), ('id','in', partner_group_tx_ids)]

            res = super(PointHistory, self).search_read(domain=domain, fields=fields, offset=offset, limit=limit, order=order)

        # If user is Operation Team or Admin.
        elif self.env.user.has_group('base.group_system') or self.env.user.has_group('loyalty.group_operation'):
            pass

        else: #No record if user not belong to either groups above.
            res = []

        return res

    @api.multi
    def read(self, fields=None, load='_classic_read'):
        res = super(PointHistory, self).read(fields=fields, load=load)
        if res:
            redeem_line_ids =  res[0].get('redeem_line')    
            if redeem_line_ids:
                point_history_id = res[0].get('id')
                point_history = self.browse(point_history_id)

                if self.env.user.has_group('loyalty.group_merchant_admin') or self.env.user.has_group('loyalty.group_merchant_user'):

                    # Check for other Merchant's point. for own customer can see everything.
                    if point_history.merchant_id.id != self.env.user.partner_id.parent_id.id:
                        merchant_groups_partner_ids = self.env['loyalty.group']._get_merchants_group_partners(merchant=self.env.user.partner_id.parent_id)

                        for each_redeem_line in redeem_line_ids:
                            redeem_l = self.env['loyalty.points.history.purchase.redeem.lines'].browse(each_redeem_line)
                            # if redeem_l.reward_merchant_id.id in merchant_groups_partner_ids or redeem_l.redeem_merchant_id.id in merchant_groups_partner_ids:
                            if redeem_l.reward_merchant_id.id == self.env.user.partner_id.parent_id.id  or redeem_l.redeem_merchant_id.id == self.env.user.partner_id.parent_id.id:
                                pass
                            else:
                                redeem_line_ids.remove(each_redeem_line)

                        res[0]['redeem_line'] = redeem_line_ids

                    else:
                        pass
                    
                # If user is Operation Team or Admin.
                elif self.env.user.has_group('base.group_system') or self.env.user.has_group('loyalty.group_operation'):
                    pass

                else: #No record if user not belong to either groups above.
                    res = []
        return res

    @api.depends('point', 'point_redeem')
    def _get_points_info(self):
        for history in self:
            is_closed = False
            point_remaining = history.point - history.point_redeem
            
            if point_remaining > 0:
                is_closed = False
            else:
                is_closed = True

            history.update({
                'is_closed': is_closed,
                'point_remaining':point_remaining
            })

    @api.depends('redeem_line.redeem_point')
    def _get_redeem_points(self):
        for purchase_line in self:
            point_redeem = 0

            for redeem_line in purchase_line.redeem_line:
                point_redeem += redeem_line.redeem_point

            purchase_line.update({
                    'point_redeem':point_redeem
                })

    def _get_redeem_line_domain(self):
        """
        """
        
        return []
            

    date = fields.Datetime('Purchase Date', required=True,)
    point = fields.Integer('Points', required=True,)
    point_type = fields.Selection([('in','Reward'), ('out', 'Redeem')], required=True, default="in")    
    merchant_point_history_id = fields.Many2one('loyalty.points.history', string='Merchant Points Reference', required=True, ondelete='cascade', index=True, copy=False, readonly=True)
    purchase_amount = fields.Monetary(string='Purchase Amount')
    currency_id = fields.Many2one('res.currency', required=True)
    customer_id = fields.Many2one('res.partner', compute="_get_data_from_history", store=True)
    merchant_id = fields.Many2one('res.partner', compute="_get_data_from_history", store=True)

    # V2 fields
    point_remaining = fields.Integer('Remaining', default=0, compute="_get_points_info")
    point_redeem = fields.Integer('Used', default=0, store=True, compute="_get_redeem_points")
    is_closed = fields.Boolean('Is Closed', compute="_get_points_info", store=False)
    is_group = fields.Boolean('Is Group', default=False)
    is_settled = fields.Boolean('Is Settled', default=False)
    redeem_line = fields.One2many('loyalty.points.history.purchase.redeem.lines', 'merchant_point_history_purchase_id', string='Point History', copy=True, auto_join=True, domain=lambda self:self._get_redeem_line_domain())


class LoyaltyPointsHistory(models.Model):

    _name = 'loyalty.points.history'

    @api.depends('purchase_line.point')
    def _compute_points(self):
        for history in self:
            total_earn_points = total_redeem_points = 0
            current_user = self.env.user
                
            if current_user.has_group('loyalty.group_merchant_admin') or current_user.has_group('loyalty.group_merchant_user'):

                if history.merchant_id.id == current_user.partner_id.id or history.merchant_id.id == current_user.partner_id.parent_id.id:
                # Condition to check and calculate only current merchant point.
                    for tx in history.purchase_line:                    
                        total_earn_points += tx.point
                        total_redeem_points += tx.point_redeem

            else:
                for tx in history.purchase_line:                    
                    total_earn_points += tx.point
                    total_redeem_points += tx.point_redeem

            history.update({
                    'points':total_earn_points - total_redeem_points,
                    'total_earn_points':total_earn_points,
                    'total_redeem_points':total_redeem_points,
                })

    def name_get(self):
        """
        Override name get to add other info
        """
        result = []
        for history in self:
            name = '%s Points from merchant - %s.' % (history.points, history.merchant_id.name)
            result.append((history.id, name))
        return result

    
    def _get_purchase_line(self):
        """
        Checks user and return points based on the user.
        """
        # TODO :: Check if the purchase line has correct domain as
        # fetching all records here can create issues
        
        user = self.env.user
        user_company = user.partner_id.parent_id

        if user.has_group('loyalty.group_merchant_admin') or user.has_group('loyalty.group_merchant_user'):
            group_merchant_ids = self.env['loyalty.group']._get_merchants_group_partners(merchant=user_company)
            other_merchant_group_earned_point_line_ids = self.env['loyalty.points.history.purchase.lines'].search([('is_group','=',True),('merchant_id','in',group_merchant_ids)]).ids
            
            all_merchant_group_earned_point_line_ids = self.env['loyalty.points.history.purchase.lines'].search([('merchant_id','=',user_company.id)]).ids

            all_point_history_purchase_line_ids = list(set(other_merchant_group_earned_point_line_ids + all_merchant_group_earned_point_line_ids))
            
            return [('id', 'in', all_point_history_purchase_line_ids)]

        else:
            # If not Merchant admin or merchant user then show all points 
            return []


    merchant_id = fields.Many2one('res.partner', domain=[('supplier','=', True)], required=True)
    points = fields.Integer('Points', required=True, compute="_compute_points")
    total_earn_points = fields.Integer('Total Earn Points', required=True, compute="_compute_points")
    total_redeem_points = fields.Integer('Total Redeem Points', required=True, compute="_compute_points")
    customer_id = fields.Many2one('res.partner', string='Customer Reference', required=True, domain=[('customer','=', True)], ondelete='cascade', index=True, copy=False, readonly=True, auto_join=True)
    purchase_line = fields.One2many('loyalty.points.history.purchase.lines', 'merchant_point_history_id', string='Point History', copy=True, auto_join=True, domain=lambda self:self._get_purchase_line())

class LoyaltyRule(models.Model):

    _name = 'loyalty.rule'

    name = fields.Char(string='Rule Reference', required=True, copy=False, readonly=True, index=True, default=lambda self: _('New'),translate=True)
    merchant_id = fields.Many2one('res.partner', domain=[('supplier','=', True)], required=True, default=lambda self:self._get_default_merchant())
    point_value = fields.Float('Amount per point', required=True)
    points = fields.Integer('Points', required=True)
    rule_type = fields.Selection([('in', 'Reward'), ('out', 'Redeem')], 'Rule Type', required=True, default=lambda self:self._get_default_rule_type())
    minimum_edge = fields.Float('Minimum Edge')
    is_lock = fields.Boolean('Is Locked', default=False)

    @api.multi
    def action_lock(self):
        for rule in self:
            rule.write({'is_lock':True})

    @api.multi
    def action_unlock(self):
        for rule in self:
            rule.write({'is_lock':False})

    @api.model
    def _get_default_rule_type(self): 
        return self.env.context.get('rule_type')

    @api.model
    def _get_default_merchant(self):
        try:
            user = self.env['res.users'].sudo().browse(self.env.uid)
            return user.partner_id.parent_id.id or user.partner_id.id
        except:
            return False

    def name_get(self):
        result = []
        for rule in self:
            if rule.rule_type == 'in':
                name = 'Earn Rule for Minimum Purchase %s.' % (rule.minimum_edge)
            elif rule.rule_type == 'out':
                name = 'Redeem Rule for points less than %s' % (rule.points)
            result.append((rule.id, name))
        return result

    @api.model
    def create(self, vals):
        if vals.get('name', _('New')) == _('New'):
            if vals.get('rule_type') == 'in':
                vals['name'] = 'Earn Rule for Minimum Purchase %s.' % (vals.get('minimum_edge'))

            elif vals.get('rule_type') == 'out':
                vals['name'] = 'Redeem Rule for points less than %s' % (vals.get('points'))

        res = super(LoyaltyRule, self).create(vals)
        return res

    @api.multi
    def write(self, vals):
        res = super(LoyaltyRule, self).write(vals)
        if self.rule_type == 'in':
            vals['name'] = 'Earn Rule for Minimum Purchase %s.' % (self.minimum_edge)

        elif self.rule_type == 'out':
            vals['name'] = 'Redeem Rule for points less than %s' % (self.points)

        res = super(LoyaltyRule, self).write(vals)

        return res

class RewardPointsWizard(models.TransientModel):

    _name = 'loyalty.reward.points.wizard'

    def get_applicable_rule(self, amount):
        user = self.env['res.users'].sudo().browse(self.env.uid)
        partner = user.partner_id.parent_id or user.partner_id # Current Logged User As merchant
        rules = self.env['loyalty.rule'].search([('rule_type','=','in'), ('merchant_id','=',partner.id), ('minimum_edge','<=', amount)])
        if len(rules) == 1:
            applicable_rule = rules[0]
        elif len(rules) > 1:
            try:
                applicable_rule = sorted(rules, key=lambda x: x.minimum_edge, reverse=True)[0]
            except:
                return False
        else:
            return False
        return applicable_rule


    @api.depends('purchase_amount')
    def _compute_points(self):
        for reward_wiz in self:
            equivalent_point = 0
            if reward_wiz.purchase_amount:
                rule_id = self.get_applicable_rule(reward_wiz.purchase_amount)
                if rule_id:
                    try:
                        equivalent_point = (reward_wiz.purchase_amount // rule_id.point_value) * rule_id.points
                    except ZeroDivisionError:
                        raise Warning(_('Invalid Reward Rule'))
                else:
                    raise Warning('No Earning Rules found for this criteria.')

            reward_wiz.update({
                    'point' : equivalent_point,
                })

    point = fields.Integer('Equivalent Reward Points', required=True, compute="_compute_points")
    purchase_amount = fields.Monetary(string='Purchase Amount')
    currency_id = fields.Many2one('res.currency', required=True, default=lambda self:self._get_default_currency())    
    
    @api.model
    def _get_default_currency(self):
        return self.env['res.partner'].browse(self.env.context.get('active_id')).company_id.currency_id.id

    @api.multi
    def reward(self):
        user = self.env.user
        customer = self.env['res.partner'].browse(self.env.context.get('active_id'))
        merchant = user.partner_id.parent_id or user.partner_id # Current Logged merchant
        if self.point:
            # if merchant.request_id.remaining_monthly_txns <= 0:
                # raise Warning('Transaction Limit Exceeded for the month for your subscription')
            
            # else:
            # update merchant txn

            merchant_txns = merchant.request_id.monthly_txns + 1
            remaining_monthly_txns = merchant.request_id.remaining_monthly_txns - 1
            merchant.request_id.write({'monthly_txns':merchant_txns, 'remaining_monthly_txns':remaining_monthly_txns})
            merchant_points = self.env['loyalty.points.history'].search([('merchant_id','=',merchant.id), ('customer_id','=', customer.id)], limit=1)

            if not merchant_points:
                merchant_points = self.env['loyalty.points.history'].create({
                        'merchant_id': merchant.id,
                        'customer_id': customer.id,
                    })
           
            merchant_group_ids = self.env['loyalty.group'].search([('state','=','progress')]) # Check if merchant belong to a group
            merchant_has_group = False

            for merchant_group in merchant_group_ids:
                if merchant.id in [mer.id for mer in merchant_group.merchant_ids]:
                    merchant_has_group = True
                    break

            merchant_purchase_line = self.env['loyalty.points.history.purchase.lines'].create({
                    'date': datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'), 
                    'point': self.point, 
                    'point_type': 'in', 
                    'merchant_point_history_id':merchant_points.id,
                    'purchase_amount':self.purchase_amount,
                    'currency_id':self.currency_id.id,
                    'is_group':merchant_has_group,
                })

            msg = 'Your account has been rewarded with %s points for your purchase of %s %s at Merchant - %s' % (self.point, self.currency_id.symbol, self.purchase_amount, merchant.name)
            
            data = {
                'points': self.point,
                'purchase_amount': self.purchase_amount,
                'currency' : self.currency_id.symbol,
                'merchant_name': merchant.name,
            }
            customer.sudo().notify(notify_type="reward", msg=msg, sms=False, email=True, push=True, data=data)
            return
        else:
            raise Warning(_('No points to reward. Please check your earning rules.'))



class RedeemPointsWizard(models.TransientModel):

    _name = 'loyalty.redeem.points.wizard'


    @api.depends('point')
    def _compute_discount(self):
        pass

    def get_applicable_rule(self, point):
        rules = self.env['loyalty.rule'].search([('rule_type','=','out'), ('points','<=', point)])
        if len(rules) == 1:
            applicable_rule = rules[0]
        elif len(rules) > 1:
            applicable_rule = sorted(rules, key=lambda x: x.points, reverse=False)[0]
        elif len(rules) == 0:
            raise Warning(_('No Redeem Rules found for this criteria.'))
        else:
            rules = self.env['loyalty.rule'].search([('rule_type','=','out')])
            applicable_rule = sorted(rules, key=lambda x: x.points, reverse=True)[0]
        return applicable_rule

    @api.depends('point')
    def _compute_discount(self):
        for redeem_wiz in self:
            equivalent_discount_amt = 0
            if redeem_wiz.point:
                rule_id = self.get_applicable_rule(redeem_wiz.point)

                if rule_id:
                    equivalent_discount_amt = rule_id.point_value * redeem_wiz.point

                else:
                    raise Warning(_('No Redeem Rules found for this criteria.'))

            redeem_wiz.update({
                    'discount_amount' : equivalent_discount_amt,
                })

    
    @api.onchange('customer_id')
    def onchange_customer(self):
        if self.customer_id:
            return {'domain':{'coupon_line_id':[('id','in',[coupon_line.id for coupon_line in self.customer_id.coupon_line if coupon_line.state == 'open'])]}}

    point = fields.Integer('No. of Redeem Points', required=False)  
    
    redeem_type = fields.Selection([
                            ('point','Loyalty Points'),
                            ('coupon','Coupon')], 
                            string="Redemption Type", default="point", required=True)


    discount_amount = fields.Monetary(string='Amount Discounted', compute="_compute_discount")
    currency_id = fields.Many2one('res.currency', required=True, default=lambda self:self._get_default_currency())    
    otp = fields.Char('OTP', required=False)
    merchant_id = fields.Many2one('res.partner', domain=[('supplier','=', True)], required=True,  default=lambda self:self._get_default_merchant(), readonly=True)    
    customer_id = fields.Many2one('res.partner', string='Customer', required=True, domain=[('customer','=', True)], ondelete='cascade', index=True, copy=False, readonly=True, default=lambda self:self._get_default_customer())    
    coupon_line_id = fields.Many2one('res.partner.coupon.line', string='Coupon')
    redeem_merchant_group_id = fields.Many2one(comodel_name='loyalty.group', string="Group")
    otp_status = fields.Selection([('unsend','Not Sent'), ('sent','Sent')], default="unsend")

    @api.onchange('merchant_id')
    def onchange_merchant(self):
        group_ids = self.env['loyalty.group']._get_merchants_groups(merchant=self.merchant_id)
        return {'domain':{'redeem_merchant_group_id':[('id','in',group_ids)]}}

    @api.model
    def _get_default_currency(self):
        return self.env['res.partner'].browse(self.env.context.get('active_id')).company_id.currency_id.id

    @api.model
    def _get_default_merchant(self):        
        user = self.env['res.users'].sudo().browse(self.env.uid)
        merchant = user.partner_id.parent_id or user.partner_id #Current Logged User As merchant
        return merchant.id

    @api.model
    def _get_default_customer(self):
        customer = self.env['res.partner'].browse(self.env.context.get('active_id'))
        return customer.id

    def set_otp_to_ctx(self, n=4):
        """
        Returns a random string of length string_length.
        """        
        range_start = 10**(n-1)
        range_end = (10**n)-1
        otp = randint(range_start, range_end)
        ctx = self.env.context.copy()
        ctx['otp'] = otp
        self.env.context = ctx
        return otp


    @api.multi
    def request_otp(self):
        """
        Request OTP
        """
        customer = self.env['res.partner'].browse(self.env.context.get('active_id'))

        if self.point <= 0:
            raise Warning(_('Choose points to redeem.'))

        if not customer.phone and not customer.mobile:
            raise Warning(_('Customer Mobile/Phone not configured. Contact System Administrator.'))

        else:# Logic to send SMS OTP            
            otp = self.set_otp_to_ctx()
            msg = 'OTP for redeemption of %s points from your Mamnon Wallet is %s. ' % (self.point, otp)
            print (msg)

            # Logic to send both SMS and Push Notification.
            self.customer_id.sudo().send_sms(msg)
            self.customer_id.sudo().send_push(msg, notify_type='redeem_auth', otp=otp)
            self.write({'otp_status':'sent'})

        return {
            'view_type': 'form',
            'view_mode': 'form',
            'res_model': self._name,
            'res_id': self.id,
            'target': 'new',
            'type': 'ir.actions.act_window',
            'context': {'current_id': self.id}
        } 
    
    def redeem_points(self):       

        if self.discount_amount <= 0:
            raise Warning(_('No discount amount.'))

        if not self.otp:
            raise Warning(_('OTP not provided.'))

        otp = self.env.context.get('otp')
        ctx = self.env.context.copy()
        ctx.pop('otp')
        self.env.context = ctx
        
        if otp == self.otp:
            point = self.point
            
            if self.redeem_merchant_group_id:

                # TODO: Code cleanup
                # Get Current Merchant's Points at 1st priority
                merchant_point_history = self.env['loyalty.points.history'].search([('merchant_id','=',self.merchant_id.id), ('customer_id','=',self.customer_id.id)], limit=1)
                merchant_point_ids = self.env['loyalty.points.history.purchase.lines'].search([('merchant_point_history_id','=', merchant_point_history.id), ('is_group','=', True), ('point_type','=','in')])
                merchant_point_ids  = sorted(merchant_point_ids, key=lambda x: x.date)

                # Get other merchants of the group 
                group_other_merchant_ids = self.redeem_merchant_group_id.merchant_ids.ids

                if self.merchant_id.id in self.redeem_merchant_group_id.merchant_ids.ids:
                    group_other_merchant_ids.remove(self.merchant_id.id) #remove current merchant

                # Use .sudo() search in order to skip record rules and access all points history, 
                # but this will be applicable only in the backend .
                other_merchant_point_history_ids = self.env['loyalty.points.history'].sudo().search([('merchant_id', 'in', group_other_merchant_ids), ('customer_id','=', self.customer_id.id)])

                other_merchant_point_ids = self.env['loyalty.points.history.purchase.lines'].sudo().search([('merchant_point_history_id','in', other_merchant_point_history_ids.ids), ('is_group','=', True), ('point_type','=','in')])
                other_merchant_point_ids = sorted(other_merchant_point_ids, key=lambda x: x.date)

                total_merchant_point_ids = []                
                for pl in merchant_point_ids:
                    total_merchant_point_ids.append(pl)
                for pl in other_merchant_point_ids:
                    total_merchant_point_ids.append(pl)

                # TODO :: Code Cleanup

                total_earn_points_available = sum(mpl.point_remaining for mpl in total_merchant_point_ids)

                if point > total_earn_points_available:
                    raise Warning(_('Customer do not have enough loyalty points'))

                while point > 0:
                    for merchant_point in total_merchant_point_ids:
                        if merchant_point.point_remaining > point:
                            merchant_point.redeem_line.create({
                                'reward_merchant_id':merchant_point.merchant_id.id,
                                'redeem_merchant_id': self.merchant_id.id,
                                'redeem_point': point,
                                'merchant_point_history_purchase_id': merchant_point.id,
                            })
                            point = 0
                            break
                        else:
                            point = point - merchant_point.point_remaining
                            merchant_point.redeem_line.create({
                                'reward_merchant_id':merchant_point.merchant_id.id,
                                'redeem_merchant_id': self.merchant_id.id,
                                'redeem_point': merchant_point.point_remaining,
                                'merchant_point_history_purchase_id': merchant_point.id,
                            })
                    break                
            else:
                # if self.point > self.customer_id.loyalty_points:
                #     raise Warning(_('Customer do not have enough loyalty points'))

                if self.merchant_id.id not in [mer.merchant_id.id for mer in self.customer_id.points_line]:
                    raise Warning(_('Customer do not have your loyalty points'))
                    
                merchant_points = self.env['loyalty.points.history'].search([('merchant_id','=',self.merchant_id.id), ('customer_id','=',self.customer_id.id)], limit=1)
                if not merchant_points:
                    raise Warning(_('Customer do not have your loyalty points'))

                merchant_purchase_line_ids = self.env['loyalty.points.history.purchase.lines'].search([('merchant_point_history_id','=', merchant_points.id), ('is_group','=', False), ('point_type','=','in')])
                merchant_own_group_purchase_line_ids = self.env['loyalty.points.history.purchase.lines'].search([('merchant_point_history_id','=', merchant_points.id), ('is_group','=', True), ('point_type','=','in')])
                
                total_merchant_point_ids = []
                
                for pl in merchant_purchase_line_ids:
                    total_merchant_point_ids.append(pl)
                for pl in merchant_own_group_purchase_line_ids:
                    total_merchant_point_ids.append(pl)

                total_merchant_point_ids  = sorted(total_merchant_point_ids, key=lambda x: x.date)                

                # Change Log :: Now no need to create a record of 
                # purchase.lines now because we are adding sub 
                # record in redeem line

                # If don't have enough loyalty point then search in groups also but only own group points no other merchant's points
                total_earn_points_available = sum(mpl.point_remaining for mpl in total_merchant_point_ids)
                if point > total_earn_points_available:
                    raise Warning(_('Customer do not have enough loyalty points'))
                
                while point > 0:
                    for merchant_point in total_merchant_point_ids:
                        if merchant_point.point_remaining > point:
                            merchant_point.redeem_line.create({
                                'reward_merchant_id':merchant_point.merchant_id.id,
                                'redeem_merchant_id': self.merchant_id.id,
                                'redeem_point': point,
                                'merchant_point_history_purchase_id': merchant_point.id,
                            })
                            point = 0 #Set Point to zero as all points redeem from the current merchant_point in the loop
                            break

                        else:
                            point = point - merchant_point.point_remaining
                            merchant_point.redeem_line.create({
                                'reward_merchant_id':merchant_point.merchant_id.id,
                                'redeem_merchant_id': self.merchant_id.id,
                                'redeem_point': merchant_point.point_remaining,
                                'merchant_point_history_purchase_id': merchant_point.id,
                            })


            msg = "Congratulations!! You have redeem %s points. You will receive discount of %s %s for this purchase." % (self.point, self.currency_id.symbol, self.discount_amount)
            data = {
                'points': self.point,
                'discount': self.discount_amount,
                'currency' : self.currency_id.symbol,
            }
            self.customer_id.sudo().notify(notify_type="redeem", msg=msg, sms=False, email=True, push=True, data=data)
            
            return  { 
                'name' : _('Points Redemption Successful'),
                'type' : 'ir.actions.act_window',
                'view_type' : 'form',
                'view_mode' : 'form',
                'res_model' : 'loyalty.redeem.success.message.wizard',
                'target' : 'new',
                'context' : {'default_message':"Redemption Successful. You have redeem %s points of Customer - %s. Customer will receive discount of %s %s for his purchase." % (self.point, self.customer_id.name, self.currency_id.symbol, self.discount_amount)} 
            }        

        else:
            raise Warning('Invalid OTP.')


    def redeem_coupon(self):
        """
        """
        if self.coupon_line_id.coupon_id.id not in [coupon_line.coupon_id.id for coupon_line in self.customer_id.coupon_line]:
            raise Warning(_('Customer do not have the selected coupon.'))

        if not self.otp:
            raise Warning(_('OTP not provided.'))

        otp = self.env.context.get('otp')
        ctx = self.env.context.copy()
        ctx.pop('otp')
        self.env.context = ctx
        
        if otp == self.otp:

            self.coupon_line_id.write({'state':'close', 'redeem_date':datetime.datetime.today().date()})            
            msg = "Congratulations!! You have redeem %s coupon." % (self.coupon_line_id.coupon_id.name)
            data = {
                'coupon': self.coupon_line_id.coupon_id.name,
            }
            self.customer_id.sudo().notify(notify_type="redeem", msg=msg, sms=True, email=True, push=True, data=data)            
            return  {
                'name' : _('Coupon Redemption Successful'),
                'type' : 'ir.actions.act_window',
                'view_type' : 'form',
                'view_mode' : 'form',
                'res_model' : 'loyalty.redeem.success.message.wizard',
                'target' : 'new',
                'context' : {'default_message':"Redemption Successful. You have redeem %s coupon of Customer - %s." % (self.coupon_line_id.coupon_id.name, self.customer_id.name)} 
            }
        else:
            raise Warning('Invalid OTP.')

    @api.multi
    def redeem(self):
        """
        Redeem the points / coupon 
        based on selection
        @params - self (object)
        """
        if self.redeem_type == 'point':
            return self.redeem_points()
        
        elif self.redeem_type == 'coupon':
            return self.redeem_coupon()

        raise Warning(_('Please choose redemption type.'))




class RedeemSuccessMessage(models.TransientModel):
    
    _name = "loyalty.redeem.success.message.wizard"

    @api.model
    def _get_default_point_msg(self):
        customer = self.env[self.env.context.get('active_model')].browse(self.env.context.get('active_id'))
        return 'Customer - %s has %s points to redeem at your shop.' % (customer.name, customer.loyalty_points)

    message = fields.Char('Message',translate=True, default=lambda self:self._get_default_point_msg())