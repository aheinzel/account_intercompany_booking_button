
{
    'name': 'Account Interco Quick Buttons',
    'version': '18.0.0.3.7',
    'category': 'Accounting',
    'summary': 'Quick fixed intercompany postings (Food/Childcare)',
    'depends': ['base', 'account'],
    'data': [
        'views/settings_view.xml',
                'views/wizard_views.xml',
        'views/move_form_view.xml',
    ],
    'installable': True,
    'application': False,
    'license': 'LGPL-3',
}
