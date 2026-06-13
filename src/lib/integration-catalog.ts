/**
 * PARWA Unified Integration Catalog
 *
 * SINGLE SOURCE OF TRUTH for all integration metadata.
 * Used by: Onboarding IntegrationStep, Settings Integrations tab, BFF routes.
 *
 * Per D2: All variants get UNLIMITED integrations.
 * Per D4: Three integration tiers — Pre-built, OpenAPI Import, Custom REST.
 * Per D6: Each integration has a pre-written HTTP test call (NO AI).
 * Per GAP 2: Universal API key system with 5 auth types.
 * Per GAP 3: Full catalog per industry (suggestions, not restrictions).
 */

// ── Auth Types (GAP 2) ──────────────────────────────────────────────────

export type AuthType = 'bearer' | 'api_key_header' | 'api_key_query' | 'basic_auth' | 'oauth2';

export interface AuthField {
  name: string;
  label: string;
  type: 'text' | 'password' | 'url';
  required: boolean;
  placeholder?: string;
}

export interface AuthSchema {
  type: AuthType;
  fields: AuthField[];
  /** Header name for api_key_header auth */
  headerName?: string;
  /** Query param name for api_key_query auth */
  queryParamName?: string;
  /** OAuth2 redirect URI */
  redirectUri?: string;
}

// ── Integration Category ────────────────────────────────────────────────

export type IntegrationCategory =
  | 'crm'
  | 'ecommerce'
  | 'helpdesk'
  | 'communication'
  | 'analytics'
  | 'marketing'
  | 'payments'
  | 'shipping'
  | 'dev_tools'
  | 'productivity'
  | 'custom';

// ── Integration Tier (D4) ──────────────────────────────────────────────

export type IntegrationTier = 'tier1_prebuilt' | 'tier2_openapi' | 'tier3_custom';

// ── Industry (D1 — 4 industries only) ──────────────────────────────────

export type ParwaIndustry = 'saas' | 'ecommerce' | 'logistics' | 'other';

// ── Integration Definition ─────────────────────────────────────────────

export interface IntegrationDefinition {
  /** Machine key — also used as integration_type in DB */
  key: string;
  /** Display name */
  name: string;
  /** Short description for UI */
  description: string;
  /** Category for grouping in UI */
  category: IntegrationCategory;
  /** Which tier this belongs to */
  tier: IntegrationTier;
  /** Auth schema — defines the credential form (GAP 2) */
  authSchema: AuthSchema;
  /** Pre-written test call (D6 — NO AI) */
  testConnection: {
    method: 'GET' | 'POST';
    /** URL template — {field_name} replaced with credential values */
    urlTemplate: string;
    /** Header template — {field_name} replaced with credential values */
    headersTemplate?: Record<string, string>;
    /** How to interpret the response */
    successCheck: 'status_200' | 'json_ok_true' | 'status_200_or_201';
    /** What to show on success — {response_json_path} for dynamic values */
    successMessage?: string;
  };
  /** Industries where this integration is SUGGESTED (not restricted to) */
  suggestedIndustries: ParwaIndustry[];
  /** Which variants can use this (empty = all) */
  availableForVariants?: ('mini_parwa' | 'parwa' | 'parwa_high')[];
  /** Icon identifier for frontend rendering */
  iconId: string;
  /** Icon color gradient for frontend */
  colorGradient: string;
  /** Whether this integration is available */
  available: boolean;
}

// ── The Unified Catalog ────────────────────────────────────────────────

