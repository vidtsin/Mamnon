# -*- coding: utf-8 -*-
from odoo import api, fields, models
from odoo.addons import decimal_precision as dp
from odoo.tools.translate import _


class CardType(models.Model):
    _name = 'card.type'
    _description = 'Loyalty Card Type'
    _order = 'name'

    name = fields.Char(
        string='Type Name',
        required=True)
    period_id = fields.Many2one(
        string='Period',
        comodel_name='card.period',
        required=1)
    categ_id = fields.Many2one(
        string='Category',
        comodel_name='card.category',
        required=1)

    partner_id = fields.Many2one(
        string='Vendor/Supplier',
        comodel_name='res.partner',
        default=lambda self: self.env.ref('cms.res_partner_default_vendor_data').id) #set default vendor
    product_id = fields.Many2one(
        string='Product Name',
        comodel_name='product.product')
    
    @api.multi
    def name_get(self):
        result = []
        for r in self:
            name = u"{} - {}".format(r.name, r.period_id.name)
            result.append((r.id, name))
        return result

    @api.multi
    def _get_next_type(self):
        self.ensure_one()
        args = [('categ_id', '=', self.categ_id.id)]
        type = self.search(args, limit=1, order='seq')
        return type

    @api.model
    def create(self,vals):
        vcard_id = self.env.ref('cms.card_category_vcard').id
        data = {
            'name': vals['name'],
            'uom_id': self.env.ref('uom.product_uom_unit').id,
            'type': 'service' if vals['categ_id'] == vcard_id else 'product',
            'sale_ok': False if vals['categ_id'] == vcard_id else True,
            'purchase_ok': False if vals['categ_id'] == vcard_id else True,
            'tracking':'serial', #add custom
        }
        product_id = self.env['product.product'].create(data)
        card_id = super(CardType, self).create(vals)
        card_id.write({'product_id':product_id.id})
        return card_id

