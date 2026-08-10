/**
 * CRM → Integration Recommendations
 *
 * When a tenant connects their CRM in onboarding Step 2, PARWA can recommend
 * other integrations they likely need based on their industry / CRM type.
 *
 * Example: Shopify connected → recommend Stripe (refunds), Brevo (emails), Twilio (SMS)
 */

export interface IntegrationRecommendation {
  type: string;
  reason: string;
  popularity: number;
}

export const CRM_RECOMMENDATIONS: Record<string, IntegrationRecommendation[]> = {
  shopify: [
    { type: 'stripe', reason: 'For processing refunds and chargebacks', popularity: 75 },
    { type: 'brevo', reason: 'For sending order confirmation and refund emails', popularity: 60 },
    { type: 'twilio', reason: 'For SMS shipping notifications', popularity: 40 },
    { type: 'klaviyo', reason: 'For marketing automation', popularity: 50 },
  ],
  woocommerce: [
    { type: 'stripe', reason: 'For processing refunds', popularity: 65 },
    { type: 'brevo', reason: 'For order emails', popularity: 50 },
    { type: 'twilio', reason: 'For SMS notifications', popularity: 30 },
  ],
  hubspot: [
    { type: 'stripe', reason: 'For subscription billing', popularity: 70 },
    { type: 'brevo', reason: 'For marketing emails', popularity: 55 },
    { type: 'slack', reason: 'For internal notifications', popularity: 65 },
  ],
  salesforce: [
    { type: 'stripe', reason: 'For billing sync', popularity: 60 },
    { type: 'brevo', reason: 'For marketing emails', popularity: 50 },
    { type: 'slack', reason: 'For internal notifications', popularity: 55 },
  ],
  zendesk: [
    { type: 'slack', reason: 'For internal escalation notifications', popularity: 70 },
    { type: 'brevo', reason: 'For customer follow-up emails', popularity: 50 },
    { type: 'twilio', reason: 'For SMS support', popularity: 35 },
  ],
  paddle: [
    { type: 'brevo', reason: 'For sending refund confirmation emails', popularity: 70 },
    { type: 'twilio', reason: 'For SMS payment notifications', popularity: 35 },
    { type: 'slack', reason: 'For high-value refund alerts', popularity: 40 },
  ],
  stripe: [
    { type: 'brevo', reason: 'For sending receipts and refund emails', popularity: 75 },
    { type: 'twilio', reason: 'For SMS payment alerts', popularity: 40 },
    { type: 'slack', reason: 'For dispute notifications', popularity: 50 },
  ],
  razorpay: [
    { type: 'brevo', reason: 'For payment confirmation emails', popularity: 60 },
    { type: 'twilio', reason: 'For SMS payment alerts (India)', popularity: 70 },
  ],
  brevo: [
    { type: 'stripe', reason: 'For syncing customer payment data', popularity: 50 },
    { type: 'hubspot', reason: 'For CRM enrichment', popularity: 45 },
  ],
  twilio: [
    { type: 'brevo', reason: 'For email + SMS combined notifications', popularity: 65 },
    { type: 'slack', reason: 'For internal alerts', popularity: 50 },
  ],
  slack: [
    { type: 'hubspot', reason: 'For deal notifications', popularity: 55 },
    { type: 'stripe', reason: 'For payment alerts', popularity: 45 },
  ],
};

export const INDUSTRY_RECOMMENDATIONS: Record<string, IntegrationRecommendation[]> = {
  ecommerce: [
    { type: 'shopify', reason: 'For order management', popularity: 80 },
    { type: 'stripe', reason: 'For payment processing', popularity: 75 },
    { type: 'brevo', reason: 'For order emails', popularity: 60 },
  ],
  saas: [
    { type: 'stripe', reason: 'For subscription billing', popularity: 80 },
    { type: 'hubspot', reason: 'For CRM', popularity: 65 },
    { type: 'slack', reason: 'For team notifications', popularity: 70 },
  ],
  healthcare: [
    { type: 'twilio', reason: 'For appointment reminders', popularity: 70 },
    { type: 'brevo', reason: 'For patient communications', popularity: 60 },
  ],
  banking: [
    { type: 'twilio', reason: 'For transaction alerts', popularity: 80 },
    { type: 'slack', reason: 'For fraud alerts', popularity: 65 },
  ],
  logistics: [
    { type: 'twilio', reason: 'For delivery SMS', popularity: 85 },
    { type: 'brevo', reason: 'For shipping notifications', popularity: 70 },
  ],
};

export function getRecommendations(
  connectedTypes: string[],
  industry?: string
): IntegrationRecommendation[] {
  const recommendations: IntegrationRecommendation[] = [];
  const connected = new Set(connectedTypes.map((t) => t.toLowerCase()));

  for (const connectedType of connectedTypes) {
    const recs = CRM_RECOMMENDATIONS[connectedType.toLowerCase()] || [];
    for (const rec of recs) {
      if (!connected.has(rec.type.toLowerCase())) {
        recommendations.push(rec);
      }
    }
  }

  if (recommendations.length === 0 && industry) {
    const industryRecs = INDUSTRY_RECOMMENDATIONS[industry.toLowerCase()] || [];
    for (const rec of industryRecs) {
      if (!connected.has(rec.type.toLowerCase())) {
        recommendations.push(rec);
      }
    }
  }

  const byType = new Map<string, IntegrationRecommendation>();
  for (const rec of recommendations) {
    const existing = byType.get(rec.type.toLowerCase());
    if (!existing || rec.popularity > existing.popularity) {
      byType.set(rec.type.toLowerCase(), rec);
    }
  }

  return Array.from(byType.values()).sort((a, b) => b.popularity - a.popularity);
}
