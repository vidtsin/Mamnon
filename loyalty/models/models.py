# -*- coding: utf-8 -*-
import string
import random
from odoo import models, fields, api, _
from datetime import datetime
from odoo.exceptions import Warning
from .filestore import ImageFilestore

class SubscriptionPlanLines(models.Model):

    _name = 'merchant.plan.deal.line'

    deal_type_id = fields.Many2one('loyalty.deal.type', 'Deal Type', domain="[('need_approval','=', False)]", required=True)
    plan_id = fields.Many2one('merchant.plan', string='Plan Reference', required=True, ondelete='cascade', index=True, copy=False, readonly=True)
    count = fields.Integer('Count', required=True, default=1)

    def check_existance(self):
        deal_type_id = self[-1].deal_type_id
        plan_id = self[-1].plan_id
        search_ids = self.search([('deal_type_id', '=', deal_type_id.id),('plan_id', '=' , plan_id.id)])
        res = True
        if len(search_ids) > 1:
            res = False
        return res
    
    _constraints = [(check_existance, _('A deal type cannot be selected twice in the same plan.'), ['deal_type_id'])]


class SubscriptionPlan(models.Model):

    _name = 'merchant.plan'
    
    name = fields.Char('Plan Name', required=True, translate=True)
    transactions = fields.Integer('Transaction Number')
    price = fields.Monetary('Price')
    currency_id = fields.Many2one('res.currency', string='Currency', required=True, default=lambda self: self.env.user.company_id.currency_id)
    free_mnth = fields.Selection([(x , str(x) +' Month') for x in range(0,7)], string='Free Month',  default=0)
    duration = fields.Integer('Duration In Months')
    deal_line = fields.One2many('merchant.plan.deal.line', 'plan_id', string='Deals Allowed', copy=True, auto_join=True)
    product_id = fields.Many2one('product.product', 'Related Product', required=False)

    @api.model
    def create(self, vals):
        product = self.env['product.product'].create({
                            'name': vals.get('name'),
                            'price': vals.get('price'),
                            'type': 'service',
                        })
        vals['product_id'] = product.id
        res = super(SubscriptionPlan, self).create(vals)
        return res 


class ShopType(models.Model):

    _name = 'merchant.shop.type'
    
    name = fields.Char('Shop Type', required=True, translate=True)
    icon_img = fields.Binary('Shop Icon', required=False)
    icon_img_with_bg = fields.Binary('Shop Icon with Background', required=False)

    icon_img_url = fields.Char('Shop Icon', translate=True)
    icon_img_with_bg_url = fields.Char('Shop Icon with Background', translate=True)

    @api.model
    def create(self, vals):
        res = super(ShopType, self).create(vals)
        if vals.get('icon_img'):
            icon_img_url = ImageFilestore().convert(res.id, res.icon_img, 'category')
            res.write({'icon_img_url':icon_img_url})
        if vals.get('icon_img_with_bg'):
            icon_img_with_bg_url = ImageFilestore().convert(res.id, res.icon_img_with_bg, 'category_with_bg')
            res.write({'icon_img_with_bg_url':icon_img_with_bg_url})
        return res

    @api.multi
    def write(self, vals):
        if vals.get('icon_img'):
            vals['icon_img_url'] = ImageFilestore().convert(self.id, vals.get('icon_img'), 'category')

        if vals.get('icon_img_with_bg'):
            vals['icon_img_with_bg_url'] = ImageFilestore().convert(self.id, vals.get('icon_img_with_bg'), 'category_with_bg')

        res = super(ShopType, self).write(vals)        
        return res

    @api.multi
    def generate_img_urls(self):
        for shop_type in self.search([]):
            if shop_type.icon_img and not shop_type.icon_img_url:
                icon_img_url = ImageFilestore().convert(shop_type.id, shop_type.icon_img, 'category')
                shop_type.write({'icon_img_url':icon_img_url})
            if shop_type.icon_img_with_bg and not shop_type.icon_img_with_bg_url:
                icon_img_with_bg_url = ImageFilestore().convert(shop_type.id, shop_type.icon_img_with_bg, 'category_with_bg')
                shop_type.write({'icon_img_with_bg_url':icon_img_with_bg_url})
        return 


def random_password_generator(size=8, chars=string.ascii_uppercase + string.digits):
    return ''.join(random.choice(chars) for _ in range(size))
    

class CustomerRegistrationWizard(models.TransientModel):

    _name = 'loyalty.customer.register.wizard'

    name = fields.Char(index=True, translate=True)
    gender = fields.Selection([('male', 'Male'), ('female','Female')])
    dob = fields.Date(string="Date of Birth")
    street = fields.Char(translate=True)
    street2 = fields.Char(translate=True)
    city = fields.Many2one('res.city', required=True)
    country_id = fields.Many2one('res.country', string='Country', ondelete='restrict')
    email = fields.Char(translate=True)
    mobile = fields.Char()
    image = fields.Binary("Image")

    @api.multi      
    def register(self):        
        customer_user_group = self.env.ref('base.group_portal')
        password = random_password_generator()
        user_vals = {
            'login':self.email, 
            'password':password,
            'name':self.name,
            'email':self.email,
            'groups_id':[(6, 0, [customer_user_group.id])]
        }
        user = self.env['res.users'].sudo().with_context({'no_reset_password':True}).create(user_vals)
        current_logged_merchant = self.env['res.users'].sudo().browse(self.env.uid)
        partner_vals = {
            'gender':self.gender, 
            'city':self.city,
            'dob':self.dob,
            # 'card_id':self.card_id, 
            'street':self.street,
            'street2':self.street2,
            'city':self.city.id,
            'country_id':self.country_id.id,
            'email':self.email,
            'mobile':self.mobile,
            'image':self.image,
            'customer':True,
            'registering_merchant_id':current_logged_merchant.partner_id.parent_id.id or current_logged_merchant.partner_id.id,
        }

        # Code to send Email and SMS
        user.partner_id.sudo().write(partner_vals)
        user.partner_id.sudo().notify(notify_type='register_by_merchant', email=True, push=True, sms=True, data={'password':password})
        return {
            'type': 'ir.actions.client',
            'tag': 'reload',
        }
        # return self.env['res.partner'].get_merchant_customer()


class LoyaltySetting(models.Model):
    
    _name = 'loyalty.setting'



