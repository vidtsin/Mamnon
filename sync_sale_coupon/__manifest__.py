# -*- coding: utf-8 -*-
# Part of Odoo. See COPYRIGHT & LICENSE files for full copyright and licensing details.

{
    'name': 'Sales Coupons',
    'version': '1.0',
    'summary': 'Allows to use discount coupons in sales orders',
    'category': 'Sales',
    'author': 'Synconics Technologies Pvt. Ltd.',
    'website': 'www.synconics.com',
    'description': """
        Integrate coupon mechanism in sales orders.
        
        sale coupon
promotion
coupon
sale
product
product promotion
discount
sales discount
product discount
discount
sales order discount
manufacturing
retailer
retail store
promo code
promotion code
coupon code
customer
customer discount
Reward
shipping
free shipping
fix price discount
percentage discount
promotion validity
minimum purchase
purchase
shoppers
Free product
Free item
free
coupon code validity
POS promotion
POS
POS coupon
POS promotion
POS discount
promotion
special offer
festival
christmas
redemption
claim
expire
redeem
sale promotion
    """,
    'depends': ['sale_management', 'delivery', 'website_sale', 'loyalty', 'product', 'merchant'],
    'data': [
        'security/ir.model.access.csv',
        'security/security.xml',
        'data/coupon_cron.xml',
        'report/sale_coupon_template.xml',
        'data/mail_data.xml',
        'wizard/coupon_views.xml',
        'wizard/sale_coupon_apply_code_views.xml',
        'wizard/coupon_rule_cancel_reason_views.xml',
        'views/sale_coupon_views.xml',
        'views/sale_coupon_rule_views.xml',
        'views/sale_views.xml',
        'views/partner_view.xml',
        'views/extra_coupon_request_view.xml',
        'menu.xml',
    ],
    'images': [
        'static/description/main_screen.jpg',
    ],
    'price': 70.0,
    'currency': 'EUR',
    'auto_install': False,
    'application': True,
    'installable': True,
    'license': 'OPL-1',
}

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
