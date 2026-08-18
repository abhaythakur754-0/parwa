/**
 * Integration test for SuperglueOnboardingFlow — the 3-phase progressive flow.
 *
 * Phase 1: CRM Connect — shows 3 CRM options, clicking opens form, submit connects + verifies
 * Phase 2: Analyzing — shows loading spinner after verify
 * Phase 3: Recommendations — shows analyser results as connectable cards
 *
 * Run: npx jest src/components/onboarding/__tests__/SuperglueOnboardingFlow.test.tsx --no-coverage
 */

import React from 'react';
import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import '@testing-library/jest-dom';
import { SuperglueOnboardingFlow } from '../SuperglueOnboardingFlow';

// ── Mock fetch ────────────────────────────────────────────────────────

const MOCK_VERIFY_RESPONSE = {
  verified: true,
  superglue_ok: true,
  mcp_registered: true,
  system_id: 'hubspot',
  name: 'My HubSpot',
  url: 'https://api.hubapi.com',
  message: 'CRM verified — connected to Superglue + registered with MCP',
};

const MOCK_ANALYSIS_RESPONSE = {
  company_id: 'test-co',
  analyzed_at: '2026-08-18T00:00:00Z',
  connected_integrations: [],
  data_profile: { total_tickets: 142 },
  detected_gaps: [],
  recommendations: [
    { name: 'Stripe', priority: 'high', reason: 'Process refunds and track payments' },
    { name: 'Shopify', priority: 'high', reason: 'Look up customer orders' },
    { name: 'Gmail', priority: 'medium', reason: 'Email follow-ups' },
  ],
  analysis_summary: 'Analyzed 142 tickets. Found 3 integrations needed.',
};

let fetchMock: ReturnType<typeof jest.fn>;

beforeEach(() => {
  fetchMock = jest.fn();
  global.fetch = fetchMock as unknown as typeof global.fetch;

  fetchMock.mockImplementation((url: string, opts?: any) => {
    // POST /api/superglue/systems — create system
    if (url === '/api/superglue/systems' && opts?.method === 'POST') {
      return Promise.resolve({
        ok: true,
        json: () => Promise.resolve({
          id: 'hubspot',
          name: 'My HubSpot',
          url: 'https://api.hubapi.com',
          icon: '🎯',
          credentials: {},
          metadata: {},
        }),
      });
    }
    // POST /api/superglue/systems/hubspot/verify
    if (url.includes('/systems/hubspot/verify') && opts?.method === 'POST') {
      return Promise.resolve({
        ok: true,
        json: () => Promise.resolve(MOCK_VERIFY_RESPONSE),
      });
    }
    // POST /api/integrations/analyze
    if (url === '/api/integrations/analyze' && opts?.method === 'POST') {
      return Promise.resolve({
        ok: true,
        json: () => Promise.resolve(MOCK_ANALYSIS_RESPONSE),
      });
    }
    return Promise.resolve({ ok: false, json: () => Promise.resolve({}) });
  });
});

afterEach(() => {
  jest.restoreAllMocks();
});

// ── Tests ─────────────────────────────────────────────────────────────

