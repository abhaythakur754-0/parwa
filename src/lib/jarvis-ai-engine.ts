/**
 * @deprecated PARWA Jarvis AI Engine — Knowledge-Based Conversational Intelligence
 *
 * DEPRECATED: This module is no longer actively imported or used.
 * The proxy route (src/app/api/jarvis/[...path]/route.ts) handles all AI
 * responses via its own getAIResponse() / callAI() / getKeywordResponse() pipeline.
 *
 * Retained for reference — the knowledge-base loading logic, intent detection,
 * and response builders may be re-integrated into the proxy route in a future refactor.
 *
 * Original purpose: When external AI providers (z-ai-sdk, Google, Cerebras, Groq)
 * are unavailable, this engine generates intelligent, contextual responses using the
 * 10-file knowledge base. It scores intents, matches FAQs/objections/competitors,
 * tracks context, and avoids repetition — making Jarvis feel smart, not robotic.
 */

import * as fs from 'fs';
import * as path from 'path';

// ── Types ──────────────────────────────────────────────────────────

interface FAQEntry { id: string; q: string; a: string; category: string; tags: string[] }
interface ObjectionEntry { id: string; objection: string; jarvis_response: string; follow_up: string; supporting_data: string[] }
interface CompetitorEntry { competitor_name: string; our_advantage: string; key_differentiators: any[]; winning_argument: string }
interface VariantEntry { id: string; name: string; industry: string; description: string; price_per_unit: number; tickets_per_month: number; what_it_handles: string[]; sample_query: string; sample_response: string; success_metrics?: any }
interface IndustryGroup { name: string; description: string; variants: VariantEntry[] }
interface ScenarioEntry { id: string; industry: string; title: string; difficulty: string; customer_message: string; expected_jarvis_behavior: string[]; talking_points: string[] }
interface EdgeCaseEntry { query_type: string; detection_keywords: string[]; response_template: string }
interface TierEntry { name: string; monthly_price: number; annual_price: number; ai_agents: number; tickets_per_month: number; channels: string[]; features: string[]; support: string; overage_per_ticket: number; voice_support: boolean }

interface KnowledgeBase {
  pricing: { tiers: TierEntry[]; billing: any; variant_pricing: any; sales_talking_points: any };
  industries: { industries: Record<string, IndustryGroup> };
  variantDetails: any;
  integrations: any;
  capabilities: any;
  demoScenarios: { scenarios: ScenarioEntry[] };
  objections: { objections: ObjectionEntry[] };
  faqs: { faqs: FAQEntry[] };
  competitors: { competitors: CompetitorEntry[] };
  edgeCases: any;
}

interface IntentResult {
  primary: string;
  confidence: number;
  entities: string[];
  isDemo: boolean;
  isObjection: boolean;
}

interface SessionLike {
  messages: Array<{ role: string; content: string }>;
  context: Record<string, any>;
  detected_stage?: string;
  stage_history?: string[];
  message_count_today?: number;
}

// ── Intent Definitions ────────────────────────────────────────────