export const INTEGRATION_CATALOG: IntegrationDefinition[] = [
  // ─── CRM ───────────────────────────────────────────────────────
  {
    key: 'hubspot',
    name: 'HubSpot',
    description: 'Look up customers, deals, and contact info from HubSpot CRM.',
    category: 'crm',
    tier: 'tier1_prebuilt',
    authSchema: {
      type: 'bearer',
      fields: [
        { name: 'api_key', label: 'HubSpot API Key', type: 'password', required: true, placeholder: 'pat-xxx-xxx' },
      ],
    },
    testConnection: {
      method: 'GET',
      urlTemplate: 'https://api.hubapi.com/crm/v3/contacts?limit=1',
      headersTemplate: { 'Authorization': 'Bearer {api_key}' },
      successCheck: 'status_200',
      successMessage: 'Connected to HubSpot CRM',
    },
    suggestedIndustries: ['saas', 'ecommerce', 'logistics', 'other'],
    iconId: 'hubspot',
    colorGradient: 'from-orange-500 to-orange-400',
    available: true,
  },
  {
    key: 'salesforce',
    name: 'Salesforce',
    description: 'Access customer records, opportunities, and cases from Salesforce.',
    category: 'crm',
    tier: 'tier1_prebuilt',
    authSchema: {
      type: 'oauth2',
      fields: [
        { name: 'client_id', label: 'Consumer Key', type: 'text', required: true, placeholder: '3MVG9...' },
        { name: 'client_secret', label: 'Consumer Secret', type: 'password', required: true },
        { name: 'instance_url', label: 'Instance URL', type: 'url', required: true, placeholder: 'https://na1.salesforce.com' },
        { name: 'refresh_token', label: 'Refresh Token', type: 'password', required: true },
      ],
    },
    testConnection: {
      method: 'GET',
      urlTemplate: '{instance_url}/services/data/v60.0/',
      headersTemplate: { 'Authorization': 'Bearer {refresh_token}' },
      successCheck: 'status_200',
      successMessage: 'Connected to Salesforce',
    },
    suggestedIndustries: ['saas', 'logistics', 'other'],
    iconId: 'salesforce',
    colorGradient: 'from-blue-500 to-blue-400',
    available: true,
  },
  {
    key: 'pipedrive',
    name: 'Pipedrive',
    description: 'Manage deals, contacts, and pipelines from Pipedrive CRM.',
    category: 'crm',
    tier: 'tier1_prebuilt',
    authSchema: {
      type: 'api_key_query',
      fields: [
        { name: 'api_token', label: 'API Token', type: 'password', required: true, placeholder: 'xxx123abc' },
        { name: 'company_domain', label: 'Company Domain', type: 'text', required: true, placeholder: 'yourcompany' },
      ],
    },
    testConnection: {
      method: 'GET',
      urlTemplate: 'https://{company_domain}.pipedrive.com/api/v1/users/me?api_token={api_token}',
      successCheck: 'json_ok_true',
      successMessage: 'Connected to Pipedrive',
    },
    suggestedIndustries: ['saas', 'other'],
    iconId: 'pipedrive',
    colorGradient: 'from-green-500 to-green-400',
    available: true,
  },

  // ─── ECOMMERCE ─────────────────────────────────────────────────
  {
    key: 'shopify',
    name: 'Shopify',
    description: 'Look up orders, products, and inventory from your Shopify store.',
    category: 'ecommerce',
    tier: 'tier1_prebuilt',
    authSchema: {
      type: 'api_key_header',
      fields: [
        { name: 'store_url', label: 'Store URL', type: 'url', required: true, placeholder: 'your-store.myshopify.com' },
        { name: 'access_token', label: 'Access Token', type: 'password', required: true, placeholder: 'shpat_xxx' },
      ],
      headerName: 'X-Shopify-Access-Token',
    },
    testConnection: {
      method: 'GET',
      urlTemplate: 'https://{store_url}/admin/api/2024-01/shop.json',
      headersTemplate: { 'X-Shopify-Access-Token': '{access_token}' },
      successCheck: 'status_200',
      successMessage: 'Connected to Shopify store',
    },
    suggestedIndustries: ['ecommerce', 'other'],
    iconId: 'shopify',
    colorGradient: 'from-green-500 to-emerald-400',
    available: true,
  },
  {
    key: 'woocommerce',
    name: 'WooCommerce',
    description: 'Access orders, products, and customers from your WooCommerce store.',
    category: 'ecommerce',
    tier: 'tier1_prebuilt',
    authSchema: {
      type: 'basic_auth',
      fields: [
        { name: 'store_url', label: 'Store URL', type: 'url', required: true, placeholder: 'https://yourstore.com' },
        { name: 'consumer_key', label: 'Consumer Key', type: 'text', required: true, placeholder: 'ck_xxx' },
        { name: 'consumer_secret', label: 'Consumer Secret', type: 'password', required: true, placeholder: 'cs_xxx' },
      ],
    },
    testConnection: {
      method: 'GET',
      urlTemplate: '{store_url}/wp-json/wc/v3/system_status',
      successCheck: 'status_200',
      successMessage: 'Connected to WooCommerce',
    },
    suggestedIndustries: ['ecommerce', 'other'],
    iconId: 'woocommerce',
    colorGradient: 'from-purple-500 to-purple-400',
    available: true,
  },
  {
    key: 'bigcommerce',
    name: 'BigCommerce',
    description: 'Manage products, orders, and customers from your BigCommerce store.',
    category: 'ecommerce',
    tier: 'tier1_prebuilt',
    authSchema: {
      type: 'api_key_header',
      fields: [
        { name: 'store_hash', label: 'Store Hash', type: 'text', required: true, placeholder: 'abc123' },
        { name: 'access_token', label: 'Access Token', type: 'password', required: true, placeholder: 'xxx' },
      ],
      headerName: 'X-Auth-Token',
    },
    testConnection: {
      method: 'GET',
      urlTemplate: 'https://api.bigcommerce.com/stores/{store_hash}/v2/store',
      headersTemplate: { 'X-Auth-Token': '{access_token}', 'Accept': 'application/json' },
      successCheck: 'status_200',
      successMessage: 'Connected to BigCommerce',
    },
    suggestedIndustries: ['ecommerce', 'other'],
    iconId: 'bigcommerce',
    colorGradient: 'from-indigo-500 to-indigo-400',
    available: true,
  },

  // ─── HELPDESK ──────────────────────────────────────────────────
  {
    key: 'zendesk',
    name: 'Zendesk',
    description: 'Manage tickets, contacts, and knowledge base from Zendesk.',
    category: 'helpdesk',
    tier: 'tier1_prebuilt',
    authSchema: {
      type: 'basic_auth',
      fields: [
        { name: 'subdomain', label: 'Subdomain', type: 'text', required: true, placeholder: 'your-company' },
        { name: 'email', label: 'Email', type: 'text', required: true, placeholder: 'admin@company.com' },
        { name: 'api_token', label: 'API Token', type: 'password', required: true, placeholder: 'zendesk_api_token' },
      ],
    },
    testConnection: {
      method: 'GET',
      urlTemplate: 'https://{subdomain}.zendesk.com/api/v2/users/me.json',
      successCheck: 'status_200',
      successMessage: 'Connected to Zendesk',
    },
    suggestedIndustries: ['saas', 'ecommerce', 'logistics', 'other'],
    iconId: 'zendesk',
    colorGradient: 'from-green-500 to-green-400',
    available: true,
  },
  {
    key: 'freshdesk',
    name: 'Freshdesk',
    description: 'Access tickets, contacts, and solutions from Freshdesk.',
    category: 'helpdesk',
    tier: 'tier1_prebuilt',
    authSchema: {
      type: 'basic_auth',
      fields: [
        { name: 'domain', label: 'Domain', type: 'text', required: true, placeholder: 'yourcompany' },
        { name: 'api_key', label: 'API Key', type: 'password', required: true, placeholder: 'freshdesk_api_key' },
      ],
    },
    testConnection: {
      method: 'GET',
      urlTemplate: 'https://{domain}.freshdesk.com/api/v2/agents/me',
      successCheck: 'status_200',
      successMessage: 'Connected to Freshdesk',
    },
    suggestedIndustries: ['saas', 'logistics', 'other'],
    iconId: 'freshdesk',
    colorGradient: 'from-blue-500 to-blue-400',
    available: true,
  },
  {
    key: 'intercom',
    name: 'Intercom',
    description: 'Access conversations, contacts, and help center from Intercom.',
    category: 'helpdesk',
    tier: 'tier1_prebuilt',
    authSchema: {
      type: 'bearer',
      fields: [
        { name: 'access_token', label: 'Access Token', type: 'password', required: true, placeholder: 'dG9rZW4...' },
      ],
    },
    testConnection: {
      method: 'GET',
      urlTemplate: 'https://api.intercom.io/me',
      headersTemplate: { 'Authorization': 'Bearer {access_token}', 'Accept': 'application/json' },
      successCheck: 'status_200',
      successMessage: 'Connected to Intercom',
    },
    suggestedIndustries: ['saas', 'other'],
    iconId: 'intercom',
    colorGradient: 'from-blue-600 to-blue-500',
    available: true,
  },
  {
    key: 'gorgias',
    name: 'Gorgias',
    description: 'Manage e-commerce support tickets from Gorgias.',
    category: 'helpdesk',
    tier: 'tier1_prebuilt',
    authSchema: {
      type: 'basic_auth',
      fields: [
        { name: 'domain', label: 'Domain', type: 'text', required: true, placeholder: 'yourcompany' },
        { name: 'email', label: 'Email', type: 'text', required: true, placeholder: 'admin@company.com' },
        { name: 'api_key', label: 'API Key', type: 'password', required: true },
      ],
    },
    testConnection: {
      method: 'GET',
      urlTemplate: 'https://{domain}.gorgias.com/api/users/me',
      successCheck: 'status_200',
      successMessage: 'Connected to Gorgias',
    },
    suggestedIndustries: ['ecommerce', 'other'],
    iconId: 'gorgias',
    colorGradient: 'from-teal-500 to-teal-400',
    available: true,
  },

  // ─── COMMUNICATION ─────────────────────────────────────────────
  {
    key: 'slack',
    name: 'Slack',
    description: 'Receive alerts, manage tickets, and respond from Slack.',
    category: 'communication',
    tier: 'tier1_prebuilt',
    authSchema: {
      type: 'bearer',
      fields: [
        { name: 'bot_token', label: 'Bot Token', type: 'password', required: true, placeholder: 'xoxb-xxx' },
      ],
    },
    testConnection: {
      method: 'POST',
      urlTemplate: 'https://slack.com/api/auth.test',
      headersTemplate: { 'Authorization': 'Bearer {bot_token}' },
      successCheck: 'json_ok_true',
      successMessage: 'Connected to Slack workspace',
    },
    suggestedIndustries: ['saas', 'ecommerce', 'logistics', 'other'],
    iconId: 'slack',
    colorGradient: 'from-purple-500 to-purple-400',
    available: true,
  },
  {
    key: 'gmail',
    name: 'Gmail',
    description: 'Sync email conversations and auto-respond via AI.',
    category: 'communication',
    tier: 'tier1_prebuilt',
    authSchema: {
      type: 'oauth2',
      fields: [
        { name: 'client_id', label: 'Client ID', type: 'text', required: true, placeholder: 'xxx.apps.googleusercontent.com' },
        { name: 'client_secret', label: 'Client Secret', type: 'password', required: true },
        { name: 'refresh_token', label: 'Refresh Token', type: 'password', required: true },
      ],
    },
    testConnection: {
      method: 'GET',
      urlTemplate: 'https://www.googleapis.com/gmail/v1/users/me/profile',
      headersTemplate: { 'Authorization': 'Bearer {refresh_token}' },
      successCheck: 'status_200',
      successMessage: 'Connected to Gmail',
    },
    suggestedIndustries: ['saas', 'ecommerce', 'logistics', 'other'],
    iconId: 'gmail',
    colorGradient: 'from-red-500 to-red-400',
    available: true,
  },

  // ─── ANALYTICS ─────────────────────────────────────────────────
  {
    key: 'mixpanel',
    name: 'Mixpanel',
    description: 'Query user events and analytics data from Mixpanel.',
    category: 'analytics',
    tier: 'tier1_prebuilt',
    authSchema: {
      type: 'basic_auth',
      fields: [
        { name: 'api_secret', label: 'API Secret', type: 'password', required: true },
      ],
    },
    testConnection: {
      method: 'GET',
      urlTemplate: 'https://mixpanel.com/api/2.0/engage?project_id=0',
      headersTemplate: {},
      successCheck: 'status_200_or_201',
      successMessage: 'Connected to Mixpanel',
    },
    suggestedIndustries: ['saas', 'other'],
    iconId: 'mixpanel',
    colorGradient: 'from-blue-500 to-indigo-400',
    available: true,
  },
  {
    key: 'amplitude',
    name: 'Amplitude',
    description: 'Access product analytics and user behavior data from Amplitude.',
    category: 'analytics',
    tier: 'tier1_prebuilt',
    authSchema: {
      type: 'api_key_header',
      headerName: 'Authorization',
      fields: [
        { name: 'api_key', label: 'API Key', type: 'text', required: true },
        { name: 'secret_key', label: 'Secret Key', type: 'password', required: true },
      ],
    },
    testConnection: {
      method: 'GET',
      urlTemplate: 'https://amplitude.com/api/2/usersearch?user=test',
      successCheck: 'status_200',
      successMessage: 'Connected to Amplitude',
    },
    suggestedIndustries: ['saas', 'other'],
    iconId: 'amplitude',
    colorGradient: 'from-blue-600 to-blue-500',
    available: true,
  },
  {
    key: 'google_analytics',
    name: 'Google Analytics',
    description: 'Access traffic, conversion, and user data from Google Analytics.',
    category: 'analytics',
    tier: 'tier1_prebuilt',
    authSchema: {
      type: 'oauth2',
      fields: [
        { name: 'client_id', label: 'Client ID', type: 'text', required: true },
        { name: 'client_secret', label: 'Client Secret', type: 'password', required: true },
        { name: 'refresh_token', label: 'Refresh Token', type: 'password', required: true },
      ],
    },
    testConnection: {
      method: 'GET',
      urlTemplate: 'https://analyticsreporting.googleapis.com/v4/userActivity:search',
      headersTemplate: { 'Authorization': 'Bearer {refresh_token}' },
      successCheck: 'status_200',
      successMessage: 'Connected to Google Analytics',
    },
    suggestedIndustries: ['ecommerce', 'other'],
    iconId: 'google-analytics',
    colorGradient: 'from-orange-500 to-yellow-400',
    available: true,
  },

  // ─── MARKETING ─────────────────────────────────────────────────
  {
    key: 'mailchimp',
    name: 'Mailchimp',
    description: 'Access subscribers, campaigns, and automation data.',
    category: 'marketing',
    tier: 'tier1_prebuilt',
    authSchema: {
      type: 'bearer',
      fields: [
        { name: 'api_key', label: 'API Key', type: 'password', required: true, placeholder: 'xxx-us1' },
      ],
    },
    testConnection: {
      method: 'GET',
      urlTemplate: 'https://us1.api.mailchimp.com/3.0/',
      headersTemplate: { 'Authorization': 'Bearer {api_key}' },
      successCheck: 'status_200',
      successMessage: 'Connected to Mailchimp',
    },
    suggestedIndustries: ['ecommerce', 'other'],
    iconId: 'mailchimp',
    colorGradient: 'from-yellow-500 to-yellow-400',
    available: true,
  },
  {
    key: 'klaviyo',
    name: 'Klaviyo',
    description: 'Access email marketing, flows, and customer data from Klaviyo.',
    category: 'marketing',
    tier: 'tier1_prebuilt',
    authSchema: {
      type: 'api_key_query',
      fields: [
        { name: 'private_api_key', label: 'Private API Key', type: 'password', required: true },
      ],
      queryParamName: 'api_key',
    },
    testConnection: {
      method: 'GET',
      urlTemplate: 'https://a.klaviyo.com/api/accounts/?api_key={private_api_key}',
      headersTemplate: { 'Accept': 'application/json' },
      successCheck: 'status_200',
      successMessage: 'Connected to Klaviyo',
    },
    suggestedIndustries: ['ecommerce', 'other'],
    iconId: 'klaviyo',
    colorGradient: 'from-green-600 to-green-500',
    available: true,
  },
  {
    key: 'brevo',
    name: 'Brevo',
    description: 'Send transactional emails and manage contacts via Brevo.',
    category: 'marketing',
    tier: 'tier1_prebuilt',
    authSchema: {
      type: 'bearer',
      fields: [
        { name: 'api_key', label: 'API Key', type: 'password', required: true, placeholder: 'xkeysib-xxx' },
      ],
    },
    testConnection: {
      method: 'GET',
      urlTemplate: 'https://api.brevo.com/v3/account',
      headersTemplate: { 'api-key': '{api_key}' },
      successCheck: 'status_200',
      successMessage: 'Connected to Brevo',
    },
    suggestedIndustries: ['ecommerce', 'saas', 'other'],
    iconId: 'brevo',
    colorGradient: 'from-blue-500 to-blue-400',
    available: true,
  },

  // ─── PAYMENTS ──────────────────────────────────────────────────
  {
    key: 'stripe',
    name: 'Stripe',
    description: 'Access payments, subscriptions, and customer billing data.',
    category: 'payments',
    tier: 'tier1_prebuilt',
    authSchema: {
      type: 'bearer',
      fields: [
        { name: 'api_key', label: 'Secret Key', type: 'password', required: true, placeholder: 'sk_live_xxx' },
      ],
    },
    testConnection: {
      method: 'GET',
      urlTemplate: 'https://api.stripe.com/v1/balance',
      headersTemplate: { 'Authorization': 'Bearer {api_key}' },
      successCheck: 'status_200',
      successMessage: 'Connected to Stripe',
    },
    suggestedIndustries: ['saas', 'ecommerce', 'other'],
    iconId: 'stripe',
    colorGradient: 'from-indigo-500 to-indigo-400',
    available: true,
  },
  {
    key: 'paddle',
    name: 'Paddle',
    description: 'Access subscriptions, transactions, and pricing data from Paddle.',
    category: 'payments',
    tier: 'tier1_prebuilt',
    authSchema: {
      type: 'bearer',
      fields: [
        { name: 'api_key', label: 'API Key', type: 'password', required: true, placeholder: 'pd_live_xxx' },
      ],
    },
    testConnection: {
      method: 'GET',
      urlTemplate: 'https://sandbox-api.paddle.com/transactions',
      headersTemplate: { 'Authorization': 'Bearer {api_key}' },
      successCheck: 'status_200',
      successMessage: 'Connected to Paddle',
    },
    suggestedIndustries: ['saas', 'other'],
    iconId: 'paddle',
    colorGradient: 'from-cyan-500 to-cyan-400',
    available: true,
  },
  {
    key: 'paypal',
    name: 'PayPal',
    description: 'Access transactions, refunds, and dispute data from PayPal.',
    category: 'payments',
    tier: 'tier1_prebuilt',
    authSchema: {
      type: 'oauth2',
      fields: [
        { name: 'client_id', label: 'Client ID', type: 'text', required: true },
        { name: 'client_secret', label: 'Client Secret', type: 'password', required: true },
        { name: 'base_url', label: 'Base URL', type: 'url', required: true, placeholder: 'https://api-m.paypal.com' },
      ],
    },
    testConnection: {
      method: 'GET',
      urlTemplate: '{base_url}/v1/identity/oauth2/userinfo?schema=paypalv1.1',
      successCheck: 'status_200',
      successMessage: 'Connected to PayPal',
    },
    suggestedIndustries: ['ecommerce', 'other'],
    iconId: 'paypal',
    colorGradient: 'from-blue-600 to-blue-500',
    available: true,
  },

  // ─── SHIPPING ──────────────────────────────────────────────────
  {
    key: 'shipstation',
    name: 'ShipStation',
    description: 'Access shipments, orders, and fulfillment data from ShipStation.',
    category: 'shipping',
    tier: 'tier1_prebuilt',
    authSchema: {
      type: 'basic_auth',
      fields: [
        { name: 'api_key', label: 'API Key', type: 'text', required: true },
        { name: 'api_secret', label: 'API Secret', type: 'password', required: true },
      ],
    },
    testConnection: {
      method: 'GET',
      urlTemplate: 'https://ssapi.shipstation.com/stores',
      successCheck: 'status_200',
      successMessage: 'Connected to ShipStation',
    },
    suggestedIndustries: ['ecommerce', 'logistics', 'other'],
    iconId: 'shipstation',
    colorGradient: 'from-blue-500 to-blue-400',
    available: true,
  },
  {
    key: 'aftership',
    name: 'AfterShip',
    description: 'Track shipments and delivery status across carriers via AfterShip.',
    category: 'shipping',
    tier: 'tier1_prebuilt',
    authSchema: {
      type: 'bearer',
      fields: [
        { name: 'api_key', label: 'API Key', type: 'password', required: true, placeholder: 'as_xxx' },
      ],
    },
    testConnection: {
      method: 'GET',
      urlTemplate: 'https://api.aftership.com/v4/couriers',
      headersTemplate: { 'aftership-api-key': '{api_key}' },
      successCheck: 'status_200',
      successMessage: 'Connected to AfterShip',
    },
    suggestedIndustries: ['ecommerce', 'logistics', 'other'],
    iconId: 'aftership',
    colorGradient: 'from-teal-500 to-teal-400',
    available: true,
  },
  {
    key: 'easypost',
    name: 'EasyPost',
    description: 'Generate labels, verify addresses, and track packages via EasyPost.',
    category: 'shipping',
    tier: 'tier1_prebuilt',
    authSchema: {
      type: 'bearer',
      fields: [
        { name: 'api_key', label: 'API Key', type: 'password', required: true, placeholder: 'EZAK_xxx' },
      ],
    },
    testConnection: {
      method: 'GET',
      urlTemplate: 'https://api.easypost.com/v2/users',
      headersTemplate: { 'Authorization': 'Bearer {api_key}' },
      successCheck: 'status_200',
      successMessage: 'Connected to EasyPost',
    },
    suggestedIndustries: ['logistics', 'other'],
    iconId: 'easypost',
    colorGradient: 'from-green-500 to-green-400',
    available: true,
  },
  {
    key: 'fedex',
    name: 'FedEx',
    description: 'Track shipments, get rates, and manage deliveries via FedEx API.',
    category: 'shipping',
    tier: 'tier1_prebuilt',
    authSchema: {
      type: 'bearer',
      fields: [
        { name: 'api_key', label: 'API Key', type: 'text', required: true, placeholder: 'l7xx...' },
        { name: 'secret_key', label: 'Secret Key', type: 'password', required: true },
      ],
    },
    testConnection: {
      method: 'POST',
      urlTemplate: 'https://apis.fedex.com/oauth/token',
      headersTemplate: { 'Content-Type': 'application/x-www-form-urlencoded' },
      successCheck: 'status_200',
      successMessage: 'Connected to FedEx',
    },
    suggestedIndustries: ['logistics', 'other'],
    iconId: 'fedex',
    colorGradient: 'from-purple-600 to-purple-500',
    available: true,
  },
  {
    key: 'ups',
    name: 'UPS',
    description: 'Track packages, get shipping rates, and validate addresses via UPS API.',
    category: 'shipping',
    tier: 'tier1_prebuilt',
    authSchema: {
      type: 'oauth2',
      fields: [
        { name: 'client_id', label: 'Client ID', type: 'text', required: true, placeholder: 'xxx' },
        { name: 'client_secret', label: 'Client Secret', type: 'password', required: true },
      ],
    },
    testConnection: {
      method: 'POST',
      urlTemplate: 'https://onlinetools.ups.com/security/v1/oauth/token',
      successCheck: 'status_200',
      successMessage: 'Connected to UPS',
    },
    suggestedIndustries: ['logistics', 'other'],
    iconId: 'ups',
    colorGradient: 'from-amber-600 to-amber-500',
    available: true,
  },
  {
    key: 'dhl',
    name: 'DHL',
    description: 'Track shipments and get delivery updates via DHL API.',
    category: 'shipping',
    tier: 'tier1_prebuilt',
    authSchema: {
      type: 'bearer',
      fields: [
        { name: 'api_key', label: 'DHL API Key', type: 'password', required: true, placeholder: 'demo-key' },
      ],
    },
    testConnection: {
      method: 'GET',
      urlTemplate: 'https://api-eu.dhl.com/track/shipments?trackingNumber=0',
      headersTemplate: { 'DHL-API-Key': '{api_key}' },
      successCheck: 'status_200',
      successMessage: 'Connected to DHL',
    },
    suggestedIndustries: ['logistics', 'other'],
    iconId: 'dhl',
    colorGradient: 'from-yellow-500 to-yellow-400',
    available: true,
  },

  // ─── DEV TOOLS ─────────────────────────────────────────────────
  {
    key: 'github',
    name: 'GitHub',
    description: 'Access issues, pull requests, and repository data from GitHub.',
    category: 'dev_tools',
    tier: 'tier1_prebuilt',
    authSchema: {
      type: 'bearer',
      fields: [
        { name: 'api_key', label: 'Personal Access Token', type: 'password', required: true, placeholder: 'ghp_xxx' },
      ],
    },
    testConnection: {
      method: 'GET',
      urlTemplate: 'https://api.github.com/user',
      headersTemplate: { 'Authorization': 'Bearer {api_key}' },
      successCheck: 'status_200',
      successMessage: 'Connected to GitHub',
    },
    suggestedIndustries: ['saas', 'other'],
    availableForVariants: ['parwa', 'parwa_high'],
    iconId: 'github',
    colorGradient: 'from-gray-600 to-gray-500',
    available: true,
  },
  {
    key: 'jira',
    name: 'Jira',
    description: 'Access issues, projects, and sprint data from Jira.',
    category: 'dev_tools',
    tier: 'tier1_prebuilt',
    authSchema: {
      type: 'basic_auth',
      fields: [
        { name: 'domain', label: 'Domain', type: 'text', required: true, placeholder: 'yourcompany' },
        { name: 'email', label: 'Email', type: 'text', required: true },
        { name: 'api_token', label: 'API Token', type: 'password', required: true },
      ],
    },
    testConnection: {
      method: 'GET',
      urlTemplate: 'https://{domain}.atlassian.net/rest/api/3/myself',
      successCheck: 'status_200',
      successMessage: 'Connected to Jira',
    },
    suggestedIndustries: ['saas', 'other'],
    availableForVariants: ['parwa', 'parwa_high'],
    iconId: 'jira',
    colorGradient: 'from-blue-500 to-blue-400',
    available: true,
  },
  {
    key: 'linear',
    name: 'Linear',
    description: 'Access issues, projects, and cycles from Linear.',
    category: 'dev_tools',
    tier: 'tier1_prebuilt',
    authSchema: {
      type: 'bearer',
      fields: [
        { name: 'api_key', label: 'API Key', type: 'password', required: true, placeholder: 'lin_api_xxx' },
      ],
    },
    testConnection: {
      method: 'POST',
      urlTemplate: 'https://api.linear.app/graphql',
      headersTemplate: { 'Authorization': '{api_key}', 'Content-Type': 'application/json' },
      successCheck: 'status_200',
      successMessage: 'Connected to Linear',
    },
    suggestedIndustries: ['saas', 'other'],
    availableForVariants: ['parwa', 'parwa_high'],
    iconId: 'linear',
    colorGradient: 'from-violet-500 to-violet-400',
    available: true,
  },

  // ─── PRODUCTIVITY ──────────────────────────────────────────────
  {
    key: 'notion',
    name: 'Notion',
    description: 'Access pages, databases, and content from Notion workspace.',
    category: 'productivity',
    tier: 'tier1_prebuilt',
    authSchema: {
      type: 'bearer',
      fields: [
        { name: 'api_key', label: 'Internal Integration Token', type: 'password', required: true, placeholder: 'ntn_xxx' },
      ],
    },
    testConnection: {
      method: 'GET',
      urlTemplate: 'https://api.notion.com/v1/users/me',
      headersTemplate: { 'Authorization': 'Bearer {api_key}', 'Notion-Version': '2022-06-28' },
      successCheck: 'status_200',
      successMessage: 'Connected to Notion',
    },
    suggestedIndustries: ['saas', 'other'],
    availableForVariants: ['parwa', 'parwa_high'],
    iconId: 'notion',
    colorGradient: 'from-gray-500 to-gray-400',
    available: true,
  },
];

