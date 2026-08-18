/**
 * Integration test for the NEW 5-phase onboarding flow.
 *
 * NEW FLOW (no user-triggered build):
 * Phase 1: CRM Connect + Verify
 * Phase 2: CRM Analysis (loading) → AUTO-TRIGGERS agent build in background
 * Phase 3: Recommendations + Test each + Verify All button + Continue button
 *   (agents build in background while user fills integrations)
 * Verify checks 3 things: API keys work + MCP connected + agents ready
 * Continue button only activates when all 3 pass
 *
 * Run: npx jest src/components/onboarding/__tests__/SuperglueOnboardingFlow.5phase.test.tsx --no-coverage
 */

import React from 'react';
import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import '@testing-library/jest-dom';
import { SuperglueOnboardingFlow } from '../SuperglueOnboardingFlow';

const MOCK_VERIFY = {
  verified: true, superglue_ok: true, mcp_registered: true,
  system_id: 'hubspot', name: 'My HubSpot', url: 'https://api.hubapi.com',
  message: 'CRM verified',
};

const MOCK_ANALYSIS = {
  company_id: 'test', analyzed_at: '2026-08-18T00:00:00Z',
  connected_integrations: [], data_profile: { total_tickets: 50 },
  detected_gaps: [],
  recommendations: [
    { name: 'Stripe', priority: 'high', reason: 'Process refunds' },
  ],
  analysis_summary: 'Analyzed 50 tickets. Found 1 integration needed.',
};

const MOCK_TEST_OK = {
  system_id: 'stripe', works: true, status_code: 200,
  tested_at: '2026-08-18T00:00:00Z', message: '✓ Connection works (HTTP 200)',
};

const MOCK_TRIGGER = {
  triggered: true, total_agents: 1, created: 1, skipped_existing: 0, failed: 0,
  agents: [{ agent_name: 'Stripe', agent_role: 'Stripe Specialist', status: 'active', superglue_tool_id: 'tool-1' }],
};

const MOCK_STATUS_READY = {
  company_id: 'test', total_agents: 1, ready: 1, pending: 0, failed: 0, all_ready: true,
  agents: MOCK_TRIGGER.agents,
};

const MOCK_STATUS_BUILDING = {
  company_id: 'test', total_agents: 1, ready: 0, pending: 1, failed: 0, all_ready: false,
  agents: [{ agent_name: 'Stripe', agent_role: 'Stripe Specialist', status: 'pending' }],
};

let fetchMock: ReturnType<typeof jest.fn>;
let statusCallCount = 0;

beforeEach(() => {
  statusCallCount = 0;
  fetchMock = jest.fn();
  global.fetch = fetchMock as unknown as typeof global.fetch;

  fetchMock.mockImplementation((url: string, opts?: any) => {
    if (url === '/api/superglue/systems' && opts?.method === 'POST') {
      return Promise.resolve({ ok: true, json: () => Promise.resolve({ id: 'x', name: 'x', url: '', icon: '', credentials: {}, metadata: {} }) });
    }
    if (url.includes('/verify') && opts?.method === 'POST') {
      return Promise.resolve({ ok: true, json: () => Promise.resolve(MOCK_VERIFY) });
    }
    if (url === '/api/integrations/analyze' && opts?.method === 'POST') {
      return Promise.resolve({ ok: true, json: () => Promise.resolve(MOCK_ANALYSIS) });
    }
    if (url.includes('/test') && opts?.method === 'POST') {
      return Promise.resolve({ ok: true, json: () => Promise.resolve(MOCK_TEST_OK) });
    }
    if (url === '/api/onboarding-build/trigger' && opts?.method === 'POST') {
      return Promise.resolve({ ok: true, json: () => Promise.resolve(MOCK_TRIGGER) });
    }
    if (url === '/api/onboarding-build/status') {
      // First call returns "building", subsequent calls return "ready"
      statusCallCount++;
      const data = statusCallCount <= 1 ? MOCK_STATUS_BUILDING : MOCK_STATUS_READY;
      return Promise.resolve({ ok: true, json: () => Promise.resolve(data) });
    }
    return Promise.resolve({ ok: false, json: () => Promise.resolve({}) });
  });
});

afterEach(() => {
  jest.restoreAllMocks();
  jest.useRealTimers();
});