const INTENT_PATTERNS: Record<string, { keywords: string[]; phrases: string[]; weight: number }> = {
  greeting: { keywords: ['hi', 'hello', 'hey', 'howdy', 'sup', 'yo', 'greetings', 'good morning', 'good afternoon', 'good evening', 'whats up'], phrases: ['how are you', 'nice to meet', 'whats going on'], weight: 1.0 },
  pricing: { keywords: ['price', 'pricing', 'cost', 'plan', 'plans', 'how much', 'monthly', 'annual', 'subscription', 'tier', 'package', 'quote', 'billing', 'afford'], phrases: ['what does it cost', 'how much does', 'pricing plan', 'subscription cost', 'plan price', 'monthly cost', 'annual cost', 'which plan'], weight: 1.0 },
  industry_ecommerce: { keywords: ['ecommerce', 'e-commerce', 'online store', 'shop', 'retail', 'amazon', 'shopify', 'woocommerce', 'magento', 'bigcommerce', 'product catalog', 'cart'], phrases: ['online store', 'e commerce', 'retail business', 'selling online'], weight: 1.2 },
  industry_saas: { keywords: ['saas', 'software', 'app company', 'platform', 'b2b software', 'subscription business', 'tech startup'], phrases: ['saas company', 'software business', 'my app'], weight: 1.2 },
  industry_logistics: { keywords: ['logistics', 'shipping', 'warehouse', 'delivery', 'freight', 'supply chain', 'courier', 'fleet', 'transportation', 'tms', 'wms', 'cargo'], phrases: ['logistics company', 'shipping business', 'supply chain'], weight: 1.2 },
  industry_logistics: { keywords: ['logistics', 'shipping', 'warehouse', 'delivery', 'freight', 'supply chain', 'courier', 'fleet', 'transportation', 'tms', 'wms', 'cargo'], phrases: ['logistics company', 'shipping business', 'supply chain'], weight: 1.2 },
  features: { keywords: ['feature', 'features', 'capability', 'capabilities', 'what can you do', 'what does parwa do', 'functionality', 'offer'], phrases: ['what can', 'what does parwa', 'tell me about', 'what do you offer', 'your features'], weight: 0.9 },
  integrations: { keywords: ['integration', 'integrate', 'connect', 'shopify', 'zendesk', 'slack', 'freshdesk', 'intercom', 'salesforce', 'hubspot', 'stripe', 'api', 'webhook'], phrases: ['integrates with', 'connect to', 'works with', 'compatible with'], weight: 1.0 },
  demo: { keywords: ['demo', 'try', 'show me', 'test', 'experience', 'see it', 'live demo', 'sample', 'example', 'roleplay'], phrases: ['show me how', 'can i try', 'give me a demo', 'let me see', 'walk me through'], weight: 1.1 },
  roi: { keywords: ['roi', 'save', 'savings', 'comparison', 'compare', 'worth', 'return', 'investment', 'value', 'benefit'], phrases: ['return on investment', 'cost savings', 'how much save', 'is it worth', 'money back'], weight: 1.0 },
  security: { keywords: ['security', 'gdpr', 'data', 'privacy', 'safe', 'compliance', 'encrypt', 'soc', 'audit', 'breach', 'protection'], phrases: ['data security', 'is it safe', 'gdpr compliant', 'data protection'], weight: 1.0 },
  competitors: { keywords: ['intercom', 'zendesk', 'freshdesk', 'crisp', 'tidio', 'drift', 'ada', 'chatbase', 'kommunicate', 'competitor', 'vs'], phrases: ['compared to', 'vs intercom', 'vs zendesk', 'better than', 'alternative to', 'how do you compare'], weight: 1.2 },
  how_it_works: { keywords: ['how does it work', 'how do you', 'technology', 'ai engine', 'under the hood', 'architecture', 'approach', 'methodology', 'process'], phrases: ['how does parwa work', 'how do you handle', 'how are you different', 'what technology'], weight: 0.9 },
  buy_signup: { keywords: ['buy', 'signup', 'get started', 'subscribe', 'checkout', 'sign up', 'purchase', 'order', 'onboard'], phrases: ['i want to buy', 'how to sign up', 'get started', 'ready to purchase'], weight: 1.0 },
  objection_expensive: { keywords: ['expensive', 'costly', 'too much', 'cant afford', 'budget', 'overpriced', 'pricey', 'out of budget', 'too steep'], phrases: ['too expensive', 'out of my budget', 'cant afford', 'costs too much', 'price is high'], weight: 1.3 },
  objection_ai_quality: { keywords: ['wrong answer', 'cant handle', 'complex', 'accuracy', 'hallucinat', 'mistake', 'incorrect', 'unreliable', 'dumb'], phrases: ['ai cant handle', 'gives wrong answers', 'what if it makes mistakes', 'not smart enough'], weight: 1.3 },
  objection_security: { keywords: ['data breach', 'privacy concern', 'trust', 'risk', 'unsafe', 'hack', 'vulnerability'], phrases: ['concerned about data', 'is my data safe', 'what about security'], weight: 1.3 },
  objection_setup_time: { keywords: ['how long', 'setup time', 'implementation', 'deploy', 'rollout', 'timeline', 'complicated', 'difficult'], phrases: ['how long to set up', 'implementation time', 'how long does it take', 'deployment timeline'], weight: 1.3 },
  objection_competitor: { keywords: ['already use', 'happy with', 'switching from', 'current provider', 'locked in', 'existing setup'], phrases: ['we already use', 'happy with our current', 'dont want to switch', 'already have'], weight: 1.3 },
  objection_think: { keywords: ['think about it', 'maybe later', 'not now', 'not ready', 'need time', 'let me consider', 'discuss', 'talk to team'], phrases: ['let me think', 'need to discuss', 'not ready yet', 'come back later'], weight: 1.3 },
  variant_returns: { keywords: ['return', 'refund', 'exchange', 'money back', 'return policy', 'return request'], phrases: ['handle returns', 'process refunds', 'return policy'], weight: 1.4 },
  variant_order: { keywords: ['order status', 'order tracking', 'track order', 'where is my order', 'order management', 'delivery status'], phrases: ['track my order', 'order status', 'where is my order'], weight: 1.4 },
  variant_shipping: { keywords: ['shipping', 'delivery time', 'ship', 'dispatch', 'eta', 'estimated delivery', 'courier'], phrases: ['shipping inquiry', 'delivery time', 'when will it arrive'], weight: 1.4 },
  variant_payment: { keywords: ['payment', 'payment issue', 'failed payment', 'charge', 'invoice', 'billing issue', 'transaction'], phrases: ['payment failed', 'billing issue', 'payment problem'], weight: 1.4 },
  variant_faq: { keywords: ['product question', 'faq', 'specification', 'how to use', 'product detail', 'manual'], phrases: ['product question', 'how does this product work', 'specifications'], weight: 1.4 },
  goodbye: { keywords: ['thanks', 'bye', 'goodbye', 'that is all', 'done', 'see you', 'later', 'take care'], phrases: ['thank you', 'goodbye', 'that is all', 'im done'], weight: 1.0 },
  edge_legal: { keywords: ['legal advice', 'sue', 'lawsuit', 'attorney', 'contract', 'liability', 'legal'], phrases: ['legal advice', 'can you help with legal'], weight: 1.5 },
  edge_professional: { keywords: ['professional advice', 'expert advice', 'consultation', 'specialist', 'recommendation'], phrases: ['professional advice', 'can you advise', 'expert opinion'], weight: 1.5 },
};

// ── JarvisAIEngine ────────────────────────────────────────────────

export class JarvisAIEngine {
  private static _instance: JarvisAIEngine | null = null;
  private kb: Partial<KnowledgeBase> = {};
  private _loaded = false;
  private _loadPromise: Promise<void> | null = null;

  static getInstance(): JarvisAIEngine {
    if (!JarvisAIEngine._instance) {
      JarvisAIEngine._instance = new JarvisAIEngine();
    }
    return JarvisAIEngine._instance;
  }

  async ensureLoaded(): Promise<void> {
    if (this._loaded) return;
    if (this._loadPromise) return this._loadPromise;

    this._loadPromise = this._loadAll();
    return this._loadPromise;
  }

  private async _loadAll(): Promise<void> {
    try {
      const kbDir = path.join(process.cwd(), '..', '..', 'backend', 'app', 'data', 'jarvis_knowledge');
      const fallbackDir = '/home/z/my-project/parwa/backend/app/data/jarvis_knowledge';

      const baseDir = fs.existsSync(kbDir) ? kbDir : fallbackDir;

      const files: Record<string, string> = {
        pricing: '01_pricing_tiers.json',
        industries: '02_industry_variants.json',
        variantDetails: '03_variant_details.json',
        integrations: '04_integrations.json',
        capabilities: '05_capabilities.json',
        demoScenarios: '06_demo_scenarios.json',
        objections: '07_objection_handling.json',
        faqs: '08_faq.json',
        competitors: '09_competitor_comparisons.json',
        edgeCases: '10_edge_cases.json',
      };

      for (const [key, filename] of Object.entries(files)) {
        const filePath = path.join(baseDir, filename);
        try {
          const raw = fs.readFileSync(filePath, 'utf-8');
          this.kb[key as keyof KnowledgeBase] = JSON.parse(raw);
        } catch (err) {
          console.error(`[JarvisEngine] Failed to load ${filename}:`, (err as Error).message);
        }
      }

      this._loaded = true;
      const loadedKeys = Object.keys(this.kb).filter(k => this.kb[k as keyof KnowledgeBase] != null);
      console.log(`[JarvisEngine] Knowledge base loaded. Keys: ${loadedKeys.join(', ')}`);
    } catch (err) {
      console.error('[JarvisEngine] Load failed:', (err as Error).message);
    }
  }

