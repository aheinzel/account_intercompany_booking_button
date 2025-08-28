from odoo import api, SUPERUSER_ID

def _tables_with_column(cr, colname, schema='public', prefix='interco'):
    cr.execute("""        SELECT table_name
        FROM information_schema.columns
        WHERE table_schema = %s
          AND column_name = %s
          AND table_name LIKE %s
        ORDER BY table_name
    """, (schema, colname, f"{prefix}%"))
    return [r[0] for r in cr.fetchall()]

def _drop_fk_on(cr, table, column):
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

def _relax_fk_for_tables(cr, tables, column='statement_line_id'):
    for table in tables:
      # 1) ensure nullable
      cr.execute("""          DO $$
          BEGIN
            IF EXISTS (
              SELECT 1 FROM information_schema.columns
              WHERE table_name = %s AND column_name = %s
            ) THEN
              EXECUTE format('ALTER TABLE %I ALTER COLUMN %I DROP NOT NULL', %s, %s);
            END IF;
          END$$;
      """, (table, column, table, column))
      # 2) drop any existing FK
      _drop_fk_on(cr, table, column)
      # 3) remove dangling refs
      cr.execute("""          UPDATE {table} r
          SET {col} = NULL
          WHERE {col} IS NOT NULL
            AND NOT EXISTS (
              SELECT 1 FROM account_bank_statement_line b WHERE b.id = r.{col}
            );
      """.format(table=table, col=column))
      # 4) recreate relaxed FK
      cr.execute("""          DO $$
          BEGIN
            IF EXISTS (
              SELECT 1 FROM information_schema.tables
              WHERE table_name = %s
            ) THEN
              EXECUTE format($SQL$
                ALTER TABLE %I
                ADD CONSTRAINT %I
                FOREIGN KEY (%I)
                REFERENCES account_bank_statement_line(id)
                ON DELETE SET NULL
                DEFERRABLE INITIALLY DEFERRED
              $SQL$, %s, %s, %s);
            END IF;
          END$$;
      """, (table, f"{table}_statement_line_id_fkey", column, table, f"{table}_statement_line_id_fkey", column))

def _repair_interco_fks(cr):
    tables = _tables_with_column(cr, 'statement_line_id', prefix='interco')
    if not tables:
        return
    _relax_fk_for_tables(cr, tables, 'statement_line_id')

def pre_init_hook(cr):
    _repair_interco_fks(cr)

def post_init_hook(cr, registry):
    _repair_interco_fks(cr)