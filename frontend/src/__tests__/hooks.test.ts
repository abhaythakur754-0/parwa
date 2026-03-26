/**
 * PARWA Hooks Tests
 *
 * Unit tests for all custom hooks.
 * Tests cover hook initialization, state updates, and API interactions.
 */

import { renderHook, act, waitFor } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";

// Mock dependencies
vi.mock("../services/api/client", () => ({
  apiClient: {
    get: vi.fn(),
    post: vi.fn(),
    patch: vi.fn(),
    put: vi.fn(),
    delete: vi.fn(),
    getAuthToken: vi.fn(() => "test-token"),
    setAuthToken: vi.fn(),
    clearAuthToken: vi.fn(),
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

vi.mock("../stores/uiStore", () => ({
  useUIStore: vi.fn(() => ({
    addToast: vi.fn(),
    removeToast: vi.fn(),
    sidebarOpen: true,
    theme: "light",
  })),
}));

vi.mock("../stores/authStore", () => ({
  useAuthStore: vi.fn(() => ({
    user: null,
    token: null,
    isAuthenticated: false,
    isLoading: false,
    error: null,
    login: vi.fn(),
    register: vi.fn(),
    logout: vi.fn(),
    restoreSession: vi.fn(),
    updateProfile: vi.fn(),
    clearError: vi.fn(),
    setToken: vi.fn(),
  })),
}));

// Import hooks after mocking
import { apiClient } from "../services/api/client";
import { useAuth } from "../hooks/useAuth";
import { useApprovals } from "../hooks/useApprovals";
import { useTickets } from "../hooks/useTickets";
import { useAnalytics } from "../hooks/useAnalytics";
import { useJarvis } from "../hooks/useJarvis";
import { useAgents } from "../hooks/useAgents";
import { useNotifications } from "../hooks/useNotifications";
import { useSearch } from "../hooks/useSearch";

const mockedApiClient = vi.mocked(apiClient);

describe("useAuth Hook", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("should initialize with default state", () => {
    const { result } = renderHook(() => useAuth());

    expect(result.current.user).toBeNull();
    expect(result.current.isAuthenticated).toBe(false);
    expect(result.current.isLoading).toBe(false);
    expect(result.current.error).toBeNull();
  });

  it("should have all required actions", () => {
    const { result } = renderHook(() => useAuth());

    expect(typeof result.current.login).toBe("function");
    expect(typeof result.current.register).toBe("function");
    expect(typeof result.current.logout).toBe("function");
    expect(typeof result.current.checkAuth).toBe("function");
    expect(typeof result.current.refreshToken).toBe("function");
    expect(typeof result.current.updateProfile).toBe("function");
    expect(typeof result.current.clearError).toBe("function");
  });
});

describe("useApprovals Hook", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockedApiClient.get.mockResolvedValue({
      data: {
        approvals: [],
        total: 0,
        page: 1,
        pageSize: 20,
      },
      status: 200,
      headers: new Headers(),
    });
  });

  it("should initialize with empty approvals", async () => {
    const { result } = renderHook(() => useApprovals());

    await waitFor(() => {
      expect(result.current.approvals).toEqual([]);
    });

    expect(result.current.total).toBe(0);
    // isLoading might be true during initial fetch, that's expected behavior
  });

  it("should have all required actions", () => {
    const { result } = renderHook(() => useApprovals());

    expect(typeof result.current.fetchApprovals).toBe("function");
    expect(typeof result.current.approve).toBe("function");
    expect(typeof result.current.deny).toBe("function");
    expect(typeof result.current.refresh).toBe("function");
    expect(typeof result.current.setFilters).toBe("function");
    expect(typeof result.current.clearError).toBe("function");
  });

  it("should fetch approvals successfully", async () => {
    const mockApprovals = [
      {
        id: "1",
        type: "refund",
        status: "pending",
        reason: "Test refund",
        requester: { id: "u1", name: "User", email: "user@test.com" },
        createdAt: "2024-01-01T00:00:00Z",
        updatedAt: "2024-01-01T00:00:00Z",
      },
    ];

    mockedApiClient.get.mockResolvedValueOnce({
      data: {
        approvals: mockApprovals,
        total: 1,
        page: 1,
        pageSize: 20,
      },
      status: 200,
      headers: new Headers(),
    });

    const { result } = renderHook(() => useApprovals());

    // Wait for the fetch to complete
    await waitFor(
      () => {
        expect(result.current.approvals).toHaveLength(1);
      },
      { timeout: 3000 }
    );

    expect(result.current.total).toBe(1);
  });

  it("should handle approve action", async () => {
    mockedApiClient.post.mockResolvedValueOnce({
      data: undefined,
      status: 200,
      headers: new Headers(),
    });

    const { result } = renderHook(() => useApprovals());

    await act(async () => {
      await result.current.approve("test-id", "Approved");
    });

    expect(mockedApiClient.post).toHaveBeenCalledWith(
      "/approvals/test-id/approve",
      { notes: "Approved" }
    );
  });

  it("should handle deny action", async () => {
    mockedApiClient.post.mockResolvedValueOnce({
      data: undefined,
      status: 200,
      headers: new Headers(),
    });

    const { result } = renderHook(() => useApprovals());

    await act(async () => {
      await result.current.deny("test-id", "Denied reason");
    });

    expect(mockedApiClient.post).toHaveBeenCalledWith(
      "/approvals/test-id/deny",
      { reason: "Denied reason" }
    );
  });
});

