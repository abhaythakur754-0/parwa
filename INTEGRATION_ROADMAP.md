# PARWA Integration Part — Production Roadmap

> Last Updated: 2026-06-10 (Discussion Round 5 — 15 Gaps Resolved)
> Status: DISCUSSION PHASE — Do not start coding until all decisions are finalized
> Owner: Abhay + Z AI Assistant

---

## DECISIONS MADE (Locked)

### D1: Industries = 4 Only
- SaaS
- E-commerce
- Logistics
- Other (shows ALL integrations, no filtering)

### D2: Integrations = Unlimited Per Variant
- Mini PARWA, PARWA, PARWA High — ALL can connect unlimited integrations
- The difference is AI BRAIN POWER (pipeline steps, techniques), not plumbing
- Custom API connector: PARWA and PARWA High only
- OpenAPI Import: PARWA High only

### D3: Voice = Both Options
- Option A: Use Parwa's number (click "Enable Voice" → instant number with our Twilio)
- Option B: Bring their own number (forward existing number → Parwa AI answers)
- Both options include: Caller ID name field, greeting style, language preference
- Twilio is primarily OUR infrastructure, but clients CAN bring their own

### D4: Universal Integration Architecture
- Tier 1: Pre-built connectors (HubSpot, Shopify, etc.) — one-click, enter API key
- Tier 2: OpenAPI Importer (client provides API docs URL, AI generates connector) — PARWA High only
- Tier 3: Custom REST Connector (client defines base URL, auth, actions manually) — PARWA and PARWA High
- No client is ever turned away because their tool isn't supported

### D5: Variant Differences = AI Power, Not Integration Access

| Feature | Mini PARWA | PARWA | PARWA High |
|---------|-----------|-------|------------|
| Integrations | Unlimited | Unlimited | Unlimited |
| AI Pipeline | 3-step | 6-step | 9-step |
| AI Techniques | Tier 1 only | Tier 1+2 | Tier 1+2+3 |
| What AI does | Answer questions, look up info | Take actions (refunds, updates, tasks) | Strategic decisions, predictions, proactive |
| Ticket volume | 500/month | 2000/month | 10000/month |
| Custom API | No | Yes | Yes |
| OpenAPI Import | No | No | Yes |
| Concurrent AI calls | 2 | 3 | 5 |

### D6: API Key Testing = Pre-written Code, NO AI
- Each integration has a specific pre-written HTTP test call
- HubSpot: GET /crm/v3/contacts?limit=1 → if 200, key works
- Salesforce: GET /services/data/v56.0/ → if 200, key works
- Shopify: GET /admin/api/2024-01/shop.json → if 200, key works
- Slack: POST /api/auth.test → if "ok": true, works
- QuickBooks: GET /v3/company/{id}/companyinfo → if 200, works
- Custom API: GET {base_url}/health → if response, works
- Zero AI tokens spent. 1-2 second response. Clear error messages (invalid key / lacks permissions / service down)

### D7: Cost Breakdown = Pure Math, NO AI (Same as ROI Calculator)
- Use existing ROI Calculator pattern from /roi-calculator/page.tsx
- Pure JavaScript math on frontend, data from pricing config
- Same calculation engine, extended with integration-specific line items
- Must show: base subscription, per-ticket cost (within/overage), add-ons, integration costs, savings vs humans
- Variant add/remove with live cost recalculation
- Overage charged at END of billing cycle (not per-day micro-charges)
- Live usage bar showing how close to limit

### D8: Customer Journey = Configure First, Pay After Verification
```
Step 1: EXPLORE (Free) — Landing, Jarvis Demo, ROI Calculator
Step 2: CONFIGURE (Free, no card) — Select industry + variant, Connect integrations, Test ALL, Upload KB
Step 3: PAY (Only when everything verified) — Review cost breakdown, Paddle checkout
Step 4: ACTIVATE (AI starts working) — Dashboard live, first ticket handled
Step 5: MODIFY (Anytime) — Change industry, add/remove variants, add/remove integrations
```

### D9: Going Back To Change = Always Possible
- Dashboard → Settings → Plan & Industry
- Change industry → integration catalog updates, warn about disconnected integrations
- Change variant → immediate upgrade, next-cycle downgrade
- Add/remove integrations anytime
- All changes reflected in cost breakdown immediately

### D10: Cost Breakdown Must Include
- Base subscription per variant
- Per-ticket cost (within limit = $0, overage = $0.10/ticket)
- Overage estimation (live usage bar + projected overage)
- Add-on costs (Voice channel, extra concurrent AI calls, Custom API)
- Connected integrations list (no extra cost for connections)
- Savings vs hiring humans (same as ROI Calculator)
- Variant add/remove with live recalculation
- "What if" preview: "Add PARWA High for +$1,500/mo → total $3,999/mo → still saving $8,001/mo"

### D11: Audit Logs = Visible to Clients
- Clients see their OWN audit trail (what AI did on their behalf)
- Parwa admin sees EVERYTHING (all clients)
- Every action logged: timestamp, tool, API call, response, approver
- Exportable for compliance

### D12: Cache Refresh = Varies by Integration Type
- Real-time data (orders, tickets): 5 minutes
- Semi-static data (contacts, deals): 15 minutes
- Rarely-changing data (company info, settings): 60 minutes
- Configurable per integration in backend

### D13: BILLING = No Extra Calls — Buy Another Variant (LOCKED)
- **ZERO extra billing triggers**: No per-integration charges, no mid-cycle proration, no per-API-call billing, no integration add-on charges
- **Adding/removing integrations = FREE** — integrations cost nothing to connect or disconnect
- **If client needs more capacity → they buy another variant** — that is the ONLY billing lever
- **Variant upgrade = immediate** (new capacity now, charged now via Paddle)
- **Variant downgrade = next billing cycle** (keep capacity until cycle ends, then drop)
- **Overage = end-of-cycle only** — no micro-charges per ticket mid-month
- **Cost Breakdown page = pure math display** — shows what they WILL pay based on current config, no hidden fees
- **Paddle checkout = only for variant subscription + add-ons (voice, custom API)** — nothing else is billable
- **No proration complexity** — if they add PARWA High mid-cycle, full month charge; if they remove Mini next cycle, it just drops

---

## KNOWN ISSUES (10 from initial audit)

1. Billing page frontend uses MOCK_INVOICES — backend has full Paddle integration
2. Tickets page uses localStorage Zustand store — backend has 20+ ticket API routers
3. CRM MCP Server returns "Sample Contact" — no real HubSpot/Salesforce
4. Ecommerce MCP Server returns "Sample Product, $149.99" — no real Shopify
5. Ticketing MCP Server returns "TKT_placeholder_XXXXX" — no real DB
6. All Knowledge MCP servers (FAQ, RAG, KB) return mock data
7. All Tool MCP servers (Analytics, Monitoring, Notifications, Compliance, SLA) return hardcoded data
8. Carrier API Connector returns random simulated tracking data
9. ProviderFactory._load_credentials() raises NotImplementedError
10. Three duplicate integration layers (ExternalToolBus, ProductionConnector, frontend direct calls)

---

## GAPS IDENTIFIED (7 Original + 15 Deep-Dive = 22 Total)

### Original 7 Gaps (A–G)

