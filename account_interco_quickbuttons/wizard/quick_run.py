
from odoo import models, fields, api, _
from odoo.exceptions import UserError

class IntercoQuickRun(models.TransientModel):
    _name = 'interco.quick.run'
    _description = 'Run predefined intercompany booking'

    template = fields.Selection([('food','Food/Groceries'),('child','Childcare')], required=True)
    ref = fields.Char(string="Reference")
    statement_line_id = fields.Many2one('account.bank.statement.line', required=True)

    def _find_account_by_code(self, company, code):
        return self.env['account.account'].search([('code','=',code),('company_id','=',company.id)], limit=1)

    def action_run(self):
        st_line = self.statement_line_id
        src_company = st_line.company_id
        dst_company = self.env['res.company'].search([('name','ilike','Household')], limit=1)
        if not dst_company:
            raise UserError(_("Destination company Household not found"))

        # Journals
        src_journal = self.env['account.journal'].search([('type','=','general'),('company_id','=',src_company.id)], limit=1)
        dst_journal = self.env['account.journal'].search([('type','=','general'),('company_id','=',dst_company.id)], limit=1)
        if not src_journal or not dst_journal:
            raise UserError(_("Need general journals in both companies"))

        # Accounts
        src_interco_ar = self._find_account_by_code(src_company,'2228')
        dst_interco_ap = self._find_account_by_code(dst_company,'3328')
        if self.template == 'food':
            src_exp = self._find_account_by_code(src_company,'10000')
            dst_exp = self._find_account_by_code(dst_company,'0000')
            ref = self.ref or _("Food/Groceries")
        else:
            src_exp = self._find_account_by_code(src_company,'10000')
            dst_exp = self._find_account_by_code(dst_company,'0001')
            ref = self.ref or _("Childcare")
        if not src_exp or not dst_exp or not src_interco_ar or not dst_interco_ap:
            raise UserError(_("Missing required accounts"))

        amount = abs(st_line.amount)

        # Source move
        with self.env.cr.savepoint():
            src_move = self.env['account.move'].with_company(src_company).create({
                'journal_id': src_journal.id,
                'line_ids':[
                    (0,0,{'account_id': src_exp.id,'debit': amount if st_line.amount<0 else 0.0,'credit': amount if st_line.amount>0 else 0.0,'name': ref}),
                    (0,0,{'account_id': src_interco_ar.id,'credit': amount if st_line.amount<0 else 0.0,'debit': amount if st_line.amount>0 else 0.0,'name': ref}),
                ],
                'ref': ref,
            })
            src_move.action_post()
        # Dest move
        with self.env.cr.savepoint():
            dst_move = self.env['account.move'].with_company(dst_company).create({
                'journal_id': dst_journal.id,
                'line_ids':[
                    (0,0,{'account_id': dst_exp.id,'debit': amount,'name': ref}),
                    (0,0,{'account_id': dst_interco_ap.id,'credit': amount,'name': ref}),
                ],
                'ref': ref,
            })
            dst_move.action_post()

        st_line.write({'note': (st_line.note or '') + f" Interco booking: {ref}"})
        return True
