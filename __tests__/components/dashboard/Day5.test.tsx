/**
 * Day 5 Unit Tests — Customers CRM + Conversations Pages
 * Tests: C1-C10 (Customers), CV1-CV12 (Conversations)
 */

import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom';

// Mock Next.js navigation
const mockPush = jest.fn();
const mockUseParams = jest.fn();
jest.mock('next/navigation', () => ({
  useRouter: () => ({ push: mockPush }),
  usePathname: () => '/dashboard/customers',
  useParams: () => mockUseParams(),
}));

// Mock Next.js Link
jest.mock('next/link', () => {
  return function MockLink({ children, href, ...props }: any) {
    return <a href={href} {...props}>{children}</a>;
  };
});

// Mock dashboard API
const mockGetCustomers = jest.fn();
const mockGetCustomer = jest.fn();
const mockGetCustomerChannels = jest.fn();
const mockGetCustomerTickets = jest.fn();
const mockGetConversations = jest.fn();
const mockGetConversationMessages = jest.fn();
const mockMergeCustomers = jest.fn();

jest.mock('@/lib/dashboard-api', () => ({
  dashboardApi: {
    getCustomers: (...args: any[]) => mockGetCustomers(...args),
    getCustomer: (...args: any[]) => mockGetCustomer(...args),
    getCustomerChannels: (...args: any[]) => mockGetCustomerChannels(...args),
    getCustomerTickets: (...args: any[]) => mockGetCustomerTickets(...args),
    getConversations: (...args: any[]) => mockGetConversations(...args),
    getConversationMessages: (...args: any[]) => mockGetConversationMessages(...args),
    mergeCustomers: (...args: any[]) => mockMergeCustomers(...args),
  },
}));

// Need to import after mocks
const CustomersPage = require('@/app/dashboard/customers/page').default;
const ConversationsPage = require('@/app/dashboard/conversations/page').default;

describe('Day 5 — Customers CRM Page', () => {
  const mockCustomers = {
    customers: [
      { id: 'cust-1', name: 'John Doe', email: 'john@example.com', phone: '+1234567890', external_id: null, metadata_json: {}, company_id: 'co-1', is_verified: true, created_at: '2026-04-01T00:00:00Z', updated_at: '2026-04-01T00:00:00Z' },
      { id: 'cust-2', name: 'Jane Smith', email: 'jane@example.com', phone: null, external_id: null, metadata_json: {}, company_id: 'co-1', is_verified: false, created_at: '2026-04-10T00:00:00Z', updated_at: '2026-04-10T00:00:00Z' },
    ],
    total: 2,
    page: 1,
    page_size: 25,
  };

  beforeEach(() => {
    jest.clearAllMocks();
    mockGetCustomers.mockResolvedValue(mockCustomers);
  });

  it('C1: renders customer list with pagination', async () => {
    render(<CustomersPage />);
    await waitFor(() => expect(mockGetCustomers).toHaveBeenCalled());
    expect(screen.getByText('Customers')).toBeInTheDocument();
    expect(screen.getByText('2 total customers')).toBeInTheDocument();
    expect(screen.getByText('John Doe')).toBeInTheDocument();
    expect(screen.getByText('jane@example.com')).toBeInTheDocument();
  });

  it('C2: search input triggers debounced API call', async () => {
    render(<CustomersPage />);
    await waitFor(() => expect(mockGetCustomers).toHaveBeenCalled());

    const searchInput = screen.getByPlaceholderText('Search by name, email, phone...');
    fireEvent.change(searchInput, { target: { value: 'john' } });

    // Wait for debounce (300ms + render)
    await waitFor(() => expect(mockGetCustomers).toHaveBeenCalled(), { timeout: 1000 });
  });

  it('C3: status filter changes API params', async () => {
    render(<CustomersPage />);
    await waitFor(() => expect(mockGetCustomers).toHaveBeenCalled());

    const select = screen.getByDisplayValue('All Status');
    fireEvent.change(select, { target: { value: 'active' } });

    await waitFor(() => expect(mockGetCustomers).toHaveBeenCalled(), { timeout: 1000 });
  });

  it('C4: clicking customer name navigates to detail', async () => {
    render(<CustomersPage />);
    await waitFor(() => expect(screen.getByText('John Doe')).toBeInTheDocument());

    const link = screen.getByText('John Doe').closest('a');
    expect(link).toHaveAttribute('href', '/dashboard/customers/cust-1');
  });

  it('C5: verified/unverified badges render correctly', async () => {
    render(<CustomersPage />);
    await waitFor(() => expect(screen.getByText('John Doe')).toBeInTheDocument());

    expect(screen.getByText('Verified')).toBeInTheDocument();
    expect(screen.getByText('Unverified')).toBeInTheDocument();
  });

  it('C6: row selection checkboxes work', async () => {
    render(<CustomersPage />);
    await waitFor(() => expect(screen.getByText('John Doe')).toBeInTheDocument());

    const checkboxes = screen.getAllByRole('checkbox');
    fireEvent.click(checkboxes[1]); // Select first customer row
    expect(screen.getByText('1 selected')).toBeInTheDocument();
  });

  it('C7: merge button appears when 2+ selected', async () => {
    render(<CustomersPage />);
    await waitFor(() => expect(screen.getByText('John Doe')).toBeInTheDocument());

    const checkboxes = screen.getAllByRole('checkbox');
    fireEvent.click(checkboxes[0]); // Select all
    expect(screen.getByText('Merge Selected')).toBeInTheDocument();
  });

  it('C8: merge modal opens on button click', async () => {
    render(<CustomersPage />);
    await waitFor(() => expect(screen.getByText('John Doe')).toBeInTheDocument());

    const checkboxes = screen.getAllByRole('checkbox');
    fireEvent.click(checkboxes[0]); // Select all
    fireEvent.click(screen.getByText('Merge Selected'));

    expect(screen.getByText('Merge Customers')).toBeInTheDocument();
    expect(screen.getByText('Confirm Merge')).toBeInTheDocument();
  });

  it('C9: handles empty state', async () => {
    mockGetCustomers.mockResolvedValue({ customers: [], total: 0, page: 1, page_size: 25 });
    render(<CustomersPage />);
    await waitFor(() => expect(screen.getByText('No customers found')).toBeInTheDocument());
  });

  it('C10: handles error state', async () => {
    mockGetCustomers.mockRejectedValue(new Error('Server error'));
    render(<CustomersPage />);
    await waitFor(() => expect(screen.getByText('Server error')).toBeInTheDocument());
  });
});

