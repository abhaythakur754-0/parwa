"use client";

import { AlertTriangle } from "lucide-react";

interface DegradedDataBannerProps {
  integrationName?: string;
  dataAge?: string;
  error?: string;
  onDismiss?: () => void;
}

/**
 * DegradedDataBanner — Yellow warning banner for Phase 15.
 * Shows when live data is unavailable and cached fallback data is being used.
 */
export function DegradedDataBanner({
  integrationName,
  dataAge,
  error,
  onDismiss,
}: DegradedDataBannerProps) {
  return (
    <div className="bg-yellow-50 border-l-4 border-yellow-400 p-4 rounded-md">
      <div className="flex items-start">
        <div className="flex-shrink-0">
          <AlertTriangle className="h-5 w-5 text-yellow-400" />
        </div>
        <div className="ml-3 flex-1">
          <p className="text-sm text-yellow-700 font-medium">
            Live data temporarily unavailable
          </p>
          <p className="mt-1 text-sm text-yellow-600">
            {integrationName
              ? `${integrationName} is currently unavailable. `
              : "An external service is currently unavailable. "}
            {dataAge
              ? `Showing cached data from ${dataAge}.`
              : "Showing cached fallback data."}
          </p>
          {error && (
            <p className="mt-1 text-xs text-yellow-500">
              Technical details: {error}
            </p>
          )}
          <p className="mt-1 text-xs text-yellow-500">
            The system will automatically retry and restore live data when available.
          </p>
        </div>
        {onDismiss && (
          <div className="ml-auto pl-3">
            <button
              onClick={onDismiss}
              className="inline-flex rounded-md bg-yellow-50 p-1.5 text-yellow-500 hover:bg-yellow-100 focus:outline-none"
            >
              <span className="sr-only">Dismiss</span>
              <span className="text-lg">&times;</span>
            </button>
          </div>
        )}
      </div>
    </div>
  );
}

interface StructuredErrorResponse {
  success: false;
  error: string;
  message: string;
  integration_id?: string;
  is_retriable?: boolean;
  degraded?: boolean;
  data_age?: string;
  retry_attempts?: number;
  status_code?: number;
}

interface StructuredErrorHandlerProps {
  error: StructuredErrorResponse;
  onRetry?: () => void;
  onDismiss?: () => void;
}

/**
 * StructuredErrorHandler — Displays structured errors from the ExternalToolBus.
 */
export function StructuredErrorHandler({
  error,
  onRetry,
  onDismiss,
}: StructuredErrorHandlerProps) {
  const getStyle = () => {
    switch (error.error) {
      case "circuit_open":
        return { bg: "bg-red-50", border: "border-red-400", text: "text-red-700", subtext: "text-red-600", icon: "🔌" };
      case "auth_failed":
        return { bg: "bg-orange-50", border: "border-orange-400", text: "text-orange-700", subtext: "text-orange-600", icon: "🔑" };
      case "rate_limited":
        return { bg: "bg-yellow-50", border: "border-yellow-400", text: "text-yellow-700", subtext: "text-yellow-600", icon: "⏳" };
      case "external_api_down":
        return { bg: "bg-yellow-50", border: "border-yellow-400", text: "text-yellow-700", subtext: "text-yellow-600", icon: "⚠️" };
      default:
        return { bg: "bg-gray-50", border: "border-gray-400", text: "text-gray-700", subtext: "text-gray-600", icon: "❌" };
    }
  };

  const style = getStyle();

  const getSuggestion = () => {
    switch (error.error) {
      case "circuit_open":
        return "The circuit breaker is open due to repeated failures. Auto-recovery in 60 seconds.";
      case "auth_failed":
        return "The API key may have expired. Try rotating the key in Settings → Integrations.";
      case "rate_limited":
        return "The external service is rate-limiting requests. Please wait before trying again.";
      case "external_api_down":
        return "The external service appears to be down. Cached data is being used as fallback.";
      case "network_error":
        return "Could not connect to the external service. Check your network connection.";
      case "all_retries_failed":
        return `All ${error.retry_attempts} retry attempts failed. The system will try again shortly.`;
      default:
        return "An unexpected error occurred. Please try again.";
    }
  };

  return (
    <div className={`${style.bg} border-l-4 ${style.border} p-4 rounded-md`}>
      <div className="flex items-start">
        <span className="text-xl mr-3">{style.icon}</span>
        <div className="flex-1">
          <p className={`text-sm ${style.text} font-medium`}>{error.message || "An error occurred"}</p>
          <p className={`mt-1 text-sm ${style.subtext}`}>{getSuggestion()}</p>
          {error.degraded && (
            <p className="mt-1 text-xs text-yellow-600">Showing cached data from {error.data_age || "unknown time ago"}</p>
          )}
          {error.retry_attempts && error.retry_attempts > 0 && (
            <p className="mt-1 text-xs opacity-70">Retry attempts: {error.retry_attempts}</p>
          )}
        </div>
        <div className="ml-auto flex gap-2">
          {error.is_retriable && onRetry && (
            <button onClick={onRetry} className="inline-flex items-center px-3 py-1.5 text-xs font-medium rounded-md bg-white border border-gray-300 text-gray-700 hover:bg-gray-50">
              Retry
            </button>
          )}
          {onDismiss && (
            <button onClick={onDismiss} className="inline-flex items-center px-2 py-1 text-xs rounded-md opacity-50 hover:opacity-100">✕</button>
          )}
        </div>
      </div>
    </div>
  );
}
