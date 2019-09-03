# -*- coding: utf-8 -*-
# Part of Odoo. See COPYRIGHT & LICENSE files for full copyright and licensing details.

import random
import string
from odoo import fields, models, api, _
from datetime import date
from dateutil.relativedelta import relativedelta
from odoo.exceptions import Warning

class SaleCoupon(models.Model):
    _name = "sale.coupon"
    _inherit = ['mail.thread']
    _description = "Sale Coupon"
    _rec_name = "code"
    _order = 'id desc'

    merchant_id = fields.Many2one('res.partner', 'Merchant', domain=[('supplier','=', True), ('parent_id','=', False)],  required=True)
    code = fields.Char('Code', readonly=True, required=True, copy=False)
    state = fields.Selection([('new', 'Valid'),
                              ('used', 'Consumed'),
                              ('expired', 'Expired'),
                              ('cancel', 'Cancelled')], string='Status', required=True, default='new', copy=False)
    expiration_date = fields.Date('Expiration Date', copy=False)
    sale_order_id = fields.Many2one('sale.order', string="Applied on Order",
                            help="Sale Order on which coupon code is applied", copy=False)
    customer_id = fields.Many2one('res.partner', string="For Customer", copy=False)
    coupon_rule_id = fields.Many2one('sale.coupon.rule', 'Coupon Rule', copy=False)

    @api.model
    def create(self, vals):
        """
            Override method to send mail to customers for coupons
        """
        code = ''.join(random.choice(string.ascii_uppercase + \
                    string.digits) for _ in range(20))
        vals.update({'code': code})
        res = super(SaleCoupon, self).create(vals)
        if res.customer_id:
            template_id = self.env.ref('sync_sale_coupon.email_sale_coupon')
            template_id.sudo().send_mail(res.id,force_send=True)
        return res

    @api.multi
    def action_coupon_send(self):
        """
            Manually send mail to customers for coupons
        """
        self.ensure_one()
        try:
            template_id = self.env.ref('sync_sale_coupon.email_sale_coupon')
        except ValueError:
            template_id = False
        try:
            compose_form_id = self.env.ref('mail.email_compose_message_wizard_form')
        except ValueError:
            compose_form_id = False
        ctx = {
            'default_model': 'sale.coupon',
            'default_res_id': self.ids[0],
            'default_use_template': bool(template_id),
            'default_template_id': template_id.id,
            'default_composition_mode': 'comment',
            'force_email': True
        }
        return {
            'type': 'ir.actions.act_window',
            'view_type': 'form',
            'view_mode': 'form',
            'res_model': 'mail.compose.message',
            'views': [(compose_form_id.id, 'form')],
            'view_id': compose_form_id.id,
            'target': 'new',
            'context': ctx,
        }

    @api.multi
    def expire_coupon(self):
        """
        Manually expire coupons
        """
        for rec in self.search([('state', '=', 'new')]):
            if rec.expiration_date and rec.expiration_date < fields.Date.today():
                rec.state = 'expired'
                # TODO: ADD Notify to customer if any.

    @api.multi
    def delete_old_coupon(self):
        """
        Deletes the old expired coupons
        """
        for rec in self.search([('state', 'in', ['expired','cancel'])]):
            six_months_back_date = date.today() - relativedelta(months=+6)
            if rec.write_date.date() < six_months_back_date:
                rec.sudo().unlink()


class RewardCouponsWizard(models.TransientModel):

    _name = 'loyalty.reward.coupon.wizard'


    @api.depends('purchase_amount')
    def _get_coupon_rule(self):
        for reward_wiz in self:
            coupon_rule_id = coupon_id = False
            if reward_wiz.purchase_amount:
                coupon_rule = reward_wiz.coupon_rule_id.get_applicable_rule(reward_wiz.purchase_amount)
                
                if coupon_rule:
                    coupon_rule_id = coupon_rule.id
                    if len([x for x in coupon_rule.coupon_ids if not x.customer_id]) > 0:
                        coupon_id = [x for x in coupon_rule.coupon_ids if not x.customer_id][0].id
                    else:
                        raise Warning(_('No Coupon remaining for this coupon rule type.'))
                
                else:
                    raise Warning(_('No Coupon Rules found for this criteria.'))

            reward_wiz.update({
                    'coupon_rule_id':coupon_rule_id,
                    'coupon_id':coupon_id,
                })

    purchase_amount = fields.Monetary(string='Purchase Amount')
    currency_id = fields.Many2one('res.currency', required=True, default=lambda self:self._get_default_currency())    
    coupon_rule_id = fields.Many2one("sale.coupon.rule", 'Coupon Rule', compute="_get_coupon_rule")
    coupon_id = fields.Many2one("sale.coupon", 'Coupon', compute="_get_coupon_rule")

    @api.model
    def _get_default_currency(self):
        return self.env['res.partner'].browse(self.env.context.get('active_id')).company_id.currency_id.id

    @api.multi
    def reward(self):
        user = self.env.user
        customer = self.env['res.partner'].browse(self.env.context.get('active_id'))
        merchant = user.partner_id.parent_id or user.partner_id # Current Logged merchant
        if self.coupon_id and self.coupon_rule_id:
            if not self.coupon_id.customer_id:
                self.coupon_id.write({
                        'customer_id':customer.id,
                    })
            else:
                raise Warning(_('Coupon already has a customer.'))
            
            msg = 'Your account has been rewarded with coupon - "%s" with code (%s) for your purchase of %s %s at Merchant - %s' % (self.coupon_rule_id.name, self.coupon_id.code, self.currency_id.symbol, self.purchase_amount, merchant.name)
            
            data = {
                'purchase_amount': self.purchase_amount,
                'currency' : self.currency_id.symbol,
                'merchant_name': merchant.name,
                'coupon_id':self.coupon_id,
            }

            # TODO :: Work on the Notifications for this
            # customer.sudo().notify(notify_type="reward_coupon", msg=msg, sms=False, email=True, push=True, data=data)
            return            
        else:
            raise Warning(_('No points to reward. Please check your earning rules.'))


