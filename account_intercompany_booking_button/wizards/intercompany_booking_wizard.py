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

    reconcile_now = fields.Boolean(string="Reconcile now", default=True)

    # Helper: get Outstanding Payments accounts configured on outbound payment methods
    def _get_outstanding_payment_accounts(self, journal):
        outbound_lines = journal.outbound_payment_method_line_ids  # empty recordset if none
        return {ml.payment_account_id.id for ml in outbound_lines if ml.payment_account_id}

    # Helper: ensure reconciliation preconditions; return (st_line_in_src_company, outstanding_account_id)
    def _ensure_reconcile_preconditions(self, line, scenario):
        if not line:
            raise UserError(_("Intercompany: No bank statement line provided for reconciliation."))
        if not hasattr(line, '_add_account_move_line'):
            raise UserError(_("Intercompany: OCA reconciliation engine not available on statement line (account_reconcile_oca missing?)."))

        st = line.with_company(scenario.source_company_id)
        outstanding_accounts = self._get_outstanding_payment_accounts(st.journal_id)
        if not outstanding_accounts:
            raise UserError(_("Intercompany: Bank journal has no Outstanding Payments account configured on outbound payment methods."))
        if scenario.source_credit_account_id.id not in outstanding_accounts:
            raise UserError(_(
                "Intercompany: Scenario must credit one of the journal's Outstanding Payments accounts configured on outbound methods."
            ))
        if not st.move_id:
            raise UserError(_("Intercompany: Bank statement line has no posted move yet."))
        unreconciled = st.move_id.line_ids.filtered(lambda ml: not ml.reconciled and ml.account_id.reconcile)
        if not unreconciled:
            raise UserError(_("Intercompany: Nothing left to reconcile on the bank statement line."))
        return st, scenario.source_credit_account_id.id

    # Helper: pick created move line matching given account id and unreconciled
    def _find_target_move_line(self, move, account_id):
        target_ml = move.line_ids.filtered(lambda ml: ml.account_id.id == account_id and not ml.reconciled)
        if not target_ml:
            raise UserError(_(
                "Intercompany: Created source move has no unreconciled line on the Outstanding Payments account configured in the scenario."
            ))
        return target_ml[0]

    # (removed) _is_reconcile_default: no longer used since we allow existing selections


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
        if not line:
            raise UserError(_("Please open the wizard from a Bank Statement Line."))

        if not self.scenario_id:
            raise UserError(_("Please select an Intercompany Scenario."))
        scenario = self.scenario_id
        if not scenario.active:
            raise UserError(_("Selected scenario is archived. Please choose an active scenario."))
        if line and scenario.source_company_id != line.company_id:
            raise UserError(_("Selected scenario's source company does not match the bank statement line company."))

        # Pre-check reconciliation preconditions early (if enabled)
        if self.reconcile_now:
            st, op_account_id = self._ensure_reconcile_preconditions(line, scenario)

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

        # Post both moves (mark as booked)
        source_company_move.with_company(scenario.source_company_id).action_post()
        destination_company_move.with_company(scenario.dest_company_id).action_post()

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

        # Post bank statement description into chatter of both moves (payment_ref only)
        if line and line.payment_ref:
            body = f"Bank statement description: {line.payment_ref}"
            for move in (source_company_move, destination_company_move):
                move.message_post(body=body)

        _logger.info("src move %s", source_company_move)
        _logger.info("dst move %s", destination_company_move)

        # Deterministic reconciliation via OCA engine (optional)
        if self.reconcile_now:
            st, op_account_id = self._ensure_reconcile_preconditions(line, scenario)
            target_ml = self._find_target_move_line(source_company_move, op_account_id)
            try:
                # Only pre-populate the reconcile view with our counterpart line.
                # Do NOT validate/apply automatically; the user will hit Validate in the UI.
                st._add_account_move_line(target_ml, keep_current=True)
                _logger.info("ICB: Added counterpart line %s to statement line %s. Validation must be done by the user.", target_ml.id, st.id)
            except Exception as e:
                raise UserError(_("Intercompany: Auto-reconcile preparation failed: %s") % e)

        return {"type": "ir.actions.act_window_close"}
