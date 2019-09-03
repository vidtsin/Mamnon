# -*- coding: utf-8 -*-
""" init object update ir.qweb """

import logging

from odoo import api, models

LOGGER = logging.getLogger(__name__)

REMOTE_CONNECTION_TIMEOUT = 2.5
from odoo.addons.base.models.qweb import QWeb, Contextifier


# pylint: disable=no-member
class IrQWeb(models.AbstractModel, QWeb):
    """ init object update ir.qweb """
    _inherit = 'ir.qweb'

    @api.model
    def render(self, id_or_xml_id, values=None, **options):
        """override render."""
        values = values or {}
        context = dict(self.env.context, **options)
        if 'lang_direction' in values:
            return super(IrQWeb, self).render(id_or_xml_id, values=values,
                                              **options)
        language = self.env['res.lang']
        lang = context.get('lang', 'en_US')
        directions = language.get_languages_dir()
        direction = directions.get(lang, 'ltr')
        values['lang_direction'] = direction
        return super(IrQWeb, self).render(id_or_xml_id, values=values,
                                          **options)