class Partner(models.Model):

    _inherit = 'res.partner'

    coupon_ids = fields.One2many('sale.coupon', 'customer_id', string="Coupons")


class ExtraCouponRequest(models.Model):

    _name = 'loyalty.extra.coupon.request'

    name = fields.Char(string='Coupon Request Reference', required=True, copy=False, readonly=True, index=True, default=lambda self: _('New'))
    merchant_id = fields.Many2one('res.partner', default=lambda self:self._get_default_merchant_id(), required=True, domain=[('parent_id','=', False), ('supplier','=', True)])
    coupon_count = fields.Selection([(x, x) for x in [100, 200, 500, 750, 1000]], 'Extra Coupon Count', required=True)
    invoice_id = fields.Many2one('account.invoice')
    state = fields.Selection([('new','New'), ('in-approval', 'In Approval'), ('approved', 'Approved'), ('reject', 'Rejected')], default='new', required=True)
    reason = fields.Text('Rejection Reason')

    @api.model
    def create(self, vals):
        if vals.get('name', _('New')) == _('New'):
            vals['name'] = self.env['ir.sequence'].next_by_code('loyalty.extra.coupon.request') or _('New')

        res = super(ExtraCouponRequest, self).create(vals)
        return res

    @api.model
    def _get_default_merchant_id(self):
        return self.env.user.partner_id.parent_id.id


    @api.multi
    def send_for_approval(self):    
        for coupon_req in self:
            coupon_req.write({'state':'in-approval'})
            # TODO :: Notify if needed
            # coupon_req.notify(ctx={'msg':'Your Coupon request has been sent for Approval Request.'})

    @api.multi
    def approve(self):
        for coupon_req in self:
            if not coupon_req.invoice_id:
                raise Warning(_('No Invoices found. Click "Generate Invoice" to generate invoice for the request.'))
            
            else:
                if coupon_req.invoice_id.state != 'paid':
                    raise Warning(_('Invoice is not paid.'))
                
                else:
                    new_count = coupon_req.merchant_id.request_id.count_coupon_available + coupon_req.coupon_count
                    coupon_req.merchant_id.request_id.write({'count_coupon_available':new_count})
                    coupon_req.write({'state':'approved'})
                    # coupon_req.notify(ctx={'msg':'Your Transaction Request has been approved. You have received %s more transactions for the month.' % (self.txn_count)})

    @api.multi
    def generate_invoice(self):
        if not self.invoice_id:                
            merchant = self.merchant_id
                
            account = merchant.property_account_receivable_id

            values = {'type': 'out_invoice', 'account_id' : account.id, 'partner_id' : merchant.id, 'origin': self.name}

            # Generate Invoice for the merchant
            invoice = self.env['account.invoice'].sudo().create(values)
            
            # Find Product 
            product_id = self.env.ref("sync_sale_coupon.product_extra_coupons")

            if not product_id:
                raise Warning(_('No Extra Coupon Request Products found.'))
            
            # Linking the invoice line to the merchant's invoice created above.
            line_id = self.env['account.invoice.line'].create({
                'name': product_id.name,
                'product_id' : product_id.id,
                'invoice_id': invoice.id,
                'price_unit' : product_id.lst_price,
                'quantity': 1.0,
                'account_id' : product_id.categ_id.property_account_income_categ_id.id,
                'uom_id': product_id.uom_id.id,
            })

            # # Assign invoice as unused 
            self.write({'invoice_id':invoice.id})

    def reject(self, reason=False):
        if not self.reason:
            raise Warning(_('Please enter reason of rejection.'))
        else:
            self.write({'state':'reject'})
            # self.notify(ctx={'msg':_('Sorry!! Your Transaction request has been Rejected.'), 'reason': self.reason})



# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:


    