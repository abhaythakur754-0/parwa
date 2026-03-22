/**
 * Dashboard Layout Tests
 *
 * Unit tests for dashboard layout and components.
 */

import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { useRouter, usePathname } from "next/navigation";

// Mock next/navigation
vi.mock("next/navigation", () => ({
  useRouter: vi.fn(),
  usePathname: vi.fn(),
}));

// Mock the stores
vi.mock("@/stores/authStore", () => ({
  useAuthStore: vi.fn(() => ({
    user: { id: "1", name: "Test User", email: "test@example.com", role: "admin" },
    isAuthenticated: true,
    logout: vi.fn(),
  })),
  useIsAuthenticated: vi.fn(() => true),
}));

vi.mock("@/stores/uiStore", () => ({
  useUIStore: vi.fn(() => ({
    sidebarOpen: true,
    sidebarCollapsed: false,
    theme: "light",
  })),
  useSidebar: vi.fn(() => ({
    sidebarOpen: true,
    sidebarCollapsed: false,
    toggleSidebar: vi.fn(),
    setSidebarOpen: vi.fn(),
    toggleSidebarCollapsed: vi.fn(),
  })),
  useTheme: vi.fn(() => ({
    theme: "light",
    toggleTheme: vi.fn(),
  })),
  useToasts: vi.fn(() => ({
    addToast: vi.fn(),
    removeToast: vi.fn(),
  })),
}));

// Mock API client
vi.mock("@/services/api/client", () => ({
  apiClient: {
    get: vi.fn(),
    post: vi.fn(),
  },
  APIError: class APIError extends Error {
    status: number;
    statusText: string;
    data: unknown;
    constructor(status: number, statusText: string, message: string, data?: unknown) {
      super(message);
      this.status = status;
      this.statusText = statusText;
      this.data = data;
    }
  },
}));

// Import components after mocks
import DashboardLayout from "@/app/dashboard/layout";
import DashboardPage from "@/app/dashboard/page";
import StatsCard from "@/components/dashboard/StatsCard";
import MetricCard from "@/components/dashboard/MetricCard";
import QuickActions from "@/components/dashboard/QuickActions";
import RecentActivity from "@/components/dashboard/RecentActivity";

describe("DashboardLayout", () => {
  const mockRouter = {
    push: vi.fn(),
  };

  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(useRouter).mockReturnValue(mockRouter as unknown as ReturnType<typeof useRouter>);
    vi.mocked(usePathname).mockReturnValue("/dashboard");
  });

  it("renders navigation items", () => {
    render(
      <DashboardLayout>
        <div>Test Content</div>
      </DashboardLayout>
    );

    expect(screen.getByText("Dashboard")).toBeInTheDocument();
    expect(screen.getByText("Tickets")).toBeInTheDocument();
    expect(screen.getByText("Approvals")).toBeInTheDocument();
    expect(screen.getByText("Agents")).toBeInTheDocument();
    expect(screen.getByText("Analytics")).toBeInTheDocument();
    expect(screen.getByText("Settings")).toBeInTheDocument();
  });

  it("renders children content", () => {
    render(
      <DashboardLayout>
        <div>Test Content</div>
      </DashboardLayout>
    );

    expect(screen.getByText("Test Content")).toBeInTheDocument();
  });

  it("displays user name in header", () => {
    render(
      <DashboardLayout>
        <div>Content</div>
      </DashboardLayout>
    );

    expect(screen.getByText("Test User")).toBeInTheDocument();
  });

  it("highlights active navigation item", () => {
    vi.mocked(usePathname).mockReturnValue("/dashboard/tickets");

    render(
      <DashboardLayout>
        <div>Content</div>
      </DashboardLayout>
    );

    const ticketsLink = screen.getByText("Tickets").closest("a");
    expect(ticketsLink).toHaveClass("bg-primary");
  });
});

describe("StatsCard", () => {
  it("renders with title and value", () => {
    render(
      <StatsCard
        title="Total Tickets"
        value={100}
      />
    );

    expect(screen.getByText("Total Tickets")).toBeInTheDocument();
    expect(screen.getByText("100")).toBeInTheDocument();
  });

  it("renders with positive trend", () => {
    render(
      <StatsCard
        title="Total Tickets"
        value={100}
        trend={12.5}
      />
    );

    expect(screen.getByText("12.5%")).toBeInTheDocument();
  });

  it("renders with negative trend", () => {
    render(
      <StatsCard
        title="Open Tickets"
        value={50}
        trend={-5.2}
      />
    );

    expect(screen.getByText("5.2%")).toBeInTheDocument();
  });

  it("renders loading state", () => {
    render(
      <StatsCard
        title="Total Tickets"
        value={0}
        isLoading
      />
    );

    // Should show loading skeleton - check for animate-pulse class
    const skeleton = document.querySelector(".animate-pulse");
    expect(skeleton).toBeInTheDocument();
    expect(skeleton).toHaveClass("bg-card");
  });

  it("renders error state", () => {
    render(
      <StatsCard
        title="Total Tickets"
        value={0}
        error="Failed to load"
      />
    );

    expect(screen.getByText("Failed to load")).toBeInTheDocument();
  });

  it("formats large numbers with locale", () => {
    render(
      <StatsCard
        title="Total Tickets"
        value={1245678}
      />
    );

    expect(screen.getByText("1,245,678")).toBeInTheDocument();
  });
});

