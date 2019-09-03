# -*- coding: utf-8 -*-
{
    'name': "MAMNON - Loyalty System",

    'category': 'POS',
    'summary': """
        Mamnon Loyalty System""",

    'description': """
        Mamnon Loyalty System consists of features like - 
        a. Deals
        b. Merchants Management
        c. Points Management
        d. Customer Rewarding / Redeemption etc..
    """,
    'author': "ESCO",
    'website': "https://www.escoiq.com",
    'category': 'Uncategorized',
    'version': '0.1',
    'depends': ['base', 'website', 'account','mail', 'contacts', 'product',],
    'data': [
        'data/data.xml',
        'data/ir_sequence_data.xml',
        'wizard/group_activation_wiz.xml',
        'security/security.xml',
        'security/ir.model.access.csv',     
        'views/reward_redeem_view.xml',
        'views/views.xml',
        'views/config.xml',
        'views/template.xml',
        'views/rule_view.xml',
        'views/deal_view.xml',
        'views/service_view.xml',
        'views/customer_register_view.xml',
        'views/email_templates.xml',
        'views/group_view.xml',
        'views/coupon_view.xml',
        'views/settlement_view.xml',
        'views/notifications.xml',
    ],
    'demo': [
        'demo/demo.xml',
    ],
    'application': True,
    'auto_install':True,
}