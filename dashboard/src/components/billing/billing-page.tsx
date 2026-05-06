'use client';

import { useEffect, useState } from 'react';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import {
  fetchSubscription, fetchUsageRecords, fetchInvoices, fetchPaymentMethods, fetchTokenBudget,
} from '@/lib/api';
import type { Subscription, UsageRecord, Invoice, PaymentMethod, TokenBudget } from '@/lib/types';
import { Skeleton } from '@/components/ui/skeleton';
import { useAppStore } from '@/lib/store';
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend,
} from 'recharts';
import {
  CreditCard, Download, Plus, CheckCircle, AlertTriangle, Calendar,
} from 'lucide-react';
import { Progress } from '@/components/ui/progress';

function SubscriptionPanel() {
  const [sub, setSub] = useState<Subscription | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchSubscription().then(d => { setSub(d); setLoading(false); });
  }, []);

  if (loading || !sub) return <Skeleton className="h-48 w-full" />;

  const statusColor = sub.status === 'active' ? 'bg-emerald-100 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-400' :
    sub.status === 'past_due' ? 'bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400' :
    'bg-gray-100 text-gray-700 dark:bg-gray-800 dark:text-gray-400';

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between">
          <div>
            <CardTitle className="text-base">Subscription</CardTitle>
            <CardDescription>Current plan and billing details</CardDescription>
          </div>
          <Badge className={`border-0 ${statusColor}`}>{sub.status}</Badge>
        </div>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="flex items-center justify-between p-4 rounded-lg bg-gradient-to-r from-emerald-50 to-amber-50 dark:from-emerald-950/20 dark:to-amber-950/20">
          <div>
            <p className="text-2xl font-bold">{sub.planName}</p>
            <p className="text-sm text-muted-foreground">via Paddle</p>
          </div>
          <div className="text-right">
            <p className="text-2xl font-bold">${sub.amount}</p>
            <p className="text-sm text-muted-foreground">/month</p>
          </div>
        </div>
        <div className="grid grid-cols-2 gap-4">
          <div>
            <p className="text-xs text-muted-foreground">Current Period</p>
            <p className="text-sm font-medium">{new Date(sub.currentPeriodStart).toLocaleDateString()} — {new Date(sub.currentPeriodEnd).toLocaleDateString()}</p>
          </div>
          <div>
            <p className="text-xs text-muted-foreground">Next Billing</p>
            <p className="text-sm font-medium flex items-center gap-1">
              <Calendar className="h-3 w-3" /> {new Date(sub.nextBillingDate).toLocaleDateString()}
            </p>
          </div>
        </div>
        <Button variant="outline" className="w-full">Manage Subscription</Button>
      </CardContent>
    </Card>
  );
}

function UsageRecordsPanel() {
  const [records, setRecords] = useState<UsageRecord[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchUsageRecords().then(d => { setRecords(d); setLoading(false); });
  }, []);

  if (loading) return <Skeleton className="h-64 w-full" />;

  // Aggregate by date
  const dailyData = records.reduce<Record<string, { date: string; mini_parwa: number; parwa: number; parwa_high: number }>>((acc, r) => {
    if (!acc[r.date]) acc[r.date] = { date: r.date, mini_parwa: 0, parwa: 0, parwa_high: 0 };
    acc[r.date][r.variant] += r.cost;
    return acc;
  }, {});

  const chartData = Object.values(dailyData).slice(-14);

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">Usage & Cost</CardTitle>
        <CardDescription>Daily token usage cost by variant</CardDescription>
      </CardHeader>
      <CardContent>
        <div className="h-64">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={chartData} margin={{ top: 5, right: 10, left: -10, bottom: 5 }}>
              <CartesianGrid strokeDasharray="3 3" className="stroke-border" />
              <XAxis dataKey="date" tick={{ fontSize: 10 }} tickFormatter={v => new Date(v).toLocaleDateString('en-US', { month: 'short', day: 'numeric' })} />
              <YAxis tick={{ fontSize: 11 }} tickFormatter={v => `$${v}`} />
              <Tooltip contentStyle={{ backgroundColor: 'hsl(var(--card))', border: '1px solid hsl(var(--border))', borderRadius: '8px', fontSize: '12px' }} formatter={(v: number) => [`$${v.toFixed(2)}`]} />
              <Legend wrapperStyle={{ fontSize: '11px' }} />
              <Bar dataKey="mini_parwa" name="Starter" fill="#10b981" stackId="a" />
              <Bar dataKey="parwa" name="Growth" fill="#f59e0b" stackId="a" />
              <Bar dataKey="parwa_high" name="High" fill="#ef4444" stackId="a" radius={[4, 4, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </CardContent>
    </Card>
  );
}

