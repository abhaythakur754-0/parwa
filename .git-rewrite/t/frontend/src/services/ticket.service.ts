/**
 * PARWA Ticket Service
 * Handles ticket API operations with backend integration.
 */

import { apiClient } from "./api/client";

export interface Ticket {
  id: string;
  subject: string;
  description: string;
  status: "open" | "in_progress" | "resolved" | "closed";
  priority: "low" | "medium" | "high" | "critical";
  source: "email" | "chat" | "phone" | "web" | "api";
  customer: { id: string; name: string; email: string; phone?: string };
  assignee?: { id: string; name: string; email: string };
  messages: Array<{ id: string; content: string; sender: string; senderName: string; createdAt: string }>;
  tags: string[];
  createdAt: string;
  updatedAt: string;
}

export interface TicketFilters {
  status?: string;
  priority?: string;
  source?: string;
  assigneeId?: string;
  customerId?: string;
  search?: string;
}

export const ticketService = {
  async getTickets(filters?: TicketFilters, page = 1, pageSize = 20) {
    const params: Record<string, string> = { page: String(page), pageSize: String(pageSize) };
    if (filters) Object.entries(filters).forEach(([k, v]) => { if (v) params[k] = String(v); });
    const res = await apiClient.get<{ tickets: Ticket[]; total: number }>("/tickets", params);
    return res.data;
  },

  async getTicket(id: string) {
    const res = await apiClient.get<Ticket>(`/tickets/${id}`);
    return res.data;
  },

  async createTicket(data: Partial<Ticket>) {
    const res = await apiClient.post<Ticket>("/tickets", data);
    return res.data;
  },

  async updateTicket(id: string, data: Partial<Ticket>) {
    const res = await apiClient.patch<Ticket>(`/tickets/${id}`, data);
    return res.data;
  },

  async assignTicket(id: string, agentId: string) {
    const res = await apiClient.post<Ticket>(`/tickets/${id}/assign`, { agentId });
    return res.data;
  },

  async closeTicket(id: string, resolution: string) {
    const res = await apiClient.post<Ticket>(`/tickets/${id}/close`, { resolution });
    return res.data;
  },

  async searchTickets(query: string) {
    const res = await apiClient.get<Ticket[]>("/tickets/search", { q: query });
    return res.data;
  },
};

export default ticketService;
