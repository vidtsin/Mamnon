
# -*- coding: utf-8 -*-

import binascii
import tempfile
import pandas as pd
from odoo.exceptions import Warning
from odoo import models, fields, api, _

class StockMove(models.Model):
    _inherit = "stock.move"

    file_name = fields.Char()
    import_excel = fields.Binary('Import Excel')

    @api.onchange('import_excel')
    def onchange_import_excel(self):
        fp = tempfile.NamedTemporaryFile(suffix=".xlsx")
        fp.write(binascii.a2b_base64(self.import_excel))
        xlsx = pd.ExcelFile(fp.name)
        pack_sheets = []
        for sheet in xlsx.sheet_names:
            pack_sheets.append(xlsx.parse(sheet))
            pack = pd.concat(pack_sheets)
            ab=pd.DataFrame(pack)
            for package,packagegroup in ab.groupby('package'):
                package_id = self.env['stock.quant.package'].sudo().search([('name', '=', package)])
                if not package_id:
                    package_id = self.env['stock.quant.package'].sudo().create({'name': package})
                for cname in packagegroup.sort_values(by='cardname').itertuples():
                    move_line = self.move_line_ids.filtered(lambda r: r.lot_name == cname.cardname)
                    if move_line:
                        move_line.result_package_id = package_id
           

    @api.one
    @api.constrains('state', 'location_id', 'location_dest_id')
    def check_user_location_rights(self):
        if self.state == 'draft':
            return True
        user_locations = self.env.user.stock_location_ids
        print(user_locations)
        print("Checking access %s" %self.env.user.default_picking_type_ids)
        if self.env.user.restrict_locations:
            message = _(
                'Invalid Location. You cannot process this move since you do '
                'not control the location "%s". '
                'Please contact your Adminstrator.')
            if self.location_id not in user_locations:
                raise Warning(message % self.location_id.name)
            elif self.location_dest_id not in user_locations:
                raise Warning(message % self.location_dest_id.name)




class StockMoveLine(models.Model):
    """To assign Serial number from card name"""
    _inherit = "stock.move.line"
    _description = 'Stock Move Line'

    @api.model
    def create(self,vals):
        """Automatically assign serial number from card name."""
        res = super(StockMoveLine, self).create(vals)
        purchase = self.env['stock.picking'].browse(vals['picking_id']).purchase_id
        card = purchase.card_lines.filtered(lambda r: not r.move_line_id)
        if card:
            card = card[0]
            res.lot_name = card.name
            card.write({'move_line_id': res.id, 'state': 'available_to_distribution'})
        return res

    @api.multi
    def write(self, vals):
        """Update reference in stock.production.lot from purchase name"""
        User = self.env['res.users']
        Card = self.env['card.card']
        StockProductionLot = self.env['stock.production.lot']
        
        for obj in self:
            #check if it is merchant transfer
            #TODO: create data for merchant transfer operation type and compare it.
            if obj.picking_id.picking_type_id.id == self.env.ref('cms.operation_type_merchant_transfer').id:
                partner_id = obj.move_id.location_dest_id.partner_id 
                user = User.search([('partner_id', '=', partner_id.id)]) #Fetch merchant user ID
                card = Card.search([('name', '=', obj.lot_id.name)]) #Fetch card
                card.write({'merchant_id' : partner_id.id, 'state': 'at_merchants'}) #Assign card and update merchant
            if 'lot_id' in vals and vals['lot_id']:
                #Set the PO reference to Lot Number
                StockProductionLot.browse(vals['lot_id']).ref = obj.move_id.origin
        return super(StockMoveLine, self).write(vals)


class ResUsers(models.Model):
    _inherit = 'res.users'

    restrict_locations = fields.Boolean('Restrict Location')

    stock_location_ids = fields.Many2many(
        'stock.location',
        'location_security_stock_location_users',
        'user_id',
        'location_id',
        'Stock Locations')

    default_picking_type_ids = fields.Many2many(
        'stock.picking.type', 'stock_picking_type_users_rel',
        'user_id', 'picking_type_id', string='Default Warehouse Operations')