describe("useTickets Hook", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockedApiClient.get.mockResolvedValue({
      data: {
        tickets: [],
        total: 0,
        page: 1,
        pageSize: 20,
      },
      status: 200,
      headers: new Headers(),
    });
  });

  it("should initialize with empty tickets", async () => {
    const { result } = renderHook(() => useTickets());

    await waitFor(() => {
      expect(result.current.tickets).toEqual([]);
    });

    expect(result.current.ticket).toBeNull();
    // isLoading might be true during initial fetch, that's expected behavior
  });

  it("should have all required actions", () => {
    const { result } = renderHook(() => useTickets());

    expect(typeof result.current.fetchTickets).toBe("function");
    expect(typeof result.current.fetchTicket).toBe("function");
    expect(typeof result.current.createTicket).toBe("function");
    expect(typeof result.current.updateTicket).toBe("function");
    expect(typeof result.current.searchTickets).toBe("function");
    expect(typeof result.current.addReply).toBe("function");
    expect(typeof result.current.refresh).toBe("function");
  });

  it("should create a new ticket", async () => {
    const mockTicket = {
      id: "t1",
      subject: "Test",
      description: "Test ticket",
      status: "open",
      priority: "medium",
      source: "web",
      customer: { id: "c1", name: "Customer", email: "c@test.com" },
      messages: [],
      tags: [],
      createdAt: "2024-01-01T00:00:00Z",
      updatedAt: "2024-01-01T00:00:00Z",
    };

    mockedApiClient.post.mockResolvedValueOnce({
      data: mockTicket,
      status: 201,
      headers: new Headers(),
    });

    const { result } = renderHook(() => useTickets());

    await act(async () => {
      await result.current.createTicket({
        subject: "Test",
        description: "Test ticket",
        customerId: "c1",
      });
    });

    expect(mockedApiClient.post).toHaveBeenCalledWith("/tickets", {
      subject: "Test",
      description: "Test ticket",
      customerId: "c1",
    });
  });
});

describe("useAnalytics Hook", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("should initialize with default state", () => {
    const { result } = renderHook(() => useAnalytics());

    expect(result.current.metrics).toBeNull();
    expect(result.current.chartData).toBeNull();
    expect(result.current.isLoading).toBe(false);
  });

  it("should have all required actions", () => {
    const { result } = renderHook(() => useAnalytics());

    expect(typeof result.current.fetchMetrics).toBe("function");
    expect(typeof result.current.fetchChartData).toBe("function");
    expect(typeof result.current.fetchAgentPerformance).toBe("function");
    expect(typeof result.current.setDateRange).toBe("function");
    expect(typeof result.current.exportToCSV).toBe("function");
    expect(typeof result.current.exportToPDF).toBe("function");
    expect(typeof result.current.exportToJSON).toBe("function");
  });

  it("should fetch metrics successfully", async () => {
    const mockMetrics = {
      totalTickets: 100,
      openTickets: 20,
      resolvedTickets: 80,
      avgResponseTime: 120,
      avgResolutionTime: 360,
      csatScore: 4.5,
      escalationRate: 0.05,
      firstContactResolution: 0.75,
    };

    mockedApiClient.get.mockResolvedValueOnce({
      data: mockMetrics,
      status: 200,
      headers: new Headers(),
    });

    const { result } = renderHook(() => useAnalytics());

    await act(async () => {
      await result.current.fetchMetrics();
    });

    await waitFor(() => {
      expect(result.current.metrics).toEqual(mockMetrics);
    });
  });

  it("should set date range", () => {
    const { result } = renderHook(() => useAnalytics());

    act(() => {
      result.current.setDateRange(
        { start: "2024-01-01", end: "2024-01-31" },
        "custom"
      );
    });

    expect(result.current.dateRange).toEqual({
      start: "2024-01-01",
      end: "2024-01-31",
    });
    expect(result.current.presetRange).toBe("custom");
  });
});

