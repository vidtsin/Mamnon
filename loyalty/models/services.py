# -*- coding: utf-8 -*-


from odoo import models, fields, api, _
from datetime import datetime
from odoo.exceptions import Warning, ValidationError

class ExtraTxnServiceRequest(models.Model):

    _name = 'loyalty.extra.txn.request'

    name = fields.Char(string='Transaction Request Reference', required=True, copy=False, readonly=True, index=True, default=lambda self: _('New'))
    merchant_id = fields.Many2one('res.partner', default=lambda self:self._get_default_merchant_id(), required=True)
    txn_count = fields.Selection([(x, x) for x in range(5000, 20000, 5000)], 'Extra Transaction Count', required=True)
    invoice_id = fields.Many2one('account.invoice', domain=[('state','=','paid')])
    state = fields.Selection([('new','New'), ('in-approval', 'In Approval'), ('approved', 'Approved'), ('reject', 'Rejected')], default='new', required=True)
    reason = fields.Text('Rejection Reason')
    
    @api.model
    def create(self, vals):
        if vals.get('name', _('New')) == _('New'):
            vals['name'] = self.env['ir.sequence'].next_by_code('loyalty.extra.txn.request') or _('New')

        res = super(ExtraTxnServiceRequest, self).create(vals)
        return res

    @api.multi
    def write(self, vals):
        if vals.get('invoice_id'):
            if self.search([('invoice_id','=',vals.get('invoice_id'))]):
                raise Warning('This Invoice is already registered with another request')

            elif self.env['merchant.request.invoice.line'].search([('invoice_id','=', vals.get('invoice_id'))]):
                raise Warning('This Invoice is already registered with another request')

        res = super(ExtraTxnServiceRequest, self).write(vals)
        return res

    def _get_invoice_domain(self, partner_id=False):
        if partner_id:
            invoices = self.env['account.invoice'].sudo().search([('type','=','out_invoice'), ('state','=', 'paid'), ('partner_id','=',partner_id)])
        else:
            invoices = self.env['account.invoice'].sudo().search([('type','=','out_invoice'), ('state','=', 'paid')])
        
        invoice_ids = [invoice.id for invoice in invoices]
        
        # Invoices used in different requests
        deal_invoices_used = [x.invoice_id.id for x in self.env['loyalty.deal'].sudo().search([]) if x.invoice_id]
        if type(self.id).__name__ == 'int':
            tx_request_invoices_used = [x.invoice_id.id for x in self.env['loyalty.extra.txn.request'].sudo().search([('id','!=',self.id)]) if x.invoice_id]
        else:
            tx_request_invoices_used = [x.invoice_id.id for x in self.env['loyalty.extra.txn.request'].sudo().search([]) if x.invoice_id]
        merchant_request_invoices_used = [x.invoice_id.id for x in self.env['merchant.request.invoice.line'].sudo().search([]) if x.invoice_id]
        
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
        
        deal_invoices_used = [x.invoice_id.id for x in self.env['loyalty.deal'].sudo().search([]) if x.invoice_id]
        if type(self.id).__name__ == 'int':
            tx_request_invoices_used = [x.invoice_id.id for x in self.env['loyalty.extra.txn.request'].sudo().search([('id','!=',self.id)]) if x.invoice_id]
        else:
            tx_request_invoices_used = [x.invoice_id.id for x in self.env['loyalty.extra.txn.request'].sudo().search([]) if x.invoice_id]

        merchant_request_invoices_used = [x.invoice_id.id for x in self.env['merchant.request.invoice.line'].sudo().search([])]
        
        invoices_used = list(set(deal_invoices_used+tx_request_invoices_used+merchant_request_invoices_used))
        
        if self.invoice_id.id in invoices_used:
            raise ValidationError(_('This invoice is already registered with another request.'))
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
        return self.env.user.partner_id.parent_id.id
    
    def notify(self, ctx={}):
        email_template = self.env.ref('loyalty.notification_txn_request')
        email_template.sudo().with_context(ctx).send_mail(self.id, force_send=True, raise_exception=True)


    @api.multi
    def approve(self):
        for txn in self:
            if txn.invoice_id:
                if self.search([('invoice_id','=',txn.invoice_id.id), ('id','!=', txn.id)]):
                    raise Warning('This Invoice is already registered with another request.')

                elif self.env['merchant.request.invoice.line'].search([('invoice_id','=', txn.invoice_id.id)]):
                    raise Warning('This Invoice is already registered with another request.')

                else:
                    txns = self.merchant_id.request_id.remaining_monthly_txns + txn.txn_count
                    txn.merchant_id.request_id.write({'remaining_monthly_txns':txns})
                    txn.write({'state':'approved'})
                    txn.notify(ctx={'msg':'Your Transaction Request has been approved. You have received %s more transactions for the month.' % (self.txn_count)})
            else:
                raise Warning('Please select Invoice.')

   


    @api.multi
    def send_for_approval(self):    
        for txn in self:
            txn.write({'state':'in-approval'})
            txn.notify(ctx={'msg':'Your Transaction request has been sent for Approval Request.'})

    def reject(self, reason=False):
        self.write({'state':'reject', 'reason':reason})
        self.notify(ctx={'msg':'Sorry!! Your Transaction request has been Rejected.','reason':reason})


