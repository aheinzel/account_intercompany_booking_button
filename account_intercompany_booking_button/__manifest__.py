{
    "name": "Accounting Intercompany Booking Button",
    "version": "18.0.0.0.0",
    "depends": ["account", "account_reconcile_oca"], 
    "data": [
       "security/ir.model.access.csv",
       "views/account_bank_statement_line.xml",
       "views/intercompany_booking_wizard.xml",
       "views/intercompany_scenario_views.xml"
    ],
    "installable": True
}
