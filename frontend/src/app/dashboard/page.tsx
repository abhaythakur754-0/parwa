"use client";

/**
 * PARWA Dashboard Home Page
 *
 * Main dashboard page with stats cards, metrics, quick actions, and recent activity.
 * CRITICAL: Loads real API data from backend.
 */

import { useState, useEffect } from "react";
import Link from "next/link";
import { apiClient, APIError } from "@/services/api/client";
import { useAuthStore } from "@/stores/authStore";
import { useToasts } from "@/stores/uiStore";
import StatsCard from "@/components/dashboard/StatsCard";
import MetricCard from "@/components/dashboard/MetricCard";
import QuickActions from "@/components/dashboard/QuickActions";
import RecentActivity from "@/components/dashboard/RecentActivity";

/**
 * Dashboard stats from API.
 */
interface DashboardStats {
  totalTickets: number;
  openTickets: number;
  resolvedToday: number;
  avgResponseTime: number; // in minutes
  totalTicketsTrend: number; // percentage
  openTicketsTrend: number;
  resolvedTodayTrend: number;
  avgResponseTimeTrend: number;
}

/**
 * Metric data for charts.
 */
interface MetricData {
  label: string;
  value: number;
  data: number[]; // Last 7 days
  trend: number;
}

/**
 * Activity item from API.
 */
interface ActivityItem {
  id: string;
  type: "ticket_created" | "ticket_resolved" | "approval" | "escalation" | "agent_action";
  user: string;
  action: string;
  timestamp: string;
  metadata?: Record<string, unknown>;
}

/**
 * Dashboard API response.
 */
interface DashboardResponse {
  stats: DashboardStats;
  metrics: MetricData[];
  recentActivity: ActivityItem[];
}

/**
 * Format response time for display.
 */
function formatResponseTime(minutes: number): string {
  if (minutes < 60) {
    return `${Math.round(minutes)}m`;
  }
  const hours = Math.floor(minutes / 60);
  const mins = Math.round(minutes % 60);
  return mins > 0 ? `${hours}h ${mins}m` : `${hours}h`;
}

/**
 * Dashboard home page component.
 */
