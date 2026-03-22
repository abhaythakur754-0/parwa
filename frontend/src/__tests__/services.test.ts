/**
 * PARWA Services Tests
 */

import { describe, it, expect, vi, beforeEach } from "vitest";

vi.mock("../services/api/client", () => ({
  apiClient: {
    get: vi.fn(),
    post: vi.fn(),
    patch: vi.fn(),
    delete: vi.fn(),
    getAuthToken: vi.fn(() => "test-token"),
  },
}));

import { apiClient } from "../services/api/client";
import { approvalService } from "../services/approval.service";
import { ticketService } from "../services/ticket.service";
import { analyticsService } from "../services/analytics.service";
import { jarvisService } from "../services/jarvis.service";
import { agentService } from "../services/agent.service";
import { notificationService } from "../services/notification.service";
import { webhookService } from "../services/webhook.service";

const mockedApi = vi.mocked(apiClient);

describe("Approval Service", () => {
  beforeEach(() => vi.clearAllMocks());

  it("should fetch approvals", async () => {
    mockedApi.get.mockResolvedValueOnce({ data: { approvals: [], total: 0 }, status: 200, headers: new Headers() });
    const result = await approvalService.getApprovals();
    expect(result.approvals).toEqual([]);
  });

  it("should approve an item", async () => {
    mockedApi.post.mockResolvedValueOnce({ data: { id: "1", status: "approved" }, status: 200, headers: new Headers() });
    await approvalService.approve("1", "notes");
    expect(mockedApi.post).toHaveBeenCalledWith("/approvals/1/approve", { notes: "notes" });
  });

  it("should deny an item", async () => {
    mockedApi.post.mockResolvedValueOnce({ data: { id: "1", status: "denied" }, status: 200, headers: new Headers() });
    await approvalService.deny("1", "reason");
    expect(mockedApi.post).toHaveBeenCalledWith("/approvals/1/deny", { reason: "reason", notes: undefined });
  });
});

describe("Ticket Service", () => {
  beforeEach(() => vi.clearAllMocks());

  it("should fetch tickets", async () => {
    mockedApi.get.mockResolvedValueOnce({ data: { tickets: [], total: 0 }, status: 200, headers: new Headers() });
    const result = await ticketService.getTickets();
    expect(result.tickets).toEqual([]);
  });

  it("should create a ticket", async () => {
    mockedApi.post.mockResolvedValueOnce({ data: { id: "1", subject: "Test" }, status: 201, headers: new Headers() });
    await ticketService.createTicket({ subject: "Test" });
    expect(mockedApi.post).toHaveBeenCalledWith("/tickets", { subject: "Test" });
  });
});

describe("Analytics Service", () => {
  beforeEach(() => vi.clearAllMocks());

  it("should fetch metrics", async () => {
    mockedApi.get.mockResolvedValueOnce({ data: { totalTickets: 100 }, status: 200, headers: new Headers() });
    const result = await analyticsService.getMetrics();
    expect(result.totalTickets).toBe(100);
  });

  it("should fetch chart data", async () => {
    mockedApi.get.mockResolvedValueOnce({ data: { data: [], summary: { total: 0, average: 0 } }, status: 200, headers: new Headers() });
    const result = await analyticsService.getChartData("ticket_volume");
    expect(result.data).toEqual([]);
  });
});

describe("Jarvis Service", () => {
  beforeEach(() => vi.clearAllMocks());

  it("should execute command", async () => {
    mockedApi.post.mockResolvedValueOnce({ data: { command: "test", result: "done", executionTime: 100 }, status: 200, headers: new Headers() });
    const result = await jarvisService.executeCommand("test");
    expect(result.result).toBe("done");
  });
});

describe("Agent Service", () => {
  beforeEach(() => vi.clearAllMocks());

  it("should fetch agents", async () => {
    mockedApi.get.mockResolvedValueOnce({ data: { agents: [], total: 0 }, status: 200, headers: new Headers() });
    const result = await agentService.getAgents();
    expect(result.agents).toEqual([]);
  });

  it("should pause agent", async () => {
    mockedApi.post.mockResolvedValueOnce({ data: { id: "1", status: "paused" }, status: 200, headers: new Headers() });
    await agentService.pauseAgent("1");
    expect(mockedApi.post).toHaveBeenCalled();
  });
});

describe("Notification Service", () => {
  beforeEach(() => vi.clearAllMocks());

  it("should fetch notifications", async () => {
    mockedApi.get.mockResolvedValueOnce({ data: { notifications: [], total: 0, unreadCount: 0 }, status: 200, headers: new Headers() });
    const result = await notificationService.getNotifications();
    expect(result.notifications).toEqual([]);
  });

  it("should mark as read", async () => {
    mockedApi.post.mockResolvedValueOnce({ data: undefined, status: 200, headers: new Headers() });
    await notificationService.markAsRead("1");
    expect(mockedApi.post).toHaveBeenCalledWith("/notifications/1/read");
  });
});

describe("Webhook Service", () => {
  beforeEach(() => vi.clearAllMocks());

  it("should fetch webhooks", async () => {
    mockedApi.get.mockResolvedValueOnce({ data: [], status: 200, headers: new Headers() });
    const result = await webhookService.getWebhooks();
    expect(result).toEqual([]);
  });

  it("should create webhook", async () => {
    mockedApi.post.mockResolvedValueOnce({ data: { id: "1", name: "Test" }, status: 201, headers: new Headers() });
    await webhookService.createWebhook({ name: "Test", url: "https://example.com", events: ["ticket.created"] });
    expect(mockedApi.post).toHaveBeenCalled();
  });
});
