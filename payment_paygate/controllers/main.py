from odoo import http
from odoo.http import request

import logging

_logger = logging.getLogger(__name__)


class payGateController(http.Controller):
    _notify_url = '/payment/paygate/notify'
    _return_url = '/payment/paygate/return_url'

    @http.route('/payment/paygate/notify', type='http', auth='none', methods=['POST'], csrf=False)
    def paygate_notify(self, *ars, **post):
        request.env['payment.transaction'].sudo().form_feedback(post, 'paygate')
        return response('OK')

    @http.route('/payment/paygate/return_url', type='http', auth="none", methods=['POST'], csrf=False)
    def paygate_return(self, **post):
        import pdb; pdb.set_trace()