describe("MetricCard", () => {
  it("renders with title and value", () => {
    render(
      <MetricCard
        title="Ticket Volume"
        value={1247}
      />
    );

    expect(screen.getByText("Ticket Volume")).toBeInTheDocument();
    expect(screen.getByText("1,247")).toBeInTheDocument();
  });

  it("renders with trend", () => {
    render(
      <MetricCard
        title="Resolution Rate"
        value={87.5}
        trend={5.2}
      />
    );

    expect(screen.getByText("+5.2%")).toBeInTheDocument();
  });

  it("renders loading state", () => {
    render(
      <MetricCard
        title="Ticket Volume"
        value={0}
        isLoading
      />
    );

    // Should have animate-pulse class
    const container = document.querySelector(".animate-pulse");
    expect(container).toBeInTheDocument();
  });

  it("renders sparkline when data provided", () => {
    const data = [100, 120, 115, 130, 125, 140, 135];

    render(
      <MetricCard
        title="Ticket Volume"
        value={135}
        data={data}
      />
    );

    // Should render SVG sparkline
    const svg = document.querySelector("svg");
    expect(svg).toBeInTheDocument();
  });
});

describe("QuickActions", () => {
  it("renders all action buttons", () => {
    const onAction = vi.fn();

    render(<QuickActions onAction={onAction} />);

    expect(screen.getByText("Create Ticket")).toBeInTheDocument();
    expect(screen.getByText("Approve Pending")).toBeInTheDocument();
    expect(screen.getByText("Run Report")).toBeInTheDocument();
    expect(screen.getByText("View Analytics")).toBeInTheDocument();
  });

  it("calls onAction when button clicked", () => {
    const onAction = vi.fn();

    render(<QuickActions onAction={onAction} />);

    fireEvent.click(screen.getByText("Create Ticket"));

    expect(onAction).toHaveBeenCalledWith("create_ticket");
  });

  it("disables buttons when loading", () => {
    const onAction = vi.fn();

    render(
      <QuickActions
        onAction={onAction}
        loadingActions={["create_ticket"]}
      />
    );

    const button = screen.getByText("Create Ticket").closest("button");
    expect(button).toBeDisabled();
  });
});

describe("RecentActivity", () => {
  const mockActivities = [
    {
      id: "1",
      type: "ticket_resolved" as const,
      user: "Sarah Agent",
      action: "Resolved ticket #TKT-1234",
      timestamp: new Date(Date.now() - 5 * 60000).toISOString(),
    },
    {
      id: "2",
      type: "approval" as const,
      user: "John Manager",
      action: "Approved refund request for $89.99",
      timestamp: new Date(Date.now() - 15 * 60000).toISOString(),
    },
    {
      id: "3",
      type: "ticket_created" as const,
      user: "PARWA Mini",
      action: "Created ticket #TKT-1235 from chat",
      timestamp: new Date(Date.now() - 30 * 60000).toISOString(),
    },
  ];

  it("renders activity items", () => {
    render(<RecentActivity activities={mockActivities} />);

    expect(screen.getByText("Sarah Agent")).toBeInTheDocument();
    expect(screen.getByText("John Manager")).toBeInTheDocument();
    expect(screen.getByText("PARWA Mini")).toBeInTheDocument();
  });

  it("renders empty state when no activities", () => {
    render(<RecentActivity activities={[]} />);

    expect(screen.getByText("No recent activity")).toBeInTheDocument();
  });

  it("renders loading skeleton", () => {
    render(<RecentActivity activities={[]} isLoading />);

    // Should have animate-pulse class
    const skeleton = document.querySelector(".animate-pulse");
    expect(skeleton).toBeInTheDocument();
  });

  it("limits displayed items to maxItems", () => {
    const manyActivities = Array.from({ length: 15 }, (_, i) => ({
      id: String(i),
      type: "ticket_created" as const,
      user: "User",
      action: `Action ${i}`,
      timestamp: new Date().toISOString(),
    }));

    render(<RecentActivity activities={manyActivities} maxItems={5} />);

    // Should only show 5 items (maxItems default)
    const items = screen.getAllByText("User");
    expect(items.length).toBe(5);
  });

  it("shows view all link when showViewAll is true", () => {
    render(<RecentActivity activities={mockActivities} showViewAll />);

    expect(screen.getByText("View All")).toBeInTheDocument();
  });
});

describe("DashboardPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders welcome message", async () => {
    const { apiClient } = await import("@/services/api/client");
    vi.mocked(apiClient.get).mockResolvedValue({
      data: {
        stats: {
          totalTickets: 100,
          openTickets: 20,
          resolvedToday: 10,
          avgResponseTime: 15,
          totalTicketsTrend: 5,
          openTicketsTrend: -2,
          resolvedTodayTrend: 3,
          avgResponseTimeTrend: -5,
        },
        metrics: [],
        recentActivity: [],
      },
      status: 200,
      headers: new Headers(),
    });

    render(<DashboardPage />);

    await waitFor(() => {
      expect(screen.getByText(/Welcome back/)).toBeInTheDocument();
    });
  });
});
