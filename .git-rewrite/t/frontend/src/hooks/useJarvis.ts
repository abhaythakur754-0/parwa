/**
 * PARWA useJarvis Hook
 *
 * Custom hook for Jarvis command terminal.
 * Handles sending commands and streaming responses.
 *
 * Features:
 * - Send commands to Jarvis
 * - Stream responses in real-time
 * - Command history management
 * - Abort capability
 */

import { useState, useCallback, useRef } from "react";
import { apiClient } from "../services/api/client";
import { useUIStore } from "../stores/uiStore";

/**
 * Command history item interface.
 */
export interface CommandHistoryItem {
  id: string;
  command: string;
  response: string;
  timestamp: string;
  status: "success" | "error" | "aborted";
}

/**
 * Jarvis command type.
 */
export type JarvisCommand =
  | "pause_refunds"
  | "resume_refunds"
  | "escalate_ticket"
  | "get_stats"
  | "analyze_customer"
  | "generate_report"
  | "custom";

/**
 * Jarvis response interface.
 */
export interface JarvisResponse {
  command: string;
  result: string;
  data?: Record<string, unknown>;
  executionTime: number;
}

/**
 * useJarvis hook return type.
 */
export interface UseJarvisReturn {
  /** Current streaming response */
  response: string;
  /** Whether currently streaming */
  isStreaming: boolean;
  /** Command history */
  commandHistory: CommandHistoryItem[];
  /** Loading state */
  isLoading: boolean;
  /** Error state */
  error: string | null;

  // Actions
  /** Send a command and stream response */
  sendCommand: (command: string) => Promise<void>;
  /** Send a structured command */
  sendStructuredCommand: (command: JarvisCommand, params?: Record<string, unknown>) => Promise<void>;
  /** Abort current stream */
  abort: () => void;
  /** Clear current response */
  clearResponse: () => void;
  /** Clear command history */
  clearHistory: () => void;
  /** Clear error */
  clearError: () => void;
}

/**
 * Generate unique ID for history items.
 */
function generateId(): string {
  return `cmd-${Date.now()}-${Math.random().toString(36).substring(2, 9)}`;
}

/**
 * Custom hook for Jarvis command terminal.
 *
 * @returns Jarvis state and actions
 *
 * @example
 * ```tsx
 * function JarvisTerminal() {
 *   const {
 *     response,
 *     isStreaming,
 *     sendCommand,
 *     abort
 *   } = useJarvis();
 *
 *   const handleSubmit = (cmd: string) => {
 *     sendCommand(cmd);
 *   };
 *
 *   return (
 *     <div>
 *       <TerminalOutput content={response} />
 *       <button onClick={abort} disabled={!isStreaming}>
 *         Abort
 *       </button>
 *     </div>
 *   );
 * }
 * ```
 */
