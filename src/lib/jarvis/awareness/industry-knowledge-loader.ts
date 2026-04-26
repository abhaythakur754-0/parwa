/**
 * JARVIS Industry Knowledge Loader
 * 
 * Loads industry-specific knowledge and configurations for JARVIS.
 * This enables domain-aware responses based on client's industry.
 */

import type { Industry } from '../integration/types';

// ── Industry Knowledge Types ─────────────────────────────────────────

export interface IndustryVariant {
  id: string;
  name: string;
  description: string;
  tickets_per_month: number;
  price_per_unit: number;
  currency: string;
  what_it_handles: string[];
  sample_query: string;
  sample_response: string;
  setup_requirements: string[];
  success_metrics: {
    target_resolution_rate: number;
    target_csat: number;
    target_response_time_seconds: number;
    target_first_contact_resolution: number;
    typical_deflection_rate: number;
  };
}

export interface IndustryConfig {
  id: string;
  name: string;
  description: string;
  variants: IndustryVariant[];
}

export interface IndustryKnowledge {
  industry: Industry | null;
  config: IndustryConfig | null;
  terminology: Record<string, string>;
  commonQueries: string[];
  escalationTriggers: string[];
  responseTemplates: Record<string, string>;
}

// ── Industry Mapping ─────────────────────────────────────────────────

const INDUSTRY_ID_MAP: Record<Industry, string> = {
  ecommerce: 'e-commerce',
  saas: 'saas',
  logistics: 'logistics',
  finance: 'finance',
  education: 'education',
  real_estate: 'real_estate',
  manufacturing: 'manufacturing',
  consulting: 'consulting',
  agency: 'agency',
  nonprofit: 'nonprofit',
  hospitality: 'hospitality',
  retail: 'retail',
  other: 'other',
};

// ── Industry Terminology ─────────────────────────────────────────────

