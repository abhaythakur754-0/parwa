import urllib.parse, psycopg2

PW = "Durgamaa@754"
PW_ENC = urllib.parse.quote(PW)
CONN = f"postgresql://postgres.fmpibdauppnzfisodkhp:{PW_ENC}@aws-1-ap-northeast-1.pooler.supabase.com:6543/postgres"

conn = psycopg2.connect(CONN)
cur = conn.cursor()
cur.execute("""
SELECT column_name, data_type, is_nullable, column_default
FROM information_schema.columns
WHERE table_name='ai_agent_assignments'
ORDER BY ordinal_position;
""")
print("== ai_agent_assignments columns ==")
for r in cur.fetchall():
    print(r)

print("\n== ai_wiki_entries exists? ==")
cur.execute("""
SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name='ai_wiki_entries');
""")
print(cur.fetchone())

cur.execute("SELECT COUNT(*) FROM ai_agent_assignments;")
print("\nagent_assignments row count:", cur.fetchone()[0])

cur.execute("SELECT id, company_id, agent_name FROM ai_agent_assignments ORDER BY created_at DESC LIMIT 5;")
print("\nlast 5 agents:")
for r in cur.fetchall():
    print(r)

conn.close()
