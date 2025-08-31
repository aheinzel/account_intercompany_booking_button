import logging
from odoo import models, fields, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

class IntercompanyBookingWizard(models.TransientModel):
    _name = "intercompany.booking.wizard"

    statement_line_id = fields.Many2one(
        'account.bank.statement.line',
        string="Bank Statement Line",
        ondelete='set null',
        required=False,
    )

    reference = fields.Char(string="Reference", required=True)


    def _build_two_line_move(self, company, journal, date, label, debit_account, credit_account, amount, clean_context = False):
        context = self.env.context
        if clean_context:
            context = dict(self.env.context)
            for k in list(context.keys()):
                 if k.startswith('default_') or k in ('active_id', 'active_ids', 'active_model'):
                     context.pop(k)

        move = self.env['account.move'].with_context(context).with_company(company).create({
            'journal_id': journal.id,
            'date': date,
            'ref': label,
            'line_ids': [
                (0, 0, {'name': label, 'account_id': debit_account.id,  'debit': amount, 'credit': 0.0}),
                (0, 0, {'name': label, 'account_id': credit_account.id, 'debit': 0.0,   'credit': amount}),
            ],
        })

        return move



    def action_confirm(self):
        _logger.info("Intercompany booking: confirm")
        self.ensure_one()
        line = self.statement_line_id

        scenarios = self.env["intercompany.scenario"].search([("active", "=", True)])
        if not scenarios:
            raise UserError(_("No active Intercompany Scenario configured. Please create one."))
        if len(scenarios) > 1:
            raise UserError(_("Multiple active Intercompany Scenarios detected. Please keep exactly one active scenario."))
        scenario = scenarios[0]

        signed_amt = line.amount or 0.0
        if signed_amt == 0.0:
            raise UserError(_("Zero-amount statement line cannot be posted."))

        amt = abs(signed_amt)
        date = line.date or fields.Date.context_today(self)
        label = self.reference

        # Create posted moves from scenario
        source_company_move = self._build_two_line_move(
            scenario.source_company_id,
            scenario.source_journal_id,
            date,
            label,
            scenario.source_debit_account_id,
            scenario.source_credit_account_id,
            amt,
            True,
        )

        destination_company_move = self._build_two_line_move(
            scenario.dest_company_id,
            scenario.dest_journal_id,
            date,
            label,
            scenario.dest_debit_account_id,
            scenario.dest_credit_account_id,
            amt,
            True,
        )

        _logger.info("src move %s", source_company_move)
        _logger.info("dst move %s", destination_company_move)

        return {"type": "ir.actions.act_window_close"}
