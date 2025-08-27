from odoo import models, fields

class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    interco_quickbuttons_enabled = fields.Boolean(
        string='Intercompany Quick Buttons',
        config_parameter='account_interco_quickbuttons.enabled',
        help='Show one-click intercompany booking wizard on bank statement-linked journal entries.'
    )
