"""
One-time migration script: copies all existing rows from your local
gaper_agent.db (SQLite) into your Turso database.

Uses the raw `libsql` client (not the sqlalchemy-libsql dialect), so it
works even though sqlalchemy-libsql/libsql-experimental failed to build
locally on Windows - `libsql` itself installed fine as a prebuilt wheel.

Run this locally, AFTER you have added TURSO_DATABASE_URL and
TURSO_AUTH_TOKEN to your .env file (uncomment them just for this run).

Usage:
    python migrate_to_turso.py

Safe to re-run: it skips rows whose id already exists on Turso.
"""
import os
import sys
import sqlite3
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

import libsql

BASE_DIR = Path(__file__).resolve().parent

OLD_DB_PATH = os.getenv("DB_PATH", str(BASE_DIR / "gaper_agent.db"))
TURSO_URL = os.environ.get("TURSO_DATABASE_URL")
TURSO_TOKEN = os.environ.get("TURSO_AUTH_TOKEN")

if not TURSO_URL or not TURSO_TOKEN:
    print("ERROR: TURSO_DATABASE_URL and TURSO_AUTH_TOKEN must be set in .env before running this script.")
    sys.exit(1)

if not Path(OLD_DB_PATH).exists():
    print(f"ERROR: Old database file not found at {OLD_DB_PATH}")
    sys.exit(1)

print(f"Old SQLite DB: {OLD_DB_PATH}")
print(f"Turso target: {TURSO_URL}")

TABLES = [
    "thread_memory", "platform_config", "guidelines_cache",
    "listing_opportunity", "article_draft", "brand_profile",
    "posted_backlink", "case_study",
]

# --- Source: old local SQLite (raw sqlite3, no SQLAlchemy needed here) ---
old_conn = sqlite3.connect(OLD_DB_PATH)
old_conn.row_factory = sqlite3.Row

# --- Destination: Turso (raw libsql client) ---
turso_conn = libsql.connect("turso.db", sync_url=TURSO_URL, auth_token=TURSO_TOKEN)
turso_conn.sync()

total_copied = 0
total_skipped = 0

for table in TABLES:
    try:
        rows = old_conn.execute(f"SELECT * FROM {table}").fetchall()
    except sqlite3.OperationalError:
        print(f"{table}: not found in old DB, skipping")
        continue

    copied = 0
    skipped = 0
    print(f"{table}: found {len(rows)} rows in old DB, starting...")

    for i, row in enumerate(rows, start=1):
        row_dict = dict(row)
        row_id = row_dict.get("id")

        existing = turso_conn.execute(f"SELECT id FROM {table} WHERE id = ?", (row_id,)).fetchall()
        if existing:
            skipped += 1
            continue

        columns = list(row_dict.keys())
        placeholders = ", ".join(["?"] * len(columns))
        col_names = ", ".join(columns)
        values = [row_dict[c] for c in columns]

        turso_conn.execute(
            f"INSERT INTO {table} ({col_names}) VALUES ({placeholders})",
            values,
        )
        copied += 1
        if i % 10 == 0:
            print(f"  ... {i}/{len(rows)} rows processed")

    turso_conn.commit()
    print(f"{table}: copied {copied}, skipped {skipped} (already existed)")
    total_copied += copied
    total_skipped += skipped

old_conn.close()

print(f"\nDone. Total copied: {total_copied}, total skipped: {total_skipped}")