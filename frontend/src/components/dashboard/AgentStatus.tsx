"use client";

import * as React from "react";
import { cn } from "@/utils/utils";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
  Pause,
  Play,
  FileText,
  Clock,
  CheckCircle,
  AlertCircle,
  Activity,
} from "lucide-react";

/**
 * Agent status type.
 */
export type AgentStatusType = "active" | "idle" | "offline" | "paused" | "error";

/**
 * Agent variant type.
 */
export type AgentVariant = "mini" | "parwa" | "parwa_high";

/**
 * Agent data structure.
 */
export interface Agent {
  /** Unique agent ID */
  id: string;
  /** Agent name */
  name: string;
  /** Agent variant */
  variant: AgentVariant;
  /** Current status */
  status: AgentStatusType;
  /** Current task description */
  currentTask?: string;
  /** Performance metrics */
  performance: {
    /** Accuracy percentage (0-100) */
    accuracy: number;
    /** Average response time in seconds */
    avgResponseTime: number;
    /** Total tickets handled */
    ticketsHandled: number;
    /** Customer satisfaction score (0-100) */
    satisfactionScore: number;
  };
  /** Last activity timestamp */
  lastActivity: string;
  /** Uptime percentage */
  uptime: number;
}

/**
 * Agent status props.
 */
export interface AgentStatusProps {
  /** Agent data */
  agent: Agent;
  /** Callback when pause is clicked */
  onPause?: (agentId: string) => void;
  /** Callback when resume is clicked */
  onResume?: (agentId: string) => void;
  /** Callback to view logs */
  onViewLogs?: (agentId: string) => void;
  /** Compact display mode */
  compact?: boolean;
  /** Additional CSS classes */
  className?: string;
}

// Status colors and labels
const statusConfig: Record<
  AgentStatusType,
  { color: string; bgColor: string; label: string; icon: React.ReactNode }
> = {
  active: {
    color: "text-green-600",
    bgColor: "bg-green-100",
    label: "Active",
    icon: <CheckCircle className="h-4 w-4" />,
  },
  idle: {
    color: "text-yellow-600",
    bgColor: "bg-yellow-100",
    label: "Idle",
    icon: <Clock className="h-4 w-4" />,
  },
  offline: {
    color: "text-gray-500",
    bgColor: "bg-gray-100",
    label: "Offline",
    icon: <AlertCircle className="h-4 w-4" />,
  },
  paused: {
    color: "text-blue-600",
    bgColor: "bg-blue-100",
    label: "Paused",
    icon: <Pause className="h-4 w-4" />,
  },
  error: {
    color: "text-red-600",
    bgColor: "bg-red-100",
    label: "Error",
    icon: <AlertCircle className="h-4 w-4" />,
  },
};

// Variant labels
const variantLabels: Record<AgentVariant, string> = {
  mini: "Mini PARWA",
  parwa: "PARWA Junior",
  parwa_high: "PARWA High",
};

/**
 * Agent Status Card Component
 *
 * Displays agent status, performance metrics, and action buttons.
 *
 * @example
 * ```tsx
 * <AgentStatus
 *   agent={agentData}
 *   onPause={(id) => pauseAgent(id)}
 *   onResume={(id) => resumeAgent(id)}
 * />
 * ```
 */
