# -*- coding: utf-8 -*-

from odoo import models, fields, api, _

class MerchantRedeemSettlment(models.Model):

    _name = 'loyalty.settlement'

    merchant_id = fields.Many2one('res.partner', default=lambda self:self._get_default_merchant_id(), required=True)
    
