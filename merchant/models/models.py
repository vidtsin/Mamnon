# -*- coding: utf-8 -*-

from geopy.geocoders import Nominatim
from validate_email import validate_email
from odoo.exceptions import ValidationError
from .filestore import ImageFilestore
import json, datetime
import urllib
from odoo import models, fields, api, _
from odoo.exceptions import Warning

class MerchantRequestImages(models.Model):

    _name = 'merchant.request.images.line'

    request_id = fields.Many2one('merchant.request', string='Request Reference', required=True, ondelete='cascade', index=True, copy=False, readonly=True)
    image = fields.Binary('Image', required=True)
    image_url = fields.Char('Image URL')

    # @api.model
    # def create(self, vals):
    #     ICP = self.env['ir.config_parameter'].sudo()
    #     max_img_size = int(ICP.get_param('merchant.max_img_size'))
    #     if vals.get('image'):
    #         img_data = vals.get('image')
    #         img_size = (((len(img_data) * 3) / 4) / 1000)

    #         if img_size > float(max_img_size):
    #             raise Warning('Image Size Too Large. Should not exceed %s KB' % str(max_img_size))
            
    #         else:
    #             res = super(MerchantRequestImages, self).create(vals)
    #             image_url = ImageFilestore().convert(res.id, img_data, 'shop')
    #             res.write({'image_url':image_url})
    #     else:
    #         res = super(MerchantRequestImages, self).create(vals)

    #     return res

    # @api.multi
    # def write(self, vals):
    #     ICP = self.env['ir.config_parameter'].sudo()
    #     max_img_size = int(ICP.get_param('merchant.max_img_size'))
    #     if vals.get('image'):
    #         img_data = vals.get('image')
    #         img_size = (((len(img_data) * 3) / 4) / 1000)

    #         if img_size > float(max_img_size):
    #             raise Warning('Image Size Too Large. Should not exceed %s KB' % str(max_img_size))
    #         else:
    #             vals['image_url'] = ImageFilestore().convert(res.id, img_data, 'shop')

    #     res = super(MerchantRequestImages, self).write(vals)

    #     return res

class Customer(models.Model):
    
    _inherit = 'res.partner'
    
    @api.depends('request_id')
    def _get_shop_type(self):
        """
        Update Shop Type
        """
        for partner in self:
            partner.update({
                    'shop_type_id':partner.request_id.shop_type_id.id,
                })


    request_id = fields.Many2one('merchant.request', string='Request Reference', required=False, ondelete='cascade', index=True, copy=False, readonly=True)
    shop_type_id = fields.Many2one('merchant.shop.type', 'Shop Type', required=False, compute="_get_shop_type", store=True)


class Users(models.Model):
    
    _inherit = 'res.users'
    
    request_id = fields.Many2one('merchant.request', string='Request Reference', required=False, ondelete='cascade', index=True, copy=False, readonly=True)

class MerchantRequestInvoice(models.Model):

    _name = 'merchant.request.invoice.line'
    _order = "create_date desc"
    

    request_id = fields.Many2one('merchant.request', string='Request Reference', required=True, ondelete='cascade', index=True, copy=False, readonly=True)
    invoice_id = fields.Many2one('account.invoice', 'Invoice', required=False, domain="[('type','=','out_invoice')]")
    action_date = fields.Date('Action Date', required=True)
    action = fields.Selection([('new', 'New Registration'), ('renew', 'Renewal')], default="new", required=True)


class MerchantRequestSuspend(models.Model):

    _name = 'merchant.request.suspend.line'
    _order = "create_date desc"


    reason = fields.Text('Suspension Reason', required=True, translate=True)
    date = fields.Date('Suspension Date', required=True)
    request_id = fields.Many2one('merchant.request', string='Request Reference', required=True, ondelete='cascade', index=True, copy=False, readonly=True)

