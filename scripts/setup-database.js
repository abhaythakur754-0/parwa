/**
 * PARWA Database Setup Script
 * 
 * Run: node scripts/setup-database.js
 * 
 * This script connects to Supabase and creates all required tables
 * for the FlexPay onboarding + payment system.
 */

const https = require('https');

// Supabase connection info (from .env)
const SUPABASE_URL = 'https://fmpibdauppnzfisodkhp.supabase.co';
const SUPABASE_KEY = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImZtcGliZGF1cHBuemZpc29ka2hwIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc0NjQ5MjE3NCwiZXhwIjoyMDAyMDY4MTc0fQ.qBGnJkO4LWHtB7p7NBnS-6UQLkXjJvnvZ0wqYZGPJvI';

// SQL to execute
const fs = require('fs');
const path = require('path');
const sqlPath = path.join(__dirname, 'setup-supabase.sql');
const sql = fs.readFileSync(sqlPath, 'utf8');

async function setupDatabase() {
  console.log('🚀 Setting up PARWA database in Supabase...\n');
  
  try {
    // Execute SQL via Supabase REST API
    const response = await fetch(`${SUPABASE_URL}/rest/v1/rpc/exec_sql`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'apikey': SUPABASE_KEY,
        'Authorization': `Bearer ${SUPABASE_KEY}`,
        'Prefer': 'return=representation',
      },
      body: JSON.stringify({ sql_statement: sql }),
    });

    if (!response.ok) {
      const error = await response.text();
      console.error('❌ Error executing SQL:', error);
      
      // Fallback: Show instructions for manual execution
      console.log('\n⚠️  Automatic setup failed. Please run the SQL manually:');
      console.log(`📄 SQL file: ${sqlPath}`);
      console.log('🔗 Open: https://supabase.com/dashboard/project/fmpibdauppnzfisodkhp/sql\n');
      return false;
    }

    const result = await response.json();
    console.log('✅ Database setup complete!\n');
    console.log('Tables created:');
    console.log('  - onboarding_sessions');
    console.log('  - user_details');
    console.log('  - legal_consents');
    console.log('  - integrations');
    console.log('  - knowledge_bases');
    console.log('  - knowledge_documents');
    console.log('  - payments');
    console.log('  - subscriptions\n');
    
    return true;
  } catch (error) {
    console.error('❌ Setup failed:', error.message);
    return false;
  }
}

// Run if called directly
if (require.main === module) {
  setupDatabase().then(success => {
    process.exit(success ? 0 : 1);
  });
}

module.exports = { setupDatabase };