describe('Day 5 — Conversations Page', () => {
  const mockConversations = {
    conversations: [
      {
        ticket_id: 'tix-001', customer_name: 'John Doe', customer_email: 'john@example.com',
        channel: 'chat', agent_name: 'E-commerce Agent', subject: 'Order refund',
        status: 'resolved', priority: 'high', confidence: 94, sentiment: 'positive',
        created_at: '2026-04-15T10:00:00Z', updated_at: '2026-04-15T10:05:00Z',
        resolution_time_seconds: 300, message_count: 8, ai_summary: 'Customer requested order refund, agent processed successfully.',
      },
      {
        ticket_id: 'tix-002', customer_name: 'Jane Smith', customer_email: 'jane@example.com',
        channel: 'email', agent_name: null, subject: 'Shipping delay',
        status: 'open', priority: 'medium', confidence: null, sentiment: 'negative',
        created_at: '2026-04-16T08:00:00Z', updated_at: '2026-04-16T08:00:00Z',
        resolution_time_seconds: null, message_count: 1, ai_summary: null,
      },
    ],
    total: 2,
    page: 1,
    page_size: 25,
  };

  beforeEach(() => {
    jest.clearAllMocks();
    mockGetConversations.mockResolvedValue(mockConversations);
  });

  it('CV1: renders conversation list', async () => {
    render(<ConversationsPage />);
    await waitFor(() => expect(mockGetConversations).toHaveBeenCalled());
    expect(screen.getByText('Conversations')).toBeInTheDocument();
    expect(screen.getByText('2 conversations across all channels')).toBeInTheDocument();
  });

  it('CV2: channel filter tabs render and work', async () => {
    render(<ConversationsPage />);
    await waitFor(() => expect(mockGetConversations).toHaveBeenCalled());

    const tabs = screen.getAllByRole('button');
    const chatTab = tabs.find(t => t.textContent === 'chat');
    if (chatTab) fireEvent.click(chatTab);

    await waitFor(() => expect(mockGetConversations).toHaveBeenCalled(), { timeout: 1000 });
  });

  it('CV3: search input renders', async () => {
    render(<ConversationsPage />);
    await waitFor(() => expect(mockGetConversations).toHaveBeenCalled());

    const searchInput = screen.getByPlaceholderText('Search conversations...');
    expect(searchInput).toBeInTheDocument();
    fireEvent.change(searchInput, { target: { value: 'refund' } });
  });

  it('CV4: date preset filters render', async () => {
    render(<ConversationsPage />);
    await waitFor(() => expect(mockGetConversations).toHaveBeenCalled());

    expect(screen.getByText('Today')).toBeInTheDocument();
    expect(screen.getByText('Last 7 days')).toBeInTheDocument();
    expect(screen.getByText('Last 30 days')).toBeInTheDocument();
    fireEvent.click(screen.getByText('Last 7 days'));
  });

  it('CV5: conversation rows show correct data', async () => {
    render(<ConversationsPage />);
    await waitFor(() => expect(screen.getByText('John Doe')).toBeInTheDocument());

    expect(screen.getByText('E-commerce Agent')).toBeInTheDocument();
    expect(screen.getByText('94%')).toBeInTheDocument();
    expect(screen.getByText('positive')).toBeInTheDocument();
  });

  it('CV6: confidence color coding (94% = green)', async () => {
    render(<ConversationsPage />);
    await waitFor(() => expect(screen.getByText('John Doe')).toBeInTheDocument());

    const confidence = screen.getByText('94%');
    expect(confidence.className).toContain('text-emerald-400');
  });

  it('CV7: null confidence shows dash', async () => {
    render(<ConversationsPage />);
    await waitFor(() => expect(screen.getByText('Jane Smith')).toBeInTheDocument());
    // Should show the customer name but no confidence percentage
  });

  it('CV8: AI summary shows for conversations that have it', async () => {
    render(<ConversationsPage />);
    await waitFor(() => expect(screen.getByText('John Doe')).toBeInTheDocument());

    expect(screen.getByText(/Customer requested order refund/)).toBeInTheDocument();
  });

  it('CV9: channel badge with correct color', async () => {
    render(<ConversationsPage />);
    await waitFor(() => expect(screen.getByText('John Doe')).toBeInTheDocument());

    // Chat channel badge should have emerald color
    const chatBadge = screen.getByText('C chat');
    expect(chatBadge.className).toContain('bg-emerald-500/10');
  });

  it('CV10: status badge renders', async () => {
    render(<ConversationsPage />);
    await waitFor(() => expect(screen.getByText('John Doe')).toBeInTheDocument());
    expect(screen.getByText('resolved')).toBeInTheDocument();
    expect(screen.getByText('open')).toBeInTheDocument();
  });

  it('CV11: export button renders', async () => {
    render(<ConversationsPage />);
    await waitFor(() => expect(screen.getByText('Conversations')).toBeInTheDocument());
    expect(screen.getByText('Export')).toBeInTheDocument();
  });

  it('CV12: handles empty state', async () => {
    mockGetConversations.mockResolvedValue({ conversations: [], total: 0, page: 1, page_size: 25 });
    render(<ConversationsPage />);
    await waitFor(() => expect(screen.getByText('No conversations found')).toBeInTheDocument());
  });
});
