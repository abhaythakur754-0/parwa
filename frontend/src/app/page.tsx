'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { useAuth } from '@/lib/auth-context';
import { jarvisApi } from '@/lib/api';
import DashboardShell from '@/components/DashboardShell';
import SystemStatusBar from '@/components/SystemStatusBar';
import ActiveAgents from '@/components/ActiveAgents';
import LiveActivityFeed from '@/components/LiveActivityFeed';
import ChatPanel from '@/components/ChatPanel';
import GSDTerminal from '@/components/GSDTerminal';
import BatchApproval from '@/components/BatchApproval';
import UrgentAttention from '@/components/UrgentAttention';
import WorkforceMap from '@/components/WorkforceMap';
import WeeklyWinsBanner from '@/components/WeeklyWinsBanner';
import HealthCard from '@/components/HealthCard';
import AdaptationTracker from '@/components/AdaptationTracker';
import QualityPanel from '@/components/QualityPanel';
import SLAPanel from '@/components/SLAPanel';
import ApprovalPanel from '@/components/ApprovalPanel';
import FlagPanel from '@/components/FlagPanel';
import Wave8Panel from '@/components/Wave8Panel';
import VoiceCommand from '@/components/VoiceCommand';
import { useMetrics } from '@/hooks/useMetrics';
import { JarvisLogo, JarvisSpinner, JarvisErrorBox } from '@/components/ui';

