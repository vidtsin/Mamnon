# -*- coding: utf-8 -*-


from odoo import models, fields, api, _
from datetime import datetime

class Account(models.Model):
    
    _inherit = 'account.invoice'

    is_used = fields.Boolean('Is Used', default=False)


    

class account_abstract_payment(models.AbstractModel):

    _inherit = "account.abstract.payment"

    journal_id = fields.Many2one('account.journal', string='Payment Journal', required=True, domain=[('type', 'in', ('cash','bank'))])
