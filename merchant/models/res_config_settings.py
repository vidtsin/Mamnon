
from odoo import api, fields, models

class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    image_count = fields.Char(string='Image Count')
    max_img_size = fields.Char('Maximum Image Upload Size (In KB)', default=5)
    twilio_cid = fields.Char(string='Twilio CID')
    twilio_token = fields.Char(string='Twilio Auth Token')
    twilio_number = fields.Char(string='Twilio Number')
    ce_msg = fields.Text(string='Message')
    ce_subject = fields.Char(string='Subject')
    ce_to = fields.Char(string='To')
    ce_cc = fields.Char(string='CC')
    ce_bcc = fields.Char(string='BCC')
    ce_file = fields.Char(string='File')
    social_msg = fields.Char(string='Message')
    social_subject = fields.Char(string='Subject')
    social_file = fields.Char(string='Social File')
    social_url = fields.Char(string='Playstore Link')
    fb_link = fields.Char(string='Facebook Link')
    insta_link = fields.Char(string='Instagram Link')
    gplus_link = fields.Char(string='Google+ Link')
    push_api_key = fields.Char(string='Push API Key')

    #Group 
    merchant_group_age = fields.Char('Merchant Group Age (In Days)', default=5)
    
    #Coupon Rule 
    max_coupon_type_generate = fields.Char('Maximum  Merchant Coupon Genertion Types', default=3)

    def get_values(self):
        res = super(ResConfigSettings, self).get_values()
        res.update(
            image_count=self.env['ir.config_parameter'].sudo().get_param('merchant.image_count'),
            twilio_cid = self.env['ir.config_parameter'].sudo().get_param('merchant.twilio_cid'),
            twilio_token = self.env['ir.config_parameter'].sudo().get_param('merchant.twilio_token'),
            twilio_number = self.env['ir.config_parameter'].sudo().get_param('merchant.twilio_number'),
            ce_msg = self.env['ir.config_parameter'].sudo().get_param('merchant.ce_msg'),
            ce_subject = self.env['ir.config_parameter'].sudo().get_param('merchant.ce_subject'),
            ce_to = self.env['ir.config_parameter'].sudo().get_param('merchant.ce_to'),
            ce_cc = self.env['ir.config_parameter'].sudo().get_param('merchant.ce_cc'),
            ce_bcc = self.env['ir.config_parameter'].sudo().get_param('merchant.ce_bcc'),
            ce_file = self.env['ir.config_parameter'].sudo().get_param('merchant.ce_file'),
            social_msg = self.env['ir.config_parameter'].sudo().get_param('merchant.social_msg'),
            social_subject = self.env['ir.config_parameter'].sudo().get_param('merchant.social_subject'),
            social_file = self.env['ir.config_parameter'].sudo().get_param('merchant.social_file'),
            social_url = self.env['ir.config_parameter'].sudo().get_param('merchant.social_url'),
            fb_link = self.env['ir.config_parameter'].sudo().get_param('merchant.fb_link'),
            insta_link = self.env['ir.config_parameter'].sudo().get_param('merchant.insta_link'),
            gplus_link = self.env['ir.config_parameter'].sudo().get_param('merchant.gplus_link'),
            push_api_key = self.env['ir.config_parameter'].sudo().get_param('merchant.push_api_key'),
            max_img_size = self.env['ir.config_parameter'].sudo().get_param('merchant.max_img_size'),
            merchant_group_age = self.env['ir.config_parameter'].sudo().get_param('merchant.merchant_group_age'),
            max_coupon_type_generate = self.env['ir.config_parameter'].sudo().get_param('merchant.max_coupon_type_generate'),
            )
        return res

    def set_values(self):
        super(ResConfigSettings, self).set_values()
        self.env['ir.config_parameter'].sudo().set_param('merchant.image_count', self.image_count)
        self.env['ir.config_parameter'].sudo().set_param('merchant.twilio_cid', self.twilio_cid)
        self.env['ir.config_parameter'].sudo().set_param('merchant.twilio_token', self.twilio_token)
        self.env['ir.config_parameter'].sudo().set_param('merchant.twilio_number', self.twilio_number)
        self.env['ir.config_parameter'].sudo().set_param('merchant.ce_msg', self.ce_msg)
        self.env['ir.config_parameter'].sudo().set_param('merchant.ce_subject', self.ce_subject)
        self.env['ir.config_parameter'].sudo().set_param('merchant.ce_to', self.ce_to)
        self.env['ir.config_parameter'].sudo().set_param('merchant.ce_cc', self.ce_cc)
        self.env['ir.config_parameter'].sudo().set_param('merchant.ce_bcc', self.ce_bcc)
        self.env['ir.config_parameter'].sudo().set_param('merchant.ce_file', self.ce_file)
        self.env['ir.config_parameter'].sudo().set_param('merchant.social_msg', self.social_msg)
        self.env['ir.config_parameter'].sudo().set_param('merchant.social_subject', self.social_subject)
        self.env['ir.config_parameter'].sudo().set_param('merchant.social_file', self.social_file)
        self.env['ir.config_parameter'].sudo().set_param('merchant.social_url', self.social_url)
        self.env['ir.config_parameter'].sudo().set_param('merchant.fb_link', self.fb_link)
        self.env['ir.config_parameter'].sudo().set_param('merchant.insta_link', self.insta_link)
        self.env['ir.config_parameter'].sudo().set_param('merchant.gplus_link', self.gplus_link)
        self.env['ir.config_parameter'].sudo().set_param('merchant.push_api_key', self.push_api_key)
        self.env['ir.config_parameter'].sudo().set_param('merchant.max_img_size', self.max_img_size)
        self.env['ir.config_parameter'].sudo().set_param('merchant.merchant_group_age', self.merchant_group_age)
        self.env['ir.config_parameter'].sudo().set_param('merchant.max_coupon_type_generate', self.max_coupon_type_generate)