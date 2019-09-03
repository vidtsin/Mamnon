# -*- coding: utf-8 -*-

import numpy as np
import random, string
from datetime import datetime
from datetime import timedelta
from odoo.exceptions import Warning
from .filestore import ImageFilestore
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError

class LoyaltyDealType(models.Model):
    
    _name = 'loyalty.deal.type'

    name = fields.Char('Deal Name Type', required=True)
    allow_description = fields.Boolean('Description Allowed?', default=False)
    allow_image = fields.Boolean('Offer Image Allowed?', default=False)
    auto_expire = fields.Boolean('Auto Expiration?', default=False)
    need_approval = fields.Boolean('Approval Needed?', default=False, help="Approval required from operation team")
    allow_merchant_request = fields.Boolean('Can Merchant Request?', default=True, help="If checked, then this type of request can be created by merchants.")
    expire_days_count = fields.Integer('Expire in (Days)')
    product_id = fields.Many2one('product.product', string="Related Product")

    @api.model
    def create(self, vals):
        res = super(LoyaltyDealType, self).create(vals)
        if vals.get('need_approval'):
            product = self.env['product.product'].create({'name': vals.get('name') + " Services",
                                'type': 'service',
                            })
            res.write({'product_id':product.id})
        return res

class LoyaltyCategory(models.Model):
    
    _name = 'loyalty.deal.category'
    
    name = fields.Char('Category', required=True, translate=True)
    

class LoyaltyDeal(models.Model):
    
    _name = 'loyalty.deal.rating.line'
    
    @api.constrains('rating')
    def check_rating(self):
        if self.rating % 0.5: 
            raise ValidationError(_('Invalid Rating should be multiple of 0.5 in range 1 to 5'))
        else:
            return True
            
    customer_id = fields.Many2one('res.partner', domain=[('customer','=',True)], required=True)
    review = fields.Text('Review')
    rating = fields.Float(required=True, digits=(2,1))
    deal_id = fields.Many2one('loyalty.deal', 'Deal Reference',required=True, ondelete='cascade', index=True, copy=False, readonly=True)

