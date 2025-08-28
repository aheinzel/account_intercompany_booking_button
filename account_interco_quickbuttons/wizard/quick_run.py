from odoo import models, fields, api, _
from odoo.exceptions import UserError

class IntercoQuickRun(models.TransientModel):
    _name = 'interco.quick.run'
    _description = 'Run predefined intercompany booking'

    template = fields.Selection([
        ('food', 'Food / Groceries'),
        ('child', 'Childcare'),
    ], string="Template")
    ref = fields.Char(string="Reference")
    statement_line_id = fields.Many2one(
        'account.bank.statement.line',
        string="Bank Statement Line",
        ondelete='set null',
        required=False,
    )

    # ---------- Helpers ----------
    def _find_account_by_code(self, company, code):
        return self.env['account.account'].search([('company_id','=',company.id), ('code','=',code)], limit=1)

    def _pick_expense_account(self, company):
        # Try common Austrian EKR expense codes first, then fallback by name
        codes = ['7201', '7200', '7300', '7610', '6000']
        for code in codes:
            acc = self._find_account_by_code(company, code)
            if acc:
                return acc
        # fallback by name
        acc = self.env['account.account'].search([('company_id','=',company.id), ('name','ilike','Lebensmittel')], limit=1)
        if acc:
            return acc
        acc = self.env['account.account'].search([('company_id','=',company.id), ('name','ilike','Aufwand')], limit=1)
        if acc:
            return acc
        acc = self.env['account.account'].search([('company_id','=',company.id), ('name','ilike','Expense')], limit=1)
        return acc

    def _pick_childcare_expense_account(self, company):
        prefs = ['7299', '7290', '7320']
        for code in prefs:
            acc = self._find_account_by_code(company, code)
            if acc:
                return acc
        acc = self.env['account.account'].search([('company_id','=',company.id), ('name','ilike','Kinder')], limit=1)
        if acc:
            return acc
        return self._pick_expense_account(company)

    def _pick_income_account(self, company):
        codes = ['4890', '4000']
        for code in codes:
            acc = self._find_account_by_code(company, code)
            if acc:
                return acc
        acc = self.env['account.account'].search([('company_id','=',company.id), ('name','ilike','Erlös')], limit=1)
        if acc:
            return acc
        acc = self.env['account.account'].search([('company_id','=',company.id), ('name','ilike','Income')], limit=1)
        return acc

    # ---------- Lifecycle guards ----------
    @api.model
    def default_get(self, fields_list):
        vals = super().default_get(fields_list)
        ctx = self.env.context or {}
        # Accept being called from account.move (map to its statement_line_id)
        if not vals.get('statement_line_id') and ctx.get('active_model') == 'account.move' and ctx.get('active_id'):
            move = self.env['account.move'].browse(ctx['active_id'])
            if move.exists() and getattr(move, 'statement_line_id', False):
                vals['statement_line_id'] = move.statement_line_id.id
        # Clear if stale
        sl_id = vals.get('statement_line_id')
        if sl_id and not self.env['account.bank.statement.line'].browse(sl_id).exists():
            vals['statement_line_id'] = False
        return vals

    @api.model_create_multi
    def create(self, vals_list):
        ABSL = self.env['account.bank.statement.line']
        for vals in vals_list:
            sl_id = vals.get('statement_line_id')
            if sl_id and not ABSL.browse(sl_id).exists():
                vals['statement_line_id'] = False
        return super().create(vals_list)

    @api.onchange('statement_line_id')
    def _onchange_statement_line_id(self):
        if self.statement_line_id and not self.statement_line_id.exists():
            self.statement_line_id = False
            return {
                'warning': {
                    'title': _('Statement line not found'),
                    'message': _('The selected bank statement line no longer exists and was cleared.')
                }
            }
        return {}

    # ---------- Action ----------
    def action_run(self):
        """Create and post a journal entry from the selected bank statement line.
        - Outgoing (negative): debit expense, credit bank.
        - Incoming (positive): debit bank, credit income.
        """
        self.ensure_one()
        st_line = self.statement_line_id
        if not st_line or not st_line.exists():
            raise UserError(_("Please select an existing Bank Statement Line (the previously selected one is gone)."))

        company = st_line.company_id
        journal = self.env['account.journal'].search([('company_id','=',company.id), ('type','=','general')], limit=1) or st_line.journal_id

        # Bank account
        bank_account = getattr(st_line.journal_id, 'default_account_id', False)
        if not bank_account:
            bank_account = self._find_account_by_code(company, '2802') or                            self._find_account_by_code(company, '2800') or                            self.env['account.account'].search([('company_id','=',company.id), ('name','ilike','Bank')], limit=1)
        if not bank_account:
            raise UserError(_("Could not determine the bank account for journal %s. Please configure default_account_id.") % (st_line.journal_id.display_name,))

        amount = st_line.amount or 0.0
        if not amount:
            raise UserError(_("The bank statement line has zero amount."))

        label = self.ref or (st_line.payment_ref or st_line.name or _('Interco booking'))
        if amount < 0:
            # money out → expense
            other_account = self._pick_childcare_expense_account(company) if self.template == 'child' else self._pick_expense_account(company)
            if not other_account:
                raise UserError(_("No suitable expense account found in company %s.") % (company.display_name,))
            debit_line = {'account_id': other_account.id, 'debit': abs(amount), 'credit': 0.0, 'name': label}
            credit_line = {'account_id': bank_account.id, 'debit': 0.0, 'credit': abs(amount), 'name': label}
        else:
            # money in → income
            other_account = self._pick_income_account(company)
            if not other_account:
                raise UserError(_("No suitable income account found in company %s.") % (company.display_name,))
            debit_line = {'account_id': bank_account.id, 'debit': amount, 'credit': 0.0, 'name': label}
            credit_line = {'account_id': other_account.id, 'debit': 0.0, 'credit': amount, 'name': label}

        move_vals = {
            'ref': label,
            'date': getattr(st_line, 'date', False) or fields.Date.context_today(self),
            'journal_id': journal.id,
            'company_id': company.id,
            'line_ids': [(0, 0, debit_line), (0, 0, credit_line)],
        }
        move = self.env['account.move'].create(move_vals)

        if 'statement_line_id' in self.env['account.move']._fields:
            move.statement_line_id = st_line.id

        move.action_post()

        try:
            st_line.message_post(body=_("Created interco entry %s via Quick Booking.") % (move.display_name,))
        except Exception:
            pass

        return {'type': 'ir.actions.act_window_close'}