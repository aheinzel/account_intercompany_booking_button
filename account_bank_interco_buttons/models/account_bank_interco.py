from odoo import api, fields, models, _
from odoo.exceptions import UserError

class AccountBankStatementLine(models.Model):
    _inherit = "account.bank.statement.line"

    interco_move_ids = fields.Many2many(
        comodel_name="account.move",
        relation="bank_stmt_line_interco_move_rel",
        column1="statement_line_id",
        column2="move_id",
        string="Intercompany Moves",
        help="Moves that were generated via the Inter-co Allocate action.",
        copy=False,
    )

    def action_open_interco_allocate_wizard(self):
        self.ensure_one()
        if self.state == 'reconciled':
            raise UserError(_("This statement line is already reconciled."))
        return {
            'name': _('Inter-co allocate'),
            'type': 'ir.actions.act_window',
            'res_model': 'interco.allocate.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_statement_line_id': self.id,
                'default_amount': abs(getattr(self, 'amount', 0.0) or getattr(self, 'balance', 0.0)),
                'default_currency_id': self.currency_id.id or self.journal_id.currency_id.id or self.company_id.currency_id.id,
            },
        }