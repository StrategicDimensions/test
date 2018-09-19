from odoo import http
from odoo.http import request
import werkzeug


import logging

_logger = logging.getLogger(__name__)


class payGateController(http.Controller):
    _notify_url = '/payment/paygate/notify'
    _return_url = '/payment/paygate/return_url'

    @http.route('/payment/paygate/notify', type='http', auth='none', methods=['POST'], csrf=False)
    def paygate_notify(self, *ars, **post):
        status = request.env['payment.transaction'].sudo().form_feedback(post, 'paygate')
        print('controler status', status)
        if status:
            return werkzeug.wrappers.Response('OK')

    @http.route('/payment/paygate/return_url', type='http', auth="none", methods=['POST'], csrf=False)
    def paygate_return(self, **post):
        return werkzeug.wrappers.Response('OK')