// ── Category Metadata ───────────────────────────────────────────────────

export const CATEGORY_META: Record<IntegrationCategory, { label: string; order: number }> = {
  crm: { label: 'CRM', order: 1 },
  ecommerce: { label: 'E-Commerce', order: 2 },
  helpdesk: { label: 'Helpdesk', order: 3 },
  communication: { label: 'Communication', order: 4 },
  analytics: { label: 'Analytics', order: 5 },
  marketing: { label: 'Marketing', order: 6 },
  payments: { label: 'Payments', order: 7 },
  shipping: { label: 'Shipping', order: 8 },
  dev_tools: { label: 'Dev Tools', order: 9 },
  productivity: { label: 'Productivity', order: 10 },
  custom: { label: 'Custom', order: 11 },
};

// ── Industry Filtering (GAP 3) ──────────────────────────────────────────

/**
 * Get integrations suggested for a specific industry.
 * Per D1/D3: "Other" shows ALL integrations (no filtering).
 * Per D3: Suggestions are NOT restrictions — clients can always connect outside their industry.
 */
export function getIntegrationsForIndustry(
  industry: ParwaIndustry
): IntegrationDefinition[] {
  if (industry === 'other') {
    return INTEGRATION_CATALOG.filter((i) => i.available);
  }
  return INTEGRATION_CATALOG.filter(
    (i) => i.available && i.suggestedIndustries.includes(industry)
  );
}

