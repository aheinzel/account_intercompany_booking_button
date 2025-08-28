
from odoo import models, fields, api, _
from odoo.exceptions import UserError

class IntercoQuickRun(models.TransientModel):
    _name = 'interco.quick.run'
    _description = 'Run predefined intercompany booking'

    template = fields.Selection([('food','Food/Groceries'),('child','Childcare')], required=False)
    ref = fields.Char(string="Reference")
    statement_line_id = fields.Many2one('account.bank.statement.line', ondelete='set null', required=False)

    def _find_account_by_code(self, company, code):
        return self.env['account.account'].search([('code','=',code),('company_id','=',company.id)], limit=1)

    
def action_run(self):
    """Create a journal entry for the selected template from a bank statement line.
    Minimal safe stub to keep module loading while we iterate.
    """
    self.ensure_one()
    st_line = self.statement_line_id
    if not st_line or not st_line.exists():
        raise UserError(_("The linked bank statement line no longer exists. Please reopen the wizard from an existing line."))

    # No-op for now (return True). Replace with actual posting logic once DB issues are fixed.
    return True
