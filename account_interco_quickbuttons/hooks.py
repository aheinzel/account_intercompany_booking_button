def post_init_hook(cr, registry):
    cr.execute("""
        ALTER TABLE IF EXISTS interco_quick_run
        ALTER COLUMN statement_line_id DROP NOT NULL;
    """)
    cr.execute("""
    DO $$
    DECLARE
        r record;
    BEGIN
        FOR r IN
            SELECT conname
            FROM pg_constraint c
            JOIN pg_class t ON t.oid = c.conrelid
            WHERE t.relname = 'interco_quick_run'
              AND conname LIKE '%statement_line_id%'
        LOOP
            EXECUTE 'ALTER TABLE interco_quick_run DROP CONSTRAINT ' || quote_ident(r.conname);
        END LOOP;
    END$$;
    """)
    cr.execute("""
        ALTER TABLE interco_quick_run
        ADD CONSTRAINT interco_quick_run_statement_line_id_fkey
        FOREIGN KEY (statement_line_id)
        REFERENCES account_bank_statement_line(id)
        ON DELETE SET NULL
        DEFERRABLE INITIALLY DEFERRED;
    """)
