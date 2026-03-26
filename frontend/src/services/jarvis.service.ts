/**
 * PARWA Jarvis Service
 * CRITICAL: Handles Jarvis command execution with streaming support.
 */

import { apiClient } from "./api/client";

export interface JarvisResponse {
  command: string;
  result: string;
  data?: Record<string, unknown>;
  executionTime: number;
}

export interface StreamCallbacks {
  onChunk: (chunk: string) => void;
  onComplete: (response: string) => void;
  onError: (error: Error) => void;
}

export const jarvisService = {
  /** Execute command and get response */
  async executeCommand(command: string): Promise<JarvisResponse> {
    const res = await apiClient.post<JarvisResponse>("/jarvis/command", { command });
    return res.data;
  },

  /** CRITICAL: Execute command with streaming response */
  async executeStreaming(command: string, callbacks: StreamCallbacks): Promise<void> {
    const token = apiClient.getAuthToken();
    const baseUrl = process.env.NEXT_PUBLIC_API_URL || "/api";

    try {
      const response = await fetch(`${baseUrl}/jarvis/stream`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
        body: JSON.stringify({ command }),
      });

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`);
      }

      const reader = response.body?.getReader();
      if (!reader) {
        // Fallback to non-streaming
        const data = await response.json();
        callbacks.onComplete(data.result || data.message);
        return;
      }

      const decoder = new TextDecoder();
      let accumulated = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        const chunk = decoder.decode(value, { stream: true });
        accumulated += chunk;
        callbacks.onChunk(chunk);
      }

      callbacks.onComplete(accumulated);
    } catch (error) {
      callbacks.onError(error instanceof Error ? error : new Error(String(error)));
    }
  },

  /** Pause all refunds - critical Jarvis command */
  async pauseRefunds(): Promise<JarvisResponse> {
    return this.executeCommand("pause_refunds");
  },

  /** Resume refunds */
  async resumeRefunds(): Promise<JarvisResponse> {
    return this.executeCommand("resume_refunds");
  },

  /** Get system stats */
  async getStats(): Promise<JarvisResponse> {
    return this.executeCommand("get_stats");
  },
};

export default jarvisService;
