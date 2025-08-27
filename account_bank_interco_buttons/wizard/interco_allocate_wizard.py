from odoo import api, fields, models, _
from odoo.exceptions import UserError

class IntercoAllocateWizard(models.TransientModel):
    _name = "interco.allocate.wizard"
    _description = "Allocate bank statement amount across companies and create mirrored moves"

    statement_line_id = fields.Many2one("account.bank.statement.line", required=True)
    amount = fields.Monetary("Base Amount", required=True)
    currency_id = fields.Many2one("res.currency", required=True)
    ref_text = fields.Char(string="Reference (ref)")

    clearing_account_id = fields.Many2one(
        "account.account",
        string="Clearing/Outstanding Expenses Account",
        help="Account to offset the bank line (e.g., 2802 Bank‑Zwischenkonto or 4890 Outstanding expenses).",
        domain=[('deprecated', '=', False)]
    )
    reconcile_mode = fields.Selection(
        [
            ("clearing", "Use Clearing/Suspense"),
            ("out_exp", "Use Outstanding Expenses"),
        ],
        default="clearing",
        required=True,
    )

    attach_file = fields.Binary(string="Attachment")
    attach_filename = fields.Char(string="Filename")

    line_ids = fields.One2many("interco.allocate.wizard.line", "wizard_id", string="Allocations", required=True)

    @api.constrains('line_ids')
    def _check_percentages(self):
        for wiz in self:
            total = sum(wiz.line_ids.mapped('percent'))
            if round(total, 4) != 100.0:
                raise UserError(_("Percentages across companies must add up to 100%% (current: %s%%)") % total)

    def action_create_moves(self):
        self.ensure_one()
        st_line = self.statement_line_id
        if not st_line:
            raise UserError(_("No statement line in context."))

        base_amt = self.amount
        created_moves = self.env['account.move']

        for line in self.line_ids:
            alloc_amt = round(base_amt * (line.percent / 100.0), 2)
            if not alloc_amt:
                continue
            created_moves |= self._create_interco_pair(st_line, line, alloc_amt)

        if created_moves:
            st_line.interco_move_ids = [(4, m.id) for m in created_moves]

        if self.attach_file and self.attach_filename:
            for m in created_moves:
                self.env['ir.attachment'].create({
                    'name': self.attach_filename,
                    'datas': self.attach_file,
                    'res_model': 'account.move',
                    'res_id': m.id,
                    'type': 'binary',
                })

        self._auto_offset_and_reconcile(st_line, base_amt)

        action = st_line.action_view_journal_entries()
        if isinstance(action, dict):
            action['domain'] = [('id', 'in', created_moves.ids)]
        return action

    def _compose_ref(self, suffix: str = ""):
        parts = []
        if self.ref_text:
            parts.append(self.ref_text)
        if suffix:
            parts.append(suffix)
        return " | ".join([p for p in parts if p])

    def _auto_offset_and_reconcile(self, st_line, total_amt):
        bank_journal = st_line.journal_id
        company = st_line.company_id
        bank_account = bank_journal.default_account_id
        clearing_account = self.clearing_account_id
        if not bank_account or not clearing_account:
            return

        amount = total_amt
        debit, credit = (0.0, amount) if amount > 0 else (abs(amount), 0.0)

        move_vals = {
            'ref': self._compose_ref(_("Auto offset for bank line %s") % (st_line.name or st_line.payment_ref or st_line.id)),
            'journal_id': bank_journal.id,
            'date': fields.Date.context_today(self),
            'company_id': company.id,
            'line_ids': [
                (0, 0, {
                    'name': 'Bank mirror',
                    'account_id': bank_account.id,
                    'debit': debit,
                    'credit': credit,
                }),
                (0, 0, {
                    'name': 'Auto offset',
                    'account_id': clearing_account.id,
                    'debit': credit,
                    'credit': debit,
                }),
            ]
        }
        move = self.env['account.move'].with_company(company).create(move_vals)
        move.action_post()

        bank_ml = move.line_ids.filtered(lambda l: l.account_id.id == bank_account.id)
        try:
            if hasattr(st_line, 'process_reconciliation'):
                st_line.process_reconciliation(new_aml_dicts=[], existing_aml_ids=bank_ml.ids)
        except Exception:
            pass

    def _create_interco_pair(self, st_line, line, alloc_amt):
        src_company = st_line.company_id
        dst_company = line.company_id
        if src_company.id == dst_company.id:
            raise UserError(_("Target company cannot be the same as the statement line company."))

        src_partner = src_company.partner_id
        dst_partner = dst_company.partner_id
        if not src_partner or not dst_partner:
            raise UserError(_("Both companies must have a linked partner (res.partner)."))

        # SOURCE MOVE
        src_journal = line.src_journal_id or src_company._get_misc_journal()
        if not src_journal:
            raise UserError(_("No source journal in %s") % src_company.display_name)
        if not line.src_expense_account_id or not line.src_interco_ar_account_id:
            raise UserError(_("Select source expense and intercompany receivable accounts."))

        src_vals = {
            'ref': self._compose_ref(_("Interco AR to %s: %s") % (dst_company.display_name, (st_line.name or st_line.payment_ref or st_line.id))),
            'journal_id': src_journal.id,
            'date': fields.Date.context_today(self),
            'company_id': src_company.id,
            'line_ids': [
                (0, 0, {
                    'name': 'Reclass expense to interco',
                    'account_id': line.src_expense_account_id.id,
                    'credit': alloc_amt,
                    'debit': 0.0,
                }),
                (0, 0, {
                    'name': 'Intercompany AR to %s' % dst_company.display_name,
                    'account_id': line.src_interco_ar_account_id.id,
                    'debit': alloc_amt,
                    'credit': 0.0,
                    'partner_id': dst_partner.id,
                }),
            ]
        }
        src_move = self.env['account.move'].with_company(src_company).create(src_vals)
        src_move.action_post()

        # DEST MOVE
        dst_journal = line.dst_journal_id or dst_company._get_misc_journal()
        if not dst_journal:
            raise UserError(_("No destination journal in %s") % dst_company.display_name)
        if not line.dst_expense_account_id or not line.dst_interco_ap_account_id:
            raise UserError(_("Select destination expense and intercompany payable accounts."))

        dst_vals = {
            'ref': self._compose_ref(_("Interco AP from %s: %s") % (src_company.display_name, (st_line.name or st_line.payment_ref or st_line.id))),
            'journal_id': dst_journal.id,
            'date': fields.Date.context_today(self),
            'company_id': dst_company.id,
            'line_ids': [
                (0, 0, {
                    'name': 'Groceries (interco)',
                    'account_id': line.dst_expense_account_id.id,
                    'debit': alloc_amt,
                    'credit': 0.0,
                    'partner_id': src_company.partner_id.id,
                }),
                (0, 0, {
                    'name': 'Intercompany AP to %s' % src_company.display_name,
                    'account_id': line.dst_interco_ap_account_id.id,
                    'credit': alloc_amt,
                    'debit': 0.0,
                    'partner_id': src_company.partner_id.id,
                }),
            ]
        }
        dst_move = self.env['account.move'].with_company(dst_company).create(dst_vals)
        dst_move.action_post()

        desc = st_line.payment_ref or st_line.name or ''
        if desc:
            dst_move.message_post(body=_('Original bank line description: %s') % desc)

        return src_move | dst_move


