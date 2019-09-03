# -*- coding: utf-8 -*-
from odoo import api, fields, models
from odoo.addons import decimal_precision as dp
from odoo.tools.translate import _

class PurchaseOrder(models.Model):
    _inherit = 'purchase.order'

    card_lines = fields.One2many('card.card','purchase_id','Cards Line')

class ProductTemplate(models.Model):
	_inherit = "product.template"

	service_to_purchase = fields.Boolean("Purchase Automatically",help="If ticked, each time you sell this product through a SO, a RfQ is automatically created to buy the product. Tip: don't forget to set a vendor on the product.")