describe("useJarvis Hook (CRITICAL)", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockedApiClient.post.mockResolvedValue({
      data: {
        command: "test",
        result: "Command executed successfully",
        executionTime: 100,
      },
      status: 200,
      headers: new Headers(),
    });
  });

  it("should initialize with empty state", () => {
    const { result } = renderHook(() => useJarvis());

    expect(result.current.response).toBe("");
    expect(result.current.isStreaming).toBe(false);
    expect(result.current.commandHistory).toEqual([]);
    expect(result.current.isLoading).toBe(false);
  });

  it("should have all required actions", () => {
    const { result } = renderHook(() => useJarvis());

    expect(typeof result.current.sendCommand).toBe("function");
    expect(typeof result.current.sendStructuredCommand).toBe("function");
    expect(typeof result.current.abort).toBe("function");
    expect(typeof result.current.clearResponse).toBe("function");
    expect(typeof result.current.clearHistory).toBe("function");
    expect(typeof result.current.clearError).toBe("function");
  });

  it("should send command and stream response", async () => {
    const { result } = renderHook(() => useJarvis());

    await act(async () => {
      await result.current.sendCommand("pause_refunds");
    });

    // Wait for simulated streaming to complete
    await waitFor(
      () => {
        expect(result.current.response).toContain("successfully");
      },
      { timeout: 5000 }
    );
  });

  it("should add command to history", async () => {
    const { result } = renderHook(() => useJarvis());

    await act(async () => {
      await result.current.sendCommand("test command");
    });

    await waitFor(() => {
      expect(result.current.commandHistory.length).toBeGreaterThan(0);
    });
  });

  it("should clear history", async () => {
    const { result } = renderHook(() => useJarvis());

    await act(async () => {
      await result.current.sendCommand("test");
    });

    await waitFor(() => {
      expect(result.current.commandHistory.length).toBeGreaterThan(0);
    });

    act(() => {
      result.current.clearHistory();
    });

    expect(result.current.commandHistory).toEqual([]);
  });

  it("should abort streaming", async () => {
    const { result } = renderHook(() => useJarvis());

    // Start command
    act(() => {
      result.current.sendCommand("long command");
    });

    // Abort immediately
    act(() => {
      result.current.abort();
    });

    expect(result.current.isStreaming).toBe(false);
    expect(result.current.isLoading).toBe(false);
  });
});

describe("useAgents Hook", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockedApiClient.get.mockResolvedValue({
      data: {
        agents: [],
        total: 0,
      },
      status: 200,
      headers: new Headers(),
    });
  });

  it("should initialize with empty agents", async () => {
    const { result } = renderHook(() => useAgents());

    await waitFor(() => {
      expect(result.current.agents).toEqual([]);
    });
  });

  it("should have all required actions", () => {
    const { result } = renderHook(() => useAgents());

    expect(typeof result.current.fetchAgents).toBe("function");
    expect(typeof result.current.pauseAgent).toBe("function");
    expect(typeof result.current.resumeAgent).toBe("function");
    expect(typeof result.current.fetchAgentLogs).toBe("function");
    expect(typeof result.current.getAgentById).toBe("function");
    expect(typeof result.current.refresh).toBe("function");
  });

  it("should pause agent", async () => {
    mockedApiClient.post.mockResolvedValueOnce({
      data: undefined,
      status: 200,
      headers: new Headers(),
    });

    const { result } = renderHook(() => useAgents());

    await act(async () => {
      await result.current.pauseAgent("agent-1");
    });

    expect(mockedApiClient.post).toHaveBeenCalledWith("/agents/agent-1/pause");
  });

  it("should resume agent", async () => {
    mockedApiClient.post.mockResolvedValueOnce({
      data: undefined,
      status: 200,
      headers: new Headers(),
    });

    const { result } = renderHook(() => useAgents());

    await act(async () => {
      await result.current.resumeAgent("agent-1");
    });

    expect(mockedApiClient.post).toHaveBeenCalledWith("/agents/agent-1/resume");
  });
});

