export type AuthType = "bearer" | "header" | "query" | "basic" | "oauth2";

export interface AuthSchemaField {
  name: string;
  label: string;
  type: "text" | "password" | "email";
  required: boolean;
}

export interface AuthSchema {
  fields: AuthSchemaField[];
}

export interface TestConfig {
  method: string;
  url: string;
  headers?: Record<string, string>;
  auth?: { username: string; password: string };
  body?: string;
}

export interface Integration {
  id: string;
  name: string;
  category: string;
  auth_type: AuthType;
  auth_schema: AuthSchema;
  test_config: TestConfig;
  tier: number;
  description: string;
  industries: string[];
}

export const INTEGRATION_CATALOG: Integration[] = [
  // ===== CRM =====
  {
    id: "hubspot",
    name: "HubSpot",
    category: "crm",
    auth_type: "bearer",
    auth_schema: {
      fields: [{ name: "api_key", label: "HubSpot API Key", type: "password", required: true }],
    },
    test_config: {
      method: "GET",
      url: "https://api.hubapi.com/crm/v3/contacts?limit=1",
      headers: { Authorization: "Bearer {api_key}" },
    },
    tier: 1,
    description: "CRM platform for managing contacts, deals, and customer relationships",
    industries: ["saas", "ecommerce", "logistics", "other"],
  },
  {
    id: "salesforce",
    name: "Salesforce",
    category: "crm",
    auth_type: "bearer",
    auth_schema: {
      fields: [
        { name: "access_token", label: "Salesforce Access Token", type: "password", required: true },
        { name: "instance_url", label: "Instance URL", type: "text", required: true },
      ],
    },
    test_config: {
      method: "GET",
      url: "{instance_url}/services/data/v58.0/query?q=SELECT+Id+FROM+Account+LIMIT+1",
      headers: { Authorization: "Bearer {access_token}" },
    },
    tier: 1,
    description: "Enterprise CRM for sales, service, and marketing automation",
    industries: ["saas", "logistics", "other"],
  },
  {
    id: "pipedrive",
    name: "Pipedrive",
    category: "crm",
    auth_type: "query",
    auth_schema: {
      fields: [{ name: "api_token", label: "Pipedrive API Token", type: "password", required: true }],
    },
    test_config: {
      method: "GET",
      url: "https://api.pipedrive.com/v1/users/me?api_token={api_token}",
    },
    tier: 1,
    description: "Sales CRM for managing pipelines and deals",
    industries: ["saas", "other"],
  },
  // ===== E-commerce =====
  {
    id: "shopify",
    name: "Shopify",
    category: "ecommerce",
    auth_type: "header",
    auth_schema: {
      fields: [
        { name: "access_token", label: "Shopify Access Token", type: "password", required: true },
        { name: "shop_domain", label: "Shop Domain (e.g. mystore.myshopify.com)", type: "text", required: true },
      ],
    },
    test_config: {
      method: "GET",
      url: "https://{shop_domain}/admin/api/2024-01/shop.json",
      headers: { "X-Shopify-Access-Token": "{access_token}" },
    },
    tier: 1,
    description: "E-commerce platform for online stores and retail",
    industries: ["ecommerce", "other"],
  },
  {
    id: "woocommerce",
    name: "WooCommerce",
    category: "ecommerce",
    auth_type: "basic",
    auth_schema: {
      fields: [
        { name: "consumer_key", label: "Consumer Key", type: "password", required: true },
        { name: "consumer_secret", label: "Consumer Secret", type: "password", required: true },
        { name: "store_url", label: "Store URL", type: "text", required: true },
      ],
    },
    test_config: {
      method: "GET",
      url: "{store_url}/wp-json/wc/v3/system_status",
      auth: { username: "{consumer_key}", password: "{consumer_secret}" },
    },
    tier: 1,
    description: "WordPress-based e-commerce platform",
    industries: ["ecommerce", "other"],
  },
  {
    id: "bigcommerce",
    name: "BigCommerce",
    category: "ecommerce",
    auth_type: "bearer",
    auth_schema: {
      fields: [
        { name: "access_token", label: "BigCommerce Access Token", type: "password", required: true },
        { name: "store_hash", label: "Store Hash", type: "text", required: true },
      ],
    },
    test_config: {
      method: "GET",
      url: "https://api.bigcommerce.com/stores/{store_hash}/v2/store",
      headers: { "X-Auth-Token": "{access_token}", Accept: "application/json" },
    },
    tier: 1,
    description: "Enterprise e-commerce platform for growing businesses",
    industries: ["ecommerce", "other"],
  },
  // ===== Helpdesk =====
  {
    id: "zendesk",
    name: "Zendesk",
    category: "helpdesk",
    auth_type: "basic",
    auth_schema: {
      fields: [
        { name: "email", label: "Zendesk Email", type: "email", required: true },
        { name: "api_token", label: "API Token", type: "password", required: true },
        { name: "subdomain", label: "Subdomain", type: "text", required: true },
      ],
    },
    test_config: {
      method: "GET",
      url: "https://{subdomain}.zendesk.com/api/v2/tickets/count",
      auth: { username: "{email}/token", password: "{api_token}" },
    },
    tier: 1,
    description: "Customer support and ticketing platform",
    industries: ["saas", "ecommerce", "logistics", "other"],
  },
  {
    id: "freshdesk",
    name: "Freshdesk",
    category: "helpdesk",
    auth_type: "basic",
    auth_schema: {
      fields: [
        { name: "api_key", label: "Freshdesk API Key", type: "password", required: true },
        { name: "domain", label: "Domain (e.g. mycompany.freshdesk.com)", type: "text", required: true },
      ],
    },
    test_config: {
      method: "GET",
      url: "https://{domain}/api/v2/tickets?per_page=1",
      auth: { username: "{api_key}", password: "X" },
    },
    tier: 1,
    description: "Freshworks customer support platform",
    industries: ["saas", "logistics", "other"],
  },
  {
    id: "intercom",
    name: "Intercom",
    category: "helpdesk",
    auth_type: "bearer",
    auth_schema: {
      fields: [{ name: "access_token", label: "Intercom Access Token", type: "password", required: true }],
    },
    test_config: {
      method: "GET",
      url: "https://api.intercom.io/admins",
      headers: { Authorization: "Bearer {access_token}", Accept: "application/json" },
    },
    tier: 1,
    description: "Customer messaging and engagement platform",
    industries: ["saas", "other"],
  },
  {
    id: "gorgias",
    name: "Gorgias",
    category: "helpdesk",
    auth_type: "basic",
    auth_schema: {
      fields: [
        { name: "email", label: "Gorgias Email", type: "email", required: true },
        { name: "api_key", label: "API Key", type: "password", required: true },
        { name: "domain", label: "Domain (e.g. mycompany.gorgias.com)", type: "text", required: true },
      ],
    },
    test_config: {
      method: "GET",
      url: "https://{domain}/api/tickets/?limit=1",
      auth: { username: "{email}", password: "{api_key}" },
    },
    tier: 1,
    description: "E-commerce helpdesk with automation",
    industries: ["ecommerce", "other"],
  },
  // ===== Analytics =====
  {
    id: "mixpanel",
    name: "Mixpanel",
    category: "analytics",
    auth_type: "basic",
    auth_schema: {
      fields: [{ name: "api_secret", label: "Mixpanel API Secret", type: "password", required: true }],
    },
    test_config: {
      method: "GET",
      url: "https://mixpanel.com/api/2.0/engage?project_id=test",
      auth: { username: "{api_secret}", password: "" },
    },
    tier: 2,
    description: "Product analytics for user behavior tracking",
    industries: ["saas", "other"],
  },
  {
    id: "amplitude",
    name: "Amplitude",
    category: "analytics",
    auth_type: "bearer",
    auth_schema: {
      fields: [{ name: "api_key", label: "Amplitude API Key", type: "password", required: true }],
    },
    test_config: {
      method: "POST",
      url: "https://amplitude.com/api/2/userprivacy/deletion",
      headers: { Authorization: "Bearer {api_key}" },
    },
    tier: 2,
    description: "Digital analytics and product intelligence platform",
    industries: ["saas", "other"],
  },
  {
    id: "google_analytics",
    name: "Google Analytics",
    category: "analytics",
    auth_type: "oauth2",
    auth_schema: {
      fields: [
        { name: "access_token", label: "Google OAuth Access Token", type: "password", required: true },
        { name: "refresh_token", label: "Google OAuth Refresh Token", type: "password", required: true },
        { name: "property_id", label: "GA4 Property ID", type: "text", required: true },
      ],
    },
    test_config: {
      method: "GET",
      url: "https://analyticsdata.googleapis.com/v1beta/properties/{property_id}/metadata",
      headers: { Authorization: "Bearer {access_token}" },
    },
    tier: 2,
    description: "Web analytics and reporting platform",
    industries: ["ecommerce", "other"],
  },
  // ===== Email Marketing =====
  {
    id: "klaviyo",
    name: "Klaviyo",
    category: "email_marketing",
    auth_type: "bearer",
    auth_schema: {
      fields: [{ name: "api_key", label: "Klaviyo Private API Key", type: "password", required: true }],
    },
    test_config: {
      method: "GET",
      url: "https://a.klaviyo.com/api/profiles/?page[size]=1",
      headers: { Authorization: "Klaviyo-API-Key {api_key}", accept: "application/json", revision: "2024-02-15" },
    },
    tier: 2,
    description: "Email marketing and SMS platform for e-commerce",
    industries: ["ecommerce", "other"],
  },
  {
    id: "mailchimp",
    name: "Mailchimp",
    category: "email_marketing",
    auth_type: "bearer",
    auth_schema: {
      fields: [{ name: "api_key", label: "Mailchimp API Key", type: "password", required: true }],
    },
    test_config: {
      method: "GET",
      url: "https://us1.api.mailchimp.com/3.0/ping",
      headers: { Authorization: "Bearer {api_key}" },
    },
    tier: 2,
    description: "Email marketing and automation platform",
    industries: ["saas", "ecommerce", "other"],
  },
  {
    id: "brevo",
    name: "Brevo",
    category: "email_marketing",
    auth_type: "bearer",
    auth_schema: {
      fields: [{ name: "api_key", label: "Brevo API Key", type: "password", required: true }],
    },
    test_config: {
      method: "GET",
      url: "https://api.brevo.com/v3/account",
      headers: { "api-key": "{api_key}" },
    },
    tier: 2,
    description: "Email marketing, SMS, and CRM platform",
    industries: ["saas", "other"],
  },
  // ===== Payments =====
  {
    id: "stripe",
    name: "Stripe",
    category: "payments",
    auth_type: "bearer",
    auth_schema: {
      fields: [{ name: "api_key", label: "Stripe Secret Key", type: "password", required: true }],
    },
    test_config: {
      method: "GET",
      url: "https://api.stripe.com/v1/balance",
      headers: { Authorization: "Bearer {api_key}" },
    },
    tier: 1,
    description: "Online payment processing platform",
    industries: ["saas", "ecommerce", "logistics", "other"],
  },
  {
    id: "paddle",
    name: "Paddle",
    category: "payments",
    auth_type: "bearer",
    auth_schema: {
      fields: [{ name: "api_key", label: "Paddle API Key", type: "password", required: true }],
    },
    test_config: {
      method: "GET",
      url: "https://sandbox-api.paddle.com/transactions",
      headers: { Authorization: "Bearer {api_key}" },
    },
    tier: 1,
    description: "SaaS billing and payment platform",
    industries: ["saas", "other"],
  },
  {
    id: "paypal",
    name: "PayPal",
    category: "payments",
    auth_type: "oauth2",
    auth_schema: {
      fields: [
        { name: "client_id", label: "PayPal Client ID", type: "text", required: true },
        { name: "client_secret", label: "PayPal Client Secret", type: "password", required: true },
      ],
    },
    test_config: {
      method: "POST",
      url: "https://api-m.sandbox.paypal.com/v1/oauth2/token",
      auth: { username: "{client_id}", password: "{client_secret}" },
    },
    tier: 1,
    description: "Global online payment platform",
    industries: ["ecommerce", "other"],
  },
  // ===== Dev Tools =====
  {
    id: "github",
    name: "GitHub",
    category: "dev_tools",
    auth_type: "bearer",
    auth_schema: {
      fields: [{ name: "api_key", label: "GitHub Personal Access Token", type: "password", required: true }],
    },
    test_config: {
      method: "GET",
      url: "https://api.github.com/user",
      headers: { Authorization: "Bearer {api_key}" },
    },
    tier: 2,
    description: "Code hosting and collaboration platform",
    industries: ["saas", "other"],
  },
  {
    id: "jira",
    name: "Jira",
    category: "dev_tools",
    auth_type: "basic",
    auth_schema: {
      fields: [
        { name: "email", label: "Atlassian Email", type: "email", required: true },
        { name: "api_token", label: "API Token", type: "password", required: true },
        { name: "domain", label: "Domain (e.g. mycompany.atlassian.net)", type: "text", required: true },
      ],
    },
    test_config: {
      method: "GET",
      url: "https://{domain}/rest/api/3/myself",
      auth: { username: "{email}", password: "{api_token}" },
    },
    tier: 2,
    description: "Project management and issue tracking",
    industries: ["saas", "other"],
  },
  {
    id: "linear",
    name: "Linear",
    category: "dev_tools",
    auth_type: "bearer",
    auth_schema: {
      fields: [{ name: "api_key", label: "Linear API Key", type: "password", required: true }],
    },
    test_config: {
      method: "POST",
      url: "https://api.linear.app/graphql",
      headers: { Authorization: "{api_key}" },
      body: '{"query": "{ viewer { id } }"}',
    },
    tier: 2,
    description: "Modern project management for software teams",
    industries: ["saas", "other"],
  },
  // ===== Shipping =====
  {
    id: "shipstation",
    name: "ShipStation",
    category: "shipping",
    auth_type: "basic",
    auth_schema: {
      fields: [
        { name: "api_key", label: "ShipStation API Key", type: "password", required: true },
        { name: "api_secret", label: "ShipStation API Secret", type: "password", required: true },
      ],
    },
    test_config: {
      method: "GET",
      url: "https://ssapi.shipstation.com/orders?pageSize=1",
      auth: { username: "{api_key}", password: "{api_secret}" },
    },
    tier: 1,
    description: "Shipping and order fulfillment platform",
    industries: ["ecommerce", "logistics", "other"],
  },
  {
    id: "aftership",
    name: "AfterShip",
    category: "shipping",
    auth_type: "bearer",
    auth_schema: {
      fields: [{ name: "api_key", label: "AfterShip API Key", type: "password", required: true }],
    },
    test_config: {
      method: "GET",
      url: "https://api.aftership.com/v4/couriers",
      headers: { "aftership-api-key": "{api_key}" },
    },
    tier: 1,
    description: "Shipment tracking and notification platform",
    industries: ["ecommerce", "logistics", "other"],
  },
  {
    id: "easypost",
    name: "EasyPost",
    category: "shipping",
    auth_type: "bearer",
    auth_schema: {
      fields: [{ name: "api_key", label: "EasyPost API Key", type: "password", required: true }],
    },
    test_config: {
      method: "GET",
      url: "https://api.easypost.com/v2/users",
    },
    tier: 1,
    description: "Shipping API and logistics platform",
    industries: ["logistics", "other"],
  },
  {
    id: "fedex",
    name: "FedEx",
    category: "shipping",
    auth_type: "oauth2",
    auth_schema: {
      fields: [
        { name: "client_id", label: "FedEx Client ID", type: "text", required: true },
        { name: "client_secret", label: "FedEx Client Secret", type: "password", required: true },
      ],
    },
    test_config: {
      method: "POST",
      url: "https://apis-sandbox.fedex.com/oauth/token",
      body: "grant_type=client_credentials&client_id={client_id}&client_secret={client_secret}",
    },
    tier: 1,
    description: "FedEx shipping and logistics services",
    industries: ["logistics", "other"],
  },
  {
    id: "ups",
    name: "UPS",
    category: "shipping",
    auth_type: "oauth2",
    auth_schema: {
      fields: [
        { name: "client_id", label: "UPS Client ID", type: "text", required: true },
        { name: "client_secret", label: "UPS Client Secret", type: "password", required: true },
      ],
    },
    test_config: {
      method: "POST",
      url: "https://wwwcie.ups.com/security/v1/oauth/token",
      body: "grant_type=client_credentials",
      headers: { Authorization: "Basic {base64(client_id:client_secret)}" },
    },
    tier: 1,
    description: "UPS shipping and logistics services",
    industries: ["logistics", "other"],
  },
  {
    id: "dhl",
    name: "DHL",
    category: "shipping",
    auth_type: "bearer",
    auth_schema: {
      fields: [{ name: "api_key", label: "DHL API Key", type: "password", required: true }],
    },
    test_config: {
      method: "GET",
      url: "https://api.dhl.com/location-finder/v1/find-by-address?countryCode=US",
      headers: { "DHL-API-Key": "{api_key}" },
    },
    tier: 1,
    description: "DHL shipping and logistics services",
    industries: ["logistics", "other"],
  },
  // ===== Communication =====
  {
    id: "slack",
    name: "Slack",
    category: "communication",
    auth_type: "bearer",
    auth_schema: {
      fields: [{ name: "bot_token", label: "Slack Bot Token (xoxb-...)", type: "password", required: true }],
    },
    test_config: {
      method: "GET",
      url: "https://slack.com/api/auth.test",
      headers: { Authorization: "Bearer {bot_token}" },
    },
    tier: 1,
    description: "Team communication and collaboration platform",
    industries: ["saas", "ecommerce", "logistics", "other"],
  },
  {
    id: "notion",
    name: "Notion",
    category: "communication",
    auth_type: "bearer",
    auth_schema: {
      fields: [{ name: "api_key", label: "Notion Integration Token", type: "password", required: true }],
    },
    test_config: {
      method: "GET",
      url: "https://api.notion.com/v1/users/me",
      headers: { Authorization: "Bearer {api_key}", "Notion-Version": "2022-06-28" },
    },
    tier: 2,
    description: "All-in-one workspace for notes, docs, and collaboration",
    industries: ["saas", "other"],
  },
];

