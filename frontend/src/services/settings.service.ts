/**
 * PARWA Settings Service
 * Handles settings and configuration API operations.
 */

import { apiClient } from "./api/client";

export interface ProfileSettings {
  name: string;
  email: string;
  phone?: string;
  timezone: string;
  language: string;
  avatar?: string;
}

export interface TeamMember {
  id: string;
  name: string;
  email: string;
  role: "admin" | "agent" | "viewer";
  status: "active" | "invited" | "inactive";
  createdAt: string;
}

export interface Integration {
  id: string;
  name: string;
  type: string;
  status: "connected" | "disconnected" | "error";
  config: Record<string, unknown>;
  lastSync?: string;
}

export interface ApiKey {
  id: string;
  name: string;
  prefix: string;
  permissions: string[];
  lastUsed?: string;
  createdAt: string;
  expiresAt?: string;
}

export const settingsService = {
  // Profile
  async getProfile() {
    const res = await apiClient.get<ProfileSettings>("/settings/profile");
    return res.data;
  },
  async updateProfile(data: Partial<ProfileSettings>) {
    const res = await apiClient.patch<ProfileSettings>("/settings/profile", data);
    return res.data;
  },

  // Team
  async getTeam() {
    const res = await apiClient.get<TeamMember[]>("/settings/team");
    return res.data;
  },
  async inviteMember(email: string, role: TeamMember["role"]) {
    const res = await apiClient.post<TeamMember>("/settings/team/invite", { email, role });
    return res.data;
  },
  async removeMember(id: string) {
    await apiClient.delete(`/settings/team/${id}`);
  },
  async updateMemberRole(id: string, role: TeamMember["role"]) {
    const res = await apiClient.patch<TeamMember>(`/settings/team/${id}`, { role });
    return res.data;
  },

  // Integrations
  async getIntegrations() {
    const res = await apiClient.get<Integration[]>("/settings/integrations");
    return res.data;
  },
  async connectIntegration(type: string, config: Record<string, unknown>) {
    const res = await apiClient.post<Integration>("/settings/integrations/connect", { type, config });
    return res.data;
  },
  async disconnectIntegration(id: string) {
    await apiClient.post(`/settings/integrations/${id}/disconnect`);
  },

  // API Keys
  async getApiKeys() {
    const res = await apiClient.get<ApiKey[]>("/settings/api-keys");
    return res.data;
  },
  async createApiKey(name: string, permissions: string[]) {
    const res = await apiClient.post<{ key: ApiKey; secret: string }>("/settings/api-keys", { name, permissions });
    return res.data;
  },
  async revokeApiKey(id: string) {
    await apiClient.delete(`/settings/api-keys/${id}`);
  },
};

export default settingsService;
