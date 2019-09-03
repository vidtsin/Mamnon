# -*- coding: utf-8 -*-
{
    'name': 'Card Management System',
    'version': '1.1',
    'category': 'Uncategorized',
    'description': """
        Manage loyalty card
    """,
    'author': 'ESCO',
    'website': 'www.escoiq.com',
    'depends': [
        'stock', 'sale','sale_management','purchase','account',
        'loyalty','merchant', 
    ],
    'data': [
        'security/ir.model.access.csv',
        'security/security.xml',
        #Data File
        'data/ir_rule_data.xml',
        'data/ir_sequence_data.xml',
        # 'data/data.xml',
        'data/res_partner_data.xml',
        'data/card_category_data.xml',
        'data/card_period_data.xml',
        'data/card_type_data.xml',
        'data/stock_picking_type_data.xml', 
        'data/config_data.xml',
        #Wizard
        'wizards/card_process_wizard.xml',
        'wizards/create_card_wizard.xml',
        'wizards/card_assign_to_merchant_wizard.xml',
        'wizards/card_management_wizard.xml',
        #Views
        'views/card_period_view.xml',
        'views/card_category_view.xml',
        'views/card_type_view.xml',
        'views/card_card_view.xml',
        'views/purchase_order.xml',
        'views/marchnat_request.xml',
        'views/res_partner.xml',
        'menu/card_menu.xml',
        'views/reason_for_card.xml',
        'views/stock_move.xml',
    ],
    'installable': True,
    'application': True,
    'pre_init_hook':'configure_cms_settings',
}
