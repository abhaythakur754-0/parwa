'use client';

import { useEffect, useState } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';

interface WidgetProps {
  className?: string;
}

// Recommendation Performance Widget
export function RecommendationPerformanceWidget({ className }: WidgetProps) {
  const [data, setData] = useState({
    recommendationsShown: 0,
    clickRate: 0,
    purchaseRate: 0,
    revenueFromRecommendations: 0,
  });
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchData = async () => {
      try {
        const response = await fetch('/api/ecommerce/analytics/recommendations');
        if (response.ok) {
          const result = await response.json();
          setData(result);
        }
      } catch (error) {
        console.error('Failed to fetch recommendation data:', error);
      } finally {
        setLoading(false);
      }
    };

    fetchData();
  }, []);

  if (loading) {
    return (
      <Card className={className}>
        <CardHeader>
          <CardTitle className="text-lg">Recommendation Performance</CardTitle>
        </CardHeader>
        <CardContent className="flex items-center justify-center h-32">
          <div className="animate-spin rounded-full h-6 w-6 border-b-2 border-primary"></div>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card className={className}>
      <CardHeader>
        <CardTitle className="text-lg">Recommendation Performance</CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="flex justify-between">
          <span className="text-muted-foreground">Recommendations Shown</span>
          <span className="font-medium">{data.recommendationsShown.toLocaleString()}</span>
        </div>
        <div className="flex justify-between">
          <span className="text-muted-foreground">Click Rate</span>
          <span className="font-medium">{(data.clickRate * 100).toFixed(1)}%</span>
        </div>
        <div className="flex justify-between">
          <span className="text-muted-foreground">Purchase Rate</span>
          <span className="font-medium">{(data.purchaseRate * 100).toFixed(1)}%</span>
        </div>
        <div className="flex justify-between">
          <span className="text-muted-foreground">Revenue from Recs</span>
          <span className="font-medium text-green-600">
            ${data.revenueFromRecommendations.toLocaleString()}
          </span>
        </div>
      </CardContent>
    </Card>
  );
}

// Cart Recovery Widget
export function CartRecoveryWidget({ className }: WidgetProps) {
  const [data, setData] = useState({
    totalAbandoned: 0,
    recovered: 0,
    recoveryRate: 0,
    revenueRecovered: 0,
  });
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchData = async () => {
      try {
        const response = await fetch('/api/ecommerce/analytics/cart-recovery');
        if (response.ok) {
          const result = await response.json();
          setData(result);
        }
      } catch (error) {
        console.error('Failed to fetch cart recovery data:', error);
      } finally {
        setLoading(false);
      }
    };

    fetchData();
  }, []);

  if (loading) {
    return (
      <Card className={className}>
        <CardHeader>
          <CardTitle className="text-lg">Cart Recovery</CardTitle>
        </CardHeader>
        <CardContent className="flex items-center justify-center h-32">
          <div className="animate-spin rounded-full h-6 w-6 border-b-2 border-primary"></div>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card className={className}>
      <CardHeader>
        <CardTitle className="text-lg">Cart Recovery</CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="flex justify-between">
          <span className="text-muted-foreground">Abandoned Carts</span>
          <span className="font-medium">{data.totalAbandoned}</span>
        </div>
        <div className="flex justify-between">
          <span className="text-muted-foreground">Recovered</span>
          <span className="font-medium text-green-600">{data.recovered}</span>
        </div>
        <div className="flex justify-between">
          <span className="text-muted-foreground">Recovery Rate</span>
          <span className="font-medium">{(data.recoveryRate * 100).toFixed(1)}%</span>
        </div>
        <div className="flex justify-between">
          <span className="text-muted-foreground">Revenue Recovered</span>
          <span className="font-medium text-green-600">
            ${data.revenueRecovered.toLocaleString()}
          </span>
        </div>
      </CardContent>
    </Card>
  );
}