export function AgentStatus({
  agent,
  onPause,
  onResume,
  onViewLogs,
  compact = false,
  className,
}: AgentStatusProps) {
  const config = statusConfig[agent.status];
  const isPaused = agent.status === "paused";
  const isActive = agent.status === "active";

  const formatRelativeTime = (timestamp: string): string => {
    const diff = Date.now() - new Date(timestamp).getTime();
    const minutes = Math.floor(diff / 60000);
    if (minutes < 1) return "Just now";
    if (minutes < 60) return `${minutes}m ago`;
    const hours = Math.floor(minutes / 60);
    if (hours < 24) return `${hours}h ago`;
    const days = Math.floor(hours / 24);
    return `${days}d ago`;
  };

  return (
    <Card
      className={cn("w-full", className)}
      data-testid={`agent-status-${agent.id}`}
    >
      <CardContent className={cn("p-4", compact && "p-3")}>
        <div className="flex items-start justify-between">
          {/* Agent info */}
          <div className="flex items-center gap-3">
            {/* Status indicator */}
            <div
              className={cn(
                "w-10 h-10 rounded-full flex items-center justify-center",
                config.bgColor
              )}
            >
              <div className={config.color}>{config.icon}</div>
            </div>

            <div>
              <div className="flex items-center gap-2">
                <h3 className="font-semibold">{agent.name}</h3>
                <Badge variant="outline" className="text-xs">
                  {variantLabels[agent.variant]}
                </Badge>
              </div>
              <div className="flex items-center gap-2 mt-1">
                <Badge
                  variant="secondary"
                  className={cn("text-xs", config.color)}
                >
                  {config.label}
                </Badge>
                <span className="text-xs text-muted-foreground">
                  <Clock className="h-3 w-3 inline mr-1" />
                  {formatRelativeTime(agent.lastActivity)}
                </span>
              </div>
            </div>
          </div>

          {/* Action buttons */}
          <div className="flex items-center gap-1">
            {isPaused ? (
              <Button
                variant="outline"
                size="sm"
                onClick={() => onResume?.(agent.id)}
                aria-label={`Resume agent ${agent.name}`}
              >
                <Play className="h-4 w-4 mr-1" />
                Resume
              </Button>
            ) : (
              <Button
                variant="outline"
                size="sm"
                onClick={() => onPause?.(agent.id)}
                disabled={!isActive}
                aria-label={`Pause agent ${agent.name}`}
              >
                <Pause className="h-4 w-4 mr-1" />
                Pause
              </Button>
            )}
            <Button
              variant="ghost"
              size="sm"
              onClick={() => onViewLogs?.(agent.id)}
              aria-label={`View logs for ${agent.name}`}
            >
              <FileText className="h-4 w-4" />
            </Button>
          </div>
        </div>

        {/* Current task */}
        {agent.currentTask && !compact && (
          <div className="mt-3 p-2 bg-muted/50 rounded-md">
            <span className="text-xs text-muted-foreground">Current task:</span>
            <p className="text-sm font-medium truncate">{agent.currentTask}</p>
          </div>
        )}

        {/* Performance metrics */}
        {!compact && (
          <div className="mt-4 grid grid-cols-4 gap-4">
            <div className="text-center">
              <div className="flex items-center justify-center gap-1 text-green-600">
                <Activity className="h-4 w-4" />
                <span className="text-lg font-semibold">
                  {agent.performance.accuracy}%
                </span>
              </div>
              <span className="text-xs text-muted-foreground">Accuracy</span>
            </div>
            <div className="text-center">
              <div className="flex items-center justify-center gap-1 text-blue-600">
                <Clock className="h-4 w-4" />
                <span className="text-lg font-semibold">
                  {agent.performance.avgResponseTime.toFixed(1)}s
                </span>
              </div>
              <span className="text-xs text-muted-foreground">Avg Time</span>
            </div>
            <div className="text-center">
              <div className="flex items-center justify-center gap-1 text-purple-600">
                <span className="text-lg font-semibold">
                  {agent.performance.ticketsHandled}
                </span>
              </div>
              <span className="text-xs text-muted-foreground">Handled</span>
            </div>
            <div className="text-center">
              <div className="flex items-center justify-center gap-1 text-orange-600">
                <span className="text-lg font-semibold">
                  {agent.performance.satisfactionScore}%
                </span>
              </div>
              <span className="text-xs text-muted-foreground">Satisfaction</span>
            </div>
          </div>
        )}

        {/* Uptime bar */}
        {!compact && (
          <div className="mt-4">
            <div className="flex items-center justify-between text-xs mb-1">
              <span className="text-muted-foreground">Uptime</span>
              <span className="font-medium">{agent.uptime}%</span>
            </div>
            <div className="h-2 bg-muted rounded-full overflow-hidden">
              <div
                className={cn(
                  "h-full rounded-full transition-all",
                  agent.uptime >= 99
                    ? "bg-green-500"
                    : agent.uptime >= 95
                    ? "bg-yellow-500"
                    : "bg-red-500"
                )}
                style={{ width: `${agent.uptime}%` }}
              />
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  );
}

export default AgentStatus;