const INDUSTRY_TERMINOLOGY: Record<Industry, Record<string, string>> = {
  ecommerce: {
    order: 'Purchase transaction',
    cart: 'Shopping basket',
    checkout: 'Payment process',
    sku: 'Product identifier',
    refund: 'Money back',
    return: 'Send back item',
    shipping: 'Delivery',
    tracking: 'Package location',
    variant: 'Product option',
    inventory: 'Stock',
    conversion: 'Purchase completion',
    checkout_abandonment: 'Incomplete purchase',
  },
  saas: {
    subscription: 'Recurring plan',
    tier: 'Plan level',
    seat: 'User license',
    usage: 'Feature consumption',
    api: 'Integration endpoint',
    webhook: 'Event notification',
    token: 'Authentication key',
    plan: 'Subscription tier',
    billing_cycle: 'Payment period',
    proration: 'Partial billing',
    churn: 'Customer leaving',
    mrr: 'Monthly revenue',
  },
  logistics: {
    shipment: 'Package delivery',
    freight: 'Cargo transport',
    carrier: 'Shipping company',
    tracking: 'Location status',
    pod: 'Delivery confirmation',
    eta: 'Arrival time',
    warehouse: 'Storage facility',
    dispatch: 'Send out',
    route: 'Delivery path',
    last_mile: 'Final delivery',
    consignment: 'Shipment batch',
    customs: 'Border clearance',
  },
  finance: {
    account: 'Financial record',
    transaction: 'Money movement',
    balance: 'Current amount',
    ledger: 'Transaction log',
    reconciliation: 'Account matching',
    deposit: 'Money in',
    withdrawal: 'Money out',
    fee: 'Service charge',
    interest: 'Earnings on balance',
    principal: 'Original amount',
    amortization: 'Payment schedule',
    compliance: 'Regulatory adherence',
  },
  education: {
    enrollment: 'Course registration',
    course: 'Learning program',
    module: 'Course section',
    assessment: 'Knowledge test',
    grade: 'Score',
    transcript: 'Academic record',
    semester: 'Academic period',
    tuition: 'Course fee',
    credit: 'Learning unit',
    prerequisite: 'Required prior course',
    certification: 'Credential',
    instructor: 'Teacher',
  },
  real_estate: {
    listing: 'Property for sale',
    showing: 'Property viewing',
    offer: 'Purchase proposal',
    closing: 'Sale completion',
    escrow: 'Fund holding',
    appraisal: 'Value assessment',
    inspection: 'Property check',
    title: 'Ownership document',
    deed: 'Ownership transfer',
    commission: 'Agent fee',
    mls: 'Property database',
    lease: 'Rental agreement',
  },
  manufacturing: {
    production: 'Making process',
    assembly: 'Putting together',
    quality_control: 'Product checking',
    batch: 'Production group',
    lead_time: 'Production time',
    raw_materials: 'Input components',
    finished_goods: 'Completed products',
    work_order: 'Production instruction',
    capacity: 'Production limit',
    yield: 'Output rate',
    downtime: 'Stop time',
    sku: 'Product code',
  },
  consulting: {
    engagement: 'Project',
    deliverable: 'Work product',
    milestone: 'Progress point',
    scope: 'Work boundaries',
    retainer: 'Ongoing agreement',
    sow: 'Work description',
    billable: 'Chargeable time',
    utilization: 'Work rate',
    client: 'Customer',
    stakeholder: 'Interested party',
    proposal: 'Work offer',
    case_study: 'Success story',
  },
  agency: {
    campaign: 'Marketing effort',
    creative: 'Design work',
    deliverable: 'Work product',
    revision: 'Change request',
    brief: 'Work instruction',
    milestone: 'Progress point',
    pitch: 'Proposal',
    impression: 'Ad view',
    click_through: 'Ad click',
    conversion: 'Goal completion',
    roi: 'Return metric',
    brand: 'Client identity',
  },
  nonprofit: {
    donation: 'Gift',
    grant: 'Funding award',
    program: 'Service activity',
    beneficiary: 'Person helped',
    volunteer: 'Unpaid helper',
    campaign: 'Fundraising effort',
    impact: 'Effect achieved',
    stewardship: 'Donor care',
    endowment: 'Invested funds',
    '501c3': 'Tax status',
    fundraising: 'Money raising',
    mission: 'Organization purpose',
  },
  hospitality: {
    reservation: 'Booking',
    check_in: 'Arrival',
    check_out: 'Departure',
    occupancy: 'Room usage',
    rate: 'Price',
    amenity: 'Guest feature',
    guest: 'Customer',
    room_type: 'Accommodation kind',
    housekeeping: 'Room cleaning',
    concierge: 'Guest service',
    no_show: 'Missed booking',
    channel: 'Booking source',
  },
  retail: {
    pos: 'Sales system',
    inventory: 'Stock',
    markdown: 'Price reduction',
    shrinkage: 'Stock loss',
    foot_traffic: 'Store visitors',
    conversion: 'Purchase rate',
    basket: 'Items bought',
    transaction: 'Sale',
    loyalty: 'Rewards program',
    merchandising: 'Product display',
    supplier: 'Product source',
    sku: 'Product code',
  },
  other: {},
};

// ── Common Queries by Industry ───────────────────────────────────────

const INDUSTRY_COMMON_QUERIES: Record<Industry, string[]> = {
  ecommerce: [
    'Where is my order?',
    'I want to return this item',
    'Can I change my shipping address?',
    'What is your refund policy?',
    'Is this product in stock?',
    'My payment was declined',
    'I received the wrong item',
    'Can I cancel my order?',
  ],
  saas: [
    'How do I upgrade my plan?',
    'I forgot my password',
    'How do I add team members?',
    'Can I get a refund?',
    'My account is locked',
    'How do I cancel my subscription?',
    'The export is timing out',
    'How do I set up the API?',
  ],
  logistics: [
    'Where is my shipment?',
    'My package was damaged',
    'Can I change delivery address?',
    'What is the ETA?',
    'I missed my delivery',
    'How do I track my cargo?',
    'Customs clearance issues',
    ' Freight quote request',
  ],
  finance: [
    'What is my account balance?',
    'I see an unauthorized transaction',
    'How do I dispute a charge?',
    'When will my deposit clear?',
    'I need a statement',
    'How do I transfer funds?',
    'What are the fees?',
    'How do I close my account?',
  ],
  education: [
    'How do I enroll?',
    'What are the prerequisites?',
    'I need a transcript',
    'Can I get an extension?',
    'How do I access my course?',
    'What is the refund policy?',
    'I need technical support',
    'How do I get certified?',
  ],
  real_estate: [
    'When is the showing?',
    'What is the asking price?',
    'Has my offer been accepted?',
    'When is the closing date?',
    'I need to schedule an inspection',
    'What are the HOA fees?',
    'Is the property still available?',
    'Can I extend the contract?',
  ],
  manufacturing: [
    'What is the lead time?',
    'Can you expedite production?',
    'What is the batch number?',
    'I need a quality report',
    'When will my order ship?',
    'Can I modify my order?',
    'What materials are used?',
    'I have a defective product',
  ],
  consulting: [
    'What is the project status?',
    'Can we extend the engagement?',
    'I need the deliverables',
    'What are the next steps?',
    'Can we schedule a meeting?',
    'I have feedback on the report',
    'What is the timeline?',
    'Can we adjust the scope?',
  ],
  agency: [
    'When will the designs be ready?',
    'Can I make a revision?',
    'What is the campaign performance?',
    'I need to pause the campaign',
    'Can we change the brief?',
    'What is the budget status?',
    'I need analytics access',
    'Can we scale the campaign?',
  ],
  nonprofit: [
    'How can I donate?',
    'Is my donation tax-deductible?',
    'How is my money used?',
    'Can I set up recurring donations?',
    'I need a receipt',
    'How do I volunteer?',
    'What programs do you offer?',
    'Can I sponsor a child?',
  ],
  hospitality: [
    'Can I change my reservation?',
    'What time is check-in?',
    'I need to cancel my booking',
    'What amenities are available?',
    'Is breakfast included?',
    'Can I get a late checkout?',
    'I have a special request',
    'What is the cancellation policy?',
  ],
  retail: [
    'Do you have this in stock?',
    'Can I return this item?',
    'What is your price match policy?',
    'Do you offer layaway?',
    'Can I use multiple coupons?',
    'What are your store hours?',
    'Is this item on sale?',
    'Do you have a loyalty program?',
  ],
  other: [
    'I have a question',
    'I need help',
    'Can I speak to someone?',
    'How does this work?',
  ],
};

// ── Escalation Triggers by Industry ───────────────────────────────────

const INDUSTRY_ESCALATION_TRIGGERS: Record<Industry, string[]> = {
  ecommerce: [
    'chargeback',
    'fraud',
    'legal',
    'lawsuit',
    'attorney',
    'bbb',
    'better business',
    'sue',
    'report',
    'scam',
  ],
  saas: [
    'data breach',
    'security incident',
    'lawsuit',
    'legal action',
    'attorney',
    'compliance violation',
    'gdpr',
    'data loss',
    'audit',
  ],
  logistics: [
    'lost shipment',
    'stolen',
    'insurance claim',
    'legal',
    'lawsuit',
    'hazardous',
    'damage claim',
    'customs seizure',
  ],
  finance: [
    'fraud',
    'unauthorized',
    'identity theft',
    'regulatory',
    'compliance',
    'lawsuit',
    'legal action',
    'audit',
    'investigation',
  ],
  education: [
    'discrimination',
    'harassment',
    'safety concern',
    'legal',
    'lawsuit',
    'accreditation',
    'violation',
    'investigation',
  ],
  real_estate: [
    'discrimination',
    'fair housing',
    'lawsuit',
    'legal action',
    'breach of contract',
    'fraud',
    'title dispute',
    'escrow issue',
  ],
  manufacturing: [
    'product recall',
    'safety hazard',
    'defect',
    'injury',
    'lawsuit',
    'regulatory',
    'compliance',
    'quality failure',
  ],
  consulting: [
    'breach of contract',
    'conflict of interest',
    'confidentiality breach',
    'lawsuit',
    'legal action',
    'intellectual property',
    'fraud',
  ],
  agency: [
    'breach of contract',
    'intellectual property',
    'copyright',
    'lawsuit',
    'legal action',
    'fraud',
    'plagiarism',
  ],
  nonprofit: [
    'misuse of funds',
    'fraud',
    'donor complaint',
    'regulatory',
    'irs',
    'lawsuit',
    'investigation',
    'scandal',
  ],
  hospitality: [
    'safety concern',
    'discrimination',
    'lawsuit',
    'injury',
    'theft',
    'harassment',
    'legal action',
    'health code',
  ],
  retail: [
    'discrimination',
    'injury',
    'lawsuit',
    'legal action',
    'fraud',
    'theft',
    'safety hazard',
    'product recall',
  ],
  other: [
    'legal',
    'lawsuit',
    'attorney',
    'fraud',
    'investigation',
  ],
};

