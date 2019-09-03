# -*- coding: utf-8 -*-
##############################################################################
#
# OdooBro - odoobro.contact@gmail.com

from odoo import api, fields, models
from odoo.tools.translate import _

class CardMembership(models.Model):
    _name = 'card.membership'
    _description = 'Card Membership'

    name = fields.Char('Name', required=True)
    code = fields.Char('Code')

class CardCategory(models.Model):
    _name = 'card.category'
    _description = 'Loyalty Card Category'
    _order = 'name'

    name = fields.Char(
        string='Name',
        required=True)
    type_ids = fields.One2many(
        string='Types',
        comodel_name='card.type',
        inverse_name='categ_id')

    _sql_constraints = [
        ('uniq_name', "unique(name)",
         _('Name value has been existed. Please choose another !'))]