export const CATEGORY_LABELS: Record<string, string> = {
  crm: "CRM",
  ecommerce: "E-commerce",
  helpdesk: "Helpdesk",
  analytics: "Analytics",
  email_marketing: "Email Marketing",
  payments: "Payments",
  dev_tools: "Dev Tools",
  shipping: "Shipping",
  communication: "Communication",
};

export const CATEGORY_ICONS: Record<string, string> = {
  crm: "Users",
  ecommerce: "ShoppingCart",
  helpdesk: "HeadphonesIcon",
  analytics: "BarChart3",
  email_marketing: "Mail",
  payments: "CreditCard",
  dev_tools: "Code2",
  shipping: "Truck",
  communication: "MessageSquare",
};

export function getIntegrationsByIndustry(industry: string): Integration[] {
  if (!industry || industry === "other") return INTEGRATION_CATALOG;
  return INTEGRATION_CATALOG.filter((i) => i.industries.includes(industry));
}

export function getIntegrationsByCategory(category: string): Integration[] {
  return INTEGRATION_CATALOG.filter((i) => i.category === category);
}

export function getIntegrationById(id: string): Integration | undefined {
  return INTEGRATION_CATALOG.find((i) => i.id === id);
}

export function getCategories(): string[] {
  return [...new Set(INTEGRATION_CATALOG.map((i) => i.category))];
}
