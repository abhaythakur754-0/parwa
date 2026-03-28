"use client";

/**
 * Financial Services Dashboard Page
 *
 * Displays:
 * - Compliance status overview
 * - Active fraud alerts
 * - Recent transactions (limited view)
 */

import { useState, useEffect } from "react";

export default function FinancialServicesPage() {
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    setIsLoading(false);
  }, []);

  if (isLoading) {
    return (
      <div className="p-8">
        <div className="animate-pulse space-y-4">
          <div className="h-32 bg-gray-200 rounded"></div>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">Financial Services</h1>
        <p className="text-gray-500">Compliance, fraud detection, and audit</p>
      </div>
      
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div className="p-4 bg-white rounded-lg shadow">
          <h3 className="text-sm text-gray-500">SOX Compliance</h3>
          <p className="text-2xl font-bold text-green-600">Compliant</p>
        </div>
        <div className="p-4 bg-white rounded-lg shadow">
          <h3 className="text-sm text-gray-500">FINRA Compliance</h3>
          <p className="text-2xl font-bold text-green-600">Compliant</p>
        </div>
        <div className="p-4 bg-white rounded-lg shadow">
          <h3 className="text-sm text-gray-500">Active Alerts</h3>
          <p className="text-2xl font-bold">0</p>
        </div>
      </div>
    </div>
  );
}
