#!/usr/bin/env python3
"""
PRODUCTION DATABASE AUDIT - List ALL tables and data that needs cleanup
"""

import psycopg2
from datetime import datetime

DB_CONFIG = {
    'host': 'aws-1-ap-northeast-1.pooler.supabase.com',
    'port': 6543,
    'database': 'postgres',
    'user': 'postgres.fmpibdauppnzfisodkhp',
    'password': 'Durgamaa@754'
}

print("=" * 80)
print("🔍 PRODUCTION DATABASE COMPLETE AUDIT")
print(f"   Time: {datetime.now().isoformat()}")
print("=" * 80)

try:
    conn = psycopg2.connect(**DB_CONFIG)
    conn.autocommit = True
    cur = conn.cursor()
    
    # ══════════════════════════════════════════════════════════════════
    # 1. GET ALL TABLES
    # ══════════════════════════════════════════════════════════════════
    print("\n" + "╔" + "═" * 78 + "╗")
    print("║" + "  📊 ALL TABLES IN DATABASE".center(76) + "║")
    print("╚" + "═" * 78 + "╝\n")
    
    cur.execute("""
        SELECT table_name, 
               (SELECT count(*) FROM information_schema.columns 
                WHERE table_name = t.table_name) as column_count
        FROM information_schema.tables t
        WHERE table_schema = 'public'
        ORDER BY table_name;
    """)
    
    tables = cur.fetchall()
    
    print(f"{'Table Name':<45} {'Columns':>10} {'Row Count':>15} {'Size Est.':>12}")
    print("-" * 82)
    
    table_data = []
    for table_name, col_count in tables:
        try:
            cur.execute(f'SELECT COUNT(*) FROM "{table_name}"')
            row_count = cur.fetchone()[0]
            
            # Estimate size (rough)
            if row_count > 0:
                cur.execute(f"""
                    SELECT pg_total_relation_size('{table_name}') 
                """)
                size_bytes = cur.fetchone()[0] if cur.fetchone() else 0
                # Re-query since fetchone consumed it
                cur.execute(f"SELECT pg_total_relation_size('{table_name}')")
                size_bytes = cur.fetchone()[0]
                
                if size_bytes > 1024*1024:
                    size_str = f"{size_bytes/(1024*1024):.1f}MB"
                elif size_bytes > 1024:
                    size_str = f"{size_bytes/1024:.1f}KB"
                else:
                    size_str = f"{size_bytes}B"
            else:
                size_str = "0B"
            
            table_data.append({
                'name': table_name,
                'columns': col_count,
                'rows': row_count,
                'size': size_str
            })
            
            print(f"{table_name:<45} {col_count:>10} {row_count:>15,} {size_str:>12}")
            
        except Exception as e:
            print(f"{table_name:<45} {col_count:>10} {'ERROR':>15} {'N/A':>12}")
            table_data.append({
                'name': table_name,
                'columns': col_count,
                'rows': -1,
                'size': 'ERROR'
            })
    
    print("\n" + "-" * 82)
    total_tables = len([t for t in table_data if t['rows'] >= 0])
    total_rows = sum(t['rows'] for t in table_data if t['rows'] > 0)
    print(f"TOTAL: {total_tables} tables | ~{total_rows:,} rows\n")
    
    # ══════════════════════════════════════════════════════════════════
    # 2. ANALYZE EACH TABLE FOR CLEANUP NEEDS
    # ══════════════════════════════════════════════════════════════════
    print("\n" + "╔" + "═" * 78 + "╗")
    print("║" + "  🗑️  CLEANUP ANALYSIS - What needs automatic deletion?".center(76) + "║")
    print("╚" + "═" * 78 + "╝\n")
    
    # Categorize tables by cleanup need
    cleanup_categories = {
        'TEMPORARY/Ephemeral Data (Should be cleaned quickly)': {
            'tables': [],
            'suggested_retention': '15 min - 24 hours',
            'reason': 'Short-lived data, no long-term value'
        },
        'LOG/Audit Data (Keep for compliance then clean)': {
            'tables': [],
            'suggested_retention': '7 - 90 days',
            'reason': 'Useful for debugging but grows fast'
        },
        'USER DATA (Keep active, clean old/resolved)': {
            'tables': [],
            'suggested_retention': '30 - 90 days',
            'reason': 'Active data needed, old resolved data can go'
        },
        'CORE/Persistent Data (NEVER auto-delete!)': {
            'tables': [],
            'suggested_retention': 'FOREVER',
            'reason': 'Critical business data - keep indefinitely'
        },
        'SYSTEM/Metadata Tables (No cleanup needed)': {
            'tables': [],
            'suggested_retention': 'N/A',
            'reason': 'Small metadata, system managed'
        }
    }
    
    # Analyze each table
    for t in table_data:
        name = t['name'].lower()
        
        # OTP / Verification codes - TEMPORARY
        if any(x in name for x in ['otp', 'verification_code', 'reset_token', 'session_token']):
            cleanup_categories['TEMPORARY/Ephemeral Data (Should be cleaned quickly)']['tables'].append(t)
            
        # Demo / Trial data - TEMPORARY to SHORT-TERM
        elif any(x in name for x in ['demo', 'trial', 'temp']):
            cleanup_categories['TEMPORARY/Ephemeral Data (Should be cleaned quickly)']['tables'].append(t)
            
        # Safety confirmations - TEMPORARY
        elif 'safety_confirmation' in name:
            cleanup_categories['TEMPORARY/Ephemeral Data (Should be cleaned quickly)']['tables'].append(t)
            
        # Logs / Events / History - LOG DATA
        elif any(x in name for x in ['log', 'event', 'history', 'audit', 'trail']):
            cleanup_categories['LOG/Audit Data (Keep for compliance then clean)']['tables'].append(t)
            
        # Tickets / Messages / Notes - USER DATA
        elif any(x in name for x in ['ticket', 'message', 'note', 'chat']):
            cleanup_categories['USER DATA (Keep active, clean old/resolved)']['tables'].append(t)
            
        # Payment failures - USER DATA
        elif 'payment_failure' in name:
            cleanup_categories['USER DATA (Keep active, clean old/resolved)']['tables'].append(t)
            
        # Core business data - PERSISTENT
        elif any(x in name for x in ['user', 'company', 'agent', 'customer', 'account', 'integration', 'subscription', 'plan', 'kb_', 'document', 'knowledge']):
            cleanup_categories['CORE/Persistent Data (NEVER auto-delete!)']['tables'].append(t)
            
        # System/metadata - NO CLEANUP NEEDED
        else:
            cleanup_categories['SYSTEM/Metadata Tables (No cleanup needed)']['tables'].append(t)
    
    # Print analysis
    for category, info in cleanup_categories.items():
        print(f"\n{'📌 ' + category:^78}")
        print("-" * 78)
        print(f"   Suggested Retention: {info['suggested_retention']}")
        print(f"   Reason: {info['reason']}")
        print(f"\n   Tables:")
        
        if info['tables']:
            for t in info['tables']:
                status_icon = "⚠️" if t['rows'] > 1000 else "✅"
                print(f"     {status_icon} {t['name']:<42} {t['rows']:>10,} rows  {t['size']}")
        else:
            print("     (none)")
    
    # ══════════════════════════════════════════════════════════════════
    # 3. SPECIFIC RECOMMENDATIONS
    # ══════════════════════════════════════════════════════════════════
    print("\n\n" + "╔" + "═" * 78 + "╗")
    print("║" + "  📋 RECOMMENDED CLEANUP SCHEDULE".center(76) + "║")
    print("╚" + "═" * 78 + "╝\n")
    
    recommendations = [
        ("phone_otp", "15 minutes", "UNVERIFIED only", "HIGH", "Security risk if left"),
        ("business_email_otp", "15 minutes", "UNVERIFIED only", "HIGH", "Security risk if left"),
        ("jarvis_safety_confirmations", "Immediate mark expired", "Delete after 7 days", "MEDIUM", "Already have cleanup"),
        ("demo_usage_events", "30 days", "All old events", "LOW", "Demo tracking only"),
        ("demo_usage_sessions", "60 days", "Expired/inactive only", "LOW", "Demo tracking only"),
        ("tickets (resolved/closed)", "30 days", "RESOLVED/CLOSED only", "MEDIUM", "Already have cleanup"),
        ("ticket_messages", "60 days", "Orphaned messages", "MEDIUM", "Already have cleanup"),
        ("payment_failures (resolved)", "90 days", "RESOLVED only", "LOW", "Already have cleanup"),
        ("audit_trail", "90 days", "Old entries", "LOW", "Optional - for compliance"),
        ("agent_config_history", "180 days", "Old versions", "LOW", "Keep recent history"),
    ]
    
    print(f"{'Table':<30} {'Retention':<20} {'Scope':<22} {'Priority'}")
    print("-" * 85)
    for table, retention, scope, priority, note in recommendations:
        priority_icon = "🔴" if priority == "HIGH" else "🟡" if priority == "MEDIUM" else "🟢"
        print(f"{priority_icon} {table:<28} {retention:<20} {scope:<22}")
    
    print("\n" + "=" * 80)
    print("✅ AUDIT COMPLETE - Ready to implement cleanup functions!")
    print("=" * 80)
    
    cur.close()
    conn.close()

except Exception as e:
    print(f"\n❌ ERROR: {e}")
    import traceback
    traceback.print_exc()
