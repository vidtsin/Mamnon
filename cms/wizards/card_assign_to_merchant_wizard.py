from odoo import api, fields, models
# To Assign card to merchant by operation team 
class AssignCardMerchnat(models.TransientModel):
    _name = 'assign.card.merchant'
    _description = 'Assign Card User'

    merchant_id = fields.Many2one('res.partner','Merchant', required=True)
    package_ids = fields.Many2many('stock.quant.package', string='Package')

    """Create Transfer for merchant to all  ote card in package""" 
    @api.multi
    def button_assign(self):
        partner_id = self.merchant_id.id
        picking_id = self.env.ref('cms.operation_type_merchant_transfer')
        location_id = self.env['stock.location'].search([('partner_id','=',partner_id)])
        package_level_line = [(0,0,{
                    'package_id' : pack_line.id,
                    'location_id': picking_id.default_location_src_id.id,
                    'location_dest_id': location_id.id,
        }) for pack_line in self.package_ids]
        value = {
            'partner_id': partner_id,
            'location_id': picking_id.default_location_src_id.id,
            'location_dest_id': location_id.id,
            'picking_type_id': picking_id.id,
            'package_level_ids': package_level_line,
        }
        picking = self.env['stock.picking'].create(value)
        picking.action_confirm()
        picking.action_assign()
        return picking.button_validate()
