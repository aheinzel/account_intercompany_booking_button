/** @odoo-module **/

import { registry } from "@web/core/registry";

function addQuickIntercoButton(env) {
    const cpRight = document.querySelector(".o_control_panel .o_cp_top_right");
    if (!cpRight) return;
    if (cpRight.querySelector(".o_interco_quick_btn")) return;

    const btn = document.createElement("button");
    btn.className = "btn btn-primary o_interco_quick_btn";
    btn.textContent = env._t ? env._t("Quick Interco") : "Quick Interco";
    btn.style.marginRight = "8px";

    btn.addEventListener("click", async () => {
        // Try to find selected statement line id in the reconciliation widget DOM
        let lineEl = document.querySelector(".o_bank_rec_widget [data-line-id].o_selected")
                  || document.querySelector(".o_bank_rec_widget [data-line-id]");
        let lineId = lineEl && (lineEl.dataset.lineId || lineEl.getAttribute("data-line-id"));
        if (!lineId) {
            // Alternative selectors fallback
            lineEl = document.querySelector(".o_bank_rec_widget .o_rec_line.o_selected")
                  || document.querySelector(".o_bank_rec_widget .o_rec_line");
            lineId = lineEl && (lineEl.dataset.id || lineEl.getAttribute("data-id"));
        }
        if (!lineId) {
            env.services.notification.add(
                "No statement line detected in the Reconcile view.",
                { type: "warning" }
            );
            return;
        }
        try {
            await env.services.action.doAction(
                "account_interco_quickbuttons.action_open_interco_quick_wizard",
                { additionalContext: { default_statement_line_id: parseInt(lineId) } }
            );
        } catch (e) {
            env.services.notification.add(
                "Cannot open Quick Interco wizard. " + (e && e.message ? e.message : ""),
                { type: "danger" }
            );
        }
    });

    cpRight.prepend(btn);
}

const service = {
    start(env) {
        // Observe the DOM and inject the button when the reconciliation widget appears
        const observer = new MutationObserver(() => {
            const recWidget = document.querySelector(".o_bank_rec_widget");
            if (recWidget) {
                addQuickIntercoButton(env);
            }
        });
        observer.observe(document.body, { childList: true, subtree: true });
        return {};
    },
};

registry.category("services").add("interco_quick_reconcile_button", service);
