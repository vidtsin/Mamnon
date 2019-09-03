# -*- coding: utf-8 -*-

import os
import re
import random, string
import json
import base64
import inspect
import logging
import tempfile
import datetime
import traceback

import werkzeug
from werkzeug import urls
from werkzeug import utils
from werkzeug import exceptions
from werkzeug.urls import iri_to_uri
from collections import OrderedDict
import odoo
from odoo import _
from odoo import api
from odoo import tools
from odoo import http
from odoo import models
from odoo import release
from odoo.http import request
from odoo.http import Response
from math import radians, cos, sin, asin, sqrt
from odoo.tools.misc import str2bool
from PIL import Image, ImageFile
ImageFile.LOAD_TRUNCATED_IMAGES = True

_logger = logging.getLogger(__name__)

REST_VERSION = {
    'server_version': release.version,
    'server_version_info': release.version_info,
    'server_serie': release.serie,
    'api_version': 2,
}

NOT_FOUND = {
    'error': 'unknown_command',
}

DB_INVALID = {
    'error': 'invalid_db',
}

FORBIDDEN = {
    'error': 'token_invalid',
}

NO_API = {
    'error': 'rest_api_not_supported',
}

LOGIN_INVALID = {
    'error': 'invalid_login',
}

DBNAME_PATTERN = '^[a-zA-Z0-9][a-zA-Z0-9_.-]+$'

def abort(message, rollback=False, status=403):
    response = Response(json.dumps(message,
        sort_keys=True, indent=4, cls=ObjectEncoder),
        content_type='application/json;charset=utf-8', status=status) 
    if request._cr and rollback:
        request._cr.rollback()
    exceptions.abort(response)
    
def check_token():
    token = request.params.get('token') and request.params.get('token').strip()
    if not token:
        abort(FORBIDDEN)
    env = api.Environment(request.cr, odoo.SUPERUSER_ID, {})
    uid = env['loyalty_rest.token'].check_token(token)
    if not uid:
        abort(FORBIDDEN)
    request._uid = uid
    request._env = api.Environment(request.cr, uid, request.session.context or {})
    
def ensure_db():
    db = request.params.get('db') and request.params.get('db').strip()
    if db and db not in http.db_filter([db]):
        db = None
    if not db and request.session.db and http.db_filter([request.session.db]):
        db = request.session.db
    if not db:
        db = http.db_monodb(request.httprequest)
    if not db:
        abort(DB_INVALID, status=404)
    if db != request.session.db:
        request.session.logout()
    request.session.db = db
    try:
        env = api.Environment(request.cr, odoo.SUPERUSER_ID, {})
        module = env['ir.module.module'].search([['name', '=', "loyalty_rest"]], limit=1)
        if module.state != 'installed':
            abort(NO_API, status=500)
    except Exception as error:
        _logger.error(error)
        abort(DB_INVALID, status=404)

def check_params(params):
    missing = []
    for key, value in params.items():
        if not value:
            missing.append(key)
    if missing:
        abort({'error': "arguments_missing %s" % str(missing)}, status=400)


def paginate(count=20, page_no=1, records=[]):
    """
    Paginate the records
    """
    res =   {}

    if not page_no:
        page_no = 1
    else:
        page_no = int(page_no)

    res['last'] = False
    from_record = (page_no - 1) * count
    to_record = (page_no * count)

    if to_record >= len(records):
        res['last'] = True
    
    if len(records)>1:
        res['records'] = records[from_record:to_record]
    
    else:
        res['records'] = records

    return res

def getCordinates(src_lat, src_lng, dest_lat,  dest_lng):
    """
    Get The Cordinates
    """
    src_lat, src_lng, dest_lat, dest_lng = map(radians,[src_lat, src_lng, dest_lat, dest_lng])
    dlon = dest_lng - src_lng
    dlat = dest_lat - src_lat
    a = sin(dlat/2)**2 + cos(src_lat) * cos(dest_lat) * sin(dlon/2)**2
    c = 2 * asin(sqrt(a))
    r = 6371 # Radius of earth in kilometers. Use 3956 for miles
    return c * r   


class ObjectEncoder(json.JSONEncoder):
    def default(self, obj):
        def encode(item):
            if isinstance(item, models.BaseModel):
                vals = {}
                for name, field in item._fields.items():
                    if name in item:
                        if isinstance(item[name], models.BaseModel):
                            records = item[name]
                            if len(records) == 1:
                                vals[name] = (records.id, records.sudo().display_name)
                            else:
                                val = []
                                for record in records:
                                    val.append((record.id, record.sudo().display_name))
                                vals[name] = val
                        else:
                            try:
                                vals[name] = item[name].decode()
                            except UnicodeDecodeError:
                                vals[name] = item[name].decode('latin-1')
                            except AttributeError:
                                vals[name] = item[name]
                    else:
                        vals[name] = None
                return vals
            if inspect.isclass(item):
                return item.__dict__
            try:
                return json.JSONEncoder.default(self, item)
            except TypeError:
                return "error"
        try:
            try:
                result = {}
                for key, value in obj.items():
                    result[key] = encode(item)
                return result
            except AttributeError:
                result = []
                for item in obj:
                    result.append(encode(item))
                return result
        except TypeError:
            return encode(item)