#### Gap A: Incoming Webhooks (Parwa doesn't listen) — HIGH
- **Scenario**: New Shopify order → Parwa doesn't know until someone asks
- **Fix**: Register webhooks with third-party tools → instant notification → AI acts proactively

#### Gap B: Data Caching/Refresh Strategy — HIGH
- **Scenario**: AI calls HubSpot 100x for same contact = slow + rate limited
- **Fix**: Cache locally with smart refresh (5/15/60 min by data type)

#### Gap C: Cross-Channel Customer Recognition — HIGH
- **Scenario**: Sarah emails + chats about same refund → 2 separate conversations
- **Fix**: Match by email/phone → unified thread

#### Gap D: Graceful Failure When Third-Party APIs Go Down — HIGH
- **Scenario**: HubSpot down → AI crashes
- **Fix**: Cached data fallback + "limited access" message + log failure

#### Gap E: Audit Trail for All AI Actions — CRITICAL
- **Scenario**: AI processed $50 refund → customer disputes → no proof
- **Fix**: Log everything: timestamp, tool, API call, response, approver

#### Gap F: Integration Disconnect Handling — MEDIUM
- **Scenario**: Client removes HubSpot → AI keeps calling it
- **Fix**: Instant stop + stale cache + AI adjusts + cleanup

#### Gap G: Third-Party Rate Limit Respect — HIGH
- **Scenario**: 50 tickets at once → 50 Shopify API calls → blocked for 5 min
- **Fix**: Queue + throttle per integration's rate limits

### Deep-Dive 15 Gaps (1–15)

---

#### GAP 1: Frontend Pages for EVERY Integration — HIGH

Every MCP server needs a frontend presence. Currently 7 MCP servers have NO UI page at all. The rule (CLAUDE.md #6) says "add to existing page, no new pages for small features" — so we embed widgets into existing pages, not create standalone pages.

| MCP Server | Current UI | What's Needed | Where It Lives |
|-----------|-----------|---------------|---------------|
| CRM | Settings/Integrations | Backend wiring only (already has connect UI) | Settings page |
| Ecommerce | Settings/Integrations | Backend wiring only (already has connect UI) | Settings page |
| Ticketing | Dashboard/Tickets | Wire to real API (already has ticket UI) | Tickets page |
| FAQ | NO PAGE | FAQ management widget — add/edit/delete FAQ entries | Settings → Knowledge section |
| RAG | NO PAGE | Document upload widget + search test UI | Settings → Knowledge section |
| Knowledge Base | Dashboard/Knowledge | Wire to real API (already has KB UI) | Knowledge page |
| Analytics | Dashboard | Wire to real data (already has analytics UI) | Dashboard page |
| Monitoring | NO PAGE | Integration health dashboard widget | Settings → Integrations section |
| Notifications | NO PAGE | Notification bell + preferences panel | Dashboard header + Settings → Notifications |
| Compliance | NO PAGE | PII scan results + compliance status widget | Settings → Compliance section |
| SLA | NO PAGE | SLA tracker widget + SLA rules config | Dashboard/Tickets + Settings → SLA |
| Carrier | NO PAGE | Carrier tracking widget in ticket detail | Ticket detail view |
| Webhook Events | NO PAGE | Webhook event log viewer | Settings → Webhooks section |

**Architecture Decision**: All missing widgets are EMBEDDED into existing pages as sections/cards/panels. Zero new standalone pages. Each widget follows the same pattern: BFF API call → backend data → render in existing layout.

---

#### GAP 2: Global API Key System Architecture — HIGH

A universal key format that accepts ANY provider's credentials. Every integration's API key form adapts dynamically based on the provider's auth requirements.

**Auth Types Supported (5 types)**:

| Auth Type | Form Fields | Example Integrations | Storage Format |
|-----------|------------|---------------------|---------------|
| Bearer Token | API Key / Token field | HubSpot, Slack, Zendesk, Stripe, GitHub | `{"type": "bearer", "token": "encrypted..."}` |
| API Key Header | Header Name + API Key | Shopify (X-Shopify-Access-Token), Mailchimp | `{"type": "header", "header_name": "X-Shopify-Access-Token", "key": "encrypted..."}` |
| API Key Query Param | Param Name + API Key | Klaviyo (api_key param) | `{"type": "query", "param_name": "api_key", "key": "encrypted..."}` |
| Basic Auth | Username + Password | WooCommerce, Twilio | `{"type": "basic", "username": "encrypted...", "password": "encrypted..."}` |
| OAuth 2.0 | Client ID + Client Secret + Redirect URI | Salesforce, QuickBooks, Google | `{"type": "oauth2", "client_id": "encrypted...", "client_secret": "encrypted...", "redirect_uri": "...", "refresh_token": "encrypted..."}` |

**Universal API Key Form Flow**:
1. Client selects integration → form renders dynamically based on that integration's auth schema
2. Each integration in the catalog has an `auth_schema` definition (which auth type, which fields, which are required)
3. Client fills fields → "Test Connection" button runs the pre-written HTTP test call (D6)
4. Test passes → keys encrypted and stored in backend → never sent back to frontend
5. Test fails → clear error message (invalid key / lacks permissions / service down)

**Auth Schema Definition** (stored per integration in catalog):
```javascript
const INTEGRATION_CATALOG = {
  hubspot: {
    name: "HubSpot",
    auth_type: "bearer",
    fields: [{ name: "api_key", label: "HubSpot API Key", type: "password", required: true }],
    test_endpoint: "GET https://api.hubapi.com/crm/v3/contacts?limit=1",
    test_headers: { "Authorization": "Bearer {api_key}" }
  },
  shopify: {
    name: "Shopify",
    auth_type: "header",
    fields: [
      { name: "store_url", label: "Store URL (e.g. mystore.myshopify.com)", type: "text", required: true },
      { name: "access_token", label: "Access Token", type: "password", required: true }
    ],
    test_endpoint: "GET https://{store_url}/admin/api/2024-01/shop.json",
    test_headers: { "X-Shopify-Access-Token": "{access_token}" }
  },
  salesforce: {
    name: "Salesforce",
    auth_type: "oauth2",
    fields: [
      { name: "client_id", label: "Consumer Key", type: "text", required: true },
      { name: "client_secret", label: "Consumer Secret", type: "password", required: true },
      { name: "instance_url", label: "Instance URL", type: "text", required: true }
    ],
    test_endpoint: "GET {instance_url}/services/data/v56.0/",
    test_flow: "oauth2_authorization_code"
  }
  // ... every integration follows same schema
};
```

**Custom REST Connector (Tier 3) Auth**: Client picks auth type from the same 5 types above, fills in the fields manually. The universal form adapts.

---

#### GAP 3: Complete Integration Catalog Per Industry — HIGH

Which integrations show for each industry when the client selects their industry during onboarding or in Settings.

| Industry | CRM | Ecommerce | Ticketing | Analytics | Marketing | Payments | Shipping | Dev Tools | Productivity |
|----------|-----|-----------|-----------|-----------|-----------|----------|----------|-----------|-------------|
| **SaaS** | HubSpot, Salesforce, Pipedrive | — | Zendesk, Freshdesk, Intercom | Mixpanel, Amplitude | Mailchimp, Brevo | Stripe, Paddle | — | GitHub, Jira, Linear | Slack, Notion |
| **E-commerce** | HubSpot | Shopify, WooCommerce, BigCommerce | Zendesk, Gorgias | Google Analytics | Klaviyo, Mailchimp | Stripe, PayPal | ShipStation, AfterShip | — | Slack |
| **Logistics** | HubSpot, Salesforce | — | Zendesk, Freshdesk | — | — | Stripe | ShipStation, AfterShip, EasyPost, FedEx, UPS, DHL | — | Slack |
| **Other** | HubSpot, Salesforce, Pipedrive | Shopify, WooCommerce, BigCommerce | Zendesk, Freshdesk, Intercom | Mixpanel, Amplitude, Google Analytics | Mailchimp, Klaviyo, Brevo | Stripe, Paddle, PayPal | ShipStation, AfterShip, EasyPost | GitHub, Jira, Linear | Slack, Notion |

**Rules**:
- **SaaS**: CRM + Ticketing + Analytics + Dev Tools heavy, no Ecommerce/Shipping
- **E-commerce**: Ecommerce + Marketing + Payments + Shipping heavy, no Dev Tools
- **Logistics**: CRM + Shipping heavy (6 carriers), no Ecommerce/Marketing/Analytics
- **Other**: Shows EVERYTHING — no filtering, client picks what they need
- **Tier 2 (OpenAPI Import) and Tier 3 (Custom REST)**: Available for ALL industries — if their tool isn't in the catalog, they can still connect it
- Client can ALWAYS connect integrations outside their industry filter (the filter is just default suggestions, not restrictions)

---

#### GAP 4: Custom REST Connector (Tier 3) Architecture — MEDIUM

For PARWA and PARWA High clients who need to connect tools not in the pre-built catalog.

**Tier 3 Setup Flow**:
1. Client clicks "Add Custom Integration" in Settings → Integrations
2. Form appears with fields:
   - **Integration Name** (client labels it, e.g. "Internal Billing API")
   - **Base URL** (e.g. `https://billing.internal.company.com/api/v1`)
   - **Auth Type** (dropdown: Bearer Token / API Key Header / API Key Query Param / Basic Auth / OAuth 2.0)
   - **Auth Fields** (dynamic — same as GAP 2 universal form, adapts to selected auth type)
   - **Actions** (the API calls the AI can make — see below)
   - **Test Endpoint** (default: `GET {base_url}/health`, client can override)

**Action Definition** (what the AI can do through this connector):
- Client defines actions one by one. Each action has:
  - **Action Name** (e.g. "Create Invoice", "Get Customer Balance")
  - **Method** (GET / POST / PUT / PATCH / DELETE)
  - **Path** (e.g. `/invoices`, `/customers/{id}/balance`)
  - **Description** (natural language — what this action does, when to use it — THIS is how the AI learns)
  - **Required Params** (e.g. `customer_id`, `amount`)
  - **Optional Params** (e.g. `due_date`, `notes`)
  - **Response Format** (JSON path to key data, e.g. `data.balance`)

**Example Custom Connector**:
```javascript
{
  name: "Internal Billing API",
  base_url: "https://billing.internal.company.com/api/v1",
  auth: { type: "bearer", token: "encrypted..." },
  actions: [
    {
      name: "Get Customer Balance",
      method: "GET",
      path: "/customers/{customer_id}/balance",
      description: "Retrieves the current account balance and payment status for a customer. Use when a customer asks about their bill, outstanding amount, or payment history.",
      params: { required: ["customer_id"], optional: [] },
      response_key: "data.balance"
    },
    {
      name: "Create Invoice",
      method: "POST",
      path: "/invoices",
      description: "Creates a new invoice for a customer. Use when a customer requests a new invoice or when billing adjustments are needed.",
      params: { required: ["customer_id", "amount"], optional: ["due_date", "notes"] },
      response_key: "data.invoice_id"
    }
  ]
}
```

**How the AI Learns a Custom Connector**:
- The `description` field on each action is injected into the AI's tool prompt at runtime
- When AI sees a ticket about billing, it matches the description text → selects this tool → calls the action
- No training needed — it's pure prompt-based tool selection
- Client can edit descriptions anytime to improve AI accuracy

**Storage**: Custom connectors stored per-tenant in `custom_connectors` table. Schema: `tenant_id, connector_id, name, base_url, auth_config (encrypted), actions (JSONB), created_at, updated_at`

**Billing**: Custom API add-on = $49/month (already in D10). No per-action charges. No per-call charges. If they need more capacity, they buy another variant.

---

#### GAP 5: OpenAPI Import (Tier 2) Architecture — MEDIUM

For PARWA High clients only. Client provides an OpenAPI/Swagger spec URL, and Parwa auto-generates a connector from it.

**Tier 2 Import Flow**:
1. Client clicks "Import API" in Settings → Integrations
2. Form appears with fields:
   - **API Documentation URL** (e.g. `https://api.example.com/docs/openapi.json`)
   - **OR Upload File** (accepts `.json` / `.yaml` / `.yml` OpenAPI specs)
   - **Integration Name** (auto-filled from spec `info.title`, client can edit)
   - **Base URL** (auto-filled from spec `servers[0].url`, client can edit)
   - **Auth Type** (auto-detected from spec `securitySchemes`, client confirms/overrides)
   - **Auth Fields** (same universal form — GAP 2)

3. Client clicks "Import" → Parwa backend processes the spec:
   - **Parse OpenAPI spec** (support v2.0/Swagger and v3.0/v3.1)
   - **Extract endpoints** → convert to actions (same format as Tier 3 actions)
   - **Auto-generate action names** from `operationId` or `summary`
   - **Auto-generate descriptions** from `description` and `summary` fields in spec
   - **Auto-detect auth** from `securitySchemes` section
   - **Auto-map parameters** from `parameters` and `requestBody`

4. Client reviews the auto-generated actions list:
   - Can edit action names, descriptions, parameters
   - Can disable actions they don't want the AI to use
   - Can add custom descriptions for better AI matching
   - "Test All" button tests each endpoint

5. Client clicks "Save" → connector stored same as Tier 3 (same `custom_connectors` table, with `source: "openapi_import"` flag)

**OpenAPI Parsing Rules**:
- Only import `GET`, `POST`, `PUT`, `PATCH`, `DELETE` methods (ignore OPTIONS, HEAD)
- Skip deprecated endpoints (mark them but don't enable by default)
- Convert path parameters (`{id}`) to required action params
- Convert query parameters to optional action params
- Convert request body schema to action params
- If spec has no descriptions → generate generic: "Calls {METHOD} {PATH}"
- Rate limit: Parse one spec at a time, max 100 endpoints per spec

**How the AI Learns an Imported API**:
- Same as Tier 3 — action descriptions injected into AI tool prompt at runtime
- OpenAPI specs typically have rich descriptions → AI gets high-quality tool definitions
- Client can always edit descriptions post-import to improve accuracy

**Billing**: OpenAPI Import is included in PARWA High subscription (no extra charge). No per-import charges. If they need more capacity, they buy another variant.

---

#### GAP 6: API Key Encryption & Security — HIGH

All third-party API keys must be encrypted at rest, never exposed to frontend, with rotation support.

**Encryption Architecture**:
- **Algorithm**: AES-256-GCM (same as existing OAuth token encryption per ADR-001 in `/backend/app/docs/adr/001-fernet-vs-aes256gcm-oauth-tokens.md`)
- **Key Management**: Master encryption key stored in environment variable `ENCRYPTION_MASTER_KEY`, rotated quarterly
- **Storage**: All API keys stored in `integration_credentials` table
  - Schema: `id, tenant_id, integration_id, auth_type, encrypted_data (JSONB), created_at, rotated_at, rotated_by`
  - `encrypted_data` contains the AES-256-GCM encrypted auth fields (token, secret, etc.)
  - Never stored in plaintext, never logged, never sent to frontend

**Key Lifecycle**:

| Action | Who Can Do It | What Happens |
|--------|--------------|--------------|
| **Add key** | Client admin | Fill form → encrypt → store → test connection |
| **View key** | NOBODY | Frontend never receives the key. Shows "••••••••" masked value. Only last 4 chars visible |
| **Rotate key** | Client admin | Enter new key → encrypt → replace old → test new → mark old as rotated |
| **Revoke key** | Client admin | Delete encrypted record → instant stop all API calls → invalidate cache |
| **Test key** | Client admin (or auto) | Pre-written HTTP call (D6) — no decryption on frontend, test runs on backend |

**Auto-Rotation Detection**:
- If a third-party API returns 401/403 on a previously working key → flag as "Key may need rotation"
- Show warning in Integration Health Dashboard (GAP 15) and notification bell
- AI switches to cached data mode (Gap D) until client rotates
- No automatic key rotation by Parwa — client must provide new credentials

**Frontend Display Rules**:
- Connected integrations show: Integration name, status (connected/error), auth type, last 4 chars of key, last tested timestamp
- Never show full key value in any API response or UI element
- "Edit" button = replace key (old key is not shown, new key form is blank)
- "Delete" button = revoke + disconnect immediately

---

#### GAP 7: Knowledge Base Upload & Management Flow — HIGH

Client uploads documents that become the AI's knowledge. This is Step 2 of the Customer Journey (D8): "Upload KB".

**Supported File Formats**:

| Format | Extension | Processing | Max Size |
|--------|-----------|-----------|----------|
| PDF | .pdf | Extract text via PyPDF2, chunk, embed | 50MB |
| Word | .docx | Extract text via python-docx, chunk, embed | 50MB |
| Text | .txt, .md | Direct chunk and embed | 10MB |
| CSV | .csv | Parse rows, embed as structured data | 25MB |
| HTML | .html, .htm | Strip tags, extract text, chunk, embed | 25MB |
| JSON | .json | Flatten and embed as structured data | 25MB |

**Upload Flow**:
1. Client goes to Settings → Knowledge → "Upload Documents"
2. Drag-and-drop or file picker (supports bulk upload, max 20 files at once)
3. Each file is processed:
   - **Validate**: Check format, size, scan for malware
   - **Extract**: Pull text content from file
   - **Chunk**: Split into ~500 token chunks with overlap
   - **Embed**: Generate vector embeddings via OpenAI ada-002
   - **Store**: Save chunks + embeddings in vector DB (Pinecone/Weaviate), linked to tenant
   - **Index**: Add to tenant's search index
4. Client sees upload progress per file: "Processing 3/20 files..." → "18 uploaded, 2 failed (reason)"
5. Failed files show clear error: "File too large (75MB, max 50MB)" / "Unsupported format (.exe)" / "Could not extract text"

**KB Management**:
- **View documents**: List of uploaded files with name, date, chunk count, status
- **Delete document**: Remove all chunks + embeddings for that file → AI no longer uses it
- **Replace document**: Delete old + upload new (treated as two operations)
- **Search test**: Client can test a query → see which KB chunks the AI would retrieve

**How AI Decides: KB vs FAQ vs RAG**:
- **FAQ**: Short, specific Q&A pairs. AI checks FAQ first for exact matches. Fast, zero-cost lookups.
- **KB (Knowledge Base)**: Uploaded documents. AI searches KB when FAQ doesn't have the answer. Used for policies, procedures, product docs.
- **RAG (Retrieval-Augmented Generation)**: Advanced search over KB + FAQ + conversation history with reranking (CLARA pipeline). Used for complex, multi-source questions. PARWA and PARWA High only (requires deeper AI pipeline).

**Priority order for AI**: FAQ → KB → RAG → External Integration (HubSpot, Shopify, etc.)

---

#### GAP 8: Existing Onboarding vs New Configure-First Flow — MEDIUM

Parwa already has a Jarvis onboarding flow. The new Customer Journey (D8) must connect to it, not replace it.

**Architecture: Jarvis Onboarding BECOMES Step 1 + Step 2 of Customer Journey**:

```
CURRENT Jarvis Flow:
  Jarvis Welcome → Industry Selection → Variant Selection → Done (no integration setup)

NEW Customer Journey (D8):
  Step 1: EXPLORE — Jarvis Demo + ROI Calculator (existing Jarvis handles this)
  Step 2: CONFIGURE — Industry + Variant + Connect Integrations + Test ALL + Upload KB
  Step 3: PAY — Cost Breakdown Review + Paddle Checkout
  Step 4: ACTIVATE — Dashboard Live
  Step 5: MODIFY — Anytime changes
```

**Merge Plan**:
- **Jarvis Demo** = Step 1 (Explore). Already exists. No changes needed.
- **Jarvis Onboarding** = Extended to include Step 2 (Configure). After industry/variant selection, Jarvis guides the client through: "Great! Now let's connect your tools. Which CRM do you use?" → "Let me test that connection..." → "Want to upload your knowledge base?" → etc.
- **Jarvis does NOT handle Step 3 (Pay)**. After configuration, Jarvis says "Everything's connected and verified! Let me take you to your cost breakdown." → redirects to cost breakdown page.
- **Step 4 (Activate)** happens automatically after Paddle checkout success callback.
- **Step 5 (Modify)** = Settings page (already exists).

**What changes in Jarvis**:
- Extend `jarvis_onboarding_service.py` to include integration connection steps
- Add Jarvis commands: "connect hubspot", "test connection", "upload knowledge base"
- Jarvis uses the same BFF APIs as the Settings page — no separate integration code path
- Jarvis conversation state tracks: `industry_selected`, `variant_selected`, `integrations_connected[]`, `kb_uploaded`, `all_tested`

---

#### GAP 9: Multi-Variant Architecture — HIGH

Clients can have MULTIPLE variants active at the same time. Each variant handles different types of work.

**Multi-Variant Rules**:
- A client can have any combination: Mini + PARWA, Mini + PARWA High, PARWA + PARWA High, all three, or just one
- **Each variant has its OWN ticket allocation**: Mini (500) + PARWA (2000) = 2500 total tickets/month
- **Each variant has its OWN AI pipeline**: Mini tickets get 3-step, PARWA tickets get 6-step, PARWA High tickets get 9-step
- **Integrations are SHARED across all variants** — connecting HubSpot once means all variants can use it
- **Knowledge base is SHARED** — one KB per client, all variants access it
- **Channels can be split per variant** or shared (client configures in Settings)

**How AI Routes Tickets to Variants**:

| Ticket Type | Routes To | Why |
|-------------|----------|-----|
| Simple FAQ lookup, "What's your return policy?" | Mini PARWA | 3-step pipeline is enough |
| Action needed: "Process my refund" | PARWA | 6-step pipeline with action tools |
| Complex: "My refund failed and I want to escalate + predict churn risk" | PARWA High | 9-step pipeline with strategic techniques |

**Routing Logic** (`variant_router.py` — already exists in codebase):
1. Ticket arrives → AI classifies intent + complexity
2. Complexity score (1-10):
   - 1-3: Route to lowest active variant (Mini if active, else PARWA, else PARWA High)
   - 4-7: Route to middle active variant (PARWA if active, else PARWA High)
   - 8-10: Route to PARWA High (must be active)
3. If target variant's ticket limit is reached → route to next higher variant
4. If ALL variant limits are reached → overage on highest variant (D7 billing rule)

**Cost of Multi-Variant**: Each variant is its own subscription. Mini ($999) + PARWA ($2,499) = $3,498/month total. No bundling discount (yet). If they need more capacity, they buy another variant.

**Frontend — Variant Mixer** (in Cost Breakdown page):
- Shows all active variants with ticket allocation per variant
- "Add Variant" button → select Mini/PARWA/PARWA High → live cost recalculation
- "Remove Variant" button → next-cycle removal → live cost recalculation
- Per-variant ticket usage bars

---

#### GAP 10: Industry Change Impact — MEDIUM

What happens when a client changes their industry after already being set up.

**Industry Change Flow**:

| What Happens | Behavior |
|-------------|----------|
| Integration catalog updates | New industry's integrations shown by default. Old industry's integrations stay connected but marked "outside your industry" |
| Existing connected integrations | STAY CONNECTED. Never auto-disconnect. Client must manually disconnect if they want |
| Tickets | PRESERVED. All historical and active tickets remain unchanged |
| Knowledge base | PRESERVED. Client's uploaded docs remain unchanged |
| AI behavior | Adjusts: if changing from E-commerce to SaaS, AI prioritizes CRM/Analytics tools over Shopify/Shipping |
| Billing | NO CHANGE. Same variant, same price. No industry-based pricing |
| Webhooks | PRESERVED. Existing webhooks keep firing |

**Warning Modal on Industry Change**:
```
"You're changing from E-commerce to SaaS.

Your connected integrations:
  - Shopify (E-commerce) → Will still work, but no longer suggested
  - HubSpot (CRM) → Still recommended for SaaS ✓
  - ShipStation (Shipping) → Will still work, but no longer suggested

Your tickets, knowledge base, and billing are NOT affected.

Would you like to disconnect any integrations that no longer apply?"
[Keep All] [Review Integrations]
```

**Key Principle**: Industry is a SUGGESTION filter, not a restriction. Changing it never breaks anything. The client's data and connections are always preserved. They can always connect tools outside their industry.

---

#### GAP 11: Integration ↔ Billing Connection — HIGH

How integrations relate to billing. **Following D13: No extra billing calls — if they need more, buy another variant.**

**Billing Rules**:

| Action | Billing Impact |
|--------|---------------|
| Connect integration | $0. FREE. No charge. |
| Disconnect integration | $0. No refund. No credit. |
| Use integration (AI calls external API) | $0. Included in variant subscription. |
| Add Custom API (Tier 3) | $49/month add-on (PARWA/PARWA High only) |
| Use OpenAPI Import (Tier 2) | $0. Included in PARWA High subscription |
| Add Voice channel | $199/month add-on (if not included in variant) |
| Exceed ticket limit | $0.10/ticket overage at end of billing cycle |
| Buy another variant | Full variant subscription price, charged immediately |

**Cost Breakdown → Paddle Checkout Flow**:
1. Client configures everything (industry, variant, integrations, KB)
2. Client clicks "Review Cost Breakdown" → sees pure-math calculation of their monthly total
3. Cost breakdown shows: Variant subscription(s) + Add-ons (voice, custom API) = Total
4. Client clicks "Proceed to Checkout" → Paddle overlay opens with exact amount
5. Paddle processes payment → webhook to Parwa backend → subscription activated
6. Client's dashboard goes live

**Mid-Cycle Changes**:
- **Variant upgrade**: Immediate. New capacity now. Full month charge via Paddle.
- **Variant downgrade**: Next cycle. Keep capacity until cycle ends. No proration, no partial refund.
- **Add integration**: FREE. No billing event at all.
- **Remove integration**: FREE. No billing event at all.
- **Add Custom API**: $49/month add-on. Charged immediately via Paddle.
- **Remove Custom API**: Next cycle. No partial refund.

**No Proration Philosophy**: Proration is complex, error-prone, and creates micro-charges. We avoid it entirely. Upgrade = pay full now. Downgrade = drops next cycle. Simple. Clean. Predictable.

---

#### GAP 12: Notification Architecture — MEDIUM

What triggers notifications, what types exist, and how they're delivered.

**Notification Types**:

| Category | Trigger | Severity | Delivery |
|----------|---------|----------|----------|
| Integration Health | API key expired / invalid | HIGH | In-app + Email |
| Integration Health | Third-party API down | MEDIUM | In-app |
| Integration Health | Rate limit approaching (80% used) | LOW | In-app |
| Integration Health | Integration disconnected | HIGH | In-app + Email |
| Billing | Overage approaching (80% of ticket limit) | MEDIUM | In-app + Email |
| Billing | Overage threshold reached | HIGH | In-app + Email |
| Billing | Payment failed | CRITICAL | In-app + Email |
| Billing | Subscription renewed | LOW | In-app |
| Webhooks | Webhook delivery failed (3 retries) | MEDIUM | In-app |
| Webhooks | New webhook event received | LOW | In-app (log only) |
| AI Actions | AI action requires approval (high-value) | HIGH | In-app + Email |
| AI Actions | AI action completed (daily summary) | LOW | In-app |
| Compliance | PII detected in outgoing response (blocked) | HIGH | In-app + Email |
| System | New feature available | LOW | In-app |
| System | Scheduled maintenance | MEDIUM | In-app + Email |

**Notification Delivery Channels**:
- **In-app**: Bell icon in dashboard header → dropdown with unread count badge → click to open notification panel
- **Email**: For HIGH and CRITICAL severity only. Sent via existing email provider (Mailgun/SendGrid)
- **No push notifications** (yet — can add later for mobile app)

**Notification Preferences** (Settings → Notifications):
- Client can enable/disable email for each category
- In-app notifications are always on (cannot be disabled)
- Critical notifications (payment failed, PII breach) cannot be disabled for either channel

**Notification Storage**:
- Table: `notifications` — `id, tenant_id, category, severity, title, body, read, created_at, action_url`
- Retention: 90 days for read notifications, forever for unread
- Max 1000 notifications per tenant (oldest auto-archived)

---

#### GAP 13: Complete Data Flow Architecture — HIGH

How every request flows from frontend through to external API and back.

**Request Flow Diagram**:
```
Frontend (React)
    ↓ BFF API call (e.g. POST /api/integrations/hubspot/contacts)
BFF Layer (Next.js API route)
    ↓ Auth check (JWT) + Tenant isolation (RLS)
    ↓ Forward to Backend
Backend (FastAPI)
    ↓ Load encrypted API key from integration_credentials
    ↓ Decrypt key
    ↓ Check cache (Redis) → if fresh, return cached data
    ↓ If stale/missing: Call External API
ExternalToolBus
    ↓ Rate limit check → Queue if needed
    ↓ Make HTTP request to third-party (HubSpot API)
    ↓ Receive response
External API (HubSpot)
    ↓ Response
ExternalToolBus
    ↓ Cache response (Redis, TTL per data type per D12)
    ↓ Log action to audit trail (Gap E)
    ↓ Return data to Backend
Backend
    ↓ Format response (strip sensitive data)
    ↓ Return to BFF
BFF Layer
    ↓ Return JSON to Frontend
Frontend
    ↓ Render in UI
```

**MCP Server Role**:
- MCP servers are the AI's tool interface, NOT the frontend's data interface
- When AI needs to call HubSpot → it uses the CRM MCP Server → which calls ExternalToolBus → which calls HubSpot API
- When frontend needs to show HubSpot data → it calls BFF API → Backend → ExternalToolBus → HubSpot API
- **Same ExternalToolBus** for both paths — no duplicate code
- MCP Server = AI's tool definitions (what actions are available, how to call them)
- ExternalToolBus = actual HTTP client that makes the calls (shared by MCP and Backend)

**Error Propagation**:
```
External API Error → ExternalToolBus catches → Circuit breaker check →
  If retriable: Queue + retry (max 3x with exponential backoff)
  If not retriable: Return error to caller
Backend receives error → Log to audit trail → Return structured error to BFF:
  { "success": false, "error": "hubspot_api_down", "message": "HubSpot is currently unavailable. Using cached data from 3 minutes ago.", "data": <cached_fallback> }
BFF receives → Return to frontend with degraded data + warning
Frontend shows: Yellow banner "Live data temporarily unavailable. Showing data from 3 minutes ago."
```

---

#### GAP 14: AI Integration Selection Logic — HIGH

When a ticket comes in, how does the AI decide WHICH integration to use?

**AI Tool Selection Pipeline**:

1. **Ticket arrives** → AI classifies intent:
   - What is the ticket about? (billing, shipping, CRM lookup, order status, general question, etc.)
   - What data does the AI need to resolve this? (customer info, order info, shipping status, KB article, etc.)

2. **AI checks available tools** (from tenant's connected integrations + KB + FAQ):
   - The AI's system prompt includes a list of all connected tools with their descriptions
   - Each tool has a natural language description (from auth schema for Tier 1, from client-written descriptions for Tier 3, from OpenAPI spec for Tier 2)
   - FAQ tool: "Search frequently asked questions for exact matches"
   - KB tool: "Search uploaded knowledge base documents for policies and procedures"
   - CRM tool: "Look up customer information in HubSpot/Salesforce. Use when you need customer details, contact info, or deal status."
   - Ecommerce tool: "Look up orders, products, and inventory in Shopify/WooCommerce. Use when customer asks about orders, refunds, or product availability."
   - Shipping tool: "Track shipments and delivery status via ShipStation/AfterShip. Use when customer asks about shipping or delivery."
   - etc.

3. **AI selects tool(s)** based on intent → tool description match:
   - Simple FAQ match → FAQ tool only
   - "Where's my order?" → Ecommerce tool (get order) + Shipping tool (get tracking)
   - "I want a refund for order #123" → Ecommerce tool (get order to verify) → Ecommerce tool (process refund)
   - "What's our company return policy?" → KB tool (search uploaded policy docs)
   - "What's my account balance?" → Custom API tool (Internal Billing API → Get Customer Balance)

4. **AI executes tool call** via MCP Server → ExternalToolBus → External API

5. **AI reasons on result** → may call additional tools or generate response

**Tool Prompt Injection (per ticket)**:
```python
# Dynamically built per tenant per ticket
system_prompt = f"""
You are Parwa AI assistant for {tenant_name} ({industry}).

Available tools:
{tool_1_name}: {tool_1_description}
{tool_2_name}: {tool_2_description}
...

Knowledge sources:
- FAQ: {faq_entry_count} entries
- Knowledge Base: {kb_document_count} documents
- Connected integrations: {integration_list}

Select the most appropriate tool for the user's request. If no tool is needed, answer from your training data or knowledge base.
"""
```

**Conflict Resolution** (multiple tools could answer):
- Priority: FAQ → KB → RAG → External Integration (same as GAP 7)
- If Shopify AND HubSpot both have customer data → use the one matching the ticket's domain (order question → Shopify, CRM question → HubSpot)
- If unsure → AI can call multiple tools and synthesize

---

#### GAP 15: Integration Health Dashboard — MEDIUM

A dashboard where clients can see the real-time status of all their connected integrations.

**Location**: Settings → Integrations → "Health" tab (embedded in existing Settings page per CLAUDE.md #6)

**Health Dashboard Sections**:

| Section | What It Shows |
|---------|--------------|
| **Integration Status Grid** | Card per connected integration: name, status icon (green/yellow/red), last successful call, last error |
| **Last Sync Time** | When data was last fetched from each integration, color-coded by freshness (green = within refresh interval, yellow = stale, red = very stale or error) |
| **Error Log** | Recent errors per integration (last 7 days): timestamp, error type, error message, resolution status |
| **API Rate Limit Usage** | Per integration: requests made today / daily limit, progress bar, estimated time until reset |
| **Connection Test** | "Re-test" button per integration — runs the same pre-written HTTP test call (D6) |
| **Cache Status** | Per integration: cache size, last refresh, next scheduled refresh |

**Status Definitions**:

| Status | Icon | Meaning |
|--------|------|---------|
| Healthy | Green circle | All API calls succeeding, cache fresh, no errors in 24h |
| Degraded | Yellow circle | Some API calls failing, using cached fallback, or rate limit >80% |
| Down | Red circle | API calls failing consistently, no cached fallback available, or key invalid |
| Disconnected | Gray circle | Integration not connected (no API key stored) |

**Auto-Health Checks**:
- Every 5 minutes: Backend pings each connected integration's test endpoint (D6)
- If test fails → update status to Degraded/Down → trigger notification (GAP 12)
- If test recovers → update status to Healthy → trigger recovery notification
- Health check results stored in `integration_health` table: `tenant_id, integration_id, status, last_check, last_success, last_error, error_count_24h`

**Admin View** (Parwa admin dashboard):
- See ALL tenants' integration health across the platform
- Filter by integration type, status, tenant
- Aggregate stats: "HubSpot: 94% healthy across 127 tenants"

---

## PRE-BUILT INTEGRATION TEST CALLS (No AI)

| Integration | Test Endpoint | Auth Method | Success = | Failure Messages |
|-------------|--------------|-------------|-----------|-----------------|
| HubSpot | GET /crm/v3/contacts?limit=1 | Bearer {api_key} | 200 | 401=Invalid key, 403=Lacks permissions |
| Salesforce | GET /services/data/v56.0/ | Bearer {token} | 200 | 401=Invalid token, 403=Insufficient access |
| Shopify | GET /admin/api/2024-01/shop.json | X-Shopify-Access-Token | 200 | 401=Invalid key, 404=Wrong store URL |
| WooCommerce | GET /wp-json/wc/v3/system_status | Basic auth | 200 | 401=Invalid credentials, 404=Wrong URL |
| Slack | POST /api/auth.test | Bearer {token} | "ok":true | "invalid_auth", "missing_scope" |
| Zendesk | GET /api/v2/users/me | Bearer {token} | 200 | 401=Invalid token |
| QuickBooks | GET /v3/company/{id}/companyinfo | Bearer {token} | 200 | 401=Invalid token, 403=Token expired |
| Stripe | GET /v1/balance | Bearer sk_... | 200 | 401=Invalid key |
| Paddle | GET /2.0/user/auth | email+pass | 200 | Invalid credentials |
| Twilio | GET /2010-04-01/Accounts/{sid}.json | Basic auth | 200 | 401=Invalid SID/token |
| Mailchimp | GET /3.0/ping | Bearer {apikey} | 200 | 401=Invalid key |
| Klaviyo | GET /api/v1/account | api_key param | 200 | 401=Invalid key |
| Jira | GET /rest/api/2/myself | Bearer {token} | 200 | 401=Invalid token |
| GitHub | GET /user | Bearer {token} | 200 | 401=Invalid token |
| Custom API | GET {base_url}/health | Custom headers | Any response | Timeout/Connection refused |
| OpenAPI Import | GET {first_endpoint} | Per spec | Per spec | Per spec |

---

## COST BREAKDOWN STRUCTURE (Pure Math, No AI)

### Data Source: Same pattern as ROI Calculator (/roi-calculator/page.tsx)

```javascript
// Pricing config (pure data, no AI)
const PRICING = {
  variants: {
    mini: { price: 999, tickets: 500, aiResolution: 0.60, channels: ['Email', 'Chat'] },
    parwa: { price: 2499, tickets: 2000, aiResolution: 0.78, channels: ['Email', 'Chat', 'SMS', 'Voice'] },
    high: { price: 3999, tickets: 10000, aiResolution: 0.88, channels: ['Email', 'Chat', 'SMS', 'Voice', 'Social', 'Video'] }
  },
  overage: 0.10, // per ticket — charged at END of billing cycle
  addOns: {
    voice: 199,      // per month (if not included in variant)
    extraCall: 99,   // per concurrent AI call per month
    customApi: 49    // per month (Tier 3 Custom REST Connector)
    // NOTE: OpenAPI Import (Tier 2) = $0, included in PARWA High
    // NOTE: Integrations = $0, unlimited connections FREE
  },
  integrations: 0,   // FREE - no cost per connection — PERIOD
  benchmarks: {
    saas: { avgTickets: 3500, avgCostPerTicket: 8.2, avgSalary: 40000 },
    ecommerce: { avgTickets: 5000, avgCostPerTicket: 6.5, avgSalary: 36000 },
    logistics: { avgTickets: 6000, avgCostPerTicket: 5.8, avgSalary: 34000 },
    other: { avgTickets: 3500, avgCostPerTicket: 7.0, avgSalary: 37000 }
  }
};

// Calculation functions (pure math)
function calculateMonthlyCost(variants, ticketCount, addOns) { ... }
function calculateOverage(variants, ticketCount) { ... }
function calculateSavings(variants, currentCosts) { ... }
function calculateVariantMix(variants, ticketCount) { ... }
// NO proration functions — upgrade = full month, downgrade = next cycle
```

### Cost Breakdown Page Sections:
1. **Base Subscription** — selected variant(s) monthly cost
2. **Ticket Costs** — included + overage estimate with live usage bar
3. **Add-Ons** — voice, extra calls, custom API (OpenAPI Import = $0)
4. **Integrations** — connected list (FREE, shows value delivered)
5. **Savings vs Humans** — same calculation as ROI Calculator
6. **Variant Mixer** — add/remove variants with live total
7. **What-If Preview** — "Add PARWA High for +$1,500/mo"
8. **Billing Summary** — "You pay $X/month. That's it. No hidden fees. No per-integration charges. Need more capacity? Add another variant."

---

## PHASES (Updated with 15 Gaps)

### Phase 1: Foundation Fixes ✅
- [x] Fix ProviderFactory._load_credentials() NotImplementedError — multi-path import + provider_config.py in top-level database/
- [x] Fix Mailgun typo (MAILGRID_BASE_URL → MAILGUN_BASE_URL) — already correct in code, docs updated
- [x] Consolidate 3 duplicate integration layers → single ExternalToolBus — canonical bus at backend/app/core/external_tool_bus.py
- [x] Make Voice a Parwa-provided channel with both options (Parwa number / bring own) — number_source, provision_parwa_number(), D3 fields added

### Phase 2: Industry-Aware Integration System
- [ ] Create industry-to-integration mapping (GAP 3 — full catalog per industry)
- [ ] Filter integration catalog by selected industry (suggestions, not restrictions)
- [ ] Remove integration count limits per variant
- [ ] Wire "Test Connection" to pre-written HTTP test calls (NO AI)
- [ ] Add Tier 2: OpenAPI Importer for PARWA High (GAP 5)
- [ ] Add Tier 3: Custom REST Connector for PARWA and PARWA High (GAP 4)
- [ ] Allow going back to change industry/variant anytime (GAP 10 — industry change impact)

### Phase 3: Wire ALL MCP Stubs to Real Backend
- [ ] CRM Server → real HubSpot/Salesforce/Pipedrive API passthrough
- [ ] Ecommerce Server → real Shopify/WooCommerce/BigCommerce API passthrough
- [ ] Ticketing Server → real backend ticket APIs (20+ endpoints)
- [ ] FAQ Server → real backend FAQ search
- [ ] RAG Server → real vector search + CLARA pipeline
- [ ] KB Server → real knowledge base API
- [ ] Analytics Server → real backend analytics
- [ ] Monitoring Server → real backend health checks
- [ ] Notification Server → real notification dispatch
- [ ] Compliance Server → real PII scanning engine
- [ ] SLA Server → real SLA tracking
- [ ] Carrier Server → real shipping API passthrough

### Phase 4: Customer Journey — Configure First, Pay After
- [ ] Step 1: Explore (free) — landing, demo, ROI calculator (existing Jarvis)
- [ ] Step 2: Configure (free, no card) — industry, variant, connect integrations, test all, upload KB (GAP 7 — KB upload flow)
- [ ] Step 3: Pay (only after verification) — cost breakdown review, Paddle checkout (GAP 11 — billing connection)
- [ ] Step 4: Activate — AI starts working, dashboard live
- [ ] Step 5: Modify — change industry/variant/integrations anytime (GAP 10)
- [ ] Merge Jarvis onboarding into Steps 1-2 (GAP 8)

### Phase 5: Cost Breakdown Page (Pure Math, No AI)
- [ ] Extend ROI Calculator pattern with integration-specific line items
- [ ] Base subscription + per-ticket + overage + add-ons
- [ ] Savings vs humans calculation (reuse ROI Calculator logic)
- [ ] Variant mixer (GAP 9 — multi-variant with live total)
- [ ] Live usage bar with overage projection
- [ ] "What if" upgrade previews
- [ ] Billing summary: "No hidden fees. Need more? Add another variant." (D13)

### Phase 6: Incoming Webhooks System
- [ ] Webhook registration endpoint (client connects tool → Parwa registers webhook URL)
- [ ] Webhook receiver endpoint (third-party sends event → Parwa processes it)
- [ ] Webhook HMAC verification (security)
- [ ] Event → AI action mapping (new Shopify order → send confirmation email)
- [ ] Webhook event log viewer UI (GAP 1 — embedded in Settings → Webhooks)

### Phase 7: Data Caching & Smart Refresh
- [ ] Cache layer for third-party API responses
- [ ] Per-integration refresh intervals (5min / 15min / 60min by data type)
- [ ] Cache invalidation on integration disconnect
- [ ] Fallback to cache when third-party API is down

### Phase 8: Cross-Channel Customer Recognition
- [ ] Customer identity matching by email/phone across channels
- [ ] Unified conversation thread view
- [ ] AI context carries across channels

### Phase 9: Audit Trail & Action Logging
- [ ] Log every AI action through integrations
- [ ] Client-visible audit trail (their own actions only)
- [ ] Parwa admin sees everything
- [ ] Export audit logs for compliance

### Phase 10: Rate Limiting & Error Handling
- [ ] Per-integration rate limit configuration
- [ ] Request queuing with polite throttling
- [ ] Circuit breaker per third-party API
- [ ] Graceful degradation when APIs fail (GAP 13 — error propagation flow)
- [ ] Integration disconnect instant cleanup

### Phase 11: Remove ALL Mock Data
- [ ] Delete MOCK_INVOICES from billing page
- [ ] Delete MOCK_DOCUMENTS from knowledge page
- [ ] Delete localStorage ticket store
- [ ] Delete all hardcoded analytics numbers
- [ ] No silent mock fallbacks — show real errors instead

### Phase 12: Add Missing Frontend Widgets (GAP 1 — Full List)
- [ ] FAQ management widget in Settings → Knowledge (add/edit/delete FAQ entries)
- [ ] RAG document upload widget + search test in Settings → Knowledge
- [ ] Notification bell + preferences panel in Dashboard header + Settings → Notifications (GAP 12)
- [ ] Compliance status widget (PII scan results) in Settings → Compliance
- [ ] SLA tracker widget in Dashboard/Tickets + SLA rules config in Settings → SLA
- [ ] Carrier tracking widget in ticket detail view
- [ ] Webhook event log viewer in Settings → Webhooks
- [ ] Live usage bar (tickets used / limit) with overage projection
- [ ] Integration Health Dashboard in Settings → Integrations → Health tab (GAP 15)

### Phase 13: Global API Key System (GAP 2 + GAP 6)
- [ ] Build universal API key form with 5 auth types (Bearer, Header, Query, Basic, OAuth2)
- [ ] Build auth schema definitions for every integration in catalog
- [ ] Dynamic form rendering based on selected integration's auth schema
- [ ] API key encryption at rest (AES-256-GCM per ADR-001)
- [ ] Key storage in integration_credentials table (encrypted JSONB)
- [ ] Key rotation flow (replace old → test new → mark rotated)
- [ ] Key revocation flow (delete → instant stop → invalidate cache)
- [ ] Frontend display: masked values (last 4 chars only), never full key
- [ ] Auto-rotation detection (401/403 on previously working key → flag warning)

### Phase 14: AI Tool Selection & Multi-Variant Routing (GAP 9 + GAP 14)
- [ ] Dynamic tool prompt injection per tenant per ticket (connected integrations + descriptions)
- [ ] Intent → tool matching logic (FAQ → KB → RAG → External Integration priority)
- [ ] Multi-variant ticket routing (complexity score → route to appropriate variant)
- [ ] Variant overflow handling (limit reached → escalate to next variant)
- [ ] Cross-variant integration sharing (one connection, all variants use it)
- [ ] Per-variant ticket usage tracking and display

### Phase 15: Data Flow & Error Architecture (GAP 13)
- [ ] Standardize request flow: Frontend → BFF → Backend → ExternalToolBus → External API
- [ ] MCP servers use ExternalToolBus (shared with Backend — no duplicate code)
- [ ] Structured error propagation: External API → ExternalToolBus → Backend → BFF → Frontend
- [ ] Degraded data responses: cached fallback + yellow warning banner
- [ ] Retry logic: 3x exponential backoff for retriable errors
- [ ] Circuit breaker: per integration, auto-open after 5 consecutive failures, auto-close after 60s

### Phase 16: End-to-End Proof
- [ ] Trace every integration path: Frontend → API → MCP → Backend → External
- [ ] Document exact file/line/endpoint for each integration
- [ ] Verify industry filtering works (GAP 3)
- [ ] Verify variant feature limits are enforced (GAP 9)
- [ ] Verify audit trail captures all actions
- [ ] Verify cost breakdown matches actual Paddle charges (GAP 11)
- [ ] Verify customer journey (configure → verify → pay → activate → modify)
- [ ] Verify API key encryption and rotation (GAP 6)
- [ ] Verify KB upload and search (GAP 7)
- [ ] Verify AI tool selection routing (GAP 14)
- [ ] Verify integration health dashboard (GAP 15)
- [ ] Verify multi-variant ticket routing (GAP 9)
- [ ] Verify notification delivery (GAP 12)
- [ ] Verify industry change preservation (GAP 10)

---

## QUESTIONS STILL OPEN

1. ~~Mini PARWA Custom API connector~~ — agreed No (3-step pipeline too simple for arbitrary APIs)
2. ~~Unlimited integrations~~ — confirmed for all variants
3. ~~Voice~~ — both options confirmed (Parwa number OR bring own)
4. ~~OpenAPI Import~~ — PARWA High only (confirmed)
5. ~~Cache refresh~~ — varies by data type (5/15/60 min) — confirmed
6. ~~Audit logs~~ — clients see their own, admin sees everything — confirmed
7. ~~What other gaps exist~~ — 15 gaps identified and resolved above
8. ~~Billing per integration~~ — RESOLVED: Zero. No extra calls. Buy another variant if you need more. (D13)
9. ~~Proration~~ — RESOLVED: No proration. Upgrade = full month now, downgrade = next cycle. (D13)
10. ~~Industry restrictions~~ — RESOLVED: Industry = suggestion filter only, never restricts connections. (GAP 3)
11. ~~Multi-variant discount~~ — Open: Should buying 2+ variants get a discount? (Currently: no discount)

---

## CLAUDE.md RULES FOR INTEGRATION

1. No direct external calls from frontend — always BFF proxy → Backend → External API
2. One integration entry point — Settings page is the ONLY place to connect/disconnect
3. API key encryption — all third-party keys encrypted at rest (AES-256-GCM), never exposed to frontend
4. Test Connection must be real — pre-written HTTP calls, NO AI tokens
5. No mock fallbacks — if backend is unreachable, show error, never fake data
6. Missing frontend = add to existing page — no new pages for small features (embed as widgets/sections)
7. Voice is Parwa-provided (with bring-own-number option)
8. Integrations are unlimited per variant — difference is AI power, not plumbing
9. Every AI action must be logged — audit trail for compliance and trust
10. Respect third-party rate limits — queue and throttle, never blast
11. Cost calculations = pure math — NO AI tokens for pricing/savings/overage
12. Customer pays ONLY after all integrations verified working
13. Going back to change = always possible (industry, variant, integrations)
14. **NO EXTRA BILLING CALLS** — integrations are free, no per-call charges, no proration. If client needs more capacity, they buy another variant (D13)
15. **Industry = suggestion, not restriction** — changing industry never disconnects or deletes anything (GAP 10)
16. **Universal API key form** — one form system handles all 5 auth types dynamically (GAP 2)
17. **ExternalToolBus is the ONLY integration caller** — MCP servers and Backend both use it, no duplicate code paths (GAP 13)
18. **AI tool selection = prompt-based** — tool descriptions in system prompt, no hardcoded routing (GAP 14)
19. **Multi-variant = separate AI pipelines, shared integrations** — each variant has own ticket limit and AI power, but all share the same connected tools and KB (GAP 9)
20. **Frontend shows masked keys only** — never display full API keys in any UI or API response (GAP 6)
