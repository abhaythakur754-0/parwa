'use client';

import React from 'react';
import { Card, CardContent } from '@/components/ui/card';
import { Skeleton } from '@/components/ui/skeleton';

/**
 * TrainingDashboardSkeleton
 * 
 * Loading skeleton for the training dashboard.
 * Provides visual feedback while data is loading.
 */
export function TrainingDashboardSkeleton() {
  return (
    <div className="min-h-screen bg-[#0D0D0D] text-white p-6">
      <div className="max-w-7xl mx-auto space-y-6">
        {/* Header Skeleton */}
        <div className="flex items-center justify-between">
          <div>
            <Skeleton className="h-9 w-48 bg-white/10" />
            <Skeleton className="h-5 w-64 bg-white/5 mt-2" />
          </div>
          <div className="flex gap-3">
            <Skeleton className="h-10 w-32 bg-white/10" />
            <Skeleton className="h-10 w-36 bg-orange-500/20" />
          </div>
        </div>

        {/* Stats Cards Skeleton */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-5 gap-4">
          {Array.from({ length: 5 }).map((_, i) => (
            <Card key={i} className="bg-[#1A1A1A] border-white/[0.08]">
              <CardContent className="p-4">
                <div className="flex items-center gap-3">
                  <Skeleton className="w-10 h-10 rounded-lg bg-white/10" />
                  <div>
                    <Skeleton className="h-7 w-12 bg-white/10" />
                    <Skeleton className="h-3 w-16 bg-white/5 mt-1" />
                  </div>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>

        {/* Tabs Skeleton */}
        <div className="space-y-6">
          <div className="flex gap-2">
            {Array.from({ length: 4 }).map((_, i) => (
              <Skeleton key={i} className="h-10 w-32 bg-white/10 rounded-lg" />
            ))}
          </div>

          {/* Content Cards Skeleton */}
          <div className="space-y-4">
            {Array.from({ length: 3 }).map((_, i) => (
              <Card key={i} className="bg-[#1A1A1A] border-white/[0.08]">
                <CardContent className="p-5">
                  <div className="flex items-start justify-between mb-4">
                    <div className="flex items-center gap-3">
                      <Skeleton className="w-10 h-10 rounded-lg bg-white/10" />
                      <div>
                        <Skeleton className="h-5 w-48 bg-white/10" />
                        <div className="flex gap-2 mt-2">
                          <Skeleton className="h-5 w-16 bg-white/5 rounded-full" />
                          <Skeleton className="h-5 w-20 bg-white/5 rounded-full" />
                        </div>
                      </div>
                    </div>
                    <Skeleton className="h-6 w-20 bg-white/10 rounded-full" />
                  </div>
                  
                  <Skeleton className="h-2 w-full bg-white/5 mb-4" />
                  
                  <div className="grid grid-cols-4 gap-4">
                    {Array.from({ length: 4 }).map((_, j) => (
                      <div key={j} className="bg-white/[0.03] rounded-lg p-3">
                        <Skeleton className="h-3 w-16 bg-white/5" />
                        <Skeleton className="h-6 w-12 bg-white/10 mt-1" />
                      </div>
                    ))}
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}

/**
 * TrainingRunCardSkeleton
 * 
 * Loading skeleton for a single training run card.
 */
export function TrainingRunCardSkeleton() {
  return (
    <Card className="bg-[#1A1A1A] border-white/[0.08]">
      <CardContent className="p-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <Skeleton className="w-8 h-8 rounded-lg bg-white/10" />
            <div>
              <Skeleton className="h-4 w-32 bg-white/10" />
              <Skeleton className="h-3 w-48 bg-white/5 mt-1" />
            </div>
          </div>
          <div className="flex items-center gap-4">
            <div className="text-right">
              <Skeleton className="h-4 w-16 bg-white/10" />
              <Skeleton className="h-3 w-10 bg-white/5 mt-1" />
            </div>
            <Skeleton className="h-1.5 w-16 bg-white/5 rounded-full" />
          </div>
        </div>
      </CardContent>
    </Card>
  );
}

/**
 * ColdStartCardSkeleton
 * 
 * Loading skeleton for cold start components.
 */
export function ColdStartCardSkeleton() {
  return (
    <Card className="bg-[#1A1A1A] border-white/[0.08]">
      <CardContent className="p-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <Skeleton className="w-10 h-10 rounded-lg bg-purple-500/20" />
            <div>
              <Skeleton className="h-4 w-48 bg-white/10" />
              <Skeleton className="h-3 w-32 bg-white/5 mt-1" />
            </div>
          </div>
          <Skeleton className="h-9 w-28 bg-purple-500/20" />
        </div>
      </CardContent>
    </Card>
  );
}

/**
 * RetrainingSkeleton
 * 
 * Loading skeleton for retraining schedule.
 */
export function RetrainingSkeleton() {
  return (
    <div className="space-y-4">
      <Card className="bg-[#1A1A1A] border-white/[0.08]">
        <CardContent className="p-4">
          <div className="grid grid-cols-2 gap-4">
            {Array.from({ length: 2 }).map((_, i) => (
              <div key={i} className="flex items-center gap-3">
                <Skeleton className="w-10 h-10 rounded-lg bg-white/10" />
                <div>
                  <Skeleton className="h-3 w-16 bg-white/5" />
                  <Skeleton className="h-6 w-12 bg-white/10 mt-1" />
                </div>
              </div>
            ))}
          </div>
        </CardContent>
      </Card>
      
      {Array.from({ length: 3 }).map((_, i) => (
        <Card key={i} className="bg-[#1A1A1A] border-white/[0.08]">
          <CardContent className="p-3">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-3">
                <Skeleton className="w-8 h-8 rounded-lg bg-white/10" />
                <div>
                  <Skeleton className="h-4 w-32 bg-white/10" />
                  <Skeleton className="h-3 w-24 bg-white/5 mt-1" />
                </div>
              </div>
              <Skeleton className="h-5 w-16 bg-white/10 rounded-full" />
            </div>
          </CardContent>
        </Card>
      ))}
    </div>
  );
}

export default TrainingDashboardSkeleton;
