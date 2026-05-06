/**
 * PARWA Services
 * Export all API services for frontend-backend integration.
 */

// API Client
export { apiClient, createAPIClient, APIError } from "./api/client";
export type { APIResponse, RequestConfig } from "./api/client";

// Auth (existing)
export { authAPI } from "./api/auth";
export type { User, LoginCredentials, RegisterData, AuthResponse } from "./api/auth";

// Services
export { approvalService } from "./approval.service";
export type { Approval, ApprovalFilters } from "./approval.service";

export { ticketService } from "./ticket.service";
export type { Ticket, TicketFilters } from "./ticket.service";

export { analyticsService } from "./analytics.service";
export type { DashboardMetrics, ChartData } from "./analytics.service";

export { jarvisService } from "./jarvis.service";
export type { JarvisResponse, StreamCallbacks } from "./jarvis.service";

export { agentService } from "./agent.service";
export type { Agent, AgentLog } from "./agent.service";

export { settingsService } from "./settings.service";
export type { ProfileSettings, TeamMember, Integration, ApiKey } from "./settings.service";

export { notificationService } from "./notification.service";
export type { Notification } from "./notification.service";

export { webhookService } from "./webhook.service";
export type { Webhook, WebhookDelivery } from "./webhook.service";
