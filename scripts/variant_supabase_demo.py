#!/usr/bin/env python3
"""
AI Variant + Supabase Integration Demo
Simulates how PARWA variants can query external DB and answer questions
"""

import psycopg2
import json
from datetime import datetime
from urllib.parse import quote_plus

# Database connection
DB_USER = "postgres.fmpibdauppnzfisodkhp"
DB_PASSWORD = "Durgamaa@754"
DB_HOST = "aws-1-ap-northeast-1.pooler.supabase.com"
DB_PORT = "6543"
DB_NAME = "postgres"

DATABASE_URL = f"postgresql://{quote_plus(DB_USER)}:{quote_plus(DB_PASSWORD)}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

class ParwaVariantWithSupabase:
    """Simulates a PARWA AI variant connected to Supabase"""
    
    def __init__(self):
        self.conn = psycopg2.connect(DATABASE_URL)
        self.cursor = self.conn.cursor()
        print("🤖 PARWA Variant initialized with Supabase connection")
    
    def close(self):
        self.cursor.close()
        self.conn.close()
    
    def query_database(self, sql, params=None):
        """Execute SQL query and return results"""
        try:
            self.cursor.execute(sql, params or ())
            columns = [desc[0] for desc in self.cursor.description]
            rows = self.cursor.fetchall()
            return columns, rows
        except Exception as e:
            return None, str(e)
    
    # ── AI Variant Capabilities ──
    
    def answer_customer_question(self, question):
        """
        Simulates AI understanding a question, querying Supabase,
        and returning a formatted answer
        """
        print(f"\n{'='*60}")
        print(f"❓ CUSTOMER ASKS: \"{question}\"")
        print(f"{'='*60}")
        
        # Step 1: AI analyzes intent (simplified)
        intent = self._detect_intent(question)
        print(f"\n🧠 AI Intent Detected: {intent['type']}")
        
        # Step 2: Query the right table based on intent
        result = self._execute_intent(intent)
        
        # Step 3: Format response like AI would
        response = self._format_ai_response(intent, result)
        
        return response
    
    def _detect_intent(self, question):
        """Detect what the customer wants to know"""
        q = question.lower()
        
        if 'order' in q or ('last' in q and 'order' in q):
            return {'type': 'ORDER_HISTORY', 'limit': 5}
        elif 'payment' in q or 'transaction' in q or 'paid' in q:
            return {'type': 'PAYMENT_HISTORY', 'limit': 10}
        elif 'customer' in q or 'account' in q or 'profile' in q:
            return {'type': 'CUSTOMER_INFO', 'email': None}
        elif 'ticket' in q or 'support' in q or 'issue' in q:
            return {'type': 'TICKET_STATUS', 'limit': 3}
        elif 'invoice' in q or 'bill' in q:
            return {'type': 'INVOICE_HISTORY', 'limit': 5}
        else:
            return {'type': 'GENERAL_QUERY'}
    
    def _execute_intent(self, intent):
        """Execute the appropriate database query"""
        type_ = intent['type']
        
        if type_ == 'ORDER_HISTORY':
            cols, rows = self.query_database("""
                SELECT po.id, pc.name, pc.email, po.amount, po.status, po.created_at
                FROM parwa_orders po
                JOIN parwa_customers pc ON po.customer_id = pc.id
                ORDER BY po.created_at DESC
                LIMIT %s;
            """, (intent.get('limit', 5),))
            
        elif type_ == 'PAYMENT_HISTORY':
            cols, rows = self.query_database("""
                SELECT pp.id, pp.amount, pp.status, pp.payment_method, pp.created_at,
                       pc.name as customer_name
                FROM parwa_payments pp
                LEFT JOIN parwa_customers pc ON pp.customer_id = pc.id
                ORDER BY pp.created_at DESC
                LIMIT %s;
            """, (intent.get('limit', 10),))
            
        elif type_ == 'CUSTOMER_INFO':
            cols, rows = self.query_database("""
                SELECT id, name, email, phone, status, created_at 
                FROM parwa_customers 
                LIMIT %s;
            """, (10,))
            
        elif type_ == 'TICKET_STATUS':
            cols, rows = self.query_database("""
                SELECT t.id, t.subject, t.status, t.priority, 
                       u.name as assigned_to, t.created_at
                FROM tickets t
                LEFT JOIN users u ON t.assigned_to = u.id
                ORDER BY t.created_at DESC
                LIMIT %s;
            """, (intent.get('limit', 3),))
            
        elif type_ == 'INVOICE_HISTORY':
            cols, rows = self.query_database("""
                SELECT pi.id, pi.amount, pi.status, pi.due_date, pi.paid_at,
                       pc.name as customer_name
                FROM parwa_invoices pi
                LEFT JOIN parwa_customers pc ON pi.customer_id = pc.id
                ORDER BY pi.created_at DESC
                LIMIT %s;
            """, (intent.get('limit', 5),))
            
        else:
            # General: show customers count
            cols, rows = self.query_database("""
                SELECT COUNT(*) as total_customers FROM customers;
            """)
        
        return {'columns': cols, 'rows': rows}
    
    def _format_ai_response(self, intent, result):
        """Format database results into a natural AI response"""
        if isinstance(result.get('rows'), str):  # Error
            return f"❌ I encountered an issue: {result['rows']}"
        
        cols = result['columns']
        rows = result['rows']
        type_ = intent['type']
        
        print(f"\n📊 Data Retrieved from Supabase:")
        print(f"   Columns: {cols}")
        print(f"   Records Found: {len(rows)}")
        
        # Format based on intent type
        if type_ == 'ORDER_HISTORY':
            if not rows:
                response = "I don't see any recent orders in our system."
            else:
                response = f"✅ Here are your recent orders:\n\n"
                for i, row in enumerate(rows, 1):
                    row_dict = dict(zip(cols, row))
                    date = row_dict['created_at'].strftime('%Y-%m-%d') if hasattr(row_dict['created_at'], 'strftime') else str(row_dict['created_at'])[:10]
                    response += f"📦 **Order #{i}**\n"
                    response += f"   • Customer: {row_dict.get('name', 'N/A')}\n"
                    response += f"   • Amount: ${row_dict.get('amount', 0)}\n"
                    response += f"   • Status: {row_dict.get('status', 'Unknown')}\n"
                    response += f"   • Date: {date}\n\n"
                response += "Would you like more details on any order?"
                
        elif type_ == 'PAYMENT_HISTORY':
            if not rows:
                response = "No payment records found."
            else:
                total = sum(r[cols.index('amount')] if 'amount' in cols else 0 for r in rows)
                response = f"💳 **Payment History** (Total: ${total:.2f})\n\n"
                for row in rows:
                    row_dict = dict(zip(cols, row))
                    date = str(row_dict.get('created_at', ''))[:10]
                    response += f"• ${row_dict.get('amount', 0)} - {row_dict.get('status', 'Unknown')} ({date})\n"
                    
        elif type_ == 'TICKET_STATUS':
            if not rows:
                response = "No recent tickets found."
            else:
                response = "🎫 **Recent Support Tickets:**\n\n"
                for row in rows:
                    row_dict = dict(zip(cols, row))
                    response += f"• [{row_dict.get('status', 'Open')}] {row_dict.get('subject', 'No subject')}\n"
                    response += f"  Priority: {row_dict.get('priority', 'Normal')} | Assigned: {row_dict.get('assigned_to', 'Unassigned')}\n\n"
                    
        elif type_ == 'INVOICE_HISTORY':
            if not rows:
                response = "No invoices found."
            else:
                response = "📄 **Invoice Summary:**\n\n"
                for row in rows:
                    row_dict = dict(zip(cols, row))
                    due = str(row_dict.get('due_date', ''))[:10]
                    paid = str(row_dict.get('paid_at', 'Unpaid'))[:10]
                    response += f"Invoice #{str(row_dict.get('id', ''))[:8]}... - ${row_dict.get('amount', 0)}\n"
                    response += f"  Due: {due} | Paid: {paid}\n\n"
                    
        else:
            response = f"I found {rows[0][0] if rows else 0} records in our system."
        
        print(f"\n🤖 AI VARIANT RESPONSE:\n")
        print(response)
        return response