  /**
   * Main entry point: Generate an intelligent response for a user message.
   */
  async generateResponse(userMessage: string, session: SessionLike): Promise<string> {
    await this.ensureLoaded();

    const intent = this.detectIntent(userMessage, session);
    const lower = userMessage.toLowerCase();
    const ctx = session.context || {};
    const industry = ctx.industry || null;

    let response: string | null = null;

    // ── Edge cases first (legal, professional, etc.) ──
    if (intent.primary === 'edge_legal' || intent.primary === 'edge_professional') {
      response = this.buildEdgeCaseResponse(intent.primary === 'edge_legal' ? 'legal' : 'professional');
      return this.avoidRepetition(response, session);
    }

    // ── Objections ──
    if (intent.isObjection) {
      const objectionMatch = this.matchObjection(lower, intent.primary);
      if (objectionMatch) {
        response = this.personalizeResponse(objectionMatch.response + '\n\n' + objectionMatch.follow_up, session);
        return this.avoidRepetition(response, session);
      }
    }

    // ── Competitor queries ──
    if (intent.primary === 'competitors') {
      const competitor = this.matchCompetitor(lower);
      if (competitor) {
        response = this.buildCompetitorResponse(competitor, session);
        return this.avoidRepetition(response, session);
      }
      // Generic competitor response
      response = "Great question! PARWA is built differently from other support platforms:\n\n- **Industry-specific AI agents** — not generic chatbots\n- **70%+ auto-resolution** (vs 30-40% for most competitors)\n- **85-92% cost savings** vs hiring human agents\n- **10-14 day deployment** (vs 4-8 weeks for most)\n\nWhich competitor are you currently evaluating? I can give you a detailed comparison.";
      return this.avoidRepetition(response, session);
    }

    // ── Variant-specific queries (returns, orders, shipping, etc.) ──
    if (intent.primary.startsWith('variant_')) {
      const variantType = intent.primary.replace('variant_', '');
      response = this.buildVariantSpecificResponse(variantType, industry, session);
      if (response) return this.avoidRepetition(response, session);
    }

    // ── Greeting ──
    if (intent.primary === 'greeting') {
      response = this.buildGreetingResponse(session);
      return this.avoidRepetition(response, session);
    }

    // ── Goodbye ──
    if (intent.primary === 'goodbye') {
      response = this.buildGoodbyeResponse(session);
      return this.avoidRepetition(response, session);
    }

    // ── FAQ match ──
    const faqMatch = this.matchFAQ(lower, intent);
    if (faqMatch) {
      response = this.personalizeResponse(faqMatch.a, session);
      return this.avoidRepetition(response, session);
    }

    // ── Industry queries ──
    if (intent.primary.startsWith('industry_')) {
      const ind = intent.primary.replace('industry_', '');
      response = this.buildIndustryResponse(ind, session);
      return this.avoidRepetition(response, session);
    }

    // ── Pricing ──
    if (intent.primary === 'pricing') {
      response = this.buildPricingResponse(session);
      return this.avoidRepetition(response, session);
    }

    // ── Demo ──
    if (intent.primary === 'demo' || intent.isDemo) {
      response = this.buildDemoResponse(industry, session);
      return this.avoidRepetition(response, session);
    }

    // ── ROI ──
    if (intent.primary === 'roi') {
      response = this.buildROIResponse(session);
      return this.avoidRepetition(response, session);
    }

    // ── Features ──
    if (intent.primary === 'features') {
      response = this.buildFeaturesResponse(session);
      return this.avoidRepetition(response, session);
    }

    // ── Integrations ──
    if (intent.primary === 'integrations') {
      response = this.buildIntegrationsResponse(session);
      return this.avoidRepetition(response, session);
    }

    // ── Security ──
    if (intent.primary === 'security') {
      response = this.buildSecurityResponse();
      return this.avoidRepetition(response, session);
    }

    // ── How it works ──
    if (intent.primary === 'how_it_works') {
      response = this.buildHowItWorksResponse(session);
      return this.avoidRepetition(response, session);
    }

    // ── Buy/signup ──
    if (intent.primary === 'buy_signup') {
      response = this.buildBuyResponse(session);
      return this.avoidRepetition(response, session);
    }

    // ── Contextual fallback — use session data to craft a smart response ──
    response = this.buildContextualResponse(userMessage, intent, session);
    return this.avoidRepetition(response, session);
  }

  // ── Intent Detection ──────────────────────────────────────────

  private detectIntent(msg: string, session: SessionLike): IntentResult {
    const lower = msg.toLowerCase();
    const ctx = session.context || {};
    const scores: Record<string, number> = {};

    for (const [intent, def] of Object.entries(INTENT_PATTERNS)) {
      let score = 0;

      // Keyword matching
      for (const kw of def.keywords) {
        if (lower.includes(kw)) score += def.weight * 1.5;
      }

      // Phrase matching (higher weight for multi-word matches)
      for (const phrase of def.phrases) {
        if (lower.includes(phrase)) score += def.weight * 3.0;
      }

      if (score > 0) scores[intent] = score;
    }

    // Contextual boosts
    if (ctx.industry) {
      const industryIntent = `industry_${ctx.industry}`;
      if (scores[industryIntent]) scores[industryIntent] += 0.5;
    }
    if (ctx.detected_stage === 'demo' && scores.demo) scores.demo += 1.0;
    if (ctx.detected_stage === 'pricing' && scores.pricing) scores.pricing += 1.0;

    // Sort by score descending
    const sorted = Object.entries(scores).sort((a, b) => b[1] - a[1]);

    if (sorted.length === 0 || sorted[0][1] < 1.0) {
      return { primary: 'unknown', confidence: 0, entities: [], isDemo: false, isObjection: false };
    }

    const primary = sorted[0][0];
    const maxScore = sorted[0][1];

    return {
      primary,
      confidence: Math.min(maxScore / 10, 1),
      entities: this.extractEntities(lower, primary),
      isDemo: primary === 'demo' || lower.includes('demo') || lower.includes('roleplay'),
      isObjection: primary.startsWith('objection_'),
    };
  }

