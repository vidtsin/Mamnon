# -*- coding: utf-8 -*-
# Part of Odoo. See COPYRIGHT & LICENSE files for full copyright and licensing details.

from odoo import api, fields, models, _
from odoo.exceptions import UserError

class SaleCouponApplyCode(models.TransientModel):
    _name = "sale.coupon.apply.code"
    _description = "Coupon Apply"

    code = fields.Char('Code', required=True)

    @api.multi
    def apply_coupon(self):
        """
            If applied coupon is valid: It is applied on sale order
            Else: raise Error
        """
        order_id = self.env['sale.order'].browse(self._context.get('active_ids'))
        coupon_id = self.env['sale.coupon'].search([('code', '=', self.code),('state', '=', 'new')])
        if coupon_id.expiration_date:
            coupon_id = coupon_id.filtered(lambda r: r.expiration_date >= order_id.date_order.date())
        if coupon_id and coupon_id.customer_id and coupon_id.customer_id != order_id.partner_id:
            raise UserError(_("Coupon Code '%s' is not applicable for %s customer." % (self.code,order_id.partner_id.name)))
        if coupon_id and coupon_id.coupon_rule_id.company_id.id == order_id.company_id.id:
            coupon_rule_id = coupon_id.coupon_rule_id
            if coupon_id.id in order_id.applied_coupon_ids.mapped('coupon_rule_id').mapped('coupon_ids').ids:
                raise UserError(_("A Coupon is already applied for same reward"))
            if order_id.check_global_discount_rule(coupon_id.coupon_rule_id):
                raise UserError(_("Global discounts are not cumulative."))
            valid = coupon_rule_id.check_conditions(order_id)
            if valid:
                coupon_rule_id.apply_coupon_discount_line(order_id)
                coupon_id.write({'state': 'used', 'sale_order_id': order_id.id})
            else:
                raise UserError(_("Coupon Code '%s' is not applicable." % self.code))
        else:
            raise UserError(_("Coupon Code '%s' is invalid." % self.code))

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4: