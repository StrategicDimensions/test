# -*- coding: utf-8 -*-
from odoo import api, models, fields, _
from odoo.addons.payment_paygate.controllers.main import payGateController
from odoo.addons.payment.models.payment_acquirer import ValidationError
from odoo.tools.float_utils import float_compare

from collections import OrderedDict
from datetime import datetime
from hashlib import md5
import logging
from urllib.parse import unquote
from werkzeug import urls
import requests

_logger = logging.getLogger(__name__)


def calculate_md5(data):
    checksum = ''
    key = 'secret'  # Make sure
    for k, v in data.items():
        checksum = '%s%s' % (checksum, v)
    checksum = '%s%s' % (checksum, key)  # add key to checksum value
    md5_hash = md5(checksum.encode('utf-8')).hexdigest()
    return md5_hash

def validate_checksum(data):
    hash_ = data.pop('CHECKSUM')
    new_hash = calculate_md5(data)
    return hash_ == new_hash, new_hash

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
        paygate_values['CURRENCY'] = self.env.user.company_id.currency_id.name
        paygate_values['RETURN_URL'] = urls.url_join(base_url, payGateController._return_url)
        paygate_values['TRANSACTION_DATE'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        paygate_values['LOCALE'] = 'en'
        paygate_values['COUNTRY'] = 'ZAF'
        paygate_values['EMAIL'] = values['partner_email']
        paygate_values['NOTIFY_URL'] = urls.url_join(base_url, payGateController._notify_url)
        paygate_values['CHECKSUM'] = calculate_md5(paygate_values)
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
        is_equal, dict_['CHECKSUM'] = validate_checksum(dict_)
        return is_equal, dict_



class PaymentTransactionPaygate(models.Model):
    _inherit = 'payment.transaction'
    
    # {'PAYGATE_ID': '10011072130', 
    # 'PAY_REQUEST_ID': 'D914A230-FE17-389A-38A8-76BA60D20BCD',
    #  'REFERENCE': 'SO034',
    #   'TRANSACTION_STATUS': '1', 
    #   'RESULT_CODE': '990017',
    #    'AUTH_CODE': '101Q07',
    #     'CURRENCY': 'ZAR',
    #      'AMOUNT': '3300', 
    #      'RESULT_DESC': 'Auth Done', 
    #      'TRANSACTION_ID': '86840779', 
    #      'RISK_INDICATOR': 'AX',
    #       'PAY_METHOD': 'CC', 
    #       'PAY_METHOD_DETAIL': 'Visa', 
    #       'CHECKSUM': '50c994315149311edd6c0babb9da3df1'}
    @api.model
    def _paygate_form_get_tx_from_data(self, data):
        ref = data.get('REFERENCE')
        tx = self.search([('reference', '=', ref)])

        if not tx or len(tx) > 1:
            error_msg = _('received data for reference %s') % (ref)
            if not tx:
                error_msg += _('; no order found')
            else:
                error_msg += _('; multiple order found')
            _logger.info(error_msg)
            raise ValidationError(error_msg)
        print('dddd', data, tx)
        is_valid, _ = validate_checksum(data)
        print('si vali', is_valid)
        if not is_valid:
            error_msg = _('Transaction has been tempered. wrong checksum')
            raise ValidationError(error_msg)
        return tx
    
    def _paygate_form_get_invalid_parameters(self, data):
        invalid_parameters = []
        print('sss', self.amount, self.env.user.company_id.currency_id.name)
        if data.get('AMOUNT') == self.amount * 100:
            invalid_parameters.append(('amount', data.get('AMOUNT'), '%.2f' % self.amount))
        if data.get('CURRENCY') != self.env.user.company_id.currency_id.name:
            invalid_parameters.append(('currency', data.get('CURRENCY'), self.currency_id.name))

        return invalid_parameters
    
    def _paygate_form_validate(self, data):
        status_code = data.get('TRANSACTION_STATUS')
        ref = data.get('TRANSACTION_ID')
        print('code and ref', type(status_code), ref)
        if status_code == '1':
            self.write({
                'state': 'done',
                'acquirer_reference': ref,
            })
            return True
        elif status_code == '0':
            self.write({
                'state': 'pending',
                'acquirer_reference': ref,
            })
            return True
        elif status_code in ['2', '3', '4']:
            self.write({
                'state': 'cancel',
                'acquirer_reference': ref,
            })
            return True
        else:
            error = 'Payget: feedback error'
            _logger.info(error)
            self.write({
                'state': 'error',
                'state_message': error,
                'acquirer_reference': ref,
            })
            return False
