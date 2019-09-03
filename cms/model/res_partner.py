# -*- coding: utf-8 -*-
import random
from datetime import datetime

from odoo import api, fields, models, _
from odoo.addons import decimal_precision as dp
from odoo.exceptions import Warning, ValidationError


class ReasonForCard(models.Model):
    _name = 'reason.for.card'
    _description = 'Reason For Card'

    name = fields.Char('Name', required=True)

class ResPartner(models.Model):
    _inherit = 'res.partner'

    card_no_id = fields.Many2one('card.card','Card #NO.')
    card_history_lines = fields.One2many('card.history','partner_id','Card History')
    new_card_id = fields.Many2one('card.card','New Card')
    reason_id = fields.Many2one('reason.for.card','Reason')
    card_type_id = fields.Many2one('card.type','Card Type')
    card_id_dup = fields.Char('Mamnon Card Number DUP')
    phone_dup = fields.Char()
    security_check = fields.Char(compute="_get_check_security")

    @api.model
    def create(self, val):
        if 'customer' in val and val['customer']:
            val['card_type_id'] = self.env.ref('cms.card_type_virtual_card').id
        res = super(ResPartner, self).create(val)
        if res.customer:
            res.action_new_card()
        return res
    
    @api.multi
    def write(self, val):
        if 'customer' in val and val['customer']:
            val['card_type_id'] = self.env.ref('cms.card_type_virtual_card').id
        res = super(ResPartner, self).write(val)
        if val.get('new_card_id'):
            if not val.get('reason_id'):
                raise Warning(_('''Error! please define reason...without reason you can change new card!!!'''))
            else:
                self.sudo().action_assign_new_card()
        if 'customer' in val and val['customer']:
            self.sudo().action_new_card()
        return res

    @api.multi
    def action_assign_new_card(self):
        #for replaced card
        if self.card_no_id:
            self.card_no_id.state = 'replaced'
            self.card_no_id.partner_id = False
            self.card_no_id.add_history()

        if self.new_card_id:
            #for new assigned card allot details changed
            self.new_card_id.state = 'active'
            self.new_card_id.partner_id = self.id

        
        #for assign new card to customer
        self.card_no_id = self.new_card_id.id
        self.card_type_id = self.new_card_id.type_id.id
        self.card_no_id.add_history()
        self.new_card_id = False
        self.reason_id = False
        return True


    @api.multi
    def action_new_card(self):
        Card = self.env['card.card']
        number = '414' + str(random.randint(0,9)) + str("{:08d}".format(int(self.env['ir.sequence'].get('sequence_seq_card_nb'))))
        res = [str(number)[y-4:y] for y in range(4, len(number)+4,4)]
        ir_sequence = self.env['ir.sequence']
        vals = {
            'type':'virtual',
            'type_id': self.card_type_id.id,
            'name' : res[0]+'-'+res[1]+'-'+res[2],
            'active':'active',
            'partner_id':self.id,
            'ref_name': ir_sequence.next_by_code('card.card') or _('New')
        }
        Card_id = Card.sudo().create(vals)
        Card_id.action_active()
        self.card_no_id = Card_id.id
    
    @api.model
    def _auto_generated_data(self):
        for data in self.search(['|',('phone_dup','=',False),('card_id_dup','=',False)]):
            data.write({'phone_dup' : data.phone,'card_id_dup' : data.card_id})
            
    @api.one 
    def _get_check_security(self):        
        res_user = self.env['res.users'].search([('id', '=', self._uid)])
        if res_user.has_group('loyalty.group_merchant_admin') or res_user.has_group('loyalty.group_merchant_user'):
            # if self.card_id:
            #     masking_number = "*" * (len(self.card_id) - 4) + self.card_id[-4:]
            #     mask = "'" + masking_number + "'"
            #     self._cr.execute('update res_partner set card_id=%s WHERE id=%s' % (mask, self.id))
            if self.phone:
                phone_masking = "*" * (len(self.phone) - 4) + self.phone[-4:]
                mask_phone = "'" + phone_masking + "'" 
                self._cr.execute('update res_partner set phone=%s WHERE id=%s' % (mask_phone, self.id))
        else: 
            if self.self.card_id_dup:
                without_mast = "'" + self.card_id_dup + "'"
                self._cr.execute('update res_partner set card_id=%s WHERE id=%s' % (without_mast, self.id))
            if self.phone_dup:
                without_mast = "'" + self.phone_dup + "'"
                self._cr.execute('update res_partner set phone=%s WHERE id=%s' % (without_mast, self.id))
    


    @api.multi
    def action_card_history(self):
        return {
                'name': _('Card History : ' + self.name),
                'view_type': 'form',
                'view_mode': 'tree,form',
                'res_model': 'card.history',
                'domain': [('partner_id', 'in', self.ids)],
                'type': 'ir.actions.act_window',
                }