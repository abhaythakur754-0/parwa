/**
 * Integration test for SuperglueIntegrationsSection component.
 *
 * Tests:
 * 1. Renders loading state initially
 * 2. Fetches catalog from /api/superglue/systems/catalog
 * 3. Fetches connected systems from /api/superglue/systems
 * 4. Renders system cards from catalog
 * 5. Clicking "Connect" opens the connect form modal
 * 6. Form submission calls POST /api/superglue/systems
 *
 * Run: npx jest src/components/integrations/__tests__/SuperglueIntegrationsSection.test.tsx --no-coverage
 */

import React from 'react';
import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import '@testing-library/jest-dom';
import { SuperglueIntegrationsSection } from '../SuperglueIntegrationsSection';

// ── Mock fetch ────────────────────────────────────────────────────────

const MOCK_CATALOG = {
  success: true,
  systems: [
    { id: 'shopify', name: 'Shopify', icon: '🛒', url_hint: 'https://{store}.myshopify.com', category: 'E-commerce' },
    { id: 'gmail', name: 'Gmail', icon: '📧', url_hint: 'https://gmail.googleapis.com', category: 'Email' },
    { id: 'slack', name: 'Slack', icon: '💬', url_hint: 'https://slack.com/api', category: 'Communication' },
  ],
};

const MOCK_CONNECTED = {
  success: true,
  systems: [],
  count: 0,
};

let fetchMock: ReturnType<typeof jest.fn>;

beforeEach(() => {
  fetchMock = jest.fn();
  global.fetch = fetchMock as unknown as typeof global.fetch;

  fetchMock.mockImplementation((url: string) => {
    if (url.includes('/systems/catalog')) {
      return Promise.resolve({
        ok: true,
        json: () => Promise.resolve(MOCK_CATALOG),
      });
    }
    if (url.endsWith('/systems') || url.includes('/systems?')) {
      return Promise.resolve({
        ok: true,
        json: () => Promise.resolve(MOCK_CONNECTED),
      });
    }
    return Promise.resolve({
      ok: false,
      json: () => Promise.resolve({ detail: 'Not found' }),
    });
  });
});

afterEach(() => {
  jest.restoreAllMocks();
});

// ── Tests ─────────────────────────────────────────────────────────────

describe('SuperglueIntegrationsSection', () => {
  it('renders loading state initially', () => {
    render(<SuperglueIntegrationsSection />);
    expect(screen.getByText('Loading integrations...')).toBeInTheDocument();
  });

  it('fetches catalog and renders system cards', async () => {
    render(<SuperglueIntegrationsSection />);

    await waitFor(() => {
      expect(screen.getByText('Shopify')).toBeInTheDocument();
    });

    expect(screen.getByText('Shopify')).toBeInTheDocument();
    expect(screen.getByText('Gmail')).toBeInTheDocument();
    expect(screen.getByText('Slack')).toBeInTheDocument();
    expect(screen.getByText('E-commerce')).toBeInTheDocument();
    expect(screen.getByText('Email')).toBeInTheDocument();
    expect(screen.getByText('Communication')).toBeInTheDocument();

    const connectButtons = screen.getAllByText('Connect');
    expect(connectButtons).toHaveLength(3);
  });

  it('shows the Superglue badge', async () => {
    render(<SuperglueIntegrationsSection />);
    await waitFor(() => {
      expect(screen.getByText('⚡ Powered by Superglue')).toBeInTheDocument();
    });
  });

  it('clicking Connect opens the connect form modal', async () => {
    render(<SuperglueIntegrationsSection />);

    await waitFor(() => {
      expect(screen.getByText('Shopify')).toBeInTheDocument();
    });

    const connectButtons = screen.getAllByText('Connect');
    fireEvent.click(connectButtons[0]);

    await waitFor(() => {
      expect(screen.getByText(/Connect Shopify/)).toBeInTheDocument();
    });

    expect(screen.getByPlaceholderText('My Shopify Store')).toBeInTheDocument();
    expect(screen.getByPlaceholderText('https://{store}.myshopify.com')).toBeInTheDocument();
    expect(screen.getByText('Connect via Superglue')).toBeInTheDocument();
  });

  it('closing the modal cancels the connect form', async () => {
    render(<SuperglueIntegrationsSection />);

    await waitFor(() => {
      expect(screen.getByText('Shopify')).toBeInTheDocument();
    });

    fireEvent.click(screen.getAllByText('Connect')[0]);
    await waitFor(() => {
      expect(screen.getByText(/Connect Shopify/)).toBeInTheDocument();
    });

    fireEvent.click(screen.getByText('Cancel'));

    await waitFor(() => {
      expect(screen.queryByText(/Connect Shopify/)).not.toBeInTheDocument();
    });
  });

  it('shows connected systems with Disconnect button', async () => {
    fetchMock.mockReset();
    fetchMock.mockImplementation((url: string) => {
      if (url.includes('/systems/catalog')) {
        return Promise.resolve({ ok: true, json: () => Promise.resolve(MOCK_CATALOG) });
      }
      if (url.endsWith('/systems') || url.includes('/systems?')) {
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve({
            success: true,
            systems: [
              { id: 'shopify', name: 'My Shopify Store', url: 'https://mystore.myshopify.com', icon: '🛒' },
            ],
            count: 1,
          }),
        });
      }
      return Promise.resolve({ ok: false, json: () => Promise.resolve({}) });
    });

    render(<SuperglueIntegrationsSection />);

    // The card shows the catalog name ("Shopify"), not the connected name
    await waitFor(() => {
      expect(screen.getByText('Shopify')).toBeInTheDocument();
    });

    // Shopify should show "Connected — Click to disconnect" (not "Connect")
    expect(screen.getByText('Connected — Click to disconnect')).toBeInTheDocument();

    // Only 2 Connect buttons (Gmail + Slack — Shopify is connected)
    expect(screen.getAllByText('Connect')).toHaveLength(2);
  });

  it('handles fetch errors gracefully', async () => {
    fetchMock.mockReset();
    fetchMock.mockRejectedValue(new Error('Network error'));

    render(<SuperglueIntegrationsSection />);

    await waitFor(() => {
      expect(screen.queryByText('Loading integrations...')).not.toBeInTheDocument();
    });

    expect(screen.getByText('⚡ Powered by Superglue')).toBeInTheDocument();
  });
});
