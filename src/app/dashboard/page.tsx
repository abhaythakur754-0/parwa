"use client";

import { useEffect, useState } from "react";
import { useAuthStore } from "@/store/auth-store";
import { OverviewCards } from "@/components/dashboard/OverviewCards";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import Link from "next/link";
import {
  Bot,
  ArrowRight,
  Plug,
  Upload,
  Settings2,
  Activity,
} from "lucide-react";

interface RecentActivity {
  id: string;
  action: string;
  severity: string;
  created_at: string;
}

export default function DashboardPage() {
  const { user } = useAuthStore();
  const [recentActivity, setRecentActivity] = useState<RecentActivity[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    loadRecentActivity();
  }, []);

  const loadRecentActivity = async () => {
    try {
      const res = await fetch("/api/audit/entries?limit=5");
      if (res.ok) {
        const data = await res.json();
        setRecentActivity(data.entries || []);
      }
    } catch {
      // Error handled silently
    } finally {
      setLoading(false);
    }
  };

  const quickActions = [
    { label: "Connect Integration", icon: Plug, href: "/dashboard/settings" },
    { label: "Upload Documents", icon: Upload, href: "/dashboard/settings" },
    { label: "Configure AI", icon: Settings2, href: "/dashboard/settings" },
    { label: "View Audit Log", icon: Activity, href: "/dashboard/settings" },
  ];

  return (
    <div className="space-y-6">
      {/* Welcome Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold">
            Welcome back, {user?.name || "User"}
          </h1>
          <p className="text-muted-foreground">
            Here&apos;s what&apos;s happening with your PARWA workspace.
          </p>
        </div>
        <Link href="/dashboard/settings">
          <Button className="bg-gradient-to-r from-emerald-500 to-teal-600 text-white">
            <Settings2 className="h-4 w-4 mr-2" />
            Settings
          </Button>
        </Link>
      </div>

      {/* Overview Cards */}
      <OverviewCards />

      <div className="grid lg:grid-cols-2 gap-6">
        {/* Quick Actions */}
        <Card>
          <CardHeader>
            <CardTitle className="text-lg">Quick Actions</CardTitle>
          </CardHeader>
          <CardContent className="space-y-2">
            {quickActions.map((action) => (
              <Link key={action.label} href={action.href}>
                <div className="flex items-center justify-between p-3 rounded-lg hover:bg-muted transition-colors">
                  <div className="flex items-center gap-3">
                    <div className="h-8 w-8 rounded-lg bg-muted flex items-center justify-center">
                      <action.icon className="h-4 w-4 text-muted-foreground" />
                    </div>
                    <span className="text-sm font-medium">{action.label}</span>
                  </div>
                  <ArrowRight className="h-4 w-4 text-muted-foreground" />
                </div>
              </Link>
            ))}
          </CardContent>
        </Card>

        {/* Recent Activity */}
        <Card>
          <CardHeader>
            <CardTitle className="text-lg">Recent Activity</CardTitle>
          </CardHeader>
          <CardContent>
            {loading ? (
              <div className="flex items-center justify-center py-8">
                <div className="h-5 w-5 border-2 border-emerald-500 border-t-transparent rounded-full animate-spin" />
              </div>
            ) : recentActivity.length === 0 ? (
              <div className="text-center py-8">
                <Bot className="h-8 w-8 text-muted-foreground mx-auto mb-2" />
                <p className="text-sm text-muted-foreground">No recent activity</p>
                <p className="text-xs text-muted-foreground">
                  Activity will appear here once you start using PARWA.
                </p>
              </div>
            ) : (
              <div className="space-y-2 max-h-64 overflow-y-auto">
                {recentActivity.map((entry) => (
                  <div key={entry.id} className="flex items-center justify-between p-3 rounded-lg bg-muted/50">
                    <div>
                      <p className="text-sm font-medium">{entry.action}</p>
                      <p className="text-xs text-muted-foreground">
                        {entry.created_at ? new Date(entry.created_at).toLocaleDateString() : "Unknown date"}
                      </p>
                    </div>
                    <Badge
                      variant={
                        entry.severity === "critical"
                          ? "destructive"
                          : entry.severity === "warning"
                          ? "secondary"
                          : "outline"
                      }
                      className="text-xs"
                    >
                      {entry.severity}
                    </Badge>
                  </div>
                ))}
              </div>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
