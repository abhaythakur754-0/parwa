"use client";

/**
 * PARWA Billing Settings Page
 *
 * Displays current plan, usage metrics, invoices, and payment methods.
 */

import { useState, useEffect } from "react";
import { apiClient, APIError } from "@/services/api/client";
import { useToasts } from "@/stores/uiStore";
import SettingsNav from "@/components/settings/SettingsNav";
import {
  Card,
  CardHeader,
  CardTitle,
  CardDescription,
  CardContent,
} from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
  Table,
  TableHeader,
  TableBody,
  TableRow,
  TableHead,
  TableCell,
} from "@/components/ui/table";

/**
 * Plan type.
 */
type PlanType = "mini" | "parwa" | "parwa_high";

/**
 * Plan details.
 */
interface PlanDetails {
  name: string;
  price: number;
  features: string[];
  limits: {
    tickets: number;
    agents: number;
    storage: number; // GB
  };
}

/**
 * Plan configurations.
 */
const plans: Record<PlanType, PlanDetails> = {
  mini: {
    name: "Mini PARWA",
    price: 49,
    features: [
      "Up to 500 tickets/month",
      "1 agent",
      "Basic FAQ handling",
      "Email support",
    ],
    limits: {
      tickets: 500,
      agents: 1,
      storage: 5,
    },
  },
  parwa: {
    name: "PARWA Junior",
    price: 149,
    features: [
      "Up to 2,000 tickets/month",
      "3 agents",
      "Advanced AI resolution",
      "Refund recommendations",
      "Priority support",
    ],
    limits: {
      tickets: 2000,
      agents: 3,
      storage: 20,
    },
  },
  parwa_high: {
    name: "PARWA High",
    price: 499,
    features: [
      "Unlimited tickets",
      "10 agents",
      "Full AI capabilities",
      "Video support",
      "Churn prediction",
      "Dedicated support",
    ],
    limits: {
      tickets: -1, // unlimited
      agents: 10,
      storage: 100,
    },
  },
};

/**
 * Usage data from API.
 */
interface UsageData {
  tickets: number;
  agents: number;
  storage: number;
}

/**
 * Invoice data.
 */
interface Invoice {
  id: string;
  date: string;
  amount: number;
  status: "paid" | "pending" | "failed";
  downloadUrl: string;
}

/**
 * Billing data from API.
 */
interface BillingData {
  currentPlan: PlanType;
  usage: UsageData;
  invoices: Invoice[];
  paymentMethod?: {
    brand: string;
    last4: string;
    expiryMonth: number;
    expiryYear: number;
  };
  billingEmail: string;
}

/**
 * Format currency.
 */
function formatCurrency(amount: number): string {
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
  }).format(amount);
}

/**
 * Format date.
 */
function formatDate(dateString: string): string {
  return new Date(dateString).toLocaleDateString("en-US", {
    year: "numeric",
    month: "short",
    day: "numeric",
  });
}

/**
 * Billing settings page component.
 */
