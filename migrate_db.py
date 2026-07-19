

"""
Run this ONCE from your project root:
    python migrate_db.py

Adds newly-added columns to your EXISTING gaper_agent.db without wiping
any data. SQLAlchemy's create_all() only creates brand-new tables - it
never alters a table that already exists, which is why link_status,
last_checked_at, and posted_url were missing after the database.py updates.
Safe to run multiple times - it skips any column that's already there.
"""
import sqlite3
import config

MIGRATIONS = [
    ("posted_backlink", "link_status", "TEXT DEFAULT 'unchecked'"),
    ("posted_backlink", "link_check_status", "TEXT DEFAULT 'unchecked'"),
    ("posted_backlink", "last_checked_at", "DATETIME"),
    ("posted_backlink", "follow_up_due_at", "DATETIME"),
    ("posted_backlink", "is_ghost", "BOOLEAN DEFAULT 0"),
    ("article_draft", "is_ghost", "BOOLEAN DEFAULT 0"),
    ("listing_opportunity", "posted_url", "VARCHAR(500)"),
    ("listing_opportunity", "relevance_score", "INTEGER DEFAULT 0"),
]


def column_exists(cursor, table, column):
    cursor.execute(f"PRAGMA table_info({table})")
    return any(row[1] == column for row in cursor.fetchall())


def main():
    conn = sqlite3.connect(config.DB_PATH)
    cursor = conn.cursor()

    for table, column, col_type in MIGRATIONS:
        # Skip tables that don't exist yet (e.g. fresh DB, init_db will make them correctly)
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table,))
        if not cursor.fetchone():
            print(f"  Table '{table}' doesn't exist yet - skipping (init_db will create it correctly).")
            continue

        if column_exists(cursor, table, column):
            print(f"  ✓ {table}.{column} already exists - skipping.")
            continue

        print(f"  + Adding {table}.{column} ({col_type})...")
        cursor.execute(f"ALTER TABLE {table} ADD COLUMN {column} {col_type}")

    conn.commit()
    conn.close()
    print("\n✅ Migration complete. No data was lost.")


if __name__ == "__main__":
    print(f"Migrating database: {config.DB_PATH}\n")
    main()