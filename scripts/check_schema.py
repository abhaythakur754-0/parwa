#!/usr/bin/env python3
"""Quick schema checker - get actual column names for all tables we need"""

import psycopg2
from urllib.parse import quote_plus

DB_USER = "postgres.fmpibdauppnzfisodkhp"
DB_PASSWORD = "Durgamaa@754"
DB_HOST = "aws-1-ap-northeast-1.pooler.supabase.com"
DB_PORT = "6543"
DB_NAME = "postgres"

encoded_password = quote_plus(DB_PASSWORD)
conn_str = f"postgresql://{DB_USER}:{encoded_password}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

conn = psycopg2.connect(conn_str)
cur = conn.cursor()

tables_to_check = [
    'companies',
    'customers', 
    'tickets',
    'ticket_messages',
    'parwa_orders',
    'parwa_payments',
    'parwa_invoices',
    'knowledge_base'
]

for table in tables_to_check:
    print(f"\n{'='*60}")
    print(f"TABLE: {table}")
    print('='*60)
    try:
        cur.execute("""
            SELECT column_name, data_type, is_nullable, column_default
            FROM information_schema.columns 
            WHERE table_name = %s 
            ORDER BY ordinal_position
        """, (table,))
        rows = cur.fetchall()
        if rows:
            for row in rows:
                nullable = "NULL" if row[2] == "YES" else "NOT NULL"
                default = f" DEFAULT {row[3]}" if row[3] else ""
                print(f"  {row[0]:30} | {row[1]:20} | {nullable:6}{default}")
        else:
            print("  Table not found or no columns")
    except Exception as e:
        print(f"  Error: {e}")

cur.close()
conn.close()
