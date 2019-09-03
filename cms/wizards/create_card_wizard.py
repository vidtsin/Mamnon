# -*- coding: utf-8 -*-
##############################################################################
#
# OdooBro - odoobro.contact@gmail.com
#
##############################################################################
from datetime import datetime, timedelta
from odoo import api, fields, models
import random

class AssignCardUser(models.TransientModel):
    _name = 'assign.card.user'
    _description = 'Assign Card User'

    partner_id = fields.Many2one('res.partner','Customer', required=True)

    @api.multi
    def action_assign_user(self):
        active_id = self._context.get('active_id')
        if active_id:
            Card_id = self.env['card.card'].browse(int(active_id))
            Card_id.partner_id = self.partner_id.id

class CreateCardsWizard(models.TransientModel):
    _name = 'create.card.wizard'
    _description = 'Card Create Wizard'

    quantity = fields.Integer(
          string="Quantity",
          required=True)
    type_id = fields.Many2one(
        string='Type',
        comodel_name='card.type',
        required=1)

    @api.multi
    def button_create(self):
        self.ensure_one()
        cards = []
        Card = self.env['card.card']
        PurchaseOrder = self.env['purchase.order']
        
        if self.quantity > 0:
            if self.type_id and self.type_id.partner_id:
                Purchase_order_line_ids = {
                    'product_id': self.type_id.product_id.id,
                    'name': self.type_id.product_id.name,
                    'product_qty': self.quantity,
                    'date_planned': fields.Datetime.now(),
                    'price_unit' : 00,
                    'product_uom': self.type_id.product_id.uom_id.id,
                        }        
                Purchase = PurchaseOrder.create({
                    'partner_id':self.type_id.partner_id.id,
                    'order_line': [(0,0,Purchase_order_line_ids)]       
                            })
                ref_name = self.env['ir.sequence'].next_by_code('card.card') or _('New')
                for a in range(self.quantity):
                    number = '424' + str(random.randint(0,9)) + str("{:08d}".format(int(self.env['ir.sequence'].get('sequence_seq_card_nb'))))
                    res = [str(number)[y-4:y] for y in range(4, len(number)+4,4)]
                    vals = {
                        'type':'physical',
                        'type_id': self.type_id.id,
                        'name' : res[0]+'-'+res[1]+'-'+res[2],
                        'purchase_id':Purchase.id,
                        'ref_name': ref_name                                                 
                    }
                    cards.append(Card.create(vals).id)
        return {
            'name': 'New Card Sires ',
            'type': 'ir.actions.act_window',
            'res_model': 'card.card',
            'view_type': 'form',
            'view_mode': 'tree,form',
            'target': 'current',
            'context': {},
            'domain': [('id', 'in', cards)],
        }
        return True
