# Enterprise Onboarding Guide

**PARWA AI Customer Support Platform**

**Version:** 2.0  
**Last Updated:** March 2026

---

## Table of Contents

1. [Welcome](#1-welcome)
2. [Pre-Onboarding Checklist](#2-pre-onboarding-checklist)
3. [Onboarding Steps](#3-onboarding-steps)
4. [SSO Configuration](#4-sso-configuration)
5. [Team Setup](#5-team-setup)
6. [Knowledge Base Setup](#6-knowledge-base-setup)
7. [Integration Setup](#7-integration-setup)
8. [Training Resources](#8-training-resources)
9. [Support](#9-support)

---

## 1. Welcome

Welcome to PARWA! This guide will help you set up your enterprise account and get your team up and running quickly.

### Your Dedicated Team

As an Enterprise client, you have access to:

- **Customer Success Manager (CSM):** Your primary point of contact
- **Implementation Specialist:** Technical setup assistance
- **Support Team:** 24/7 technical support

### Onboarding Timeline

| Week | Activities |
|------|------------|
| Week 1 | Account setup, SSO configuration |
| Week 2 | Team setup, knowledge base |
| Week 3 | Integrations, testing |
| Week 4 | Go-live, training |

---

## 2. Pre-Onboarding Checklist

Before starting onboarding, please have the following information ready:

### 2.1 Technical Requirements

- [ ] SSO Identity Provider details (Okta, Azure AD, etc.)
- [ ] IP addresses for allowlisting
- [ ] DNS records for custom domain (if applicable)
- [ ] SSL certificates (or authorization to use PARWA certificates)

### 2.2 Administrative Information

- [ ] List of administrators (names, emails, roles)
- [ ] Company logo and branding assets
- [ ] Support email address and phone number
- [ ] Timezone and business hours

### 2.3 Integration Requirements

- [ ] Third-party systems to integrate (Zendesk, Shopify, etc.)
- [ ] API credentials for integrations
- [ ] Webhook endpoints
- [ ] Data migration requirements (if applicable)

---

## 3. Onboarding Steps

### Step 1: Company Information

**Duration:** 30 minutes

Provide your company details:

1. Company name and legal entity
2. Billing contact and address
3. Primary administrator contact
4. Support branding preferences

### Step 2: Contract Review

**Duration:** 1-2 days

1. Review and sign the Enterprise Agreement
2. Sign the Data Processing Agreement (DPA)
3. Confirm billing details and payment method

### Step 3: Contract Signing

**Duration:** Immediate upon signature

Your account will be activated upon contract signing. You'll receive:

- Tenant ID and API keys
- Admin account credentials
- Access to the Enterprise Dashboard

### Step 4: SSO Configuration

**Duration:** 2-4 hours

Configure Single Sign-On with your Identity Provider. See [Section 4](#4-sso-configuration) for detailed instructions.

### Step 5: Team Setup

**Duration:** 1-2 hours

Add your team members and assign roles. See [Section 5](#5-team-setup) for details.

### Step 6: Knowledge Base Setup

**Duration:** 4-8 hours

Configure your knowledge base with FAQs and documentation. See [Section 6](#6-knowledge-base-setup).

### Step 7: Integration Setup

**Duration:** 2-4 hours

Connect your existing tools and systems. See [Section 7](#7-integration-setup).

### Step 8: Training

**Duration:** 2-4 hours

Complete administrator training sessions. See [Section 8](#8-training-resources).

---

## 4. SSO Configuration

### 4.1 Supported Identity Providers

PARWA supports the following Identity Providers (IdPs):

- **Okta** (Recommended)
- **Microsoft Azure AD**
- **Google Workspace**
- **OneLogin**
- **Custom SAML 2.0 providers**

### 4.2 Okta Configuration

#### Step 1: Create SAML Application in Okta

1. Log in to Okta Admin Console
2. Navigate to **Applications > Applications**
3. Click **Create App Integration**
4. Select **SAML 2.0**
5. Click **Next**

#### Step 2: Configure General Settings

- **App name:** PARWA
- **App logo:** Upload your company logo
- **App visibility:** Check "Display application icon"

#### Step 3: Configure SAML Settings

Enter the following values provided by PARWA:

| Field | Value |
|-------|-------|
| Single sign-on URL | `https://api.parwa.ai/sso/acs/{tenant_id}` |
| Audience URI (SP Entity ID) | `https://parwa.ai/sp/{tenant_id}` |
| Default RelayState | Leave blank |
| Name ID format | EmailAddress |
| Application username | Email |

#### Step 4: Attribute Statements

Add the following attribute statements:

| Name | Name format | Value |
|------|-------------|-------|
| email | Unspecified | user.email |
| firstName | Unspecified | user.firstName |
| lastName | Unspecified | user.lastName |
| role | Unspecified | (user role) |

#### Step 5: Complete Setup

1. Click **Next**
2. Select "I'm a software vendor..." if applicable
3. Click **Finish**

#### Step 6: Provide Okta Details to PARWA

Send the following to your Implementation Specialist:

- Identity Provider Issuer (Entity ID)
- Identity Provider Single Sign-On URL
- X.509 Certificate

### 4.3 Azure AD Configuration

#### Step 1: Create Enterprise Application

1. Go to Azure Portal > Azure Active Directory
2. Navigate to **Enterprise applications**
3. Click **New application**
4. Click **Create your own application**
5. Enter "PARWA" and select "Integrate any other application"

#### Step 2: Configure Single Sign-On

1. Go to **Single sign-on**
2. Select **SAML**
3. Enter the Basic SAML Configuration:

| Field | Value |
|-------|-------|
| Identifier | `https://parwa.ai/sp/{tenant_id}` |
| Reply URL | `https://api.parwa.ai/sso/acs/{tenant_id}` |
| Sign on URL | `https://app.parwa.ai/login` |

#### Step 3: Configure Attributes

Add the following claims:

| Name | Source | Source attribute |
|------|--------|------------------|
| email | Attribute | user.mail |
| firstName | Attribute | user.givenname |
| lastName | Attribute | user.surname |

#### Step 4: Assign Users

1. Go to **Users and groups**
2. Click **Add user/group**
3. Select users and groups to grant access

### 4.4 Testing SSO

After configuration:

1. Test login from your IdP dashboard
2. Verify user attributes are correctly passed
3. Test user provisioning (if SCIM enabled)
4. Verify session management

---

## 5. Team Setup

### 5.1 User Invitation Methods

1. **Manual Invitation**
   - Enter email addresses individually
   - Assign roles during invitation

2. **Bulk Import**
   - Upload CSV file with user details
   - Format: email, first_name, last_name, role

3. **SCIM Provisioning**
   - Automatic user creation from IdP
   - Automatic deprovisioning

### 5.2 Role Assignment

| Role | Capabilities |
|------|--------------|
| Super Admin | Full system access, billing, API keys |
| Admin | User management, configuration, reports |
| Manager | Team management, analytics, quality review |
| Agent | Ticket handling, knowledge base |
| Viewer | Read-only access to dashboards |

### 5.3 Team Structure

Recommended team structure:

```
├── Support Manager (Admin)
│   ├── Team Lead (Manager)
│   │   ├── Senior Agent
│   │   └── Agent
│   └── Team Lead (Manager)
│       ├── Senior Agent
│       └── Agent
└── Technical Admin (Admin)
```

---

## 6. Knowledge Base Setup

### 6.1 Knowledge Base Structure

```
├── FAQs
│   ├── General
│   ├── Account & Billing
│   ├── Technical Support
│   └── Returns & Refunds
├── How-to Guides
│   ├── Getting Started
│   ├── Advanced Features
│   └── Troubleshooting
└── Policies
    ├── Privacy Policy
    ├── Terms of Service
    └── Return Policy
```

### 6.2 Content Requirements

Each FAQ entry should include:

- Question (user-facing)
- Answer (clear, concise response)
- Category
- Tags for searchability
- Related articles

### 6.3 Import Options

1. **Manual Entry**
   - Use the Knowledge Base Editor
   - Rich text formatting supported

2. **CSV Import**
   - Batch upload FAQs
   - Format: question, answer, category, tags

3. **API Import**
   - Programmatically add articles
   - Suitable for large knowledge bases

### 6.4 Quality Guidelines

- Use clear, simple language
- Keep answers under 200 words
- Include links to related resources
- Update content regularly
- Review accuracy monthly

---

## 7. Integration Setup

### 7.1 Available Integrations

| Category | Integrations |
|----------|--------------|
| E-commerce | Shopify, WooCommerce, BigCommerce, Magento |
| CRM | Salesforce, HubSpot, Zoho |
| Ticketing | Zendesk, Freshdesk, HelpScout |
| Communication | Slack, Microsoft Teams, Discord |
| Payments | Stripe, PayPal, Paddle |
| Analytics | Google Analytics, Mixpanel, Amplitude |

### 7.2 API Access

1. Navigate to **Settings > API Keys**
2. Click **Create API Key**
3. Select required scopes
4. Set rate limits
5. Configure IP restrictions (optional)
6. Copy and securely store the key

### 7.3 Webhook Configuration

1. Navigate to **Settings > Webhooks**
2. Click **Add Webhook**
3. Enter endpoint URL
4. Select events to subscribe to
5. Configure authentication (HMAC signature)
6. Test the webhook

### 7.4 Data Migration

If migrating from another platform:

1. Export data from existing system
2. Format according to PARWA templates
3. Coordinate with Implementation Specialist
4. Schedule migration during off-peak hours
5. Verify data integrity post-migration

---

## 8. Training Resources

### 8.1 Administrator Training

**Duration:** 2 hours

Topics covered:
- Dashboard overview
- User management
- Configuration options
- Analytics and reporting
- Best practices

### 8.2 Agent Training

**Duration:** 1 hour

Topics covered:
- Ticket handling workflow
- AI assistance features
- Knowledge base usage
- Communication tools
- Quality guidelines

### 8.3 Self-Service Resources

- **Knowledge Base:** help.parwa.ai
- **Video Tutorials:** academy.parwa.ai
- **API Documentation:** docs.parwa.ai
- **Community Forum:** community.parwa.ai

### 8.4 Training Schedule

| Session | Audience | Duration |
|---------|----------|----------|
| Admin Overview | Administrators | 2 hours |
| Agent Training | Support Agents | 1 hour |
| Technical Deep Dive | Technical Team | 2 hours |
| Q&A Session | All Users | 1 hour |

---

## 9. Support

### 9.1 Support Channels

| Channel | Availability | Response Time |
|---------|--------------|---------------|
| Enterprise Support | 24/7/365 | 15 minutes (P1) |
| Email | support@parwa.ai | 4 hours |
| Phone | [Phone Number] | 1 hour |
| Chat | In-app chat | 15 minutes |

### 9.2 Your Support Team

**Customer Success Manager:**  
Name: [CSM Name]  
Email: [email]  
Phone: [phone]

**Technical Support:**  
Email: enterprise-support@parwa.ai  
Emergency: [phone]

### 9.3 Escalation Path

1. **Level 1:** Support Team (immediate)
2. **Level 2:** Technical Support (4 hours)
3. **Level 3:** Engineering Team (8 hours)
4. **Executive Escalation:** [executive email]

---

## 10. Quick Reference

### Important URLs

- **Dashboard:** https://app.parwa.ai
- **API Endpoint:** https://api.parwa.ai
- **Status Page:** https://status.parwa.ai
- **Documentation:** https://docs.parwa.ai

### Key Contacts

- **Support:** support@parwa.ai
- **Security:** security@parwa.ai
- **Billing:** billing@parwa.ai

---

**Document Version:** 2.0  
**Last Updated:** March 2026

*Thank you for choosing PARWA! We're excited to partner with you.*