function InvoicesPanel() {
  const [invoices, setInvoices] = useState<Invoice[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchInvoices().then(d => { setInvoices(d); setLoading(false); });
  }, []);

  if (loading) return <Skeleton className="h-64 w-full" />;

  return (
    <Card>
      <CardHeader><CardTitle className="text-base">Invoices</CardTitle></CardHeader>
      <CardContent>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-border">
                <th className="text-left font-medium text-muted-foreground pb-3">Invoice</th>
                <th className="text-left font-medium text-muted-foreground pb-3">Date</th>
                <th className="text-right font-medium text-muted-foreground pb-3">Amount</th>
                <th className="text-left font-medium text-muted-foreground pb-3">Status</th>
                <th className="text-right font-medium text-muted-foreground pb-3"></th>
              </tr>
            </thead>
            <tbody>
              {invoices.map(inv => (
                <tr key={inv.id} className="border-b border-border/50 hover:bg-muted/50">
                  <td className="py-3 font-mono text-xs">{inv.number}</td>
                  <td className="py-3 text-xs">{new Date(inv.date).toLocaleDateString()}</td>
                  <td className="py-3 text-right font-medium">${inv.amount.toFixed(2)}</td>
                  <td className="py-3">
                    <Badge variant="outline" className={`text-[10px] px-1.5 py-0 border-0 ${
                      inv.status === 'paid' ? 'bg-emerald-100 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-400' : 'bg-gray-100 text-gray-600 dark:bg-gray-800 dark:text-gray-400'
                    }`}>{inv.status}</Badge>
                  </td>
                  <td className="py-3 text-right">
                    <Button variant="ghost" size="sm"><Download className="h-3 w-3" /></Button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </CardContent>
    </Card>
  );
}

function PaymentMethodsPanel() {
  const [methods, setMethods] = useState<PaymentMethod[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchPaymentMethods().then(d => { setMethods(d); setLoading(false); });
  }, []);

  if (loading) return <Skeleton className="h-48 w-full" />;

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between">
          <CardTitle className="text-base">Payment Methods</CardTitle>
          <Button variant="outline" size="sm"><Plus className="h-3 w-3 mr-1" /> Add</Button>
        </div>
      </CardHeader>
      <CardContent className="space-y-3">
        {methods.map(method => (
          <div key={method.id} className="flex items-center justify-between p-3 rounded-lg border border-border">
            <div className="flex items-center gap-3">
              <CreditCard className="h-8 w-8 text-muted-foreground" />
              <div>
                <p className="text-sm font-medium">
                  {method.brand} •••• {method.last4}
                  {method.isDefault && <Badge className="ml-2 text-[10px] bg-emerald-100 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-400 border-0">Default</Badge>}
                </p>
                {method.expiryMonth && (
                  <p className="text-xs text-muted-foreground">Expires {method.expiryMonth}/{method.expiryYear}</p>
                )}
              </div>
            </div>
            <Button variant="ghost" size="sm" className="text-xs">Edit</Button>
          </div>
        ))}
      </CardContent>
    </Card>
  );
}

function BudgetManagementPanel() {
  const [budget, setBudget] = useState<TokenBudget | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchTokenBudget().then(d => { setBudget(d); setLoading(false); });
  }, []);

  if (loading || !budget) return <Skeleton className="h-64 w-full" />;

  const dailyPct = (budget.daily.used / budget.daily.limit) * 100;
  const monthlyPct = (budget.monthly.used / budget.monthly.limit) * 100;

  return (
    <Card>
      <CardHeader><CardTitle className="text-base">Budget Management</CardTitle></CardHeader>
      <CardContent className="space-y-6">
        <div className="space-y-2">
          <div className="flex items-center justify-between">
            <span className="text-sm font-medium">Daily Budget</span>
            <span className="text-sm">{(budget.daily.used / 1000000).toFixed(1)}M / {(budget.daily.limit / 1000000).toFixed(1)}M tokens</span>
          </div>
          <Progress value={dailyPct} className="h-3" />
          <p className="text-xs text-muted-foreground">{dailyPct.toFixed(1)}% used</p>
        </div>
        <div className="space-y-2">
          <div className="flex items-center justify-between">
            <span className="text-sm font-medium">Monthly Budget</span>
            <span className="text-sm">{(budget.monthly.used / 1000000).toFixed(1)}M / {(budget.monthly.limit / 1000000).toFixed(0)}M tokens</span>
          </div>
          <Progress value={monthlyPct} className="h-3" />
          <p className="text-xs text-muted-foreground">{monthlyPct.toFixed(1)}% used</p>
        </div>
        {budget.overageCount > 0 && (
          <div className="flex items-center gap-2 p-3 rounded-lg bg-amber-50 dark:bg-amber-950/30 text-amber-700 dark:text-amber-400">
            <AlertTriangle className="h-4 w-4" />
            <span className="text-xs">{budget.overageCount} overage event(s) recorded</span>
          </div>
        )}
      </CardContent>
    </Card>
  );
}

export function BillingPage() {
  const { billingTab, setBillingTab } = useAppStore();

  return (
    <Tabs value={billingTab} onValueChange={setBillingTab}>
      <TabsList>
        <TabsTrigger value="subscription">Subscription</TabsTrigger>
        <TabsTrigger value="usage">Usage</TabsTrigger>
        <TabsTrigger value="invoices">Invoices</TabsTrigger>
        <TabsTrigger value="budget">Budget</TabsTrigger>
      </TabsList>
      <TabsContent value="subscription" className="mt-6 space-y-6">
        <SubscriptionPanel />
        <PaymentMethodsPanel />
      </TabsContent>
      <TabsContent value="usage" className="mt-6">
        <UsageRecordsPanel />
      </TabsContent>
      <TabsContent value="invoices" className="mt-6">
        <InvoicesPanel />
      </TabsContent>
      <TabsContent value="budget" className="mt-6">
        <BudgetManagementPanel />
      </TabsContent>
    </Tabs>
  );
}
