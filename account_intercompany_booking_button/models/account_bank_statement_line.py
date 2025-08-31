
from odoo import models, fields
import logging

_logger = logging.getLogger(__name__)

class AccountBankStatementLine(models.Model):
    _inherit = "account.bank.statement.line"

    def action_open_intercompany_booking_wizard(self):
        return {
            "type": "ir.actions.act_window",
            "res_model": "intercompany.booking.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {"default_statement_line_id": self.id},
        }
