# -*- coding: utf-8 -*-
""" init main controllers"""
from odoo.addons.web.controllers.main import WebClient

from odoo import http


class UpdateWebClient(WebClient):
    """update object WebClient"""

    @http.route('/web/webclient/locale/<string:lang>', type='http', auth="none")
    def load_locale(self, lang):
        """override load_locale"""
        if lang.startswith('ar_'):
            lang = 'ar_SA'
        return super(UpdateWebClient, self).load_locale(lang)
