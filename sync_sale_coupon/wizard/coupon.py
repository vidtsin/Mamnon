# -*- coding: utf-8 -*-
# Part of Odoo. See COPYRIGHT & LICENSE files for full copyright and licensing details.

from dateutil.relativedelta import relativedelta
from odoo import api, fields, models

class Coupon(models.TransientModel):
    _name = "coupon.coupon"
    _description = "Coupon"

    generation_type = fields.Selection([('nbr_coupon', 'Number of Coupons'),
                                        ('nbr_customer', 'Number of Customers')], string="Generation Type",
                                        required=True, default='nbr_coupon')
    based_on = fields.Selection([('customer', 'Customers'),
                                 ('customer_categ', 'Customer Category')], default='customer')
    customer_ids = fields.Many2many('res.partner', string='Customers', domain=[('customer', '=', True)])
    categ_ids = fields.Many2many('res.partner.category', string='Customer Categories')
    nbr_coupons = fields.Integer('Number of Coupons', default=1, required=True)

    @api.onchange('based_on')
    def onchange_based_on(self):
        self.customer_ids = []
        self.categ_ids = []


    @api.onchange('categ_ids')
    def onchange_categ_ids(self):
        self.customer_ids = []
        if self.categ_ids:
            customer_ids = self.env['res.partner'].search([('customer', '=', True), ('category_id', 'in', self.categ_ids.ids)])
            self.customer_ids = customer_ids and [(6, 0, customer_ids.ids)] or []


    def prepare_coupon_values(self):
        """
        Prepare coupon values
        """
        context = dict(self._context)
        coupon_rule_id = self.env['sale.coupon.rule'].browse(context.get('active_ids'))
        expiry_date = False
        if coupon_rule_id.duration > 0:
            expiry_date = fields.Date.today() + relativedelta(days=coupon_rule_id.duration)

        coupon_values = {'expiration_date': expiry_date,
                         'coupon_rule_id': coupon_rule_id.id, 
                         'merchant_id':coupon_rule_id.merchant_id.id
                         }
        if context.get('customer'):
            coupon_values.update({'customer_id': context['customer']})
        return coupon_values

    def generate_customer_coupons(self):
        """
            Generate customer specific coupons
        """
        if self.customer_ids:
            for customer in self.customer_ids:
                for nbr in range(0, self.nbr_coupons):
                    vals = self.with_context(customer=customer.id).prepare_coupon_values()
                    self.env['sale.coupon'].create(vals)

    def generate_coupons(self):
        """
            Generate coupons
        """
        if self.generation_type == 'nbr_coupon':
            coupon_rule_id = self.env['sale.coupon.rule'].browse(self.env.context.get('active_ids'))
            merchant_request_id = coupon_rule_id.merchant_id.request_id.sudo()
            if merchant_request_id.count_coupon_available >= self.nbr_coupons:
                for coupon_nbr in range(0, self.nbr_coupons):
                    self.env['sale.coupon'].create(self.prepare_coupon_values())

                merchant_request_id.count_coupon_available = merchant_request_id.count_coupon_available - self.nbr_coupons
                merchant_request_id.count_coupon_generated = merchant_request_id.count_coupon_generated + self.nbr_coupons
            else:
                raise Warning(_('Not enough coupons to generate. Get more coupons.'))
        # else:
        #     self.generate_customer_coupons()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4: