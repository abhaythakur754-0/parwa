/**
 * Dashboard Components Tests
 *
 * Unit tests for all dashboard components:
 * - TicketList
 * - ApprovalQueue
 * - JarvisTerminal
 * - AgentStatus
 * - ActivityFeed
 * - NotificationCenter
 * - SearchBar
 */

import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import React from "react";

// Import components
import { TicketList, type Ticket, type SortConfig } from "../components/dashboard/TicketList";
import { ApprovalQueue, type ApprovalRequest } from "../components/dashboard/ApprovalQueue";
import { JarvisTerminal } from "../components/dashboard/JarvisTerminal";
import { AgentStatus, type Agent } from "../components/dashboard/AgentStatus";
import { ActivityFeed, type Activity } from "../components/dashboard/ActivityFeed";
import { NotificationCenter, type Notification } from "../components/dashboard/NotificationCenter";
import { SearchBar, type SearchResult } from "../components/dashboard/SearchBar";

// Mock data
const mockTickets: Ticket[] = [
  {
    id: "ticket-1",
    subject: "Cannot login to my account",
    customer: { id: "cust-1", name: "John Doe", email: "john@example.com" },
    status: "open",
    priority: "high",
    assignee: { id: "agent-1", name: "Agent Smith" },
    createdAt: "2024-01-01T10:00:00Z",
    updatedAt: "2024-01-01T11:00:00Z",
    channel: "email",
  },
  {
    id: "ticket-2",
    subject: "Refund request for order #123",
    customer: { id: "cust-2", name: "Jane Smith", email: "jane@example.com" },
    status: "in_progress",
    priority: "medium",
    createdAt: "2024-01-01T09:00:00Z",
    updatedAt: "2024-01-01T10:30:00Z",
    channel: "chat",
  },
];

const mockApprovals: ApprovalRequest[] = [
  {
    id: "approval-1",
    type: "refund",
    amount: 75.0,
    description: "Refund for defective product",
    requester: { id: "user-1", name: "Agent Alice", email: "alice@parwa.ai" },
    status: "pending",
    createdAt: "2024-01-01T10:00:00Z",
    updatedAt: "2024-01-01T10:00:00Z",
    minutesPending: 30,
  },
  {
    id: "approval-2",
    type: "escalation",
    description: "Customer complaint escalation",
    requester: { id: "user-2", name: "Agent Bob", email: "bob@parwa.ai" },
    status: "pending",
    createdAt: "2024-01-01T09:30:00Z",
    updatedAt: "2024-01-01T09:30:00Z",
    minutesPending: 60,
  },
];

const mockAgent: Agent = {
  id: "agent-1",
  name: "Support Agent Alpha",
  variant: "parwa",
  status: "active",
  currentTask: "Handling ticket #1234",
  performance: {
    accuracy: 94,
    avgResponseTime: 2.5,
    ticketsHandled: 156,
    satisfactionScore: 92,
  },
  lastActivity: new Date().toISOString(),
  uptime: 99.5,
};

const mockActivities: Activity[] = [
  {
    id: "activity-1",
    type: "ticket_resolved",
    description: "Resolved ticket #1234",
    user: { id: "user-1", name: "Agent Alice" },
    timestamp: new Date().toISOString(),
  },
  {
    id: "activity-2",
    type: "refund_processed",
    description: "Processed refund of $50",
    user: { id: "user-2", name: "Agent Bob" },
    timestamp: new Date(Date.now() - 3600000).toISOString(),
  },
];

const mockNotifications: Notification[] = [
  {
    id: "notif-1",
    title: "New approval request",
    description: "Refund request pending approval",
    type: "info",
    isRead: false,
    createdAt: new Date().toISOString(),
  },
  {
    id: "notif-2",
    title: "Ticket resolved",
    description: "Ticket #1234 has been resolved",
    type: "success",
    isRead: true,
    createdAt: new Date(Date.now() - 3600000).toISOString(),
  },
];