export default function DashboardPage() {
  const { isAuthenticated, user } = useAuthStore();
  const { addToast } = useToasts();

  // State
  const [stats, setStats] = useState<DashboardStats | null>(null);
  const [metrics, setMetrics] = useState<MetricData[]>([]);
  const [activities, setActivities] = useState<ActivityItem[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  /**
   * Fetch dashboard data from API.
   * CRITICAL: This must load real data.
   */
  useEffect(() => {
    const fetchDashboardData = async () => {
      setIsLoading(true);
      setError(null);

      try {
        const response = await apiClient.get<DashboardResponse>("/dashboard");

        setStats(response.data.stats);
        setMetrics(response.data.metrics);
        setActivities(response.data.recentActivity);
      } catch (err) {
        const message =
          err instanceof APIError ? err.message : "Failed to load dashboard data";
        setError(message);
        addToast({
          title: "Error",
          description: message,
          variant: "error",
        });

        // Set mock data for development/demo purposes
        // This ensures the dashboard still renders even if backend is unavailable
        setStats({
          totalTickets: 1247,
          openTickets: 89,
          resolvedToday: 34,
          avgResponseTime: 12.5,
          totalTicketsTrend: 12.5,
          openTicketsTrend: -5.2,
          resolvedTodayTrend: 8.3,
          avgResponseTimeTrend: -15.0,
        });

        setMetrics([
          {
            label: "Ticket Volume",
            value: 1247,
            data: [145, 167, 189, 156, 178, 201, 195],
            trend: 12.5,
          },
          {
            label: "Resolution Rate",
            value: 87.5,
            data: [82, 85, 84, 88, 87, 89, 87.5],
            trend: 5.2,
          },
          {
            label: "CSAT Score",
            value: 4.6,
            data: [4.3, 4.4, 4.5, 4.4, 4.6, 4.5, 4.6],
            trend: 3.5,
          },
        ]);

        setActivities([
          {
            id: "1",
            type: "ticket_resolved",
            user: "Sarah Agent",
            action: "Resolved ticket #TKT-1234",
            timestamp: new Date(Date.now() - 5 * 60000).toISOString(),
          },
          {
            id: "2",
            type: "approval",
            user: "John Manager",
            action: "Approved refund request for $89.99",
            timestamp: new Date(Date.now() - 15 * 60000).toISOString(),
          },
          {
            id: "3",
            type: "ticket_created",
            user: "PARWA Mini",
            action: "Created ticket #TKT-1235 from chat",
            timestamp: new Date(Date.now() - 30 * 60000).toISOString(),
          },
          {
            id: "4",
            type: "escalation",
            user: "PARWA Junior",
            action: "Escalated ticket #TKT-1230 to senior support",
            timestamp: new Date(Date.now() - 45 * 60000).toISOString(),
          },
          {
            id: "5",
            type: "agent_action",
            user: "PARWA High",
            action: "Completed churn risk analysis for 15 customers",
            timestamp: new Date(Date.now() - 60 * 60000).toISOString(),
          },
        ]);
      } finally {
        setIsLoading(false);
      }
    };

    if (isAuthenticated) {
      fetchDashboardData();
    }
  }, [isAuthenticated, addToast]);

  /**
   * Handle quick action clicks.
   */
  const handleQuickAction = (action: string) => {
    switch (action) {
      case "create_ticket":
        // Navigate to create ticket page
        window.location.href = "/dashboard/tickets/new";
        break;
      case "approve_pending":
        window.location.href = "/dashboard/approvals";
        break;
      case "run_report":
        window.location.href = "/dashboard/analytics";
        break;
      case "view_analytics":
        window.location.href = "/dashboard/analytics";
        break;
    }
  };

  /**
   * Loading skeleton component.
   */
  const LoadingSkeleton = () => (
    <div className="space-y-6">
      {/* Stats Row */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        {[...Array(4)].map((_, i) => (
          <div
            key={i}
            className="h-32 bg-muted animate-pulse rounded-xl"
          />
        ))}
      </div>
      {/* Metrics Row */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {[...Array(3)].map((_, i) => (
          <div
            key={i}
            className="h-48 bg-muted animate-pulse rounded-xl"
          />
        ))}
      </div>
      {/* Activity */}
      <div className="h-64 bg-muted animate-pulse rounded-xl" />
    </div>
  );

  /**
   * Error state with retry.
   */
  const ErrorState = () => (
    <div className="text-center py-12">
      <p className="text-destructive text-lg">{error}</p>
      <p className="text-muted-foreground text-sm mt-2">
        Showing demo data instead
      </p>
    </div>
  );

  return (
    <div className="space-y-6">
      {/* Page Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Dashboard</h1>
          <p className="text-muted-foreground">
            Welcome back, {user?.name || "User"}! Here&apos;s what&apos;s happening today.
          </p>
        </div>
        <div className="text-sm text-muted-foreground">
          Last updated: {new Date().toLocaleTimeString()}
        </div>
      </div>

      {isLoading ? (
        <LoadingSkeleton />
      ) : (
        <>
          {/* Stats Cards Row */}
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
            <StatsCard
              title="Total Tickets"
              value={stats?.totalTickets ?? 0}
              trend={stats?.totalTicketsTrend ?? 0}
              icon={
                <svg className="h-6 w-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2" />
                </svg>
              }
              color="blue"
            />
            <StatsCard
              title="Open Tickets"
              value={stats?.openTickets ?? 0}
              trend={stats?.openTicketsTrend ?? 0}
              icon={
                <svg className="h-6 w-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
                </svg>
              }
              color="yellow"
            />
            <StatsCard
              title="Resolved Today"
              value={stats?.resolvedToday ?? 0}
              trend={stats?.resolvedTodayTrend ?? 0}
              icon={
                <svg className="h-6 w-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
                </svg>
              }
              color="green"
            />
            <StatsCard
              title="Avg Response Time"
              value={formatResponseTime(stats?.avgResponseTime ?? 0)}
              trend={stats?.avgResponseTimeTrend ?? 0}
              icon={
                <svg className="h-6 w-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
                </svg>
              }
              color="blue"
              invertTrend
            />
          </div>

          {/* Quick Actions */}
          <QuickActions onAction={handleQuickAction} />

          {/* Metrics Row */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            {metrics.map((metric, index) => (
              <MetricCard
                key={index}
                title={metric.label}
                value={metric.value}
                data={metric.data}
                trend={metric.trend}
              />
            ))}
          </div>

          {/* Recent Activity */}
          <RecentActivity activities={activities} />

          {/* Error Notice */}
          {error && <ErrorState />}
        </>
      )}
    </div>
  );
}
