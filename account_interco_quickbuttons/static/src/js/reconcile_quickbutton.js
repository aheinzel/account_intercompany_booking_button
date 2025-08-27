/** @odoo-module **/

import { registry } from "@web/core/registry";

function _pickStatementLineId(root) {
    // 1) Exact model-tagged nodes
    let el =
        root.querySelector('[data-model="account.bank.statement.line"][data-id].o_selected') ||
        root.querySelector('[data-res-model="account.bank.statement.line"][data-res-id].o_selected') ||
        root.querySelector('[data-model="account.bank.statement.line"][data-id]') ||
        root.querySelector('[data-res-model="account.bank.statement.line"][data-res-id]');

    // 2) Generic line containers
    if (!el) {
        el = root.querySelector('[data-line-id].o_selected') || root.querySelector('[data-line-id]');
    }
    if (!el) {
        el = root.querySelector('.o_rec_line.o_selected') || root.querySelector('.o_rec_line');
    }
    if (!el) {
        return null;
    }

    // Extract possible id values
    const candidates = [
        el.dataset.id,
        el.getAttribute('data-id'),
        el.dataset.resId,
        el.getAttribute('data-res-id'),
        el.dataset.lineId,
        el.getAttribute('data-line-id'),
    ].filter(Boolean);

    for (let raw of candidates) {
        // Potentially in form "model,id"
        const parts = String(raw).split(',');
        let maybe = parts.length > 1 ? parts[1] : parts[0];
        // Strip non-digits
        maybe = (maybe || '').match(/\d+/);
        if (maybe) {
            return parseInt(maybe[0]);
        }
    }
    return null;
}

async function openQuickInterco(env) {
    const recRoot = document.querySelector('.o_bank_rec_widget') || document.body;
    const id = _pickStatementLineId(recRoot);
    if (!id) {
        env.services.notification.add(env._t('No statement line detected in Reconcile view.'), { type: 'warning' });
        return;
    }
    try {
        // Verify the ID exists to avoid server crash.
        const check = await env.services.orm.searchRead(
            'account.bank.statement.line',
            [['id', '=', id]],
            ['id']
        );
        if (!check || !check.length) {
            env.services.notification.add(env._t('Selected statement line no longer exists. Please refresh and try again.'), { type: 'warning' });
            return;
        }
        await env.services.action.doAction('account_interco_quickbuttons.action_open_interco_quick_wizard', {
            additionalContext: { default_statement_line_id: id },
        });
    } catch (e) {
        env.services.notification.add((e && e.message) || env._t('Could not open Quick Interco wizard.'), { type: 'danger' });
    }
}

function addButton(env) {
    const cpRight = document.querySelector('.o_control_panel .o_cp_top_right');
    if (!cpRight) return;
    if (cpRight.querySelector('.o_interco_quick_btn')) return;

    const btn = document.createElement('button');
    btn.className = 'btn btn-primary o_interco_quick_btn';
    btn.textContent = env._t ? env._t('Quick Interco') : 'Quick Interco';
    btn.style.marginRight = '8px';
    btn.addEventListener('click', () => openQuickInterco(env));
    cpRight.prepend(btn);
}

const service = {
    start(env) {
        const observer = new MutationObserver(() => {
            const recWidget = document.querySelector('.o_bank_rec_widget');
            if (recWidget) {
                addButton(env);
            }
        });
        observer.observe(document.body, { childList: true, subtree: true });
        return {};
    },
};

registry.category('services').add('interco_quick_reconcile_button', service);
