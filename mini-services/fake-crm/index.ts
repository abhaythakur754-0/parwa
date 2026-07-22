/**
 * FakeCRM Server - ZAI Mini-Service
 * 
 * Mock CRM platform simulating HubSpot/Salesforce/Zendesk
 * For testing Parwa CRM Analyzer feature
 * 
 * Exposed via ZAI domain - accessible from internet!
 */

import { Hono } from 'hono';
import { cors } from 'hono/cors';
import { logger } from 'hono/logger';

const app = new Hono();
const PORT = 8888;

// Middleware
app.use('*', cors());
app.use('*', logger());

// ============================================================
// IN-MEMORY DATABASE (Realistic Fake Data)
// ============================================================

const DB = {
  contacts: [] as any[],
  companies: [] as any[],
  deals: [] as any[],
  tickets: [] as any[],
  orders: [] as any[],
  products: [] as any[],
  notes: [] as any[],
  oauthTokens: [] as any[],
  webhooks: [] as any[],
};

const CONNECTED_APPS: any[] = [];

// ============================================================
// DATA GENERATION
// ============================================================

const FIRST_NAMES = ["James", "Mary", "John", "Patricia", "Robert", "Jennifer", "Michael", "Linda", 
  "William", "Elizabeth", "David", "Barbara", "Richard", "Susan", "Joseph", "Jessica",
  "Thomas", "Sarah", "Charles", "Karen", "Christopher", "Nancy", "Daniel", "Lisa",
  "Matthew", "Betty", "Anthony", "Margaret", "Mark", "Sandra", "Donald", "Ashley"];

const LAST_NAMES = ["Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia", "Miller", "Davis",
  "Rodriguez", "Martinez", "Hernandez", "Lopez", "Gonzalez", "Wilson", "Anderson",
  "Thomas", "Taylor", "Moore", "Jackson", "Martin", "Lee", "Perez", "Thompson",
  "White", "Harris", "Sanchez", "Clark", "Ramirez", "Lewis", "Robinson", "Walker"];

const COMPANY_NAMES = ["TechCorp Inc", "Global Solutions Ltd", "InnovateTech", "DataDriven Co",
  "CloudSystems", "AI Dynamics", "NextGen Software", "Digital Frontier",
  "CyberSecure Corp", "FutureTech Industries", "SmartScale LLC", "Apex Digital",
  "Quantum Labs", "Pixel Perfect", "Streamline Services"];

const DOMAINS = ["techcorp.com", "globalsolutions.io", "innovatetech.co", "datadriven.net",
  "cloudsystems.com", "aidynamics.io", "nextgen.software", "digitalfrontier.tech",
  "cybersecurecorp.com", "futuretech.industries", "smartscale.llc", "apex.digital"];

const TITLES = ["CEO", "CTO", "CFO", "VP of Sales", "VP of Marketing", "Sales Director",
  "Marketing Manager", "Product Manager", "Engineering Lead", "Customer Success Manager",
  "Head of Operations", "Business Development Manager", "Account Executive",
  "Senior Developer", "DevOps Engineer", "Data Scientist"];

const INDUSTRIES = ["Technology", "SaaS", "E-commerce", "Healthcare", "Finance", "Education",
  "Manufacturing", "Retail", "Consulting", "Media & Entertainment"];

const TICKET_SUBJECTS = [
  "Unable to login to dashboard",
  "Feature request: Bulk export functionality",
  "Integration with Salesforce not working",
  "Billing discrepancy on invoice #4521",
  "How to set up automated workflows?",
  "API rate limiting issues",
  "Data sync delay between systems",
  "Custom field not appearing in reports",
  "SSO configuration help needed",
  "Performance degradation after update",
  "Mobile app crashes on iOS 17",
  "Webhook delivery failures",
  "User permission management questions",
  "Import failed - CSV format error",
  "Two-factor authentication problems"
];