// Pricing Alerts Widget
export function PricingAlertsWidget({ className }: WidgetProps) {
  const [alerts, setAlerts] = useState<Array<{
    productId: string;
    productName: string;
    alertType: string;
    priceChange: number;
  }>>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchData = async () => {
      try {
        const response = await fetch('/api/ecommerce/pricing/alerts');
        if (response.ok) {
          const result = await response.json();
          setAlerts(result.alerts || []);
        }
      } catch (error) {
        console.error('Failed to fetch pricing alerts:', error);
      } finally {
        setLoading(false);
      }
    };

    fetchData();
  }, []);

  if (loading) {
    return (
      <Card className={className}>
        <CardHeader>
          <CardTitle className="text-lg">Pricing Alerts</CardTitle>
        </CardHeader>
        <CardContent className="flex items-center justify-center h-32">
          <div className="animate-spin rounded-full h-6 w-6 border-b-2 border-primary"></div>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card className={className}>
      <CardHeader>
        <CardTitle className="text-lg">Pricing Alerts</CardTitle>
      </CardHeader>
      <CardContent>
        {alerts.length === 0 ? (
          <p className="text-muted-foreground text-sm">No active alerts</p>
        ) : (
          <div className="space-y-2">
            {alerts.slice(0, 5).map((alert, index) => (
              <div key={index} className="flex justify-between items-center py-2 border-b">
                <div>
                  <p className="font-medium text-sm">{alert.productName}</p>
                  <p className="text-xs text-muted-foreground">{alert.alertType}</p>
                </div>
                <span
                  className={`text-sm font-medium ${
                    alert.priceChange > 0 ? 'text-red-600' : 'text-green-600'
                  }`}
                >
                  {alert.priceChange > 0 ? '+' : ''}
                  {alert.priceChange}%
                </span>
              </div>
            ))}
          </div>
        )}
      </CardContent>
    </Card>
  );
}

// Order Tracking Widget
export function OrderTrackingWidget({ className }: WidgetProps) {
  const [stats, setStats] = useState({
    pendingOrders: 0,
    inTransit: 0,
    delivered: 0,
    exceptions: 0,
  });
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchData = async () => {
      try {
        const response = await fetch('/api/ecommerce/orders/tracking-stats');
        if (response.ok) {
          const result = await response.json();
          setStats(result);
        }
      } catch (error) {
        console.error('Failed to fetch tracking stats:', error);
      } finally {
        setLoading(false);
      }
    };

    fetchData();
  }, []);

  if (loading) {
    return (
      <Card className={className}>
        <CardHeader>
          <CardTitle className="text-lg">Order Tracking</CardTitle>
        </CardHeader>
        <CardContent className="flex items-center justify-center h-32">
          <div className="animate-spin rounded-full h-6 w-6 border-b-2 border-primary"></div>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card className={className}>
      <CardHeader>
        <CardTitle className="text-lg">Order Tracking</CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="flex justify-between">
          <span className="text-muted-foreground">Pending</span>
          <span className="font-medium">{stats.pendingOrders}</span>
        </div>
        <div className="flex justify-between">
          <span className="text-muted-foreground">In Transit</span>
          <span className="font-medium">{stats.inTransit}</span>
        </div>
        <div className="flex justify-between">
          <span className="text-muted-foreground">Delivered</span>
          <span className="font-medium text-green-600">{stats.delivered}</span>
        </div>
        <div className="flex justify-between">
          <span className="text-muted-foreground">Exceptions</span>
          <span className="font-medium text-red-600">{stats.exceptions}</span>
        </div>
      </CardContent>
    </Card>
  );
}

// Revenue Trend Widget
export function RevenueTrendWidget({ className }: WidgetProps) {
  const [data, setData] = useState<Array<{ date: string; revenue: number }>>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchData = async () => {
      try {
        const response = await fetch('/api/ecommerce/analytics/revenue-trend');
        if (response.ok) {
          const result = await response.json();
          setData(result);
        }
      } catch (error) {
        console.error('Failed to fetch revenue trend:', error);
      } finally {
        setLoading(false);
      }
    };

    fetchData();
  }, []);

  if (loading) {
    return (
      <Card className={className}>
        <CardHeader>
          <CardTitle className="text-lg">Revenue Trend</CardTitle>
        </CardHeader>
        <CardContent className="flex items-center justify-center h-48">
          <div className="animate-spin rounded-full h-6 w-6 border-b-2 border-primary"></div>
        </CardContent>
      </Card>
    );
  }

  const maxRevenue = Math.max(...data.map((d) => d.revenue), 1);

  return (
    <Card className={className}>
      <CardHeader>
        <CardTitle className="text-lg">Revenue Trend</CardTitle>
      </CardHeader>
      <CardContent>
        <div className="flex items-end gap-2 h-48">
          {data.slice(-14).map((point, index) => (
            <div
              key={index}
              className="flex-1 bg-primary rounded-t"
              style={{
                height: `${(point.revenue / maxRevenue) * 100}%`,
                minHeight: '4px',
              }}
              title={`${point.date}: $${point.revenue.toLocaleString()}`}
            />
          ))}
        </div>
        <div className="flex justify-between mt-2 text-xs text-muted-foreground">
          <span>{data[0]?.date || '-'}</span>
          <span>{data[data.length - 1]?.date || '-'}</span>
        </div>
      </CardContent>
    </Card>
  );
}
