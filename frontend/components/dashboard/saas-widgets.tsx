/**
 * SaaS Dashboard Widgets - Week 32, Builder 5.
 * 
 * React components for SaaS analytics dashboard.
 */

'use client';

import React from 'react';

interface WidgetProps {
  loading?: boolean;
}

export function SubscriptionStatusWidget({ loading }: WidgetProps) {
  if (loading) {
    return <div className="animate-pulse bg-gray-200 rounded-lg h-32"></div>;
  }

  return (
    <div className="bg-white rounded-lg border p-4 shadow-sm">
      <h3 className="text-sm font-medium text-gray-500 mb-2">Subscription Status</h3>
      <div className="flex items-center justify-between">
        <span className="text-2xl font-bold text-green-600">Active</span>
        <span className="text-xs bg-green-100 text-green-700 px-2 py-1 rounded">PARWA High</span>
      </div>
      <p className="text-sm text-gray-500 mt-2">Renews: April 27, 2026</p>
    </div>
  );
}

export function UsageMetricsWidget({ loading }: WidgetProps) {
  if (loading) {
    return <div className="animate-pulse bg-gray-200 rounded-lg h-32"></div>;
  }

  const metrics = [
    { label: 'API Calls', value: '45,000', limit: '50,000', percent: 90 },
    { label: 'AI Interactions', value: '8,500', limit: '10,000', percent: 85 },
    { label: 'Voice Minutes', value: '450', limit: '500', percent: 90 },
    { label: 'Storage (GB)', value: '85', limit: '100', percent: 85 },
  ];

  return (
    <div className="bg-white rounded-lg border p-4 shadow-sm">
      <h3 className="text-sm font-medium text-gray-500 mb-2">Usage Metrics</h3>
      <div className="space-y-2">
        {metrics.map((m) => (
          <div key={m.label} className="flex items-center justify-between">
            <span className="text-sm">{m.label}</span>
            <span className="text-sm font-medium">
              {m.value} / {m.limit}
              <span className="text-xs text-gray-400 ml-2">({m.percent}%)</span>
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}

export function ChurnRiskWidget({ loading }: WidgetProps) {
  if (loading) {
    return <div className="animate-pulse bg-gray-200 rounded-lg h-32"></div>;
  }

  return (
    <div className="bg-white rounded-lg border p-4 shadow-sm">
      <h3 className="text-sm font-medium text-gray-500 mb-2">Churn Risk</h3>
      <div className="flex items-center gap-4">
        <div className="text-3xl font-bold text-green-600">Low</div>
        <div>
          <p className="text-sm text-gray-600">Risk Score: 15%</p>
          <p className="text-xs text-green-600">No immediate concerns</p>
        </div>
      </div>
    </div>
  );
}

export function FeatureRequestWidget({ loading }: WidgetProps) {
  if (loading) {
    return <div className="animate-pulse bg-gray-200 rounded-lg h-32"></div>;
  }

  const features = [
    { title: 'Advanced Analytics Dashboard', votes: 45, status: 'planned' },
    { title: 'API Rate Limit Override', votes: 32, status: 'submitted' },
    { title: 'Dark Mode Support', votes: 28, status: 'reviewing' },
  ];

  return (
    <div className="bg-white rounded-lg border p-4 shadow-sm">
      <h3 className="text-sm font-medium text-gray-500 mb-2">Top Feature Requests</h3>
      <div className="space-y-2">
        {features.map((f, i) => (
          <div key={i} className="flex items-center justify-between text-sm">
            <span className="truncate flex-1">{f.title}</span>
            <div className="flex items-center gap-2">
              <span className="text-xs text-gray-500">{f.votes} votes</span>
              <span className={`text-xs px-2 py-0.5 rounded ${
                f.status === 'planned' ? 'bg-blue-100 text-blue-700' :
                f.status === 'submitted' ? 'bg-gray-100 text-gray-700' :
                'bg-yellow-100 text-yellow-700'
              }`}>
                {f.status}
              </span>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

export function RevenueTrendWidget({ loading }: WidgetProps) {
  if (loading) {
    return <div className="animate-pulse bg-gray-200 rounded-lg h-48"></div>;
  }

  return (
    <div className="bg-white rounded-lg border p-4 shadow-sm">
      <h3 className="text-sm font-medium text-gray-500 mb-2">Revenue Trend</h3>
      <div className="grid grid-cols-2 gap-4 mb-4">
        <div>
          <p className="text-xs text-gray-500">MRR</p>
          <p className="text-2xl font-bold">$499</p>
        </div>
        <div>
          <p className="text-xs text-gray-500">ARR</p>
          <p className="text-2xl font-bold">$5,988</p>
        </div>
      </div>
      <div className="flex justify-between text-xs text-gray-500">
        <span>Growth: +12.5%</span>
        <span>Churn: 2.3%</span>
      </div>
    </div>
  );
}

export function HealthScoreWidget({ loading }: WidgetProps) {
  if (loading) {
    return <div className="animate-pulse bg-gray-200 rounded-lg h-32"></div>;
  }

  return (
    <div className="bg-white rounded-lg border p-4 shadow-sm">
      <h3 className="text-sm font-medium text-gray-500 mb-2">Account Health</h3>
      <div className="flex items-center gap-4">
        <div className="text-3xl font-bold text-green-600">85</div>
        <div>
          <p className="text-sm font-medium text-green-600">Good</p>
          <p className="text-xs text-gray-500">All metrics healthy</p>
        </div>
      </div>
    </div>
  );
}