const TICKET_STATUSES = ["new", "open", "pending", "waiting_on_customer", "resolved", "closed"];
const TICKET_PRIORITIES = ["low", "medium", "high", "urgent"];

const DEAL_NAMES = [
  "Enterprise License - Q4 2026",
  "Annual Subscription Renewal",
  "Professional Services Engagement",
  "API Integration Project",
  "Training & Onboarding Package",
  "White-label Partnership Deal",
  "Volume Discount Agreement",
  "Technical Support Contract",
  "Custom Development Work",
  "Data Migration Services"
];

const DEAL_STAGES = ["lead", "qualified", "proposal_sent", "negotiation", "closed_won", "closed_lost"];

const PRODUCT_NAMES = [
  "Pro Plan Monthly", "Enterprise Annual", "API Access Tier", 
  "Support Add-on", "Training Module", "Integration Pack",
  "Analytics Pro", "Security Suite", "Storage Extension", "User Seat"
];

function generateId(prefix: string): string {
  return `${prefix}-${Math.random().toString(36).substring(2, 10)}`;
}

function randomItem<T>(arr: T[]): T {
  return arr[Math.floor(Math.random() * arr.length)];
}

function randomInt(min: number, max: number): number {
  return Math.floor(Math.random() * (max - min + 1)) + min;
}

function randomDate(daysAgo: number): string {
  const date = new Date();
  date.setDate(date.getDate() - randomInt(0, daysAgo));
  return date.toISOString();
}

