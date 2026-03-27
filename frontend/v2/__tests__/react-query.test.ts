/**
 * PARWA v2 - React Query Configuration Tests
 *
 * Unit tests for React Query client and helpers.
 */

import { describe, it, expect, vi, beforeEach } from "vitest";
import { createQueryClient, queryKeys } from "../lib/react-query/query-client";
import { QueryClient } from "@tanstack/react-query";

describe("createQueryClient", () => {
  it("should create a QueryClient instance", () => {
    const client = createQueryClient();
    expect(client).toBeInstanceOf(QueryClient);
  });

  it("should use default staleTime of 5 minutes", () => {
    const client = createQueryClient();
    const defaultOptions = client.getDefaultOptions();
    expect(defaultOptions.queries?.staleTime).toBe(5 * 60 * 1000);
  });

  it("should use default gcTime of 30 minutes", () => {
    const client = createQueryClient();
    const defaultOptions = client.getDefaultOptions();
    expect(defaultOptions.queries?.gcTime).toBe(30 * 60 * 1000);
  });

  it("should use default retry count of 3", () => {
    const client = createQueryClient();
    const defaultOptions = client.getDefaultOptions();
    expect(defaultOptions.queries?.retry).toBe(3);
  });

  it("should allow custom options", () => {
    const client = createQueryClient({
      staleTime: 10 * 60 * 1000,
      gcTime: 60 * 60 * 1000,
      retry: 5,
    });
    const defaultOptions = client.getDefaultOptions();
    expect(defaultOptions.queries?.staleTime).toBe(10 * 60 * 1000);
    expect(defaultOptions.queries?.gcTime).toBe(60 * 60 * 1000);
    expect(defaultOptions.queries?.retry).toBe(5);
  });

  it("should have refetchOnWindowFocus enabled", () => {
    const client = createQueryClient();
    const defaultOptions = client.getDefaultOptions();
    expect(defaultOptions.queries?.refetchOnWindowFocus).toBe(true);
  });

  it("should have refetchOnReconnect enabled", () => {
    const client = createQueryClient();
    const defaultOptions = client.getDefaultOptions();
    expect(defaultOptions.queries?.refetchOnReconnect).toBe(true);
  });
});

describe("queryKeys", () => {
  it("should generate ticket query keys", () => {
    expect(queryKeys.tickets.all).toEqual(["tickets"]);
    expect(queryKeys.tickets.lists()).toEqual(["tickets", "list"]);
    expect(queryKeys.tickets.list({ status: "open" })).toEqual([
      "tickets",
      "list",
      { status: "open" },
    ]);
    expect(queryKeys.tickets.detail("123")).toEqual(["tickets", "detail", "123"]);
    expect(queryKeys.tickets.search("query")).toEqual(["tickets", "search", "query"]);
  });

  it("should generate approval query keys", () => {
    expect(queryKeys.approvals.all).toEqual(["approvals"]);
    expect(queryKeys.approvals.lists()).toEqual(["approvals", "list"]);
    expect(queryKeys.approvals.detail("456")).toEqual(["approvals", "detail", "456"]);
    expect(queryKeys.approvals.stats()).toEqual(["approvals", "stats"]);
  });

  it("should generate analytics query keys", () => {
    expect(queryKeys.analytics.all).toEqual(["analytics"]);
    expect(queryKeys.analytics.overview()).toEqual(["analytics", "overview"]);
    expect(queryKeys.analytics.metrics({ start: "2024-01-01", end: "2024-01-31" })).toEqual([
      "analytics",
      "metrics",
      { start: "2024-01-01", end: "2024-01-31" },
    ]);
    expect(queryKeys.analytics.trends("7d")).toEqual(["analytics", "trends", "7d"]);
    expect(queryKeys.analytics.realtime()).toEqual(["analytics", "realtime"]);
  });

  it("should generate client query keys", () => {
    expect(queryKeys.clients.all).toEqual(["clients"]);
    expect(queryKeys.clients.lists()).toEqual(["clients", "list"]);
    expect(queryKeys.clients.detail("client-1")).toEqual(["clients", "detail", "client-1"]);
    expect(queryKeys.clients.health("client-1")).toEqual(["clients", "health", "client-1"]);
  });

  it("should generate dashboard query keys", () => {
    expect(queryKeys.dashboard.all).toEqual(["dashboard"]);
    expect(queryKeys.dashboard.metrics()).toEqual(["dashboard", "metrics"]);
    expect(queryKeys.dashboard.activity()).toEqual(["dashboard", "activity"]);
    expect(queryKeys.dashboard.notifications()).toEqual(["dashboard", "notifications"]);
    expect(queryKeys.dashboard.stats()).toEqual(["dashboard", "stats"]);
  });
});
