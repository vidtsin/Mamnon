# -*- coding: utf-8 -*-
""" init object update res.lang """

import odoo
from odoo import api, models


class Language(models.Model):
    """ init object update res.lang """
    _inherit = 'res.lang'

    # pylint: disable=no-member
    @api.model
    @odoo.tools.ormcache(skiparg=1)
    def _get_languages_dir(self):
        """private get records lang active."""
        langs = self.search([('active', '=', True)])
        return dict([(lg.code, lg.direction) for lg in langs])

    @api.multi
    def get_languages_dir(self):
        """public get records lang active."""
        return self._get_languages_dir()

    @api.multi
    def write(self, vals):
        """override write."""
        self._get_languages_dir.clear_cache(self)
        return super(Language, self).write(vals)
