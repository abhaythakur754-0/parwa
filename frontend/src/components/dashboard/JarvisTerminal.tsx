"use client";

import * as React from "react";
import { cn } from "@/utils/utils";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import {
  Send,
  Copy,
  Check,
  ChevronUp,
  ChevronDown,
  Terminal,
  Loader2,
} from "lucide-react";

/**
 * Terminal line type.
 */
export interface TerminalLine {
  /** Unique line ID */
  id: string;
  /** Line content */
  content: string;
  /** Line type */
  type: "input" | "output" | "error" | "system";
  /** Timestamp */
  timestamp: Date;
}

/**
 * Jarvis command handler.
 */
export type CommandHandler = (
  command: string
) => Promise<string | AsyncGenerator<string, void, unknown>>;

/**
 * Jarvis terminal props.
 */
export interface JarvisTerminalProps {
  /** Terminal title */
  title?: string;
  /** Welcome message */
  welcomeMessage?: string;
  /** Command handler function */
  onCommand?: CommandHandler;
  /** Available commands for autocomplete */
  commands?: string[];
  /** Maximum lines to display */
  maxLines?: number;
  /** Additional CSS classes */
  className?: string;
}

// Available Jarvis commands
const DEFAULT_COMMANDS = [
  "status",
  "pause refunds",
  "resume refunds",
  "force escalation",
  "list approvals",
  "agent status",
  "system health",
  "clear",
  "help",
];

/**
 * Jarvis Terminal Component
 *
 * A terminal-like interface for interacting with Jarvis AI assistant.
 * Supports command input, response streaming, command history, and copy to clipboard.
 *
 * @example
 * ```tsx
 * <JarvisTerminal
 *   onCommand={async (cmd) => {
 *     // Handle command and return response
 *     return "Command executed";
 *   }}
 *   commands={["status", "pause refunds"]}
 * />
 * ```
 */
