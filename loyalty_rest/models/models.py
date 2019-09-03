# -*- coding: utf-8 -*-

import time
import logging
from odoo import models, api, fields
_logger = logging.getLogger(__name__)

class AutoVacuum(models.AbstractModel):
    _inherit = 'ir.autovacuum'

    @api.model
    def power_on(self, *args, **kwargs):
        self.env['loyalty_rest.token']._garbage_collect()
        return super(AutoVacuum, self).power_on(*args, **kwargs)

try:
    import secrets
    def token_urlsafe():
        return secrets.token_urlsafe(64)
except ImportError:
    import re
    import uuid
    import base64
    def token_urlsafe():
        rv = base64.b64encode(uuid.uuid4().bytes).decode('utf-8')
        return re.sub(r'[\=\+\/]', lambda m: {'+': '-', '/': '_', '=': ''}[m.group(0)], rv)

class RESTToken(models.Model):
    _name = 'loyalty_rest.token'
    
    token = fields.Char(
        string="Token",
        required=True)
    
    lifetime = fields.Integer(
        string="Lifetime",
        required=True)
    
    user = fields.Many2one(
        'res.users',
        string="User",
        required=True,  ondelete='cascade')
        
    @api.model
    def lifetime_token(self, token):
        token = self.search([['token', '=', token]], limit=1)
        if token:
            return int(token.lifetime - time.time())
        return False

    @api.model
    def delete_token(self, token):
        token = self.search([['token', '=', token]], limit=1)
        if token:
            return token.unlink()
        return False

    @api.model
    def refresh_token(self, token, lifetime=3600):
        token = self.search([['token', '=', token]], limit=1)
        if token:
            timestamp = int(time.time() + lifetime)
            return token.write({'lifetime': timestamp})
        return False

    @api.model
    def check_token(self, token):
        token = self.search([['token', '=', token]], limit=1)   
        # return token.user.id if token and int(time.time()) < token.lifetime else False
        return token.user.id #if token and int(time.time()) < token.lifetime else False
    
    @api.model
    def generate_token(self, uid, lifetime=3600):
        token = token_urlsafe()
        timestamp = int(time.time() + lifetime)
        return self.create({'token': token, 'lifetime': timestamp, 'user': uid})
    
    @api.model
    def _garbage_collect(self):
        token = self.search([['lifetime', '>', int(time.time())]], limit=1)
        token.unlink()




        # check_params({'partner_id':partner_id})
        # try:
        #     env = api.Environment(request.cr, odoo.SUPERUSER_ID, {})
        #     res = {'merchant_points_line':[]}
        #     partner = env['res.partner'].browse(int(partner_id))
        #     for point_line in partner.points_line:
        #         merchant_point_dict = {'merchant_id':point_line.merchant_id.id}
        #         merchant_point_dict['purchase_line'] = []
        #         for pur_line in point_line.purchase_line:
        #             purchase_line_dict = {
        #                 'merchant_id':pur_line.merchant_id.id,
        #                 'date':pur_line.date.strftime('%d/%m/%Y'),
        #                 'purchase_amount':pur_line.purchase_amount,
        #                 'point':pur_line.point,
        #                 'point_redeem':pur_line.point_redeem,
        #                 'point_remaining':pur_line.point_remaining,
        #                 'is_closed':pur_line.is_closed,
        #                 'is_group':pur_line.is_group,
        #                 'is_settled':pur_line.is_settled,
        #             }
        #             merchant_point_dict['purchase_line'].append(purchase_line_dict)

        #         res['merchant_points_line'].append(merchant_point_dict)

        #     return Response(json.dumps(res,
        #             sort_keys=True, indent=4, cls=ObjectEncoder),
        #             content_type='application/json;charset=utf-8', status=200)
        # except:
        #     return Response(json.dumps({'error': 'API not working'},
        #             sort_keys=True, indent=4, cls=ObjectEncoder),
        #             content_type='application/json;charset=utf-8', status=500)