describe("TicketList", () => {
  it("renders ticket list correctly", () => {
    render(<TicketList tickets={mockTickets} />);

    expect(screen.getByTestId("ticket-list")).toBeInTheDocument();
    expect(screen.getByText("Cannot login to my account")).toBeInTheDocument();
    expect(screen.getByText("Refund request for order #123")).toBeInTheDocument();
  });

  it("shows loading state", () => {
    render(<TicketList tickets={[]} isLoading />);

    expect(screen.getByText(/loading/i)).toBeInTheDocument();
  });

  it("shows empty state when no tickets", () => {
    render(<TicketList tickets={[]} />);

    expect(screen.getByText(/no tickets found/i)).toBeInTheDocument();
  });

  it("calls onTicketClick when row is clicked", () => {
    const handleClick = vi.fn();
    render(<TicketList tickets={mockTickets} onTicketClick={handleClick} />);

    fireEvent.click(screen.getByTestId("ticket-row-ticket-1"));

    expect(handleClick).toHaveBeenCalledWith(mockTickets[0]);
  });

  it("handles sorting", () => {
    const handleSort = vi.fn();
    render(<TicketList tickets={mockTickets} onSort={handleSort} />);

    // Click on Subject column header
    fireEvent.click(screen.getByText(/subject/i));

    expect(handleSort).toHaveBeenCalledWith({ column: "subject", direction: "asc" });
  });

  it("renders compact mode", () => {
    render(<TicketList tickets={mockTickets} compact />);

    // In compact mode, assignee and channel columns should not be present
    expect(screen.queryByText("Assignee")).not.toBeInTheDocument();
    expect(screen.queryByText("Channel")).not.toBeInTheDocument();
  });
});

describe("ApprovalQueue", () => {
  it("renders approval queue correctly", () => {
    render(<ApprovalQueue approvals={mockApprovals} />);

    expect(screen.getByTestId("approval-queue")).toBeInTheDocument();
    expect(screen.getByText("Refund for defective product")).toBeInTheDocument();
    expect(screen.getByText("Customer complaint escalation")).toBeInTheDocument();
  });

  it("shows pending count badge", () => {
    render(<ApprovalQueue approvals={mockApprovals} />);

    expect(screen.getByText("2")).toBeInTheDocument();
  });

  it("shows empty state when no approvals", () => {
    render(<ApprovalQueue approvals={[]} />);

    expect(screen.getByText(/all caught up/i)).toBeInTheDocument();
  });

  it("calls onApprove when approve button is clicked", async () => {
    const handleApprove = vi.fn().mockResolvedValue(undefined);
    render(<ApprovalQueue approvals={mockApprovals} onApprove={handleApprove} />);

    const approveButtons = screen.getAllByText(/approve/i);
    fireEvent.click(approveButtons[0]);

    await waitFor(() => {
      expect(handleApprove).toHaveBeenCalledWith("approval-1");
    });
  });

  it("calls onDeny when deny button is clicked", async () => {
    const handleDeny = vi.fn().mockResolvedValue(undefined);
    render(<ApprovalQueue approvals={mockApprovals} onDeny={handleDeny} />);

    const denyButtons = screen.getAllByText(/deny/i);
    fireEvent.click(denyButtons[0]);

    await waitFor(() => {
      expect(handleDeny).toHaveBeenCalledWith("approval-1");
    });
  });

  it("calls onRefresh when refresh button is clicked", async () => {
    const handleRefresh = vi.fn().mockResolvedValue(undefined);
    render(<ApprovalQueue approvals={mockApprovals} onRefresh={handleRefresh} />);

    fireEvent.click(screen.getByLabelText(/refresh approval queue/i));

    await waitFor(() => {
      expect(handleRefresh).toHaveBeenCalled();
    });
  });

  it("shows amount with correct color coding", () => {
    render(<ApprovalQueue approvals={mockApprovals} />);

    // $75 should have orange/blue color
    expect(screen.getByText("$75.00")).toBeInTheDocument();
  });
});

describe("JarvisTerminal", () => {
  it("renders terminal correctly", () => {
    render(<JarvisTerminal />);

    expect(screen.getByTestId("jarvis-terminal")).toBeInTheDocument();
    expect(screen.getByText(/welcome to jarvis/i)).toBeInTheDocument();
  });

  it("shows command input", () => {
    render(<JarvisTerminal />);

    expect(screen.getByPlaceholderText(/enter command/i)).toBeInTheDocument();
  });

  it("handles command submission", async () => {
    const handleCommand = vi.fn().mockResolvedValue("Command executed");
    render(<JarvisTerminal onCommand={handleCommand} />);

    const input = screen.getByPlaceholderText(/enter command/i);
    fireEvent.change(input, { target: { value: "status" } });
    fireEvent.submit(input.closest("form")!);

    await waitFor(() => {
      expect(handleCommand).toHaveBeenCalledWith("status");
    });
  });

  it("clears terminal on clear command", () => {
    render(<JarvisTerminal />);

    const input = screen.getByPlaceholderText(/enter command/i);
    fireEvent.change(input, { target: { value: "clear" } });
    fireEvent.submit(input.closest("form")!);

    // Should show welcome message only
    expect(screen.getByText(/welcome to jarvis/i)).toBeInTheDocument();
  });

  it("shows help on help command", async () => {
    render(<JarvisTerminal />);

    const input = screen.getByPlaceholderText(/enter command/i);
    fireEvent.change(input, { target: { value: "help" } });
    fireEvent.submit(input.closest("form")!);

    expect(screen.getByText(/available commands/i)).toBeInTheDocument();
  });

  it("disables input while processing", async () => {
    const handleCommand = vi.fn().mockImplementation(
      () => new Promise((resolve) => setTimeout(() => resolve("done"), 100))
    );
    render(<JarvisTerminal onCommand={handleCommand} />);

    const input = screen.getByPlaceholderText(/enter command/i);
    fireEvent.change(input, { target: { value: "test" } });
    fireEvent.submit(input.closest("form")!);

    // Input should be cleared immediately
    expect(input).toHaveValue("");
  });
});

