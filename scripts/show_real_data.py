#!/usr/bin/env python3
"""
Show real data from Supabase - What AI Variant sees (Fixed)
"""

import psycopg2
import json
from urllib.parse import quote_plus

DB_USER = "postgres.fmpibdauppnzfisodkhp"
DB_PASSWORD = "Durgamaa@754"
DB_HOST = "aws-1-ap-northeast-1.pooler.supabase.com"
DB_PORT = "6543"
DB_NAME = "postgres"

DATABASE_URL = f"postgresql://{quote_plus(DB_USER)}:{quote_plus(DB_PASSWORD)}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

def show_data():
    conn = psycopg2.connect(DATABASE_URL)
    cursor = conn.cursor()
    
    print("=" * 70)
    print("📊 YOUR SUPABASE DATA - What AI Variants Can Access")
    print("=" * 70)
    
    # 1. PARWA Customers
    print("\n[1] 🧑‍💼 PARWA CUSTOMERS:")
    print("-" * 50)
    cursor.execute("SELECT id, name, email, company, lifetime_value FROM parwa_customers;")
    for row in cursor.fetchall():
        print(f"   Name: {row[1]} | Email: {row[2]} | Company: {row[3]} | LTV: ${row[4]}")
    
    # 2. PARWA Orders  
    print("\n[2] 📦 PARWA ORDERS:")
    print("-" * 50)
    cursor.execute("""
        SELECT po.id, pc.name, po.total_price, po.financial_status, po.fulfillment_status, po.created_at 
        FROM parwa_orders po 
        LEFT JOIN parwa_customers pc ON po.customer_id = pc.id;
    """)
    for row in cursor.fetchall():
        print(f"   Customer: {row[1]} | Amount: ${row[2]} | Financial: {row[3]} | Fulfillment: {row[4]}")
    
    # 3. PARWA Payments
    print("\n[3] 💳 PARWA PAYMENTS:")
    print("-" * 50)
    cursor.execute("""
        SELECT pp.id, pp.amount, pp.status, pp.method, pp.created_at,
               pc.name as customer_name
        FROM parwa_payments pp
        LEFT JOIN parwa_customers pc ON pp.customer_id = pc.id;
    """)
    for row in cursor.fetchall():
        print(f"   ${row[1]} | Status: {row[2]} | Method: {row[3]} | Customer: {row[5]}")
    
    # 4. PARWA Invoices
    print("\n[4] 📄 PARWA INVOICES:")
    print("-" * 50)
    cursor.execute("""
        SELECT pi.id, pi.amount, pi.status, pi.customer_email, pi.created_at
        FROM parwa_invoices pi;
    """)
    for row in cursor.fetchall():
        print(f"   ${row[1]} | Status: {row[2]} | Email: {row[3]} | Date: {row[4]}")
    
    # 5. Sample Tickets
    print("\n[5] 🎫 SAMPLE TICKETS (from CRM):")
    print("-" * 50)
    cursor.execute("""
        SELECT t.id, t.subject, t.status, t.priority, u.name as agent
        FROM tickets t
        LEFT JOIN users u ON t.assigned_to = u.id
        LIMIT 5;
    """)
    for row in cursor.fetchall():
        subject = str(row[1])[:40] if row[1] else 'N/A'
        print(f"   [{row[2]}] P{row[3]} | {subject}... | Agent: {row[4]}")
    
    # 6. REST Connectors (for external APIs)
    print("\n[6] 🔌 REST CONNECTORS (External API Integrations):")
    print("-" * 50)
    cursor.execute("SELECT id, name, base_url, auth_type FROM rest_connectors;")
    for row in cursor.fetchall():
        print(f"   {row[1]} → {row[2][:50]}... (Auth: {row[3]})")
    
    cursor.close()
    conn.close()
    
    print("\n" + "=" * 70)
    print("✅ ALL DATA ACCESSIBLE BY YOUR AI VARIANTS!")
    print("=" * 70)

if __name__ == "__main__":
    show_data()
