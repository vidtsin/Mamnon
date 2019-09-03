from odoo import api, fields, models

class CardManagementAction(models.TransientModel):
    _name = 'card.management.view.wizard'
    _description = 'Wizard view for card Assign no customer form'
    
    partner_id=fields.Many2one('res.partner',string='Customer')
    new_card_id = fields.Many2one('card.card',string='New Card', required=True)
    reason_id = fields.Many2one('reason.for.card', string='Reason', required=True)

    @api.multi
    def assign_card(self):
        """It will assign card to the partner"""
        for record in self:
            record.partner_id.sudo().write({'reason_id': record.reason_id.id,'new_card_id':record.new_card_id.id})
        return True



        