function generateFakeData(): void {
  // Generate Companies
  for (let i = 0; i < 15; i++) {
    DB.companies.push({
      id: generateId('company'),
      name: COMPANY_NAMES[i],
      domain: DOMAINS[i],
      industry: randomItem(INDUSTRIES),
      size: randomItem(["1-10", "11-50", "51-200", "201-500", "500+"]),
      revenue: `$${randomInt(1, 1000)}M`,
      phone: `+1-${randomInt(200, 999)}-${randomInt(100, 999)}-${randomInt(1000, 9999)}`,
      website: `https://${DOMAINS[i]}`,
      created_at: randomDate(365),
    });
  }

  // Generate Contacts
  for (let i = 0; i < 50; i++) {
    const company = DB.companies[i % DB.companies.length];
    DB.contacts.push({
      id: generateId('contact'),
      firstname: FIRST_NAMES[i % FIRST_NAMES.length],
      lastname: LAST_NAMES[i % LAST_NAMES.length],
      email: `${FIRST_NAMES[i % FIRST_NAMES.length].toLowerCase()}.${LAST_NAMES[i % LAST_NAMES.length].toLowerCase()}@${company.domain}`,
      phone: `+1-${randomInt(200, 999)}-${randomInt(100, 999)}-${randomInt(1000, 9999)}`,
      jobtitle: TITLES[i % TITLES.length],
      company: company.name,
      company_id: company.id,
      industry: company.industry,
      lifecyclestage: randomItem(["subscriber", "lead", "mql", "sql", "opportunity", "customer", "evangelist"]),
      lead_score: randomInt(0, 100),
      source: randomItem(["organic_search", "paid_search", "social_media", "referral", "email_campaign", "direct", "event"]),
      created_at: randomDate(365),
      updated_at: new Date().toISOString(),
    });
  }

  // Generate Deals
  for (let i = 0; i < 25; i++) {
    const contact = DB.contacts[i * 2 % DB.contacts.length];
    const company = DB.companies[i % DB.companies.length];
    const amount = randomItem([randomInt(500, 5000), randomInt(5000, 25000), randomInt(25000, 150000)]);
    
    DB.deals.push({
      id: `deal-${String(i + 1).padStart(5, '0')}`,
      dealname: DEAL_NAMES[i % DEAL_NAMES.length],
      dealstage: DEAL_STAGES[i % DEAL_STAGES.length],
      amount,
      currency: "USD",
      closedate: randomDate(-90 + randomInt(0, 270)),
      probability: [10, 20, 40, 60, 100, 0][i % 6],
      contact_id: contact.id,
      company_id: company.id,
      company_name: company.name,
      contact_name: `${contact.firstname} ${contact.lastname}`,
      created_at: randomDate(120),
      type: randomItem(["newbusiness", "existingbusiness", "upsell", "cross-sell"]),
    });
  }

  // Generate Tickets
  for (let i = 0; i < 35; i++) {
    const contact = Math.random() > 0.2 ? DB.contacts[i * 3 % DB.contacts.length] : null;
    const created = new Date(Date.now() - randomInt(0, 60) * 24 * 60 * 60 * 1000);
    const status = TICKET_STATUSES[randomInt(0, TICKET_STATUSES.length - 1)];
    
    let updated: Date;
    if (["resolved", "closed"].includes(status)) {
      updated = new Date(created.getTime() + randomInt(1, 168) * 60 * 60 * 1000);
    } else {
      updated = new Date();
    }
    
    DB.tickets.push({
      id: String(i + 1).padStart(6, '0'),
      subject: TICKET_SUBJECTS[i % TICKET_SUBJECTS.length],
      description: `Detailed description about: ${TICKET_SUBJECTS[i % TICKET_SUBJECTS.length].toLowerCase()}. Customer needs assistance.`,
      status,
      priority: randomItem(TICKET_PRIORITIES),
      type: randomItem(["question", "incident", "problem", "task", "feature_request"]),
      requester: contact ? {
        id: contact.id,
        name: `${contact.firstname} ${contact.lastname}`,
        email: contact.email,
      } : null,
      assignee: randomItem(["agent-smith", "agent-johnson", null]),
      group: randomItem(["support", "technical", "billing", null]),
      created_at: created.toISOString(),
      updated_at: updated.toISOString(),
      tags: ["urgent", "billing", "technical"].slice(0, randomInt(1, 3)),
      via: randomItem(["web", "email", "api", "chat"]),
    });
  }

  // Generate Orders
  for (let i = 0; i < 40; i++) {
    const contact = DB.contacts[i % DB.contacts.length];
    const company = DB.companies[i % DB.companies.length];
    const itemsCount = randomInt(1, 5);
    const itemPrice = randomItem([29, 49, 99, 199, 499, 999]);
    
    DB.orders.push({
      id: `ORD-${String(1000 + i).padStart(6, '0')}`,
      order_number: `ORD-${String(1000 + i).padStart(6, '0')}`,
      contact_id: contact.id,
      contact_name: `${contact.firstname} ${contact.lastname}`,
      contact_email: contact.email,
      company_id: company.id,
      company_name: company.name,
      status: randomItem(["pending", "processing", "shipped", "delivered", "cancelled", "refunded"]),
      subtotal: itemsCount * itemPrice,
      tax: Math.round(itemsCount * itemPrice * 0.08 * 100) / 100,
      discount: Math.random() > 0.6 ? Math.round(itemsCount * itemPrice * randomItem([0.1, 0.15, 0.2]) * 100) / 100 : 0,
      total: 0,
      currency: "USD",
      payment_method: randomItem(["credit_card", "paypal", "bank_transfer"]),
      payment_status: randomItem(["paid", "pending", "failed"]),
      created_at: randomDate(180),
      source: randomItem(["website", "mobile_app", "api", "phone"]),
    });
    // Calculate total
    DB.orders[DB.orders.length - 1].total = DB.orders[DB.orders.length - 1].subtotal + DB.orders[DB.orders.length - 1].tax - DB.orders[DB.orders.length - 1].discount;
  }

  // Generate Products
  for (let i = 0; i < PRODUCT_NAMES.length; i++) {
    DB.products.push({
      id: `prod-${String(i + 1).padStart(3, '0')}`,
      name: PRODUCT_NAMES[i],
      description: `Premium ${PRODUCT_NAMES[i]} offering with full features.`,
      price: [29, 49, 99, 199, 499, 999][i % 6],
      currency: "USD",
      category: randomItem(["subscription", "license", "service", "add-on"]),
      active: true,
    });
  }
}

