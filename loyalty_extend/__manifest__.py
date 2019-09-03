# -*- coding: utf-8 -*-
{
    'name': "MAMNON - Loyalty System Extend Module",

    'category': 'POS',
    'summary': """
        Mamnon Loyalty System Extend""",

    'description': """
        Mamnon Loyalty System Extend..
    """,
    'author': "ESCO",
    'category': 'Uncategorized',
    'version': '0.1',
    'depends': ['base', 'merchant', 'loyalty','product'],
    'data': [
       'data/data.xml',
       'views/marchnat_request.xml',
    ],
    
    'application': True,
}