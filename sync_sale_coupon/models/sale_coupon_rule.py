# -*- coding: utf-8 -*-
# Part of Odoo. See COPYRIGHT & LICENSE files for full copyright and licensing details.

from odoo import fields, models, api, _
from odoo.exceptions import UserError, Warning

class SaleCouponRule(models.Model):
    _name = "sale.coupon.rule"
    _inherits = {"product.product": "reward_line_product_id"}
    _inherit = ['mail.thread']
    _description = "Sale Coupon Rule"
    _order = 'id desc'

    @api.multi
    def get_coupon_count(self):
        """
            Get coupon count
        """
        for rec in self:
            rec.coupon_count = rec.coupon_ids and len(rec.coupon_ids.ids) or 0

    @api.multi
    def get_sales_count(self):
        """
            Get sales count
        """
        for rec in self:
            rec.sales_count = len(rec.order_line_ids.mapped('order_id'))

    @api.model
    def _get_default_merchant(self):
        """
        """
        if self.env.user.partner_id.parent_id:
            return self.env['res.users'].sudo().browse(self.env.uid).partner_id.parent_id.id
        else:
            return self.env['res.users'].sudo().browse(self.env.uid).partner_id.id

    product_domain_rule = fields.Char('Based on Products', required=True,
                            states={'draft': [('readonly', False)]}, readonly=True,
                            default=[], track_visibility='onchange',
                            help="On purchase of selected product, reward will be given.")

    # product_domain_rule = fields.Char('Based on Products', required=True,
    #                         states={'draft': [('readonly', False)]}, readonly=True,
    #                         default=[('sale_ok', '=', True)], track_visibility='onchange',
    #                         help="On purchase of selected product, reward will be given.")

    merchant_id = fields.Many2one('res.partner', 
        'Merchant', domain=[('supplier','=', True), ('parent_id','=', False)],  required=True, default=lambda self:self._get_default_merchant())


    min_product_qty = fields.Integer('Min Quantity', states={'draft': [('readonly', False)]},
                            readonly=True, default=1,
                            help="Minimum required product quantity to avail reward.")
    min_amount_rule = fields.Float('Min Purchase Amount', readonly=True,
                            states={'draft': [('readonly', False)]},
                            help="Minimum required amount to avail reward.")
    min_amount_tax_rule = fields.Selection([('tax_include', 'Tax Included'),
                                            ('tax_exclude', 'Tax Excluded')],
                                            string='Tax Rule',
                                            states={'draft': [('readonly', False)]},
                                            readonly=True, default="")
    reward_type = fields.Selection([('discount', 'Discount'),
                                    ('product', 'Product'),
                                    ('free_shipping', 'Free Shipping')],
                                    string='Reward', required=True, readonly=True, track_visibility='onchange',
                                    states={'draft': [('readonly', False)]}, default='discount',
                                    help=""" Discount - Reward will be provided as discount
                                             Product - Free product will be provided as reward
                                             Free Shipping - Shipping charges will be free as reward """)
    reward_line_product_id = fields.Many2one('product.product', string='Reward Line Product',
                                    states={'draft': [('readonly', False)]}, readonly=True, copy=False,
                                    required=True, ondelete='cascade', track_visibility='onchange',
                                    help="Product used in Sales Order to apply discount. Each coupon rule has its own reward product for reporting purpose")
    discount_type = fields.Selection([('percentage', 'Percentage'),
                                      ('fixed_amount', 'Fixed Amount')],
                                      string='Apply Discount',
                                      states={'draft': [('readonly', False)]},
                                      readonly=True, default='percentage', track_visibility='onchange',
                                      help="""Percentage - Entered percentage discount will be provided as reward
                                              Fixed Amount - Entered fixed amount discount will be provided as reward""")
    discount_percentage = fields.Float('Discount', readonly=True,
                                states={'draft': [('readonly', False)]}, default=10.0)
    discount_apply_on = fields.Selection([('order', 'On Order'),
                                          ('cheapest_product', 'On Cheapest Product'),
                                          ('specific_product', 'On Specific Product')],
                                          string='Discount Apply',
                                          states={'draft': [('readonly', False)]},
                                          readonly=True, default="order", track_visibility='onchange',
                                          help="""On Order - Discount will be applied on whole order
                                                  On Cheapest Product - Discount will be applied on the cheapest product of order
                                                  On Specific Product - Discount will be applied on the selected specific product""")
    max_discount_amount = fields.Float('Max Discount Amount', readonly=True,
                                    states={'draft': [('readonly', False)]}, track_visibility='onchange',
                                    help="Maximum discount that can be provided")
    discount_specific_product_id = fields.Many2one('product.product', string='Product',
                                        readonly=True, states={'draft': [('readonly', False)]},
                                        track_visibility='onchange',
                                        help="Selected product will be discounted if the discount is applied")
    discount_fixed_amount = fields.Float('Fixed Amount', readonly=True,
                                    states={'draft': [('readonly', False)]}, default=10.0,
                                    help="The discount in fixed amount")
    reward_product_id = fields.Many2one('product.product', string='Free Product',
                                    readonly=True, track_visibility='onchange',
                                    states={'draft': [('readonly', False)]},
                                    help="Reward Product")
    reward_product_qty = fields.Integer('Quantity', readonly=True, default=1,
                                    states={'draft': [('readonly', False)]}, track_visibility='onchange',
                                    help="Reward Product Quantity")
    reward_product_uom_id = fields.Many2one('uom.uom', string='Unit of Measure',
                                states={'draft': [('readonly', False)]}, readonly=True,
                                related='reward_product_id.uom_id')
    website_id = fields.Many2one('website', string='Website', readonly=True,
                                states={'draft': [('readonly', False)]}, track_visibility='onchange',
                                help="Restrict publishing to this website")
    duration = fields.Integer('Validity Duration',readonly=True, required=True,
                        states={'draft': [('readonly', False)]}, track_visibility='onchange', default=1,
                        help="Validity duration after coupon in generated")
    coupon_ids = fields.One2many('sale.coupon', 'coupon_rule_id', string='Coupons', copy=False,
                            readonly=True, states={'draft': [('readonly', False)]}, track_visibility='onchange')
    coupon_count = fields.Integer(string='Coupons', compute="get_coupon_count", copy=False)
    state = fields.Selection([('draft', 'Draft'),
                              ('open', 'Open'),
                              ('expired', 'Expired'),
                              ('cancel', 'Cancel')], string='Status',
                              states={'draft': [('readonly', False)]},
                              readonly=True, default='draft', track_visibility='onchange')
    cancel_reason = fields.Text(string='Cancellation Reason', track_visibility='onchange')
    note = fields.Text(string='Note', track_visibility='onchange')
    company_id = fields.Many2one('res.company', string='Company', required=True,
                        readonly=True, states={'draft': [('readonly', False)]},
                        default=lambda self: self.env['res.company']._company_default_get('sale.coupon.rule'))
    currency_id = fields.Many2one("res.currency", related='company_id.currency_id', string="Currency", readonly=True, required=True)
    order_line_ids = fields.Many2many('sale.order.line', string='Order Lines')
    promotion_type = fields.Selection([('coupon', 'Coupons'),
                                       ('promotion', 'Promotions')], string='Promotion Type')
    sales_count = fields.Integer('Sales', compute="get_sales_count", copy=False)

    @api.constrains('min_product_qty')
    def check_min_product_qty(self):
        """
            Constrain to check minimum quantity
        """
        if not self.min_product_qty or self.min_product_qty <= 0:
            raise UserError(_('Minimum Quantity should be greater than 0.'))

    @api.constrains('min_amount_rule')
    def check_min_amount_rule(self):
        """
            Constrain to check minimum amount
        """
        if self.min_amount_rule < 0:
            raise UserError(_('Minimum Purchase Amount should be greater than 0.'))

    @api.multi
    def set_open(self):
        """
            Set coupon rule to 'open' state to make it available
        """
        self.ensure_one()
        self.state = 'open'

    @api.multi
    def set_expired(self):
        """
            Set coupon rule and its related coupons to 'expired' state
        """
        self.ensure_one()
        if self.coupon_ids:
            for coupon in self.coupon_ids.filtered(lambda r: r.state != 'used'):
                coupon.state = 'expired'
        self.state = 'expired'

    @api.multi
    def set_draft(self):
        """
            Set coupon rule to 'draft' state
        """
        self.ensure_one()
        self.state = 'draft'

    @api.multi
    def action_view_sales_orders(self):
        """
            View sale orders in which coupon rule is applied
        """
        action = {
            'name': _('Sales Order(s)'),
            'type': 'ir.actions.act_window',
            'res_model': 'sale.order',
            'target': 'current',
        }
        sale_order_ids = self.order_line_ids.mapped('order_id').ids
        if len(sale_order_ids) == 1:
            action['res_id'] = sale_order_ids[0]
            action['view_mode'] = 'form'
        else:
            action['view_mode'] = 'tree,form'
            action['domain'] = [('id', 'in', sale_order_ids)]
        return action

    @api.multi
    def unlink(self):
        """
            Override method to restrict for deletion
        """
        for rec in self:
            if rec.state not in ('draft'):
                raise UserError(_('You can not delete a confirmed Sale Coupon Rule. You must first set it to draft.'))
        return super(SaleCouponRule, self).unlink()

    @api.model
    def create(self, vals):
        """
        Override method to set default values for few fields of products
        """
        merchant_id = vals.get('merchant_id')
        merchant_coupons_rules = self.search([('merchant_id','=', vals.get('merchant_id'))])
        allowed_coupon_rules_per_merchant = self.env['ir.config_parameter'].sudo().get_param('merchant.max_coupon_type_generate')

        if len(merchant_coupons_rules) < int(allowed_coupon_rules_per_merchant):
            vals.update({'type': 'service',
                         'sale_ok': False,
                         'purchase_ok': False,
                         'lst_price': 0.0,
                         'standard_price': 0.0,
                         'website_published': False,
                         'taxes_id': False,})
            return super(SaleCouponRule, self).create(vals)            

        else:
            raise Warning(_('Only %s types of coupons allowed per merchant.') % (allowed_coupon_rules_per_merchant))

    # def check_qty(self, product_ids, min_qty, order):
    def check_qty(self, product_ids, order):
        """
            To check minimum quantity rule
        """
        order_lines = order.order_line.filtered(lambda r: r.product_id.id in product_ids and not r.is_coupon_line)
        if self.reward_type == 'discount':
            if self.discount_apply_on == 'cheapest_product':
                order_lines = order_lines.filtered(lambda r: r.price_subtotal == min(order_lines.filtered(lambda li: not li.is_delivery).mapped('price_subtotal')))
            elif self.discount_apply_on == 'specific_product':
                order_lines = order_lines.filtered(lambda r: self.discount_specific_product_id.id == r.product_id.id)
        # return any(qty >= min_qty for qty in order_lines.mapped('product_uom_qty'))
        return sum(order_lines.mapped('product_uom_qty'))

    def check_order_amount(self, min_amount, tax_rule, order, product_ids):
        """
            To check minimum order amount rule including/excluding tax
        """
        order_lines = order.order_line.filtered(lambda r: r.product_id.id in product_ids and not r.is_coupon_line)
        if tax_rule == 'tax_exclude':
            if self.reward_type == 'discount':
                if self.discount_apply_on == 'cheapest_product':
                    cheapest_product_line = order_lines.filtered(lambda r: r.price_unit == min(order_lines.filtered(lambda li: not li.is_delivery).mapped('price_unit')))
                    if min_amount < sum(cheapest_product_line.mapped('price_subtotal')):
                        return False
                elif self.discount_apply_on == 'specific_product':
                    specific_product_lines = order_lines.filtered(lambda r: self.discount_specific_product_id.id == r.product_id.id)
                    if min_amount < sum(specific_product_lines.mapped('price_subtotal')):
                        return False
                elif order.amount_untaxed < min_amount:
                    return False
            elif order.amount_untaxed < min_amount:
                return False
        elif tax_rule == 'tax_include':
            if self.reward_type == 'discount':
                if self.discount_apply_on == 'cheapest_product':
                    cheapest_product_line = order_lines.filtered(lambda r: (r.price_unit + price_tax) == (min(order_lines.filtered(lambda li: not li.is_delivery).mapped('price_unit')) + r.price_tax))
                    if min_amount < (sum(cheapest_product_line.mapped('price_subtotal')) + sum(cheapest_product_line.mapped('price_tax'))):
                        return False
                elif self.discount_apply_on == 'specific_product':
                    specific_product_lines = order_lines.filtered(lambda r: self.discount_specific_product_id.id == r.product_id.id)
                    if min_amount < (sum(specific_product_lines.mapped('price_subtotal')) + sum(specific_product_lines.mapped('price_tax'))):
                        return False
                elif order.amount_untaxed < min_amount:
                    return False
            elif order.amount_total < min_amount:
                return False
        return True

    def check_conditions(self, order):
        """
            To check coupon rule conditions
        """
        order_lines = order.order_line
        order_line_product_ids = set(order_lines.filtered(lambda r: not r.is_coupon_line).mapped('product_id').ids)
        domain_rule_product_ids = set(self.env['product.product'].search(eval(self.product_domain_rule)).ids)
        valid_product = domain_rule_product_ids.intersection(order_line_product_ids)
        if not valid_product:
            return False
        if self.min_product_qty > 1:
            # valid_qty = self.check_qty(valid_product, self.min_product_qty, order)
            valid_qty = self.check_qty(valid_product, order)
            if not valid_qty or self.min_product_qty > valid_qty:
                return False
        if self.min_amount_rule > 0.0:
            tax_rule = self.min_amount_tax_rule or 'tax_exclude'
            valid_amount = self.check_order_amount(self.min_amount_rule, tax_rule, order, valid_product)
            if not valid_amount:
                return False
        if self.website_id:
            if self._context.get('website') and self._context.get('website') != self.website_id.id:
                return False
        return True

    def prepare_order_line(self, orderline=False, order_id=False):
        """
            To prepare reward line data without combining order lines
        """
        unit_price = orderline and orderline.price_subtotal or (self.discount_fixed_amount if self.discount_fixed_amount < order_id.amount_total else order_id.amount_total)
        if self.reward_type == 'product' and self.reward_product_id:
            unit_price = self.reward_product_id.lst_price
        if self._context.get('order'):
            unit_price = (orderline.price_subtotal * self.discount_percentage)/100
        if self._context.get('cheapest'):
            unit_price = (unit_price * self.discount_percentage)/100
        if self._context.get('free_shipping'):
            unit_price = orderline and orderline.price_subtotal or 0.0
        product_quantity = 1.0
        if self.reward_type == 'product':
            product_quantity = self.reward_product_qty
        unit_price = self.currency_id._convert(unit_price, order_id.currency_id, order_id.company_id, order_id.date_order or fields.Date.today())
        tax_ids = (orderline and orderline.tax_id) and orderline.tax_id.ids or False
        return {
                'product_id': self.reward_line_product_id.id,
                'name': 'Discount Product for %s' % (orderline and orderline.product_id.name or self.reward_line_product_id.name or ''),
                'product_uom_qty': product_quantity,
                'price_unit': unit_price and -unit_price or unit_price,
                'tax_id': tax_ids and [(6, 0, tax_ids)] or False,
                'is_coupon_line': True,
                'order_id': order_id.id,
            }

    def prepare_merge_order_lines(self, orderlines):
        """
            To prepare combined reward line data for order lines
            with same taxes or without taxes
        """
        unit_price = -(sum(orderlines.mapped('price_subtotal')) * self.discount_percentage)/100
        order_id = orderlines[0].order_id
        unit_price = self.currency_id._convert(unit_price, order_id.currency_id, order_id.company_id, order_id.date_order or fields.Date.today())
        tax_ids = orderlines[0].tax_id and orderlines[0].tax_id.ids or False
        return {'product_id': self.reward_line_product_id.id,
                'name': 'Discount Product %s' % orderlines.mapped('tax_id.name') if orderlines.mapped('tax_id.name') else 'Discount Product',
                'product_uom_qty': self.reward_product_qty,
                'price_unit': unit_price,
                'tax_id': tax_ids and [(6, 0, tax_ids)] or False,
                'is_coupon_line': True,
                'order_id': orderlines[0].order_id.id,
                }

    def apply_coupon_discount(self, order):
        """
            To apply reward lines for discount type rewards
        """
        order_lines = order.order_line.filtered(lambda r: not r.is_coupon_line)
        applied_coupons = order.applied_coupon_ids.mapped('coupon_rule_id').filtered(lambda r: r.reward_type == 'product')
        if applied_coupons:
            free_products = applied_coupons.mapped('reward_product_id').ids
            if set(order_lines.mapped('product_id').ids).intersection(set(free_products)):
                order_lines = order_lines.filtered(lambda r: r.product_id.id not in free_products)
        if self._context.get('promotion_ids'):
            order_lines = order_lines.filtered(lambda r: r.product_id.id not in self._context['promotion_ids'].filtered(lambda r: r.reward_type == 'product').mapped('reward_product_id').ids and not r.is_delivery)
        new_lines = []
        if self.reward_type == 'discount':
            if self.discount_type == 'percentage':
                if self.discount_apply_on == 'order':
                    added_line = []
                    no_tax_lines = order_lines.filtered(lambda r: not r.tax_id and r.id not in added_line)
                    if no_tax_lines:
                        new_lines.append(self.prepare_merge_order_lines(no_tax_lines))
                        added_line+=no_tax_lines.ids
                    for line in (order_lines - no_tax_lines):
                        if line.id not in added_line:
                            same_tax_lines = order_lines.filtered(lambda r: r.tax_id and r.tax_id.ids == line.tax_id.ids)
                            if same_tax_lines:
                                new_lines.append(self.prepare_merge_order_lines(same_tax_lines))
                                added_line+=same_tax_lines.ids
                                continue
                            new_lines.append(self.with_context(order=True).prepare_order_line(line, order))
                            added_line.append(line.id)
                elif self.discount_apply_on == 'cheapest_product':
                    cheapest_product_line = order_lines.filtered(lambda r: r.price_unit == min(order_lines.filtered(lambda li: not li.is_delivery).mapped('price_unit')))
                    if cheapest_product_line:
                        new_lines.append(self.with_context(cheapest=True).prepare_order_line(cheapest_product_line[0], order))
                else: # on specific product
                    special_product_line = order_lines.filtered(lambda r: r.product_id.id == self.discount_specific_product_id.id)
                    if special_product_line:
                        new_lines.append(self.with_context(cheapest=True).prepare_order_line(special_product_line, order))
            else:
                new_lines.append(self.with_context(order_id=order).prepare_order_line(orderline=False, order_id=order))
        return new_lines

    def apply_coupon_product(self, order):
        """
            To apply reward lines for free product type rewards
        """
        order_line = order.order_line.filtered(lambda r: r.product_id.id == self.reward_product_id.id and not r.is_coupon_line)
        if not order_line or (self.min_product_qty and order_line and sum(order_line.mapped('product_uom_qty')) < self.min_product_qty):
            return []
            # raise UserError(_("The reward products should be in the sales order lines to apply the discount."))
        return [self.prepare_order_line(order_line, order)]

    def apply_coupon_free_shipping(self, order):
        """
            To apply reward lines for free shipping type rewards
        """
        order_line = order.order_line.filtered(lambda r: r.is_delivery and not r.is_coupon_line and r.price_unit > 0.0)
        return [self.with_context(free_shipping=True, order_id=order).prepare_order_line(order_line or False, order)]

    def apply_coupon_discount_line(self, order):
        """
            To apply reward lines in sale order
        """
        new_order_lines = None
        if self.reward_type == 'product':
            new_order_lines = self.apply_coupon_product(order)
        elif self.reward_type == 'discount':
            new_order_lines = self.apply_coupon_discount(order)
        else: # Free Shipping
            new_order_lines = self.apply_coupon_free_shipping(order)

        if new_order_lines:
            order_line_obj = self.env['sale.order.line']
            discount_amt = 0.0
            for line in new_order_lines:
                discount_amt += line['price_unit']
                if self.max_discount_amount:
                    if (-discount_amt) < self.max_discount_amount:
                        new_line = order_line_obj.create(line)
                        self.write({'order_line_ids': [(4, new_line.id, 0)]})
                    elif (-discount_amt) > self.max_discount_amount:
                        remaining_discount_amt = self.max_discount_amount + (discount_amt-line['price_unit'])
                        remaining_discount_amt = remaining_discount_amt > self.max_discount_amount and self.max_discount_amount or -remaining_discount_amt
                        line.update({'price_unit': remaining_discount_amt})
                        new_line = order_line_obj.create(line)
                        self.write({'order_line_ids': [(4, new_line.id, 0)]})
                        break
                    else:
                        break
                else:
                    new_line = order_line_obj.create(line)
                    self.write({'order_line_ids': [(4, new_line.id, 0)]})

    def get_applicable_rule(self, purchase_amount=0):
        user = self.env.user
        partner = user.partner_id.parent_id or user.partner_id # Current Logged User As merchant
        rules = self.env['sale.coupon.rule'].search([('min_amount_rule','<=', purchase_amount)])
        
        if len(rules) == 1:
            applicable_rule = rules[0]
        elif len(rules) > 1:
            try:
                applicable_rule = sorted(rules, key=lambda x: x.min_amount_rule, reverse=True)[0]
            except:
                return False
        else:
            return False
        
        return applicable_rule

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4: