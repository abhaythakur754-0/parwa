# PARWA integrations and agent data flow

This document describes the intended production data path for CRM, SaaS, and database integrations and the ticket-solving pipeline.

## 1. Who owns the data?

PARWA does not copy every connected system into one central database. The connected provider remains the source of truth. PARWA stores the connection metadata and ticket/workflow records it needs, while agents query external systems through tenant-scoped Superglue tools.

| Data | Storage | Notes |
|---|---|---|
| Integration identity, provider, status, non-secret settings | `integrations` | Scoped by `company_id`; OAuth status is not treated as a provider token |
| API-key credentials used by legacy direct adapters | `integrations.credentials_encrypted` | Encrypted with `DATA_ENCRYPTION_KEY`; never returned by integration list/detail APIs |
| Tenant Superglue service-account key | `superglue_tenant_accounts.api_key_encrypted` | One account per tenant; encrypted at rest |
| Provider OAuth/API credentials and Superglue system connections | Superglue tenant workspace | Credentials remain with Superglue; OAuth consent is granted by the customer |
| Database connection configuration | `db_connections.connection_string_encrypted` | Structured connection details encrypted at rest; read-only intent is recorded |
| Database schema metadata | `db_connections.schema_analysis` | Table/column/type metadata only; sample rows and values are not passed to agents |
| CRM analysis and recommendations | `crm_analysis_results` | Stores the analysis profile and recommended integrations/agents |
| Agent assignments and generated tool definitions | `ai_agent_assignments` | Stores tenant-scoped tool IDs, definitions, capabilities and verification status |
| In-flight Superglue calls and retry payloads | `superglue_call_queue` | Tenant-scoped; input JSON is encrypted at rest; successful calls are removed |
| Side-effect idempotency history | `ticket_tool_executions` | Stores tenant, ticket, tool, action and execution status; no raw customer payload |
| PARWA ticket and conversation records | Ticket/message tables | Local workflow copy used for routing, audit and response generation |

## 2. Connection and discovery flow

1. The CRM analyser reviews the tenant's ticket patterns and recommends the systems and agent capabilities needed to handle them.
2. The user chooses a recommended provider and completes the provider's OAuth consent flow or supplies a provider-issued API key. PARWA cannot grant OAuth consent on the user's behalf.
3. PARWA creates the provider system in Superglue and stores the connection under the tenant's Superglue service account. Empty or unverified credentials are not marked as connected.
4. For database integrations, PARWA stores the encrypted structured connection configuration and asks Superglue to discover the schema. A connection is not marked verified when schema discovery fails or only a generic fallback is available.
5. PARWA stores sanitized schema metadata. Agents receive table and column names/types, not cached customer rows. They query live records from the source system through generated tools when a ticket requires them.
6. The agent builder receives only verified tenant integrations and verified database schemas. Generated tools are checked using the tenant's Superglue key before the agent is marked active.

## 3. Ticket-solving flow

1. The ticket pipeline loads the tenant's connected integration inventory and discovered database schema.
2. The reasoning step chooses the relevant data source and tool. The generated tool's input schema is used to map ticket and CRM context into the exact required parameters.
3. If a required identifier or other input is missing, the tool is not called. The agent asks the customer for the missing information or routes the case for review.
4. Tool execution uses the tenant's Superglue service-account key and tenant-namespaced tool ID. There is no global-admin-key fallback for customer tool execution.
5. Safety checks classify the operation. Unknown actions are blocked; financial writes require a verified positive amount and approval; destructive actions require approval.
6. A tenant-scoped idempotency reservation is committed before the external side effect. An ambiguous or failed call retains its reservation so a retry cannot accidentally issue a second refund or duplicate a customer-visible update.
7. The Ticket Reply Specialist posts the customer-facing response to the original CRM ticket through Superglue. The Ticket Escalation Specialist adds a private/internal note and updates the ticket for human handoff. Legacy API-key CRM adapters remain a fallback where configured.

## 4. Tenant isolation and privacy controls

- Tenant IDs are derived from authenticated users for connection and agent-building endpoints; request-supplied tenant IDs cannot override the authenticated tenant.
- Superglue systems and tools are tenant-namespaced. Customer tool execution requires the tenant's own service-account key.
- Tenant RLS is applied to service-account records, call-queue records and tool-execution idempotency records. Worker sessions set tenant context or use the audited administrative recovery path.
- API credentials, database connection configuration and queued tool inputs are encrypted at rest.
- Tool error records store bounded status/error metadata rather than full upstream response bodies.
- Agents receive schema metadata and only the live records returned by a specific tool call. They do not receive a blanket database dump.

## 5. What still requires real production validation

Code-level checks cannot prove that a provider account is authorized, that a customer-specific CRM endpoint behaves as expected, or that every generated Superglue tool performs the intended side effect. Before describing PARWA as a human replacement, each supported provider needs sandbox end-to-end tests for OAuth/API-key setup, schema discovery, ticket lookup, the relevant action, customer reply, private escalation, retries, tenant isolation and audit records. Financial and destructive actions must also be tested against provider sandboxes with approval gates enabled.

OAuth providers require a customer consent step. API-key-only providers require the customer to supply a valid key. Unsupported providers or tools must remain pending rather than being shown as production-ready.