// Initialize data
generateFakeData();

console.log('='.repeat(60));
console.log('  🎭 FAKECRM SERVER INITIALIZED');
console.log(`  📊 Data Generated:`);
console.log(`     • Companies: ${DB.companies.length}`);
console.log(`     • Contacts: ${DB.contacts.length}`);
console.log(`     • Deals: ${DB.deals.length}`);
console.log(`     • Tickets: ${DB.tickets.length}`);
console.log(`     • Orders: ${DB.orders.length}`);
console.log(`     • Products: ${DB.products.length}`);
console.log('='.repeat(60));

// ============================================================
// AUTHENTICATION HELPER
// ============================================================

function verifyToken(authorization: string | undefined): boolean {
  if (!authorization) {
    return false;
  }
  return authorization.startsWith('Bearer ');
}

// ============================================================
// API ROUTES
// ============================================================

// Health Check
app.get('/health', (c) => c.json({
  status: 'healthy',
  server: 'FakeCRM Test Server (ZAI Deployed)',
  version: '1.0.0-zai',
  timestamp: new Date().toISOString(),
  data_stats: {
    contacts: DB.contacts.length,
    companies: DB.companies.length,
    deals: DB.deals.length,
    tickets: DB.tickets.length,
    orders: DB.orders.length,
    products: DB.products.length,
    connected_apps: CONNECTED_APPS.length,
  },
  warning: 'THIS IS A TEST SERVER WITH FAKE DATA',
}));

// Root / Info
app.get('/', (c) => c.json({
  name: '🎭 FakeCRM Server',
  description: 'Mock CRM platform for testing Parwa integrations - DEPLOYED ON ZAI',
  version: '1.0.0-zai',
  status: 'running',
  purpose: 'TESTING ONLY - All data is fake',
  available_endpoints: {
    health: '/health',
    analytics: '/analytics/overview',
    contacts: '/crm/v3/objects/contacts',
    companies: '/crm/v3/objects/companies',
    deals: '/crm/v3/objects/deals',
    pipelines: '/crm/v3/pipelines/deals',
    tickets: '/api/v2/tickets',
    orders: '/admin/api/2024-01/orders.json',
    oauth_authorize: '/oauth/authorize',
  },
  test_credentials: {
    note: 'Any Bearer token works for testing',
    example_header: 'Authorization: Bearer test-token-123',
  },
  data_summary: {
    contacts: DB.contacts.length,
    companies: DB.companies.length,
    deals: DB.deals.length,
    tickets: DB.tickets.length,
    orders: DB.orders.length,
  },
}));

