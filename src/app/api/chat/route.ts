import { NextRequest, NextResponse } from 'next/server';
import ZAI from 'z-ai-web-dev-sdk';

export async function POST(req: NextRequest) {
  try {
    const { message, industry, variant } = await req.json();

    if (!message || typeof message !== 'string' || message.trim().length === 0) {
      return NextResponse.json(
        { status: 'error', message: 'Message is required' },
        { status: 400 }
      );
    }

    const zai = await ZAI.create();

    const systemPrompt = `You are PARWA's AI sales assistant — a friendly, knowledgeable expert on PARWA's AI customer support platform. You help businesses understand which PARWA plan (Starter $999/mo, Growth $2,499/mo, or High $3,999/mo) best fits their needs.

Key facts:
- PARWA Starter ($999/mo): Up to 3 AI agents, 1,000 tickets/mo, Email & Chat, FAQ handling, Phone (2 concurrent). Best for SMBs with 50-200 daily tickets. Replaces ~4 trainee agents ($14,000/mo).
- PARWA Growth ($2,499/mo): Up to 8 AI agents, 5,000 tickets/mo, All Starter channels + SMS & Voice, Smart Router, Agent Lightning, Batch approvals, Advanced analytics. Best for SMBs with 200-500 daily tickets. Replaces ~4 junior agents ($18,000/mo).
- PARWA High ($3,999/mo): Up to 15 AI agents, 15,000 tickets/mo, All channels including Social Media, Quality coaching, Churn prediction, Video support, 5 concurrent voice calls, Custom integrations. Best for businesses with 500+ daily tickets. Replaces ~5 senior agents ($28,000/mo).

Industry-specific capabilities:
- E-commerce: Order tracking, returns, cart recovery, fraud detection (Shopify, Magento, WooCommerce)
- SaaS: Technical support, API troubleshooting, churn prediction, in-app guidance (GitHub, Jira, Slack)
- Logistics: Shipment tracking, driver coordination, proof of delivery, hazmat protocol (TMS, WMS, GPS)
- Healthcare: Appointment scheduling, insurance verification, HIPAA compliance, clinical escalation (Epic EHR, FHIR)

Cancellation policy: Cancel anytime, no refunds once paid, access continues until end of billing month, no free trials.
${industry ? `\nThe user is interested in the ${industry} industry.` : ''}
${variant ? `\nThe user is looking at the ${variant} plan.` : ''}

Be concise, friendly, and helpful. Keep responses under 150 words. Use bullet points for features. If asked about pricing, give exact numbers.`;

    const completion = await zai.chat.completions.create({
      messages: [
        { role: 'system', content: systemPrompt },
        { role: 'user', content: message },
      ],
      temperature: 0.7,
      max_tokens: 300,
    });

    const reply = completion.choices[0]?.message?.content || "I'd be happy to help! Could you tell me more about your business needs so I can recommend the best PARWA plan for you?";

    return NextResponse.json({ status: 'success', reply });
  } catch (error: any) {
    console.error('Chat API error:', error);
    return NextResponse.json(
      { status: 'error', message: 'Failed to get response. Please try again.' },
      { status: 500 }
    );
  }
}
