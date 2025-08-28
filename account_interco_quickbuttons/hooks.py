from odoo import api, SUPERUSER_ID

def _drop_fk_on(cr, table, column):
    # Drop any FK on table(column)
    cr.execute("""
        SELECT conname
        FROM pg_constraint c
        JOIN pg_class t ON t.oid = c.conrelid
        JOIN pg_attribute a ON a.attrelid = t.oid
        WHERE t.relname = %s
          AND a.attnum = ANY (c.conkey)
          AND a.attname = %s
          AND c.contype = 'f'
    """, (table, column))
    for (conname,) in cr.fetchall():
        cr.execute('ALTER TABLE "%s" DROP CONSTRAINT "%s"' % (table, conname))

def pre_init_hook(cr):
    # Ensure column is nullable
    cr.execute("""        DO $$
        BEGIN
          IF EXISTS (
            SELECT 1
            FROM information_schema.columns
            WHERE table_name = 'interco_quick_run'
              AND column_name = 'statement_line_id'
          ) THEN
            EXECUTE 'ALTER TABLE interco_quick_run ALTER COLUMN statement_line_id DROP NOT NULL';
          END IF;
        END$$;
    """)
    # Drop any existing FK and recreate relaxed FK with SET NULL + DEFERRABLE
    _drop_fk_on(cr, 'interco_quick_run', 'statement_line_id')
    cr.execute("""        DO $$
        BEGIN
          IF EXISTS (
            SELECT 1 FROM information_schema.tables
            WHERE table_name = 'interco_quick_run'
          ) THEN
            EXECUTE $SQL$
              ALTER TABLE interco_quick_run
              ADD CONSTRAINT interco_quick_run_statement_line_id_fkey
              FOREIGN KEY (statement_line_id)
              REFERENCES account_bank_statement_line(id)
              ON DELETE SET NULL
              DEFERRABLE INITIALLY DEFERRED
            $SQL$;
          END IF;
        END$$;
    """)

def post_init_hook(cr, registry):
    # No-op, reserved for future
    pass