export function JarvisTerminal({
  title = "JARVIS Terminal",
  welcomeMessage = "Welcome to JARVIS. Type 'help' for available commands.",
  onCommand,
  commands = DEFAULT_COMMANDS,
  maxLines = 100,
  className,
}: JarvisTerminalProps) {
  const [lines, setLines] = React.useState<TerminalLine[]>([
    {
      id: "welcome",
      content: welcomeMessage,
      type: "system",
      timestamp: new Date(),
    },
  ]);
  const [input, setInput] = React.useState("");
  const [isProcessing, setIsProcessing] = React.useState(false);
  const [copiedId, setCopiedId] = React.useState<string | null>(null);
  const [historyIndex, setHistoryIndex] = React.useState(-1);
  const inputRef = React.useRef<HTMLInputElement>(null);
  const terminalRef = React.useRef<HTMLDivElement>(null);
  const commandHistory = React.useRef<string[]>([]);

  // Auto-scroll to bottom
  React.useEffect(() => {
    if (terminalRef.current) {
      terminalRef.current.scrollTop = terminalRef.current.scrollHeight;
    }
  }, [lines]);

  // Focus input on mount
  React.useEffect(() => {
    inputRef.current?.focus();
  }, []);

  const addLine = (content: string, type: TerminalLine["type"]) => {
    const newLine: TerminalLine = {
      id: `line-${Date.now()}-${Math.random().toString(36).slice(2, 9)}`,
      content,
      type,
      timestamp: new Date(),
    };

    setLines((prev) => {
      const updated = [...prev, newLine];
      // Limit max lines
      if (updated.length > maxLines) {
        return updated.slice(-maxLines);
      }
      return updated;
    });
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!input.trim() || isProcessing) return;

    const command = input.trim();
    setInput("");
    setIsProcessing(true);

    // Add command to terminal
    addLine(`> ${command}`, "input");

    // Add to history
    commandHistory.current.unshift(command);
    if (commandHistory.current.length > 50) {
      commandHistory.current = commandHistory.current.slice(0, 50);
    }
    setHistoryIndex(-1);

    // Handle built-in commands
    if (command.toLowerCase() === "clear") {
      setLines([
        {
          id: "cleared",
          content: welcomeMessage,
          type: "system",
          timestamp: new Date(),
        },
      ]);
      setIsProcessing(false);
      return;
    }

    if (command.toLowerCase() === "help") {
      addLine(
        "Available commands:\n" + commands.map((c) => `  • ${c}`).join("\n"),
        "output"
      );
      setIsProcessing(false);
      return;
    }

    // Handle custom commands
    if (onCommand) {
      try {
        const result = await onCommand(command);

        // Check if it's an async generator (streaming)
        if (result && typeof (result as AsyncGenerator)[Symbol.asyncIterator] === "function") {
          const generator = result as AsyncGenerator<string>;
          let fullResponse = "";

          for await (const chunk of generator) {
            fullResponse += chunk;
            // Update last line with streaming content
            setLines((prev) => {
              const updated = [...prev];
              const lastLine = updated[updated.length - 1];
              if (lastLine && lastLine.type === "output") {
                lastLine.content = fullResponse;
              } else {
                updated.push({
                  id: `stream-${Date.now()}`,
                  content: fullResponse,
                  type: "output",
                  timestamp: new Date(),
                });
              }
              return updated;
            });
          }
        } else {
          addLine(result || "Command executed successfully.", "output");
        }
      } catch (error) {
        addLine(
          `Error: ${error instanceof Error ? error.message : "Unknown error"}`,
          "error"
        );
      }
    } else {
      // Default handler for demo
      addLine(
        `Command "${command}" received. Connect onCommand handler for real responses.`,
        "system"
      );
    }

    setIsProcessing(false);
  };

  const handleCopy = async (content: string, lineId: string) => {
    try {
      await navigator.clipboard.writeText(content);
      setCopiedId(lineId);
      setTimeout(() => setCopiedId(null), 2000);
    } catch {
      console.error("Failed to copy");
    }
  };

  const handleHistoryUp = () => {
    if (commandHistory.current.length === 0) return;
    const newIndex = Math.min(historyIndex + 1, commandHistory.current.length - 1);
    setHistoryIndex(newIndex);
    setInput(commandHistory.current[newIndex] || "");
  };

  const handleHistoryDown = () => {
    if (historyIndex <= 0) {
      setHistoryIndex(-1);
      setInput("");
      return;
    }
    const newIndex = historyIndex - 1;
    setHistoryIndex(newIndex);
    setInput(commandHistory.current[newIndex] || "");
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "ArrowUp") {
      e.preventDefault();
      handleHistoryUp();
    } else if (e.key === "ArrowDown") {
      e.preventDefault();
      handleHistoryDown();
    }
  };

  return (
    <Card className={cn("w-full", className)} data-testid="jarvis-terminal">
      <CardHeader className="flex flex-row items-center justify-between pb-2">
        <CardTitle className="text-lg font-semibold flex items-center gap-2">
          <Terminal className="h-5 w-5" />
          {title}
        </CardTitle>
        <div className="flex items-center gap-1">
          <span
            className={cn(
              "w-2 h-2 rounded-full",
              isProcessing ? "bg-yellow-500 animate-pulse" : "bg-green-500"
            )}
            aria-label={isProcessing ? "Processing" : "Ready"}
          />
          <span className="text-xs text-muted-foreground">
            {isProcessing ? "Processing..." : "Ready"}
          </span>
        </div>
      </CardHeader>
      <CardContent className="p-0">
        {/* Terminal output */}
        <div
          ref={terminalRef}
          className="h-64 overflow-y-auto bg-gray-950 text-gray-100 font-mono text-sm p-4 space-y-2"
          onClick={() => inputRef.current?.focus()}
        >
          {lines.map((line) => (
            <div
              key={line.id}
              className={cn(
                "group flex items-start gap-2",
                line.type === "input" && "text-green-400",
                line.type === "output" && "text-gray-100",
                line.type === "error" && "text-red-400",
                line.type === "system" && "text-blue-400"
              )}
            >
              <span className="flex-1 whitespace-pre-wrap break-all">
                {line.content}
              </span>
              <Button
                variant="ghost"
                size="icon"
                className="h-6 w-6 opacity-0 group-hover:opacity-100 shrink-0 text-gray-400 hover:text-gray-200"
                onClick={(e) => {
                  e.stopPropagation();
                  handleCopy(line.content, line.id);
                }}
                aria-label="Copy to clipboard"
              >
                {copiedId === line.id ? (
                  <Check className="h-3 w-3" />
                ) : (
                  <Copy className="h-3 w-3" />
                )}
              </Button>
            </div>
          ))}
          {isProcessing && (
            <div className="flex items-center gap-2 text-yellow-400">
              <Loader2 className="h-4 w-4 animate-spin" />
              <span>Processing...</span>
            </div>
          )}
        </div>

        {/* Input area */}
        <form onSubmit={handleSubmit} className="border-t flex items-center p-2 gap-2">
          <span className="text-muted-foreground font-mono">$</span>
          <input
            ref={inputRef}
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Enter command..."
            className="flex-1 bg-transparent outline-none font-mono text-sm"
            disabled={isProcessing}
            list="command-suggestions"
            aria-label="Command input"
          />
          <datalist id="command-suggestions">
            {commands.map((cmd) => (
              <option key={cmd} value={cmd} />
            ))}
          </datalist>
          <Button
            type="submit"
            size="sm"
            disabled={!input.trim() || isProcessing}
            aria-label="Send command"
          >
            <Send className="h-4 w-4" />
          </Button>
        </form>

        {/* History navigation */}
        <div className="border-t px-3 py-1 flex items-center justify-between text-xs text-muted-foreground">
          <span>Use ↑↓ for history</span>
          <div className="flex items-center gap-2">
            <Button
              variant="ghost"
              size="sm"
              className="h-6 px-2"
              onClick={handleHistoryUp}
              disabled={commandHistory.current.length === 0}
              aria-label="Previous command"
            >
              <ChevronUp className="h-3 w-3" />
            </Button>
            <Button
              variant="ghost"
              size="sm"
              className="h-6 px-2"
              onClick={handleHistoryDown}
              disabled={historyIndex < 0}
              aria-label="Next command"
            >
              <ChevronDown className="h-3 w-3" />
            </Button>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}

export default JarvisTerminal;