// Analytics Overview (CRM Analyzer reads this!)
app.get('/analytics/overview', (c) => {
  const auth = c.req.header('authorization');
  if (!verifyToken(auth)) {
    return c.json({ error: 'Authorization required' }, 401);
  }

  const totalDealValue = DB.deals.filter(d => d.dealstage !== 'closed_lost').reduce((sum, d) => sum + d.amount, 0);
  const wonDealValue = DB.deals.filter(d => d.dealstage === 'closed_won').reduce((sum, d) => sum + d.amount, 0);
  const openTickets = DB.tickets.filter(t => ['new', 'open', 'pending'].includes(t.status)).length;
  const totalOrdersValue = DB.orders.filter(o => ['delivered', 'shipped'].includes(o.status)).reduce((sum, o) => sum + o.total, 0);

  return c.json({
    summary: {
      total_contacts: DB.contacts.length,
      total_companies: DB.companies.length,
      total_deals: DB.deals.length,
      total_tickets: DB.tickets.length,
      total_orders: DB.orders.length,
      total_products: DB.products.length,
      total_pipeline_value: totalDealValue,
      won_deal_value: wonDealValue,
      avg_deal_size: Math.round(totalDealValue / DB.deals.length),
      open_tickets: openTickets,
      ticket_resolution_rate: (DB.tickets.filter(t => t.status === 'closed').length / DB.tickets.length).toFixed(2),
      total_revenue: Math.round(totalOrdersValue),
      active_webhooks: DB.webhooks.length,
      connected_apps: CONNECTED_APPS.length,
    },
    breakdown: {
      by_status: {
        tickets: Object.fromEntries(TICKET_STATUSES.map(s => [s, DB.tickets.filter(t => t.status === s).length])),
        deals: Object.fromEntries(DEAL_STAGES.map(s => [s, DB.deals.filter(d => d.dealstage === s).length])),
        orders: Object.fromEntries(['pending', 'processing', 'shipped', 'delivered', 'cancelled'].map(s => [s, DB.orders.filter(o => o.status === s).length])),
      },
      by_priority: Object.fromEntries(TICKET_PRIORITIES.map(p => [p, DB.tickets.filter(t => t.priority === p).length])),
      by_industry: Object.fromEntries(INDUSTRIES.map(ind => [ind, DB.contacts.filter(c => c.industry === ind).length])),
    },
    generated_at: new Date().toISOString(),
    data_freshness: 'realtime',
    server_info: {
      name: 'FakeCRM Test Server (ZAI)',
      version: '1.0.0-zai',
      purpose: 'Testing Only - All Data is Fake',
      deployed_via: 'ZAI Platform',
    },
  });
});

// Contacts API (HubSpot-style)
app.get('/crm/v3/objects/contacts', (c) => {
  const auth = c.req.header('authorization');
  if (!verifyToken(auth)) {
    return c.json({ error: 'Authorization required' }, 401);
  }

  const limit = parseInt(c.req.query('limit') || '100');
  const after = c.req.query('after');
  
  let contacts = DB.contacts;
  if (after) {
    const idx = contacts.findIndex(ct => ct.id === after);
    if (idx >= 0) contacts = contacts.slice(idx + 1);
  }
  
  const paginated = contacts.slice(0, limit);
  
  return c.json({
    results: paginated.map(contact => ({
      id: contact.id,
      properties: contact,
    })),
    paging: {
      next: paginated.length === limit && contacts.length > limit 
        ? { after: paginated[paginated.length - 1].id } 
        : null,
    },
  });
});

// Companies API
app.get('/crm/v3/objects/companies', (c) => {
  const auth = c.req.header('authorization');
  if (!verifyToken(auth)) {
    return c.json({ error: 'Authorization required' }, 401);
  }

  const limit = parseInt(c.req.query('limit') || '100');
  
  return c.json({
    results: DB.companies.slice(0, limit).map(company => ({
      id: company.id,
      properties: company,
    })),
    total: DB.companies.length,
  });
});

// Deals API
app.get('/crm/v3/objects/deals', (c) => {
  const auth = c.req.header('authorization');
  if (!verifyToken(auth)) {
    return c.json({ error: 'Authorization required' }, 401);
  }

  const limit = parseInt(c.req.query('limit') || '100');
  
  return c.json({
    results: DB.deals.slice(0, limit).map(deal => ({
      id: deal.id,
      properties: deal,
    })),
    total: DB.deals.length,
  });
});

