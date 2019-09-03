# -*- coding: utf-8 -*-
##############################################################################
#
# OdooBro - odoobro.contact@gmail.com
#
##############################################################################

from datetime import datetime, timedelta
from odoo import api, fields, models
from odoo.addons import decimal_precision as dp

class CardHistory(models.Model):
    _name = 'card.history'
    _description = 'Loyalty Card History'
    _order = 'end_date DESC'

    card_id = fields.Many2one(
        string='Card',
        comodel_name='card.card',
        ondelete='cascade',
        required=1)
    start_date = fields.Date(
        string='Start Date')
    end_date = fields.Date(
        string='End Date')
    point_in_period = fields.Float(
        string='Points in Period',
        digits=dp.get_precision('Discount'))
    total_point = fields.Float(
        string='Total Points',
        digits=dp.get_precision('Discount'))
    user_id = fields.Many2one(
        string='Responsibility',
        ondelete='set null',
        comodel_name='res.users')
    type_id = fields.Many2one(
        string='Type',
        comodel_name='card.type',
        required=1)
    partner_id = fields.Many2one('res.partner', 'Customer')
    status = fields.Selection([('draft','Draft'),
                            ('sent_to_printing','Sent to Printing'),
                            ('available_to_distribution','Available'),
                            ('at_merchants','At Merchants'),
                            ('active','Active'),
                            ('terminated','Terminated'),
                            ('lost_or_stolen','Lost Or Stolen'),
                            ('replaced','Replaced')], default='draft', track_visibility='always', index=True)
