# -*- coding: utf-8 -*-

from odoo.exceptions import Warning
from odoo import models, fields, api, _
from datetime import datetime, timedelta


class LoyaltyGroupPaymentInvoiceLine(models.Model):

    """
    Modal Class for Group Definition
    """
    
    _name = 'loyalty.group.payment.invoice.line'

    payment_id = fields.Many2one('loyalty.group.payment.line', string='Payment Reference', required=True, ondelete='cascade', index=True, copy=False, readonly=True)
    invoice_id = fields.Many2one('account.invoice', 'Invoice', required=True)
    partner_id = fields.Many2one('res.partner', domain=[('supplier','=', True)], required=True)


class LoyaltyGroupPaymentLine(models.Model):

    """
    Modal Class for Group Definition
    """
    
    _name = 'loyalty.group.payment.line'

    group_id = fields.Many2one('loyalty.group', string='Group Reference', required=True, ondelete='cascade', index=True, copy=False, readonly=True)
    start_date = fields.Date('Start Date', required=True)
    expire_date = fields.Date('Expire Date', required=True)
    invoice_line = fields.One2many('loyalty.group.payment.invoice.line', 'payment_id', string='Payment Lines', copy=True, auto_join=True)


class LoyaltyGroup(models.Model):

    """
    Modal Class for Group Definition
    """    
    _name = 'loyalty.group'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _rec_name = 'name'

    def _get_merchant_domain(self):
        merchant_company_ids = [partner.id for partner in self.env['res.partner'].search([('supplier','=',True)]) if not partner.parent_id]
        return [('id','in', merchant_company_ids)]

    @api.depends('payment_line.expire_date')
    def _compute_expire_date(self):
        """
        Compute Expire Date based on last payment line
        """
        for group in self:
            if group.payment_line:
                last_payment_line = group.payment_line[-1]
                group.update({
                        'expire_date':last_payment_line.expire_date,
                    })

    name = fields.Char(string='Order Reference', required=True, copy=False, readonly=True, index=True, default=lambda self: _('New'))
    merchant_ids = fields.Many2many('res.partner', 'merchant_group_rel', 'group_id', 'merchant_id', domain=lambda self:self._get_merchant_domain(), required=True)
    payment_line = fields.One2many('loyalty.group.payment.line', 'group_id', string='Payment Lines', copy=True, auto_join=True)
    duration = fields.Selection([
        (7, '1 Week'),
        (14,'2 Weeks'),
        (30,'1 Month')], default=7, string="Duration Type", required=True)
    state = fields.Selection([
        ('new', 'Draft'), 
        ('progress','Active'), 
        ('suspend', 'Suspended'),
        ('expire', 'Expired')], default='new', required=True, track_visibility="onchange")

    expire_date = fields.Date('Expire Date', compute="_compute_expire_date", store=True)
    unused_invoice_ids = fields.Many2many('account.invoice', 'invoice_group_rel', 'group_id', 'invoice_id', 'Unused Invoices')

    @api.model
    def create(self, vals):
        """
        Override create method to explicitly add
        sequence of group name
            @param - self, type(empty recordset)
            @param - vals, type(dict)
        """
        if len(vals.get('merchant_ids')[0][2]) >= 2:
            vals['name'] = self.env['ir.sequence'].next_by_code('loyalty.merchant.group') or _('New')
            res = super(LoyaltyGroup, self).create(vals)
            res.message_subscribe(partner_ids=[partner_id for partner_id in res.merchant_ids.ids])
            # res._auto_generate_invoices()            
            return res
        else:
            raise Warning(_('Please select atleast 2 merchants.'))


    @api.multi
    def write(self, vals):
        """
        """
        res = super(LoyaltyGroup, self).write(vals)
        if vals.get('merchant_ids'):
            self.message_subscribe(partner_ids=[partner_id for partner_id in self.merchant_ids.ids])
        return res

    def _auto_generate_invoices(self, merchant):
        """
        """
        # if not self.unused_invoice_ids:
        #     invoice_ids = []
            # for merchant in self.merchant_ids:

        account = merchant.property_account_receivable_id
        
        values = {
            'type': 'out_invoice',
            'account_id' : account.id,
            'partner_id' : merchant.id,
            'origin':self.name,
        }

        # Generate Invoice for the merchant
        invoice = self.env['account.invoice'].sudo().create(values)           

        # Find Grouping Service Product
        group_services_product = self.env.ref('loyalty.product_grouping_service')

        # Linking the invoice line to the merchant's invoice created above.
        line_id = self.env['account.invoice.line'].create({
            'name': group_services_product.name,
            'product_id' : group_services_product.id,
            'invoice_id': invoice.id,
            'price_unit' : group_services_product.lst_price,
            'quantity': 1.0,
            'account_id' : group_services_product.categ_id.property_account_income_categ_id.id,
            'uom_id': group_services_product.uom_id.id,
        })
        
        # self.write({'unused_invoice_ids':[(6, 0, invoice_ids)]})
        return invoice.id


    def _get_merchants_groups(self, merchant=False):
        """
        This methods takes merchant as argument
        and returns groups beloning to the 
        particular merchant.
        """
        res = []

        for group in self.search([('state','=', 'progress')]):
            if merchant.id in group.merchant_ids.ids:
                res.append(group.id)
        return res

    def _get_merchants_group_partners(self, merchant=False):
        """
        This methods takes merchant as argument
        and returns merchants beloning to the 
        particular merchant.
        """
        res = []

        for group in self.search([('state','=', 'progress')]):
            if merchant.id in group.merchant_ids.ids:
                res.append(group.merchant_ids.ids)

        # Merge the merchant_ids
        if res :
            from functools import reduce
            res = list(set(reduce(lambda a,b: a+b,res)))

        return res

    def _action_open_invoice_wiz(self):
        """
        Action to Open Invoice Wiz
        """
        wizObj = self.env['loyalty.group.activate.wizard'].create({})

        if not self.unused_invoice_ids:
            invoice_ids = []
            
            for merchant in self.merchant_ids:
                
                invoice_id = self._auto_generate_invoices(merchant=merchant)
                invoice_ids.append(invoice_id)

                self.env['loyalty.group.activate.wizard.line'].create({
                    'payment_id': wizObj.id,
                    'partner_id': merchant.id,
                    'invoice_id': invoice_id,
                })

            self.write({'unused_invoice_ids':[(6, 0, invoice_ids)]})

        else:
            for invoice in self.unused_invoice_ids:
                if invoice.partner_id.id in [merchant.id for merchant in self.merchant_ids]:
                    self.env['loyalty.group.activate.wizard.line'].create({
                        'payment_id':wizObj.id,
                        'partner_id':invoice.partner_id.id,
                        'invoice_id':invoice.id,
                    })
                else:
                    raise Warning(_('Invoice not found for the merchant.'))

        return {
            'type': 'ir.actions.act_window',
            'name': (_('Info : Select Invoices')),
            'res_model': 'loyalty.group.activate.wizard',
            'view_type': 'form',
            'view_mode': 'form',
            'res_id' : wizObj.id,
            'view_id': self.env.ref('loyalty.loyalty_group_activate_wizard_form').id,
            'target': 'new',
        }

    @api.multi
    def action_renew(self):
        return self.action_active()


    @api.multi
    def action_active(self):
        """
        This method activates a group
        """
        if self.merchant_ids:
            return self._action_open_invoice_wiz()
        raise Warning (_('Please Select Merchants.'))


    @api.multi
    def action_suspend(self):
        self.write({'state':'suspend'})

    @api.multi
    def action_resume(self):
        """
        This method resumes a group
        """
        if self.merchant_ids:
            return self._action_open_invoice_wiz()
        raise Warning (_('Please Select Merchants.'))


    @api.multi
    
    def action_expire(self):
        self.write({'state':'expire'})

    ##############################################################
    # CRON Related Methods                                       #
    ##############################################################

    @api.multi
    def auto_expire_merchant_group(self):
        """
        Handler for cron job - auto expire merchant
        """
        for group in self.search([('expire_date','>', datetime.today()), ('state','=', 'progress')]):
            group.action_expire()


    ##############################################################
    # Auto Generate Invoice Methods                                       #
    ##############################################################
   