  private extractEntities(msg: string, intent: string): string[] {
    const entities: string[] = [];

    // Extract industry mentions
    const industryMap: Record<string, string> = {
      'ecommerce': 'e-commerce', 'e-commerce': 'e-commerce', 'online store': 'e-commerce', 'retail': 'e-commerce',
      'saas': 'saas', 'software': 'saas',
      'logistics': 'logistics', 'shipping': 'logistics', 'warehouse': 'logistics', 'freight': 'logistics',
      'logistics': 'logistics', 'shipping': 'logistics', 'warehouse': 'logistics', 'freight': 'logistics',
    };
    for (const [keyword, entity] of Object.entries(industryMap)) {
      if (msg.includes(keyword)) entities.push(entity);
    }

    // Extract competitor mentions
    const competitors = ['intercom', 'zendesk', 'freshdesk', 'crisp', 'tidio', 'drift', 'ada', 'chatbase', 'kommunicate'];
    for (const comp of competitors) {
      if (msg.includes(comp)) entities.push(comp);
    }

    return Array.from(new Set(entities));
  }

  // ── FAQ Matching ──────────────────────────────────────────────

  private matchFAQ(msg: string, intent: IntentResult): { a: string; q: string } | null {
    const faqs = this.kb.faqs?.faqs;
    if (!faqs || !faqs.length) return null;

    let bestMatch: { a: string; q: string; score: number } | null = null;

    for (const faq of faqs) {
      let score = 0;
      const qLower = faq.q.toLowerCase();
      const tagsStr = (faq.tags || []).join(' ');

      // Direct question match (very high weight)
      const msgWords = msg.split(/\s+/).filter(w => w.length > 2);
      const qWords = qLower.split(/\s+/).filter(w => w.length > 2);
      const overlap = msgWords.filter(w => qWords.includes(w) || qLower.includes(w));
      score += overlap.length * 2;

      // Tag matching
      for (const tag of (faq.tags || [])) {
        if (msg.includes(tag.toLowerCase())) score += 1.5;
      }

      // Intent category boost
      if (intent.primary === 'pricing' && faq.category === 'pricing') score += 2;
      if (intent.primary === 'security' && faq.category === 'security') score += 2;
      if (intent.primary === 'features' && faq.category === 'features') score += 2;
      if (intent.primary.startsWith('industry_') && faq.category === 'industries') score += 2;

      if (score > 3 && (!bestMatch || score > bestMatch.score)) {
        bestMatch = { a: faq.a, q: faq.q, score };
      }
    }

    return bestMatch;
  }

  // ── Objection Matching ────────────────────────────────────────

  private matchObjection(msg: string, intentPrimary: string): { response: string; follow_up: string } | null {
    const objections = this.kb.objections?.objections;
    if (!objections || !objections.length) return null;

    let bestMatch: { response: string; follow_up: string; score: number } | null = null;

    for (const obj of objections) {
      let score = 0;
      const objLower = obj.objection.toLowerCase();

      // Check if the objection text matches
      const msgWords = msg.split(/\s+/).filter(w => w.length > 2);
      const objWords = objLower.split(/\s+/).filter(w => w.length > 2);
      const overlap = msgWords.filter(w => objWords.includes(w) || objLower.includes(w));
      score += overlap.length * 2;

      // Exact keyword matching for specific objection types
      if (intentPrimary === 'objection_expensive' && (objLower.includes('expensive') || objLower.includes('cost'))) score += 5;
      if (intentPrimary === 'objection_ai_quality' && (objLower.includes('complex') || objLower.includes('wrong'))) score += 5;
      if (intentPrimary === 'objection_security' && objLower.includes('security')) score += 5;
      if (intentPrimary === 'objection_setup_time' && objLower.includes('setup')) score += 5;
      if (intentPrimary === 'objection_competitor' && (objLower.includes('already use') || objLower.includes('competitor'))) score += 5;
      if (intentPrimary === 'objection_think' && (objLower.includes('think') || objLower.includes('time'))) score += 5;

      if (score > 4 && (!bestMatch || score > bestMatch.score)) {
        bestMatch = { response: obj.jarvis_response, follow_up: obj.follow_up, score };
      }
    }

    return bestMatch;
  }

  // ── Competitor Matching ───────────────────────────────────────

  private matchCompetitor(msg: string): CompetitorEntry | null {
    const competitors = this.kb.competitors?.competitors;
    if (!competitors || !competitors.length) return null;

    for (const comp of competitors) {
      const name = comp.competitor_name.toLowerCase();
      if (msg.includes(name)) return comp;
    }
    return null;
  }

  // ── Response Builders ──────────────────────────────────────────