export function useJarvis(): UseJarvisReturn {
  const [response, setResponse] = useState("");
  const [isStreaming, setIsStreaming] = useState(false);
  const [commandHistory, setCommandHistory] = useState<CommandHistoryItem[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const abortControllerRef = useRef<AbortController | null>(null);
  const { addToast } = useUIStore();

  /**
   * Add item to command history.
   */
  const addToHistory = useCallback(
    (command: string, result: string, status: CommandHistoryItem["status"]): void => {
      const item: CommandHistoryItem = {
        id: generateId(),
        command,
        response: result,
        timestamp: new Date().toISOString(),
        status,
      };

      setCommandHistory((prev) => [item, ...prev].slice(0, 100)); // Keep last 100
    },
    []
  );

  /**
   * Send a command and stream response.
   */
  const sendCommand = useCallback(
    async (command: string): Promise<void> => {
      if (!command.trim()) {
        return;
      }

      // Abort any existing stream
      if (abortControllerRef.current) {
        abortControllerRef.current.abort();
      }

      setIsLoading(true);
      setIsStreaming(true);
      setError(null);
      setResponse("");

      // Create new abort controller
      abortControllerRef.current = new AbortController();

      try {
        // Try streaming endpoint first
        const streamingSupported = false; // Will be enabled when backend supports

        if (streamingSupported) {
          // Streaming implementation (future)
          const streamResponse = await fetch(
            `${process.env.NEXT_PUBLIC_API_URL || "/api"}/jarvis/stream`,
            {
              method: "POST",
              headers: {
                "Content-Type": "application/json",
                Authorization: `Bearer ${apiClient.getAuthToken()}`,
              },
              body: JSON.stringify({ command }),
              signal: abortControllerRef.current.signal,
            }
          );

          if (!streamResponse.ok) {
            throw new Error(`HTTP ${streamResponse.status}: ${streamResponse.statusText}`);
          }

          const reader = streamResponse.body?.getReader();
          if (!reader) {
            throw new Error("Streaming not supported");
          }

          const decoder = new TextDecoder();
          let accumulatedResponse = "";

          while (true) {
            const { done, value } = await reader.read();

            if (done) break;

            const chunk = decoder.decode(value, { stream: true });
            accumulatedResponse += chunk;
            setResponse(accumulatedResponse);
          }

          addToHistory(command, accumulatedResponse, "success");
        } else {
          // Fallback to regular API call with simulated streaming
          const apiResponse = await apiClient.post<JarvisResponse>(
            "/jarvis/command",
            { command },
            { signal: abortControllerRef.current.signal }
          );

          const resultText = apiResponse.data.result;

          // Simulate streaming for better UX
          const words = resultText.split(" ");
          let currentIndex = 0;

          const streamInterval = setInterval(() => {
            if (currentIndex >= words.length) {
              clearInterval(streamInterval);
              setIsStreaming(false);
              addToHistory(command, resultText, "success");
              return;
            }

            const chunkSize = Math.min(3, words.length - currentIndex);
            const chunk = words.slice(currentIndex, currentIndex + chunkSize).join(" ");
            currentIndex += chunkSize;

            setResponse((prev) => (prev ? `${prev} ${chunk}` : chunk));
          }, 50);

          // Wait for streaming to complete
          await new Promise<void>((resolve) => {
            const checkComplete = setInterval(() => {
              if (currentIndex >= words.length) {
                clearInterval(checkComplete);
                resolve();
              }
            }, 100);
          });

          addToast({
            title: "Command executed",
            description: "Jarvis has processed your command.",
            variant: "success",
          });
        }
      } catch (err) {
        // Check if aborted
        if (err instanceof Error && err.name === "AbortError") {
          addToHistory(command, response || "Command aborted", "aborted");
          addToast({
            title: "Command aborted",
            description: "The command was interrupted.",
            variant: "warning",
          });
          return;
        }

        const message = err instanceof Error ? err.message : "Failed to execute command";
        setError(message);
        addToHistory(command, message, "error");

        addToast({
          title: "Command failed",
          description: message,
          variant: "error",
        });
      } finally {
        setIsLoading(false);
        setIsStreaming(false);
        abortControllerRef.current = null;
      }
    },
    [addToHistory, addToast, response]
  );

  /**
   * Send a structured command.
   */
  const sendStructuredCommand = useCallback(
    async (command: JarvisCommand, params?: Record<string, unknown>): Promise<void> => {
      const fullCommand = params ? `${command} ${JSON.stringify(params)}` : command;
      await sendCommand(fullCommand);
    },
    [sendCommand]
  );

  /**
   * Abort current stream.
   */
  const abort = useCallback((): void => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
      abortControllerRef.current = null;
      setIsStreaming(false);
      setIsLoading(false);
    }
  }, []);

  /**
   * Clear current response.
   */
  const clearResponse = useCallback((): void => {
    setResponse("");
  }, []);

  /**
   * Clear command history.
   */
  const clearHistory = useCallback((): void => {
    setCommandHistory([]);
  }, []);

  /**
   * Clear error.
   */
  const clearError = useCallback((): void => {
    setError(null);
  }, []);

  return {
    response,
    isStreaming,
    commandHistory,
    isLoading,
    error,
    sendCommand,
    sendStructuredCommand,
    abort,
    clearResponse,
    clearHistory,
    clearError,
  };
}

export default useJarvis;
