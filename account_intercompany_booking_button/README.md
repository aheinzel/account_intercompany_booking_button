# Accounting Intercompany Booking Button (POC)

> ⚠️ **Disclaimer**  
> This repository is **another attempt to let GPT‑5 develop an Odoo add‑on** for a very specific use case.  
> It is **not** production‑ready and is provided **for educational purposes only**.  
> Expect hardcoded values, missing edge‑case handling, and compatibility quirks.
> This specific version (current commit) was not GPT-5 generated as we have hit multiple road blocks, but next iterations will again use GPT-5.
> **Also this readme has been written by GPT-5**

## What it is

A tiny proof‑of‑concept add‑on that puts an **“Intercompany”** button on **Bank Statement Lines** (in the OCA reconcile form) and opens a wizard that books a **single hardcoded intercompany scenario**. The wizard creates **two 2‑line journal entries** (one in a source company and one in a destination company) using fixed company names, account codes, and journal codes; the **amount** comes from the selected **bank statement line**.

Tested on **Odoo 18** with **`account_reconcile_oca`** installed.

## Why this version exists (and why earlier iterations failed)

Earlier runs attempted a more dynamic, configurable module (settings panel, header buttons on multiple views, injection into the reconcile widget, transient wizard constraints, etc.). The failures we hit are common when developing against varying Odoo setups:

- **View inheritance targets differed** across editions/installs (e.g., missing XMLIDs like `base.view_res_config_settings`, `account.view_bank_stmt_line_form` vs `view_bank_statement_line_form`, or depending on OCA views).  
- The **reconcile screen is an OWL/JS widget**, not a simple form; adding buttons requires frontend assets and robust selectors (DOM can differ).  
- **Transient model access & FKs**: a Many2one to `account.bank.statement.line` initially blocked deletions due to a restrictive FK; changing `ondelete` in Python doesn’t retro‑rewrite PostgreSQL constraints, so upgrade hooks/SQL were needed.  
- **Stale selection IDs** from the reconcile UI produced “record missing” errors when the DOM didn’t reflect real DB ids (or lines were auto‑removed).

To move forward quickly, this POC keeps everything **hardcoded** and supports **one happy path** only. Previous iterations are nevertheless kept in the repository.

## Features (hardcoded)

- Adds an **Intercompany** button to the **OCA Bank Statement Line** reconcile form (`account_reconcile_oca.bank_statement_line_form_reconcile_view`).
- Opens a wizard model: `intercompany.booking.wizard`.
- Uses **hardcoded** values inside `action_confirm`:
  - **Source company name**: `Andreas`
  - **Destination company name**: `Haushalt`
  - **Accounts (by code)**: `10000`, `2228`, `3328`, `0000`
  - **Journal (by code)**: `MISC`
- Amount = `abs(statement_line.amount)`; Date = statement line date (or today).
- Creates two minimal moves (2 lines each), one per company.

> Note: The exact constants live in `wizards/intercompany_booking_wizard.py` (methods like `_find_company_by_name`, `_find_account_by_code`, `_find_journal_by_code`, and `action_confirm`).

## Compatibility & Dependencies

- **Odoo**: 18.0 (manifest `version: 18.0.0.0.0`)
- **Depends on**:
  - `account`
  - `account_reconcile_oca` (from OCA)—the “Intercompany” button is added on the OCA reconcile view.

## Installation

1. Ensure `account_reconcile_oca` is installed and working.
2. Copy this add‑on directory into your server add‑ons path, e.g. `/mnt/extra-addons/account_intercompany_booking_button`.
3. In Apps:
   - **Update Apps List**
   - Search for **Accounting Intercompany Booking Button**
   - **Install** (or **Upgrade** if already installed)
4. If you changed any web assets, reload with `?debug=assets` or clear cache.

## Usage

1. Go to **Accounting → Reconcile** and open a **Bank Statement Line** in the OCA reconcile form.
2. Click **Intercompany** in the header/statusbar.
3. In the wizard, (optionally) type a reference and **Confirm**.
4. The module will create two 2‑line journal entries using the **fixed companies/accounts/journal** and the **amount** from the selected line.

## Configuration

None. This POC is intentionally hardcoded. To adapt it:
- Edit `wizards/intercompany_booking_wizard.py`:
  - Change company lookup strings (e.g., `"Andreas"`, `"Haushalt"`)
  - Change `_find_account_by_code` and account codes
  - Change `_find_journal_by_code` and journal code

## Known Limitations

- **Hardcoded** companies, accounts and journals (single scenario only).
- No currency conversion, taxes, analytic, or multi‑line logic.
- No automatic reconciliation; it just posts minimal moves.
- Minimal access control (transient wizard access only).
- Limited validation / error messages.
- Depends on the OCA reconcile view XMLID; if your DB uses a different view, the inheritance will fail.
- Some files are intentionally kept **bare‑bones** to focus on the happy path.

## Project Layout (key files)

- `__manifest__.py` — metadata & dependencies  
- `models/account_bank_statement_line.py` — model shim / view trigger (POC‑level)  
- `views/account_bank_statement_line.xml` — adds the **Intercompany** button on the OCA reconcile view  
- `wizards/intercompany_booking_wizard.py` — the transient wizard, hardcoded booking logic  
- `views/intercompany_booking_wizard.xml` — wizard form (reference input + confirm/cancel)  
- `security/ir.model.access.csv` — grants internal users access to the wizard

## Development Notes

- If the **button doesn’t appear**, verify that `account_reconcile_oca` is installed and that the XMLID
  `account_reconcile_oca.bank_statement_line_form_reconcile_view` exists in your DB.
- If you see **“record missing”** errors, ensure you actually opened the OCA reconcile form of a *real* bank statement line.
- If you want to generalize this:
  - Replace hardcoded lookups with settings or mapping models.
  - Add safety checks: journal availability per company, account types, posted state, locked dates, etc.
  - Write tests and linting; add proper security rules and logging.

## License

This repository is a **learning artifact**. No license has been chosen;

---

Built as a minimal, working spike to explore intercompany flow mechanics in Odoo 18. Use it as a starting point—**not** as a finished solution.