describe("useNotifications Hook", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockedApiClient.get.mockResolvedValue({
      data: {
        notifications: [],
        total: 0,
        unreadCount: 0,
        page: 1,
        pageSize: 20,
      },
      status: 200,
      headers: new Headers(),
    });
  });

  it("should initialize with empty notifications", async () => {
    const { result } = renderHook(() => useNotifications());

    await waitFor(() => {
      expect(result.current.notifications).toEqual([]);
    });
    expect(result.current.unreadCount).toBe(0);
  });

  it("should have all required actions", () => {
    const { result } = renderHook(() => useNotifications());

    expect(typeof result.current.fetchNotifications).toBe("function");
    expect(typeof result.current.markAsRead).toBe("function");
    expect(typeof result.current.markAllAsRead).toBe("function");
    expect(typeof result.current.subscribe).toBe("function");
    expect(typeof result.current.refresh).toBe("function");
  });

  it("should mark notification as read", async () => {
    mockedApiClient.post.mockResolvedValueOnce({
      data: undefined,
      status: 200,
      headers: new Headers(),
    });

    const { result } = renderHook(() => useNotifications());

    await act(async () => {
      await result.current.markAsRead("notif-1");
    });

    expect(mockedApiClient.post).toHaveBeenCalledWith("/notifications/notif-1/read");
  });

  it("should mark all notifications as read", async () => {
    mockedApiClient.post.mockResolvedValueOnce({
      data: undefined,
      status: 200,
      headers: new Headers(),
    });

    const { result } = renderHook(() => useNotifications());

    await act(async () => {
      await result.current.markAllAsRead();
    });

    expect(mockedApiClient.post).toHaveBeenCalledWith("/notifications/read-all");
  });
});

describe("useSearch Hook", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    localStorage.clear();
  });

  afterEach(() => {
    vi.clearAllMocks();
  });

  it("should initialize with empty state", () => {
    const { result } = renderHook(() => useSearch());

    expect(result.current.results).toEqual([]);
    expect(result.current.suggestions).toEqual([]);
    expect(result.current.query).toBe("");
    expect(result.current.isLoading).toBe(false);
  });

  it("should have all required actions", () => {
    const { result } = renderHook(() => useSearch());

    expect(typeof result.current.search).toBe("function");
    expect(typeof result.current.fetchSuggestions).toBe("function");
    expect(typeof result.current.clearResults).toBe("function");
    expect(typeof result.current.clearHistory).toBe("function");
    expect(typeof result.current.removeFromHistory).toBe("function");
    expect(typeof result.current.clearError).toBe("function");
  });

  it("should perform search", async () => {
    const mockResults = [
      {
        id: "r1",
        type: "ticket",
        title: "Test Ticket",
        url: "/tickets/r1",
        score: 0.95,
      },
    ];

    mockedApiClient.get.mockResolvedValueOnce({
      data: {
        results: mockResults,
        total: 1,
        query: "test",
        took: 50,
      },
      status: 200,
      headers: new Headers(),
    });

    const { result } = renderHook(() => useSearch());

    await act(async () => {
      await result.current.search("test");
    });

    await waitFor(() => {
      expect(result.current.results).toHaveLength(1);
      expect(result.current.total).toBe(1);
    });
  });

  it("should clear results", async () => {
    mockedApiClient.get.mockResolvedValueOnce({
      data: {
        results: [{ id: "r1", type: "ticket", title: "Test", url: "/t/1", score: 1 }],
        total: 1,
        query: "test",
        took: 50,
      },
      status: 200,
      headers: new Headers(),
    });

    const { result } = renderHook(() => useSearch());

    await act(async () => {
      await result.current.search("test");
    });

    await waitFor(() => {
      expect(result.current.results.length).toBeGreaterThan(0);
    });

    act(() => {
      result.current.clearResults();
    });

    expect(result.current.results).toEqual([]);
    expect(result.current.query).toBe("");
  });

  it("should clear history", () => {
    const { result } = renderHook(() => useSearch());

    act(() => {
      result.current.clearHistory();
    });

    expect(result.current.recentSearches).toEqual([]);
  });
});
