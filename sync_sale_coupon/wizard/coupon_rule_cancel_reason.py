# -*- coding: utf-8 -*-
# Part of Odoo. See COPYRIGHT & LICENSE files for full copyright and licensing details.

from odoo import api, fields, models

class CouponRuleCancelReason(models.TransientModel):
    _name = "coupon.rule.cancel.reason"
    _description = "Coupon Cancel Reason"

    reason = fields.Text('Reason', required=True)

    def cancel_coupon_rule(self):
        """
            Adds cancellation reason in coupon rule
        """
        coupon_rule_id = self.env['sale.coupon.rule'].browse(self._context.get('active_id'))
        if coupon_rule_id.coupon_ids:
            coupons_to_expire = coupon_rule_id.coupon_ids.filtered(lambda r: r.state != 'used')
            for coupon in coupons_to_expire:
                if not coupon.customer_id:
                    coupon.state = 'cancel'
        coupon_rule_id.cancel_reason = self.reason
        coupon_rule_id.state = 'cancel'

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4: