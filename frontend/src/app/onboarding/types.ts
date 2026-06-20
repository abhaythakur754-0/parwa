// ── Shared Onboarding Types ──────────────────────────────────

export interface WizardData {
  tenantId: string;
  tenantName: string;
  adminEmail: string;
  jwtToken: string;
  apiKey: string;
  tier: string;
  billingCycle: string;
  integrations: Array<{ type: string; name: string; status: string }>;
  kbEntries: Array<{ title: string; content: string; category: string; wordCount: number }>;
  policies: Record<string, any>;
  generatedKey: string;
}

export const STEPS = [
  'Account Setup',
  'Select Tier',
  'Integrations',
  'Knowledge Base',
  'Policies',
  'Go Live',
] as const;

export const initialData: WizardData = {
  tenantId: '',
  tenantName: '',
  adminEmail: '',
  jwtToken: '',
  apiKey: '',
  tier: '',
  billingCycle: 'monthly',
  integrations: [],
  kbEntries: [],
  policies: {},
  generatedKey: '',
};

export function getStepDescription(step: number): string {
  const descs: Record<number, string> = {
    1: 'Create your company account to initialize the JARVIS operating system',
    2: 'Choose a pricing tier that matches your business requirements',
    3: 'Connect your communication channels and business tools',
    4: 'Upload your knowledge base so JARVIS understands your business',
    5: 'Configure response policies, escalation rules, and safety limits',
    6: 'Generate your API key and run a test ticket through the pipeline',
  };
  return descs[step] || '';
}