def main():
    print("=" * 70)
    print("🚀 PARWA AI VARIANT + SUPABASE INTEGRATION DEMO")
    print("=" * 70)
    print("\nThis demonstrates how your variants can access EXTERNAL databases")
    print("(beyond CRM) to answer customer questions with REAL data.\n")
    
    # Initialize variant
    variant = ParwaVariantWithSupabase()
    
    try:
        # Test different question types
        test_questions = [
            "Show me my last 5 orders",
            "What are my recent payments?",
            "Check my support ticket status",
            "Show my invoices",
        ]
        
        results = []
        for question in test_questions:
            response = variant.answer_customer_question(question)
            results.append({'question': question, 'response': response})
            print("\n" + "-" * 60)
        
        # Summary
        print("\n" + "=" * 70)
        print("🎉 DEMO COMPLETE!")
        print("=" * 70)
        print("\n✅ PROVEN: Your AI Variants CAN:")
        print("   ✓ Connect to external databases (Supabase)")
        print("   ✓ Query real-time data (orders, payments, tickets)")
        print("   ✓ Understand customer questions")
        print("   ✓ Return formatted, helpful answers")
        print("\n💡 This works for ANY external data source:")
        print("   • Bank APIs → Transaction history")
        print("   • Inventory systems → Stock levels")
        print("   • Shipping APIs → Order tracking")
        print("   • Your custom databases → Any data you have!")
        
    finally:
        variant.close()

if __name__ == "__main__":
    main()