  private buildGreetingResponse(session: SessionLike): string {
    const ctx = session.context || {};
    const msgCount = session.message_count_today || 0;
    const industry = ctx.industry;
    const clickedVariant = ctx.variant as string | undefined;
    const entrySource = ctx.entry_source as string | undefined;

    // If they've been chatting a while, don't re-greet
    if (msgCount > 3) {
      const continuations = [
        "What else can I help you with? I'm your control — just ask.",
        "Anything else on your mind? I can cover pricing, features, demos — you name it.",
        "Where would you like to go from here? I'm your control center.",
      ];
      return this.pickRandom(continuations, session);
    }

    // PROACTIVE: If they came from models page with a specific variant
    if (clickedVariant && entrySource === 'models_page') {
      return `I see you were checking out **${clickedVariant}**! I'm **Jarvis** — your control from here. You can do anything just by chatting with me.\n\nHere's what **${clickedVariant}** can do for you:\n- Handle customer support tickets 24/7\n- Reduce response time to under 3 seconds\n- Save you up to 85% on support costs\n\nWant me to show you how it works, or would you like to compare it with other models?`;
    }

    // PROACTIVE: If they came from ROI Calculator
    if (entrySource === 'roi' && ctx.roi_result) {
      const roi = ctx.roi_result as Record<string, unknown>;
      const savingsPct = roi.savings_pct as string | undefined;
      if (savingsPct) {
        return `Based on your ROI calculation, you could save up to **${savingsPct}%**! I'm **Jarvis** — your control from here.\n\nI can show you exactly how PARWA delivers those savings. Want to see it in action?`;
      }
    }

    if (industry) {
      return `I'm **Jarvis** — your control from here. I see you're in the **${this.formatIndustry(industry)}** space.\n\nYou can do anything just by chatting with me. What would you like to explore?`;
    }

    return `Welcome! I'm **Jarvis** — your control from here. You can do anything just by chatting with me.\n\nI help businesses find the perfect AI customer support setup. What would you like to explore?`;
  }

  private buildGoodbyeResponse(session: SessionLike): string {
    const ctx = session.context || {};

    if (ctx.selected_variants && ctx.selected_variants.length > 0) {
      return `Thanks for chatting! Quick recap: you were looking at ${ctx.selected_variants.length} variant(s) for your ${ctx.industry ? this.formatIndustry(ctx.industry) : 'business'}.\n\nFeel free to come back anytime — I'll remember our conversation. You can also:\n- Ask me more questions about features or pricing\n- Try a demo scenario to see PARWA in action\n- Get started with a plan when you're ready\n\nHave a great day!`;
    }

    return `Thanks for chatting with me! Here's a quick summary:\n\n- **3 plans**: Starter ($999/mo), Growth ($2,499/mo), High ($3,999/mo)\n- **3 industries**: E-commerce, SaaS, Logistics\n- **20 AI agent variants** to choose from\n- **85-92% cost savings** vs hiring human agents\n\nCome back anytime — I'll be here! Have a great day!`;
  }

  private buildPricingResponse(session: SessionLike): string {
    const tiers = this.kb.pricing?.tiers;
    if (!tiers || tiers.length === 0) {
      return "PARWA offers three plans: **Starter** ($999/mo), **Growth** ($2,499/mo), and **High** ($3,999/mo). Each comes with different features and ticket limits. Would you like me to compare them in detail for your industry?";
    }

    const ctx = session.context || {};
    const variants = ctx.selected_variants || [];

    let response = "Here are PARWA's three plans:\n\n";

    for (const tier of tiers) {
      response += `**${tier.name} — $${tier.monthly_price.toLocaleString()}/mo**\n`;
      response += `- ${tier.ai_agents} AI agents | ${tier.tickets_per_month.toLocaleString()} tickets/mo | ${tier.channels.join(', ')}\n`;
      if (tier.voice_support) response += `- Voice support included\n`;
      response += `- Overage: $${tier.overage_per_ticket}/ticket\n\n`;
    }

    response += `**Annual billing** saves 15% on all plans.\n`;
    response += `**No long-term contracts** — cancel anytime with 30 days notice.\n`;

    if (variants.length > 0) {
      response += `\nYou've selected ${variants.length} variant(s). Want me to show you a bill summary with the total?`;
    } else {
      response += `\nWhich plan sounds like the right fit for your business? I can also calculate your specific ROI.`;
    }

    return response;
  }

  private buildIndustryResponse(industry: string, session: SessionLike): string {
    const industries = this.kb.industries?.industries;
    if (!industries) return `I'd love to tell you about our ${industry} solutions! PARWA offers industry-specific AI agents that automate the most common support tickets. What specific aspect interests you?`;

    const industryKey = industry === 'ecommerce' ? 'ecommerce' :
                        industry === 'saas' ? 'saas' :
                        industry === 'logistics' ? 'logistics' :
                        industry === 'logistics' ? 'logistics' : null;

    if (!industryKey || !industries[industryKey]) {
      // Try to find by partial match
      for (const [key, group] of Object.entries(industries)) {
        if (industry.includes(key) || key.includes(industry)) {
          return this.formatIndustryResponse(group, session);
        }
      }
      return `PARWA supports 3 industries: **E-commerce, SaaS, and Logistics**. Each has 5 specialized AI agent variants. Which industry are you in? I'll show you the perfect setup.`;
    }

    return this.formatIndustryResponse(industries[industryKey], session);
  }

  private formatIndustryResponse(group: IndustryGroup, session: SessionLike): string {
    let response = `**${group.name}** is one of PARWA's strongest verticals! Here are the 5 AI agents available:\n\n`;

    for (const v of group.variants) {
      response += `- **${v.name}** ($${v.price_per_unit}/mo) — ${v.description}\n`;
    }

    response += `\nEach agent handles ${Math.min(...group.variants.map(v => v.tickets_per_month))}-${Math.max(...group.variants.map(v => v.tickets_per_month))} tickets/month with ${Math.min(...group.variants.map(v => v.success_metrics?.target_resolution_rate || 90))}-${Math.max(...group.variants.map(v => v.success_metrics?.target_resolution_rate || 95))}% resolution rate.\n\n`;

    response += `Want me to show you how one of these agents works? Just ask, and I'll roleplay a real customer scenario!`;
    return response;
  }