// Helper: complete Phase 1 + 2 (connect CRM → analysis → recommendations appear)
async function completePhase1And2() {
  render(<SuperglueOnboardingFlow />);
  fireEvent.click(screen.getByText('HubSpot'));
  await waitFor(() => expect(screen.getByText(/Connect HubSpot/)).toBeInTheDocument());
  fireEvent.change(screen.getByPlaceholderText('My HubSpot Account'), { target: { value: 'My HubSpot' } });
  fireEvent.change(screen.getByPlaceholderText('https://api.hubapi.com'), { target: { value: 'https://api.hubapi.com' } });
  fireEvent.click(screen.getByText('Connect & Verify'));
  await waitFor(() => expect(screen.getByText('Stripe')).toBeInTheDocument());
}

// Helper: connect + test a recommendation
// Now connectRecommendation opens a form modal — need to fill it + submit
async function connectAndTestRecommendation() {
  await completePhase1And2();
  // Click Connect (opens the form modal)
  fireEvent.click(screen.getAllByText('Connect')[0]);
  // Wait for the form modal to appear
  await waitFor(() => expect(screen.getByText(/Connect Stripe/)).toBeInTheDocument());
  // Fill the URL field (API form, not database form)
  fireEvent.change(screen.getByPlaceholderText('https://api.yourcrm.com'), { target: { value: 'https://api.stripe.com' } });
  // Click "Connect & Verify" in the modal
  fireEvent.click(screen.getByText('Connect & Verify'));
  // Wait for the Test button to appear (means it's connected)
  await waitFor(() => expect(screen.getByText('Test')).toBeInTheDocument());
  // Click Test
  fireEvent.click(screen.getByText('Test'));
  // Wait for verified badge
  await waitFor(() => expect(screen.getByText('✓ Verified')).toBeInTheDocument());
}

