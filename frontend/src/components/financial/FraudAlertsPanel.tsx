"use client";

/**
 * Fraud Alerts Panel Component
 *
 * Displays active fraud alerts with:
 * - Alert severity indicators
 * - Quick actions (escalate, resolve)
 * - Alert history
 */

import { useState } from "react";

interface FraudAlert {
  id: string;
  risk_level: "low" | "medium" | "high" | "critical";
  customer_id: string;
  description: string;
  detected_at: string;
  status: "pending" | "investigating" | "resolved";
}

interface FraudAlertsPanelProps {
  alerts?: FraudAlert[];
  onEscalate?: (alertId: string) => void;
  onResolve?: (alertId: string) => void;
}

export function FraudAlertsPanel({
  alerts = [],
  onEscalate,
  onResolve,
}: FraudAlertsPanelProps) {
  const [selectedAlert, setSelectedAlert] = useState<string | null>(null);

  const getRiskBadgeClass = (level: string) => {
    switch (level) {
      case "critical":
        return "bg-red-100 text-red-800 border-red-200";
      case "high":
        return "bg-orange-100 text-orange-800 border-orange-200";
      case "medium":
        return "bg-yellow-100 text-yellow-800 border-yellow-200";
      default:
        return "bg-green-100 text-green-800 border-green-200";
    }
  };

  const getStatusBadgeClass = (status: string) => {
    switch (status) {
      case "pending":
        return "bg-yellow-100 text-yellow-800";
      case "investigating":
        return "bg-blue-100 text-blue-800";
      case "resolved":
        return "bg-green-100 text-green-800";
      default:
        return "bg-gray-100 text-gray-800";
    }
  };

  return (
    <div className="bg-white rounded-lg shadow p-4">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-lg font-semibold">Fraud Alerts</h3>
        <span className="text-sm text-gray-500">
          {alerts.length} active
        </span>
      </div>

      {alerts.length === 0 ? (
        <div className="text-center py-8 text-gray-500">
          <svg
            className="mx-auto h-12 w-12 text-gray-400"
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"
            />
          </svg>
          <p className="mt-2">No active fraud alerts</p>
        </div>
      ) : (
        <div className="space-y-3">
          {alerts.map((alert) => (
            <div
              key={alert.id}
              className={`p-3 border rounded-lg cursor-pointer transition-colors ${
                selectedAlert === alert.id ? "border-blue-500 bg-blue-50" : ""
              }`}
              onClick={() => setSelectedAlert(
                selectedAlert === alert.id ? null : alert.id
              )}
            >
              <div className="flex items-center justify-between">
                <div className="flex items-center space-x-2">
                  <span className={`px-2 py-1 text-xs rounded border ${getRiskBadgeClass(alert.risk_level)}`}>
                    {alert.risk_level.toUpperCase()}
                  </span>
                  <span className={`px-2 py-1 text-xs rounded ${getStatusBadgeClass(alert.status)}`}>
                    {alert.status}
                  </span>
                </div>
                <span className="text-xs text-gray-500">
                  {new Date(alert.detected_at).toLocaleDateString()}
                </span>
              </div>

              <p className="mt-2 text-sm text-gray-700">{alert.description}</p>

              {selectedAlert === alert.id && (
                <div className="mt-3 flex space-x-2">
                  <button
                    className="px-3 py-1 text-sm bg-orange-100 text-orange-800 rounded hover:bg-orange-200"
                    onClick={(e) => {
                      e.stopPropagation();
                      onEscalate?.(alert.id);
                    }}
                  >
                    Escalate
                  </button>
                  <button
                    className="px-3 py-1 text-sm bg-green-100 text-green-800 rounded hover:bg-green-200"
                    onClick={(e) => {
                      e.stopPropagation();
                      onResolve?.(alert.id);
                    }}
                  >
                    Resolve
                  </button>
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