  private buildVariantSpecificResponse(variantType: string, industry: string | null, session: SessionLike): string {
    const industries = this.kb.industries?.industries;
    if (!industries) return '';

    // Find the matching variant across all industries
    const variantKeywords: Record<string, string[]> = {
      returns: ['return', 'refund', 'exchange'],
      order: ['order status', 'order tracking', 'order management', 'track order'],
      shipping: ['shipping', 'delivery', 'dispatch', 'courier'],
      payment: ['payment', 'billing', 'charge', 'invoice', 'transaction'],
      faq: ['product question', 'faq', 'specification', 'how to use'],
      technical: ['technical', 'bug', 'error', 'troubleshoot', 'api'],
      billing_saas: ['subscription', 'plan upgrade', 'billing'],
      feature_request: ['feature request', 'roadmap', 'new feature'],
      api_support: ['api key', 'api documentation', 'integration'],
      account: ['account', 'login', 'password', 'settings'],
      tracking: ['shipment', 'tracking', 'track package'],
      delivery_issue: ['delivery issue', 'damaged', 'late delivery', 'missing'],
      warehouse: ['warehouse', 'inventory', 'stock'],
      fleet: ['fleet', 'driver', 'vehicle', 'route'],
      customs: ['customs', 'import', 'export', 'compliance'],
      appointment: ['appointment', 'scheduling', 'booking'],
      insurance: ['insurance', 'claim', 'coverage'],

    };

    const searchKey = Object.keys(variantKeywords).find(k =>
      variantType.includes(k) || k.includes(variantType)
    );

    if (!searchKey) return '';

    const keywords = variantKeywords[searchKey];
    const allVariants: VariantEntry[] = [];

    for (const [indKey, group] of Object.entries(industries)) {
      for (const v of group.variants) {
        const vLower = `${v.id} ${v.name} ${v.description}`.toLowerCase();
        if (keywords.some(kw => vLower.includes(kw))) {
          allVariants.push(v);
        }
      }
    }

    if (allVariants.length === 0) return '';

    // Prefer variant from the session's industry
    const preferred = industry ? allVariants.find(v => v.industry === industry || v.id.includes(industry)) : allVariants[0];
    const variant = preferred || allVariants[0];

    // Build a detailed response about this variant
    let response = `Great question about **${variant.name}**!\n\n`;
    response += `**What it handles:**\n`;
    for (const cap of (variant.what_it_handles || []).slice(0, 5)) {
      response += `- ${cap}\n`;
    }

    response += `\n**Here's how it works in practice:**\n`;
    response += `> **Customer:** "${variant.sample_query}"\n`;
    response += `> **Jarvis:** "${variant.sample_response}"\n\n`;

    response += `At **$${variant.price_per_unit}/month**, it handles up to **${variant.tickets_per_month} tickets/month** with an average response time of **${variant.success_metrics?.target_response_time_seconds || 3} seconds**.\n\n`;
    response += `Want to see another variant in action?`;

    return response;
  }

  private buildFeaturesResponse(session: SessionLike): string {
    const caps = this.kb.capabilities;
    if (!caps) {
      return `PARWA is a complete AI customer support platform. Key capabilities:\n\n- **24/7 automated ticket handling** across email, chat, phone, SMS\n- **Self-learning knowledge base** that gets smarter over time\n- **Smart escalation** to human agents when needed\n- **Multi-language support** (50+ languages)\n- **Advanced analytics** with real-time dashboards\n- **17+ integrations** with popular tools\n\nWant to know more about any specific feature?`;
    }

    const coreCaps = caps.core_capabilities || [];
    let response = "Here's what PARWA can do for your business:\n\n";

    for (const cap of coreCaps.slice(0, 6)) {
      const name = cap.name || cap.capability || '';
      const desc = cap.description || cap.details || '';
      response += `- **${name}**: ${desc}\n`;
    }

    const aiEngine = caps.ai_engine_details;
    if (aiEngine) {
      response += `\nPARWA uses a sophisticated AI engine with **${aiEngine.techniques?.length || 14} techniques** including NLP, sentiment analysis, intent classification (95%+ accuracy), and confidence scoring to ensure quality.\n`;
    }

    response += `\nWhich capability interests you most? Or want to see a live demo?`;
    return response;
  }

  private buildIntegrationsResponse(session: SessionLike): string {
    const integrations = this.kb.integrations;
    if (!integrations) {
      return "PARWA integrates with popular platforms:\n\n- **E-commerce**: Shopify, WooCommerce, Magento, BigCommerce\n- **Help Desk**: Zendesk, Freshdesk, Intercom, Help Scout\n- **Communication**: Slack, Email, WhatsApp\n- **Payment**: Stripe, Razorpay\n- **Custom**: REST API, Webhooks, SDKs\n\nSetup takes 10-45 minutes depending on complexity. Which integrations do you use?";
    }

    const categories = integrations.integration_categories || [];
    let response = "PARWA integrates with your existing tools seamlessly:\n\n";

    for (const cat of categories.slice(0, 4)) {
      const items = cat.integrations || [];
      response += `**${cat.category}:** `;
      response += items.map((i: any) => i.name).join(', ');
      response += '\n';
    }

    response += "\n**Custom Integration**: REST API + Webhooks + SDKs (Python, Node.js, Java, Go)\n\n";
    response += "Most integrations take 10-30 minutes to set up. Which ones are you currently using?";
    return response;
  }

  private buildSecurityResponse(): string {
    return "Data security is PARWA's top priority:\n\n- **Encryption**: AES-256 at rest, TLS 1.3 in transit\n- **Compliance**: GDPR, SOC 2 Type II, PCI DSS\n- **Data isolation**: Per-tenant isolation at app, DB, and infrastructure layers\n- **Audit trail**: Comprehensive logs with 24-month retention\n- **Access control**: RBAC with 2FA enforcement\n- **Vulnerability management**: Continuous monitoring with SLA-backed response times\n- **Data residency**: US, EU, and APAC options\n\nYour customer data is never used to train models for other clients. Every tenant is completely isolated. Want details on any specific security area?";
  }

  private buildROIResponse(session: SessionLike): string {
    const ctx = session.context || {};
    const talkingPoints = this.kb.pricing?.sales_talking_points;

    let response = "Here's the bottom line on PARWA's ROI:\n\n";

    response += "**Cost Comparison:**\n";
    response += "- Human support agent: **$8-12 per ticket** (salary + benefits + training)\n";
    response += "- PARWA AI: **under $1 per ticket** (Starter tier)\n\n";

    response += "**Plan-specific savings:**\n";
    response += "- **Starter ($999/mo)** vs 3 agents ($14K/mo) = **$156K/year saved**\n";
    response += "- **Growth ($2,499/mo)** vs 4 juniors ($18K/mo) = **$186K/year saved**\n";
    response += "- **High ($3,999/mo)** vs 5 seniors ($28K/mo) = **$288K/year saved**\n\n";

    response += "**Key metrics:**\n";
    response += "- **70% cost reduction** in support operations\n";
    response += "- **50% faster** average resolution time\n";
    response += "- **95%+ CSAT** score (AI responses)\n";
    response += "- ROI typically achieved within **30 days**\n\n";

    if (talkingPoints) {
      response += "Want me to calculate your specific savings? Just tell me:\n1. How many support agents do you have?\n2. What's your average ticket volume per month?";
    } else {
      response += "Want me to run a personalized ROI calculation for your business?";
    }

    return response;
  }