describe('NEW 5-Phase Onboarding Flow (auto-build + verify gate)', () => {

  it('Phase 2→3: agent build auto-triggers when analysis returns (no button click)', async () => {
    await completePhase1And2();
    // The build should have been triggered automatically — check the trigger was called
    await waitFor(() => {
      const triggerCalls = fetchMock.mock.calls.filter(
        ([url, opts]: any) => url === '/api/onboarding-build/trigger' && opts?.method === 'POST'
      );
      expect(triggerCalls.length).toBeGreaterThan(0);
    });
  });

  it('Phase 3: shows background build status indicator', async () => {
    await completePhase1And2();
    // Should show the background build status (after status poll returns)
    await waitFor(() => {
      expect(screen.getByText(/AI Agents \(building in background\)/i)).toBeInTheDocument();
    }, { timeout: 5000 });
  });

  it('Phase 3: NO "Create AI Agents" button (auto-triggered now)', async () => {
    await completePhase1And2();
    // Should NOT have a "Create AI Agents" button anymore
    expect(screen.queryByText(/Create AI Agents/)).not.toBeInTheDocument();
  });

  it('Phase 3: "Verify All Connections" button appears after connecting + testing', async () => {
    await connectAndTestRecommendation();
    await waitFor(() => {
      expect(screen.getByText('Verify All Connections')).toBeInTheDocument();
    });
  });

  it('Phase 3: Verify button is disabled until all integrations tested', async () => {
    await completePhase1And2();
    // Click Connect (opens form modal)
    fireEvent.click(screen.getAllByText('Connect')[0]);
    await waitFor(() => expect(screen.getByText(/Connect Stripe/)).toBeInTheDocument());
    // Fill the URL + submit
    fireEvent.change(screen.getByPlaceholderText('https://api.yourcrm.com'), { target: { value: 'https://api.stripe.com' } });
    fireEvent.click(screen.getByText('Connect & Verify'));
    // Wait for Test button to appear (means connected)
    await waitFor(() => expect(screen.getByText('Test')).toBeInTheDocument());
    // Verify button should be disabled (not all tested yet)
    const verifyBtn = screen.getByText('Verify All Connections').closest('button');
    expect(verifyBtn).toBeDisabled();
    // Should show the "test first" warning
    expect(screen.getByText(/Test all integrations first/i)).toBeInTheDocument();
  });

  it('Phase 3: clicking Verify shows progressive loading (3 checks one by one)', async () => {
    await connectAndTestRecommendation();
    await waitFor(() => {
      expect(screen.getByText('Verify All Connections')).not.toBeDisabled();
    });
    fireEvent.click(screen.getByText('Verify All Connections'));
    // Should show the progressive loading state
    await waitFor(() => {
      expect(screen.getByText('Verifying your setup...')).toBeInTheDocument();
    });
    // Should show the 3 check labels
    expect(screen.getByText(/Checking API keys are genuine/i)).toBeInTheDocument();
  });

  it('Phase 3: after loading completes, shows "All checks passed" + Continue activates', async () => {
    await connectAndTestRecommendation();
    await waitFor(() => {
      expect(screen.getByText('Verify All Connections')).not.toBeDisabled();
    });
    fireEvent.click(screen.getByText('Verify All Connections'));
    // First: loading state appears
    await waitFor(() => {
      expect(screen.getByText('Verifying your setup...')).toBeInTheDocument();
    });
    // Then: loading disappears + result appears
    await waitFor(() => {
      expect(screen.queryByText('Verifying your setup...')).not.toBeInTheDocument();
    }, { timeout: 5000 });
    // Should show success message
    await waitFor(() => {
      expect(screen.getByText(/All checks passed/i)).toBeInTheDocument();
    });
    // Continue button should now be enabled
    expect(screen.getByText('Continue to Next Step').closest('button')).not.toBeDisabled();
  });

  it('Phase 3: Continue button is disabled during loading, activates after success', async () => {
    await connectAndTestRecommendation();
    // Continue should be disabled before Verify
    expect(screen.getByText('Continue to Next Step').closest('button')).toBeDisabled();
    // Run Verify
    await waitFor(() => expect(screen.getByText('Verify All Connections')).not.toBeDisabled());
    fireEvent.click(screen.getByText('Verify All Connections'));
    // During loading, Continue should still be disabled
    await waitFor(() => expect(screen.getByText('Verifying your setup...')).toBeInTheDocument());
    expect(screen.getByText('Continue to Next Step').closest('button')).toBeDisabled();
    // After success, Continue should activate
    await waitFor(() => {
      expect(screen.getByText('Continue to Next Step').closest('button')).not.toBeDisabled();
    }, { timeout: 5000 });
  });

  it('Phase 3: Verify shows failure when agents not ready', async () => {
    // Override: status always returns "building" (never ready)
    fetchMock.mockImplementation((url: string, opts?: any) => {
      if (url === '/api/superglue/systems' && opts?.method === 'POST') {
        return Promise.resolve({ ok: true, json: () => Promise.resolve({ id: 'x', name: 'x', url: '', icon: '', credentials: {}, metadata: {} }) });
      }
      if (url.includes('/verify') && opts?.method === 'POST') {
        return Promise.resolve({ ok: true, json: () => Promise.resolve(MOCK_VERIFY) });
      }
      if (url === '/api/integrations/analyze' && opts?.method === 'POST') {
        return Promise.resolve({ ok: true, json: () => Promise.resolve(MOCK_ANALYSIS) });
      }
      if (url.includes('/test') && opts?.method === 'POST') {
        return Promise.resolve({ ok: true, json: () => Promise.resolve(MOCK_TEST_OK) });
      }
      if (url === '/api/onboarding-build/trigger' && opts?.method === 'POST') {
        return Promise.resolve({ ok: true, json: () => Promise.resolve(MOCK_TRIGGER) });
      }
      if (url === '/api/onboarding-build/status') {
        return Promise.resolve({ ok: true, json: () => Promise.resolve(MOCK_STATUS_BUILDING) });
      }
      return Promise.resolve({ ok: false, json: () => Promise.resolve({}) });
    });

    await connectAndTestRecommendation();
    await waitFor(() => expect(screen.getByText('Verify All Connections')).not.toBeDisabled());
    fireEvent.click(screen.getByText('Verify All Connections'));
    // Should show failure (agents not ready)
    await waitFor(() => {
      expect(screen.getByText(/Pending.*agents building/i)).toBeInTheDocument();
    });
    // Continue should stay disabled
    expect(screen.getByText('Continue to Next Step').closest('button')).toBeDisabled();
  });
});
