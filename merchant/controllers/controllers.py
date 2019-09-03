# -*- coding: utf-8 -*-

import base64
from odoo import http
from odoo.http import request
import json


class Merchant(http.Controller):
    
    

    def get_context(self):
        """
        This method prepare common context for both
        request types.
        """
        plans = request.env['merchant.plan'].sudo().search([])
        cities = request.env['res.city'].sudo().search([])
        countries = request.env['res.country'].sudo().search([])
        shop_types = request.env['merchant.shop.type'].sudo().search([])
        shop_img_count = int(request.env['ir.config_parameter'].sudo().get_param('merchant.image_count'))
        # max_img_size = int(request.env['ir.config_parameter'].sudo().get_param('merchant.max_img_size'))
        ctx = {
            'plans':plans,
            'cities':cities,
            'countries':countries,
            'shop_types':shop_types,
            'shop_img_count':shop_img_count,
            # 'max_img_size':max_img_size,
        }
        return ctx


    @http.route('/merchant/request/status', auth='public', website=True)
    def get_status(self,**kwargs):
        if request.env['merchant.request'].sudo().search([('name','=', kwargs.get('id'))]):
            req_number = request.env['merchant.request'].sudo().search([('name','=', kwargs.get('id'))])
            if req_number.email == kwargs.get('email'):
                req_state = req_number.state
                states = {'new':'Requested', 'approved':'Approved', 'progress':'In-Progress', 'reject':'Rejected','suspend':'Suspended'}
                return json.dumps({'msg': 'Your Registration Request is at - ' + states[req_state] + ' stage'})
            else:
                return json.dumps({'msg':'Incorrect Email.'})
        else:
            return json.dumps({'msg':'Requested ID not found'})


    @http.route('/merchant/register/', auth='public', website=True)
    def register(self, **kw):
        """
        This method takes the requested values 
        and registers the merchant after validations.
        """
        ctx = self.get_context()
        
        if http.request.httprequest.method == 'POST':
            validate_form = request.env['merchant.request']._validate_form(kw)
            
            for x in range(ctx.get('shop_img_count')):
                img_data = kw.get('base' +str(x))
                img_size = (((len(img_data) * 3) / 4) / 1000)

                # if img_size > float(ctx.get('max_img_size')):
                #     validate_form['field_errors'].append('Image size is greater than %s KB' % (ctx.get('max_img_size')))
                #     break

            if not validate_form.get('field_errors'):
                
                vals = {
                    'username' : kw.get('username'),
                    'username2' : kw.get('username2'),  
                    'shopname' : kw.get('shopname'),
                    'shop_type_id' : kw.get('shop_type_id'),
                    'plan_id' : kw.get('plan_id'),
                    'email' : kw.get('email'),
                    'email2' : kw.get('email2'),
                    'mobile' : kw.get('mobile'),
                    'city' : kw.get('city_id'),
                    'location' : kw.get('location'),
                    'location_lat' : kw.get('lat'),
                    'location_lng' : kw.get('lng'),
                    'country_id' : request.env['res.country'].sudo().search([('code','=', kw.get('country_id'))], limit=1).id,
                    'logo' : base64.encodestring(kw.get('logo').read()),
                    'has_branches':True if kw.get('branches') == 'on' else False,
                    'social_gplus_link':kw.get('social_gplus_link'),
                    'social_fb_link':kw.get('social_fb_link'),
                    'description':kw.get('description'),
                }
                
                requestObj = request.env['merchant.request'].sudo().create(vals)                
                for x in range(ctx.get('shop_img_count')):
                    img_data = kw.get('base' +str(x)).replace('data:image/jpeg;base64,', '').replace('data:image/png;base64,', '').replace('data:image/jpg;base64,', '')
                    if len(img_data) % 4:
                        img_data += '=' * (4 - len(img_data) % 4)
                    if img_data:
                        img = request.env['merchant.request.images.line'].sudo().create({'image':img_data, 'request_id':requestObj.id})

                    response = {'merchant_request':requestObj}
            
                return http.request.render('merchant.registration.success', response)

            else:

                ctx['field_errors'] = validate_form.get('field_errors')
                ctx['form_values'] = kw

        else:
            val = {}

        return http.request.render('merchant.registration', ctx)