  private buildDemoResponse(industry: string | null, session: SessionLike): string {
    const scenarios = this.kb.demoScenarios?.scenarios;
    if (!scenarios || scenarios.length === 0) {
      return `Absolutely! I **am** the demo. Ask me anything your customers would ask, and I'll show you exactly how PARWA handles it.\n\nFor example:\n- "Where's my order #12345?"\n- "How do I reset my password?"\n- "Track my shipment"\n\nOr unlock the **$1 Demo Pack** for 500 messages + a 3-minute AI voice call!`;
    }

    const industryScenarios = industry
      ? scenarios.filter(s => s.industry === industry || s.industry.includes(industry))
      : scenarios.slice(0, 5);

    if (industryScenarios.length === 0) {
      let demoList = `Absolutely! I'd love to show you PARWA in action. Here are some demo scenarios I can roleplay:\n\n`;

      // Show one from each industry
      const sampleScenarios = [0, 5, 10, 15].map(i => scenarios[i]).filter(Boolean);
      for (const s of sampleScenarios.slice(0, 4)) {
        demoList += `- **${s.title}** (${s.industry})\n`;
      }
      return demoList + "\nWhich one interests you? Or ask me anything your customers would!";
    }

    const sample = this.pickRandom(industryScenarios, session);
    let response = `Great choice! Let me show you a real scenario:\n\n`;
    response += `**Scenario: ${sample.title}** (${sample.industry})\n\n`;
    response += `> **Customer:** "${sample.customer_message}"\n\n`;
    response += `Here's what I'd do:\n`;
    for (const step of (sample.expected_jarvis_behavior || []).slice(0, 4)) {
      response += `1. ${step}\n`;
    }
    response += `\n**Key talking points:**\n`;
    for (const tp of (sample.talking_points || []).slice(0, 3)) {
      response += `- ${tp}\n`;
    }
    response += `\nWant me to roleplay another scenario?`;
    return response;
  }

  private buildCompetitorResponse(competitor: CompetitorEntry, session: SessionLike): string {
    let response = `Here's how PARWA compares to **${competitor.competitor_name}**:\n\n`;
    response += `**PARWA's advantage:** ${competitor.our_advantage}\n\n`;

    if (competitor.key_differentiators && competitor.key_differentiators.length > 0) {
      response += "**Key differences:**\n";
      for (const diff of competitor.key_differentiators.slice(0, 4)) {
        const feature = diff.feature || '';
        const parwa = diff.parwa || diff.advantage || '';
        const them = diff.competitor || diff.disadvantage || '';
        response += `- **${feature}**: PARWA ${parwa} vs ${competitor.competitor_name} ${them}\n`;
      }
      response += '\n';
    }

    if (competitor.winning_argument) {
      response += `**Bottom line:** ${competitor.winning_argument}\n\n`;
    }

    response += "Want to explore other comparisons or see PARWA in action?";
    return response;
  }

  private buildHowItWorksResponse(session: SessionLike): string {
    return "Here's how PARWA works — it's simpler than you'd think:\n\n**1. Upload your knowledge base** (PDFs, docs, FAQs) — Jarvis learns from your content\n**2. Connect your channels** (email, chat, phone, SMS, social media)\n**3. AI starts handling tickets** immediately, 24/7\n\n**Under the hood:**\n- PARWA uses advanced AI to understand customer intent with **95%+ accuracy**\n- Each query is matched against your knowledge base and handled automatically\n- When confidence is low or the issue is complex, it **escalates to a human** with full context\n- Every resolved ticket makes the system smarter through **continuous auto-learning**\n\n**Setup takes 10-14 days** — most businesses are 90% operational within 2 weeks.\n\nWant to see it in action with a demo?";
  }

  private buildBuyResponse(session: SessionLike): string {
    return "Getting started is easy!\n\n**Three steps:**\n1. **Choose your plan** — Starter ($999), Growth ($2,499), or High ($3,999)\n2. **Add industry variants** — Pick the AI agents for your support needs\n3. **Go live** — Upload your KB, connect channels, and start!\n\n**No long-term contracts** — monthly billing, cancel anytime with 30 days notice.\n**15% discount** on annual billing.\n\nReady to pick a plan? I can show you the best fit for your business. Just tell me your industry and daily ticket volume!";
  }

  private buildEdgeCaseResponse(type: string): string {
    if (type === 'legal') {
      return "I appreciate the question, but I'm not able to provide legal advice. For legal matters, I'd recommend consulting with a qualified attorney.\n\nWhat I *can* help with is showing you how PARWA's AI can streamline your customer support operations. Would you like to explore that?";
    }
    if (type === 'professional') {
      return "I'm not able to provide professional advice — that should always come from a qualified professional.\n\nWhat I *can* help with is showing you how PARWA's AI can streamline your customer support operations. Would you like to explore that?";
    }
    return "That's outside my area of expertise, but I'd love to help you with anything related to PARWA's AI customer support platform! What would you like to know?";
  }