class IntercoAllocateWizardLine(models.TransientModel):
    # Source company helper (related)
    _name = "interco.allocate.wizard.line"
    _description = "Per-company allocation row"

    wizard_id = fields.Many2one("interco.allocate.wizard", required=True, ondelete="cascade")
    src_company_id = fields.Many2one('res.company', string='Source Company', related='wizard_id.statement_line_id.company_id', readonly=True)
    company_id = fields.Many2one("res.company", required=True)
    percent = fields.Float(required=True, default=100.0, help="Share of base amount (must sum to 100 across lines)")

    # Source accounts
    src_expense_account_id = fields.Many2one("account.account", string="Source Expense", required=True, domain=[('deprecated', '=', False)])
    src_interco_ar_account_id = fields.Many2one("account.account", string="Source Interco AR (Forderungen)", required=True, domain=[('deprecated', '=', False)])
    src_journal_id = fields.Many2one("account.journal", string="Source Journal", domain=[('type', 'in', ['general', 'bank', 'cash'])])

    # Destination accounts
    dst_expense_account_id = fields.Many2one("account.account", string="Dest Expense (e.g., Groceries)", required=True, domain=[('deprecated', '=', False)])
    dst_interco_ap_account_id = fields.Many2one("account.account", string="Dest Interco AP (Verbindlichkeiten)", required=True, domain=[('deprecated', '=', False)])
    dst_journal_id = fields.Many2one("account.journal", string="Dest Journal", domain=[('type', 'in', ['general', 'bank', 'cash'])])

@api.onchange('company_id', 'src_company_id')
def _onchange_set_domains(self):
    for line in self:
        src_co = line.src_company_id.id if line.src_company_id else False
        dst_co = line.company_id.id if line.company_id else False
        line_domain = {
            'src_expense_account_id': [('deprecated', '=', False)],
            'src_interco_ar_account_id': [('deprecated', '=', False)],
            'src_journal_id': [('type','in', ['general','bank','cash'])],
            'dst_expense_account_id': [('deprecated', '=', False)],
            'dst_interco_ap_account_id': [('deprecated', '=', False)],
            'dst_journal_id': [('type','in', ['general','bank','cash'])],
        }
        if src_co:
            line_domain['src_expense_account_id'].append(('company_id', '=', src_co))
            line_domain['src_interco_ar_account_id'].append(('company_id', '=', src_co))
            line_domain['src_journal_id'].append(('company_id', '=', src_co))
        if dst_co:
            line_domain['dst_expense_account_id'].append(('company_id', '=', dst_co))
            line_domain['dst_interco_ap_account_id'].append(('company_id', '=', dst_co))
            line_domain['dst_journal_id'].append(('company_id', '=', dst_co))
        return {'domain': line_domain}