describe("AgentStatus", () => {
  it("renders agent status correctly", () => {
    render(<AgentStatus agent={mockAgent} />);

    expect(screen.getByTestId("agent-status-agent-1")).toBeInTheDocument();
    expect(screen.getByText("Support Agent Alpha")).toBeInTheDocument();
  });

  it("shows status badge", () => {
    render(<AgentStatus agent={mockAgent} />);

    expect(screen.getByText("Active")).toBeInTheDocument();
  });

  it("shows performance metrics", () => {
    render(<AgentStatus agent={mockAgent} />);

    expect(screen.getByText("94%")).toBeInTheDocument();
    expect(screen.getByText("2.5s")).toBeInTheDocument();
    expect(screen.getByText("156")).toBeInTheDocument();
  });

  it("calls onPause when pause button is clicked", () => {
    const handlePause = vi.fn();
    render(<AgentStatus agent={mockAgent} onPause={handlePause} />);

    fireEvent.click(screen.getByText(/pause/i));

    expect(handlePause).toHaveBeenCalledWith("agent-1");
  });

  it("shows resume button when paused", () => {
    const pausedAgent = { ...mockAgent, status: "paused" as const };
    render(<AgentStatus agent={pausedAgent} />);

    expect(screen.getByText(/resume/i)).toBeInTheDocument();
  });

  it("renders compact mode", () => {
    render(<AgentStatus agent={mockAgent} compact />);

    // Performance metrics should not be shown
    expect(screen.queryByText("Accuracy")).not.toBeInTheDocument();
  });
});

describe("ActivityFeed", () => {
  it("renders activity feed correctly", () => {
    render(<ActivityFeed activities={mockActivities} />);

    expect(screen.getByTestId("activity-feed")).toBeInTheDocument();
    expect(screen.getByText("Resolved ticket #1234")).toBeInTheDocument();
    expect(screen.getByText("Processed refund of $50")).toBeInTheDocument();
  });

  it("shows empty state when no activities", () => {
    render(<ActivityFeed activities={[]} />);

    expect(screen.getByText(/no activity yet/i)).toBeInTheDocument();
  });

  it("shows load more button when hasMore is true", () => {
    render(<ActivityFeed activities={mockActivities} hasMore onLoadMore={vi.fn()} />);

    expect(screen.getByText(/load more/i)).toBeInTheDocument();
  });

  it("calls onLoadMore when load more is clicked", () => {
    const handleLoadMore = vi.fn();
    render(<ActivityFeed activities={mockActivities} hasMore onLoadMore={handleLoadMore} />);

    fireEvent.click(screen.getByText(/load more/i));

    expect(handleLoadMore).toHaveBeenCalled();
  });
});

