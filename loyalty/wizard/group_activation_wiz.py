# -*- coding: utf-8 -*-

from datetime import datetime, timedelta
from odoo.exceptions import Warning
from odoo import models, fields, api, _

class LoyaltyGroupActivatePaymentInvoiceLine(models.TransientModel):

    """
    Modal Class for Group Definition
    """
    
    _name =  'loyalty.group.activate.wizard.line'

    def _get_invoice_domain(self):  

        # used_loyalty_invoices_ids = self.env['loyalty.deal']._get_invoice_domain(self.partner_id.id)

        # if self.partner_id:
        #     invoices = self.env['account.invoice'].sudo().search([('type','=','out_invoice'), ('state','=', 'paid'), ('partner_id','=',self.partner_id.id)])
        # else:
        #     invoices = self.env['account.invoice'].sudo().search([('type','=','out_invoice'), ('state','=', 'paid')])
        
        # invoice_ids = [invoice.id for invoice in invoices]
        # group_payment_invoice_ids = [x.invoice_id.id for x in self.env['loyalty.group.payment.invoice.line'].sudo().search([])]
        # invoices_used = list(set(used_loyalty_invoices_ids + group_payment_invoice_ids))
        # res_ids = list(set(invoice_ids) - set(invoices_used))
        return [('id','in', [])]

    payment_id = fields.Many2one('loyalty.group.activate.wizard', string='Payment Reference', required=True, ondelete='cascade', index=True, copy=False, readonly=True)
    invoice_id = fields.Many2one('account.invoice', 'Invoice', required=False, domain=lambda self:self._get_invoice_domain())
    partner_id = fields.Many2one('res.partner', domain=[('supplier','=', True)], required=True)


class LoyaltyGroupActivateWizard(models.TransientModel):
    """
    Modal Class for Group Definition
    """

    _name = 'loyalty.group.activate.wizard'

    
    @api.depends('start_date')
    def _get_expiration(self):
        for group in self:
            active_group = self.env['loyalty.group'].browse(self.env.context.get('active_id'))
            group_age = active_group.duration
            expire_date = group.start_date + timedelta(days=int(group_age))
            group.update({
                    'expire_date':expire_date,
                })

    start_date = fields.Date('Start Date', required=True, default=fields.Date.today())
    expire_date = fields.Date('Expire Date', required=True, compute="_get_expiration")
    invoice_line = fields.One2many('loyalty.group.activate.wizard.line', 'payment_id', string='Payment Lines', copy=True, auto_join=True)

    @api.multi
    def active(self):
        """
        Activate the merchant group.
        """
        if not any([x.invoice_id for x in self.invoice_line]):
            raise Warning(_('Please choose all the invoices.'))

        
        if not all(x.invoice_id.state == 'paid' for x in self.invoice_line):
            raise Warning(_('Some invoices are not paid. Please mark them as paid and try again.'))
            
        ctx = self.env.context

        active_merchant_group = self.env[ctx.get('active_model')].browse(ctx.get('active_id'))

        payment = self.env['loyalty.group.payment.line'].create({
                'start_date':self.start_date, 
                'expire_date':self.expire_date, 
                'group_id':active_merchant_group.id,
            })

        for invoice_line in self.invoice_line:
            self.env['loyalty.group.payment.invoice.line'].create({
                    'invoice_id':invoice_line.invoice_id.id,
                    'partner_id':invoice_line.partner_id.id,
                    'payment_id':payment.id ,
                })

        active_merchant_group.write({'state':'progress', 'unused_invoice_ids':[(6,0,[])]})


    @api.multi
    def view_invoices(self):
        return {
            'type': 'ir.actions.act_window',
            'name': (_('Pay Invoices')),
            'res_model': 'account.invoice',
            'view_type': 'form',
            'domain': [('id', 'in', [x.invoice_id.id for x in self.invoice_line])],
            'view_mode': 'tree',
            'view_id': self.env.ref('account.invoice_tree_with_onboarding').id,
            'target': 'current',
        }