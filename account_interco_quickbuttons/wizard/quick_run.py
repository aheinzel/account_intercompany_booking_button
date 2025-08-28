
from odoo import models, fields, api, _
from odoo.exceptions import UserError

class IntercoQuickRun(models.TransientModel):

    @api.model
    def default_get(self, fields_list):
        vals = super().default_get(fields_list)
        ctx = self.env.context or {}
        active_model = ctx.get('active_model')
        active_id = ctx.get('active_id')
        # If called from account.move, map to its statement_line_id
        if not vals.get('statement_line_id') and active_model == 'account.move' and active_id:
            move = self.env['account.move'].browse(active_id)
            if move.exists() and getattr(move, 'statement_line_id', False):
                vals['statement_line_id'] = move.statement_line_id.id
        ABSL = self.env['account.bank.statement.line']
        # Prefer active_ids (list selection), fallback to active_id
        ctx = self.env.context or {}
        line_id = vals.get('statement_line_id') or (ctx.get('active_ids')[0] if ctx.get('active_ids') else ctx.get('active_id'))
        if line_id and ABSL.browse(line_id).exists():
            vals['statement_line_id'] = line_id
        else:
            # ensure empty if invalid/missing
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
    _name = 'interco.quick.run'
    _description = 'Run predefined intercompany booking'

    template = fields.Selection([('food','Food/Groceries'),('child','Childcare')], required=False)
    ref = fields.Char(string="Reference")
    statement_line_id = fields.Many2one('account.bank.statement.line', ondelete='set null', required=True)

    def _find_account_by_code(self, company, code):
        return self.env['account.account'].search([('code','=',code),('company_id','=',company.id)], limit=1)

    def action_run(self):
        """Create a journal entry for the selected template from a bank statement line.
        Minimal safe stub to keep module loading while we iterate.
        """
        self.ensure_one()
        st_line = self.statement_line_id
        if not st_line or not st_line.exists():
            raise UserError(_("Please select an existing Bank Statement Line (the previously selected one is gone)."))
        return True