// ── Landing Page ──────────────────────────────────────────
function LandingPage() {
  const router = useRouter();
  const { login } = useAuth();
  const [showSignIn, setShowSignIn] = useState(false);
  const [signEmail, setSignEmail] = useState('');
  const [signPassword, setSignPassword] = useState('');
  const [signInError, setSignInError] = useState('');
  const [signingIn, setSigningIn] = useState(false);

  const handleSignIn = async () => {
    if (!signEmail || !signPassword) {
      setSignInError('Email and password required');
      return;
    }
    setSigningIn(true);
    setSignInError('');
    try {
      const result = await jarvisApi.login({ email: signEmail, password: signPassword });
      login({
        tenantId: result.tenant_id || result.tenantId || '',
        tenantName: result.company_name || result.tenantName || result.tenant_id || 'My Company',
        adminEmail: signEmail,
        jwtToken: result.jwt_token || result.jwtToken || result.token || '',
        apiKey: result.api_key || result.apiKey || '',
        tier: result.tier || '',
      });
      router.push('/');
    } catch (err: any) {
      setSignInError(err.message || 'Login failed');
    } finally {
      setSigningIn(false);
    }
  };

  return (
    <div className="min-h-screen bg-jarvis-bg flex flex-col">
      {/* Header */}
      <header className="border-b border-jarvis-border px-6 py-4">
        <div className="max-w-5xl mx-auto flex items-center justify-between">
          <JarvisLogo subtitle="AI Operating System" />
          <button
            onClick={() => setShowSignIn(!showSignIn)}
            className="jarvis-btn-ghost text-xs"
          >
            {showSignIn ? 'CLOSE' : 'SIGN IN'}
          </button>
        </div>
      </header>

      {/* Main */}
      <main className="flex-1 flex flex-col items-center justify-center px-6 py-12">
        <div className="max-w-3xl w-full text-center fade-in">
          {/* Hero */}
          <div className="mb-10">
          <div className="flex justify-center mb-6">
            <JarvisLogo size="lg" />
          </div>
            <h2 className="text-2xl sm:text-3xl font-bold text-jarvis-text tracking-wider mb-3">
              AI Operating System <span className="text-jarvis-green">for Business</span>
            </h2>
            <p className="text-xs text-jarvis-muted max-w-lg mx-auto leading-relaxed">
              Autonomous AI agents that handle customer support tickets end-to-end — from classification to resolution.
              Self-learning, policy-aware, and continuously improving.
            </p>
          </div>

          {/* CTA */}
          <div className="mb-12">
            <button
              onClick={() => router.push('/onboarding')}
              className="jarvis-btn-primary text-sm px-8 py-3 glow-green"
            >
              GET STARTED →
            </button>
          </div>

          {/* Feature cards */}
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 text-left">
            <FeatureCard
              icon="◉"
              color="cyan"
              title="Awareness"
              desc="Real-time monitoring of all customer interactions across channels. See what your AI agents are doing at every moment."
            />
            <FeatureCard
              icon="◈"
              color="green"
              title="Control"
              desc="Define policies, set boundaries, and approve or reject actions. The AI operates within the rules you set — never beyond."
            />
            <FeatureCard
              icon="◎"
              color="yellow"
              title="Intelligence"
              desc="Continuous learning from corrections, drift detection, and quality scoring. Your system gets smarter with every interaction."
            />
          </div>
        </div>
      </main>

      {/* Sign In Modal */}
      {showSignIn && (
        <div className="fixed inset-0 z-50 bg-black/60 flex items-center justify-center p-4">
          <div className="jarvis-card max-w-sm w-full border-jarvis-border" onClick={(e) => e.stopPropagation()}>
            <div className="flex items-center justify-between mb-4">
              <span className="text-sm font-bold text-jarvis-text tracking-wider">SIGN IN</span>
              <button
                onClick={() => { setShowSignIn(false); setSignInError(''); }}
                className="text-jarvis-muted hover:text-jarvis-text text-xs"
              >
                ✕
              </button>
            </div>

            <div className="mb-3">
              <JarvisErrorBox message={signInError} />
            </div>

            <div className="space-y-3">
              <div>
                <label className="text-[10px] text-jarvis-muted tracking-wider uppercase">Email</label>
                <input
                  type="email"
                  className="jarvis-input mt-1 text-xs w-full"
                  placeholder="admin@company.com"
                  value={signEmail}
                  onChange={(e) => setSignEmail(e.target.value)}
                />
              </div>
              <div>
                <label className="text-[10px] text-jarvis-muted tracking-wider uppercase">Password</label>
                <input
                  type="password"
                  className="jarvis-input mt-1 text-xs w-full"
                  placeholder="••••••••"
                  value={signPassword}
                  onChange={(e) => setSignPassword(e.target.value)}
                  onKeyDown={(e) => e.key === 'Enter' && handleSignIn()}
                />
              </div>
              <button
                onClick={handleSignIn}
                disabled={signingIn}
                className="jarvis-btn-primary text-xs w-full disabled:opacity-50"
              >
                {signingIn ? (
                  <span className="flex items-center justify-center gap-2">
                    <JarvisSpinner size="xs" />
                    SIGNING IN...
                  </span>
                ) : (
                  'SIGN IN →'
                )}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Footer */}
      <footer className="border-t border-jarvis-border px-6 py-3 mt-auto">
        <div className="max-w-5xl mx-auto flex items-center justify-between">
          <span className="text-[10px] text-jarvis-muted tracking-widest">JARVIS.OS PHASE-9</span>
          <span className="text-[10px] text-jarvis-muted tracking-widest">PARWA AI SYSTEMS</span>
        </div>
      </footer>
    </div>
  );
}

function FeatureCard({ icon, color, title, desc }: { icon: string; color: string; title: string; desc: string }) {
  const colorMap: Record<string, string> = {
    cyan: 'text-jarvis-cyan',
    green: 'text-jarvis-green',
    yellow: 'text-jarvis-yellow',
  };
  return (
    <div className="jarvis-card">
      <span className={`text-xl ${colorMap[color] || 'text-jarvis-muted'}`}>{icon}</span>
      <h3 className="text-xs font-bold text-jarvis-text tracking-wider mt-2 mb-1">{title}</h3>
      <p className="text-[10px] text-jarvis-muted leading-relaxed">{desc}</p>
    </div>
  );
}

// ── Dashboard Content ──────────────────────────────────────
function DashboardContent() {
  const { data: metrics } = useMetrics(7);

  return (
    <DashboardShell>
      {/* Weekly Wins Banner */}
      <div className="mb-4">
        <WeeklyWinsBanner />
      </div>

      {/* Urgent Attention (sticky) */}
      <div className="mb-4">
        <UrgentAttention />
      </div>

      {/* System Status Bar */}
      <div className="mb-4">
        <SystemStatusBar />
      </div>

      {/* Metrics Summary Cards */}
      {metrics && (
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mb-4">
          <MetricCard label="Total Tasks" value={metrics.total_tasks} icon="◉" color="text-jarvis-cyan" />
          <MetricCard label="Auto-Resolved" value={metrics.auto_resolved} icon="✓" color="text-jarvis-green" />
          <MetricCard label="Batched" value={metrics.batched} icon="◈" color="text-jarvis-yellow" />
          <MetricCard label="Escalated" value={metrics.escalated} icon="▲" color="text-jarvis-red" />
        </div>
      )}

      {/* Row 1: Chat + Activity Feed + Agents */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4 mb-4">
        <div className="lg:col-span-2">
          <ChatPanel compact />
        </div>
        <div className="lg:col-span-1 space-y-4">
          <ActiveAgents />
        </div>
      </div>

      {/* Row 2: GSD Terminal + Batch Approvals */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 mb-4">
        <GSDTerminal />
        <BatchApproval />
      </div>

      {/* Row 3: Activity Feed + Workforce Map */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4 mb-4">
        <div className="lg:col-span-2">
          <LiveActivityFeed />
        </div>
        <div className="lg:col-span-1">
          <WorkforceMap />
        </div>
      </div>

      {/* Row 4: Health + Adaptation + Quality */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4 mb-4">
        <HealthCard />
        <AdaptationTracker />
        <QualityPanel />
      </div>

      {/* Row 5: SLA + Approvals + Flags */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4 mb-4">
        <SLAPanel />
        <ApprovalPanel />
        <FlagPanel />
      </div>

      {/* Row 6: Wave 8 — Advanced Features */}
      <div className="mb-4">
        <div className="flex items-center gap-2 mb-2">
          <span className="text-[10px] text-jarvis-cyan tracking-[0.2em] uppercase font-bold">WAVE 8</span>
          <span className="text-[9px] text-jarvis-muted">Advanced — Agent Creation, Co-Pilot, Voice, DSPy</span>
          <div className="flex-1 h-px bg-jarvis-border/30" />
        </div>
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
          <div className="lg:col-span-2">
            <Wave8Panel />
          </div>
          <div>
            <VoiceCommand />
          </div>
        </div>
      </div>
    </DashboardShell>
  );
}

function MetricCard({ label, value, icon, color }: { label: string; value: number; icon: string; color: string }) {
  return (
    <div className="jarvis-card flex items-center gap-3">
      <span className={`text-xl ${color}`}>{icon}</span>
      <div>
        <div className={`text-lg font-bold tabular-nums ${color}`}>
          {typeof value === 'number' ? value.toLocaleString() : value}
        </div>
        <div className="text-[10px] text-jarvis-muted tracking-wider uppercase">{label}</div>
      </div>
    </div>
  );
}

// ── Smart Router ───────────────────────────────────────────
export default function RootPage() {
  const { isAuthenticated, isLoading } = useAuth();

  if (isLoading) {
    return (
      <div className="min-h-screen bg-jarvis-bg flex items-center justify-center">
        <JarvisSpinner size="md" label="INITIALIZING SYSTEM..." />
      </div>
    );
  }

  if (!isAuthenticated) {
    return <LandingPage />;
  }

  return <DashboardContent />;
}