// Pipelines API
app.get('/crm/v3/pipelines/deals', (c) => {
  const auth = c.req.header('authorization');
  if (!verifyToken(auth)) {
    return c.json({ error: 'Authorization required' }, 401);
  }

  return c.json({
    results: [{
      pipelineId: 'default',
      label: 'Sales Pipeline',
      stages: [
        { stageId: 'lead', label: 'Lead', metadata: { probability: 10 } },
        { stageId: 'qualified', label: 'Qualified', metadata: { probability: 20 } },
        { stageId: 'proposal_sent', label: 'Proposal Sent', metadata: { probability: 40 } },
        { stageId: 'negotiation', label: 'Negotiation', metadata: { probability: 60 } },
        { stageId: 'closed_won', label: 'Closed Won', metadata: { probability: 100 } },
        { stageId: 'closed_lost', label: 'Closed Lost', metadata: { probability: 0 } },
      ],
    }],
  });
});

// Tickets API (Zendesk-style)
app.get('/api/v2/tickets', (c) => {
  const auth = c.req.header('authorization');
  if (!verifyToken(auth)) {
    return c.json({ error: 'Authorization required' }, 401);
  }

  const perPage = parseInt(c.req.query('per_page') || '30');
  const page = parseInt(c.req.query('page') || '1');
  const statusFilter = c.req.query('status');
  
  let tickets = DB.tickets;
  if (statusFilter) {
    tickets = tickets.filter(t => t.status === statusFilter);
  }
  
  const start = (page - 1) * perPage;
  const paginated = tickets.slice(start, start + perPage);
  
  return c.json({
    tickets: paginated,
    count: tickets.length,
    next_page: start + perPage < tickets.length ? page + 1 : null,
  });
});

// Orders API (Shopify-style)
app.get('/admin/api/2024-01/orders.json', (c) => {
  const auth = c.req.header('authorization');
  if (!verifyToken(auth)) {
    return c.json({ error: 'Authorization required' }, 401);
  }

  const limit = parseInt(c.req.query('limit') || '50');
  const statusFilter = c.req.query('status');
  
  let orders = DB.orders;
  if (statusFilter) {
    orders = orders.filter(o => o.status === statusFilter);
  }
  
  return c.json({
    orders: orders.slice(0, limit),
    count: orders.length,
  });
});

// OAuth Authorize Page
app.get('/oauth/authorize', (c) => {
  const clientId = c.req.query('client_id') || '';
  const redirectUri = c.req.query('redirect_uri') || '';
  const state = c.req.query('state') || '';

  return c.html(`
<!DOCTYPE html>
<html>
<head>
    <title>FakeCRM - Connect Your Account</title>
    <style>
        body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; 
               background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); 
               min-height: 100vh; display: flex; align-items: center; justify-content: center; margin: 0; }
        .container { background: white; padding: 40px; border-radius: 12px; box-shadow: 0 20px 60px rgba(0,0,0,0.3); max-width: 450px; text-align: center; }
        .logo { font-size: 48px; margin-bottom: 20px; }
        h1 { color: #333; margin-bottom: 10px; }
        p { color: #666; margin-bottom: 30px; }
        .permissions { background: #f5f5f5; padding: 20px; border-radius: 8px; margin-bottom: 30px; text-align: left; }
        .permission-item { padding: 8px 0; border-bottom: 1px solid #e0e0e0; display: flex; align-items: center; gap: 10px; }
        .permission-icon { color: #4CAF50; }
        .btn { display: inline-block; padding: 14px 32px; font-size: 16px; border: none; border-radius: 6px; cursor: pointer; margin: 5px; text-decoration: none; color: white; }
        .btn-connect { background: #FF6B35; } 
        .btn-cancel { background: #e0e0e0; color: #666; }
        .info { font-size: 12px; color: #999; margin-top: 20px; }
    </style>
</head>
<body>
    <div class="container">
        <div class="logo">🎭</div>
        <h1>FakeCRM</h1>
        <p>Parwa wants to access your FakeCRM account</p>
        
        <div class="permissions">
            <strong>This application will be able to:</strong>
            <div class="permission-item">
                <span class="permission-icon">✓</span> Read your contacts
            </div>
            <div class="permission-item">
                <span class="permission-icon">✓</span> Read your deals/pipelines
            </div>
            <div class="permission-item">
                <span class="permission-icon">✓</span> Read your support tickets
            </div>
            <div class="permission-item">
                <span class="permission-icon">✓</span> Read your orders data
            </div>
            <div class="permission-item">
                <span class="permission-icon">✓</span> Create webhooks
            </div>
        </div>
        
        <a href="/oauth/approve?client_id=${clientId}&redirect_uri=${encodeURIComponent(redirectUri)}&state=${state}" class="btn btn-connect">
            ✨ Connect Account
        </a>
        <a href="/oauth/deny?redirect_uri=${encodeURIComponent(redirectUri)}&state=${state}" class="btn btn-cancel">
            Cancel
        </a>
        
        <div class="info">
            <p>This is a <strong>TEST ENVIRONMENT</strong> deployed on ZAI</p>
            <p>All data is fake and generated for testing purposes</p>
        </div>
    </div>
</body>
</html>
  `);
});

