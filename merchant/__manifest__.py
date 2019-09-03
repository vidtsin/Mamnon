# -*- coding: utf-8 -*-
{
    'name': "Mamnon Merchant Registeration",

    'summary': """
        Mamnon Loyalty System """,

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
    'depends': ['account', 'loyalty', 'contacts', 'website', 'base', 'google_place_autocomplete'],
    'data': [
        'security/ir.model.access.csv',
        'data/menu.xml',
        'data/cron.xml',
        'data/ir_sequence_data.xml',  
        'views/views.xml',
        'views/templates.xml',
        'views/email_merchant_register.xml',
        'views/config.xml',
    ],
    'demo': [
        'demo/demo.xml',
    ],
}

