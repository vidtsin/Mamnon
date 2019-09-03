# -*- coding: utf-8 -*-


from odoo import models, fields, api, _
from datetime import datetime

class FAQCategory(models.Model):
    
    _name = 'loyalty.faq.category'

    name = fields.Char('FAQ Category Name', required=True)

class FAQ(models.Model):
    
    _name = 'loyalty.faq'
    _rec_name = 'question'

    category_id = fields.Many2one('loyalty.faq.category', 'FAQ Category', required=True)
    question = fields.Text('Question', required=True, translate=True)
    answer = fields.Text('Answer', required=True, translate=True)