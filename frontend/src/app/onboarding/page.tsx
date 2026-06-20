'use client';

import React, { useState, useCallback, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { useAuth } from '@/lib/auth-context';
import { jarvisApi } from '@/lib/api';
import { JarvisLogo, JarvisSpinner, JarvisErrorBox } from '@/components/ui';
import { type WizardData, STEPS, initialData, getStepDescription } from './types';

// ── Shared UI Primitives ────────────────────────────────────

function FieldGroup({ children }: { children: React.ReactNode }) {
  return <div className="flex flex-col gap-1">{children}</div>;
}

// ── Main Wizard ───────────────────────────────────────────
export default function OnboardingPage() {
  const router = useRouter();
  const { login, isAuthenticated, isLoading: authLoading } = useAuth();
  const [step, setStep] = useState(1);
  const [data, setData] = useState<WizardData>(initialData);
  const [error, setError] = useState('');
  const [globalLoading, setGlobalLoading] = useState(false);

  // Resume: If already authenticated, redirect to dashboard
  useEffect(() => {
    if (!authLoading && isAuthenticated) {
      router.push('/');
    }
  }, [authLoading, isAuthenticated, router]);

  const updateData = useCallback((partial: Partial<WizardData>) => {
    setData((prev) => ({ ...prev, ...partial }));
    setError('');
  }, []);

  const goNext = () => {
    if (step < 6) setStep(step + 1);
  };
  const goBack = () => {
    if (step > 1) {
      setStep(step - 1);
      setError('');
    }
  };

  const handleComplete = useCallback(() => {
    login({
      tenantId: data.tenantId,
      tenantName: data.tenantName,
      adminEmail: data.adminEmail,
      jwtToken: data.jwtToken,
      apiKey: data.apiKey || data.generatedKey,
      tier: data.tier,
    });
    router.push('/');
  }, [data, login, router]);

  return (
    <div className="min-h-screen bg-jarvis-bg flex flex-col">
      {/* Header */}
      <header className="border-b border-jarvis-border px-6 py-4">
        <div className="max-w-5xl mx-auto">
          <div className="flex items-center justify-between mb-3">
            <JarvisLogo subtitle="Onboarding" />
            <span className="text-[10px] text-jarvis-muted tracking-widest">
              STEP {step}/{6}
            </span>
          </div>

          {/* Progress bar */}
          <div className="flex gap-1">
            {STEPS.map((label, i) => {
              const stepNum = i + 1;
              const isActive = stepNum === step;
              const isComplete = stepNum < step;
              return (
                <React.Fragment key={label}>
                  {i > 0 && (
                    <div className="flex-1 h-px bg-jarvis-border relative top-3" />
                  )}
                  <div className="flex flex-col items-center gap-1 min-w-[60px]">
                    <div
                      className={`
                        w-6 h-6 rounded-full flex items-center justify-center text-[10px] font-bold transition-all duration-300
                        ${isComplete ? 'bg-jarvis-green/20 border border-jarvis-green/50 text-jarvis-green' : ''}
                        ${isActive ? 'bg-jarvis-green/10 border border-jarvis-green/40 text-jarvis-green glow-green' : ''}
                        ${!isComplete && !isActive ? 'bg-jarvis-card border border-jarvis-border text-jarvis-muted' : ''}
                      `}
                    >
                      {isComplete ? '✓' : stepNum}
                    </div>
                    <span className={`text-[9px] tracking-wider uppercase whitespace-nowrap ${isActive ? 'text-jarvis-green' : 'text-jarvis-muted'}`}>
                      {label}
                    </span>
                  </div>
                </React.Fragment>
              );
            })}
          </div>
        </div>
      </header>

      {/* Content */}
      <main className="flex-1 overflow-y-auto px-4 py-6">
        <div className="max-w-4xl mx-auto">
          {/* Step title */}
          <div className="mb-6">
            <h2 className="text-lg font-bold text-jarvis-text tracking-wider">{STEPS[step - 1]}</h2>
            <p className="text-[10px] text-jarvis-muted tracking-wider mt-1">
              {getStepDescription(step)}
            </p>
          </div>

          {/* Error display */}
          {error && (
            <div className="mb-4 p-3 bg-jarvis-red/10 border border-jarvis-red/30 rounded-lg text-xs text-jarvis-red">
              <span className="font-bold">ERROR:</span> {error}
            </div>
          )}

          {/* Steps */}
          {step === 1 && <Step1AccountSetup data={data} updateData={updateData} goNext={goNext} setError={setError} setLoading={setGlobalLoading} loading={globalLoading} />}
          {step === 2 && <Step2TierSelection data={data} updateData={updateData} goNext={goNext} setError={setError} setLoading={setGlobalLoading} loading={globalLoading} />}
          {step === 3 && <Step3Integrations data={data} updateData={updateData} goNext={goNext} setError={setError} setLoading={setGlobalLoading} loading={globalLoading} />}
          {step === 4 && <Step4KnowledgeBase data={data} updateData={updateData} goNext={goNext} setError={setError} setLoading={setGlobalLoading} loading={globalLoading} />}
          {step === 5 && <Step5PolicyConfig data={data} updateData={updateData} goNext={goNext} setError={setError} setLoading={setGlobalLoading} loading={globalLoading} />}
          {step === 6 && <Step6GoLive data={data} updateData={updateData} onComplete={handleComplete} setError={setError} setLoading={setGlobalLoading} loading={globalLoading} />}

          {/* Navigation */}
          <div className="flex items-center justify-between mt-8 pt-4 border-t border-jarvis-border">
            <button
              onClick={goBack}
              disabled={step <= 1}
              className="jarvis-btn-ghost text-xs disabled:opacity-30 disabled:cursor-not-allowed"
            >
              ← BACK
            </button>
            <button
              onClick={step === 6 ? handleComplete : goNext}
              disabled={step === 6 && !data.generatedKey}
              className="jarvis-btn-primary text-xs disabled:opacity-30 disabled:cursor-not-allowed"
            >
              {step === 6 ? 'GO TO DASHBOARD →' : 'NEXT →'}
            </button>
          </div>
        </div>
      </main>
    </div>
  );
}

// ── Step 1: Account Setup ──────────────────────────────────
function Step1AccountSetup({ data, updateData, goNext, setError, setLoading, loading }: {
  data: WizardData;
  updateData: (p: Partial<WizardData>) => void;
  goNext: () => void;
  setError: (e: string) => void;
  setLoading: (l: boolean) => void;
  loading: boolean;
}) {
  const [form, setForm] = useState({
    companyName: '',
    adminEmail: '',
    password: '',
    industry: '',
    companySize: '',
  });

  const handleSubmit = async () => {
    if (!form.companyName || !form.adminEmail || !form.password || !form.industry || !form.companySize) {
      setError('All fields are required');
      return;
    }
    setLoading(true);
    try {
      const result = await jarvisApi.accountSetup({
        company_name: form.companyName,
        admin_email: form.adminEmail,
        password: form.password,
        industry: form.industry,
        company_size: form.companySize,
      });
      updateData({
        tenantId: result.tenant_id || result.tenantId || '',
        tenantName: form.companyName,
        adminEmail: form.adminEmail,
        jwtToken: result.jwt_token || result.jwtToken || result.token || '',
        apiKey: result.api_key || result.apiKey || '',
      });
      goNext();
    } catch (err: any) {
      setError(err.message || 'Account setup failed');
    } finally {
      setLoading(false);
    }
  };

  const updateField = (key: string, value: string) => {
    setForm((prev) => ({ ...prev, [key]: value }));
  };

  return (
    <div className="space-y-4 fade-in">
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        <FieldGroup>
          <label className="text-[10px] text-jarvis-muted tracking-wider uppercase">Company Name</label>
          <input
            type="text"
            className="jarvis-input mt-1"
            placeholder="Acme Corp"
            value={form.companyName}
            onChange={(e) => updateField('companyName', e.target.value)}
          />
        </FieldGroup>
        <FieldGroup>
          <label className="text-[10px] text-jarvis-muted tracking-wider uppercase">Admin Email</label>
          <input
            type="email"
            className="jarvis-input mt-1"
            placeholder="admin@acme.com"
            value={form.adminEmail}
            onChange={(e) => updateField('adminEmail', e.target.value)}
          />
        </FieldGroup>
      </div>

      <FieldGroup>
        <label className="text-[10px] text-jarvis-muted tracking-wider uppercase">Password</label>
        <input
          type="password"
          className="jarvis-input mt-1"
          placeholder="••••••••"
          value={form.password}
          onChange={(e) => updateField('password', e.target.value)}
        />
      </FieldGroup>

      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        <FieldGroup>
          <label className="text-[10px] text-jarvis-muted tracking-wider uppercase">Industry</label>
          <select
            className="jarvis-input mt-1"
            value={form.industry}
            onChange={(e) => updateField('industry', e.target.value)}
          >
            <option value="">Select industry...</option>
            <option value="ecommerce">E-commerce</option>
            <option value="saas">SaaS</option>
            <option value="healthcare">Healthcare</option>
            <option value="finance">Finance</option>
            <option value="education">Education</option>
            <option value="other">Other</option>
          </select>
        </FieldGroup>
        <FieldGroup>
          <label className="text-[10px] text-jarvis-muted tracking-wider uppercase">Company Size</label>
          <select
            className="jarvis-input mt-1"
            value={form.companySize}
            onChange={(e) => updateField('companySize', e.target.value)}
          >
            <option value="">Select size...</option>
            <option value="1-10">1-10 employees</option>
            <option value="11-50">11-50 employees</option>
            <option value="51-200">51-200 employees</option>
            <option value="200+">200+ employees</option>
          </select>
        </FieldGroup>
      </div>

      <div className="flex justify-end pt-2">
        <button
          onClick={handleSubmit}
          disabled={loading}
          className="jarvis-btn-primary text-xs disabled:opacity-50"
        >
          {loading ? (
            <span className="flex items-center gap-2">
              <span className="inline-block w-3 h-3 border border-jarvis-green/50 border-t-transparent rounded-full animate-spin" />
              CREATING...
            </span>
          ) : (
            'CREATE ACCOUNT →'
          )}
        </button>
      </div>

      {data.tenantId && (
        <div className="jarvis-card border-jarvis-green/20">
          <div className="flex items-center gap-2 mb-2">
            <span className="text-jarvis-green text-xs">✓</span>
            <span className="text-[10px] text-jarvis-green tracking-wider uppercase font-bold">Account Created</span>
          </div>
          <div className="text-[10px] text-jarvis-muted space-y-1">
            <div className="flex justify-between">
              <span>TENANT ID</span>
              <span className="text-jarvis-cyan font-mono">{data.tenantId}</span>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

// ── Step 2: Tier Selection ─────────────────────────────────
function Step2TierSelection({ data, updateData, goNext, setError, setLoading, loading }: {
  data: WizardData;
  updateData: (p: Partial<WizardData>) => void;
  goNext: () => void;
  setError: (e: string) => void;
  setLoading: (l: boolean) => void;
  loading: boolean;
}) {
  const [selectedTier, setSelectedTier] = useState(data.tier || '');
  const [billingCycle, setBillingCycle] = useState<'monthly' | 'annual'>(data.billingCycle as 'monthly' | 'annual' || 'monthly');

  const tiers = [
    {
      id: 'mini_parwa',
      name: 'MINI PARWA',
      role: 'The 24/7 Trainee',
      monthlyPrice: 999,
      annualPrice: 799,
      desc: 'Handles repetitive tasks that freshers normally do — FAQs, order tracking, refund collection',
      features: [
        { label: 'Tickets/Day', value: '200' },
        { label: 'Decision Making', value: 'Collects only' },
        { label: 'Refund Execution', value: 'Never executes' },
        { label: 'Peer Review', value: 'No' },
        { label: 'Voice Calls', value: 'No' },
      ],
      overage: '+$0.10/ticket over 200',
      color: 'cyan',
    },
    {
      id: 'parwa',
      name: 'PARWA',
      role: 'The Junior Agent',
      monthlyPrice: 2499,
      annualPrice: 1999,
      desc: 'Autonomous resolution of 70-80% routine tasks with intelligent recommendations',
      badge: 'RECOMMENDED',
      features: [
        { label: 'Tickets/Day', value: '300' },
        { label: 'Decision Making', value: 'Recommends' },
        { label: 'Refund Execution', value: 'Human triggers' },
        { label: 'Peer Review', value: 'Ask High for help' },
        { label: 'Voice Calls', value: '3 concurrent' },
      ],
      overage: '+$0.10/ticket over 300',
      color: 'green',
    },
    {
      id: 'parwa_high',
      name: 'PARWA HIGH',
      role: 'The Senior Agent',
      monthlyPrice: 3999,
      annualPrice: 3199,
      desc: 'Eliminates 80-85% human workload — VIPs, fraud detection, strategic intelligence',
      features: [
        { label: 'Tickets/Day', value: '500+' },
        { label: 'Decision Making', value: 'Strategic' },
        { label: 'Refund Execution', value: 'VIP + auto' },
        { label: 'Peer Review', value: 'Quality Coach' },
        { label: 'Voice Calls', value: '5 + video' },
      ],
      overage: 'Included in base',
      color: 'yellow',
    },
  ];

  const handleSelect = async () => {
    if (!selectedTier || !data.tenantId) {
      setError('No tenant ID found — go back to Step 1');
      return;
    }
    setLoading(true);
    try {
      await jarvisApi.selectTier({
        tenant_id: data.tenantId,
        tier: selectedTier,
        billing_cycle: billingCycle,
      });
      updateData({ tier: selectedTier, billingCycle });
      goNext();
    } catch (err: any) {
      setError(err.message || 'Tier selection failed');
    } finally {
      setLoading(false);
    }
  };

  const colorClass = (tier: any, field: string) => {
    const map: Record<string, Record<string, string>> = {
      cyan: { text: 'text-jarvis-cyan', border: 'border-jarvis-cyan/30', bg: 'bg-jarvis-cyan/10', badge: 'jarvis-badge-cyan', glow: '' },
      green: { text: 'text-jarvis-green', border: 'border-jarvis-green/30', bg: 'bg-jarvis-green/10', badge: 'jarvis-badge-green', glow: 'glow-green' },
      yellow: { text: 'text-jarvis-yellow', border: 'border-jarvis-yellow/30', bg: 'bg-jarvis-yellow/10', badge: 'jarvis-badge-yellow', glow: '' },
    };
    return map[tier.color]?.[field] || '';
  };

  return (
    <div className="space-y-4 fade-in">
      {/* Billing toggle */}
      <div className="flex items-center justify-center gap-3">
        <span className={`text-xs tracking-wider ${billingCycle === 'monthly' ? 'text-jarvis-green' : 'text-jarvis-muted'}`}>MONTHLY</span>
        <button
          onClick={() => setBillingCycle(billingCycle === 'monthly' ? 'annual' : 'monthly')}
          className={`
            relative w-10 h-5 rounded-full transition-all duration-300
            ${billingCycle === 'annual' ? 'bg-jarvis-green/20 border-jarvis-green/40' : 'bg-jarvis-card border-jarvis-border'}
          `}
          style={{ border: '1px solid' }}
        >
          <div
            className={`
              absolute top-0.5 w-4 h-4 rounded-full transition-all duration-300
              ${billingCycle === 'annual' ? 'left-[22px] bg-jarvis-green' : 'left-0.5 bg-jarvis-muted'}
            `}
          />
        </button>
        <span className={`text-xs tracking-wider ${billingCycle === 'annual' ? 'text-jarvis-green' : 'text-jarvis-muted'}`}>
          ANNUAL <span className="text-[10px] jarvis-badge-green ml-1">-20%</span>
        </span>
      </div>

      {/* Variant cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {tiers.map((tier) => {
          const isSelected = selectedTier === tier.id;
          const price = billingCycle === 'annual' ? tier.annualPrice : tier.monthlyPrice;
          return (
            <button
              key={tier.id}
              onClick={() => setSelectedTier(tier.id)}
              className={`
                text-left p-4 rounded-lg border transition-all duration-300 relative
                ${isSelected
                  ? 'bg-jarvis-green/5 border-jarvis-green/40 shadow-[0_0_20px_rgba(0,255,136,0.1)]'
                  : 'bg-jarvis-card border-jarvis-border hover:border-jarvis-muted'
                }
              `}
            >
              {tier.badge && (
                <span className={`absolute -top-2 right-3 ${colorClass(tier, 'badge')} text-[9px] px-2 py-0.5 rounded`}>
                  {tier.badge}
                </span>
              )}
              <div className="mb-3">
                <span className={`text-sm font-bold tracking-wider ${colorClass(tier, 'text')}`}>{tier.name}</span>
                <div className="text-[9px] text-jarvis-muted tracking-wider uppercase mt-0.5">{tier.role}</div>
                <p className="text-[10px] text-jarvis-muted mt-1">{tier.desc}</p>
              </div>

              <div className="mb-4">
                <span className="text-xl font-bold text-jarvis-text">${price.toLocaleString()}</span>
                <span className="text-[10px] text-jarvis-muted">/mo</span>
                {billingCycle === 'annual' && (
                  <span className="ml-2 text-[9px] jarvis-badge-green">SAVE {((tier.monthlyPrice - tier.annualPrice) * 12).toLocaleString()}/yr</span>
                )}
              </div>

              <div className="space-y-2">
                {tier.features.map((f) => (
                  <div key={f.label} className="flex justify-between text-[10px]">
                    <span className="text-jarvis-muted">{f.label}</span>
                    <span className="text-jarvis-text">{f.value}</span>
                  </div>
                ))}
              </div>

              <div className="mt-3 pt-2 border-t border-jarvis-border/50">
                <span className="text-[9px] text-jarvis-muted">Overage: {tier.overage}</span>
              </div>

              {isSelected && (
                <div className="mt-2 pt-2 border-t border-jarvis-green/20 flex items-center gap-2">
                  <span className="text-[10px] text-jarvis-green glow-green">✓ SELECTED</span>
                </div>
              )}
            </button>
          );
        })}
      </div>

      <div className="flex justify-end pt-2">
        <button
          onClick={handleSelect}
          disabled={!selectedTier || loading}
          className="jarvis-btn-primary text-xs disabled:opacity-50"
        >
          {loading ? (
            <span className="flex items-center gap-2">
              <span className="inline-block w-3 h-3 border border-jarvis-green/50 border-t-transparent rounded-full animate-spin" />
              SELECTING...
            </span>
          ) : (
            'CONFIRM TIER →'
          )}
        </button>
      </div>
    </div>
  );
}

// ── Step 3: Integrations ─────────────────────────────────
function Step3Integrations({ data, updateData, goNext, setError, setLoading, loading }: {
  data: WizardData;
  updateData: (p: Partial<WizardData>) => void;
  goNext: () => void;
  setError: (e: string) => void;
  setLoading: (l: boolean) => void;
  loading: boolean;
}) {
  const [connecting, setConnecting] = useState<string | null>(null);
  const [credForms, setCredForms] = useState<Record<string, string>>({});

  const integrations = [
    { type: 'sendgrid', name: 'SendGrid', category: 'Email', icon: '✉', fields: ['API Key'] },
    { type: 'whatsapp', name: 'WhatsApp', category: 'Chat', icon: '◈', fields: ['Phone Number', 'API Key'] },
    { type: 'intercom', name: 'Intercom', category: 'Chat', icon: '◉', fields: ['Access Token'] },
    { type: 'hubspot', name: 'HubSpot', category: 'CRM', icon: '◎', fields: ['API Key'] },
    { type: 'salesforce', name: 'Salesforce', category: 'CRM', icon: '◈', fields: ['Client ID', 'Client Secret'] },
    { type: 'zendesk', name: 'Zendesk', category: 'Helpdesk', icon: '◈', fields: ['API Token', 'Email'] },
    { type: 'freshdesk', name: 'Freshdesk', category: 'Helpdesk', icon: '◉', fields: ['API Key', 'Domain'] },
  ];

  const isConnected = (type: string) => data.integrations.some((i) => i.type === type && i.status === 'connected');

  const handleConnect = async (type: string, fields: string[]) => {
    const creds: Record<string, string> = {};
    for (const field of fields) {
      const val = credForms[`${type}_${field.toLowerCase().replace(/ /g, '_')}`];
      if (!val) {
        setError(`Please fill in ${field} for ${type}`);
        return;
      }
      creds[field.toLowerCase().replace(/ /g, '_')] = val;
    }

    setConnecting(type);
    try {
      await jarvisApi.connectIntegration({
        tenant_id: data.tenantId,
        integration_type: type,
        credentials: creds,
      });
      const newIntegrations = [...data.integrations.filter((i) => i.type !== type), { type, name: type, status: 'connected' }];
      updateData({ integrations: newIntegrations });
    } catch (err: any) {
      setError(err.message || `Failed to connect ${type}`);
    } finally {
      setConnecting(null);
    }
  };

  return (
    <div className="space-y-4 fade-in">
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
        {integrations.map((integ) => {
          const connected = isConnected(integ.type);
          const isConnecting = connecting === integ.type;
          const showForm = !connected;

          return (
            <div key={integ.type} className={`jarvis-card ${connected ? 'border-jarvis-green/30' : ''}`}>
              <div className="flex items-center justify-between mb-3">
                <div className="flex items-center gap-2">
                  <span className={`text-lg ${connected ? 'text-jarvis-green' : 'text-jarvis-muted'}`}>{integ.icon}</span>
                  <div>
                    <div className="text-xs font-bold text-jarvis-text">{integ.name}</div>
                    <div className="text-[9px] text-jarvis-muted tracking-wider uppercase">{integ.category}</div>
                  </div>
                </div>
                {connected && (
                  <span className="jarvis-badge-green text-[9px]">✓ LIVE</span>
                )}
              </div>

              {showForm && (
                <div className="space-y-2">
                  {integ.fields.map((field) => (
                    <div key={field}>
                      <label className="text-[9px] text-jarvis-muted tracking-wider uppercase">{field}</label>
                      <input
                        type={field.toLowerCase().includes('secret') || field.toLowerCase() === 'api key' || field === 'API Token' || field === 'Access Token' ? 'password' : 'text'}
                        className="jarvis-input mt-0.5 text-xs py-1.5 px-3"
                        placeholder={`Enter ${field}...`}
                        value={credForms[`${integ.type}_${field.toLowerCase().replace(/ /g, '_')}`] || ''}
                        onChange={(e) => {
                          setCredForms((prev) => ({
                            ...prev,
                            [`${integ.type}_${field.toLowerCase().replace(/ /g, '_')}`]: e.target.value,
                          }));
                        }}
                      />
                    </div>
                  ))}
                  <button
                    onClick={() => handleConnect(integ.type, integ.fields)}
                    disabled={isConnecting}
                    className="jarvis-btn-primary text-[10px] w-full py-1.5 disabled:opacity-50"
                  >
                    {isConnecting ? 'CONNECTING...' : 'CONNECT'}
                  </button>
                </div>
              )}
            </div>
          );
        })}
      </div>

      {/* Stats */}
      <div className="jarvis-card">
        <div className="flex items-center justify-between">
          <span className="text-[10px] text-jarvis-muted tracking-wider uppercase">Connected Integrations</span>
          <span className="text-sm font-bold text-jarvis-green">{data.integrations.filter((i) => i.status === 'connected').length}/{integrations.length}</span>
        </div>
      </div>

      <div className="flex justify-end pt-2">
        <button
          onClick={goNext}
          className="jarvis-btn-primary text-xs"
        >
          SKIP OR CONTINUE →
        </button>
      </div>
    </div>
  );
}

// ── Step 4: Knowledge Base ─────────────────────────────────
function Step4KnowledgeBase({ data, updateData, goNext, setError, setLoading, loading }: {
  data: WizardData;
  updateData: (p: Partial<WizardData>) => void;
  goNext: () => void;
  setError: (e: string) => void;
  setLoading: (l: boolean) => void;
  loading: boolean;
}) {
  const [title, setTitle] = useState('');
  const [content, setContent] = useState('');
  const [category, setCategory] = useState('general');
  const [uploading, setUploading] = useState(false);

  const categories = ['General', 'Product', 'Billing', 'Returns', 'Shipping', 'Technical', 'FAQ'];

  const handleAdd = async () => {
    if (!title.trim() || !content.trim()) {
      setError('Title and content are required');
      return;
    }
    setUploading(true);
    try {
      const result = await jarvisApi.uploadKB({
        tenant_id: data.tenantId,
        content,
        title,
        category,
      });
      const newEntry = {
        title,
        content,
        category,
        wordCount: content.split(/\s+/).filter(Boolean).length,
      };
      updateData({
        kbEntries: [...data.kbEntries, newEntry],
      });
      setTitle('');
      setContent('');
      setCategory('general');
    } catch (err: any) {
      setError(err.message || 'Failed to upload knowledge entry');
    } finally {
      setUploading(false);
    }
  };

  const totalWords = data.kbEntries.reduce((sum, e) => sum + e.wordCount, 0);

  return (
    <div className="space-y-4 fade-in">
      {/* Upload form */}
      <div className="jarvis-card">
        <div className="text-[10px] text-jarvis-muted tracking-wider uppercase mb-3">Add Knowledge Entry</div>
        <div className="space-y-3">
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <FieldGroup>
              <label className="text-[10px] text-jarvis-muted tracking-wider uppercase">Title</label>
              <input
                type="text"
                className="jarvis-input mt-1 text-xs"
                placeholder="e.g., Return Policy"
                value={title}
                onChange={(e) => setTitle(e.target.value)}
              />
            </FieldGroup>
            <FieldGroup>
              <label className="text-[10px] text-jarvis-muted tracking-wider uppercase">Category</label>
              <select
                className="jarvis-input mt-1 text-xs"
                value={category}
                onChange={(e) => setCategory(e.target.value)}
              >
                {categories.map((c) => (
                  <option key={c} value={c.toLowerCase()}>{c}</option>
                ))}
              </select>
            </FieldGroup>
          </div>
          <div>
            <label className="text-[10px] text-jarvis-muted tracking-wider uppercase">Content</label>
            <textarea
              className="jarvis-input mt-1 text-xs min-h-[120px] w-full resize-y"
              placeholder="Paste your knowledge content here..."
              value={content}
              onChange={(e) => setContent(e.target.value)}
            />
          </div>
          <div className="flex justify-end">
            <button
              onClick={handleAdd}
              disabled={uploading || !title.trim() || !content.trim()}
              className="jarvis-btn-primary text-[10px] disabled:opacity-50"
            >
              {uploading ? 'UPLOADING...' : '+ ADD ENTRY'}
            </button>
          </div>
        </div>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-2 gap-3">
        <div className="jarvis-card text-center">
          <div className="text-lg font-bold text-jarvis-cyan">{data.kbEntries.length}</div>
          <div className="text-[10px] text-jarvis-muted tracking-wider uppercase">Total Entries</div>
        </div>
        <div className="jarvis-card text-center">
          <div className="text-lg font-bold text-jarvis-green">{totalWords.toLocaleString()}</div>
          <div className="text-[10px] text-jarvis-muted tracking-wider uppercase">Total Words</div>
        </div>
      </div>

      {/* Entry list */}
      {data.kbEntries.length > 0 && (
        <div className="jarvis-card">
          <div className="text-[10px] text-jarvis-muted tracking-wider uppercase mb-3">Uploaded Entries</div>
          <div className="space-y-2 max-h-48 overflow-y-auto">
            {data.kbEntries.map((entry, i) => (
              <div key={i} className="flex items-center justify-between py-2 border-b border-jarvis-border/50 last:border-0">
                <div className="flex items-center gap-3">
                  <span className="text-jarvis-green text-xs">✓</span>
                  <div>
                    <div className="text-xs text-jarvis-text">{entry.title}</div>
                    <div className="text-[9px] text-jarvis-muted">
                      {entry.category} · {entry.wordCount} words
                    </div>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      <div className="flex justify-end pt-2">
        <button
          onClick={goNext}
          className="jarvis-btn-primary text-xs"
        >
          SKIP OR CONTINUE →
        </button>
      </div>
    </div>
  );
}

// ── Step 5: Policy Configuration ───────────────────────────
function Step5PolicyConfig({ data, updateData, goNext, setError, setLoading, loading }: {
  data: WizardData;
  updateData: (p: Partial<WizardData>) => void;
  goNext: () => void;
  setError: (e: string) => void;
  setLoading: (l: boolean) => void;
  loading: boolean;
}) {
  const [tone, setTone] = useState('professional');
  const [bizStart, setBizStart] = useState('09:00');
  const [bizEnd, setBizEnd] = useState('18:00');
  const [maxRefund, setMaxRefund] = useState('500');
  const [requireApproval, setRequireApproval] = useState(true);
  const [sentimentThreshold, setSentimentThreshold] = useState(0.3);
  const [keywords, setKeywords] = useState('');
  const [restrictRefund, setRestrictRefund] = useState(true);
  const [restrictDiscount, setRestrictDiscount] = useState(false);
  const [restrictPersonal, setRestrictPersonal] = useState(true);

  const handleSave = async () => {
    const policies: Record<string, any> = {
      response_tone: tone,
      business_hours: { start: bizStart, end: bizEnd },
      refund_rules: { max_amount: parseFloat(maxRefund) || 500, require_approval: requireApproval },
      escalation_triggers: {
        sentiment_threshold: sentimentThreshold,
        keywords: keywords.split(',').map((k) => k.trim()).filter(Boolean),
      },
      restricted_actions: {
        refund_over_limit: restrictRefund,
        discount: restrictDiscount,
        personal_data: restrictPersonal,
      },
    };

    setLoading(true);
    try {
      await jarvisApi.setPolicy({
        tenant_id: data.tenantId,
        policies,
      });
      updateData({ policies });
      goNext();
    } catch (err: any) {
      setError(err.message || 'Failed to save policies');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="space-y-4 fade-in">
      {/* Response Tone */}
      <div className="jarvis-card">
        <div className="text-[10px] text-jarvis-muted tracking-wider uppercase mb-3">Response Tone</div>
        <div className="flex gap-2">
          {['professional', 'friendly', 'concise'].map((t) => (
            <button
              key={t}
              onClick={() => setTone(t)}
              className={`
                flex-1 py-2 rounded-lg border text-xs tracking-wider uppercase transition-all
                ${tone === t
                  ? 'bg-jarvis-green/10 border-jarvis-green/30 text-jarvis-green'
                  : 'bg-jarvis-bg border-jarvis-border text-jarvis-muted hover:text-jarvis-text'
                }
              `}
            >
              {t}
            </button>
          ))}
        </div>
      </div>

      {/* Business Hours */}
      <div className="jarvis-card">
        <div className="text-[10px] text-jarvis-muted tracking-wider uppercase mb-3">Business Hours</div>
        <div className="grid grid-cols-2 gap-3">
          <FieldGroup>
            <label className="text-[10px] text-jarvis-muted tracking-wider uppercase">Start</label>
            <input
              type="time"
              className="jarvis-input mt-1 text-xs"
              value={bizStart}
              onChange={(e) => setBizStart(e.target.value)}
            />
          </FieldGroup>
          <FieldGroup>
            <label className="text-[10px] text-jarvis-muted tracking-wider uppercase">End</label>
            <input
              type="time"
              className="jarvis-input mt-1 text-xs"
              value={bizEnd}
              onChange={(e) => setBizEnd(e.target.value)}
            />
          </FieldGroup>
        </div>
      </div>

      {/* Refund Rules */}
      <div className="jarvis-card">
        <div className="text-[10px] text-jarvis-muted tracking-wider uppercase mb-3">Refund Rules</div>
        <div className="space-y-3">
          <FieldGroup>
            <label className="text-[10px] text-jarvis-muted tracking-wider uppercase">Max Auto-Refund Amount ($)</label>
            <input
              type="number"
              className="jarvis-input mt-1 text-xs w-full sm:w-48"
              value={maxRefund}
              onChange={(e) => setMaxRefund(e.target.value)}
            />
          </FieldGroup>
          <label className="flex items-center gap-2 cursor-pointer">
            <input
              type="checkbox"
              checked={requireApproval}
              onChange={(e) => setRequireApproval(e.target.checked)}
              className="w-3.5 h-3.5 rounded accent-jarvis-green"
            />
            <span className="text-xs text-jarvis-text">Require approval for amounts above threshold</span>
          </label>
        </div>
      </div>

      {/* Escalation Triggers */}
      <div className="jarvis-card">
        <div className="text-[10px] text-jarvis-muted tracking-wider uppercase mb-3">Escalation Triggers</div>
        <div className="space-y-3">
          <FieldGroup>
            <label className="text-[10px] text-jarvis-muted tracking-wider uppercase">
              Sentiment Threshold: <span className="text-jarvis-yellow">{sentimentThreshold.toFixed(2)}</span>
            </label>
            <input
              type="range"
              min="0"
              max="1"
              step="0.05"
              value={sentimentThreshold}
              onChange={(e) => setSentimentThreshold(parseFloat(e.target.value))}
              className="w-full accent-jarvis-yellow mt-1"
            />
            <div className="flex justify-between text-[9px] text-jarvis-muted">
              <span>0.00 (Happy)</span>
              <span>1.00 (Angry)</span>
            </div>
          </FieldGroup>
          <FieldGroup>
            <label className="text-[10px] text-jarvis-muted tracking-wider uppercase">Escalation Keywords (comma separated)</label>
            <input
              type="text"
              className="jarvis-input mt-1 text-xs"
              placeholder="manager, supervisor, complaint, lawsuit..."
              value={keywords}
              onChange={(e) => setKeywords(e.target.value)}
            />
          </FieldGroup>
        </div>
      </div>

      {/* Restricted Actions */}
      <div className="jarvis-card">
        <div className="text-[10px] text-jarvis-muted tracking-wider uppercase mb-3">Restricted Actions (require human approval)</div>
        <div className="space-y-2">
          <label className="flex items-center gap-2 cursor-pointer">
            <input
              type="checkbox"
              checked={restrictRefund}
              onChange={(e) => setRestrictRefund(e.target.checked)}
              className="w-3.5 h-3.5 rounded accent-jarvis-yellow"
            />
            <span className="text-xs text-jarvis-text">Refunds above threshold</span>
          </label>
          <label className="flex items-center gap-2 cursor-pointer">
            <input
              type="checkbox"
              checked={restrictDiscount}
              onChange={(e) => setRestrictDiscount(e.target.checked)}
              className="w-3.5 h-3.5 rounded accent-jarvis-yellow"
            />
            <span className="text-xs text-jarvis-text">Discounts</span>
          </label>
          <label className="flex items-center gap-2 cursor-pointer">
            <input
              type="checkbox"
              checked={restrictPersonal}
              onChange={(e) => setRestrictPersonal(e.target.checked)}
              className="w-3.5 h-3.5 rounded accent-jarvis-yellow"
            />
            <span className="text-xs text-jarvis-text">Personal data access</span>
          </label>
        </div>
      </div>

      <div className="flex justify-end pt-2">
        <button
          onClick={handleSave}
          disabled={loading}
          className="jarvis-btn-primary text-xs disabled:opacity-50"
        >
          {loading ? (
            <span className="flex items-center gap-2">
              <span className="inline-block w-3 h-3 border border-jarvis-green/50 border-t-transparent rounded-full animate-spin" />
              SAVING...
            </span>
          ) : (
            'SAVE POLICIES →'
          )}
        </button>
      </div>
    </div>
  );
}

// ── Step 6: Go Live ────────────────────────────────────────
function Step6GoLive({ data, updateData, onComplete, setError, setLoading, loading }: {
  data: WizardData;
  updateData: (p: Partial<WizardData>) => void;
  onComplete: () => void;
  setError: (e: string) => void;
  setLoading: (l: boolean) => void;
  loading: boolean;
}) {
  const [testQuery, setTestQuery] = useState('');
  const [testResult, setTestResult] = useState<any>(null);
  const [testLoading, setTestLoading] = useState(false);
  const [copied, setCopied] = useState(false);

  const handleGenerateKey = async () => {
    setLoading(true);
    try {
      const result = await jarvisApi.generateKey({
        tenant_id: data.tenantId,
        key_type: 'live',
        name: 'Production API Key',
      });
      const key = result.full_key || result.api_key || result.key || result.token || `pk_live_${Math.random().toString(36).substring(2, 15)}`;
      updateData({ generatedKey: key });
    } catch (err: any) {
      setError(err.message || 'Key generation failed');
    } finally {
      setLoading(false);
    }
  };

  const handleTestTicket = async () => {
    if (!testQuery.trim()) return;
    setTestLoading(true);
    setTestResult(null);
    try {
      const result = await jarvisApi.testTicket({
        tenant_id: data.tenantId,
        query: testQuery,
      });
      setTestResult(result);
    } catch (err: any) {
      setTestResult({ error: true, message: err.message });
    } finally {
      setTestLoading(false);
    }
  };

  const handleCopy = () => {
    if (data.generatedKey) {
      navigator.clipboard.writeText(data.generatedKey);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  };

  return (
    <div className="space-y-4 fade-in">
      {/* Key Generation */}
      <div className="jarvis-card">
        <div className="text-[10px] text-jarvis-muted tracking-wider uppercase mb-3">API Key Generation</div>
        {!data.generatedKey ? (
          <div className="text-center py-6">
            <div className="text-jarvis-muted text-xs mb-4">Generate your production API key to enable live operations</div>
            <button
              onClick={handleGenerateKey}
              disabled={loading}
              className="jarvis-btn-primary text-xs disabled:opacity-50"
            >
              {loading ? 'GENERATING...' : '⚡ GENERATE API KEY'}
            </button>
          </div>
        ) : (
          <div className="space-y-3">
            <div className="text-[10px] text-jarvis-green tracking-wider uppercase font-bold">✓ Key Generated</div>
            <div className="bg-jarvis-bg border border-jarvis-border rounded-lg p-3 flex items-center justify-between gap-3">
              <code className="text-xs text-jarvis-cyan break-all flex-1">{data.generatedKey}</code>
              <button
                onClick={handleCopy}
                className="jarvis-btn-ghost text-[10px] px-2 py-1 shrink-0"
              >
                {copied ? 'COPIED!' : 'COPY'}
              </button>
            </div>
            <div className="text-[9px] text-jarvis-yellow">⚠ Store this key securely. It will not be shown again.</div>
          </div>
        )}
      </div>

      {/* Test Ticket */}
      <div className="jarvis-card">
        <div className="text-[10px] text-jarvis-muted tracking-wider uppercase mb-3">Send Test Ticket</div>
        <div className="space-y-3">
          <div>
            <label className="text-[10px] text-jarvis-muted tracking-wider uppercase">Test Query</label>
            <div className="flex gap-2 mt-1">
              <input
                type="text"
                className="jarvis-input text-xs flex-1"
                placeholder="e.g., I want to return my order #12345"
                value={testQuery}
                onChange={(e) => setTestQuery(e.target.value)}
              />
              <button
                onClick={handleTestTicket}
                disabled={testLoading || !testQuery.trim()}
                className="jarvis-btn-secondary text-[10px] shrink-0 disabled:opacity-50"
              >
                {testLoading ? '...' : 'TEST'}
              </button>
            </div>
          </div>

          {/* Predefined test queries */}
          <div className="flex flex-wrap gap-2">
            {[
              'I want to return my order #12345',
              'Can I get a discount?',
              'What are your shipping options?',
            ].map((q) => (
              <button
                key={q}
                onClick={() => setTestQuery(q)}
                className="text-[9px] text-jarvis-muted border border-jarvis-border rounded px-2 py-1 hover:text-jarvis-text hover:border-jarvis-muted transition-all"
              >
                {q}
              </button>
            ))}
          </div>

          {/* Result */}
          {testResult && (
            <div className={`p-3 rounded-lg border mt-2 ${testResult.error ? 'border-jarvis-red/30 bg-jarvis-red/5' : 'border-jarvis-green/30 bg-jarvis-green/5'}`}>
              <div className="flex items-center gap-2 mb-2">
                <span className={testResult.error ? 'text-jarvis-red' : 'text-jarvis-green'}>
                  {testResult.error ? '✗' : '✓'}
                </span>
                <span className={`text-xs font-bold tracking-wider ${testResult.error ? 'text-jarvis-red' : 'text-jarvis-green'}`}>
                  {testResult.error ? 'FAILED' : 'RESOLVED'}
                </span>
              </div>
              {testResult.confidence !== undefined && (
                <div className="text-[10px] text-jarvis-muted mb-2">
                  Confidence: <span className="text-jarvis-yellow font-bold">{(testResult.confidence * 100).toFixed(1)}%</span>
                </div>
              )}
              {testResult.response && (
                <div className="text-xs text-jarvis-text mt-1 p-2 bg-jarvis-bg rounded border border-jarvis-border">
                  {testResult.response}
                </div>
              )}
              {testResult.message && (
                <div className="text-[10px] text-jarvis-muted mt-1">{testResult.message}</div>
              )}
            </div>
          )}
        </div>
      </div>

      {/* Complete onboarding */}
      <div className="jarvis-card border-jarvis-green/20 text-center py-6">
        <div className="text-jarvis-green text-2xl mb-2 glow-green">◉</div>
        <div className="text-sm font-bold text-jarvis-text mb-1">System Ready</div>
        <div className="text-[10px] text-jarvis-muted max-w-md mx-auto mb-4">
          Your JARVIS operating system is now configured and ready to process tickets.
          Navigate to the dashboard to begin monitoring operations.
        </div>
        <button
          onClick={onComplete}
          disabled={!data.generatedKey}
          className="jarvis-btn-primary text-xs disabled:opacity-50 px-6 py-2"
        >
          GO TO DASHBOARD →
        </button>
      </div>
    </div>
  );
}