class RESTController(http.Controller):

    #----------------------------------------------------------
    # General
    #----------------------------------------------------------

    @http.route('/api/<path:path>', auth="none", type='http', csrf=False)
    def api_catch(self, **kw):    
        return Response(json.dumps(NOT_FOUND,
            sort_keys=True, indent=4, cls=ObjectEncoder),
            content_type='application/json;charset=utf-8', status=404) 
    
    @http.route('/api', auth="none", type='http')
    def api_version(self, **kw):    
        return Response(json.dumps(REST_VERSION,
            sort_keys=True, indent=4, cls=ObjectEncoder),
            content_type='application/json;charset=utf-8', status=200) 
    
    @http.route('/api/change_master_password', auth="none", type='http', methods=['POST'], csrf=False)
    def api_change_password(self, password_old="admin", password_new=None, **kw):
        check_params({'password_new': password_new})
        try:
            http.dispatch_rpc('db', 'change_admin_password', [
                password_old,
                password_new])
            return Response(json.dumps(True,
                sort_keys=True, indent=4, cls=ObjectEncoder),
                content_type='application/json;charset=utf-8', status=200)
        except Exception as error:
            _logger.error(error)
            abort({'error': traceback.format_exc()}, status=400)
    
    #----------------------------------------------------------
    # Database
    #----------------------------------------------------------
    
    @http.route('/api/database/list', auth="none", type='http', csrf=False)
    def api_database_list(self, **kw):
        databases = []
        incompatible_databases = []
        try:
            databases = http.db_list()
            incompatible_databases = odoo.service.db.list_db_incompatible(databases)
        except odoo.exceptions.AccessDenied:
            monodb = http.db_monodb()
            if monodb:
                databases = [monodb]
        info = {
            'databases': databases,
            'incompatible_databases': incompatible_databases}
        return Response(json.dumps(info,
            sort_keys=True, indent=4, cls=ObjectEncoder),
            content_type='application/json;charset=utf-8', status=200)

    @http.route('/api/database/create', auth="none", type='http', methods=['POST'], csrf=False)
    def api_database_create(self, master_password="admin", lang="en_US", database_name=None, 
                        admin_login=None, admin_password=None, **kw):
        check_params({
            'database_name': database_name,
            'admin_login': admin_login,
            'admin_password': admin_password})
        try:
            if not re.match(DBNAME_PATTERN, database_name):
                raise Exception(_('Invalid database name.'))
            http.dispatch_rpc('db', 'create_database', [
                master_password,
                database_name,
                bool(kw.get('demo')),
                lang,
                admin_password,
                admin_login,
                kw.get('country_code') or False])
            return Response(json.dumps(True,
                sort_keys=True, indent=4, cls=ObjectEncoder),
                content_type='application/json;charset=utf-8', status=200)
        except Exception as error:
            _logger.error(error)
            abort({'error': traceback.format_exc()}, status=400)
    
    @http.route('/api/database/duplicate', auth="none", type='http', methods=['POST'], csrf=False)
    def api_database_duplicate(self, master_password="admin", database_old=None, database_new=None, **kw):
        check_params({
            'database_old': database_old,
            'database_new': database_new})
        try:
            if not re.match(DBNAME_PATTERN, database_new):
                raise Exception(_('Invalid database name.'))
            http.dispatch_rpc('db', 'duplicate_database', [
                master_password,
                database_old,
                database_new])
            return Response(json.dumps(True,
                sort_keys=True, indent=4, cls=ObjectEncoder),
                content_type='application/json;charset=utf-8', status=200)
        except Exception as error:
            _logger.error(error)
            abort({'error': traceback.format_exc()}, status=400)
    
    @http.route('/api/database/drop', auth="none", type='http', methods=['POST'], csrf=False)
    def api_database_drop(self, master_password="admin", database_name=None, **kw):
        check_params({'database_name': database_name})
        try:
            http.dispatch_rpc('db','drop', [
                master_password,
                database_name])
            request._cr = None
            return Response(json.dumps(True,
                sort_keys=True, indent=4, cls=ObjectEncoder),
                content_type='application/json;charset=utf-8', status=200)
        except Exception as error:
            _logger.error(error)
            abort({'error': traceback.format_exc()}, status=400)

    #----------------------------------------------------------
    # Backup & Restore
    #----------------------------------------------------------        
    
    @http.route('/api/database/backup', auth="none", type='http', methods=['POST'], csrf=False)
    def api_database_backup(self, master_password="admin", database_name=None, backup_format='zip', **kw):
        check_params({'database_name': database_name})
        try:
            odoo.service.db.check_super(master_password)
            ts = datetime.datetime.utcnow().strftime("%Y-%m-%d_%H-%M-%S")
            filename = "%s_%s.%s" % (database_name, ts, backup_format)
            headers = [
                ('Content-Type', 'application/octet-stream; charset=binary'),
                ('Content-Disposition', http.content_disposition(filename)),
            ]
            dump_stream = odoo.service.db.dump_db(database_name, None, backup_format)
            return Response(dump_stream, headers=headers, direct_passthrough=True)
        except Exception as error:
            _logger.error(error)
            abort({'error': traceback.format_exc()}, status=400)
            
    @http.route('/api/database/restore', auth="none", type='http', methods=['POST'], csrf=False)
    def api_restore(self, master_password="admin", backup_file=None, database_name=None, copy=False, **kw):
        check_params({'backup_file': backup_file, 'database_name': database_name})
        try:
            with tempfile.NamedTemporaryFile(delete=False) as data_file:
                backup_file.save(data_file)
            odoo.service.db.restore_db(database_name, data_file.name, str2bool(copy))
            return Response(json.dumps(True,
                sort_keys=True, indent=4, cls=ObjectEncoder),
                content_type='application/json;charset=utf-8', status=200)
        except Exception as error:
            _logger.error(error)
            abort({'error': traceback.format_exc()}, status=400)
        finally:
            os.unlink(data_file.name)
    
    #----------------------------------------------------------
    # Token Authentication
    #----------------------------------------------------------
    
    @http.route('/api/authenticate', auth="none", type='http', methods=['POST'], csrf=False)
    def api_authenticate(self, db=None, login=None, password=None, **kw):    
        check_params({'db': db, 'login': login, 'password': password})
        ensure_db()
        try:
            uid = request.session.authenticate(db, login, password)
        except:
            return Response(json.dumps({'error': 'Invalid Credentials'},
                sort_keys=True, indent=4, cls=ObjectEncoder),
                content_type='application/json;charset=utf-8', status=500)
        if uid:
            env = api.Environment(request.cr, odoo.SUPERUSER_ID, {})
            user = env['res.users'].browse(uid)
            
            if kw.get('deviceId'):
                user.write({'device_id':kw.get('deviceId')})

            token = env['loyalty_rest.token'].generate_token(uid)
            profile_complete = False
            
            if user.partner_id.mobile and user.partner_id.mobile_verified:
                profile_complete = True

            return Response(json.dumps({'token': token.token, 'uid':uid, 'partner_id':user.partner_id.id, 'profile_complete':profile_complete, 'lang':user.lang},
                sort_keys=True, indent=4, cls=ObjectEncoder),
                content_type='application/json;charset=utf-8', status=200) 
        else:
            abort(LOGIN_INVALID, status=401)


    @http.route('/api/register', auth="none", type='http', methods=['POST'], csrf=False)
    def api_register(self, db=None, login=None, password=None, **kw):
        ensure_db()
        try:
            env = api.Environment(request.cr, odoo.SUPERUSER_ID, {})
            mobile = ''
            if kw.get('mobile'):
                mobile = '+'+kw.get('mobile').strip()

            if env['res.partner'].search([('mobile','=',mobile)]):
                return Response(json.dumps({'error': 'Mobile No. already registered'},
                    sort_keys=True, indent=4, cls=ObjectEncoder),
                    content_type='application/json;charset=utf-8', status=500)

            elif env['res.users'].search([('email','=',kw.get('email'))]):
                return Response(json.dumps({'error': 'Email already registered'},
                    sort_keys=True, indent=4, cls=ObjectEncoder),
                    content_type='application/json;charset=utf-8', status=500)

            else:
                # Verify OTP - 
                registered_otp = env['loyalty.mobile.otp.register'].search([('mobile','=', mobile)], limit=1)
                if kw.get('otp') and registered_otp:
                    if kw.get('otp') == registered_otp.otp:
                        portal_user = request.env.ref('base.group_portal')
                        user = env['res.users'].with_context({'no_reset_password':True}).create({'login':kw.get('email'), 'password':password, 'name':kw.get('name'), 'email':kw.get('email'), 'groups_id':[(6, 0, [portal_user.id])] , 'device_id': kw.get('deviceId')})
                        if user.partner_id:
                            
                            user.partner_id.write({
                                    'city': kw.get('city') or False, 
                                    'mobile':mobile,
                                    'street':kw.get('fullAddress') or '',
                                    'dob': kw.get('dob') or False,
                                    'gender': kw.get('gender') or '',
                                    'customer':True,
                                    'mobile_verified':True,
                                })
                        
                            user.partner_id.notify(notify_type="registration", msg=False, sms=True, email=True)                        
                        token = env['loyalty_rest.token'].generate_token(user.id)
                        profile_complete = False                    
                        if user.partner_id.mobile and user.partner_id.mobile_verified:
                            profile_complete = True

                        return Response(json.dumps({'token': token.token, 'uid':user.id, 'partner_id':user.partner_id.id, 'profile_complete':profile_complete, 'lang':user.lang},
                            sort_keys=True, indent=4, cls=ObjectEncoder),
                            content_type='application/json;charset=utf-8', status=200)
                    else:
                        return Response(json.dumps({'error': 'Invalid OTP'},
                            sort_keys=True, indent=4, cls=ObjectEncoder),
                            content_type='application/json;charset=utf-8', status=500)
                else:
                    return Response(json.dumps({'error': 'Invalid OTP'},
                        sort_keys=True, indent=4, cls=ObjectEncoder),
                        content_type='application/json;charset=utf-8', status=500)
        except:
            return Response(json.dumps({'error': 'Error occured while registration'},
                sort_keys=True, indent=4, cls=ObjectEncoder),
                content_type='application/json;charset=utf-8', status=500)


    # GmailSignupAuthenication
    @http.route('/api/authenticate/google', auth="none", type='http', methods=['POST'], csrf=False)
    def api_google_authenticate(self, db=None, login=None, password=None, **kw):    
        ensure_db()
        # Todo :: Check if Try catch needed.
        env = api.Environment(request.cr, odoo.SUPERUSER_ID, {})

        user_exist = env['res.users'].search(['|', ('email','=',kw.get('email')), ('oauth_uid','=', kw.get('userId'))], limit=1)
        if user_exist:

            uid = False

            if user_exist.oauth_provider_id:    
                google_provider_id = env.ref('auth_oauth.provider_google').id
                if user_exist.oauth_provider_id.id == google_provider_id:
                    try:
                        uid = request.session.authenticate(db, kw.get('email'), kw.get('userId'))
                    except:
                        return Response(json.dumps({'error': 'Invalid Credentials'},
                            sort_keys=True, indent=4, cls=ObjectEncoder),
                            content_type='application/json;charset=utf-8', status=500)
                else:
                    return Response(json.dumps({'error': 'This email is already registered.'},
                        sort_keys=True, indent=4, cls=ObjectEncoder),
                        content_type='application/json;charset=utf-8', status=500)
            else:
                return Response(json.dumps({'error': 'This email is already registered.'},
                        sort_keys=True, indent=4, cls=ObjectEncoder),
                        content_type='application/json;charset=utf-8', status=500)

            if uid:
                user = env['res.users'].browse(uid)
                
                if kw.get('deviceId'):
                    user.write({'device_id':kw.get('deviceId')})

                token = env['loyalty_rest.token'].generate_token(uid)

                profile_complete = False
            
                if user.partner_id.mobile and user.partner_id.mobile_verified:
                    profile_complete = True

                return Response(json.dumps({'token': token.token, 'uid':uid, 'partner_id':user.partner_id.id, 'profile_complete':profile_complete, 'lang':user.lang},
                    sort_keys=True, indent=4, cls=ObjectEncoder),
                    content_type='application/json;charset=utf-8', status=200) 
            else:
                abort(LOGIN_INVALID, status=401)
        else:
            oauth_user_id = kw.get('userId')
            oauth_access_token = kw.get('accessToken')

            env = api.Environment(request.cr, odoo.SUPERUSER_ID, {})
            
            try:
                oauth_provider_id = request.env.ref('auth_oauth.provider_google').id
            except:
                return Response(json.dumps({'error': 'Google Auth not enabled'},
                    sort_keys=True, indent=4, cls=ObjectEncoder),
                    content_type='application/json;charset=utf-8', status=500)

            portal_user = request.env.ref('base.group_portal')
            env = api.Environment(request.cr, odoo.SUPERUSER_ID, {})            
            user = env['res.users'].with_context({'no_reset_password':True}).create({
                    'login':kw.get('email'), 
                    'password':oauth_user_id,
                    'oauth_uid':oauth_user_id, 
                    'oauth_provider_id':oauth_provider_id,
                    # 'oauth_access_token':oauth_access_token,
                    'name':kw.get('displayName'), 
                    'email':kw.get('email'),
                    'groups_id':[(6, 0, [portal_user.id])],
                    'device_id':kw.get('deviceId'),
                })
            user.partner_id.notify(notify_type="registration", msg=False, sms=True, email=True)
            user.partner_id.write({'customer':True})
            token = env['loyalty_rest.token'].generate_token(user.id)

            profile_complete = False
        
            if user.partner_id.mobile and user.partner_id.mobile_verified:
                profile_complete = True

            
            return Response(json.dumps({'token': token.token, 'uid':user.id, 'partner_id':user.partner_id.id, 'profile_complete':profile_complete, 'lang':user.lang},
                    sort_keys=True, indent=4, cls=ObjectEncoder),
                    content_type='application/json;charset=utf-8', status=200)


    @http.route('/api/profile', auth="none", type='http', methods=['GET'], csrf=False)
    def api_profile(self, token=None, user_id=False, **kw):
        check_params({'token': token, 'user_id':user_id})
        ensure_db()
        check_token()
        env = api.Environment(request.cr, odoo.SUPERUSER_ID, {})
        user = env['res.users'].browse(int(user_id))
        partner = user.partner_id
        image_url = ''
        if partner.image and partner.image_url:
            if kw.get('is_updated') == 1:
                random_param = ''.join(random.choice(string.ascii_uppercase + string.digits) for _ in range(8)).lower()
                image_url = '/api/image/partner/%s?random=%s' % (partner.id, random_param)
            else:
                image_url = '/api/image/partner/%s' % (partner.id)
                
        if user:
            vals= {
                'image':image_url, 
                'mobile':partner.mobile,
                'dob':partner.dob.strftime('%Y-%m-%d') if partner.dob else '',
                'street':partner.street,
                'name':partner.name,
                'city':partner.city.name if partner.city else False,
                'city_id':partner.city.id if partner.city else False,
                'gender':partner.gender if partner.gender else False,
                'email':partner.email or user.login, 
                'mobile_verified': partner.mobile_verified,
                'notify_email':user.notify_email,
                'notify_push':user.notify_push,
                'notify_sms':user.notify_sms,
            }            
            return Response(json.dumps(vals,
                sort_keys=True, indent=4, cls=ObjectEncoder),
                content_type='application/json;charset=utf-8', status=200)
        else:
            return Response(json.dumps({'error': 'Error getting profile data'},
                    sort_keys=True, indent=4, cls=ObjectEncoder),
                    content_type='application/json;charset=utf-8', status=500)


    # @http.route('/api/edit-profile', auth="none", type='http', methods=['POST'], csrf=False)
    # def api_edit_profile(self, token=None, user_id=False, **kw):
    #     check_params({'token': token, 'user_id':user_id})
    #     ensure_db()
    #     check_token()
    #     env = api.Environment(request.cr, odoo.SUPERUSER_ID, {})
    #     user = env['res.users'].browse(int(user_id))
    #     if user:
    #         kw.pop('db')
    #         if kw.get('image'):
    #             kw['image'] = kw.get('image').replace(' ','+')
    #             img_data = kw.get('image')                
                
    #             if len(img_data) % 4:
    #                 img_data += '=' * (4 - len(img_data) % 4)
    #             kw['image'] = img_data

    #         if not kw.get('dob'):
    #             kw['dob'] = False

    #         if kw.get('mobile'):
    #             kw['mobile'] = '+'+kw.get('mobile')


    #         # registered_otp = env['loyalty.mobile.otp.register'].search([('mobile','=', kw.get('mobile'))], limit=1)
    #         partner = user.partner_id.write(kw)

    #         return Response(json.dumps({'msg': 'Profile Updated Successfully!!'},
    #             sort_keys=True, indent=4, cls=ObjectEncoder),
    #             content_type='application/json;charset=utf-8', status=200)            

    #         # if kw.get('otp') and registered_otp:
    #         #     if kw.get('otp') == registered_otp.otp:
    #         #         kw.pop('otp')
    #         #     else:
    #         #         return Response(json.dumps({'error': 'Invalid OTP'}, 
    #         #             sort_keys=True, indent=4, cls=ObjectEncoder),
    #         #             content_type='application/json;charset=utf-8', status=500)
    #         # else:
    #         #     return Response(json.dumps({'error': 'Invalid OTP'},
    #         #             sort_keys=True, indent=4, cls=ObjectEncoder),
    #         #             content_type='application/json;charset=utf-8', status=500)
    #     else:
    #         return Response(json.dumps({'error': 'Error updating profile'},
    #                 sort_keys=True, indent=4, cls=ObjectEncoder),
    #                 content_type='application/json;charset=utf-8', status=500)


    @http.route('/api/authenticate/fb', auth="none", type='http', methods=['POST'], csrf=False)
    def api_fb_authenticate(self, db=None, userId=None, **kw):
        ensure_db()
        check_params({'displayName':kw.get('displayName'), 'login':kw.get('login'), 'userId':userId})
        try:
            # Todo :: Check if Try catch needed.
            env = api.Environment(request.cr, odoo.SUPERUSER_ID, {})
            
            if not db:
                db = request.db

            user_exist = env['res.users'].search(['|', ('email','=',kw.get('email')), ('oauth_uid', '=', userId)], limit=1)
            if user_exist:
                uid = False
                if user_exist.oauth_provider_id:
                    fb_provider_id = env.ref('auth_oauth.provider_facebook').id
                    if user_exist.oauth_provider_id.id == fb_provider_id:
                        try:
                            uid = request.session.authenticate(db, kw.get('email'), userId)
                        except:
                            return Response(json.dumps({'error': 'Invalid Credentials or Email is already registered.'},
                                sort_keys=True, indent=4, cls=ObjectEncoder),
                                content_type='application/json;charset=utf-8', status=500)
                    else:
                        return Response(json.dumps({'error': 'This email is already registered.'},
                            sort_keys=True, indent=4, cls=ObjectEncoder),
                            content_type='application/json;charset=utf-8', status=500)
                else:
                    return Response(json.dumps({'error': 'This email is already registered.'},
                                sort_keys=True, indent=4, cls=ObjectEncoder),
                                content_type='application/json;charset=utf-8', status=500)

                if uid:
                    user = env['res.users'].browse(uid)
                    
                    if kw.get('deviceId'):
                        user.write({'device_id':kw.get('deviceId')})

                    token = env['loyalty_rest.token'].generate_token(uid)
                    profile_complete = False

                    if user.partner_id.mobile and user.partner_id.mobile_verified:
                        profile_complete = True

                    return Response(json.dumps({'token': token.token, 'uid':uid, 'partner_id':user.partner_id.id, 'profile_complete':profile_complete, 'lang':user.lang},
                        sort_keys=True, indent=4, cls=ObjectEncoder),
                        content_type='application/json;charset=utf-8', status=200) 
                else:
                    abort(LOGIN_INVALID, status=401)
            else:
                oauth_access_token = kw.get('accessToken')

                env = api.Environment(request.cr, odoo.SUPERUSER_ID, {})
                
                try:
                    oauth_provider_id = request.env.ref('auth_oauth.provider_facebook').id
                
                except:
                    return Response(json.dumps({'error': 'Facebook Auth not enabled'},
                        sort_keys=True, indent=4, cls=ObjectEncoder),
                        content_type='application/json;charset=utf-8', status=500)

                portal_user = request.env.ref('base.group_portal')
                
                user = env['res.users'].with_context({'no_reset_password':True}).create({
                        'login':kw.get('login'), 
                        'password':userId,
                        'oauth_uid':userId, 
                        'oauth_provider_id':oauth_provider_id,
                        # 'oauth_access_token':oauth_access_token,
                        'name':kw.get('displayName'), 
                        'email':kw.get('email'),
                        'groups_id':[(6, 0, [portal_user.id])],
                        'device_id':kw.get('deviceId'),
                    })

                user.partner_id.notify(notify_type="registration", msg=False, sms=True, email=True)
                user.partner_id.write({'customer':True})

                token = env['loyalty_rest.token'].generate_token(user.id)
                profile_complete = False

                if user.partner_id.mobile and user.partner_id.mobile_verified:
                    profile_complete = True
                
                return Response(json.dumps({'token': token.token, 'uid':user.id, 'partner_id':user.partner_id.id, 'profile_complete':profile_complete, 'lang':user.lang},
                        sort_keys=True, indent=4, cls=ObjectEncoder),
                        content_type='application/json;charset=utf-8', status=200)
        except:
            return Response(json.dumps({'error': 'API not working'},
                    sort_keys=True, indent=4, cls=ObjectEncoder),
                    content_type='application/json;charset=utf-8', status=500)

    @http.route('/api/logout', auth="none", type='http', methods=['POST'], csrf=False)
    def api_logout(self, db=None, login=None, password=None, **kw):    
        request.session.logout()
        return Response(json.dumps({'msg': 'Logout Successfully!!'},
                sort_keys=True, indent=4, cls=ObjectEncoder),
                content_type='application/json;charset=utf-8', status=200)


    @http.route('/api/city', auth="none", type='http', methods=['GET'], csrf=False)
    def api_city(self, token=None, **kw):
        ensure_db()
        check_token()
        env = api.Environment(request.cr, odoo.SUPERUSER_ID, {}) 
        cities = env['res.city'].search([])           
        res = []
        try:
            for city in cities:
                res_dict = {}
                res_dict['id'] = city.id
                res_dict['name'] = city.name
                res.append(res_dict)
            return Response(json.dumps(res,
                sort_keys=True, indent=4, cls=ObjectEncoder),
                content_type='application/json;charset=utf-8', status=200) 
        except:
            return Response(json.dumps({'error': 'City Api not working'},
                    sort_keys=True, indent=4, cls=ObjectEncoder),
                    content_type='application/json;charset=utf-8', status=500)

    @http.route('/api/faq', auth="none", type='http', methods=['GET'], csrf=False)
    def api_faq(self, token=None, **kw):
        ensure_db()
        check_token()
        env = api.Environment(request.cr, odoo.SUPERUSER_ID, {}) 
        faqs_categs = env['loyalty.faq.category'].search([])           
        res = []
        try:
            for categ in faqs_categs:
                categ_dict = {}
                question_list = []
                questions = env['loyalty.faq'].search([('category_id','=',categ.id)])
                
                for question in questions:
                    question_list.append({question.question:question.answer})
                categ_dict['category'] = categ.name
                categ_dict['questions'] = question_list
                res.append(categ_dict)

            return Response(json.dumps(res,
                sort_keys=True, indent=4, cls=ObjectEncoder),
                content_type='application/json;charset=utf-8', status=200) 
        except:
            return Response(json.dumps({'error': 'FAQ Api not working'},
                sort_keys=True, indent=4, cls=ObjectEncoder),
                content_type='application/json;charset=utf-8', status=500)


    @http.route('/api/cemail/conf', auth="none", type='http', methods=['GET'], csrf=False)
    def api_cemail(self, token=None, **kw):
        ensure_db()
        check_token()
        settings = request.env['ir.config_parameter'].sudo()
        res = []
        try:    
            cemail_dict = {}
            cemail_dict['msg'] = settings.get_param('merchant.ce_msg')
            cemail_dict['subject'] = settings.get_param('merchant.ce_subject')
            cemail_dict['to'] = settings.get_param('merchant.ce_to')
            cemail_dict['from'] = settings.get_param('merchant.ce_from')
            cemail_dict['cc'] = settings.get_param('merchant.ce_cc')
            cemail_dict['bcc'] = settings.get_param('merchant.ce_bcc')
            cemail_dict['ce_file'] = settings.get_param('merchant.ce_file')
            res.append(cemail_dict)

            return Response(json.dumps(res,
                sort_keys=True, indent=4, cls=ObjectEncoder),
                content_type='application/json;charset=utf-8', status=200) 
        except:
            return Response(json.dumps({'error': 'Compose API not working'},
                sort_keys=True, indent=4, cls=ObjectEncoder),
                content_type='application/json;charset=utf-8', status=500)

    @http.route('/api/social/conf', auth="none", type='http', methods=['GET'], csrf=False)
    def api_social(self, token=None, **kw):
        ensure_db()
        check_token()
        settings = request.env['ir.config_parameter'].sudo()
        res = []
        try:    
            social_dict = {}
            social_dict['msg'] = settings.get_param('merchan t.social_msg')
            social_dict['subject'] = settings.get_param('merchant.social_subject')
            social_dict['file'] = settings.get_param('merchant.social_file')
            social_dict['url'] = settings.get_param('merchant.social_url')
            res.append(social_dict)

            return Response(json.dumps(res,
                sort_keys=True, indent=4, cls=ObjectEncoder),
                content_type='application/json;charset=utf-8', status=200) 
        except:
            return Response(json.dumps({'error': 'Social Links API not working'},
                sort_keys=True, indent=4, cls=ObjectEncoder),
                content_type='application/json;charset=utf-8', status=500)

    @http.route('/api/about/conf', auth="none", type='http', methods=['GET'], csrf=False)
    def api_about(self, token=None, **kw):
        ensure_db()
        check_token()
        settings = request.env['ir.config_parameter'].sudo()
        res = []
        try:    
            about_dict = {}
            about_dict['fb_link'] = settings.get_param('merchant.fb_link')
            about_dict['insta_link'] = settings.get_param('merchant.insta_link')
            about_dict['gplus_link'] = settings.get_param('merchant.gplus_link')
            res.append(about_dict)

            return Response(json.dumps(res,
                sort_keys=True, indent=4, cls=ObjectEncoder),
                content_type='application/json;charset=utf-8', status=200) 
        except:
            return Response(json.dumps({'error': 'About API not working'},
                sort_keys=True, indent=4, cls=ObjectEncoder),
                content_type='application/json;charset=utf-8', status=500)


    @http.route('/api/contact', auth="none", type='http', methods=['GET'], csrf=False)
    def api_contact(self, token=None, **kw):
        ensure_db()
        check_token()
        env = api.Environment(request.cr, odoo.SUPERUSER_ID, {}) 
        phone = env['res.users'].browse(env.uid).company_id.phone
        res = {'phone': phone}        
        return Response(json.dumps(res,
            sort_keys=True, indent=4, cls=ObjectEncoder),
            content_type='application/json;charset=utf-8', status=200) 
    

    @http.route('/api/contact/merchant/<merchant_id>', auth="none", type='http', methods=['GET'], csrf=False)
    def api_contact_merchant(self, token=None, **kw):
        ensure_db()
        check_token()
        check_params({'merchant_id':kw.get('merchant_id')})
        try:
            env = api.Environment(request.cr, odoo.SUPERUSER_ID, {})
            merchant = env['res.partner'].browse(int(kw.get('merchant_id')))
            phone = merchant.mobile or merchant.phone or merchant.request_id.mobile
            res = {'phone': phone}
            
            return Response(json.dumps(res,
                sort_keys=True, indent=4, cls=ObjectEncoder),
                content_type='application/json;charset=utf-8', status=200) 
        
        except:
            return Response(json.dumps({'error': 'About API not working'},
                sort_keys=True, indent=4, cls=ObjectEncoder),
                content_type='application/json;charset=utf-8', status=500)

    
    @http.route('/api/refresh', auth="none", type='http', methods=['POST'], csrf=False)
    def api_refresh(self, token=None, **kw):
        check_params({'token': token})
        ensure_db()
        check_token()
        env = api.Environment(request.cr, odoo.SUPERUSER_ID, {})
        result = env['loyalty_rest.token'].refresh_token(token)
        return Response(json.dumps(result,
            sort_keys=True, indent=4, cls=ObjectEncoder),
            content_type='application/json;charset=utf-8', status=200)

    @http.route('/api/password/change', auth="none", type='http', methods=['POST'], csrf=False)
    def api_password_change(self, token=None, ids=None, new_password = None,  **kw):
        check_params({'ids': ids, 'token': token})
        ensure_db()
        check_token()
        try:
            env = api.Environment(request.cr, odoo.SUPERUSER_ID, {})
            user = env['res.users'].browse(ids)
            user.write({'password': new_password})
            return Response(json.dumps({'success': 'Password Changed Successfully'},
                sort_keys=True, indent=4, cls=ObjectEncoder),
                content_type='application/json;charset=utf-8', status=200)
        except:
            return Response(json.dumps({'error': 'Error in Changing Password'},
                sort_keys=True, indent=4, cls=ObjectEncoder),
                content_type='application/json;charset=utf-8', status=500)

    @http.route('/api/password/reset', auth="none", type='http', methods=['POST'], csrf=False)
    def api_password_reset(self, login=None, **kw):
        ensure_db()
        try:
            env = api.Environment(request.cr, odoo.SUPERUSER_ID, {})
            if not env['res.users'].search([('login','=',login)]):                
                return Response(json.dumps({'error': 'This email is not registered.'},
                sort_keys=True, indent=4, cls=ObjectEncoder),
                content_type='application/json;charset=utf-8', status=500)
            request.env['res.users'].sudo().reset_password(login)
            return Response(json.dumps({'success': 'A Reset link has been sent to your email.'},
                sort_keys=True, indent=4, cls=ObjectEncoder),
                content_type='application/json;charset=utf-8', status=200)
            
        except:
            return Response(json.dumps({'error': 'Error in Reseting Password'},
                sort_keys=True, indent=4, cls=ObjectEncoder),
                content_type='application/json;charset=utf-8', status=500)
    
    @http.route([
        '/api/life',
        '/api/life/<string:token>'], auth="none", type='http', csrf=False)
    def api_life(self, token=None, **kw):
        check_params({'token': token})
        ensure_db()
        check_token()
        env = api.Environment(request.cr, odoo.SUPERUSER_ID, {})
        result = env['loyalty_rest.token'].lifetime_token(token)
        return Response(json.dumps(result,
            sort_keys=True, indent=4, cls=ObjectEncoder),
            content_type='application/json;charset=utf-8', status=200) 
        
    @http.route('/api/close', auth="none", type='http', methods=['POST'], csrf=False)
    def api_close(self, token=None, **kw):
        check_params({'token': token})
        ensure_db()
        check_token()
        env = api.Environment(request.cr, odoo.SUPERUSER_ID, {})
        result = env['loyalty_rest.token'].delete_token(token)
        return Response(json.dumps(result,
            sort_keys=True, indent=4, cls=ObjectEncoder),
            content_type='application/json;charset=utf-8', status=200) 
    
    #----------------------------------------------------------
    # System
    #----------------------------------------------------------
        
    @http.route([
        '/api/search',
        '/api/search/<string:model>',
        '/api/search/<string:model>/<int:id>',
        '/api/search/<string:model>/<int:id>/<int:limit>',
        '/api/search/<string:model>/<int:id>/<int:limit>/<int:offset>'], auth="none", type='http', csrf=False)
    def api_search(self, model='res.partner', id=None, domain=None, context=None, count=False,
               limit=80, offset=0, order=None, token=None, **kw):
        check_params({'token': token})
        ensure_db()
        check_token()
        try:
            args = domain and json.loads(domain) or []
            if id:
                args.append(['id', '=', id])
            context = context and json.loads(context) or {}
            default = request.session.context.copy()
            default.update(context)
            count = count and bool(count) or None
            limit = limit and int(limit) or None
            offset = offset and int(offset) or None
            model = request.env[model].with_context(default)
            result = model.search(args, offset=offset, limit=limit, order=order, count=count)
            return Response(json.dumps(result,
                sort_keys=True, indent=4, cls=ObjectEncoder),
                content_type='application/json;charset=utf-8', status=200)
        except Exception as error:
            _logger.error(error)
            abort({'error': traceback.format_exc()}, rollback=True, status=400)
        
    @http.route([
        '/api/read',
        '/api/read/<string:model>',
        '/api/read/<string:model>/<int:id>',
        '/api/read/<string:model>/<int:id>/<int:limit>',
        '/api/read/<string:model>/<int:id>/<int:limit>/<int:offset>'], auth="none", type='http', csrf=False)
    def api_read(self, model='res.partner', id=None, fields=None, domain=None, context=None,
             limit=80, offset=0, order=None, token=None, **kw):
        check_params({'token': token})
        ensure_db()
        check_token()
        try:
            fields = fields and json.loads(fields) or None
            args = domain and json.loads(domain) or []
            if id:
                args.append(['id', '=', id])
            context = context and json.loads(context) or {}
            default = request.session.context.copy()
            default.update(context)
            limit = limit and int(limit) or None
            offset = offset and int(offset) or None
            model = request.env[model].with_context(default)
            result = model.search_read(domain=args, fields=fields, offset=offset, limit=limit, order=order)
            return Response(json.dumps(result,
                sort_keys=True, indent=4, cls=ObjectEncoder),
                content_type='application/json;charset=utf-8', status=200)
        except Exception as error:
            _logger.error(error)
            abort({'error': traceback.format_exc()}, rollback=True, status=400)
            
    @http.route('/api/create', auth="none", type='http', methods=['POST'], csrf=False)
    def api_create(self, model='res.partner', values=None, context=None, token=None, **kw):
        check_params({'token': token})
        ensure_db()
        check_token()
        try:
            values = values and json.loads(values) or {}
            context = context and json.loads(context) or {}
            default = request.session.context.copy()
            default.update(context)
            model = request.env[model].with_context(default)
            result = model.create(values)
            return Response(json.dumps(result,
                sort_keys=True, indent=4, cls=ObjectEncoder),
                content_type='application/json;charset=utf-8', status=200)
        except Exception as error:
            _logger.error(error)
            abort({'error': traceback.format_exc()}, rollback=True, status=400)
            
    @http.route('/api/write', auth="none", type='http', methods=['PUT'], csrf=False)
    def api_write(self, model='res.partner', ids=None, values=None, context=None, token=None, **kw):
        check_params({'ids': ids, 'token': token})
        ensure_db()
        check_token()
        try:
            ids = ids and json.loads(ids) or []
            values = values and json.loads(values) or {}
            context = context and json.loads(context) or {}
            default = request.session.context.copy()
            default.update(context)
            model = request.env[model].with_context(default)
            records = model.browse(ids)
            result = records.write(values)
            return Response(json.dumps(result,
                sort_keys=True, indent=4, cls=ObjectEncoder),
                content_type='application/json;charset=utf-8', status=200)
        except Exception as error:
            _logger.error(error)
            abort({'error': traceback.format_exc()}, rollback=True, status=400)

    @http.route('/api/unlink', auth="none", type='http', methods=['DELETE'], csrf=False)
    def api_unlink(self, model='res.partner', ids=None, context=None, token=None, **kw):
        check_params({'ids': ids, 'token': token})
        ensure_db()
        check_token()
        try:
            ids = ids and json.loads(ids) or []
            context = context and json.loads(context) or {}
            default = request.session.context.copy()
            default.update(context)
            model = request.env[model].with_context(default)
            records = model.browse(ids)
            result = records.unlink()
            return Response(json.dumps(result,
                sort_keys=True, indent=4, cls=ObjectEncoder),
                content_type='application/json;charset=utf-8', status=200)
        except Exception as error:
            _logger.error(error)
            abort({'error': traceback.format_exc()}, rollback=True, status=400)
            
    @http.route('/api/call', auth="none", type='http', methods=['POST'], csrf=False)
    def api_call(self, model='res.partner', method=None, ids=None, context=None, args=None,
               kwargs=None, token=None, **kw):
        check_params({'method': method, 'token': token})
        ensure_db()
        check_token()
        try:
            ids = ids and json.loads(ids) or []
            args = args and json.loads(args) or []
            kwargs = kwargs and json.loads(kwargs) or {}
            context = context and json.loads(context) or {}
            default = request.session.context.copy()
            default.update(context)
            model = request.env[model].with_context(default)
            records = model.browse(ids)
            result = getattr(records, method)(*args, **kwargs)
            return Response(json.dumps(result,
                sort_keys=True, indent=4, cls=ObjectEncoder),
                content_type='application/json;charset=utf-8', status=200)
        except Exception as error:
            _logger.error(error)
            abort({'error': traceback.format_exc()}, rollback=True, status=400)
            
    @http.route([
        '/api/report',
        '/api/report/<string:model>',
        '/api/report/<string:model>/<string:report>',
        ], auth="none", type='http', csrf=False)
    def api_report(self, model='res.partner', report=None, ids=None, type="pdf", context=None,
               args=None, kwargs=None, token=None, **kw):
        check_params({'report': report, 'ids': ids, 'token': token})
        ensure_db()
        check_token()
        try:
            ids = ids and json.loads(ids) or []
            args = args and json.loads(args) or []
            kwargs = kwargs and json.loads(kwargs) or {}
            context = context and json.loads(context) or {}
            default = request.session.context.copy()
            default.update(context)
            model = request.env[model].with_context(default)
            if type == "html":
                data = request.env.ref(report).render_qweb_html(ids)[0]
                headers = [
                    ('Content-Type', 'text/html'),
                    ('Content-Length', len(data)),
                ]
                return request.make_response(data, headers=headers)
            else:
                data = request.env.ref(report).render_qweb_pdf(ids)[0]
                headers = [
                    ('Content-Type', 'application/pdf'),
                    ('Content-Length', len(data)),
                ]
                return request.make_response(data, headers=headers)
        except Exception as error:
            _logger.error(error)
            abort({'error': traceback.format_exc()}, rollback=True, status=400)

    @http.route([
        '/api/binary',
        '/api/binary/<string:xmlid>',
        '/api/binary/<string:xmlid>/<string:filename>',
        '/api/binary/<int:id>',
        '/api/binary/<int:id>/<string:filename>',
        '/api/binary/<int:id>-<string:unique>',
        '/api/binary/<int:id>-<string:unique>/<string:filename>',
        '/api/binary/<string:model>/<int:id>/<string:field>',
        '/api/binary/<string:model>/<int:id>/<string:field>/<string:filename>'], auth="none", type='http', csrf=False)
    def api_binary(self, token=None, xmlid=None, model='ir.attachment', id=None, field='datas', filename=None,
               filename_field='datas_fname', unique=None, mimetype=None, **kw):
        ensure_db()
        check_token()
        try:
            status, headers, content = request.registry['ir.http'].binary_content(
                xmlid=xmlid, model=model, id=id, field=field, unique=unique, filename=filename,
                filename_field=filename_field, mimetype=mimetype, download=True)
            if status == 200:
                content_base64 = base64.b64decode(content)
                headers.append(('Content-Length', len(content_base64)))
                return request.make_response(content_base64, headers=headers)
            else:
                abort({'error': status}, status=status)
        except Exception as error:
            _logger.error(error)
            abort({'error': traceback.format_exc()}, rollback=True, status=400)


    ##################################################################
    # Custom API's
    ##################################################################

    @http.route('/api/loyalty/<point_type>/<partner_id>', auth="none", type='http', methods=['GET'], csrf=False)
    def api_get_points(self, token=None, **kw):
        ensure_db()
        check_token()       

        try:  
            customer_id = kw.get('partner_id')
            env = api.Environment(request.cr, odoo.SUPERUSER_ID, {})
            merchant_points_historys = env['loyalty.points.history'].search([('customer_id','=',int(kw.get('partner_id')))], order='create_date')
            page_no = int(kw.get('page'))
            merchant_points_history = [history for history in merchant_points_historys]            
            response = {}
            res = []           
            response['last'] = False
            from_record = (page_no - 1) * 10
            to_record = (page_no * 10)

            if to_record >= len(merchant_points_history):
                response['last'] = True

            if len(merchant_points_history) > 0:
                merchant_points_history.sort(key=lambda x: x.id, reverse=True)

            merchant_points_history = merchant_points_history[from_record:to_record]

            for merchant_point in merchant_points_history:
                data = {}
                data['merchant'] = merchant_point.merchant_id.name or merchant_point.merchant_id.request_id.shopname or ''
                # data['merchant_id'] = merchant_point.merchant_id.user_ids[0].id
                data['merchant_id'] = merchant_point.merchant_id.id

                # if merchant_point.merchant_id.image:
                    # data['logo'] = merchant_point.merchant_id.image.decode('utf-8')

                # elif merchant_point.merchant_id.parent_id.image:
                    # data['logo'] = merchant_point.merchant_id.parent_id.image.decode('utf-8')

                # elif merchant_point.merchant_id.request_id.logo:
                #     data['logo'] = merchant_point.merchant_id.request_id.logo.decode('utf-8')
                random_param = ''.join(random.choice(string.ascii_uppercase + string.digits) for _ in range(8)).lower()
                if merchant_point.merchant_id.image_url:
                    data['logo_url'] = '/api/image/partner/%s' % (merchant_point.merchant_id.id)
                
                elif merchant_point.merchant_id.parent_id.image_url:
                    data['logo_url'] = '/api/image/partner/%s' % (merchant_point.merchant_id.parent_id.id)

                if kw.get("point_type") == 'spend':
                    data['total_points'] = merchant_point.total_redeem_points
                
                elif kw.get("point_type") == 'reward':
                    data['total_points'] = merchant_point.points

                data['purchase_line'] = []

                for purchase in merchant_point.purchase_line:
                    if (kw.get('point_type') == 'reward' and purchase.point_type == 'in') or (kw.get('point_type') == 'spend' and purchase.point_type == 'out') :
                        purchase_data = {}
                        purchase_data['date'] = purchase.date.strftime('%d-%m-%Y')          
                        purchase_data['points'] = purchase.point 
                        purchase_data['currency'] = purchase.currency_id.symbol 
                        # if kw.get('point_type') == 'reward':
                        purchase_data['amt'] = purchase.purchase_amount
                        data['purchase_line'].append(purchase_data)
                res.append(data)
            response['data'] = res
            partner = env['res.partner'].browse(int(kw.get('partner_id')))
            response['my_points'] = partner.loyalty_points

            return Response(json.dumps(response,
                    sort_keys=True, indent=4),
                    content_type='application/json;charset=utf-8', status=200) 
        except:

            return Response(json.dumps({'error': 'Points API not working'},
                sort_keys=True, indent=4, cls=ObjectEncoder),
                content_type='application/json;charset=utf-8', status=500)



    @http.route('/api/loyalty/home', auth="none", type='http', methods=['GET'], csrf=False)
    def api_app_home(self, token=None, uid=False, partner_id=False, **kw):
        """
        Homepage API
        """
        
        try:        

            env = api.Environment(request.cr, odoo.SUPERUSER_ID, {})
            res = {}
            
            for x in ['active_offers', 'vip_offers', 'top_offers']:
                res[x] = []
            
            partner = False

            if partner_id:            
                ensure_db()
                check_token()
                partner = env['res.partner'].browse(int(partner_id))
                # Custom Code
                res['username'] = partner.name.strip()
                res['balance'] = partner.loyalty_points
                res['unread_notification_count'] = len([x for x in partner.notification_line if not x.is_read])

            else:
                res['balance'] = 0
                res['unread_notification_count'] = 0

            #Top Graphic Ads Types
            top_offer_type_id = env.ref('loyalty.deal_type_top_graphic_ad').id
            extra_top_offer_type_id = env.ref('loyalty.deal_type_extra_top_graphic_ad').id
            active_offer_type_id = env.ref('loyalty.deal_type_active_offer').id
            vip_companies_type_id = env.ref('loyalty.deal_type_extra_vip_ad').id

            top_offers = env['loyalty.deal'].search([('state','=','publish'), ('type_id','in',[top_offer_type_id,extra_top_offer_type_id])])
            active_offers = env['loyalty.deal'].search([('state','=','publish'), ('type_id','in',[active_offer_type_id])])
            vip_offers = env['loyalty.deal'].search([('state','=','publish'), ('type_id','=', vip_companies_type_id)])

            for offer_details in [{'d_type':'top_offers', 'deals':top_offers}, {'d_type':'active_offers', 'deals':active_offers}, {'d_type':'vip_offers', 'deals':vip_offers}]:
                for offer in offer_details['deals']:
                    offer_data = {}
                    # offer_data['image_url'] = '/api/image/deals/%s' % (offer.id)image_url_public
                    offer_data['image_url'] = offer.image_url_public
                    offer_data['id'] = offer.id
                    offer_data['title'] = offer.title
                    offer_data['rating_avg'] = offer.rating
                    offer_data['is_favorite'] = False
                    if partner:
                        if offer.id in partner.favourite_deal_ids.ids:
                            offer_data['is_favorite'] = True

                    if offer.expiration_date:
                        today =  datetime.datetime.today().date()
                        offer_data['expire_in'] = '%s days left' % (offer.expiration_date - today).days
                                    
                    res[offer_details['d_type']].append(offer_data)

            return Response(json.dumps(res,
                        sort_keys=True, indent=4),
                        content_type='application/json;charset=utf-8', status=200) 
        except: 

            return Response(json.dumps({'error': 'HomepageAPI not working'},
                sort_keys=True, indent=4, cls=ObjectEncoder),
                content_type='application/json;charset=utf-8', status=500)

    # @http.route('/api/loyalty/deal-detail/<deal_id>/<partner_id>', auth="none", type='http', methods=['GET'], csrf=False)
    # def api_app_deal_detail(self, token=None, **kw):
    #     check_params({'token': token})
    #     ensure_db()
    #     check_token()   
        
    #     try:
    #         env = api.Environment(request.cr, odoo.SUPERUSER_ID, {})
    #         res = {}

    #         if not kw.get('deal_id') or not kw.get('partner_id'):
    #             return Response(json.dumps({'error': 'Parameters Missing'},
    #                 sort_keys=True, indent=4, cls=ObjectEncoder),
    #                 content_type='application/json;charset=utf-8', status=500)
            
    #         deal = env['loyalty.deal'].browse(int(kw.get('deal_id')))
    #         text_ad_id = env.ref('loyalty.deal_type_text_ad').id
    #         extra_text_ad_id = env.ref('loyalty.deal_type_extra_text_ad').id
    #         res['image_url'] = ''
    #         random_param = ''.join(random.choice(string.ascii_uppercase + string.digits) for _ in range(8)).lower()
    #         if deal.type_id.id not in [text_ad_id,extra_text_ad_id]:
    #             res['image_url'] = '/api/image/deals/%s?random=%s' % (deal.id, random_param)
    #         # res['image'] = deal.image.decode('utf-8') if deal.image else ''
    #         res['title'] = deal.title
    #         res['description'] = deal.description
    #         res['mobile'] = deal.merchant_id.mobile or deal.merchant_id.parent_id.mobile or deal.merchant_id.request_id.mobile or ''
    #         res['shopname'] = deal.merchant_id.parent_id.name or deal.merchant_id.request_id.shopname or ''
    #         res['location_lat'] = deal.merchant_id.request_id.location_lat
    #         res['location_lng'] = deal.merchant_id.request_id.location_lng

    #         res['location_address'] = deal.merchant_id.request_id.location
    #         res['location_city'] = deal.merchant_id.request_id.city.name if deal.merchant_id.request_id.city else ''
    #         res['location_country'] = deal.merchant_id.request_id.country_id.name if deal.merchant_id.request_id.country_id else ''

    #         res['social_gplus_link'] = deal.merchant_id.social_gplus_link or deal.merchant_id.request_id.social_gplus_link or ''
    #         res['social_fb_link'] =  deal.merchant_id.social_fb_link or deal.merchant_id.request_id.social_fb_link or ''

            
    #         return Response(json.dumps(res,
    #                     sort_keys=True, indent=4),
    #                     content_type='application/json;charset=utf-8', status=200)

    #     except:
    #         return Response(json.dumps({'error': 'Deal Detail API not working'},
    #             sort_keys=True, indent=4, cls=ObjectEncoder),
    #             content_type='application/json;charset=utf-8', status=500)


    @http.route('/api/loyalty/deal/category', auth="none", type='http', methods=['GET'], csrf=False)
    def api_app_deal_categories(self, **kw):
        ensure_db()
        try:
            env = api.Environment(request.cr, odoo.SUPERUSER_ID, {})
            res = []

            for categ in env['merchant.shop.type'].search([]):
                data_list = {}
                data_list['category_name'] = categ.name
                data_list['category_icon_url'] = ''
                random_param = ''.join(random.choice(string.ascii_uppercase + string.digits) for _ in range(8)).lower()

                if categ.icon_img and categ.icon_img_url:
                    data_list['category_icon_url'] = '/api/image/category/%s' % (categ.id)

                data_list['category_icon_with_bg_url'] = ''
                if categ.icon_img_with_bg and categ.icon_img_with_bg_url:
                    data_list['category_icon_with_bg_url'] = '/api/image/category_with_bg/%s' % (categ.id)

                data_list['category_id'] = categ.id
                res.append(data_list)
            
            return Response(json.dumps(res,
                        sort_keys=True, indent=4),
                        content_type='application/json;charset=utf-8', status=200)
        except:
            return Response(json.dumps({'error': 'Category API not working'},
                sort_keys=True, indent=4, cls=ObjectEncoder),
                content_type='application/json;charset=utf-8', status=500)


    # @http.route('/api/loyalty/deal/', auth="none", type='http', methods=['GET'], csrf=False)
    # def api_app_deal(self, token=None, **kw):
    #     check_params({'partner_id': kw.get('partner_id'), 'category_id':kw.get('category_id')})
    #     ensure_db()
    #     # check_token()
    #     # try:
    #     env = api.Environment(request.cr, odoo.SUPERUSER_ID, {})
    #     res = {}
        
    #     partner = env['res.partner'].browse(int(kw.get('partner_id')))

    #     #Top Graphic Ads Types
    #     text_ad_id = env.ref('loyalty.deal_type_text_ad').id
    #     graphic_ad_id = env.ref('loyalty.deal_type_graphic_ad').id
    #     extra_text_ad_id = env.ref('loyalty.deal_type_extra_text_ad').id
    #     extra_graphic_ad_id = env.ref('loyalty.deal_type_extra_graphic_ad').id

    #     merchant_ids = []
    #     categ = env['merchant.shop.type'].browse(int(kw.get('category_id')))
        
    #     res['slider_images'] = []
    #     res['merchants_deals'] = []
        
    #     if kw.get('deal_type') == 'all':
    #         # Search All Merchant Deals
    #         all_deals = env['loyalty.deal'].search([('category_id','=',categ.id), ('state','=','publish'), ('type_id','in',[text_ad_id,extra_text_ad_id,graphic_ad_id, extra_graphic_ad_id])])
            
    #     elif kw.get('deal_type') == 'my':
    #         merchant_ids = [x.merchant_id.id for x in partner.points_line]
    #         if partner.registering_merchant_id:
    #             merchant_ids.append(partner.registering_merchant_id.id)
    #         all_deals = env['loyalty.deal'].search([('category_id','=',categ.id), ('state','=','publish'), ('type_id','in',[text_ad_id,extra_text_ad_id, graphic_ad_id, extra_graphic_ad_id]), ('merchant_id','in', merchant_ids)])

    #     # Grouping Deals by Merchant
    #     merchants_deals = {}
    #     for each_deal in all_deals:
    #         if each_deal.merchant_id in merchants_deals:
    #             merchants_deals[each_deal.merchant_id].append(each_deal)
    #         else:
    #             merchants_deals[each_deal.merchant_id] = [each_deal]
    #             merchants_deals[each_deal.merchant_id].sort(key=lambda x: x.create_date, reverse=True)
        
    #     # Paginate the deals
    #     if not kw.get('page_no'):
    #         kw['page_no'] = 1

    #     page_no = int(kw.get('page_no'))

    #     res['last'] = False
    #     from_record = (page_no - 1) * 5
    #     to_record = (page_no * 5)

    #     if to_record >= len(merchants_deals):
    #         res['last'] = True

    #     odict =  OrderedDict(sorted(merchants_deals.items(), key=lambda t: t[0].name))
        
    #     merchants_deals = {key:value for key,value in list(odict.items())[from_record:to_record]}
        
    #     for merchant,deals in merchants_deals.items():
    #         merchant_deal_data = {}
    #         merchant_deal_data['merchant_name'] = merchant.parent_id.name or merchant.name
    #         merchant_deal_data['merchant_city'] = merchant.city.name or merchant.request_id.city.name or ''
    #         merchant_deal_data['merchant_id'] = merchant.id
    #         random_param = ''.join(random.choice(string.ascii_uppercase + string.digits) for _ in range(8)).lower()
            
    #         if merchant.image_url:
    #             merchant_deal_data['merchant_image_url'] = '/api/image/partner/%s?random=%s' % (merchant.id, random_param)

    #         elif merchant.parent_id.image_url:
    #             merchant_deal_data['merchant_image_url'] = '/api/image/partner/%s?random=%s' % (merchant.parent_id.id, random_param)

    #         merchant_deal_data['deals'] = []
    #         for deal in deals:
    #             deal_data = {}
    #             if deal.type_id.id in [text_ad_id, extra_text_ad_id]:
    #                 deal_data['type'] = 'text'
                
    #             elif deal.type_id.id in [graphic_ad_id, extra_graphic_ad_id]:
    #                 deal_data['type'] = 'graphic'
    #                 if deal.image:
    #                     res['slider_images'].append({'image_url':'/api/image/deals/%s?random=%s' % (deal.id, random_param), 'deal_id':deal.id})

    #             deal_data['title'] = deal.title
    #             deal_data['deal_id'] = deal.id
    #             merchant_deal_data['deals'].append(deal_data)
    #         res['merchants_deals'].append(merchant_deal_data)

    #     #Double Ordering after clipping selected records
    #     if res.get('merchants_deals'):
    #         res['merchants_deals'] = sorted(res['merchants_deals'], key=lambda k: k['merchant_name'])

    #     return Response(json.dumps(res,
    #             sort_keys=True, indent=4),
    #             content_type='application/json;charset=utf-8', status=200) 

    #     # except:
    #     #     return Response(json.dumps({'error': 'Deal List API not working'},
    #     #         sort_keys=True, indent=4, cls=ObjectEncoder),
    #     #         content_type='application/json;charset=utf-8', status=500)


    @http.route('/api/loyalty/mobile-verify', auth="none", type='http', methods=['GET'], csrf=False)
    def api_app_verify_mobile(self, mobile=False, **kw):
        try:
            env = api.Environment(request.cr, odoo.SUPERUSER_ID, {})
            if not mobile:
                return Response(json.dumps({'error': 'Mobile No. not provided.'},
                    sort_keys=True, indent=4, cls=ObjectEncoder),
                    content_type='application/json;charset=utf-8', status=500)
            else:
                mobile = "+"+mobile.strip()
                sms_sent = env['res.partner'].send_register_verification_otp(mobile=mobile)
                if sms_sent:
                    return Response(json.dumps({'msg': 'OTP Sent Successfully.'},
                            sort_keys=True, indent=4),
                            content_type='application/json;charset=utf-8', status=200)
                else:
                    return Response(json.dumps({'error': 'Error Sending OTP via SMS. Please check mobile number again.'},
                            sort_keys=True, indent=4),
                            content_type='application/json;charset=utf-8', status=500)

        except:
            return Response(json.dumps({'error': 'Mobile Verification API not working'},
                sort_keys=True, indent=4, cls=ObjectEncoder),
                content_type='application/json;charset=utf-8', status=500)


    @http.route('/api/edit-profile', auth="none", type='http', methods=['POST'], csrf=False)
    def api_edit_profile(self, token=None, user_id=False, **kw):
        check_params({'token': token, 'user_id':user_id})
        ensure_db()
        check_token()
        try:
            env = api.Environment(request.cr, odoo.SUPERUSER_ID, {})
            user = env['res.users'].browse(int(user_id))
            profile_complete = False
            if user:
                kw.pop('db')
                if kw.get('image'):             
                    kw['image'] = kw.get('image').replace(' ','+')
                    img_data = kw.get('image')                
                    
                    if len(img_data) % 4:
                        img_data += '=' * (4 - len(img_data) % 4)
                    kw['image'] = img_data

                if not kw.get('dob'):
                    kw['dob'] = False

                if kw.get('mobile'):
                    kw['mobile'] = '+'+kw.get('mobile').strip()
              
                if env['res.partner'].search([('mobile','=', kw.get('mobile')),('id','!=',user.partner_id.id)]):
                    return Response(json.dumps({'error': 'Mobile No. Already Registered','profile_complete':profile_complete},
                                    sort_keys=True, indent=4, cls=ObjectEncoder),
                                    content_type='application/json;charset=utf-8', status=500)

                if kw.get('mobile') != user.partner_id.mobile: 
                    registered_otp = env['loyalty.mobile.otp.register'].search([('mobile','=', kw.get('mobile'))], limit=1)
                    if kw.get('otp') and registered_otp:
                        if kw.get('otp') == registered_otp.otp:
                            kw.pop('otp')
                            kw['mobile_verified'] = True
                            partner = user.partner_id.write(kw)

                        if user.partner_id.mobile and user.partner_id.mobile_verified:
                            profile_complete = True

                            return Response(json.dumps({'msg': 'Profile Updated Successfully!!','profile_complete':profile_complete},
                                sort_keys=True, indent=4, cls=ObjectEncoder),
                                content_type='application/json;charset=utf-8', status=200)
                        else:
                            return Response(json.dumps({'error': 'Invalid OTP','profile_complete':profile_complete},
                                sort_keys=True, indent=4, cls=ObjectEncoder),
                                content_type='application/json;charset=utf-8', status=500)
                    else:
                        return Response(json.dumps({'error': 'Invalid OTP','profile_complete':profile_complete},
                                sort_keys=True, indent=4, cls=ObjectEncoder),
                                content_type='application/json;charset=utf-8', status=500)
                else :
                    if env['res.partner'].search([('mobile','=',kw.get('mobile'))]):
                        if user.partner_id.mobile != kw.get('mobile'):
                            return Response(json.dumps({'error': 'Mobile No. Already Registered','profile_complete':profile_complete},
                                    sort_keys=True, indent=4, cls=ObjectEncoder),
                                    content_type='application/json;charset=utf-8', status=500)
                    if kw.get('otp'):
                        kw.pop('otp')
                    partner = user.partner_id.write(kw)

                    if user.partner_id.mobile and user.partner_id.mobile_verified:
                            profile_complete = True
                    return Response(json.dumps({'msg': 'Profile Updated Successfully!!','profile_complete':profile_complete},
                                sort_keys=True, indent=4, cls=ObjectEncoder),
                                content_type='application/json;charset=utf-8', status=200)

        except:
            return Response(json.dumps({'error': 'Error updating profile'},
                    sort_keys=True, indent=4, cls=ObjectEncoder),
                    content_type='application/json;charset=utf-8', status=500)


    @http.route('/api/loyalty/merchant-detail', auth="none", type='http', methods=['GET'], csrf=False)
    def api_app_merchant_detail(self, token=None, partner_id=False, **kw):
        ensure_db()
        check_token()
        check_params({'merchant_id': kw.get('merchant_id'), 'partner_id':partner_id})
        try:
            res = {}
            env = api.Environment(request.cr, odoo.SUPERUSER_ID, {})

            merchant = env['res.partner'].browse(int(kw.get('merchant_id')))
            
            res['shopname'] = merchant.name or merchant.request_id.shopname or ''
            res['shop_icon_url'] = ''
            random_param = ''.join(random.choice(string.ascii_uppercase + string.digits) for _ in range(8)).lower()
            if merchant.image and merchant.image_url: 
                res['shop_icon_url'] = '/api/image/partner/%s' % (merchant.id)

            # res['shop_icon'] = merchant.parent_id.image.decode('utf-8') if merchant.parent_id.image else ''
            res['shop_images'] = []
            res['deals'] = []

            if merchant.request_id:
                for imgLine in merchant.request_id.images_line:
                    if imgLine.image_url:
                        res['shop_images'].append('/api/image/shop/%s' % (imgLine.id))
                    
            text_ad_id = env.ref('loyalty.deal_type_text_ad').id
            graphic_ad_id = env.ref('loyalty.deal_type_graphic_ad').id
            extra_text_ad_id = env.ref('loyalty.deal_type_extra_text_ad').id
            extra_graphic_ad_id = env.ref('loyalty.deal_type_extra_graphic_ad').id

            res['location_lat'] = merchant.request_id.location_lat
            res['location_lng'] = merchant.request_id.location_lng
            res['location_address'] = merchant.request_id.location
            res['location_city'] = merchant.request_id.city.name if merchant.request_id.city else ''
            res['location_country'] = merchant.request_id.country_id.name if merchant.request_id.country_id else ''
            res['mobile'] = merchant.mobile or merchant.parent_id.mobile or merchant.request_id.mobile or ''
            res['category_id'] =  merchant.request_id.shop_type_id.id or ''
            # Social Links
            res['social_gplus_link'] = merchant.social_gplus_link or merchant.request_id.social_gplus_link or ''
            res['social_fb_link'] =  merchant.social_fb_link or merchant.request_id.social_fb_link or ''
            res['category_id'] =  merchant.request_id.shop_type_id.id or ''

            merchant_point = env['loyalty.points.history'].search([('merchant_id','=', merchant.id), ('customer_id','=',int(partner_id))], limit=1)
            res['merchant_point'] = merchant_point.points or 0

            all_deals = env['loyalty.deal'].search([('merchant_id','=', merchant.id), ('state','=','publish'), ('type_id','in',[text_ad_id,extra_text_ad_id,graphic_ad_id, extra_graphic_ad_id])])

            for deal in all_deals:
                deal_data = {}
                
                if deal.type_id.id in [text_ad_id, extra_text_ad_id]:
                    deal_data['type'] = 'text'
                
                elif deal.type_id.id in [graphic_ad_id, extra_graphic_ad_id]:
                    deal_data['type'] = 'graphic'
                    
                deal_data['title'] = deal.title
                deal_data['deal_id'] = deal.id
                res['deals'].append(deal_data)
            
            return Response(json.dumps(res,
                                sort_keys=True, indent=4, cls=ObjectEncoder),
                                content_type='application/json;charset=utf-8', status=200)

        except:
            return Response(json.dumps({'error': 'Merchant Detail API Not Working'},
                    sort_keys=True, indent=4, cls=ObjectEncoder),
                    content_type='application/json;charset=utf-8', status=500)


    @http.route('/api/image/<image_type>/<record_id>', auth="none", type='http', methods=['GET'], csrf=False, cors="*")
    def api_app_image(self, token=None, **kw):
        try:

            record_id = int(kw.get('record_id'))
            image_type = kw.get('image_type')

            env = api.Environment(request.cr, odoo.SUPERUSER_ID, {})

            if image_type == 'deals':
                deal = env['loyalty.deal'].browse(record_id)
                if deal.image and deal.image_url:
                    with open(deal.image_url, 'rb') as img:
                        return http.Response(img.read(), content_type='image/png')
                else:
                    return werkzeug.exceptions.NotFound()

            elif image_type == 'partner':
                merchant = env['res.partner'].browse(record_id)
                if merchant.parent_id:

                    merchant = merchant.parent_id
                    
                if merchant.image and merchant.image_url:
                    with open(merchant.image_url, 'rb') as img:
                        return http.Response(img.read(), content_type='image/png')
                else:
                    return werkzeug.exceptions.NotFound()

            elif image_type == 'shop':
                shop = env['merchant.request.images.line'].browse(record_id)
                if shop.image and shop.image_url:                
                    with open(shop.image_url, 'rb') as img:
                        return http.Response(img.read(), content_type='image/png')
                else:
                    return werkzeug.exceptions.NotFound()

            elif image_type in ['category', 'category_with_bg']:
                category = env['merchant.shop.type'].browse(record_id)
                
                if image_type == 'category':
                    with open(category.icon_img_url, 'rb') as img:
                        return http.Response(img.read(), content_type='image/png')

                elif image_type == 'category_with_bg':
                    with open(category.icon_img_with_bg_url, 'rb') as img:
                        return http.Response(img.read(), content_type='image/png')
                        
                return werkzeug.exceptions.NotFound()

        except:
            return Response(json.dumps({'error': 'Image Not Available'},
                    sort_keys=True, indent=4, cls=ObjectEncoder),
                    content_type='application/json;charset=utf-8', status=500)



    #################################################
    # POINTS API [UPDATED]
    #################################################

    @http.route('/api/my/<point_type>', auth="none", type='http', methods=['GET'], csrf=False)
    def api_get_loyalty_points(self,  token=None, partner_id=False, **kw):
        """
        API return reward points
        """
        ensure_db()
        check_token()
        check_params({'partner_id':partner_id, 'point_type':kw.get('point_type')})
        try:
            env = api.Environment(request.cr, odoo.SUPERUSER_ID, {})
            res = {'merchant_points_line':[]}
            partner = env['res.partner'].browse(int(partner_id))
            try:
                for point_line in partner.points_line:
                    merchant_point_dict = {'merchant_id':point_line.merchant_id.id}
                    merchant_point_dict['purchase_line'] = []
                    merchant_point_dict['merchant_icon_url'] = '/api/image/partner/%s' % (point_line.merchant_id.id)
                    merchant_point_dict['total_points'] = point_line.points
                    merchant_point_dict['merchant_name'] = point_line.merchant_id.name
                    for pur_line in point_line.purchase_line:
                        purchase_line_dict = {
                            'merchant_id':pur_line.merchant_id.id,
                            'merchant_name':pur_line.merchant_id.name,
                            'date':pur_line.date.strftime('%d/%m/%Y'),
                            'purchase_amount':pur_line.purchase_amount,
                            'point':pur_line.point,
                            'point_redeem':pur_line.point_redeem,
                            'point_remaining':pur_line.point_remaining,
                            'is_closed':pur_line.is_closed,
                            'is_group':pur_line.is_group,
                            'is_settled':pur_line.is_settled,
                        }
                        if kw.get('point_type') == 'spend':
                            purchase_line_dict['redeem_line'] = []
                            for spend_line in pur_line.redeem_line:
                                redeem_line_dict = {
                                    'redeem_merchant_id':spend_line.redeem_merchant_id.name,
                                    'redeem_merchant':spend_line.redeem_merchant_id.id,
                                    'redeem_point':spend_line.redeem_point,
                                }
                                purchase_line_dict['redeem_line'].append(redeem_line_dict)
                        merchant_point_dict['purchase_line'].append(purchase_line_dict)
                    res['merchant_points_line'].append(merchant_point_dict)
                return Response(json.dumps(res,
                        sort_keys=True, indent=4, cls=ObjectEncoder),
                        content_type='application/json;charset=utf-8', status=200)
            except:
                return Response(json.dumps({'error': 'Customer not exists'},
                    sort_keys=True, indent=4, cls=ObjectEncoder),
                    content_type='application/json;charset=utf-8', status=500)

        except:
            return Response(json.dumps({'error': 'API not working'},
                    sort_keys=True, indent=4, cls=ObjectEncoder),
                    content_type='application/json;charset=utf-8', status=500)


    @http.route('/api/favorite/<favorite_type>', auth="none", type='http', methods=['GET'], csrf=False)
    def api_get_favorite(self,  token=None, partner_id=False, **kw):
        """
        This API returns Favorite brands and 
        merchants based on the selected partner. 
        """
        # if 
        ensure_db()
        check_token()
        check_params({'partner_id':partner_id, 'favorite_type':kw.get('favorite_type')})
        env = api.Environment(request.cr, odoo.SUPERUSER_ID, {})
        partner = env['res.partner'].browse(int(partner_id))
        res = []

        try:
            if kw.get('favorite_type') == 'brand':
                for merchant in partner.favourite_merchant_ids:
                    res.append({
                            'merchant_name':merchant.name,
                            'merchant_id':merchant.id,
                            'image_url':'/api/image/partner/%s' % (merchant.id)
                        })
            
            elif kw.get('favorite_type') == 'deal':
                for deal in partner.favourite_deal_ids:
                    # res['expire_in'] = False
                    deal_vals = {
                        'deal_name':deal.name,
                        'deal_title':deal.title,
                        'merchant_name':deal.merchant_id.name,
                        'deal_id':deal.id,
                        'image_url': deal.image_url_public,
                        'expire_in':False
                    }
                    if deal.expiration_date:
                        today =  datetime.datetime.today().date()
                        deal_vals['expire_in'] = '%s days left' % (deal.expiration_date - today).days
                    res.append(deal_vals)                    
            else:
                return Response(json.dumps({'error': 'Invalid API Call'},
                    sort_keys=True, indent=4, cls=ObjectEncoder),
                    content_type='application/json;charset=utf-8', status=500)

            return Response(json.dumps(res,
                    sort_keys=True, indent=4, cls=ObjectEncoder),
                    content_type='application/json;charset=utf-8', status=200)

        except:
            return Response(json.dumps({'error': 'API not working'},
                    sort_keys=True, indent=4, cls=ObjectEncoder),
                    content_type='application/json;charset=utf-8', status=500)


    @http.route('/api/favorite/update/<favorite_type>/<action>', auth="none", type='http', methods=['POST'], csrf=False)
    def api_favorite_update(self,  token=None, partner_id=False, deal_id=False, merchant_id=False, **kw):
        """
        This method favorites/unfavorite the merchants/deals
        from the customer profile
        @param - token (Auth Token) Type(Char)
        @param - partner_id(Session Partner_id) Type(int)
        @param - deal_id Type(int)
        @param - merchant_id Type(int)
        @kw - Type (dict)
        """
        ensure_db()
        check_token()
        check_params({'favorite_type':kw.get('favorite_type')})

        if kw.get('favorite_type') == 'deal':
            check_params({
                'partner_id':partner_id,
                'deal_id':deal_id, 
                'action':kw.get('action'), 
            })
        
        elif kw.get('favorite_type') == 'merchant':
            check_params({
                'partner_id':partner_id,
                'action':kw.get('action'), 
                'merchant_id':merchant_id
            })

        try:

            env = api.Environment(request.cr, odoo.SUPERUSER_ID, {})
            res = {}
            partner = env['res.partner'].browse(int(partner_id))

            # Check if favorite type is deal
            if kw.get('favorite_type') == 'deal':
                partner_favorite_deal_ids = partner.favourite_deal_ids.ids
                if (kw.get('action') == 'add') and (int(deal_id) not in partner_favorite_deal_ids):
                    partner_favorite_deal_ids.append(int(deal_id))

                elif (kw.get('action') == 'remove') and (int(deal_id) in partner_favorite_deal_ids):
                    partner_favorite_deal_ids.remove(int(deal_id))

                partner.write({'favourite_deal_ids':[(6, 0, partner_favorite_deal_ids)]}) 
                res = {'deal_id':int(deal_id), 'result':'success'}

            # Check if favorite type is merchant
            elif kw.get('favorite_type') == 'merchant':
                partner_favorite_merchant_ids = partner.favourite_merchant_ids.ids
                if (kw.get('action') == 'add') and (int(merchant_id) not in partner_favorite_merchant_ids):
                    partner_favorite_merchant_ids.append(int(merchant_id))

                elif (kw.get('action') == 'remove') and (int(merchant_id) in partner_favorite_merchant_ids):
                    partner_favorite_merchant_ids.remove(int(merchant_id))

                # Update Partner with new list of favorite merchants created above.
                partner.write({'favourite_merchant_ids':[(6, 0, partner_favorite_merchant_ids)]}) 

                res = {'merchant_id':int(merchant_id), 'result':'success'}

            return Response(json.dumps(res,
                sort_keys=True, indent=4, cls=ObjectEncoder),
                content_type='application/json;charset=utf-8', status=200)

        except:
            return Response(json.dumps({'error': 'API not working'},
                    sort_keys=True, indent=4, cls=ObjectEncoder),
                    content_type='application/json;charset=utf-8', status=500)


    @http.route('/api/loyalty/deal-detail/<deal_id>', auth="none", type='http', methods=['GET'], csrf=False)
    def api_deal_detail(self, token=None, partner_id=False, **kw):
        """
            This method returns deal deatils
            from the customer profile
            @param - token (Auth Token) Type(Char)
            @param - partner_id(Session Partner_id) Type(int)
            @kw - Type (dict)
        """
        ensure_db()
        check_params({'deal_id':kw.get('deal_id')})
        
        if partner_id:
            partner_id = int(partner_id)
            check_token()

        try:
            env = api.Environment(request.cr, odoo.SUPERUSER_ID, {})
            res = {}
            deal = env['loyalty.deal'].browse(int(kw.get('deal_id')))
            
            res['deal_id'] = deal.id
            res['title'] = deal.title
            res['expire_in'] = False
            res['rating'] = deal.rating
            res['description'] = deal.description
            res['own_rating'] = 0
            res['image_url'] = ''
            res['is_favorite'] = False

            if deal.image and deal.image_url:
                res['image_url'] = deal.image_url_public

            if deal.expiration_date:
                today =  datetime.datetime.today().date()
                res['expire_in'] = '%s days left' % (deal.expiration_date - today).days
            
            if partner_id:
                for rating in deal.rating_line:
                    if rating.customer_id.id == partner_id:
                        res['own_rating'] = rating.rating or 0

                partner = env['res.partner'].browse(int(partner_id))
                if deal.id in partner.favourite_deal_ids.ids:
                    res['is_favorite'] = True

            return Response(json.dumps(res,
                sort_keys=True, indent=4, cls=ObjectEncoder),
                content_type='application/json;charset=utf-8', status=200)

        except:
            return Response(json.dumps({'error': 'API not working'},
                    sort_keys=True, indent=4, cls=ObjectEncoder),
                    content_type='application/json;charset=utf-8', status=500)


    @http.route('/api/loyalty/merchant-detail/<merchant_id>', auth="none", type='http', methods=['GET'], csrf=False)
    def api_shop_detail(self, token=None, partner_id=False, **kw):
        """
            This method returns merchant/shop deatils
            from the customer profile
            @param - token (Auth Token) Type(Char)
            @param - partner_id(Session Partner_id) Type(int)
            @kw - Type (dict)
        """
        ensure_db()
        check_params({'merchant_id':kw.get('merchant_id')})
        
        if partner_id:
            partner_id = int(partner_id)
            # check_token()            

        try:
            env = api.Environment(request.cr, odoo.SUPERUSER_ID, {})

            # Copy code
            res = {}

            merchant = env['res.partner'].browse(int(kw.get('merchant_id')))
            
            res['shopname'] = merchant.name or merchant.request_id.shopname or ''
            res['shop_icon_url'] = ''                   
            if merchant.image and merchant.image_url: 
                res['shop_icon_url'] = '/api/image/partner/%s' % (merchant.id)

            # res['shop_icon'] = merchant.parent_id.image.decode('utf-8') if merchant.parent_id.image else ''
            res['shop_images'] = []
            res['deals'] = []
            
            res['social_gplus_link'] = merchant.social_gplus_link or merchant.request_id.social_gplus_link or ''
            res['social_fb_link'] =  merchant.social_fb_link or merchant.request_id.social_fb_link or ''
            
            if merchant.request_id:
                for imgLine in merchant.request_id.images_line:
                    if imgLine.image_url:
                        res['shop_images'].append('/api/image/shop/%s' % (imgLine.id))
                    
            text_ad_id = env.ref('loyalty.deal_type_text_ad').id
            graphic_ad_id = env.ref('loyalty.deal_type_graphic_ad').id
            extra_text_ad_id = env.ref('loyalty.deal_type_extra_text_ad').id
            extra_graphic_ad_id = env.ref('loyalty.deal_type_extra_graphic_ad').id

            res['category_id'] =  merchant.request_id.shop_type_id.id or ''
            # ################
            res['is_favorite'] = False
            res['rating'] = merchant.rating
            res['own_rating'] = 0
            res['description'] =  merchant.request_id.description or ''
            # ################

            all_deals = env['loyalty.deal'].search([('merchant_id','=', merchant.id), ('state','=','publish'), ('type_id','in',[text_ad_id,extra_text_ad_id,graphic_ad_id, extra_graphic_ad_id])])

            for deal in all_deals:
                deal_data = {}
                
                if deal.type_id.id in [text_ad_id, extra_text_ad_id]:
                    deal_data['type'] = 'text'
                
                elif deal.type_id.id in [graphic_ad_id, extra_graphic_ad_id]:
                    deal_data['type'] = 'graphic'
                    
                deal_data['title'] = deal.title
                deal_data['deal_id'] = deal.id
                res['deals'].append(deal_data)
            
            # Copy code End

            if partner_id:
                merchant_point = env['loyalty.points.history'].search([('merchant_id','=', merchant.id), ('customer_id','=',int(partner_id))], limit=1)
                res['total_points'] = merchant_point.points or 0
                
                for rating in merchant.rating_line:
                    if rating.customer_id.id == partner_id:
                        res['own_rating'] = rating.rating or 0

                partner = env['res.partner'].browse(int(partner_id))

                if merchant.id in partner.favourite_merchant_ids.ids:
                    res['is_favorite'] = True

            return Response(json.dumps(res,
                sort_keys=True, indent=4, cls=ObjectEncoder),
                content_type='application/json;charset=utf-8', status=200)

        except:
            return Response(json.dumps({'error': 'API not working'},
                    sort_keys=True, indent=4, cls=ObjectEncoder),
                    content_type='application/json;charset=utf-8', status=500)


    # TODO :: Create All Deal and All Shops API generic

    # API FOR ALL Deals
    @http.route('/api/loyalty/deal', auth="none", type='http', methods=['GET'], csrf=False)
    def api_app_deal(self, token=None, partner_id=False, category_id=False, **kw):
        """
            This method returns all deal list
            @param - token (Auth Token) Type(Char)
            @param - partner_id(Session Partner_id) Type(int)
            @kw - Type (dict)
        """
        ensure_db()
        page_no = kw.get('page_no')

        try:
            res = {}
            env = api.Environment(request.cr, odoo.SUPERUSER_ID, {})
            partner = False

            if partner_id:
                check_token()
                partner = env['res.partner'].browse(int(partner_id))

            deals = []

            if category_id:
                category_id = int(category_id)
                deals = env['loyalty.deal'].search([
                        ('category_id','=',category_id), 
                        ('state','=','publish'), 
                    ])

            else:
                deals = env['loyalty.deal'].search([
                        ('state','=','publish'),
                    ])
            
            paginated = paginate(page_no=page_no, records=deals)
            res['last'] = paginated['last']
            res['deals'] = []

            for deal in paginated['records']:
                deal_data = {}
                deal_data['title'] = deal.title
                deal_data['deal_id'] = deal.id
                deal_data['image_url'] = deal.image_url_public
                deal_data['rating_avg'] = deal.rating
                deal_data['own_rating'] = 0
                deal_data['is_favorite'] = False
                
                if partner:
                    for rating in deal.rating_line:
                        if rating.customer_id.id == partner.id:
                            deal_data['own_rating'] = rating.rating or 0

                    if deal.id in partner.favourite_deal_ids.ids:
                        deal_data['is_favorite'] = True

                if deal.expiration_date:
                    today =  datetime.datetime.today().date()
                    deal_data['expire_in'] = '%s days left' % (deal.expiration_date - today).days
                
                res['deals'].append(deal_data)

            return Response(json.dumps(res,
                sort_keys=True, indent=4, cls=ObjectEncoder),
                content_type='application/json;charset=utf-8', status=200)

        except:
            return Response(json.dumps({'error': 'API not working'},
                    sort_keys=True, indent=4, cls=ObjectEncoder),
                    content_type='application/json;charset=utf-8', status=500)


    # API FOR ALL Shops
    @http.route('/api/loyalty/shop/<list_type>', auth="none", type='http', methods=['GET'], csrf=False)
    def api_app_shop(self, token=None, partner_id=False, shop_type_id=False, **kw):
        """
            This method returns all shops and my shops list
            from the customer profile
            @param - token (Auth Token) Type(Char)
            @param - partner_id(Session Partner_id) Type(int)
            @kw - Type (dict)
        """
        ensure_db()        
        try:
            res = {}
            env = api.Environment(request.cr, odoo.SUPERUSER_ID, {})
            partner = False
            page_no = kw.get('page_no')
            shops = env['res.partner'].search([('parent_id','=', False),('supplier','=',True)])

            if shop_type_id:
                shop_type = env['merchant.shop.type'].browse(int(shop_type_id))
                shops = env['res.partner'].search([('id','in',shops.ids), ('shop_type_id','=',shop_type.id)])

            if kw.get('list_type') == 'my':
                check_params({'partner_id':partner_id})
                check_token()
                partner = env['res.partner'].browse(int(partner_id))
                shop_ids = [x.merchant_id.id for x in partner.points_line]
                            
                if partner.registering_merchant_id:
                    shop_ids.append(partner.registering_merchant_id.id)

                merchant_shop_ids = list(set(shops.ids).intersection(shop_ids))
                shops = env['res.partner'].search([('id','in',merchant_shop_ids)])

            paginated = paginate(page_no=page_no, records=shops)
            res['last'] = paginated['last']
            res['shops'] = []

            for shop in paginated['records']:
                shop_data = {}
                shop_data['id'] = shop.id
                shop_data['image_url'] = '/api/image/partner/%s' % (shop.id)
                shop_data['name'] = shop.name or shop.request_id.shopname or ''
                shop_data['shop_images'] = []
                
                for imgLine in shop.request_id.images_line:
                    if imgLine.image_url:
                        shop_data['shop_images'].append('/api/image/shop/%s' % (imgLine.id))
                
                res['shops'].append(shop_data)

            return Response(json.dumps(res,
                sort_keys=True, indent=4, cls=ObjectEncoder),
                content_type='application/json;charset=utf-8', status=200)

        except:
            return Response(json.dumps({'error': 'API not working'},
                    sort_keys=True, indent=4, cls=ObjectEncoder),
                    content_type='application/json;charset=utf-8', status=500)


    @http.route('/api/loyalty/review/<review_type>', auth="none", type='http', methods=['POST'], csrf=False)
    def api_loyalty_reviews(self, token=None, partner_id=False, deal_id=False, merchant_id=False, **kw):
        """
        This method favorites/unfavorite the merchants/deals
        from the customer profile
        @param - token (Auth Token) Type(Char)
        @param - partner_id(Session Partner_id) Type(int)
        @param - deal_id Type(int)
        @param - merchant_id Type(int)
        @kw - Type (dict)
        """
        ensure_db()
        check_token()
        check_params({'review_type':kw.get('review_type'), 'review':kw.get('review'), 'rating':kw.get('rating')})
        try:
            env = api.Environment(request.cr, odoo.SUPERUSER_ID, {})

            if kw.get('review_type') == 'deal':
                check_params({
                    'partner_id':partner_id,
                    'deal_id':deal_id,
                })
                deal_id = int(deal_id)
                partner_id = int(partner_id)

                rating_exist = env['loyalty.deal.rating.line'].search([('deal_id','=',deal_id), ('customer_id','=', partner_id)], limit=1)
                
                if not rating_exist:
                    vals = {
                        'customer_id':partner_id,
                        'review':kw.get('review'),
                        'rating':float(kw.get('rating')),
                        'deal_id':deal_id,
                    }
                    env['loyalty.deal.rating.line'].create(vals)
                    
                else:        
                    rating_exist.write({'review':kw.get('review'),'rating':float(kw.get('rating')),})

                return Response(json.dumps({'msg':'Review Successfull'},
                        sort_keys=True, indent=4, cls=ObjectEncoder),
                        content_type='application/json;charset=utf-8', status=200)

            elif kw.get('review_type') == 'merchant':

                check_params({
                    'partner_id':partner_id,
                    'merchant_id':merchant_id
                })

                rating_exist = env['res.partner.rating.line'].search([('customer_id','=',partner_id), ('partner_id','=', merchant_id)], limit=1)
                
                if not rating_exist:
                    vals = {
                        'customer_id':partner_id,
                        'review':kw.get('review'),
                        'rating':float(kw.get('rating')),
                        'partner_id':merchant_id,
                    }
                    env['res.partner.rating.line'].create(vals)
                else:       
                    rating_exist.write({
                            'review':kw.get('review'),
                            'rating':float(kw.get('rating')),
                        })
                    
                return Response(json.dumps({'msg':'Review Successfull'},
                    sort_keys=True, indent=4, cls=ObjectEncoder),
                    content_type='application/json;charset=utf-8', status=200)
            
            else:
                return Response(json.dumps({'error': 'Invalid Request'},
                    sort_keys=True, indent=4, cls=ObjectEncoder),
                    content_type='application/json;charset=utf-8', status=500)

        except:
            return Response(json.dumps({'error': 'API not working'},
                sort_keys=True, indent=4, cls=ObjectEncoder),
                content_type='application/json;charset=utf-8', status=500)


    @http.route('/api/loyalty/search/<search_type>', auth="none", type='http', methods=['GET'], csrf=False)
    def api_loyalty_search(self, token=None, partner_id=False, category_id=False , query='', **kw):
        """
        This method searches the merchants/deals
        from the customer profile.
        @param - search_type Type(option-merchant/deal)
        @query - Type (dict)
        """
        ensure_db()
        check_token()
        check_params({'partner_id': partner_id, 'search_type':kw.get('search_type'), 'query':query, 'category_id':category_id})

        try:
            env = api.Environment(request.cr, odoo.SUPERUSER_ID, {})
            res = []
            partner = env['res.partner'].browse(int(partner_id))

            if kw.get('search_type') == 'merchant':
                merchants = env['res.partner'].search([('supplier','=',True), ('parent_id','=',False), ('display_name', '=ilike', '%'+query+'%')])

                for merchant in merchants:
                    if merchant.request_id.shop_type_id.id == int(category_id):                            
                        merchant_data = {}
                        merchant_data['id'] = merchant.id
                        merchant_data['image_url'] = '/api/image/partner/%s' % (merchant.id)
                        merchant_data['name'] = merchant.name or merchant.request_id.shopname or ''
                        res.append(merchant_data)

            elif kw.get('search_type') == 'deal':
                deals = env['loyalty.deal'].search([('state','=','publish'),'|',('title','=ilike', '%'+query+'%'), ('description','=ilike', '%'+query+'%')])

                for deal in deals:
                    if deal.category_id.id == int(category_id):                            
                        deal_data = {}
                        deal_data['title'] = deal.title
                        deal_data['deal_id'] = deal.id
                        deal_data['image_url'] = deal.image_url_public
                        deal_data['rating_avg'] = deal.rating
                        deal_data['own_rating'] = 0
                        deal_data['is_favorite'] = False

                        for rating in deal.rating_line:
                            if rating.customer_id.id == partner.id:
                                deal_data['own_rating'] = rating.rating or 0

                        if deal.id in partner.favourite_deal_ids.ids:
                            deal_data['is_favorite'] = True

                        if deal.expiration_date:
                            today =  datetime.datetime.today().date()
                            deal_data['expire_in'] = '%s days left' % (deal.expiration_date - today).days
                        
                        res.append(deal_data)

            else:
                return Response(json.dumps({'error': 'Invalid Search Type'},
                    sort_keys=True, indent=4, cls=ObjectEncoder),
                    content_type='application/json;charset=utf-8', status=500)
            
            return Response(json.dumps(res,
                sort_keys=True, indent=4, cls=ObjectEncoder),
                content_type='application/json;charset=utf-8', status=200)

        except:
            return Response(json.dumps({'error': 'API not working'},
                sort_keys=True, indent=4, cls=ObjectEncoder),
                content_type='application/json;charset=utf-8', status=500)


    @http.route('/api/loyalty/notification', auth="none", type='http', methods=['GET'], csrf=False)
    def api_loyalty_notification(self, token=None, partner_id=False, **kw):
        """
        This method returns the notification list
        from the customer profile.
        """
        ensure_db()
        check_token()
        check_params({'partner_id': partner_id})

        page_no = kw.get('page_no')

        try:
            res = {}
            env = api.Environment(request.cr, odoo.SUPERUSER_ID, {})
            partner = env['res.partner'].browse(int(partner_id))
            
            paginated = paginate(page_no=page_no, records=partner.notification_line)
            res['last'] = paginated['last']
            res['notifications'] = []

            for notification in paginated['records']:
                notification_data = {}
                notification_data['id'] = notification.id
                notification_data['message'] = notification.message
                notification_data['is_read'] = notification.is_read
                res['notifications'].append(notification_data)

            return Response(json.dumps(res,
                sort_keys=True, indent=4, cls=ObjectEncoder),
                content_type='application/json;charset=utf-8', status=200)

        except:
            return Response(json.dumps({'error': 'API not working'},
                sort_keys=True, indent=4, cls=ObjectEncoder),
                content_type='application/json;charset=utf-8', status=500)


    @http.route('/api/loyalty/notification/update/<update_type>', auth="none", type='http', methods=['POST'], csrf=False)
    def api_loyalty_notification_update(self, token=None, partner_id=False, notification_id=False, **kw):
        """
        This method updates the notification list
        from the customer profile.
        """
        ensure_db()
        # check_token()
        check_params({'partner_id': partner_id, 'update_type':kw.get('update_type')})

        env = api.Environment(request.cr, odoo.SUPERUSER_ID, {})

        try:

            if kw.get('update_type') in ['read','unread']:
                check_params({'notification_id': notification_id})

                # Using Search instead of browse due to security purpose
                notifications = env['res.partner.notification'].search([('id','=',int(notification_id)), ('receipient_id','=', int(partner_id))])

            elif kw.get('update_type') in ['read_all', 'unread_all']:

                # Search all Notification
                notifications = env['res.partner.notification'].search([('receipient_id','=', int(partner_id))])

            if kw.get('update_type') in ['read','read_all']:
                notifications.read_notification()

            elif kw.get('update_type') in ['unread','unread_all']:
                notifications.unread_notification()

            return Response(json.dumps({'msg':'Updated Successfully'},
                sort_keys=True, indent=4, cls=ObjectEncoder),
                content_type='application/json;charset=utf-8', status=200)

        except:
            return Response(json.dumps({'error': 'API not working'},
                sort_keys=True, indent=4, cls=ObjectEncoder),
                content_type='application/json;charset=utf-8', status=500)


    @http.route('/api/loyalty/coupon', auth="none", type='http', methods=['GET'], csrf=False)
    def api_loyalty_coupon(self, token=None, partner_id=False, **kw):
        """
        This method updates the notification list
        from the customer profile.
        """
        ensure_db()
        check_token()       
        check_params({'partner_id': partner_id})

        try:
            res = {}
            env = api.Environment(request.cr, odoo.SUPERUSER_ID, {})
            partner = env['res.partner'].browse(int(partner_id))
            res['coupons'] = []
            page_no = kw.get('page_no')

            paginated = paginate(page_no=page_no, records=partner.coupon_ids)
            res['last'] = paginated['last']
            
            for coupon in paginated['records']:
                coupon_data = {}
                coupon_data['name'] = coupon.coupon_rule_id.name
                coupon_data['merchant_id'] = coupon.merchant_id.name
                coupon_data['code'] = coupon.code
                coupon_data['status'] = coupon.state
                coupon_data['expiration_date'] = coupon.expiration_date.strftime("%Y-%m-%d_%H-%M-%S")
                res['coupons'].append(coupon_data)

            return Response(json.dumps(res,
                sort_keys=True, indent=4, cls=ObjectEncoder),
                content_type='application/json;charset=utf-8', status=200)

        except:
            return Response(json.dumps({'error': 'API not working'},
                sort_keys=True, indent=4, cls=ObjectEncoder),
                content_type='application/json;charset=utf-8', status=500)


    @http.route('/api/loyalty/preferences/<pref_type>/<switch>', auth="none", type='http', methods=['POST'], csrf=False)
    def api_loyalty_preferences(self, token=None, uid=False, **kw):
        """
        This method updates the user preferences
        """
        ensure_db()
        check_token()       
        check_params({'uid': uid,'pref_type':kw.get('pref_type'), 'switch':kw.get('switch')})

        try:
            res = {}
            env = api.Environment(request.cr, odoo.SUPERUSER_ID, {})  
            user = env['res.users'].browse(int(uid))
            
            if kw.get('pref_type') == 'email' and kw.get('switch') == 'on':
                user.write({'notify_email':True})

            elif kw.get('pref_type') == 'email' and kw.get('switch') == 'off':
                user.write({'notify_email':False})

            elif kw.get('pref_type') == 'sms' and kw.get('switch') == 'on':
                user.write({'notify_sms':True})
            
            elif kw.get('pref_type') == 'sms' and kw.get('switch') == 'off':
                user.write({'notify_sms':False})

            elif kw.get('pref_type') == 'push' and kw.get('switch') == 'on':
                user.write({'notify_push':True})
            
            elif kw.get('pref_type') == 'push' and kw.get('switch') == 'off':
                user.write({'notify_push':False})

            else:
                return Response(json.dumps({'error': 'Bad Request'},
                    sort_keys=True, indent=4, cls=ObjectEncoder),
                    content_type='application/json;charset=utf-8', status=400)

            return Response(json.dumps({'msg':'Updated Successfully'},
                sort_keys=True, indent=4, cls=ObjectEncoder),
                content_type='application/json;charset=utf-8', status=200)

        except:
            return Response(json.dumps({'error': 'API not working'},
                sort_keys=True, indent=4, cls=ObjectEncoder),
                content_type='application/json;charset=utf-8', status=500)


    @http.route('/api/loyalty/deal-filter', auth="none", type='http', methods=['GET'], csrf=False)
    def api_deal_filter(self, lat=0, lng=0, radius=1, **kw):
        """
        Deal Filter
        """ 
        ensure_db()
        check_params({'lat': lat,'lng':lng, 'radius':radius})

        try:
            env = api.Environment(request.cr, odoo.SUPERUSER_ID, {})  
            res = []    
            lat, lng, radius = float(lat), float(lng), float(radius)

            for deal in env['loyalty.deal'].search([('state','=','publish')]):
                
                if deal.merchant_id.request_id:                
                    merchant_shop_lat = deal.merchant_id.request_id.location_lat
                    merchant_shop_lng = deal.merchant_id.request_id.location_lng                
                    distance_from_shop = getCordinates(lat, lng, float(merchant_shop_lat), float(merchant_shop_lng))                
                    if distance_from_shop <= radius:
                        deal_data = {}                
                        deal_data['title'] = deal.title
                        deal_data['deal_id'] = deal.id
                        deal_data['merchant_id'] = deal.merchant_id.id
                        deal_data['merchant'] = deal.merchant_id.name
                        deal_data['merchant_location_lat'] = deal.merchant_id.request_id.location_lat
                        deal_data['merchant_location_lng'] = deal.merchant_id.request_id.location_lng
                        deal_data['distance'] = round(distance_from_shop, 2)
                        res.append(deal_data)

            return Response(json.dumps(res,
                sort_keys=True, indent=4, cls=ObjectEncoder),
                content_type='application/json;charset=utf-8', status=200)

        except:
            return Response(json.dumps({'error': 'API not working'},
                sort_keys=True, indent=4, cls=ObjectEncoder),
                content_type='application/json;charset=utf-8', status=500)

    @http.route('/api/loyalty/update-password-otp/<update_type>', auth="none", type='http', methods=['GET'], csrf=False)
    def api_change_password_send_otp(self, partner_id=False, mobile=False,**kw):
        ensure_db()
        try:
            env = api.Environment(request.cr, odoo.SUPERUSER_ID, {})
            
            if kw.get('update_type') == 'change':
                check_params({'partner_id': partner_id})
                partner = env['res.partner'].browse(int(partner_id))

                if not partner.mobile:
                    return Response(json.dumps({'error': 'Mobile No. not provided.'},
                        sort_keys=True, indent=4, cls=ObjectEncoder),
                        content_type='application/json;charset=utf-8', status=500)

                mobile = partner.mobile.strip()

            elif kw.get('update_type') == 'reset':
                check_params({'mobile': mobile})
                mobile = '+'+mobile.strip()

            else:
                return Response(json.dumps({'error': 'Invalid Request'},
                    sort_keys=True, indent=4, cls=ObjectEncoder),
                    content_type='application/json;charset=utf-8', status=400)
            
            sms_sent = env['res.partner'].send_register_verification_otp(mobile=mobile)

            if sms_sent:
                return Response(json.dumps({'msg': 'OTP Sent Successfully.'},
                        sort_keys=True, indent=4),
                        content_type='application/json;charset=utf-8', status=200)
            else:
                return Response(json.dumps({'error': 'Error Sending OTP via SMS. Please check mobile number again.'},
                        sort_keys=True, indent=4),
                        content_type='application/json;charset=utf-8', status=500)

        except:
            return Response(json.dumps({'error': 'API not working'},
                sort_keys=True, indent=4, cls=ObjectEncoder),
                content_type='application/json;charset=utf-8', status=500) 


    @http.route('/api/loyalty/update-password/<update_type>', auth="none", type='http', methods=['POST'], csrf=False)
    def api_reset_password(self, token=False, uid=False, partner_id=False, mobile=False, otp=False, new_password=False, **kw):
        
        ensure_db()

        try:
            env = api.Environment(request.cr, odoo.SUPERUSER_ID, {})

            if kw.get('update_type') == 'change':
                check_token()
                check_params({'uid': uid, 'otp':otp, 'new_password':new_password, 'partner_id':partner_id})
                partner = env['res.partner'].browse(int(partner_id))
                registered_otp = env['loyalty.mobile.otp.register'].search([('mobile','=', partner.mobile)], limit=1)

            elif kw.get('update_type') == 'reset':
                check_params({'otp':otp, 'new_password':new_password, 'mobile': mobile})
                mobile = '+'+mobile.strip()
                partner = env['res.partner'].search([('mobile','=',mobile)], limit=1)
                uid = partner.user_ids.ids[0]
                registered_otp = env['loyalty.mobile.otp.register'].search([('mobile','=', mobile)], limit=1)
                
            else:
                return Response(json.dumps({'error': 'Invalid Request'},
                    sort_keys=True, indent=4, cls=ObjectEncoder),
                    content_type='application/json;charset=utf-8', status=400)
                        
            # Verify OTP
            if otp == registered_otp.otp:
                env['res.users'].browse(int(uid)).write({'password': new_password})
                return Response(json.dumps({'msg':'Password Changed Successfully'},
                    sort_keys=True, indent=4, cls=ObjectEncoder),
                    content_type='application/json;charset=utf-8', status=200)
            else:
                return Response(json.dumps({'error': 'Invalid OTP'},
                    sort_keys=True, indent=4, cls=ObjectEncoder),
                    content_type='application/json;charset=utf-8', status=500)
        except:
            return Response(json.dumps({'error': 'API not working'},
                sort_keys=True, indent=4, cls=ObjectEncoder),
                content_type='application/json;charset=utf-8', status=500) 

    @http.route('/api/loyalty/set-lang', auth="none", type='http', methods=['POST'], csrf=False)
    def api_set_language(self, token=False, uid=False, lang=False, **kw):
        ensure_db()
        check_token()
        check_params({'uid':uid, 'lang':lang})

        try:
            env = api.Environment(request.cr, odoo.SUPERUSER_ID, {})
            user = env['res.users'].browse(int(uid))
            user.write({'lang':lang})
            return Response(json.dumps({'msg':'Language Set Successfully'},
                    sort_keys=True, indent=4, cls=ObjectEncoder),
                    content_type='application/json;charset=utf-8', status=200)
        except:
            return Response(json.dumps({'error': 'API not working'},
                sort_keys=True, indent=4, cls=ObjectEncoder),
                content_type='application/json;charset=utf-8', status=500) 
        
    
    @http.route('/api/loyalty/card', auth="none", type='http', methods=['GET'], csrf=False)
    def api_my_card(self, token=False, partner_id=False, **kw):
        ensure_db()
        check_token()
        check_params({'partner_id':partner_id})
        try:
            res = {}
            env = api.Environment(request.cr, odoo.SUPERUSER_ID, {})
            partner = env['res.partner'].browse(int(partner_id))
            res['balance'] = partner.loyalty_points
            res['card_no'] = False
            if partner.card_no_id:
                res['card_no'] = partner.card_no_id.name
            return Response(json.dumps(res,
                sort_keys=True, indent=4, cls=ObjectEncoder),
                content_type='application/json;charset=utf-8', status=200)
        
        except:
            return Response(json.dumps({'error': 'API not working'},
                sort_keys=True, indent=4, cls=ObjectEncoder),
                content_type='application/json;charset=utf-8', status=500) 
        