# -*- coding: utf-8 -*-
from odoo import api, models, fields
from odoo.addons.payment_paygate.controllers.main import payGateController

from collections import OrderedDict
from datetime import datetime
from hashlib import md5
import logging
from urllib.parse import unquote
from werkzeug import urls

import requests


_logger = logging.getLogger(__name__)

class payGate(models.Model):
    _inherit = 'payment.acquirer'

    provider = fields.Selection(selection_add=[('paygate', 'Paygate')])
    paygate_id = fields.Char('Paygate ID', help="Paygate id provided by payget provider")

    @api.model
    def _get_paygate_urls(self, environment):
        return {
            'paygate_form_url': 'https://secure.paygate.co.za/payweb3/process.trans'
            }

    @api.multi
    def paygate_get_form_action_url(self):
        return self._get_paygate_urls(self.environment)['paygate_form_url']

    @api.multi
    def paygate_form_generate_values(self, values):
        self.ensure_one()
        paygate_values = {}
        base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url')
        paygate_values['PAYGATE_ID'] = self.paygate_id or '10011072130'
        paygate_values['REFERENCE'] = values['reference']
        paygate_values['AMOUNT'] = int(values['amount'] * 100)
        paygate_values['CURRENCY'] = 'ZAR'
        paygate_values['RETURN_URL'] = urls.url_join(base_url, payGateController._return_url)
        paygate_values['TRANSACTION_DATE'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        paygate_values['LOCALE'] = 'en'
        paygate_values['COUNTRY'] = 'ZAF'
        paygate_values['EMAIL'] = values['partner_email']
        paygate_values['NOTIFY_URL'] = urls.url_join(base_url, payGateController._notify_url)
        paygate_values['CHECKSUM'] = self.calculate_md5(paygate_values)
        hash_valid, response_data = self.post_payment(paygate_values)
        # new checksum
        paygate_values['CHECKSUM'] = response_data['CHECKSUM']
        paygate_values['PAY_REQUEST_ID'] = response_data['PAY_REQUEST_ID']
        values.update(paygate_values)
        return values

    def post_payment(self, data):
        url = 'https://secure.paygate.co.za/payweb3/initiate.trans'
        response = requests.post(url, data=data)
        dict_ = OrderedDict()
        new = response.text.split('&')
        for item in new:
            list_ = item.split('=')
            key = list_[0]
            value = list_[1]
            dict_[key] = unquote(value)
        is_equal, dict_['CHECKSUM'] = self.validate_checksum(dict_)
        return is_equal, dict_

    @api.model
    def calculate_md5(self, data):
        checksum = ''
        key = 'secret'  # Make sure
        for k, v in data.items():
            checksum = '%s%s' % (checksum, v)
        checksum = '%s%s' % (checksum, key)  # add key to checksum value
        md5_hash = md5(checksum.encode('utf-8')).hexdigest()
        return md5_hash

    @api.model
    def validate_checksum(self, data):
        hash_ = data.pop('CHECKSUM')
        new_hash = self.calculate_md5(data)
        return hash_ == new_hash, new_hash
