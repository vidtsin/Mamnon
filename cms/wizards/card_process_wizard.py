# -*- coding: utf-8 -*-

from odoo import api, fields, models

class CardProcessWizard(models.TransientModel):
    _name = 'card.process.wizard'
    _description = 'Card Process Wizard'

    card_ids = fields.Many2many(
        string="Cards",
        comodel_name="card.card")
    is_force = fields.Boolean(
        string='Is Force?')

    @api.model
    def default_get(self, fields_list):
        res = super(CardProcessWizard, self).default_get(fields_list)
        card_ids = self._context.get('card_ids', [])
        res.update({'card_ids': [(6, 0, card_ids)]})
        return res

    @api.multi
    def button_proceed(self):
        self.ensure_one()
        cards = self.card_ids
        return {
            'name': 'Cards',
            'view_type': 'form',
            'view_mode': 'tree,form',
            'res_model': 'card.card',
            'type': 'ir.actions.act_window',
            'domain': [('id', 'in', cards.ids)]
        }
        return True

