# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import Warning
from twilio.rest import Client
from pyfcm import FCMNotification 


class Notification(models.Model):

    _name = 'res.partner.notification'

    receipient_id = fields.Many2one('res.partner', 'Receipient', required=True)
    message = fields.Char(string ='Notifications', required=True)
    is_read = fields.Boolean(string="Is Seen?", default=False)

    @api.multi
    def read_notification(self):
        for notification in self:
            notification.write({'is_read':True})

    @api.multi
    def unread_notification(self):
        for notification in self:
            notification.write({'is_read':False})


class UserNotification(models.Model):

    _inherit = 'res.partner'

    def send_email(self, notify_type, msg=False, data=False):
        """
        Method to send Email Notification to Customer
        """
        if notify_type == 'registration':
            email_template = self.env.ref('loyalty.notification_registration')

        if notify_type == 'redeem':
            email_template = self.env.ref('loyalty.notification_redeem')
            return email_template.sudo().with_context({'msg':msg,'points':data.get('points'),'discount':data.get('discount'),'currency':data.get('currency')}).send_mail(self.id, force_send=True, raise_exception=True)

        if notify_type == 'reward':
            email_template = self.env.ref('loyalty.notification_reward')
            return email_template.sudo().with_context({'msg':msg,'points':data.get('points'),'purchase_amount':data.get('purchase_amount'),'currency':data.get('currency'),'merchant_name':data.get('merchant_name')}).send_mail(self.id, force_send=True, raise_exception=True)

        if notify_type == 'register_by_merchant':
            email_template = self.env.ref('loyalty.notification_reg_by_merchant')
            return email_template.sudo().with_context({'password':data.get('password')}).send_mail(self.id, force_send=True, raise_exception=True)

        if notify_type == 'settlement':
            email_template = self.env.ref('loyalty.notification_merchant_settlement')
            return email_template.sudo().with_context(data).send_mail(self.id, force_send=True, raise_exception=True)
        
        return email_template.sudo().with_context({'msg':msg}).send_mail(self.id, force_send=True, raise_exception=True)

    def send_sms(self, msg, notify_type=False):
        """
        Method to send SMS Notification to Customer
        """
        account_sid = self.env['ir.config_parameter'].sudo().get_param('merchant.twilio_cid')
        auth_token = self.env['ir.config_parameter'].sudo().get_param('merchant.twilio_token')
        twilio_number = self.env['ir.config_parameter'].sudo().get_param('merchant.twilio_number')
        try:
            client = Client(account_sid, auth_token)
        except:
            raise Warning(_('Please Check Twilio Credentials.'))


        if not msg and notify_type in ['registration','register_by_merchant']:
            msg = _('Registration Successful - You have been successfully registered to MAMNON.')

        try:
            message = client.messages.create(
                    body=msg,
                    from_=twilio_number,
                    to=self.mobile
                )
            print ("SMS Notification sent successfully!!")

        except:
            print ("Error Sending SMS Notification")

        return

    def send_push(self, msg, notify_type=False, otp=False):
        """
        Method to send Push Notification to Customer
        """
        try:
            push_api_key = self.env['ir.config_parameter'].sudo().get_param('merchant.push_api_key')
            push_service = FCMNotification(api_key=push_api_key) 
            registration_id = self.user_ids[0].device_id
            data_message = {'type':notify_type}
            
            if notify_type == 'redeem_auth':
                message_title = "Points Redemption Authentication"
                data_message['otp'] = otp

            if notify_type == 'reward':
                message_title = _("Points Rewarded")

            if notify_type == 'redeem':
                message_title = _("Points Redeemed")

            if notify_type == 'coupon_publish':
                message_title = _('Coupons Published')

            result = push_service.notify_single_device(registration_id=registration_id, click_action='FCM_PLUGIN_ACTIVITY', sound='default', message_title=message_title, message_body=msg, data_message=data_message, timeout=10)             
            print ("Push Notification sent successfully!!")

        except:
            print ("Error Sending Push Notification")


    def notify(self, notify_type, msg=False, sms=False, push=False, email=False, data=False):
        if sms:
            try:
                self.send_sms(notify_type=notify_type, msg=msg)
            except:
                pass
        if push:
            try:
                self.send_push(notify_type=notify_type, msg=msg)
            except:
                pass
        if email:
            try:
                self.send_email(notify_type=notify_type, msg=msg, data=data)
            except:
                pass
        return
