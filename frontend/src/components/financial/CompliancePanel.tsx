"use client";

/**
 * Compliance Panel Component
 *
 * Displays real-time compliance status with:
 * - Violation count
 * - Recent compliance events
 * - Audit trail access
 */

import { useState, useEffect } from "react";

interface ComplianceData {
  sox: {
    compliant: boolean;
    violations: number;
    last_check: string;
  };
  finra: {
    compliant: boolean;
    violations: number;
    last_check: string;
  };
  overall_status: string;
}

export function CompliancePanel() {
  const [data, setData] = useState<ComplianceData | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    // Simulate loading
    setIsLoading(false);
    setData({
      sox: { compliant: true, violations: 0, last_check: new Date().toISOString() },
      finra: { compliant: true, violations: 0, last_check: new Date().toISOString() },
      overall_status: "compliant",
    });
  }, []);

  if (isLoading) {
    return (
      <div className="p-4 bg-white rounded-lg shadow animate-pulse">
        <div className="h-4 bg-gray-200 rounded w-1/4 mb-4"></div>
        <div className="h-8 bg-gray-200 rounded w-1/2"></div>
      </div>
    );
  }

  const getStatusColor = (compliant: boolean) => {
    return compliant ? "bg-green-500" : "bg-red-500";
  };

  return (
    <div className="bg-white rounded-lg shadow p-4">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-lg font-semibold">Compliance Status</h3>
        <span className={`px-2 py-1 text-xs rounded ${
          data?.overall_status === "compliant"
            ? "bg-green-100 text-green-800"
            : "bg-red-100 text-red-800"
        }`}>
          {data?.overall_status?.toUpperCase()}
        </span>
      </div>

      <div className="space-y-4">
        {/* SOX Status */}
        <div className="flex items-center justify-between p-3 bg-gray-50 rounded">
          <div className="flex items-center">
            <span className={`w-3 h-3 rounded-full ${getStatusColor(data?.sox.compliant || false)} mr-3`}></span>
            <span className="font-medium">SOX</span>
          </div>
          <div className="text-sm text-gray-500">
            {data?.sox.violations || 0} violations
          </div>
        </div>

        {/* FINRA Status */}
        <div className="flex items-center justify-between p-3 bg-gray-50 rounded">
          <div className="flex items-center">
            <span className={`w-3 h-3 rounded-full ${getStatusColor(data?.finra.compliant || false)} mr-3`}></span>
            <span className="font-medium">FINRA</span>
          </div>
          <div className="text-sm text-gray-500">
            {data?.finra.violations || 0} violations
          </div>
        </div>
      </div>

      {/* Last Check */}
      <div className="mt-4 text-xs text-gray-400">
        Last check: {data?.sox.last_check
          ? new Date(data.sox.last_check).toLocaleString()
          : "N/A"}
      </div>
    </div>
  );
}
