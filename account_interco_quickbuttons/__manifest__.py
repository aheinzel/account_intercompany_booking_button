
{
    'name': 'Account Interco Quick Buttons',
    'version': '18.0.0.4.2',
    'category': 'Accounting',
    'summary': 'Quick fixed intercompany postings (Food/Childcare)',
    'depends': ['account'],
    'data': [
        'security/ir.model.access.csv',
        'views/settings_view.xml',
                'views/wizard_views.xml',
        'views/move_form_view.xml',
    ],
    'installable': True,
    'application': False,
    'license': 'LGPL-3', 
    'assets': {
        'web.assets_backend': [
            'account_interco_quickbuttons/static/src/js/reconcile_quickbutton.js',
        ],
    }
}