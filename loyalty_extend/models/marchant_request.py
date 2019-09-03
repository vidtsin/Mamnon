# -*- coding: utf-8 -*-


from odoo import models, fields, api, _
from datetime import datetime



class LoyaltyDealType(models.Model):

	_inherit = 'loyalty.deal.type'
	
	# @api.model
	# def create(self, vals):
	# 	self.env['product.product'].create({'name': vals.get('name'),
	# 	    'type': 'service'})
	# 	res = super(LoyaltyDealType, self).create(vals)
	# 	return res 

	@api.multi
	def write(self, vals):
		if vals.get('name'):
			product_search = self.env['product.product'].search([('name','=',self.name)])
			if vals.get('name'):
				product_search.write({'name' : vals.get('name')})
		res = super(LoyaltyDealType, self).write(vals)
		return res

class MerchantPlan(models.Model):

	_inherit = 'merchant.plan'

	# @api.model
	# def create(self, vals):
	# 	self.env['product.product'].create({'name': vals.get('name'),
	# 	    'price': vals.get('price'),
	# 	    'type': 'service',
	# 	    })
	# 	res = super(MerchantPlan, self).create(vals)
	# 	return res 

	@api.multi
	def write(self, vals):
		if vals.get('name') or vals.get('price'):
			product_search = self.env['product.product'].search([('name','=',self.name)])
			if vals.get('name'):
				product_search.write({'name' : vals.get('name')})
			else:
				product_search.write({'lst_price' : vals.get('price')}) 	
		res = super(MerchantPlan, self).write(vals)
		return res

class MerchantRequest(models.Model):

	_inherit = 'merchant.request'

	is_already_invoice = fields.Boolean(sting="Is Invoiced")
	invoice_id = fields.Many2one('account.invoice')

	@api.model
	def _auto_generated_invoice(self):
		for data in self.search([('state','=','approved'),('is_already_invoice','=',False)]):
			
			inv_context = {
				'type': 'out_invoice',
				'default_currency_id': data.company_id.currency_id.id,
				'default_company_id': data.company_id.id,
				'company_id': data.company_id.id,
			}

			partner_id = self.env['res.partner'].search([('name','=',data.shopname)])
			account_id = partner_id.property_account_receivable_id.id

			values = {
				'type': 'out_invoice',
				'currency_id': data.company_id.currency_id.id,
				'company_id': data.company_id.id,
				'account_id' : account_id,
				'partner_id' : partner_id.id,
			}
			invoice_id = self.env['account.invoice'].with_context(inv_context).create(values)
			data.write({'invoice_id' : invoice_id.id,'is_already_invoice' : True})

			product_id = self.env['product.product'].search([('name','=',data.plan_id.name)])
			if not product_id:
				product_id = self.env['product.product'].create({'name' : data.plan_id.name, 'lst_price' : data.plan_id.price})
			
			line_id = self.env['account.invoice.line'].create({'name': product_id.name,
					'product_id' : product_id.id,
					'invoice_id': invoice_id.id,
					'price_unit': data.plan_id.price,
					'quantity': 1.0,
					'account_id' : product_id.categ_id.property_account_income_categ_id.id,
					'uom_id': product_id.uom_id.id
				})
