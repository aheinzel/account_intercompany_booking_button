import logging
from odoo import models, fields

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


    def _find_company_by_name(self, name):
        return self.env['res.company'].search([
            ('name', 'ilike', name)
        ], limit=1)

    def _find_account_by_code(self, company, code):
        return self.env['account.account'].search([
            ('company_ids', '=', company.id),
            ('code', '=', code)
        ], limit=1)

    def _find_journal_by_code(self, company, code):
        _logger.info("journal search: %s", ('company_id', '=', company.id))
        _logger.info("journal search: %s", ('code' '=', code))
        return self.env['account.journal'].search([
            ('company_id', '=', company.id),
            ('code', '=', code)
        ], limit=1)

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
        _logger.info("run")
        line = self.statement_line_id
        source_company = self._find_company_by_name("Andreas")
        source_company_credit_account = self._find_account_by_code(source_company, 10000)
        source_company_debit_account = self._find_account_by_code(source_company, 2228)

        destination_company = self._find_company_by_name("Haushalt")
        destination_company_credit_account = self._find_account_by_code(destination_company, 3328)
        destination_company_debit_account = self._find_account_by_code(destination_company, "0000")

        _logger.info("source_company_credit_account: %s", source_company_credit_account)
        _logger.info("source_company_debit_account: %s", source_company_debit_account)
        _logger.info("destination_company_credit_account: %s", destination_company_credit_account)
        _logger.info("destination_company_debit_account: %s", destination_company_debit_account)

        signed_amt = line.amount or 0.0
        if signed_amt == 0.0:
            raise UserError(_("Zero-amount statement line cannot be posted."))

        amt = abs(signed_amt)
        date = line.date or fields.Date.context_today(self)
        label = self.reference

        # Pick journals (adapt preferred_code/jtype to your setup)
        source_company_journal = self._find_journal_by_code(source_company, 'MISC')
        destination_company_journal = self._find_journal_by_code(destination_company, 'MISC')


        # Create posted moves
        source_company_move = self._build_two_line_move(
             source_company, source_company_journal, 
             date, label, source_company_debit_account, source_company_credit_account, amt,
             True
        )

        destination_company_move = self._build_two_line_move(
             destination_company, destination_company_journal, 
             date, label, destination_company_debit_account, destination_company_credit_account, amt,
             True
        )


        _logger.info("src move %s", source_company_move)
        _logger.info("dst move %s", destination_company_move)

        return {"type": "ir.actions.act_window_close"}
