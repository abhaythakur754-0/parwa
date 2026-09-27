#!/usr/bin/env python3
"""
Supabase Connection Test Script
Tests connection to user's Supabase database and lists available tables/data
"""

import psycopg2
import json

# Database connection string from user
DATABASE_URL = "postgresql://postgres.fmpibdauppnzfisodkhp:Durgamaa@754@aws-1-ap-northeast-1.pooler.supabase.com:6543/postgres"

def test_connection():
    """Test database connection and list tables"""
    print("=" * 60)
    print("🔌 SUPABASE CONNECTION TEST")
    print("=" * 60)
    
    try:
        # Connect to the database
        print("\n[1/4] Connecting to Supabase...")
        conn = psycopg2.connect(DATABASE_URL)
        cursor = conn.cursor()
        print("✅ Connection successful!")
        
        # Get database info
        print("\n[2/4] Getting database info...")
        cursor.execute("SELECT version();")
        version = cursor.fetchone()[0]
        print(f"📊 PostgreSQL Version: {version.split(',')[0]}")
        
        # List all tables
        print("\n[3/4] Listing all tables...")
        cursor.execute("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public' 
            ORDER BY table_name;
        """)
        tables = [row[0] for row in cursor.fetchall()]
        
        if not tables:
            print("⚠️  No public tables found")
        else:
            print(f"📋 Found {len(tables)} tables:")
            for i, table in enumerate(tables, 1):
                # Get row count for each table
                cursor.execute(f'SELECT COUNT(*) FROM "{table}";')
                count = cursor.fetchone()[0]
                print(f"   {i}. {table} ({count} rows)")
        
        # Sample data from each table
        print("\n[4/4] Sampling data from each table...")
        for table in tables[:5]:  # Limit to first 5 tables
            try:
                cursor.execute(f'SELECT * FROM "{table}" LIMIT 2;')
                columns = [desc[0] for desc in cursor.description]
                rows = cursor.fetchall()
                
                print(f"\n📦 Table: {table}")
                print(f"   Columns: {columns}")
                
                if rows:
                    for row in rows:
                        row_dict = dict(zip(columns, row))
                        # Truncate long values
                        truncated = {k: str(v)[:50] + '...' if len(str(v)) > 50 else v 
                                    for k, v in row_dict.items()}
                        print(f"   Sample: {json.dumps(truncated, default=str)}")
                else:
                    print("   (empty table)")
                    
            except Exception as e:
                print(f"   ⚠️  Error reading {table}: {e}")
        
        # Close connection
        cursor.close()
        conn.close()
        print("\n" + "=" * 60)
        print("✅ TEST COMPLETE - Connection working!")
        print("=" * 60)
        
        return tables
        
    except Exception as e:
        print(f"\n❌ CONNECTION FAILED!")
        print(f"Error: {e}")
        return []

if __name__ == "__main__":
    tables = test_connection()
    
    if tables:
        print(f"\n🎉 SUCCESS! Your variants can access these tables:")
        for t in tables:
            print(f"   • {t}")
