'use client';

import { useEffect, useState } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import {
  RecommendationPerformanceWidget,
  CartRecoveryWidget,
  PricingAlertsWidget,
  OrderTrackingWidget,
  RevenueTrendWidget,
} from '@/components/dashboard/ecommerce-widgets';

export default function EcommerceDashboardPage() {
  const [loading, setLoading] = useState(true);
  const [summary, setSummary] = useState({
    totalRevenue: 0,
    totalOrders: 0,
    conversionRate: 0,
    cartAbandonmentRate: 0,
  });

  useEffect(() => {
    // Fetch dashboard data
    const fetchData = async () => {
      try {
        const response = await fetch('/api/ecommerce/analytics/summary');
        if (response.ok) {
          const data = await response.json();
          setSummary(data);
        }
      } catch (error) {
        console.error('Failed to fetch analytics:', error);
      } finally {
        setLoading(false);
      }
    };

    fetchData();
  }, []);

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary"></div>
      </div>
    );
  }

  return (
    <div className="container mx-auto py-6 space-y-6">
      <div className="flex justify-between items-center">
        <h1 className="text-3xl font-bold">E-commerce Analytics</h1>
        <span className="text-sm text-muted-foreground">
          Last updated: {new Date().toLocaleString()}
        </span>
      </div>

      {/* Summary Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">
              Total Revenue
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">
              ${summary.totalRevenue.toLocaleString()}
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">
              Total Orders
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{summary.totalOrders}</div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">
              Conversion Rate
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">
              {(summary.conversionRate * 100).toFixed(1)}%
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">
              Cart Abandonment
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">
              {(summary.cartAbandonmentRate * 100).toFixed(1)}%
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Widgets */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <RevenueTrendWidget />
        <CartRecoveryWidget />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <RecommendationPerformanceWidget />
        <PricingAlertsWidget />
        <OrderTrackingWidget />
      </div>
    </div>
  );
}
