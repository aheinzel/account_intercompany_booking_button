# Accounting Intercompany Booking Button (POC)

> WARNING
> Built and maintained using OpenAI's Codex CLI. This is a learning project, not production-ready; expect limited scope and missing edge-cases.

## What it is

A tiny proof-of-concept add-on that puts an **"Intercompany"** button on **Bank Statement Lines** (in the OCA reconcile form) and opens a wizard that books an **intercompany scenario** defined in configuration. The wizard creates **two 2-line journal entries** (one in a source company and one in a destination company) using the scenario's journals and accounts; the **amount** comes from the selected **bank statement line**.

Tested on **Odoo 18** with **`account_reconcile_oca`** installed.

## Background

This is the first iteration starting from a non GPT-5 produced PoC. We started from a non AI PoC because attempts to build the add-on from scratch with GPT-5 failed. See the git history for details. We are rebuilding and extending it with Codex CLI while keeping scope narrow and configuration in a dedicated model.

## Features

- Adds an **Intercompany** button to the **OCA Bank Statement Line** reconcile form (`account_reconcile_oca.bank_statement_line_form_reconcile_view`).
- Opens a wizard model: `intercompany.booking.wizard`.
- Uses a central configuration model: `intercompany.scenario`.
  - Multiple scenarios can be active; the wizard lets you select one.
  - The selector only lists scenarios whose source company matches the statement line's company.
  - Each scenario stores: source/destination companies, journals, and debit/credit accounts.
- Amount = `abs(statement_line.amount)`; Date = statement line date (or today).
- Creates and posts two minimal moves (2 lines each), one per company.
- Optional: upload a file in the wizard to attach it to both created journal entries.
- Posts the bank statement payment reference into the chatter of both moves, prefixed with "Bank statement description:".

Note: Scenario values live in `intercompany.scenario` and are read by the wizard during `action_confirm`.

## Compatibility & Dependencies

- **Odoo**: 18.0 (manifest `version: 18.0.0.0.0`)
- **Depends on**:
  - `account`
  - `account_reconcile_oca` (from OCA) - the "Intercompany" button is added on the OCA reconcile view.

## Installation

1. Ensure `account_reconcile_oca` is installed and working.
2. Copy this add-on directory into your server add-ons path, e.g. `/mnt/extra-addons/account_intercompany_booking_button`.
3. In Apps:
   - Update Apps List
   - Search for "Accounting Intercompany Booking Button"
   - Install (or Upgrade if already installed)
4. Refresh the browser if needed.

## Usage

1. Go to Accounting -> Reconcile and open a Bank Statement Line in the OCA reconcile form.
2. Click "Intercompany" in the header/statusbar.
3. In the wizard, pick a scenario (filtered to the statement line's company), optionally type a reference, and optionally upload a file to attach.
4. Confirm. The module creates and posts two 2-line journal entries using the selected scenario and the amount from the selected line; the uploaded file is attached to both moves, and the payment reference is logged in each move's chatter.

## Configuration

- Menu: Accounting -> Configuration -> Intercompany -> Intercompany Scenarios.
- Create scenario records with the desired companies, journals and accounts.
- You may have multiple active scenarios. In the wizard, choose the desired scenario. The list is filtered to the bank statement line's company (as source).
  In the action, archived (inactive) records are visible by default.

## Known Limitations

- Wizard requires a scenario selection (defaults to the first active scenario for the line's company when possible).
- No currency conversion, taxes, analytic, or multi-line logic.
- No automatic reconciliation; it just posts minimal moves.
- Minimal access control (transient wizard access only).
- Limited validation / error messages.
- Depends on the OCA reconcile view XMLID; if your DB uses a different view, the inheritance will fail.
- Some files are intentionally kept **bare-bones** to focus on the happy path.

## Project Layout (key files)

- `__manifest__.py` - metadata & dependencies  
- `models/account_bank_statement_line.py` - model shim / view trigger (POC-level)  
- `views/account_bank_statement_line.xml` - adds the **Intercompany** button on the OCA reconcile view  
- `wizards/intercompany_booking_wizard.py` - the transient wizard, reads active scenario and books moves  
- `views/intercompany_booking_wizard.xml` - wizard form (reference input + confirm/cancel)  
- `models/intercompany_scenario.py` - scenario model storing companies, accounts, journals  
- `views/intercompany_scenario_views.xml` - scenario tree/form views and menu entries  
- `security/ir.model.access.csv` - grants internal users access to the wizard and scenarios

## Development Notes

- If the **button doesn't appear**, verify that `account_reconcile_oca` is installed and that the XMLID
  `account_reconcile_oca.bank_statement_line_form_reconcile_view` exists in your DB.
- If you see **"record missing"** errors, ensure you actually opened the OCA reconcile form of a *real* bank statement line.
- If you want to generalize this:
  - Replace hardcoded lookups with settings or mapping models.
  - Add safety checks: journal availability per company, account types, posted state, locked dates, etc.
  - Write tests and linting; add proper security rules and logging.

## License

This repository is a learning artifact. No license has been chosen.

---

Built as a minimal spike to explore intercompany flow mechanics in Odoo 18 using Codex CLI. Use it as a starting point - not as a finished solution.