class MerchantRequest(models.Model):
    
    _name = 'merchant.request'
    _inherit = ['portal.mixin', 'mail.thread', 'mail.activity.mixin']
    _order = "create_date desc"


    name = fields.Char(string='Request Reference', required=True, copy=False, readonly=True, states={'new': [('readonly', False)]}, index=True, default=lambda self: _('New'), translate=True)
    username = fields.Char('Admin Username', required=True, translate=True)
    username2 = fields.Char('2nd User Name', required=True, translate=True)
    shopname = fields.Char('Shop Name', required=True, translate=True)
    shop_type_id = fields.Many2one('merchant.shop.type', 'Shop Type', required=True)
    plan_id = fields.Many2one('merchant.plan', 'Subscription Plan', required=True)
    email = fields.Char('Admin Email', required=True, translate=True)
    email2 = fields.Char('2nd User Email', required=True, translate=True)
    mobile = fields.Char('Mobile No. ', required=True, translate=True)
    city = fields.Many2one('res.city', 'City', required=True)
    country_id = fields.Many2one('res.country', 'Country', required=True, default=lambda self:self._get_default_country())
    location = fields.Char('Location', required=True)
    location_lat = fields.Char('Location Latitute', translate=True)
    location_lng = fields.Char('Location Longitude', translate=True)
    logo = fields.Binary('Shop Logo', translate=True)
    images_line = fields.One2many('merchant.request.images.line', 'request_id', string='Shop Images', copy=True, auto_join=True)
    invoice_line = fields.One2many('merchant.request.invoice.line', 'request_id', string='Invoices', copy=True, auto_join=True, )
    has_branches =  fields.Boolean('Has Branches?', default=False)

    state = fields.Selection([
        ('new', 'Requested'), 
        ('approved','Approved'), 
        ('progress','Active'), 
        ('reject', 'Rejected'), 
        ('suspend', 'Suspended'),
        ('expire', 'Expired')], default='new', required=True)

    reason = fields.Text('Rejection Reason', translate=True)
    company_id = fields.Many2one('res.company','Company',default=lambda self: self.env.user.company_id)
    partner_ids = fields.One2many('res.partner', 'request_id', string='Partners', copy=True, auto_join=True)
    user_ids = fields.One2many('res.users', 'request_id', string='Users', copy=True, auto_join=True)
    suspend_line = fields.One2many('merchant.request.suspend.line', 'request_id', string='Suspensions', copy=True, auto_join=True)
    expire_date = fields.Date('Expiration Date')
    monthly_txns = fields.Integer('Transactions this month', required=True, default=0)
    remaining_monthly_txns = fields.Integer('Remaining Transactions this month', required=True, default=0)
    
    # Social Links
    social_fb_link = fields.Char('Facebook Link')
    social_gplus_link = fields.Char('Google+ Link')

    # Unused Invoices
    unused_invoice_id = fields.Many2one('account.invoice', 'Unused Invoices')
    description = fields.Text('Description', required=True)

    @api.model
    def _get_default_country(self):
        iraq_country_obj = self.env['res.country'].search([('code','=','IQ')], limit=1)
        if iraq_country_obj:
            return iraq_country_obj.id

    @api.onchange('city')
    def onchange_city(self):
        if self.city and self.city.country_id:
            country_id = self.city.country_id.id
            self.country_id = country_id

    def validate_captcha(self, recaptcha_response):
        url = 'https://www.google.com/recaptcha/api/siteverify'
        values = {
            'secret': '6LcBD5oUAAAAAFyXUwD3E-HzBqteMLnMZrXLngNu',
            'response': recaptcha_response,
        }
        data = urllib.parse.urlencode(values).encode()
        req =  urllib.request.Request(url, data=data)
        response = urllib.request.urlopen(req)
        result = json.loads(response.read().decode())
        if result['success']:
            return True
        else:
            return False


    @api.multi
    def generate_img_urls(self):
        for req_line in self.env['merchant.request.images.line'].search([]):
            if req_line.image and not req_line.image_url:
                img_data = str(req_line.image)
                if len(img_data) % 4:
                        img_data += '=' * (4 - len(img_data) % 4)
                image_url = ImageFilestore().convert(req_line.id, img_data, 'shop')
                req_line.write({'image_url':image_url})
        return 


    def _validate_form(self, vals):
        """
        """
        res = {'field_errors':[]}

        is_admin_email_valid = validate_email(vals.get('email'), check_mx=False, verify=False, debug=False, smtp_timeout=10)
        is_user_email_valid = validate_email(vals.get('email2'), check_mx=False, verify=False, debug=False, smtp_timeout=10)

        if is_admin_email_valid is not True:
            res['field_errors'].append('Invalid Admin Email Address.')

        if is_user_email_valid is not True:
            res['field_errors'].append('Invalid User Email Address.')

        if self.env['merchant.request'].sudo().search([('email','=',vals.get('email'))]):
            res['field_errors'].append('Merchant Admin Email Address already registered with another request.')
    
        if self.env['merchant.request'].sudo().search([('email2','=',vals.get('email2'))]):
            res['field_errors'].append('Merchant Admin Email Address already registered with another request.')

        if not self.env['merchant.shop.type'].sudo().search([('id','=', vals.get('shop_type_id'))]):
            res['field_errors'].append('Invalid Shop Type')

        if not self.env['merchant.plan'].sudo().search([('id','=', vals.get('plan_id'))]):
            res['field_errors'].append('Invalid Plan')
        
        if not self.env['res.city'].sudo().search([('id','=', vals.get('city_id'))]):
            res['field_errors'].append('Invalid City')

        if not self.env['res.country'].sudo().search([('code','=', vals.get('country_id'))]):
            res['field_errors'].append('Invalid Country')

        if not self.validate_captcha(vals.get('g-recaptcha-response')):
            res['field_errors'].append('Invalid Captcha')

        if vals.get('email') == vals.get('email2'):
            res['field_errors'].append('Both emails cannot be same') 

        return res
        

    @api.multi
    def notify_register(self):
        email_template = self.env.ref('merchant.merchant_register_template')
        return email_template.send_mail(self.id, force_send=True, raise_exception=True)
        
    @api.multi
    def notify_action(self):
        email_template = self.env.ref('merchant.merchant_register_email_template_approve_reject')
        return email_template.send_mail(self.id, force_send=True, raise_exception=True)

    @api.multi
    def notify_suspend(self, reason):
        email_template = self.env.ref('merchant.merchant_register_email_template_suspend')
        return email_template.with_context({'reason':reason}).send_mail(self.id, force_send=True, raise_exception=True)

    @api.multi
    def notify_expire(self):
        email_template = self.env.ref('merchant.merchant_register_email_template_expire')
        return email_template.with_context({}).send_mail(self.id, force_send=True, raise_exception=True)

    @api.multi
    def notify_pre_expire(self):
        email_template = self.env.ref('merchant.merchant_register_email_template_pre_expire')
        return email_template.with_context({}).send_mail(self.id, force_send=True, raise_exception=True)

    @api.multi
    def notify_renewed(self,):
        email_template = self.env.ref('merchant.merchant_register_email_template_renewal')
        return email_template.send_mail(self.id, force_send=True, raise_exception=True)
        
    @api.constrains('email')
    def validate_adminemail(self):
        is_valid = validate_email(self.email, check_mx=False, verify=False, debug=False, smtp_timeout=10)
        if is_valid is not True:
            raise ValidationError(_('You can use only valid email address.Email address %s is invalid or does not exit')
                                  % self.email)

        if self.search([('email','=', self.email), ('id','!=', self.id)]) or self.search([('email2','=', self.email2), ('id','!=', self.id)]):
            raise ValidationError(_('The user email address is already registered with other request. '))

    @api.constrains('email2')
    def validate_useremail(self):
        is_valid = validate_email(self.email2, check_mx=False, verify=False, debug=False, smtp_timeout=10)
        if is_valid is not True:
            raise ValidationError(_('You can use only valid email address.Email address %s is invalid or does not exit')
                                  % self.email2)

        if self.search([('email','=', self.email2), ('id','!=', self.id)]) or self.search([('email2','=', self.email2), ('id','!=', self.id)]):
            raise ValidationError(_('The user email address is already registered with other request. '))



    @api.model
    def create(self, vals):
        # if vals.get('location') and (not vals.get('location_lat') or not vals.get('location_lng')):
        #     geolocator = Nominatim(user_agent="mamnon")
        #     location = geolocator.geocode(vals.get('location'))
        #     vals['location_lat'] = location.latitude
        #     vals['location_lng'] = location.longitude
            
        if vals.get('name', _('New')) == _('New'):
            vals['name'] = self.env['ir.sequence'].next_by_code('merchant.request') or _('New')
        res = super().create(vals)
        res.notify_register()
        return res


    @api.multi
    def write(self, vals):
        if vals.get('invoice_id') and self.search([('invoice_id','=',vals.get('invoice_id'))]):
            raise Warning('This Invoice is already registered with another request')

        elif vals.get('invoice_id') and self.env['loyalty.deal'].search([('invoice_id','=',vals.get('invoice_id'))]):
            raise Warning('This Invoice is already registered with another request')

        res = super().write(vals)
        return res
    
    @api.multi
    def approve(self):
        self.write({'state':'approved'})
        merchant_shop_partner = self.register_company()
        self.notify_action()
        self.message_post(body=_('Request Approved by %s') % (self.env.user.name))
        # self.write({'state': 'confirm', 'date_done': time.strftime("%Y-%m-%d %H:%M:%S")})

    @api.multi
    def reject(self, reason=False):
        self.write({
                'state':'reject',
                'reason':reason,
            })
        self.notify_action()
        self.message_post(body=_('Request Rejected by %s') % (self.env.user.name))


    @api.multi
    def suspend(self, reason=False):
        suspension_line_ids = [line.id for line in self.suspend_line]
        new_suspend_line = self.suspend_line.create({'reason':reason, 'date':datetime.datetime.today().strftime('%Y-%m-%d'), 'request_id':self.id, })
        suspension_line_ids.append(new_suspend_line.id)
        self.write({'suspend_line':[(6, 0, suspension_line_ids)], 'state':'suspend'})
        merchant_active_group = self.env.ref('loyalty.group_merchant_active')
        for user in self.user_ids:
            groups_id = [group.id for group in user.groups_id]
            if merchant_active_group.id in groups_id:
                groups_id.remove(merchant_active_group.id)
            user.sudo().write({'groups_id':[(6, 0, groups_id)]})

        related_deals = self.env['loyalty.deal'].search([('merchant_id','in',[x.id for x in self.partner_ids])])
        related_deals.unpublish()
        self.notify_suspend(reason)
        self.message_post(body=_('Merchant Services Suspended by %s') % (self.env.user.name))


    @api.multi
    def resume(self, reason=False):
        self.write({
                'state':'progress',
            })

        merchant_active_group = self.env.ref('loyalty.group_merchant_active')

        for user in self.user_ids.search([('request_id','=',self.id)]):
            groups_id = [group.id for group in user.groups_id]
            if merchant_active_group.id not in groups_id:
                groups_id.append(merchant_active_group.id)
            user.sudo().write({'groups_id':[(6, 0, groups_id)]})

        expire_months = self.plan_id.duration + self.plan_id.free_mnth
        expire_date = (datetime.date.today() + datetime.timedelta(expire_months*365/12)).strftime('%Y-%m-%d')        
        new_tx = self.plan_id.transactions
        self.write({'expire_date':expire_date, 'monthly_txns':0, 'remaining_monthly_txns': new_tx})
        # self._check_clear_unused_invoice(invoice_id=)
        self.notify_renewed()
        self.message_post(body=_('Request Resumed by %s') % (self.env.user.name))


    @api.multi
    def start(self):
        expire_months = self.plan_id.duration + self.plan_id.free_mnth
        expire_date = (datetime.date.today() + datetime.timedelta(expire_months*365/12)).strftime('%Y-%m-%d')
        self.write({
                'state':'progress',
                'expire_date':expire_date,
                'remaining_monthly_txns': self.plan_id.transactions if self.plan_id else 0,
            })

    def register_company(self):
        return self.env['res.partner'].create({
                'company_type':'company',
                'customer':False,
                'supplier':True,
                'request_id': self.id, 
                'name':self.shopname,
                'image':self.logo,
                'street':self.location, 
                'city':self.city.id, 
                'mobile':self.mobile,
                'country_id':self.country_id.id,
                'social_fb_link':self.social_fb_link,
                'social_gplus_link':self.social_gplus_link,
            })

    def register_partner(self, vals):
        """
        Register PArtner
        """
        merchant_admin_group = self.env.ref('loyalty.group_merchant_admin')
        merchant_user_group = self.env.ref('loyalty.group_merchant_user')
        merchant_active_group = self.env.ref('loyalty.group_merchant_active')
        internal_user_group = self.env.ref('base.group_user')
        
        if vals.get('is_admin'):
            groups_id = [merchant_admin_group.id, internal_user_group.id, merchant_active_group.id]
        else:
            groups_id = [merchant_user_group.id, internal_user_group.id, merchant_active_group.id]

        vals.pop('is_admin')
        user = self.env['res.users'].sudo().create(vals)
        user.partner_id.write({
                'image':self.logo,
                'email':vals.get('login'), 
                'supplier':True, 
                'request_id': self.id, 
                'street':self.location, 
                'city':self.city.id, 
                'mobile':self.mobile,
                'social_fb_link':self.social_fb_link,
                'social_gplus_link':self.social_gplus_link,
            })
        
        user.write({'groups_id':[(6, 0, groups_id)], 'request_id': self.id})
        user.action_reset_password()
        return user

    def _check_clear_unused_invoice(self, invoice_id=False):
        """
        Check and Clear Unused Invoice
        """
        if invoice_id and (self.unused_invoice_id.id == invoice_id.id):
            self.unused_invoice_id.write({'is_used':True})
            self.write({'unused_invoice_id':False})

    def validate_and_register_invoice(self, invoice_id, action='new'):
        # TODO :: Check this condition to more optimize is_used = False
        if self.invoice_line.search([('invoice_id','=',invoice_id.id)]):
            return False

        elif invoice_id and self.env['loyalty.deal'].search([('invoice_id','=',invoice_id.id)]):
            return False

        else:
            invoice_line_ids = [line.id for line in self.invoice_line]
            new_invoice_line = self.invoice_line.create({'invoice_id':invoice_id.id, 'action_date':datetime.datetime.today().strftime('%Y-%m-%d'), 'request_id':self.id, 'action': action})
            invoice_line_ids.append(new_invoice_line.id)
            self.write({'invoice_line':[(6, 0, invoice_line_ids)]})
            self._check_clear_unused_invoice(invoice_id=invoice_id)
            return True


    @api.multi
    def reset_monthly_txn(self):
        merchant_requests = self.search([('state','=','progress')])
        for request in merchant_requests:
            new_tx = request.plan_id.transactions
            request.sudo().write({'monthly_txns':0, 'remaining_monthly_txns': new_tx})
            # Logic to log history of the tnxs (If needed)
        print("CRON Executed - All the merchant txns reset")
        return

    @api.multi
    def expire_merchant_pre_notification(self):
        merchant_requests = self.search([('state','=','progress')])
        for request in merchant_requests:
            delta = request.expire_date - datetime.date.today()
            if delta.days == 3:
                request.notify_pre_expire()
            else:
                pass


    def expire(self):
        self.write({'state':'expire'})
        merchant_active_group = self.env.ref('loyalty.group_merchant_active')
        for user in self.user_ids:
            groups_id = [group.id for group in user.groups_id]
            if merchant_active_group.id in groups_id:
                groups_id.remove(merchant_active_group.id)
            user.sudo().write({'groups_id':[(6, 0, groups_id)]})

        related_deals = self.env['loyalty.deal'].search([('merchant_id','in',[x.id for x in self.partner_ids])])
        related_deals.unpublish()
        self.notify_expire()
        self.message_post(body=_('Merchant Services Expired Automatically'))

    @api.multi
    def expire_merchant(self):
        merchant_requests = self.search([('state','=','progress')])
        for request in merchant_requests:
            if request.expire_date == datetime.date.today():
                request.expire()
            else:
                pass


    def _auto_generate_invoices(self):
        """
        Auto Generate Invoices
        """

        if self.partner_ids:
            merchant = self.partner_ids[0]
        else:
            merchant = self.register_company()

        account = merchant.property_account_receivable_id

        values = {'type': 'out_invoice', 'account_id' : account.id, 'partner_id' : merchant.id, 'origin': self.name}

        # Generate Invoice for the merchant
        invoice = self.env['account.invoice'].sudo().create(values)

        # Find Plan Product 
        plan_product_id = self.plan_id.product_id

        # Linking the invoice line to the merchant's invoice created above.
        line_id = self.env['account.invoice.line'].create({
            'name': plan_product_id.name,
            'product_id' : plan_product_id.id,
            'invoice_id': invoice.id,
            'price_unit' : plan_product_id.lst_price,
            'quantity': 1.0,
            'account_id' : plan_product_id.categ_id.property_account_income_categ_id.id,
            'uom_id': plan_product_id.uom_id.id,
        })

        # Assign invoice as unused 
        self.write({'unused_invoice_id':invoice.id})

        return invoice
                

