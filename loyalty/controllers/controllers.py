# -*- coding: utf-8 -*-
import odoo
import json
import werkzeug
import datetime
from odoo import http, _
from odoo.exceptions import UserError
from odoo.http import request
from odoo.addons.auth_signup.controllers.main import AuthSignupHome
from odoo.addons.auth_signup.models.res_users import SignupError
from odoo.addons.web.controllers.main import ensure_db,Session


class Session(Session):

    @http.route('/web/session/logout', type='http', auth="user")
    def logout(self, redirect='/web'):
        try:
            user = request.env.user.sudo().write({'notified':False})
        except:
            pass
        request.session.logout(keep_db=True)
        return werkzeug.utils.redirect(redirect, 303)


class CustomController(odoo.http.Controller):
        
    @http.route('/loyalty/check_merchant_txns', type="http", auth="public", website=True, csrf=False)
    def check_merchant_txns(self , **kw):

        show_tx_notification_popup = False
        notify_msg = '<h4>You have some notifications!!</h4><ul style="margin-top:10px;text-align:left">'
        res_user = request.env.user
        notified = res_user.sudo().notified

        # TX Notification
        if not notified and (res_user.has_group('loyalty.group_merchant_admin') or res_user.has_group('loyalty.group_merchant_user')) and res_user.partner_id.request_id.remaining_monthly_txns == 0:
            show_tx_notification_popup = True
            notify_msg += '<li>Your transaction limit for the month is exceeded. Please contact MAMNON Operation Team for extra services.</li>'

        # Pre_Expire Notification
        if not notified and (res_user.has_group('loyalty.group_merchant_admin') or res_user.has_group('loyalty.group_merchant_user')):
            delta = res_user.partner_id.request_id.expire_date - datetime.date.today()
            if delta.days in [1,2,3]:
                show_tx_notification_popup = True
                notify_msg += '<li>Your subscription is expiring in %s days! Please renew your service before expiration.</li>' % (delta.days)
            
            elif delta.days <= 0:
                show_tx_notification_popup = True
                notify_msg += '<li>Your subscription is over. Please renew your services.</li>'

            if res_user.partner_id.request_id.state == 'expire' or res_user.partner_id.parent_id.request_id.state == 'expire':
                show_tx_notification_popup = True
                notify_msg += '<li>Your subscription is expired.</li>'                

            if res_user.partner_id.request_id.state == 'suspend' or res_user.partner_id.parent_id.request_id.state == 'suspend':
                show_tx_notification_popup = True
                notify_msg += '<li>Your subscription is Suspended.</li>'                
        
        notify_msg += '</ul>'

        res_user.write({'notified': True})

        return json.dumps({'show_tx_notification_popup':show_tx_notification_popup, 'notify_msg':notify_msg})