describe('SuperglueOnboardingFlow — 3-Phase Progressive Flow', () => {

  // ── Phase 1: CRM Connect ──────────────────────────────────────────

  it('Phase 1: shows the Superglue badge + CRM connect section', () => {
    render(<SuperglueOnboardingFlow />);
    expect(screen.getByText('⚡ Powered by Superglue')).toBeInTheDocument();
    expect(screen.getByText(/①/)).toBeInTheDocument();
    expect(screen.getByText('Connect Your CRM')).toBeInTheDocument();
  });

  it('Phase 1: shows 3 CRM options (HubSpot, Zendesk, Custom CRM)', () => {
    render(<SuperglueOnboardingFlow />);
    expect(screen.getByText('HubSpot')).toBeInTheDocument();
    expect(screen.getByText('Zendesk')).toBeInTheDocument();
    expect(screen.getByText('Custom CRM')).toBeInTheDocument();
  });

  it('Phase 1: clicking a CRM opens the connect form modal', async () => {
    render(<SuperglueOnboardingFlow />);
    fireEvent.click(screen.getByText('HubSpot'));
    await waitFor(() => {
      expect(screen.getByText(/Connect HubSpot/)).toBeInTheDocument();
    });
    // Form fields
    expect(screen.getByPlaceholderText('My HubSpot Account')).toBeInTheDocument();
    expect(screen.getByText('Connect & Verify')).toBeInTheDocument();
  });

  it('Phase 1: submitting the form connects + verifies + shows verified state', async () => {
    render(<SuperglueOnboardingFlow />);

    // Open form
    fireEvent.click(screen.getByText('HubSpot'));
    await waitFor(() => {
      expect(screen.getByText(/Connect HubSpot/)).toBeInTheDocument();
    });

    // Fill + submit
    fireEvent.change(screen.getByPlaceholderText('My HubSpot Account'), { target: { value: 'My HubSpot' } });
    fireEvent.change(screen.getByPlaceholderText('https://api.hubapi.com'), { target: { value: 'https://api.hubapi.com' } });
    fireEvent.change(screen.getByPlaceholderText('••••••••••••'), { target: { value: 'pat_test123' } });
    fireEvent.click(screen.getByText('Connect & Verify'));

    // Should show verified state (CRM name + "Verified" badge)
    await waitFor(() => {
      expect(screen.getByText('Verified')).toBeInTheDocument();
    });
    expect(screen.getByText('My HubSpot')).toBeInTheDocument();
    expect(screen.getByText('Connected to Superglue + registered with MCP')).toBeInTheDocument();
  });

  // ── Phase 2: Analyzing ────────────────────────────────────────────

  it('Phase 2: transitions through analyzing to recommendations', async () => {
    render(<SuperglueOnboardingFlow />);

    // Connect + verify
    fireEvent.click(screen.getByText('HubSpot'));
    await waitFor(() => {
      expect(screen.getByText(/Connect HubSpot/)).toBeInTheDocument();
    });
    fireEvent.change(screen.getByPlaceholderText('My HubSpot Account'), { target: { value: 'My HubSpot' } });
    fireEvent.change(screen.getByPlaceholderText('https://api.hubapi.com'), { target: { value: 'https://api.hubapi.com' } });
    fireEvent.click(screen.getByText('Connect & Verify'));

    // The analysis mock resolves fast, so we should land on recommendations
    // (the analyzing phase is a transient state the user sees for 2-3 min in prod)
    await waitFor(() => {
      expect(screen.getByText('Stripe')).toBeInTheDocument();
    });
    // Verify the analysis summary is shown (proves analysis ran)
    expect(screen.getByText(/Analyzed 142 tickets/i)).toBeInTheDocument();
  });

  // ── Phase 3: Recommendations ──────────────────────────────────────

  it('Phase 3: shows recommended integrations after analysis completes', async () => {
    render(<SuperglueOnboardingFlow />);

    // Connect + verify (triggers analysis)
    fireEvent.click(screen.getByText('HubSpot'));
    await waitFor(() => {
      expect(screen.getByText(/Connect HubSpot/)).toBeInTheDocument();
    });
    fireEvent.change(screen.getByPlaceholderText('My HubSpot Account'), { target: { value: 'My HubSpot' } });
    fireEvent.change(screen.getByPlaceholderText('https://api.hubapi.com'), { target: { value: 'https://api.hubapi.com' } });
    fireEvent.click(screen.getByText('Connect & Verify'));

    // Wait for recommendations to appear
    await waitFor(() => {
      expect(screen.getByText('Stripe')).toBeInTheDocument();
    });
    expect(screen.getByText('Shopify')).toBeInTheDocument();
    expect(screen.getByText('Gmail')).toBeInTheDocument();
    expect(screen.getByText('Process refunds and track payments')).toBeInTheDocument();
    expect(screen.getByText(/Analyzed 142 tickets/i)).toBeInTheDocument();
  });

  it('Phase 3: each recommendation has a Connect button', async () => {
    render(<SuperglueOnboardingFlow />);

    // Connect CRM to trigger analysis
    fireEvent.click(screen.getByText('HubSpot'));
    await waitFor(() => {
      expect(screen.getByText(/Connect HubSpot/)).toBeInTheDocument();
    });
    fireEvent.change(screen.getByPlaceholderText('My HubSpot Account'), { target: { value: 'My HubSpot' } });
    fireEvent.change(screen.getByPlaceholderText('https://api.hubapi.com'), { target: { value: 'https://api.hubapi.com' } });
    fireEvent.click(screen.getByText('Connect & Verify'));

    // Wait for recommendations
    await waitFor(() => {
      expect(screen.getByText('Stripe')).toBeInTheDocument();
    });

    // Should have 3 Connect buttons (one per recommendation)
    const connectButtons = screen.getAllByText('Connect');
    expect(connectButtons.length).toBeGreaterThanOrEqual(3);
  });

  // ── Error handling ────────────────────────────────────────────────

  it('shows error state when analysis fails', async () => {
    fetchMock.mockReset();
    fetchMock.mockImplementation((url: string, opts?: any) => {
      if (url === '/api/superglue/systems' && opts?.method === 'POST') {
        return Promise.resolve({ ok: true, json: () => Promise.resolve({ id: 'hubspot', name: 'My HubSpot', url: '', icon: '', credentials: {}, metadata: {} }) });
      }
      if (url.includes('/verify') && opts?.method === 'POST') {
        return Promise.resolve({ ok: true, json: () => Promise.resolve(MOCK_VERIFY_RESPONSE) });
      }
      if (url === '/api/integrations/analyze' && opts?.method === 'POST') {
        return Promise.resolve({ ok: false, json: () => Promise.resolve({ detail: 'Analyser service unavailable' }) });
      }
      return Promise.resolve({ ok: false, json: () => Promise.resolve({}) });
    });

    render(<SuperglueOnboardingFlow />);

    // Connect CRM
    fireEvent.click(screen.getByText('HubSpot'));
    await waitFor(() => {
      expect(screen.getByText(/Connect HubSpot/)).toBeInTheDocument();
    });
    fireEvent.change(screen.getByPlaceholderText('My HubSpot Account'), { target: { value: 'My HubSpot' } });
    fireEvent.change(screen.getByPlaceholderText('https://api.hubapi.com'), { target: { value: 'https://api.hubapi.com' } });
    fireEvent.click(screen.getByText('Connect & Verify'));

    // Should show error state
    await waitFor(() => {
      expect(screen.getByText('Analysis failed')).toBeInTheDocument();
    });
    expect(screen.getByText(/Analyser service unavailable/)).toBeInTheDocument();
    expect(screen.getByText('Retry analysis')).toBeInTheDocument();
  });
});