// OAuth Approve
app.get('/oauth/approve', async (c) => {
  const clientId = c.req.query('client_id') || '';
  const redirectUri = c.req.query('redirect_uri') || '';
  const state = c.req.query('state') || '';

  const authCode = `fake-auth-${Math.random().toString(36).substring(2, 18)}`;
  
  DB.oauthTokens.push({
    code: authCode,
    client_id: clientId,
    redirect_uri: redirectUri,
    created_at: new Date().toISOString(),
  });

  const separator = redirectUri.includes('?') ? '&' : '?';
  return c.redirect(`${redirectUri}${separator}code=${authCode}&state=${state}`);
});

// OAuth Deny
app.get('/oauth/deny', (c) => {
  const redirectUri = c.req.query('redirect_uri') || '';
  const state = c.req.query('state') || '';
  
  const separator = redirectUri.includes('?') ? '&' : '?';
  return c.redirect(`${redirectUri}${separator}error=access_denied&state=${state}`);
});

// Token Exchange
app.post('/oauth/token', async (c) => {
  const body = await c.req.json();
  const code = body.code;

  const validToken = DB.oauthTokens.find(t => t.code === code);
  if (!validToken) {
    return c.json({ error: 'Invalid authorization code' }, 400);
  }

  const accessToken = `fake-access-${Math.random().toString(36).substring(2, 34)}`;
  const refreshToken = `fake-refresh-${Math.random().toString(36).substring(2, 34)}`;

  CONNECTED_APPS.push({
    client_id: body.client_id,
    connected_at: new Date().toISOString(),
    access_token: accessToken,
  });

  return c.json({
    access_token: accessToken,
    token_type: 'bearer',
    expires_in: 3600,
    refresh_token: refreshToken,
    scope: 'contacts deals tickets orders webhooks read write',
  });
});

// Webhooks Subscribe
app.post('/webhooks/subscribe', async (c) => {
  const auth = c.req.header('authorization');
  if (!verifyToken(auth)) {
    return c.json({ error: 'Authorization required' }, 401);
  }

  const body = await c.req.json();
  const webhook = {
    id: `wh-${Math.random().toString(36).substring(2, 10)}`,
    url: body.url,
    events: body.events || [],
    created_at: new Date().toISOString(),
    status: 'active',
  };
  DB.webhooks.push(webhook);

  return c.json({ webhook }, 201);
});

// List Webhooks
app.get('/webhooks', (c) => {
  const auth = c.req.header('authorization');
  if (!verifyToken(auth)) {
    return c.json({ error: 'Authorization required' }, 401);
  }

  return c.json({ webhooks: DB.webhooks });
});

// Start server
console.log('\n🚀 Starting FakeCRM Server on port', PORT);
console.log('⚠️  FOR TESTING ONLY - All data is fake!');
console.log('🌐 DEPLOYED VIA ZAI - Accessible from internet!\n');

export default {
  port: PORT,
  fetch: app.fetch,
};
