/**
 * PARWA Channels API Client
 *
 * API helper functions for channel configuration management.
 * Communicates with the backend channels API endpoints.
 *
 * D9-P10 FIX: Refactored to use centralized API wrapper (get/put/post)
 * instead of raw apiClient calls. This ensures channel requests go
 * through the same safe-parse, token-refresh, and error-handling
 * pipeline as all other API calls.
 */

import { get, put, post } from '@/lib/api';

// ── Types ──────────────────────────────────────────────────────────────

export interface ChannelInfo {
  name: string;
  channel_type: string;
  description: string;
}

export interface ChannelConfig {
  channel_type: string;
  channel_category: string;
  description: string;
  is_enabled: boolean;
  config: Record<string, unknown>;
  auto_create_ticket: boolean;
  char_limit: number | null;
  allowed_file_types: string[];
  max_file_size: number;
}

export interface ChannelTestResult {
  channel_type: string;
  success: boolean;
  message: string;
  tested_at: string;
}

export interface UpdateChannelConfigPayload {
  is_enabled?: boolean;
  config?: Record<string, unknown>;
  auto_create_ticket?: boolean;
  char_limit?: number | null;
  allowed_file_types?: string[];
  max_file_size?: number;
}

// ── API Functions ──────────────────────────────────────────────────────

/**
 * List all available system channels.
 */
export async function getAvailableChannels(): Promise<ChannelInfo[]> {
  return get<ChannelInfo[]>('/api/v1/channels/');
}

/**
 * Get company's channel configuration (all channels with current settings).
 */
export async function getChannelConfig(): Promise<ChannelConfig[]> {
  return get<ChannelConfig[]>('/api/v1/channels/config');
}

/**
 * Update configuration for a specific channel.
 */
export async function updateChannelConfig(
  channelType: string,
  payload: UpdateChannelConfigPayload,
): Promise<ChannelConfig> {
  return put<ChannelConfig>(
    `/api/v1/channels/config/${channelType}`,
    payload,
  );
}

/**
 * Test connectivity for a channel.
 */
export async function testChannelConnection(
  channelType: string,
  testConfig?: Record<string, unknown>,
): Promise<ChannelTestResult> {
  return post<ChannelTestResult>(
    `/api/v1/channels/config/${channelType}/test`,
    { test_config: testConfig },
  );
}
