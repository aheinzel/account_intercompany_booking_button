import logging
from odoo import models, fields, _, api
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

    scenario_id = fields.Many2one(
        'intercompany.scenario',
        string="Scenario",
        required=True,
    )

    reference = fields.Char(string="Reference", required=True)

    file_data = fields.Binary(string="Attachment")
    file_name = fields.Char(string="Filename")
    file_mimetype = fields.Char(string="MIME Type")


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



    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        line_id = self.env.context.get('default_statement_line_id')
        if line_id and 'scenario_id' in fields_list:
            line = self.env['account.bank.statement.line'].browse(line_id)
            scenario = self.env['intercompany.scenario'].search([
                ('active', '=', True),
                ('source_company_id', '=', line.company_id.id),
            ], limit=1)
            if scenario:
                res['scenario_id'] = scenario.id
        return res


    @api.onchange('statement_line_id')
    def _onchange_statement_line_id(self):
        domain = [('active', '=', True)]
        if self.statement_line_id:
            domain.append(('source_company_id', '=', self.statement_line_id.company_id.id))
        return {'domain': {'scenario_id': domain}}


    def action_confirm(self):
        _logger.info("Intercompany booking: confirm")
        self.ensure_one()
        line = self.statement_line_id

        if not self.scenario_id:
            raise UserError(_("Please select an Intercompany Scenario."))
        scenario = self.scenario_id
        if not scenario.active:
            raise UserError(_("Selected scenario is archived. Please choose an active scenario."))
        if line and scenario.source_company_id != line.company_id:
            raise UserError(_("Selected scenario's source company does not match the bank statement line company."))

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

        # Attach uploaded file to both moves, if provided
        if self.file_data:
            attach_vals_common = {
                'name': self.file_name or 'attachment',
                'datas': self.file_data,
                'type': 'binary',
                'mimetype': self.file_mimetype or None,
                'res_model': 'account.move',
            }
            for move in (source_company_move, destination_company_move):
                vals = dict(attach_vals_common)
                vals.update({'res_id': move.id, 'company_id': move.company_id.id})
                self.env['ir.attachment'].create(vals)

        _logger.info("src move %s", source_company_move)
        _logger.info("dst move %s", destination_company_move)

        return {"type": "ir.actions.act_window_close"}