export default function BillingSettingsPage() {
  const { addToast } = useToasts();

  // State
  const [billingData, setBillingData] = useState<BillingData | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [showUpgradeModal, setShowUpgradeModal] = useState(false);

  /**
   * Fetch billing data on mount.
   */
  useEffect(() => {
    const fetchBillingData = async () => {
      setIsLoading(true);

      try {
        const response = await apiClient.get<BillingData>("/billing");
        setBillingData(response.data);
      } catch (error) {
        // Set demo data for development
        setBillingData({
          currentPlan: "parwa",
          usage: {
            tickets: 1247,
            agents: 2,
            storage: 8.5,
          },
          invoices: [
            {
              id: "INV-001",
              date: "2026-03-01",
              amount: 149,
              status: "paid",
              downloadUrl: "/invoices/INV-001.pdf",
            },
            {
              id: "INV-002",
              date: "2026-02-01",
              amount: 149,
              status: "paid",
              downloadUrl: "/invoices/INV-002.pdf",
            },
            {
              id: "INV-003",
              date: "2026-01-01",
              amount: 149,
              status: "paid",
              downloadUrl: "/invoices/INV-003.pdf",
            },
          ],
          paymentMethod: {
            brand: "Visa",
            last4: "4242",
            expiryMonth: 12,
            expiryYear: 2027,
          },
          billingEmail: "billing@company.com",
        });
      } finally {
        setIsLoading(false);
      }
    };

    fetchBillingData();
  }, [addToast]);

  /**
   * Handle plan upgrade.
   */
  const handleUpgrade = (plan: PlanType) => {
    addToast({
      title: "Coming Soon",
      description: `Upgrade to ${plans[plan].name} will be available soon`,
      variant: "warning",
    });
    setShowUpgradeModal(false);
  };

  /**
   * Loading skeleton.
   */
  if (isLoading) {
    return (
      <div className="space-y-6">
        <div className="h-8 w-48 bg-muted animate-pulse rounded" />
        <div className="h-64 bg-muted animate-pulse rounded-xl" />
        <div className="h-48 bg-muted animate-pulse rounded-xl" />
      </div>
    );
  }

  const currentPlan = billingData ? plans[billingData.currentPlan] : plans.parwa;
  const usage = billingData?.usage || { tickets: 0, agents: 0, storage: 0 };

  return (
    <div className="space-y-6">
      {/* Page Header */}
      <div>
        <h1 className="text-2xl font-bold">Billing</h1>
        <p className="text-muted-foreground">
          Manage your subscription, usage, and invoices
        </p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-4 gap-6">
        {/* Sidebar Navigation */}
        <div className="lg:col-span-1">
          <Card className="sticky top-6">
            <CardContent className="pt-6">
              <SettingsNav />
            </CardContent>
          </Card>
        </div>

        {/* Main Content */}
        <div className="lg:col-span-3 space-y-6">
          {/* Current Plan */}
          <Card>
            <CardHeader>
              <div className="flex items-center justify-between">
                <div>
                  <CardTitle>Current Plan</CardTitle>
                  <CardDescription>
                    Your current subscription and its features
                  </CardDescription>
                </div>
                <Badge variant="default">{currentPlan.name}</Badge>
              </div>
            </CardHeader>
            <CardContent>
              <div className="flex items-baseline gap-2 mb-4">
                <span className="text-4xl font-bold">{formatCurrency(currentPlan.price)}</span>
                <span className="text-muted-foreground">/month</span>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-6">
                <div>
                  <h4 className="font-medium mb-2">Features included:</h4>
                  <ul className="space-y-2">
                    {currentPlan.features.map((feature, index) => (
                      <li key={index} className="flex items-center gap-2 text-sm">
                        <svg className="h-4 w-4 text-green-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                        </svg>
                        {feature}
                      </li>
                    ))}
                  </ul>
                </div>

                <div>
                  <h4 className="font-medium mb-2">Plan limits:</h4>
                  <ul className="space-y-2 text-sm">
                    <li className="flex items-center gap-2">
                      <svg className="h-4 w-4 text-muted-foreground" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2" />
                      </svg>
                      Tickets: {currentPlan.limits.tickets === -1 ? "Unlimited" : `${currentPlan.limits.tickets.toLocaleString()}/mo`}
                    </li>
                    <li className="flex items-center gap-2">
                      <svg className="h-4 w-4 text-muted-foreground" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0z" />
                      </svg>
                      Agents: {currentPlan.limits.agents}
                    </li>
                    <li className="flex items-center gap-2">
                      <svg className="h-4 w-4 text-muted-foreground" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 7v10c0 2.21 3.582 4 8 4s8-1.79 8-4V7M4 7c0 2.21 3.582 4 8 4s8-1.79 8-4M4 7c0-2.21 3.582-4 8-4s8 1.79 8 4" />
                      </svg>
                      Storage: {currentPlan.limits.storage} GB
                    </li>
                  </ul>
                </div>
              </div>

              <div className="flex gap-2">
                <Button variant="outline" onClick={() => setShowUpgradeModal(true)}>
                  Upgrade Plan
                </Button>
                {billingData?.currentPlan !== "mini" && (
                  <Button variant="ghost">
                    Downgrade
                  </Button>
                )}
              </div>
            </CardContent>
          </Card>

          {/* Usage */}
          <Card>
            <CardHeader>
              <CardTitle>Current Usage</CardTitle>
              <CardDescription>
                Your usage for this billing period
              </CardDescription>
            </CardHeader>
            <CardContent>
              <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                {/* Tickets Usage */}
                <div>
                  <div className="flex items-center justify-between mb-2">
                    <span className="text-sm font-medium">Tickets</span>
                    <span className="text-sm text-muted-foreground">
                      {usage.tickets.toLocaleString()} / {currentPlan.limits.tickets === -1 ? "∞" : currentPlan.limits.tickets.toLocaleString()}
                    </span>
                  </div>
                  <div className="h-2 bg-muted rounded-full overflow-hidden">
                    <div
                      className="h-full bg-primary rounded-full transition-all"
                      style={{
                        width: currentPlan.limits.tickets === -1
                          ? "10%"
                          : `${Math.min((usage.tickets / currentPlan.limits.tickets) * 100, 100)}%`,
                      }}
                    />
                  </div>
                </div>

                {/* Agents Usage */}
                <div>
                  <div className="flex items-center justify-between mb-2">
                    <span className="text-sm font-medium">Agents</span>
                    <span className="text-sm text-muted-foreground">
                      {usage.agents} / {currentPlan.limits.agents}
                    </span>
                  </div>
                  <div className="h-2 bg-muted rounded-full overflow-hidden">
                    <div
                      className="h-full bg-primary rounded-full transition-all"
                      style={{ width: `${Math.min((usage.agents / currentPlan.limits.agents) * 100, 100)}%` }}
                    />
                  </div>
                </div>

                {/* Storage Usage */}
                <div>
                  <div className="flex items-center justify-between mb-2">
                    <span className="text-sm font-medium">Storage</span>
                    <span className="text-sm text-muted-foreground">
                      {usage.storage.toFixed(1)} GB / {currentPlan.limits.storage} GB
                    </span>
                  </div>
                  <div className="h-2 bg-muted rounded-full overflow-hidden">
                    <div
                      className="h-full bg-primary rounded-full transition-all"
                      style={{ width: `${Math.min((usage.storage / currentPlan.limits.storage) * 100, 100)}%` }}
                    />
                  </div>
                </div>
              </div>
            </CardContent>
          </Card>

          {/* Payment Method */}
          <Card>
            <CardHeader>
              <CardTitle>Payment Method</CardTitle>
              <CardDescription>
                Your payment method for subscription billing
              </CardDescription>
            </CardHeader>
            <CardContent>
              {billingData?.paymentMethod ? (
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-3">
                    <div className="h-12 w-12 rounded-md bg-muted flex items-center justify-center font-bold text-sm">
                      {billingData.paymentMethod.brand}
                    </div>
                    <div>
                      <p className="font-medium">
                        •••• •••• •••• {billingData.paymentMethod.last4}
                      </p>
                      <p className="text-sm text-muted-foreground">
                        Expires {billingData.paymentMethod.expiryMonth}/{billingData.paymentMethod.expiryYear}
                      </p>
                    </div>
                  </div>
                  <Button variant="outline">
                    Update
                  </Button>
                </div>
              ) : (
                <div className="text-center py-4">
                  <p className="text-muted-foreground mb-3">No payment method on file</p>
                  <Button>Add Payment Method</Button>
                </div>
              )}
            </CardContent>
          </Card>

          {/* Invoice History */}
          <Card>
            <CardHeader>
              <CardTitle>Invoice History</CardTitle>
              <CardDescription>
                Download your past invoices
              </CardDescription>
            </CardHeader>
            <CardContent>
              {billingData?.invoices && billingData.invoices.length > 0 ? (
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Invoice</TableHead>
                      <TableHead>Date</TableHead>
                      <TableHead>Amount</TableHead>
                      <TableHead>Status</TableHead>
                      <TableHead className="text-right">Action</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {billingData.invoices.map((invoice) => (
                      <TableRow key={invoice.id}>
                        <TableCell className="font-medium">{invoice.id}</TableCell>
                        <TableCell>{formatDate(invoice.date)}</TableCell>
                        <TableCell>{formatCurrency(invoice.amount)}</TableCell>
                        <TableCell>
                          <Badge
                            variant={
                              invoice.status === "paid"
                                ? "default"
                                : invoice.status === "pending"
                                ? "secondary"
                                : "destructive"
                            }
                          >
                            {invoice.status}
                          </Badge>
                        </TableCell>
                        <TableCell className="text-right">
                          <Button variant="ghost" size="sm" asChild>
                            <a href={invoice.downloadUrl} download>
                              Download
                            </a>
                          </Button>
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              ) : (
                <p className="text-muted-foreground text-center py-8">No invoices yet</p>
              )}
            </CardContent>
          </Card>

          {/* Billing Contact */}
          <Card>
            <CardHeader>
              <CardTitle>Billing Contact</CardTitle>
              <CardDescription>
                Where we send billing notifications
              </CardDescription>
            </CardHeader>
            <CardContent>
              <div className="flex items-center justify-between">
                <div>
                  <p className="font-medium">{billingData?.billingEmail || "No billing email set"}</p>
                  <p className="text-sm text-muted-foreground">Billing email</p>
                </div>
                <Button variant="outline">
                  Update
                </Button>
              </div>
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}
