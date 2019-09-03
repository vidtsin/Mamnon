# -*- coding: utf-8 -*-
# Part of Odoo. See COPYRIGHT & LICENSE files for full copyright and licensing details.

from odoo import api, fields, models, _
from odoo.exceptions import UserError


class SaleOrder(models.Model):
    _inherit = "sale.order"

    applied_coupon_ids = fields.One2many('sale.coupon', 'sale_order_id', string="Coupons", copy=False)

    @api.multi
    def copy(self, default=None):
        """
            Override method for duplicate SO time remove coupon lines
        """
        order = super(SaleOrder, self).copy(default)
        order.get_coupon_lines().unlink()
        return order

    @api.multi
    def get_coupon_lines(self):
        """
            Get coupon lines
        """
        self.ensure_one()
        return self.order_line.filtered(lambda line: line.is_coupon_line)

    @api.multi
    def check_global_discount_rule(self, new_rule):
        """
            Check whether global discount is applied or not
        """
        self.ensure_one()
        global_discount_applied = self.applied_coupon_ids.mapped('coupon_rule_id').filtered(lambda r: r.reward_type == 'discount' and r.discount_type == 'percentage' and r.discount_apply_on == 'order').ids
        if new_rule.reward_type == 'discount' and new_rule.discount_type == 'percentage'\
             and new_rule.discount_apply_on == 'order' and global_discount_applied:
             return True
        return False

    @api.multi
    def action_confirm(self):
        """
            Override method to send used coupon mail
        """
        res = super(SaleOrder, self).action_confirm()
        template_id = self.env.ref('sync_sale_coupon.email_sale_coupon_used')
        if template_id:
            for rec in self:
                for coupon_id in rec.applied_coupon_ids:
                    template_id.send_mail(coupon_id.id,force_send=True)
        return res


class SaleOrderLine(models.Model):
    _inherit = "sale.order.line"

    is_coupon_line = fields.Boolean('Coupon Line')

    @api.multi
    def unlink(self):
        """
            Override method for remove coupon related lines
        """
        so_lines = self.env['sale.order.line']
        current_ids = so_lines.search([('id', 'in', self.ids)])
        if current_ids:
            for line in self.filtered(lambda line: line.is_coupon_line):
                related_coupons = line.order_id.applied_coupon_ids.filtered(lambda coupon: coupon.coupon_rule_id.reward_line_product_id.id == line.product_id.id)
                for coupon in related_coupons:
                    if coupon.coupon_rule_id.state == 'expired':
                        coupon.write({'state': 'expired'})
                    elif coupon.coupon_rule_id.state == 'cancel':
                        coupon.write({'state': 'cancel'})
                    else:
                        coupon.write({'state': 'new'})
                line.order_id.applied_coupon_ids -= related_coupons
                coupon_rule = self.env['sale.coupon.rule'].search([('reward_line_product_id', '=', line.product_id.id)], limit=1)
                if coupon_rule:
                    so_lines |= line.order_id.order_line.filtered(lambda l: l.product_id.id == coupon_rule.reward_line_product_id.id) - line
        return super(SaleOrderLine, current_ids | so_lines).unlink()

class Product(models.Model):

    _inherit = 'product.product'

class ProductTemplate(models.Model):

    _inherit = 'product.template'

class ProductPriceHistory(models.Model):

    _inherit = 'product.price.history'

class MerchantRequest(models.Model):

    _inherit = 'merchant.request'

    count_coupon_available = fields.Integer('Available Coupons', required=True, default=20)
    count_coupon_generated = fields.Integer('Coupons Generated', required=True, default=0)        

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4: