# -*- coding: utf-8 -*-

import numpy as np
import uuid
from random import randint
from .filestore import ImageFilestore
import logging
import pyotp
import string
import random
from pyfcm import FCMNotification 
from odoo.exceptions import Warning, UserError
from odoo import models, fields, api, _
from twilio.rest import Client
from datetime import datetime
from odoo.addons.auth_signup.models.res_partner import SignupError, now
_logger = logging.getLogger(__name__)

class City(models.Model):
    
    _name = 'res.city'
    _rec_name = 'name'

    name = fields.Char('City Name', required=True)
    country_id = fields.Many2one('res.country','Country')


class LoyaltyMobileOTPRegister(models.TransientModel):

    _name = 'loyalty.mobile.otp.register'

    mobile = fields.Char('Mobile No.', required=True)
    otp = fields.Char('OTP', required=True)

class LoyaltyDeal(models.Model):
    
    _name = 'res.partner.rating.line'

    @api.constrains('rating')
    def check_rating(self):
        if self.rating % 0.5: 
            raise ValidationError(_('Invalid Rating should be multiple of 0.5 in range 1 to 5'))
        else:
            return True

    customer_id = fields.Many2one('res.partner', domain=[('customer','=',True)], required=True)
    review = fields.Text('Review')
    rating = fields.Float(required=True, digits=(2,1))
    partner_id = fields.Many2one('res.partner', 'Partner Reference',required=True, ondelete='cascade', index=True, copy=False, readonly=True)

class Customer(models.Model):
    
    _inherit = 'res.partner'
    
    @api.depends('points_line.points')
    def _compute_points(self):
        for customer in self:
            total_points = 0
            
            for mer_points in customer.points_line:
                total_points += mer_points.points

            customer.update({
                    'loyalty_points': total_points
                })


    def _get_point_line(self):
        """
        Filter the point lines based on 
        current logged merchant
        """
        user = self.env.user
        user_company = user.partner_id.parent_id
        if user.has_group('loyalty.group_merchant_admin') or user.has_group('loyalty.group_merchant_user'):
            
            # Get Other merchant points which are grouped (i.e is_grouped=True)
            group_merchant_ids = self.env['loyalty.group']._get_merchants_group_partners(merchant=user_company)
            other_merchant_group_earned_point_line_ids = self.env['loyalty.points.history.purchase.lines'].search([('is_group','=',True),('merchant_id','in',group_merchant_ids)])
            other_merchant_point_history_ids = [point_line.merchant_point_history_id.id for point_line in other_merchant_group_earned_point_line_ids]
    
            # Get current merchants all points
            current_merchant_point_history_ids = self.env['loyalty.points.history'].search([('merchant_id','=',user_company.id)]).ids

            all_point_history_ids = list(set(other_merchant_point_history_ids + current_merchant_point_history_ids))
            return [('id','in',all_point_history_ids)]

        else:            
            # If not Merchant admin or merchant user then show all points 
            return []

    @api.depends('rating_line.rating')
    def _get_average_rating(self):
        for merchant in self:
            merchant_rating_avg = 0
            
            if merchant.rating_line:
                merchant_rating_avg = sum([float(rl.rating) for rl in merchant.rating_line]) / len(merchant.rating_line)

            merchant.update({
                    'rating':merchant_rating_avg,
                })

    @api.depends('mobile')
    def _get_masked_mobile(self):
        """
        Get Masked Mobile
        """
        for partner in self:
            if partner.mobile:
                mobile_masked = partner.mobile[-4:].rjust(len(partner.mobile), "*")
            else:
                mobile_masked = False
            partner.update({
                    'mobile_mask':mobile_masked,
                })

    mobile_mask = fields.Char('Mobile', compute="_get_masked_mobile", store=False)

    gender = fields.Selection([('male', 'Male'), ('female','Female')])
    city = fields.Many2one('res.city')
    dob = fields.Date(string="Date of Birth")
    loyalty_points = fields.Integer('Loyalty Points', default=0, compute="_compute_points")
    # card_id = fields.Char('Mamnon Card Number')
    points_line = fields.One2many('loyalty.points.history', 'customer_id', string='Point History', copy=True, auto_join=True, domain=lambda self:self._get_point_line())
    # merchant_points_line = fields.One2many('loyalty.points.history', 'merchant_id', string='Point History', copy=True, auto_join=True)
    registering_merchant_id = fields.Many2one('res.partner', 'Registering Merchant')
    mobile_verified = fields.Boolean('Is Mobile Verified', default=False)

    # Social Links
    social_fb_link = fields.Char('Facebook Link')
    social_gplus_link = fields.Char('Google+ Link')
    image_url = fields.Char('Image URL')

    favourite_deal_ids = fields.Many2many(comodel_name='loyalty.deal',
                            relation='customer_favourite_deal_rel',
                            column1='customer_id',
                            column2='deal_id', string="Favourite Deals")

    favourite_merchant_ids = fields.Many2many(comodel_name='res.partner',
                            relation='customer_favourite_merchant_rel',
                            column1='customer_id',
                            column2='merchant_id',
                            domain=[('supplier', '=', True), ('parent_id','=', False)], string="Favourite Merchants")

    # coupon_ids = fields.Many2many(comodel_name='loyalty.coupon',
    #                         relation='customer_coupon_rel',
    #                         column1='customer_id',
    #                         column2='coupons_id', string="Coupons")

    # coupon_line = fields.One2many('respartner.coupon.line', 'customer_id', string='Coupon Lines', copy=True, auto_join=True)
    group_line = fields.Many2many('loyalty.group', 'merchant_group_rel', 'merchant_id', 'group_id', string="Group Lines")
    notification_line = fields.One2many('res.partner.notification', 'receipient_id', 'Notification Line', copy=True, auto_join=True)
    
    rating_line = fields.One2many('res.partner.rating.line', 'partner_id', string='Rating Line', copy=True, auto_join=True)
    rating = fields.Float('Average Rating', required=True, default=0, compute="_get_average_rating", digits=(14,1), readonly=False)
    

    # @api.multi
    # def get_merchant_customer(self):
    #     logged_user = self.env['res.users'].sudo().browse(self.env.uid)
    #     current_logged_merchant_id = logged_user.partner_id.parent_id.id
    #     res_ids = []
    #     action = self.env.ref('loyalty.action_loyalty_customer').read()[0]

    #     if logged_user.has_group('loyalty.group_merchant_admin') or logged_user.has_group('loyalty.group_merchant_user'):
    #         for customer in self.search([]):            
    #             if current_logged_merchant_id in [points.merchant_id.id for points in customer.points_line]:
    #                 res_ids.append(customer.id)
    #             if current_logged_merchant_id == customer.registering_merchant_id.id:
    #                 res_ids.append(customer.id)
    #         action['domain'] = "[('customer','=',True), ('id','in',%s)]" % res_ids        
    #     else:
    #         action['domain'] = "[('customer','=',True)]" 

    #     return action


    @api.model
    def create(self, vals):
        """
        # DOC STRING
        """
        res = super(Customer, self).create(vals)
        if vals.get('image'):
            image_url = ImageFilestore().convert(res.id, res.image, 'partner')
            res.write({'image_url':image_url})
        return res


    @api.multi
    def write(self, vals):
        """
        # DOC STRING
        """
        if vals.get('image'):
            vals['image_url'] = ImageFilestore().convert(self.id, vals.get('image'), 'partner')
            
        res = super(Customer, self).write(vals)

        return res

    @api.multi
    def generate_img_urls(self):
        for partner in self.search([]):
            if partner.image:
                image_url = ImageFilestore().convert(partner.id, partner.image, 'partner')
                partner.write({'image_url':image_url})
        return 

    
    @api.model
    def search_read(self, domain=None, fields=None, offset=0, limit=None, order=None):
        """
        Override Method to filter 
        Records based on access groups
        """
        res = super(Customer, self).search_read(domain=domain, fields=fields, offset=offset, limit=limit, order=order)
        
        if self.env.context.get('is_parent_view'):
            res = super(Customer, self).search_read(domain=[('customer','=',True)], fields=fields, offset=offset, limit=limit, order=order)

            if domain:
                domain = [domain.pop(-1)]
                res = super(Customer, self).search_read(domain=domain, fields=fields, offset=offset, limit=limit, order=order)
                return res

            record_ids = [record.get('id') for record in res]
            records = self.env[self._name].browse(record_ids)
            current_merchant = self.env.user.partner_id.parent_id

            # If user is Active Merchant.
            if self.env.user.has_group('loyalty.group_merchant_admin') or self.env.user.has_group('loyalty.group_merchant_user'):
                res = []
                for record in records:
                    record_data = {}
                    # Check if redeem merchant id is current merchant and reward merchant is not current merchant 
                    # This is done because a particular merchant will only settle other merchant's transaction 
                    # not own settlements of redemption
                    if current_merchant.id in [points.merchant_id.id for points in record.points_line]:
                        record_data = {
                            'id':record.id,
                            'name':record.name,
                            'email':record.email,
                            'mobile':record.mobile,
                            'loyalty_points':record.loyalty_points,
                        }
                    
                    if current_merchant.id == record.registering_merchant_id.id:
                        record_data = {
                            'id':record.id,
                            'name':record.name,
                            'email':record.email,
                            'mobile':record.mobile,
                            'loyalty_points':record.loyalty_points,
                        }

                    if record_data:
                        res.append(record_data)

            # If user is Operation Team or Admin.
            elif self.env.user.has_group('base.group_system') or self.env.user.has_group('loyalty.group_operation'):
                pass

            else: #No record if user not belong to either groups above.
                res = []

        return res

    def generate_otp(self, n=4):
        range_start = 10**(n-1)
        range_end = (10**n)-1
        otp = randint(range_start, range_end)
        return otp

    def send_register_verification_otp(self, mobile=False):
        
        if not mobile:
            return False

        registered_otpObj = self.env['loyalty.mobile.otp.register'].search([('mobile','=',mobile)], limit=1)

        otp = self.generate_otp()

        if registered_otpObj:
            registered_otpObj.write({'otp':otp})
        
        else:
            registered_otpObj = self.env['loyalty.mobile.otp.register'].create({
                    'mobile':mobile, 
                    'otp':otp,
                })

        # SEND OTP VIA SMS 
        account_sid = self.env['ir.config_parameter'].sudo().get_param('merchant.twilio_cid')
        auth_token = self.env['ir.config_parameter'].sudo().get_param('merchant.twilio_token')
        twilio_number = self.env['ir.config_parameter'].sudo().get_param('merchant.twilio_number')
        client = Client(account_sid, auth_token)  
        
        msg = 'OTP for mobile verification of your MAMNON Account is - %s' % (otp)
        
        try:
            message = client.messages.create(
                    body=msg,
                    from_=twilio_number,
                    to=mobile,
                )
            print ("OTP Sent to SMS successfully!")
            return True
        except:
            print ("Error Sending SMS Notification")
            return False

    ##################################
    # CRON RELATED METHODS
    ##################################    

    @api.multi
    def _get_publish_ad_limit(self, ad_typeObj=False):
        """
        This method returns the publish ad limit 
        of the particular ad type
        """
        plan = self.request_id.plan_id

        subscription_type_ad_line = self.env['merchant.plan.deal.line'].search([('plan_id','=',plan.id), ('deal_type_id','=',ad_typeObj.id)], limit=1)
        
        if not subscription_type_ad_line:
            return 0

        return subscription_type_ad_line.count

