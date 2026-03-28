'use client';

import { ReactElement } from 'react';
import Link from 'next/link';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import {
  Shield,
  Users,
  CreditCard,
  Settings,
  FileText,
  Key,
  Lock,
  Activity,
  ArrowRight
} from 'lucide-react';

/**
 * Enterprise Dashboard Page
 * 
 * Main dashboard for enterprise administrators with overview
 * of SSO, billing, security, and team management.
 */

interface QuickAction {
  title: string;
  description: string;
  icon: ReactElement;
  href: string;
  badge?: string;
}

const quickActions: QuickAction[] = [
  {
    title: 'SSO Configuration',
    description: 'Configure Single Sign-On with your identity provider',
    icon: <Key className="h-5 w-5" />,
    href: '/dashboard/enterprise/sso',
    badge: 'Setup Required'
  },
  {
    title: 'Team Management',
    description: 'Manage users, roles, and permissions',
    icon: <Users className="h-5 w-5" />,
    href: '/dashboard/settings/team'
  },
  {
    title: 'Enterprise Billing',
    description: 'View contract details and invoices',
    icon: <CreditCard className="h-5 w-5" />,
    href: '/dashboard/enterprise/billing'
  },
  {
    title: 'Security Settings',
    description: 'IP allowlisting, API keys, and audit logs',
    icon: <Shield className="h-5 w-5" />,
    href: '/dashboard/settings/security'
  }
];

interface StatCard {
  title: string;
  value: string | number;
  description: string;
  trend?: {
    value: number;
    positive: boolean;
  };
}

const stats: StatCard[] = [
  {
    title: 'Active Users',
    value: 45,
    description: 'Users with SSO access',
    trend: { value: 12, positive: true }
  },
  {
    title: 'API Calls (MTD)',
    value: '125,432',
    description: 'This month',
    trend: { value: 8, positive: true }
  },
  {
    title: 'Contract Seats',
    value: '50',
    description: '5 remaining'
  },
  {
    title: 'SLA Uptime',
    value: '99.97%',
    description: 'Current month',
    trend: { value: 0.02, positive: true }
  }
];

export default function EnterpriseDashboardPage() {
  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Enterprise Dashboard</h1>
          <p className="text-muted-foreground">
            Manage your enterprise account, SSO, and security settings
          </p>
        </div>
        <Badge variant="secondary" className="text-sm">
          Enterprise Plan
        </Badge>
      </div>

      {/* Stats Grid */}
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
        {stats.map((stat) => (
          <Card key={stat.title}>
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium">{stat.title}</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">{stat.value}</div>
              <p className="text-xs text-muted-foreground">
                {stat.description}
                {stat.trend && (
                  <span className={stat.trend.positive ? 'text-green-600 ml-1' : 'text-red-600 ml-1'}>
                    {stat.trend.positive ? '+' : '-'}{stat.trend.value}%
                  </span>
                )}
              </p>
            </CardContent>
          </Card>
        ))}
      </div>

      {/* Quick Actions */}
      <div className="grid gap-4 md:grid-cols-2">
        {quickActions.map((action) => (
          <Link key={action.title} href={action.href}>
            <Card className="hover:bg-accent/50 transition-colors cursor-pointer">
              <CardHeader>
                <div className="flex items-center justify-between">
                  <div className="flex items-center space-x-3">
                    <div className="rounded-lg bg-primary/10 p-2">
                      {action.icon}
                    </div>
                    <div>
                      <CardTitle className="text-lg">{action.title}</CardTitle>
                      <CardDescription>{action.description}</CardDescription>
                    </div>
                  </div>
                  <ArrowRight className="h-5 w-5 text-muted-foreground" />
                </div>
              </CardHeader>
              {action.badge && (
                <CardContent className="pt-0">
                  <Badge variant="outline" className="bg-amber-50 text-amber-700 border-amber-200">
                    {action.badge}
                  </Badge>
                </CardContent>
              )}
            </Card>
          </Link>
        ))}
      </div>

      {/* Security Overview */}
      <Card>
        <CardHeader>
          <div className="flex items-center space-x-2">
            <Lock className="h-5 w-5" />
            <CardTitle>Security Overview</CardTitle>
          </div>
          <CardDescription>
            Your enterprise security configuration status
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <div className="flex items-center space-x-3">
                <Shield className="h-4 w-4 text-green-500" />
                <span className="text-sm">SSO Enabled</span>
              </div>
              <Badge variant="outline" className="bg-green-50 text-green-700">
                Active
              </Badge>
            </div>
            <div className="flex items-center justify-between">
              <div className="flex items-center space-x-3">
                <Lock className="h-4 w-4 text-green-500" />
                <span className="text-sm">MFA Required for Admins</span>
              </div>
              <Badge variant="outline" className="bg-green-50 text-green-700">
                Enforced
              </Badge>
            </div>
            <div className="flex items-center justify-between">
              <div className="flex items-center space-x-3">
                <Activity className="h-4 w-4 text-green-500" />
                <span className="text-sm">IP Allowlist</span>
              </div>
              <Badge variant="outline" className="bg-amber-50 text-amber-700">
                Not Configured
              </Badge>
            </div>
            <div className="flex items-center justify-between">
              <div className="flex items-center space-x-3">
                <Key className="h-4 w-4 text-green-500" />
                <span className="text-sm">API Key Access</span>
              </div>
              <Badge variant="outline" className="bg-green-50 text-green-700">
                3 Active Keys
              </Badge>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Recent Activity */}
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <CardTitle>Recent Activity</CardTitle>
            <Button variant="ghost" size="sm" asChild>
              <Link href="/dashboard/settings/audit-logs">View All</Link>
            </Button>
          </div>
        </CardHeader>
        <CardContent>
          <div className="space-y-4">
            {[
              { action: 'User login via SSO', user: 'john.doe@company.com', time: '2 minutes ago' },
              { action: 'API key created', user: 'admin@company.com', time: '1 hour ago' },
              { action: 'SSO configuration updated', user: 'admin@company.com', time: '2 days ago' },
              { action: 'Contract renewed', user: 'billing@company.com', time: '1 week ago' }
            ].map((activity, i) => (
              <div key={i} className="flex items-center justify-between text-sm">
                <div>
                  <span className="font-medium">{activity.action}</span>
                  <span className="text-muted-foreground"> by {activity.user}</span>
                </div>
                <span className="text-muted-foreground">{activity.time}</span>
              </div>
            ))}
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