  private buildContextualResponse(msg: string, intent: IntentResult, session: SessionLike): string {
    const ctx = session.context || {};
    const industry = ctx.industry;

    // Use industry context if available
    if (industry && intent.entities.length === 0) {
      const industryName = this.formatIndustry(industry);
      const responses = [
        `Good question! Since you're in the **${industryName}** space, let me share what's most relevant.\n\nPARWA has 5 specialized AI agents for ${industryName} that handle the most common support tickets automatically — everything from ${industry === 'ecommerce' ? 'order tracking to returns and refunds' : industry === 'saas' ? 'technical support to billing questions' : industry === 'logistics' ? 'shipment tracking to delivery issues' : 'appointment scheduling to insurance verification'}.\n\nMost ${industryName} businesses start with our **Growth plan ($2,499/mo)** for the best value. Want specifics?`,
        `That's a great point. In the **${industryName}** industry, PARWA's AI agents typically resolve **${industry === 'ecommerce' ? '88-94%' : '85-95%'}** of support tickets automatically, saving your team ${industry === 'ecommerce' ? '30-40 hours per week' : '25-35 hours per week'}.\n\nWhat specific challenge are you facing with your current support setup?`,
        `Interesting! For **${industryName}** businesses like yours, here's what I'd recommend:\n\n1. Start with the most painful ticket type (what takes the most time?)\n2. Deploy 1-2 AI agents for that specific area\n3. Expand as you see results — most clients add more agents within 30 days\n\nWhat's the #1 support issue you want to solve?`,
      ];
      return this.pickRandom(responses, session);
    }

    // Generic contextual response using session stage
    const stage = session.detected_stage || ctx.detected_stage || 'discovery';

    if (stage === 'welcome' || stage === 'discovery') {
      return `I'd love to help! To give you the most relevant answer, could you tell me:\n\n1. **What industry** is your business in?\n2. **How many support tickets** do you handle per day?\n3. **What's the biggest pain point** with your current support?\n\nPARWA works across **E-commerce, SaaS, and Logistics** — each with specialized AI agents tailored to that industry.`;
    }

    if (stage === 'pricing') {
      return `Good question! PARWA's plans range from **$999/mo** to **$3,999/mo**, with the sweet spot for most businesses being **Growth at $2,499/mo**.\n\nWant a detailed plan comparison, or should I calculate the ROI for your specific situation?`;
    }

    if (stage === 'demo') {
      return `Sure thing! I can show you exactly how PARWA works. Just ask me anything your customers would ask — like "where's my order?", "how do I reset my password?", or "track my shipment" — and I'll demonstrate how the AI handles it in real time.\n\nWhat would you like to try?`;
    }

    // Final generic fallback
    const genericResponses = [
      `That's a great question! PARWA is an AI-powered customer support platform that handles tickets 24/7 across email, chat, phone, and SMS. We serve **4 industries** with **20 specialized AI agents**.\n\nTo give you the most helpful answer, could you share what industry you're in and what support challenges you're facing?`,
      `I appreciate the question! Let me help you find the right answer. PARWA automates customer support with AI that:\n\n- Resolves **60-70%** of tickets automatically\n- Responds in **2-5 seconds** average\n- Learns from your knowledge base continuously\n- Costs **85-92% less** than human agents\n\nWhat specific aspect would you like to dive deeper into?`,
      `Great question! I want to make sure I give you the most relevant information. PARWA has a lot to offer across different industries and use cases.\n\nCould you tell me a bit about your business? Specifically:\n- Your industry\n- Your daily ticket volume\n- Your current support setup\n\nThat way I can tailor my answer to exactly what you need.`,
    ];
    return this.pickRandom(genericResponses, session);
  }

  // ── Utility Methods ──────────────────────────────────────────

  private formatIndustry(ind: string): string {
    const map: Record<string, string> = {
      ecommerce: 'E-commerce', e_commerce: 'E-commerce',
      saas: 'SaaS', logistics: 'Logistics', others: 'Other',
    };
    return map[ind] || ind.charAt(0).toUpperCase() + ind.slice(1);
  }

  private pickRandom<T>(arr: T[], session: SessionLike): T {
    const recent = session.messages
      ?.filter(m => m.role === 'jarvis')
      .slice(-3)
      .map(m => m.content.toLowerCase()) || [];

    // Shuffle and pick first non-repeating
    const shuffled = [...arr].sort(() => Math.random() - 0.5);
    for (const item of shuffled) {
      const text = String(item).toLowerCase().slice(0, 60);
      if (!recent.some(r => r.includes(text) || text.includes(r.slice(0, 40)))) {
        return item;
      }
    }
    return arr[0];
  }

  private avoidRepetition(response: string, session: SessionLike): string {
    const recent = session.messages
      ?.filter(m => m.role === 'jarvis')
      .slice(-3)
      .map(m => m.content.toLowerCase()) || [];

    const responseLower = response.toLowerCase();

    // Check if this response is too similar to recent ones
    for (const recentMsg of recent) {
      const overlap = this.calculateOverlap(responseLower, recentMsg);
      if (overlap > 0.7) {
        // Too repetitive — add a follow-up to make it fresh
        const followUps = [
          '\n\nIs there anything specific you\'d like to explore further?',
          '\n\nWant me to dive deeper into any of these areas?',
          '\n\nWhat other questions do you have?',
          '\n\nLet me know if you\'d like to see a demo of any of this!',
        ];
        const freshFollowUp = followUps.find(f =>
          !recentMsg.includes(f.toLowerCase().slice(0, 30))
        ) || followUps[0];
        return response + freshFollowUp;
      }
    }

    return response;
  }

  private calculateOverlap(a: string, b: string): number {
    const wordsA = new Set(a.split(/\s+/).filter(w => w.length > 3));
    const wordsB = new Set(b.split(/\s+/).filter(w => w.length > 3));
    if (wordsA.size === 0) return 0;
    let matches = 0;
    for (const w of Array.from(wordsA)) {
      if (wordsB.has(w)) matches++;
    }
    return matches / wordsA.size;
  }

  private personalizeResponse(template: string, session: SessionLike): string {
    const ctx = session.context || {};
    let result = template;

    if (ctx.industry) {
      result = result.replace(/\{industry\}/g, this.formatIndustry(ctx.industry));
    }
    if (ctx.selected_variants && ctx.selected_variants.length > 0) {
      result = result.replace(/\{variant_count\}/g, String(ctx.selected_variants.length));
    }
    if (ctx.roi_result) {
      result = result.replace(/\{roi\}/g, JSON.stringify(ctx.roi_result));
    }

    return result;
  }
}

export default JarvisAIEngine;