class Users(models.Model):
    _inherit = 'res.users'

    device_id = fields.Char(string='Device ID')
    notified = fields.Boolean('Is Notified ?', default=False)

    # Notification Related Fields
    notify_email = fields.Boolean('Enable Email Notification', default=True)
    notify_sms = fields.Boolean('Enable SMS Notification', default=True)
    notify_push = fields.Boolean('Enable Push Notification', default=True)


    @api.multi
    def action_reset_password(self):
        """ create signup token for each user, and send their signup url by email """
        # prepare reset password signup
        create_mode = bool(self.env.context.get('create_user'))

        # no time limit for initial invitation, only for reset password
        expiration = False if create_mode else now(days=+1)

        self.mapped('partner_id').signup_prepare(signup_type="reset", expiration=expiration)

        # send email to users with their signup url
        template = False
        if create_mode:
            try:
                template = self.env.ref('loyalty.set_password_email', raise_if_not_found=False)
            except ValueError:
                pass
        if not template:
            template = self.env.ref('loyalty.reset_password_email')
        assert template._name == 'mail.template'

        template_values = {
            'email_to': '${object.email|safe}',
            'email_cc': False,
            'auto_delete': True,
            'partner_to': False,
            'scheduled_date': False,
        }
        template.write(template_values)

        for user in self:
            if not user.email:
                raise UserError(_("Cannot send email: user %s has no email address.") % user.name)
            with self.env.cr.savepoint():
                template.with_context(lang=user.lang).send_mail(user.id, force_send=True, raise_exception=True)
            _logger.info("Password reset email sent for user <%s> to <%s>", user.login, user.email)


    def _set_reminder_notify(self, kw):

        pass

class ActServer(models.Model):
    
    _inherit = 'ir.actions.server'    

    activity_user_type = fields.Selection([
        ('specific', 'Specific User'),
        ('generic', 'Generic User From Record')], default="specific", required=False,
        help="Use 'Specific User' to always assign the same user on the next activity. Use 'Generic User From Record' to specify the field name of the user to choose on the record.")