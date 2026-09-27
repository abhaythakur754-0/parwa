/**
 * PARWA DashboardSkeleton
 *
 * Skeleton loading states for the dashboard page.
 * Uses the existing shadcn/ui Skeleton component to create
 * realistic content placeholders that match the dashboard layout.
 *
 * WCAG: Uses aria-busy, aria-label, and role="status" for
 * screen reader accessibility during loading states.
 */

'use client';

import React from 'react';
import { Skeleton } from '@/components/ui/skeleton';

// ── KPI Card Skeleton ────────────────────────────────────────────

export function KPICardSkeleton() {
  return (
    <div
      className="rounded-xl border border-white/[0.06] bg-white/[0.02] p-6 space-y-4"
      aria-busy="true"
      aria-label="Loading KPI data"
      role="status"
      data-testid="kpi-skeleton"
    >
      <div className="flex items-center justify-between">
        <Skeleton className="h-4 w-24" />
        <Skeleton className="h-8 w-8 rounded-lg" />
      </div>
      <Skeleton className="h-8 w-32" />
      <div className="flex items-center gap-2">
        <Skeleton className="h-3 w-16" />
        <Skeleton className="h-3 w-20" />
      </div>
    </div>
  );
}

// ── Chart Skeleton ───────────────────────────────────────────────

export function ChartSkeleton({ className }: { className?: string }) {
  return (
    <div
      className={`rounded-xl border border-white/[0.06] bg-white/[0.02] p-6 space-y-4 ${className || ''}`}
      aria-busy="true"
      aria-label="Loading chart"
      role="status"
      data-testid="chart-skeleton"
    >
      <div className="flex items-center justify-between">
        <Skeleton className="h-5 w-36" />
        <Skeleton className="h-8 w-8 rounded" />
      </div>
      <div className="flex items-end gap-1 h-48">
        {Array.from({ length: 12 }).map((_, i) => (
          <Skeleton
            key={i}
            className="flex-1 rounded-t"
            style={{ height: `${30 + Math.random() * 70}%` }}
          />
        ))}
      </div>
      <div className="flex justify-between">
        <Skeleton className="h-3 w-12" />
        <Skeleton className="h-3 w-12" />
        <Skeleton className="h-3 w-12" />
      </div>
    </div>
  );
}

// ── Table Skeleton ───────────────────────────────────────────────

export function TableSkeleton({ rows = 5 }: { rows?: number }) {
  return (
    <div
      className="rounded-xl border border-white/[0.06] bg-white/[0.02] p-6 space-y-4"
      aria-busy="true"
      aria-label="Loading table data"
      role="status"
      data-testid="table-skeleton"
    >
      <div className="flex items-center justify-between">
        <Skeleton className="h-5 w-48" />
        <Skeleton className="h-8 w-24 rounded-lg" />
      </div>
      {/* Header */}
      <div className="flex gap-4 py-3 border-b border-white/[0.06]">
        <Skeleton className="h-4 w-20" />
        <Skeleton className="h-4 w-24" />
        <Skeleton className="h-4 w-16" />
        <Skeleton className="h-4 w-20" />
        <Skeleton className="h-4 w-16" />
      </div>
      {/* Rows */}
      {Array.from({ length: rows }).map((_, i) => (
        <div key={i} className="flex gap-4 py-2">
          <Skeleton className="h-4 w-20" />
          <Skeleton className="h-4 w-24" />
          <Skeleton className="h-4 w-16" />
          <Skeleton className="h-4 w-20" />
          <Skeleton className="h-4 w-16" />
        </div>
      ))}
    </div>
  );
}

// ── Full Dashboard Skeleton ──────────────────────────────────────

export function DashboardSkeleton() {
  return (
    <div
      className="space-y-6"
      aria-busy="true"
      aria-label="Loading dashboard"
      role="status"
      data-testid="dashboard-skeleton"
    >
      {/* Welcome header */}
      <div className="space-y-2">
        <Skeleton className="h-8 w-64" />
        <Skeleton className="h-4 w-96" />
      </div>

      {/* KPI Row */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <KPICardSkeleton />
        <KPICardSkeleton />
        <KPICardSkeleton />
        <KPICardSkeleton />
      </div>

      {/* Charts Row */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <ChartSkeleton />
        <ChartSkeleton />
      </div>

      {/* Table */}
      <TableSkeleton rows={6} />

      {/* Screen reader announcement */}
      <span className="sr-only">Dashboard content is loading, please wait.</span>
    </div>
  );
}

export default DashboardSkeleton;
