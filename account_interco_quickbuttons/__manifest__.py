
{
    'name': 'Account Interco Quick Buttons',
    'version': '18.0.0.3.2',
    'category': 'Accounting',
    'summary': 'Quick fixed intercompany postings (Food/Childcare)',
    'depends': ['base', 'account'],
    'data': [
        'views/settings_view.xml',
        'views/statement_line_view.xml',
        'views/wizard_views.xml',
    ],
    'installable': True,
    'application': False,
    'license': 'LGPL-3',
}