class RejectionReasonWizard(models.TransientModel):

    _name = 'merchant.request.reject.reason.wizard'

    reason = fields.Text('Reason', required=True, translate=True)    
    reason_type = fields.Selection([('reject','Rejected'), ('suspend', 'Suspended')], default=lambda self: self._get_default_reason_type(), required=True)


    @api.model
    def _get_default_reason_type(self):
        return self.env.context.get('reason_type')
        
    @api.multi
    def reject(self):
        merchant_request = self.env['merchant.request'].browse(self.env.context.get('active_id'))
        merchant_request.reject(self.reason)
        return

    @api.multi
    def suspend(self):
        merchant_request = self.env['merchant.request'].browse(self.env.context.get('active_id'))
        merchant_request.suspend(self.reason)
        return


class MerchantRequest(models.Model):
    
    _name = 'merchant.setting'



class ApprovalWizard(models.TransientModel):

    _name = 'merchant.request.approval.wizard'

    

    mer_admin_email = fields.Char('Merchant Admin Email', required=False, default=lambda self: self._get_default_admin_email(),)
    mer_admin_username = fields.Char('Merchant Admin Username', required=False, default=lambda self: self._get_default_admin_name(), translate=True)
    mer_user_email = fields.Char('Merchant User Email', required=False, default=lambda self: self._get_default_user_email(),)
    mer_user_username = fields.Char('Merchant User Username', required=False, default=lambda self: self._get_default_user_name(),)
    invoice_id = fields.Many2one('account.invoice', required=True, default=lambda self: self._get_default_invoice())
    approval_type = fields.Selection([('new','New Registration'), ('renew', 'Renewal')], default=lambda self: self._get_default_approval_type())
    company_id = fields.Many2one('res.partner', string="Related Customer Company", default=lambda self: self._get_default_customer_company())


    @api.model
    def _get_default_invoice(self):
        """
        """
        request = self.env['merchant.request'].browse(self.env.context.get('active_id'))

        if not request.unused_invoice_id:
            unused_invoice = request._auto_generate_invoices()

        else:
            unused_invoice = request.unused_invoice_id
        
        return unused_invoice.id

    @api.model
    def _get_default_admin_email(self):
        request = self.env['merchant.request'].browse(self.env.context.get('active_id'))
        return request.email

    @api.model
    def _get_default_admin_name(self):
        request = self.env['merchant.request'].browse(self.env.context.get('active_id'))
        return request.username
    
    @api.model
    def _get_default_customer_company(self):
        request = self.env['merchant.request'].browse(self.env.context.get('active_id'))
        request_ids = [x.id for x in request.partner_ids if x.company_type=='company']
        if len(request_ids)>0:
            return request_ids[0]
        return False

    def _get_invoice_domain(self, partner_id=False):
        if partner_id:
            invoices = self.env['account.invoice'].sudo().search([('type','=','out_invoice'), ('state','=', 'paid'), ('partner_id','=',partner_id)])
        else:
            invoices = self.env['account.invoice'].sudo().search([('type','=','out_invoice'), ('state','=', 'paid')])
        
        invoice_ids = [invoice.id for invoice in invoices]
        
        # Invoices used in different requests
        deal_invoices_used = [x.invoice_id.id for x in self.env['loyalty.deal'].sudo().search([]) if x.invoice_id]
        tx_request_invoices_used = [x.invoice_id.id for x in self.env['loyalty.extra.txn.request'].sudo().search([]) if x.invoice_id]
        
        if type(self.id).__name__ == 'int':
            merchant_request_invoices_used = [x.invoice_id.id for x in self.env['merchant.request.invoice.line'].sudo().search([('id','!=',self.id)])]
        else:
            merchant_request_invoices_used = [x.invoice_id.id for x in self.env['merchant.request.invoice.line'].sudo().search([])]
        
        invoices_used = list(set(deal_invoices_used+tx_request_invoices_used+merchant_request_invoices_used))

        for invoice_id in invoice_ids:
            if invoice_id in invoices_used:
                invoice_ids.remove(invoice_id)
        return invoice_ids
                

    @api.constrains('invoice_id')
    def validate_invoice_id(self):
        if self.company_id:
            invoices = self.env['account.invoice'].sudo().search([('type','=','out_invoice'), ('state','=', 'paid'), ('partner_id','=',self.company_id.id)])
        else:
            invoices = self.env['account.invoice'].sudo().search([('type','=','out_invoice'), ('state','=', 'paid')])
        invoice_ids = [invoice.id for invoice in invoices]
        
        deal_invoices_used = [x.invoice_id.id for x in self.env['loyalty.deal'].sudo().search([]) if x.invoice_id]
        tx_request_invoices_used = [x.invoice_id.id for x in self.env['loyalty.extra.txn.request'].sudo().search([]) if x.invoice_id]
        if type(self.id).__name__ == 'int':
            merchant_request_invoices_used = [x.invoice_id.id for x in self.env['merchant.request.invoice.line'].sudo().search([('id','!=',self.id)])]
        else:
            merchant_request_invoices_used = [x.invoice_id.id for x in self.env['merchant.request.invoice.line'].sudo().search([])]
            
        invoices_used = list(set(deal_invoices_used+tx_request_invoices_used+merchant_request_invoices_used))
        
        if self.invoice_id.id in invoices_used:
            raise ValidationError(_('This Invoice is already registered with another request.'))

        else:
            pass

    @api.onchange('company_id')
    def onchange_company_id(self):
        invoice_ids = self._get_invoice_domain()
        if self.company_id:
            invoice_ids = self._get_invoice_domain(self.company_id.id)
        return {'domain':{'invoice_id':[('id','in',invoice_ids)]}}


    @api.model
    def _get_default_user_email(self):
        request = self.env['merchant.request'].browse(self.env.context.get('active_id'))
        return request.email2

    @api.model
    def _get_default_user_name(self):
        request = self.env['merchant.request'].browse(self.env.context.get('active_id'))
        return request.username2       

    @api.model
    def _get_default_approval_type(self):
        return self.env.context.get('approval_type')

    @api.multi
    def create_users_and_start_service(self): 
        """
        This method creates the user and starts 
        the service.
        """
        mer_request = self.env['merchant.request'].browse(self.env.context.get('active_id'))

        # Invoice Validation for duplicacy
        if not mer_request.validate_and_register_invoice(action=self.approval_type, invoice_id=self.invoice_id):
            raise Warning(_('Invoice ID is already registered.'))

        # Invoice Validation
        if self.invoice_id.state != 'paid':
            raise Warning(_('Invoice is not paid. Please mark invoice as paid and try again.'))

        if self.approval_type == 'new':
            merchant_admin = mer_request.register_partner({'login':self.mer_admin_email, 'name':mer_request.shopname+' - Admin (%s)' % (self.mer_admin_username), 'is_admin':True, 'parent_id':mer_request.partner_ids[0].id})
            merchant_user = mer_request.register_partner({'login':self.mer_user_email, 'name':mer_request.shopname+' - User (%s)' % (self.mer_user_username), 'is_admin':False, 'parent_id':mer_request.partner_ids[0].id})
            mer_request.start()

        elif self.approval_type == 'renew':
            mer_request.resume()
        
        return

    @api.multi
    def view_invoice(self):
        return {
            'type': 'ir.actions.act_window',
            'name': (_('Pay Invoices')),
            'res_model': 'account.invoice',
            'view_type': 'form',
            'res_id': self.invoice_id.id,
            'view_mode': 'form',
            'view_id': self.env.ref('account.invoice_form').id,
            'target': 'current',
        }



