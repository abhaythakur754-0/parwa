"use client";

import { useState, useEffect } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Alert, AlertDescription } from "@/components/ui/alert";
import {
  Activity,
  CheckCircle2,
  AlertTriangle,
  XCircle,
  RefreshCw,
  Loader2,
  Shield,
} from "lucide-react";

interface IntegrationHealth {
  integration_id: string;
  integration_name: string;
  status: string;
  last_tested_at: string | null;
  circuit_breaker: string;
  rate_limit: string;
}

interface HealthData {
  integrations: IntegrationHealth[];
  total: number;
  healthy: number;
  unhealthy: number;
}

export function IntegrationHealthDashboard() {
  const [health, setHealth] = useState<HealthData | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);

  useEffect(() => {
    loadHealth();
  }, []);

  const loadHealth = async () => {
    try {
      const res = await fetch("/api/integrations/health");
      if (res.ok) {
        const data = await res.json();
        setHealth(data);
      }
    } catch {
      // Error handled silently
    } finally {
      setLoading(false);
    }
  };

  const handleRefresh = async () => {
    setRefreshing(true);
    await loadHealth();
    setRefreshing(false);
  };

  const getOverallBadge = () => {
    if (!health || health.total === 0) return { label: "No Integrations", variant: "secondary" as const, icon: Activity };
    if (health.unhealthy === 0) return { label: "Healthy", variant: "default" as const, icon: CheckCircle2 };
    if (health.healthy > health.unhealthy) return { label: "Degraded", variant: "secondary" as const, icon: AlertTriangle };
    return { label: "Unhealthy", variant: "destructive" as const, icon: XCircle };
  };

  const getStatusIcon = (status: string) => {
    switch (status) {
      case "active": return <CheckCircle2 className="h-4 w-4 text-emerald-500" />;
      case "error": return <XCircle className="h-4 w-4 text-destructive" />;
      case "disconnected": return <AlertTriangle className="h-4 w-4 text-amber-500" />;
      default: return <Activity className="h-4 w-4 text-muted-foreground" />;
    }
  };

  const getCircuitBreakerBadge = (state: string) => {
    switch (state) {
      case "closed": return <Badge variant="default" className="text-[10px] bg-emerald-500">Closed (Healthy)</Badge>;
      case "open": return <Badge variant="destructive" className="text-[10px]">Open (Failing)</Badge>;
      case "half-open": return <Badge variant="secondary" className="text-[10px]">Half-Open (Testing)</Badge>;
      default: return <Badge variant="secondary" className="text-[10px]">{state}</Badge>;
    }
  };

  if (loading) {
    return (
      <Card>
        <CardContent className="p-6 flex items-center justify-center">
          <Loader2 className="h-5 w-5 animate-spin text-emerald-500" />
        </CardContent>
      </Card>
    );
  }

  const overall = getOverallBadge();
  const OverallIcon = overall.icon;

  return (
    <div className="space-y-4">
      {/* Overall Health */}
      <Card>
        <CardHeader className="flex flex-row items-center justify-between pb-2">
          <CardTitle className="text-base flex items-center gap-2">
            <Activity className="h-4 w-4" />
            Integration Health
          </CardTitle>
          <div className="flex items-center gap-2">
            <OverallIcon className="h-4 w-4" />
            <Badge variant={overall.variant} className="text-xs">{overall.label}</Badge>
            <Button variant="ghost" size="sm" className="h-7 w-7 p-0" onClick={handleRefresh}>
              <RefreshCw className={`h-3.5 w-3.5 ${refreshing ? "animate-spin" : ""}`} />
            </Button>
          </div>
        </CardHeader>
        <CardContent>
          {health && health.total > 0 ? (
            <div className="flex gap-4 text-sm">
              <span className="text-emerald-600 font-medium">{health.healthy} healthy</span>
              <span className="text-destructive font-medium">{health.unhealthy} unhealthy</span>
              <span className="text-muted-foreground">{health.total} total</span>
            </div>
          ) : (
            <p className="text-sm text-muted-foreground">No integrations connected yet.</p>
          )}
        </CardContent>
      </Card>

      {/* Per-Integration Health */}
      {health && health.integrations.length > 0 && (
        <div className="space-y-2">
          {health.integrations.map((ih) => (
            <Card key={ih.integration_id}>
              <CardContent className="p-3">
                <div className="flex items-center justify-between mb-2">
                  <div className="flex items-center gap-2">
                    {getStatusIcon(ih.status)}
                    <span className="text-sm font-medium">{ih.integration_name}</span>
                  </div>
                  {ih.status === "error" && (
                    <Alert variant="destructive" className="py-1 px-2 text-xs">
                      <AlertDescription className="text-xs flex items-center gap-1">
                        <Shield className="h-3 w-3" />
                        Key may need rotation
                      </AlertDescription>
                    </Alert>
                  )}
                </div>
                <div className="flex items-center gap-3 text-xs">
                  {getCircuitBreakerBadge(ih.circuit_breaker)}
                  <Badge variant="outline" className="text-[10px]">
                    Rate limit: {ih.rate_limit}
                  </Badge>
                  {ih.last_tested_at && (
                    <span className="text-muted-foreground">
                      Last tested: {new Date(ih.last_tested_at).toLocaleDateString()}
                    </span>
                  )}
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}
