# -*- coding: utf-8 -*-
{
    'name': "Loyalty Rest API",

    'summary': """
        Rest API for Loyalty Module. """,

    'description': """
        Rest API for Loyalty Module for Mamnon IONIC Mobile Application to show 
        - Deals
        - Loyalty Points
        - Offers/Promotions etc..
    """,

    'author': "ESCO",
    'website': "https://www.escoiq.com",

    'category': 'Uncategorized',
    'version': '0.1',
    'depends': ['loyalty'],
    'data': [
        'security/ir.model.access.csv',
        'views/views.xml',
        'views/templates.xml',
    ],
    'demo': [
        'demo/demo.xml',
    ],
    'auto_install':True,
}