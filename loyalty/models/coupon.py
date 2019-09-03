# -*- coding: utf-8 -*-

from odoo.exceptions import ValidationError
from datetime import datetime
from odoo import models, fields, api, _

class LoyaltyCoupon(models.Model):
    _name = 'loyalty.coupon'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _sql_constraints = [('code_unique', 'unique(code)', _('Coupon Code already exists.'))]

    @api.depends('limit', 'count_alloted')
    def _get_coupon_count(self):
        for coupon in self:
            
            count_remaining = coupon.limit
            
            if coupon.limit > coupon.count_alloted:
                count_remaining = coupon.limit - coupon.count_alloted
            else:
                raise Warning(_('Alloted Coupons cannot be greater than Limit.'))
            
            coupon.update({
                    'count_remaining':count_remaining,
                })

    name = fields.Char('Coupon Name', required=True)
    merchant_id = fields.Many2one('res.partner', default=lambda self:self._get_default_merchant_id(), required=True)
    description = fields.Text('Coupon Detail', required=True)
    code = fields.Char('Coupon Code', required=True)
    expire_date = fields.Date('Expire Date', required=True)
    limit = fields.Integer('Coupon Limit', required=True, default=10)
    count_alloted = fields.Integer('Coupons Alloted', required=True, default=0, store=True)
    count_remaining = fields.Integer('Coupons Remaining', required=True,  default=0, compute="_get_coupon_count", store=True)
    coupon_type = fields.Selection([
            ('percent', 'Percentage'),
            ('amount', 'Amount')
        ], string='Coupon Type', default='percent', required=True)
    disc_amount = fields.Float('Discount Amount', required=True)
    disc_percent = fields.Float('Discount (%)', required=True)
    state = fields.Selection([
            ('new', 'Draft'),
            ('requested','Requested'),
            ('active', 'Approved/Active'),
            ('inactive', 'Expired')
        ], string='State', default='new', required=True, track_visibility="onchange")
 
    @api.model
    def _get_default_merchant_id(self):
        if self.env['res.users'].sudo().browse(self.env.uid).partner_id.parent_id:
            return self.env['res.users'].sudo().browse(self.env.uid).partner_id.parent_id.id
        else:
            return self.env['res.users'].sudo().browse(self.env.uid).partner_id.id

    @api.constrains('expire_date')
    def _check_expire(self):
        current_date = datetime.today().date()

        for record in self:
            if current_date >= record.expire_date:
                raise ValidationError(_('The expire date should be greater than current date.'))

    @api.multi
    def action_draft(self):
        for record in self:
            record.write({'state':'new'})

    @api.multi
    def action_request_approve(self):
        for record in self:
            record.write({'state':'requested'})        

    @api.multi
    def action_active(self):
        """
        Activate the Coupon and notify to all the customers
        """
        for record in self:
            msg = 'Coupon %s published by %s' % (record.name, record.merchant_id.name)            
            for customer in self.env['res.partner'].search([('customer','=',True)]):
                customer.sudo().notify(notify_type="coupon_publish", msg=msg, sms=False, email=True, push=True, data={})            
            record.write({'state':'active'})

    @api.multi
    def action_inactive(self):
        for record in self:
            record.write({'state':'inactive'})

    def name_get(self):
        result = []
        for coupon in self:
            name = '%s / %s' % (coupon.merchant_id.name, coupon.code)
            result.append((coupon.id, name))
        return result

    ##############################################################
    # CRON Related Methods                                       #
    ##############################################################
    
    @api.multi
    def auto_expire_merchant_coupon(self):
        """
        Handler for cron job - auto expire merchant
        """
        for coupon in self.search([('expire_date','>', datetime.today()), ('state','=', 'active')]):
            coupon.action_inactive()
            
            # Expire the coupons line of customer Also.
            for coupon_line in self.env['res.partner.coupon.line'].search([('coupon_id','=',coupon.id)]):
                coupon_line.action_expire()
            

# class PartnerCouponLine(models.Model):
    
#     _name = 'res.partner.coupon.line'
#     _rec_name = 'coupon_id'

#     def check_customer_coupon(self):
#         for record in self:
#             search_ids = self.search([('customer_id', '=', record.customer_id.id),('coupon_id', '=' , record.coupon_id.id)])
#             res = True
#             if len(search_ids) > 1:
#                 res = False
#             return res

#     _constraints = [(check_customer_coupon,'A coupon is allowed only once for a customer.', ['coupon_id'])]

#     customer_id = fields.Many2one('res.partner', string='Customer Reference', required=True, ondelete='cascade', index=True, copy=False, readonly=True)
#     coupon_id = fields.Many2one('loyalty.coupon', string="Coupon", required=True)
#     state = fields.Selection([
#             ('open', 'Not Used'),
#             ('close', 'Used'),
#             ('expire', 'Expired'),
#         ], string="State", default="open", required=True)

#     expire_date = fields.Date('Expire Date', required=True)
#     redeem_date = fields.Date('Redeem Date')

#     @api.multi
#     def action_expire(self):
#         for coupon_line in self:
#             coupon_line.write({'state':'expire'})