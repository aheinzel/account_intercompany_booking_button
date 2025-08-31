from odoo import models, fields


class IntercompanyScenario(models.Model):
    _name = "intercompany.scenario"
    _description = "Intercompany Booking Scenario"

    name = fields.Char(required=True)
    active = fields.Boolean(default=True)

    source_company_id = fields.Many2one(
        "res.company",
        string="Source Company",
        required=True,
    )
    dest_company_id = fields.Many2one(
        "res.company",
        string="Destination Company",
        required=True,
    )

    source_journal_id = fields.Many2one(
        "account.journal",
        string="Source Journal",
        required=True,
    )
    dest_journal_id = fields.Many2one(
        "account.journal",
        string="Destination Journal",
        required=True,
    )

    source_debit_account_id = fields.Many2one(
        "account.account",
        string="Source Debit Account",
        required=True,
    )
    source_credit_account_id = fields.Many2one(
        "account.account",
        string="Source Credit Account",
        required=True,
    )
    dest_debit_account_id = fields.Many2one(
        "account.account",
        string="Destination Debit Account",
        required=True,
    )
    dest_credit_account_id = fields.Many2one(
        "account.account",
        string="Destination Credit Account",
        required=True,
    )

    # Multiple active scenarios are allowed; selection happens in the wizard.
