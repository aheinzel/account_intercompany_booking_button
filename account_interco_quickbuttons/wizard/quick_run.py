
from odoo import models, fields, api, _
from odoo.exceptions import UserError
from datetime import date

class IntercoQuickRun(models.TransientModel):
    _name = "interco.quick.run"
    _description = "Run a preconfigured intercompany quick booking"

    statement_line_id = fields.Many2one("account.bank.statement.line", required=True, readonly=True)
    template = fields.Selection([('food','Food / Groceries'), ('child','Childcare')], required=True, default='food')
    ref_override = fields.Char(string="Override Ref")
    attach_file = fields.Binary(string="Attachment")
    attach_filename = fields.Char(string="Filename")

    def _find_company(self, key_hint=None):
        st = self.statement_line_id
        src_company = st.company_id
        dst_id = self._get_param_id('interco.quick.dst_company_id', required=False)
        if dst_id:
            dst_company = self.env['res.company'].browse(dst_id)
        else:
            dst_company = self.env['res.company'].search([('name', 'ilike', 'Household')], limit=1)
        if not dst_company:
            raise UserError(_("Destination company not set. Please set it in Settings ▸ Intercompany Quick Buttons."))
        return src_company, dst_company

    def _find_journal(self, company, param_key):
        j_id = self._get_param_id(param_key, required=False)
        if j_id:
            j = self.env['account.journal'].browse(j_id)
            if j.company_id != company:
                raise UserError(_("Configured journal for %s does not belong to %s") % (param_key, company.name))
            return j
        j = self.env['account.journal'].search([('type', '=', 'general'), ('company_id', '=', company.id)], limit=1)
        if not j:
            raise UserError(_("No Miscellaneous Journal found in %s") % company.name)
        return j

    def _find_account_by_code(self, company, code):
        return self.env['account.account'].search([('code', '=', code), ('company_id', '=', company.id)], limit=1)

    def _resolve_accounts(self, src_company, dst_company, template_key):
        src_interco_ar_id = self._get_param_id('interco.quick.src_interco_ar_account_id', required=False)
        src_interco_ar = self.env['account.account'].browse(src_interco_ar_id) if src_interco_ar_id else self._find_account_by_code(src_company, '2228')
        if not src_interco_ar:
            raise UserError(_("Set Source Interco AR in Settings or create code 2228 in %s") % src_company.name)

        if template_key == 'food':
            src_exp_id = self._get_param_id('interco.quick.src_food_expense_account_id', required=False)
            src_exp = self.env['account.account'].browse(src_exp_id) if src_exp_id else self._find_account_by_code(src_company, '10000')
        else:
            src_exp_id = self._get_param_id('interco.quick.src_child_expense_account_id', required=False)
            src_exp = self.env['account.account'].browse(src_exp_id) if src_exp_id else self._find_account_by_code(src_company, '10000')
        if not src_exp:
            raise UserError(_("Set Source Expense (%s) in Settings or create code 10000 in %s") % (template_key, src_company.name))

        dst_interco_ap_id = self._get_param_id('interco.quick.dst_interco_ap_account_id', required=False)
        dst_interco_ap = self.env['account.account'].browse(dst_interco_ap_id) if dst_interco_ap_id else self._find_account_by_code(dst_company, '3328')
        if not dst_interco_ap:
            raise UserError(_("Set Destination Interco AP in Settings or create code 3328 in %s") % dst_company.name)

        if template_key == 'food':
            dst_exp_id = self._get_param_id('interco.quick.dst_food_expense_account_id', required=False)
            dst_exp = self.env['account.account'].browse(dst_exp_id) if dst_exp_id else self._find_account_by_code(dst_company, '0000')
            default_ref = _("Food/Groceries")
        else:
            dst_exp_id = self._get_param_id('interco.quick.dst_child_expense_account_id', required=False)
            dst_exp = self.env['account.account'].browse(dst_exp_id) if dst_exp_id else self._find_account_by_code(dst_company, '0001')
            default_ref = _("Childcare")
        if not dst_exp:
            raise UserError(_("Set Destination Expense (%s) in Settings or create code %s in %s") % (template_key, '0000' if template_key=='food' else '0001', dst_company.name))

        return src_exp, src_interco_ar, dst_exp, dst_interco_ap, default_ref

    def _get_param_id(self, key, required=True):
        val = self.env['ir.config_parameter'].sudo().get_param(key)
        rec_id = int(val) if val and val.isdigit() else False
        if required and not rec_id:
            raise UserError(_("Missing configuration: %s") % key)
        return rec_id

    def _get_param_bool(self, key, default=True):
        val = self.env['ir.config_parameter'].sudo().get_param(key)
        if val is None:
            return default
        return val.lower() in ('1','true','yes','y')

    def action_run(self):
        self.ensure_one()
        st = self.statement_line_id

        src_company, dst_company = self._find_company()
        src_journal = self._find_journal(src_company, 'interco.quick.src_journal_id')
        dst_journal = self._find_journal(dst_company, 'interco.quick.dst_journal_id')

        src_exp, src_interco_ar, dst_exp, dst_interco_ap, default_ref = self._resolve_accounts(src_company, dst_company, self.template)

        amt = st.amount or 0.0
        if self._get_param_bool('interco.quick.use_abs_amount', True):
            amt = abs(amt)
        if not amt:
            raise UserError(_("The bank line has zero amount."))

        ref = self.ref_override or (st.payment_ref or st.name or default_ref or '')

        src_move = self.env['account.move'].with_company(src_company.id).create({
            'date': date.today(),
            'ref': ref,
            'journal_id': src_journal.id,
            'company_id': src_company.id,
            'line_ids': [
                (0, 0, {'name': ref, 'account_id': src_exp.id, 'debit': amt if amt>0 else 0.0, 'credit': -amt if amt<0 else 0.0}),
                (0, 0, {'name': ref, 'account_id': src_interco_ar.id, 'credit': amt if amt>0 else 0.0, 'debit': -amt if amt<0 else 0.0}),
            ]
        })
        src_move._post()

        dst_move = self.env['account.move'].with_company(dst_company.id).create({
            'date': date.today(),
            'ref': ref,
            'journal_id': dst_journal.id,
            'company_id': dst_company.id,
            'line_ids': [
                (0, 0, {'name': ref, 'account_id': dst_exp.id, 'debit': amt if amt>0 else 0.0, 'credit': -amt if amt<0 else 0.0}),
                (0, 0, {'name': ref, 'account_id': dst_interco_ap.id, 'credit': amt if amt>0 else 0.0, 'debit': -amt if amt<0 else 0.0}),
            ]
        })
        dst_move._post()

        st.write({'interco_move_ids': [(4, src_move.id), (4, dst_move.id)]})
        if self.attach_file and self.attach_filename:
            for mv in (src_move, dst_move):
                self.env['ir.attachment'].create({'name': self.attach_filename, 'res_model': 'account.move', 'res_id': mv.id, 'datas': self.attach_file})

        return {
            'name': _('Intercompany Moves'),
            'type': 'ir.actions.act_window',
            'res_model': 'account.move',
            'view_mode': 'list,form',
            'domain': [('id', 'in', [src_move.id, dst_move.id])],
        }