// ── Response Templates by Industry ─────────────────────────────────────

const INDUSTRY_RESPONSE_TEMPLATES: Record<Industry, Record<string, string>> = {
  ecommerce: {
    order_status: 'I found your order #{order_id}. It is currently {status}. Expected delivery: {eta}.',
    return_initiated: 'I have initiated a return for your {item}. You will receive a prepaid label at {email}.',
    refund_processed: 'Your refund of {amount} has been processed to your {payment_method}. It should appear in 5-7 business days.',
  },
  saas: {
    subscription_updated: 'Your subscription has been updated to {plan}. Your new billing cycle starts {date}.',
    account_issue: 'I have {action} your account. You should receive a confirmation email shortly.',
    technical_issue: 'I have identified the issue: {issue}. Here is how to resolve it: {solution}',
  },
  logistics: {
    shipment_status: 'Your shipment {tracking_number} is currently {status}. Expected delivery: {eta}.',
    delivery_exception: 'There is an exception with your shipment: {reason}. We are working to resolve it.',
    pod_request: 'Proof of delivery for shipment {tracking_number}: Delivered on {date} at {time}. Signed by: {signatory}.',
  },
  finance: {
    account_balance: 'Your account balance as of {date} is {amount}.',
    transaction_dispute: 'I have initiated a dispute for transaction {transaction_id}. Reference number: {reference}.',
    payment_confirmation: 'Payment of {amount} has been processed. Confirmation number: {confirmation}.',
  },
  education: {
    enrollment_confirmed: 'You have been enrolled in {course}. Start date: {date}. Access link: {link}.',
    grade_inquiry: 'Your grade for {course} is {grade}. If you have questions, please contact your instructor.',
    transcript_request: 'Your transcript has been requested. It will be sent to {email} within {days} business days.',
  },
  real_estate: {
    showing_confirmed: 'Your showing for {address} is confirmed for {date} at {time}. Agent: {agent_name}.',
    offer_status: 'Your offer on {address} is currently {status}. Next steps: {next_steps}.',
    closing_update: 'Closing for {address} is scheduled for {date}. Required documents: {documents}.',
  },
  manufacturing: {
    order_status: 'Production order {order_id} is {status}. Estimated completion: {eta}.',
    quality_report: 'Quality report for batch {batch_id}: {result}. Certificate available at {link}.',
    lead_time: 'Lead time for {product} is currently {days} days. Rush options available.',
  },
  consulting: {
    milestone_update: 'Milestone {name} has been {status}. Next deliverable due: {date}.',
    deliverable_ready: 'Deliverable {name} is ready for review. Access link: {link}.',
    meeting_scheduled: 'Meeting scheduled for {date} at {time}. Agenda: {agenda}. Participants: {participants}.',
  },
  agency: {
    campaign_update: 'Campaign {name} is {status}. Current metrics: {metrics}.',
    creative_ready: 'Creative assets for {campaign} are ready for review. Revision count: {revisions}.',
    performance_report: 'Performance report for {period}: {summary}. Key insights: {insights}.',
  },
  nonprofit: {
    donation_confirmed: 'Thank you for your donation of {amount}! Tax receipt: {receipt_number}. Impact: {impact}.',
    volunteer_signup: 'You are registered for {event} on {date}. Location: {location}. What to bring: {items}.',
    program_info: 'Our {program} program {description}. How to participate: {instructions}.',
  },
  hospitality: {
    reservation_confirmed: 'Your reservation at {property} is confirmed for {dates}. Confirmation: {confirmation}.',
    cancellation: 'Your reservation has been cancelled. Cancellation reference: {reference}. Refund: {refund_info}.',
    amenity_info: 'Available amenities: {amenities}. Additional requests can be made at check-in.',
  },
  retail: {
    stock_check: 'Item {sku} is {availability} at {store}. {additional_info}.',
    return_policy: 'Our return policy: {policy}. For this item specifically: {item_policy}.',
    loyalty_points: 'You have {points} points. Current tier: {tier}. Points to next tier: {needed}.',
  },
  other: {},
};

