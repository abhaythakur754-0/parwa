import pytest
import sqlite3 # Just for syntax checks if needed, but we prefer checking the file content here
import os

def test_rls_sql_syntax_and_completeness():
    """
    Verifies that the RLS SQL script exists and contains policies for all required tables.
    """
    sql_path = "security/rls_policies.sql"
    assert os.path.exists(sql_path), f"File {sql_path} does not exist"
    
    with open(sql_path, "r", encoding="utf-8") as f:
        content = f.read().lower()
        
    required_tables = [
        "companies", 
        "users", 
        "licenses", 
        "subscriptions", 
        "support_tickets", 
        "audit_trails"
    ]
    
    for table in required_tables:
        assert f"alter table {table} enable row level security" in content, f"RLS not enabled for {table}"
        assert f"create policy" in content and f"on {table}" in content, f"Policy not defined for {table}"
        assert "app.current_company_id" in content, "Session variable 'app.current_company_id' not found in script"

def test_rls_logic_separation():
    """
    Verifies that the logic correctly distinguishes between self-referencing (companies) 
    and company_id referencing tables.
    """
    sql_path = "security/rls_policies.sql"
    with open(sql_path, "r", encoding="utf-8") as f:
        content = f.read()
        
    # Check companies use 'id'
    assert "CREATE POLICY company_isolation_policy ON companies" in content
    assert "USING (id = current_setting" in content
    
    # Check others use 'company_id'
    assert "ON users" in content
    assert "USING (company_id = current_setting" in content