/**
 * Get integrations grouped by category for a specific industry.
 */
export function getIntegrationsGroupedByCategory(
  industry: ParwaIndustry
): Record<IntegrationCategory, IntegrationDefinition[]> {
  const filtered = getIntegrationsForIndustry(industry);
  const grouped: Record<string, IntegrationDefinition[]> = {};

  for (const integration of filtered) {
    if (!grouped[integration.category]) {
      grouped[integration.category] = [];
    }
    grouped[integration.category].push(integration);
  }

  return grouped as Record<IntegrationCategory, IntegrationDefinition[]>;
}

/**
 * Get a single integration by key.
 */
export function getIntegrationByKey(key: string): IntegrationDefinition | undefined {
  return INTEGRATION_CATALOG.find((i) => i.key === key);
}

/**
 * Check if an integration is available for a specific variant.
 * Per D2: ALL variants get unlimited integrations.
 * availableForVariants is ONLY for tier-gating (Custom API, OpenAPI).
 */
export function isIntegrationAvailableForVariant(
  integration: IntegrationDefinition,
  _variant: 'mini_parwa' | 'parwa' | 'parwa_high'
): boolean {
  // Per D2: All variants get UNLIMITED integrations.
  // availableForVariants is only used for feature gating, not count limits.
  if (!integration.availableForVariants || integration.availableForVariants.length === 0) {
    return true;
  }
  return integration.availableForVariants.includes(_variant);
}

/**
 * Map frontend Industry type (14 values) to ParwaIndustry (4 values).
 * Mirrors backend's map_onboarding_industry_to_enum().
 */
export function mapIndustryToParwaIndustry(
  industry: string
): ParwaIndustry {
  const mapping: Record<string, ParwaIndustry> = {
    ecommerce: 'ecommerce',
    retail: 'ecommerce',
    hospitality: 'ecommerce',
    logistics: 'logistics',
    saas: 'saas',
    technology: 'saas',
    finance: 'saas',
    healthcare: 'saas',
    education: 'saas',
    real_estate: 'other',
    manufacturing: 'other',
    consulting: 'other',
    agency: 'other',
    nonprofit: 'other',
    other: 'other',
  };
  return mapping[industry.toLowerCase()] || 'other';
}