describe("NotificationCenter", () => {
  beforeEach(() => {
    // Clear any previous renders
    vi.clearAllMocks();
  });

  it("renders notification center correctly", () => {
    render(<NotificationCenter notifications={mockNotifications} />);

    expect(screen.getByLabelText(/notifications/i)).toBeInTheDocument();
  });

  it("shows unread badge count", () => {
    render(<NotificationCenter notifications={mockNotifications} />);

    expect(screen.getByText("1")).toBeInTheDocument();
  });

  it("opens dropdown when bell is clicked", () => {
    render(<NotificationCenter notifications={mockNotifications} />);

    fireEvent.click(screen.getByLabelText(/notifications/i));

    expect(screen.getByTestId("notification-dropdown")).toBeInTheDocument();
  });

  it("shows notifications in dropdown", () => {
    render(<NotificationCenter notifications={mockNotifications} />);

    fireEvent.click(screen.getByLabelText(/notifications/i));

    expect(screen.getByText("New approval request")).toBeInTheDocument();
    expect(screen.getByText("Ticket resolved")).toBeInTheDocument();
  });

  it("calls onMarkAsRead when notification is clicked", () => {
    const handleMarkAsRead = vi.fn();
    render(
      <NotificationCenter
        notifications={mockNotifications}
        onMarkAsRead={handleMarkAsRead}
      />
    );

    fireEvent.click(screen.getByLabelText(/notifications/i));
    fireEvent.click(screen.getByTestId("notification-notif-1"));

    expect(handleMarkAsRead).toHaveBeenCalledWith("notif-1");
  });

  it("calls onMarkAllAsRead when mark all read is clicked", () => {
    const handleMarkAllAsRead = vi.fn();
    render(
      <NotificationCenter
        notifications={mockNotifications}
        onMarkAllAsRead={handleMarkAllAsRead}
      />
    );

    fireEvent.click(screen.getByLabelText(/notifications/i));
    fireEvent.click(screen.getByText(/mark all read/i));

    expect(handleMarkAllAsRead).toHaveBeenCalled();
  });
});

describe("SearchBar", () => {
  it("renders search bar correctly", () => {
    render(<SearchBar />);

    expect(screen.getByPlaceholderText(/search tickets/i)).toBeInTheDocument();
  });

  it("updates query on input change", () => {
    render(<SearchBar />);

    const input = screen.getByPlaceholderText(/search tickets/i);
    fireEvent.change(input, { target: { value: "test query" } });

    expect(input).toHaveValue("test query");
  });

  it("shows clear button when query exists", () => {
    render(<SearchBar />);

    const input = screen.getByPlaceholderText(/search tickets/i);
    fireEvent.change(input, { target: { value: "test" } });

    expect(screen.getByLabelText(/clear search/i)).toBeInTheDocument();
  });

  it("clears search when clear button is clicked", () => {
    render(<SearchBar />);

    const input = screen.getByPlaceholderText(/search tickets/i);
    fireEvent.change(input, { target: { value: "test" } });
    fireEvent.click(screen.getByLabelText(/clear search/i));

    expect(input).toHaveValue("");
  });

  it("calls onSearch with debounced query", async () => {
    const handleSearch = vi.fn().mockResolvedValue([]);
    render(<SearchBar onSearch={handleSearch} />);

    const input = screen.getByPlaceholderText(/search tickets/i);
    fireEvent.change(input, { target: { value: "test query" } });

    await waitFor(
      () => {
        expect(handleSearch).toHaveBeenCalledWith("test query");
      },
      { timeout: 500 }
    );
  });

  it("shows recent searches when available", () => {
    render(<SearchBar recentSearches={["refund", "login issue"]} />);

    const input = screen.getByPlaceholderText(/search tickets/i);
    fireEvent.focus(input);

    expect(screen.getByText(/recent searches/i)).toBeInTheDocument();
    expect(screen.getByText("refund")).toBeInTheDocument();
  });

  it("handles keyboard navigation", () => {
    const mockResults: SearchResult[] = [
      { id: "1", type: "ticket", title: "Test Ticket" },
      { id: "2", type: "customer", title: "Test Customer" },
    ];

    render(<SearchBar onSearch={vi.fn().mockResolvedValue(mockResults)} />);

    const input = screen.getByPlaceholderText(/search tickets/i);
    fireEvent.change(input, { target: { value: "test" } });
    fireEvent.focus(input);

    // Test keyboard navigation
    fireEvent.keyDown(input, { key: "ArrowDown" });
    fireEvent.keyDown(input, { key: "ArrowUp" });
    fireEvent.keyDown(input, { key: "Escape" });
  });

  it("calls onResultSelect when result is clicked", async () => {
    const mockResults: SearchResult[] = [
      { id: "ticket-1", type: "ticket", title: "Test Ticket" },
    ];
    const handleResultSelect = vi.fn();
    const handleSearch = vi.fn().mockResolvedValue(mockResults);

    render(
      <SearchBar onSearch={handleSearch} onResultSelect={handleResultSelect} />
    );

    const input = screen.getByPlaceholderText(/search tickets/i);
    fireEvent.change(input, { target: { value: "test" } });

    await waitFor(() => expect(handleSearch).toHaveBeenCalled(), { timeout: 500 });

    // Click on result (if visible)
    const resultElement = screen.queryByText("Test Ticket");
    if (resultElement) {
      fireEvent.click(resultElement);
      expect(handleResultSelect).toHaveBeenCalled();
    }
  });
});