// ── Industry Knowledge Loader Class ────────────────────────────────────

export class IndustryKnowledgeLoader {
  private knowledgeCache: Map<Industry, IndustryKnowledge> = new Map();

  /**
   * Load industry knowledge for a specific industry
   */
  async loadIndustryKnowledge(industry: Industry | null | undefined): Promise<IndustryKnowledge> {
    // Default knowledge for missing/null industry
    if (!industry) {
      return this.getDefaultKnowledge();
    }

    // Check cache first
    if (this.knowledgeCache.has(industry)) {
      return this.knowledgeCache.get(industry)!;
    }

    // Build knowledge for industry
    const knowledge: IndustryKnowledge = {
      industry,
      config: null, // Would load from JSON files in production
      terminology: INDUSTRY_TERMINOLOGY[industry] || {},
      commonQueries: INDUSTRY_COMMON_QUERIES[industry] || [],
      escalationTriggers: INDUSTRY_ESCALATION_TRIGGERS[industry] || [],
      responseTemplates: INDUSTRY_RESPONSE_TEMPLATES[industry] || {},
    };

    // Cache the result
    this.knowledgeCache.set(industry, knowledge);

    return knowledge;
  }

  /**
   * Get default knowledge when industry is not specified
   */
  private getDefaultKnowledge(): IndustryKnowledge {
    return {
      industry: null,
      config: null,
      terminology: {},
      commonQueries: [],
      escalationTriggers: INDUSTRY_ESCALATION_TRIGGERS.other,
      responseTemplates: {},
    };
  }

  /**
   * Get industry-specific terminology
   */
  getTerminology(industry: Industry | null | undefined): Record<string, string> {
    if (!industry) return {};
    return INDUSTRY_TERMINOLOGY[industry] || {};
  }

  /**
   * Get common queries for an industry
   */
  getCommonQueries(industry: Industry | null | undefined): string[] {
    if (!industry) return [];
    return INDUSTRY_COMMON_QUERIES[industry] || [];
  }

  /**
   * Check if a message contains escalation triggers for an industry
   */
  hasEscalationTrigger(industry: Industry | null | undefined, message: string): boolean {
    if (!industry) return false;
    
    const triggers = INDUSTRY_ESCALATION_TRIGGERS[industry] || [];
    const lowerMessage = message.toLowerCase();
    
    return triggers.some(trigger => lowerMessage.includes(trigger.toLowerCase()));
  }

  /**
   * Get response template for an industry and scenario
   */
  getResponseTemplate(
    industry: Industry | null | undefined,
    scenario: string
  ): string | null {
    if (!industry) return null;
    
    const templates = INDUSTRY_RESPONSE_TEMPLATES[industry] || {};
    return templates[scenario] || null;
  }

  /**
   * Map frontend industry ID to knowledge base industry ID
   */
  mapIndustryToKnowledgeBase(industry: Industry): string {
    return INDUSTRY_ID_MAP[industry] || 'other';
  }

  /**
   * Clear the knowledge cache
   */
  clearCache(): void {
    this.knowledgeCache.clear();
  }
}

// ── Singleton Instance ────────────────────────────────────────────────

let loaderInstance: IndustryKnowledgeLoader | null = null;

export function getIndustryKnowledgeLoader(): IndustryKnowledgeLoader {
  if (!loaderInstance) {
    loaderInstance = new IndustryKnowledgeLoader();
  }
  return loaderInstance;
}

export function createIndustryKnowledgeLoader(): IndustryKnowledgeLoader {
  return new IndustryKnowledgeLoader();
}