class LoyaltyDeal(models.Model):
    
    _name = 'loyalty.deal'


    @api.depends('rating_line.rating')
    def _get_average_rating(self):
        for deal in self:
            deal_rating_avg = 0
            if deal.rating_line:
                deal_rating_avg = sum([float(rl.rating) for rl in deal.rating_line]) / len(deal.rating_line)
            deal.update({
                    'rating':deal_rating_avg,
                })

    @api.depends('merchant_id')
    def _get_merchant_shop_category(self):
        for deal in self:
            deal.update({
                    'category_id':deal.merchant_id.request_id.sudo().shop_type_id.id,
                })

    @api.depends('merchant_id')
    def _get_merchant_plan(self):
        for deal in self:
            deal.update({
                    'plan_id':deal.merchant_id.request_id.sudo().plan_id.id,
                })


    name = fields.Char(string='Deal Reference', required=True, copy=False, readonly=True, index=True, default=lambda self: _('New'),translate=True)
    title = fields.Char(string='Title',translate=True)
    description = fields.Text('Description', translate=True)
    type_id = fields.Many2one('loyalty.deal.type', 'Deal Type', required=True)
    category_id = fields.Many2one('merchant.shop.type', 'Shop Category', compute="_get_merchant_shop_category", required=False, readonly=True, store=True)
    merchant_id = fields.Many2one('res.partner', default=lambda self:self._get_default_merchant_id(), domain=[('supplier','=', True), ('parent_id','=', False)], required=True)
    image = fields.Binary("Image")
    image_url = fields.Char("Image URL", translate=False)
    image_url_public = fields.Char("Image Public URL", translate=False)
    publish_date = fields.Date(string='Activation Date')
    expiration_date = fields.Date(string='Expiration Date')
    allow_description = fields.Boolean('Description Allowed?', default=False)
    allow_image = fields.Boolean('Offer Image Allowed?', default=False)
    auto_expire = fields.Boolean('Manual Expire Allowed?', default=False)
    state = fields.Selection([('unpublish','Unpublished'), ('approval','Waiting for Approval'), ('publish','Published'), ('reject', 'Rejected')], default='unpublish', copy=False, required=True)
    need_approval = fields.Boolean('Approval Needed?', store=True, default=False, help="Approval required from operation team")
    is_extra_transaction_needed = fields.Boolean('Extra Transaction Needed ?', default=False)
    extra_transaction_limit = fields.Integer('Extra Transaction Limit')
    invoice_id = fields.Many2one('account.invoice', 'Invoice', required=False, copy=False)
    reason = fields.Text('Rejection Reason', translate=True)
    rating_line = fields.One2many('loyalty.deal.rating.line', 'deal_id', string='Rating Line', copy=True, auto_join=True)
    rating = fields.Float('Average Rating', required=True, default=0, compute="_get_average_rating", digits=(14,1))
    plan_id = fields.Many2one('merchant.plan', 'Merchant Plan', required=True, compute="_get_merchant_plan")


    def _get_invoice_domain(self, partner_id=False):
        """
        Compute Invoice Domain
        """
        if partner_id:
            invoices = self.env['account.invoice'].sudo().search([('type','=','out_invoice'), ('state','=', 'paid'), ('partner_id','=',partner_id)])
        else:
            invoices = self.env['account.invoice'].sudo().search([('type','=','out_invoice'), ('state','=', 'paid')])
        
        invoice_ids = [invoice.id for invoice in invoices]
        
        # Invoices used in different requests
        if type(self.id).__name__ == 'int':
            deal_invoices_used = [x.invoice_id.id for x in self.env['loyalty.deal'].sudo().search([('id','!=',self.id)]) if x.invoice_id]
        else:
            deal_invoices_used = [x.invoice_id.id for x in self.env['loyalty.deal'].sudo().search([]) if x.invoice_id]

        tx_request_invoices_used = [x.invoice_id.id for x in self.env['loyalty.extra.txn.request'].sudo().search([]) if x.invoice_id]
        
        try:
            merchant_request_invoices_used = [x.invoice_id.id for x in self.env['merchant.request.invoice.line'].sudo().search([]) if x.invoice_id]
        except:
            merchant_request_invoices_used = []
        
        invoices_used = list(set(deal_invoices_used+tx_request_invoices_used+merchant_request_invoices_used))

        for invoice_id in invoice_ids:
            if invoice_id in invoices_used:
                invoice_ids.remove(invoice_id)
        return invoice_ids
                

    @api.constrains('invoice_id')
    def validate_invoice_id(self):
        if self.merchant_id:
            invoices = self.env['account.invoice'].sudo().search([('type','=','out_invoice'), ('state','=', 'paid'), ('partner_id','=',self.merchant_id.id)])
        else:
            invoices = self.env['account.invoice'].sudo().search([('type','=','out_invoice'), ('state','=', 'paid')])
        invoice_ids = [invoice.id for invoice in invoices]
        
        if type(self.id).__name__ == 'int':
            deal_invoices_used = [x.invoice_id.id for x in self.env['loyalty.deal'].sudo().search([('id','!=',self.id)]) if x.invoice_id]
        else:
            deal_invoices_used = [x.invoice_id.id for x in self.env['loyalty.deal'].sudo().search([]) if x.invoice_id]

        tx_request_invoices_used = [x.invoice_id.id for x in self.env['loyalty.extra.txn.request'].sudo().search([]) if x.invoice_id]
        merchant_request_invoices_used = [x.invoice_id.id for x in self.env['merchant.request.invoice.line'].sudo().search([])]
        
        invoices_used = list(set(deal_invoices_used+tx_request_invoices_used+merchant_request_invoices_used))
        
        if self.invoice_id.id in invoices_used:
            raise ValidationError(_('Invoice Already used.'))
        else:
            pass

    @api.onchange('merchant_id')
    def onchange_merchant_id(self):
        partner_id = False
        if self.merchant_id:
            partner_id = self.merchant_id.id
        invoice_ids = self._get_invoice_domain(partner_id=partner_id)
        return {'domain':{'invoice_id':[('id','in',invoice_ids)]}}

    @api.model
    def _get_default_merchant_id(self):
        if self.env.user.partner_id.parent_id:
            return self.env['res.users'].sudo().browse(self.env.uid).partner_id.parent_id.id
        else:
            return self.env['res.users'].sudo().browse(self.env.uid).partner_id.id

    @api.model
    def create(self, vals):
        user = self.env['res.users'].sudo()

        if not vals.get('category_id'):
            request_id = user.browse(self.env.uid).partner_id.request_id
            vals['category_id'] = request_id.shop_type_id.id
        
        if not vals.get('category_id') and user.has_group('loyalty.group_merchant_admin'):
            raise Warning(_('Your Merchant Request is not registered. Contact System Admin to link your account with your merchant registeration request.'))
            
        if vals.get('invoice_id'):
            if self.search([('invoice_id','=',vals.get('invoice_id'))]):
                raise Warning(_('This Invoice is already registered with another request'))

            elif self.env['merchant.request.invoice.line'].sudo().search([('invoice_id','=', vals.get('invoice_id'))]):
                raise Warning(_('This Invoice is already registered with another request'))

        if vals.get('name', _('New')) == _('New'):
            vals['name'] = self.env['ir.sequence'].next_by_code('loyalty.deal') or _('New')

        res = super(LoyaltyDeal, self).create(vals)
        if vals.get('image'):
            image_url = ImageFilestore().convert(res.id, res.image, 'deals')
            random_param = ''.join(random.choice(string.ascii_uppercase + string.digits) for _ in range(8)).lower()
            image_url_public = '/api/image/deals/%s?random=%s' % (res.id, random_param)
            res.write({'image_url':image_url, 'image_url_public':image_url_public})
        return res

    @api.multi
    def write(self, vals):
        if vals.get('invoice_id'):
            if self.search([('invoice_id','=',vals.get('invoice_id'))]):
                raise Warning(_('This Invoice is already registered with another request'))

            elif self.env['merchant.request.invoice.line'].search([('invoice_id','=', vals.get('invoice_id'))]):
                raise Warning(_('This Invoice is already registered with another request'))

        if vals.get('image'):
            vals['image_url'] = ImageFilestore().convert(self.id, vals.get('image'), 'deals')
            random_param = ''.join(random.choice(string.ascii_uppercase + string.digits) for _ in range(8)).lower()
            vals['image_url_public'] = '/api/image/deals/%s?random=%s' % (self.id, random_param)
        res = super(LoyaltyDeal, self).write(vals)
        return res


    @api.multi
    def generate_img_urls(self):
        for deal in self.search([]):
            if deal.allow_image and deal.image:
                image_url = ImageFilestore().convert(deal.id, deal.image, 'deals')
                random_param = ''.join(random.choice(string.ascii_uppercase + string.digits) for _ in range(8)).lower()
                image_url_public = '/api/image/deals/%s?random=%s' % (deal.id, random_param)
                deal.write({'image_url':image_url, 'image_url_public':image_url_public})
        return

    # @api.constrains('image')
    # def validate_image_size(self):
    #     if self.image:
    #         ICP = self.env['ir.config_parameter'].sudo()
    #         max_img_size = int(ICP.get_param('merchant.max_img_size'))
    #         img_data = self.image
    #         img_size = (((len(img_data) * 3) / 4) / 1000)
    #         if img_size > float(max_img_size):
    #             raise ValidationError(_('Image Size Too Large. Should not exceed %s KB' % str(max_img_size)))

    @api.onchange('type_id')
    def deal_type_field(self):
        if self.type_id.allow_description == True:
            self.allow_description = True
        else:
            self.allow_description = False

        if self.type_id.allow_image == True:
            self.allow_image = True
        else:
            self.allow_image = False

        if self.type_id.auto_expire == True:
            self.auto_expire = True
        else:
            self.auto_expire = False
        
        if self.type_id.need_approval == True:
            self.need_approval = True
        else:
            self.need_approval = False

    def _get_partner(self):
        user = self.env['res.users'].sudo().browse(self.env.uid)
        partner = user.partner_id
        return partner

    @api.multi
    def unpublish(self):
        for deal in self:
            deal.write({'state':'unpublish'})

    def notify(self, ctx={}):
        email_template = self.env.ref('loyalty.notification_deal_request')
        email_template.sudo().with_context(ctx).send_mail(self.id, force_send=True, raise_exception=True)

    @api.multi
    def publish(self):
        """
        """
        expirable_deal_type_ids = [x.id for x in self.env['loyalty.deal.type'].search([]) if x.auto_expire == True]
        for deal in self:
            expire_date = False
            partner = deal._get_partner()
            if partner.user_ids[0].has_group('loyalty.group_merchant_admin'):
                ad_type_limit = partner._get_publish_ad_limit(ad_typeObj=deal.type_id)
                published_ads = deal.search([('merchant_id','=',partner.id), ('type_id','=',deal.type_id.id), ('state','=', 'publish')])
                if len(published_ads) < ad_type_limit:
                    if deal.type_id.id in expirable_deal_type_ids:
                        expire_date = datetime.now() + timedelta(days=deal.type_id.expire_days_count)
                        expire_date = expire_date.strftime('%Y-%m-%d')
                        publish_date = datetime.now()
                        publish_date= publish_date.strftime('%Y-%m-%d')
                    deal.write({'state':'publish', 'expiration_date':expire_date, 'publish_date':publish_date})
                    deal.notify(ctx={'msg':'Congratulation!! Your Deal request has been Publised.'})            
                else:
                    raise Warning('Limit Exceeded to publish this type of Deal.')
            elif partner.user_ids[0].has_group('loyalty.group_operation') or partner.user_ids[0].has_group('base.group_system'):
                    # Same Logic Here
                    expire_date = datetime.now() + timedelta(days=deal.type_id.expire_days_count)
                    expire_date = expire_date.strftime('%Y-%m-%d')
                    publish_date = datetime.now()
                    publish_date= publish_date.strftime('%Y-%m-%d')
                    deal.write({'state':'publish', 'expiration_date':expire_date, 'publish_date':publish_date}) 
                    try:
                        deal.notify(ctx={'msg':'Congratulation!! Your Deal request has been Publised.'})            
                    except:
                        pass
    
    @api.multi
    def unpublish(self, notify_msg=False):
        for deal in self:
            partner = deal._get_partner()    
            deal.write({'state':'unpublish', 'publish_date':False})
            if notify_msg:
                deal.notify(ctx={'msg':notify_msg})
            else:
                deal.notify(ctx={'msg':'You have unpublished your deal.'})

    @api.multi
    def approve(self):
        for deal in self:
            if deal.invoice_id:
                expire_date = datetime.now() + timedelta(days=deal.type_id.expire_days_count)
                expire_date = expire_date.strftime('%Y-%m-%d')
                deal.write({'state':'publish', 'expiration_date':expire_date})
                deal.notify(ctx={'msg':'Your Deal has been Approved and Published.'})
            else:
                raise Warning('Please select Invoice.')
                
    @api.multi
    def send_for_approval(self):
        for deal in self:
            partner = deal._get_partner()
            deal.write({'state':'approval'})
            deal.notify(ctx={'msg':'Your Deal request has been sent for Approval Request.'})

    def reject(self, reason=False):
        self.write({'state':'reject', 'reason':reason})
        self.notify(ctx={'msg':'Sorry!! Your Deal request has been Rejected.'})


    @api.multi
    def unpublish_expired_extra_deal(self):
        for deal in self.search([('state','=','publish')]):
            if deal.type_id.auto_expire:
                if datetime.now().date() >  deal.expiration_date:
                    deal.unpublish(notify_msg=_('Your deal is published automatically as it\'s service period is expired.'))

    @api.multi
    def generate_invoice(self):
        if not self.invoice_id:                
            merchant = self.merchant_id
                
            account = merchant.property_account_receivable_id

            values = {'type': 'out_invoice', 'account_id' : account.id, 'partner_id' : merchant.id, 'origin': self.name}

            # Generate Invoice for the merchant
            invoice = self.env['account.invoice'].sudo().create(values)

            if not self.type_id.product_id:
                raise Warning(_('Deal Type has no invoice product.'))
            
            # Find Plan Product 
            deal_type_product_id = self.type_id.product_id

            # Linking the invoice line to the merchant's invoice created above.
            line_id = self.env['account.invoice.line'].create({
                'name': deal_type_product_id.name,
                'product_id' : deal_type_product_id.id,
                'invoice_id': invoice.id,
                'price_unit' : deal_type_product_id.lst_price,
                'quantity': 1.0,
                'account_id' : deal_type_product_id.categ_id.property_account_income_categ_id.id,
                'uom_id': deal_type_product_id.uom_id.id,
            })

            # # Assign invoice as unused 
            self.write({'invoice_id':invoice.id})

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

       
class DealServiceCommonRejectionReasonWizard(models.TransientModel):

    _name = 'deal.service.common.reject.reason.wizard'

    reason = fields.Text('Reason', required=True, translate=True) 

    @api.multi
    def reject(self):
        activeObj = self.env[self.env.context.get('active_model')].browse(self.env.context.get('active_id'))
        activeObj.reject(self.reason)
        return
