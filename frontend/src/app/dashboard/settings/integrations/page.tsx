"use client";

/**
 * PARWA Integrations Settings Page
 *
 * Manage connected integrations with external services.
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
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
  DialogDescription,
} from "@/components/ui/dialog";
import { cn } from "@/utils/utils";

/**
 * Integration status.
 */
type IntegrationStatus = "connected" | "disconnected" | "pending" | "error";

/**
 * Integration data.
 */
interface Integration {
  id: string;
  name: string;
  description: string;
  category: string;
  icon: string;
  status: IntegrationStatus;
  lastSync?: string;
  features: string[];
}

/**
 * Integrations response from API.
 */
interface IntegrationsResponse {
  integrations: Integration[];
}

/**
 * Status badge colors.
 */
const statusColors: Record<IntegrationStatus, "default" | "secondary" | "destructive" | "outline"> = {
  connected: "default",
  disconnected: "outline",
  pending: "secondary",
  error: "destructive",
};

/**
 * Format relative time.
 */
function formatRelativeTime(dateString: string): string {
  const date = new Date(dateString);
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffMins = Math.floor(diffMs / 60000);
  const diffHours = Math.floor(diffMs / 3600000);
  const diffDays = Math.floor(diffMs / 86400000);

  if (diffMins < 1) return "Just now";
  if (diffMins < 60) return `${diffMins}m ago`;
  if (diffHours < 24) return `${diffHours}h ago`;
  if (diffDays < 7) return `${diffDays}d ago`;

  return date.toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
  });
}

/**
 * Integrations settings page component.
 */
export default function IntegrationsSettingsPage() {
  const { addToast } = useToasts();

  // State
  const [integrations, setIntegrations] = useState<Integration[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [selectedIntegration, setSelectedIntegration] = useState<Integration | null>(null);
  const [showConnectModal, setShowConnectModal] = useState(false);
  const [showDisconnectModal, setShowDisconnectModal] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [configForm, setConfigForm] = useState<Record<string, string>>({});

  /**
   * Fetch integrations on mount.
   */
  useEffect(() => {
    const fetchIntegrations = async () => {
      setIsLoading(true);

      try {
        const response = await apiClient.get<IntegrationsResponse>("/integrations");
        setIntegrations(response.data.integrations);
      } catch (error) {
        // Set demo data for development
        setIntegrations([
          {
            id: "shopify",
            name: "Shopify",
            description: "Sync orders, customers, and products from your Shopify store",
            category: "E-commerce",
            icon: "🛒",
            status: "connected",
            lastSync: new Date(Date.now() - 3600000).toISOString(),
            features: ["Order sync", "Customer data", "Product catalog", "Refunds"],
          },
          {
            id: "zendesk",
            name: "Zendesk",
            description: "Import tickets and sync support conversations",
            category: "Support",
            icon: "🎫",
            status: "connected",
            lastSync: new Date(Date.now() - 7200000).toISOString(),
            features: ["Ticket import", "Agent sync", "Knowledge base"],
          },
          {
            id: "twilio",
            name: "Twilio",
            description: "Send and receive SMS and voice calls",
            category: "Communication",
            icon: "📞",
            status: "disconnected",
            features: ["SMS", "Voice calls", "WhatsApp"],
          },
          {
            id: "stripe",
            name: "Stripe",
            description: "Process payments and handle refunds",
            category: "Payments",
            icon: "💳",
            status: "connected",
            lastSync: new Date(Date.now() - 1800000).toISOString(),
            features: ["Payment processing", "Refunds", "Subscriptions"],
          },
          {
            id: "slack",
            name: "Slack",
            description: "Send notifications to Slack channels",
            category: "Communication",
            icon: "💬",
            status: "disconnected",
            features: ["Notifications", "Alerts", "Reports"],
          },
          {
            id: "github",
            name: "GitHub",
            description: "Connect repositories for issue tracking",
            category: "Development",
            icon: "🐙",
            status: "pending",
            features: ["Issue sync", "PR notifications", "Webhooks"],
          },
          {
            id: "email",
            name: "Email (Brevo)",
            description: "Send transactional and marketing emails",
            category: "Communication",
            icon: "📧",
            status: "connected",
            lastSync: new Date(Date.now() - 300000).toISOString(),
            features: ["Transactional email", "Templates", "Tracking"],
          },
          {
            id: "aftership",
            name: "AfterShip",
            description: "Track shipments and delivery status",
            category: "Logistics",
            icon: "📦",
            status: "disconnected",
            features: ["Shipment tracking", "Delivery updates", "Notifications"],
          },
        ]);
      } finally {
        setIsLoading(false);
      }
    };

    fetchIntegrations();
  }, []);

  /**
   * Handle connect integration.
   */
  const handleConnect = async (integration: Integration) => {
    setSelectedIntegration(integration);
    setConfigForm({});
    setShowConnectModal(true);
  };

  /**
   * Handle disconnect integration.
   */
  const handleDisconnect = async (integration: Integration) => {
    setSelectedIntegration(integration);
    setShowDisconnectModal(true);
  };

  /**
   * Submit connection.
   */
  const submitConnect = async () => {
    if (!selectedIntegration) return;

    setIsSubmitting(true);

    try {
      await apiClient.post(`/integrations/${selectedIntegration.id}/connect`, configForm);

      addToast({
        title: "Success",
        description: `${selectedIntegration.name} connected successfully`,
        variant: "success",
      });

      // Update status
      setIntegrations((prev) =>
        prev.map((i) =>
          i.id === selectedIntegration.id
            ? { ...i, status: "connected", lastSync: new Date().toISOString() }
            : i
        )
      );

      setShowConnectModal(false);
      setSelectedIntegration(null);
    } catch (error) {
      const message =
        error instanceof APIError ? error.message : "Failed to connect integration";
      addToast({
        title: "Error",
        description: message,
        variant: "error",
      });
    } finally {
      setIsSubmitting(false);
    }
  };

  /**
   * Submit disconnect.
   */
  const submitDisconnect = async () => {
    if (!selectedIntegration) return;

    setIsSubmitting(true);

    try {
      await apiClient.post(`/integrations/${selectedIntegration.id}/disconnect`);

      addToast({
        title: "Success",
        description: `${selectedIntegration.name} disconnected`,
        variant: "success",
      });

      // Update status
      setIntegrations((prev) =>
        prev.map((i) =>
          i.id === selectedIntegration.id
            ? { ...i, status: "disconnected", lastSync: undefined }
            : i
        )
      );

      setShowDisconnectModal(false);
      setSelectedIntegration(null);
    } catch (error) {
      const message =
        error instanceof APIError ? error.message : "Failed to disconnect integration";
      addToast({
        title: "Error",
        description: message,
        variant: "error",
      });
    } finally {
      setIsSubmitting(false);
    }
  };

  /**
   * Group integrations by category.
   */
  const groupedIntegrations = integrations.reduce((acc, integration) => {
    const category = integration.category;
    if (!acc[category]) {
      acc[category] = [];
    }
    acc[category].push(integration);
    return acc;
  }, {} as Record<string, Integration[]>);

  /**
   * Loading skeleton.
   */
  if (isLoading) {
    return (
      <div className="space-y-6">
        <div className="h-8 w-48 bg-muted animate-pulse rounded" />
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {[...Array(6)].map((_, i) => (
            <div key={i} className="h-48 bg-muted animate-pulse rounded-xl" />
          ))}
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Page Header */}
      <div>
        <h1 className="text-2xl font-bold">Integrations</h1>
        <p className="text-muted-foreground">
          Connect PARWA with your favorite tools and services
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
          {/* Connected Overview */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <Card>
              <CardContent className="pt-6">
                <div className="text-2xl font-bold text-green-600">
                  {integrations.filter((i) => i.status === "connected").length}
                </div>
                <p className="text-sm text-muted-foreground">Connected</p>
              </CardContent>
            </Card>
            <Card>
              <CardContent className="pt-6">
                <div className="text-2xl font-bold text-yellow-600">
                  {integrations.filter((i) => i.status === "pending").length}
                </div>
                <p className="text-sm text-muted-foreground">Pending Setup</p>
              </CardContent>
            </Card>
            <Card>
              <CardContent className="pt-6">
                <div className="text-2xl font-bold text-muted-foreground">
                  {integrations.filter((i) => i.status === "disconnected").length}
                </div>
                <p className="text-sm text-muted-foreground">Available</p>
              </CardContent>
            </Card>
          </div>

          {/* Integrations by Category */}
          {Object.entries(groupedIntegrations).map(([category, items]) => (
            <div key={category}>
              <h2 className="text-lg font-semibold mb-4">{category}</h2>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {items.map((integration) => (
                  <Card key={integration.id} className="hover:shadow-md transition-shadow">
                    <CardContent className="pt-6">
                      <div className="flex items-start gap-4">
                        {/* Icon */}
                        <div className="h-12 w-12 rounded-lg bg-muted flex items-center justify-center text-2xl">
                          {integration.icon}
                        </div>

                        {/* Content */}
                        <div className="flex-1 min-w-0">
                          <div className="flex items-center gap-2 mb-1">
                            <h3 className="font-semibold">{integration.name}</h3>
                            <Badge variant={statusColors[integration.status]}>
                              {integration.status}
                            </Badge>
                          </div>
                          <p className="text-sm text-muted-foreground mb-3">
                            {integration.description}
                          </p>

                          {/* Features */}
                          <div className="flex flex-wrap gap-1 mb-3">
                            {integration.features.slice(0, 3).map((feature) => (
                              <span
                                key={feature}
                                className="text-xs px-2 py-0.5 bg-muted rounded-full"
                              >
                                {feature}
                              </span>
                            ))}
                          </div>

                          {/* Last Sync */}
                          {integration.lastSync && (
                            <p className="text-xs text-muted-foreground mb-3">
                              Last synced: {formatRelativeTime(integration.lastSync)}
                            </p>
                          )}

                          {/* Actions */}
                          <div className="flex gap-2">
                            {integration.status === "connected" ? (
                              <>
                                <Button
                                  variant="outline"
                                  size="sm"
                                  onClick={() => handleDisconnect(integration)}
                                >
                                  Disconnect
                                </Button>
                                <Button variant="ghost" size="sm">
                                  Configure
                                </Button>
                              </>
                            ) : integration.status === "pending" ? (
                              <Button size="sm" onClick={() => handleConnect(integration)}>
                                Complete Setup
                              </Button>
                            ) : (
                              <Button size="sm" onClick={() => handleConnect(integration)}>
                                Connect
                              </Button>
                            )}
                          </div>
                        </div>
                      </div>
                    </CardContent>
                  </Card>
                ))}
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Connect Modal */}
      <Dialog open={showConnectModal} onOpenChange={setShowConnectModal}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Connect {selectedIntegration?.name}</DialogTitle>
            <DialogDescription>
              Enter your credentials to connect {selectedIntegration?.name}
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-4 py-4">
            <div>
              <label htmlFor="api-key" className="text-sm font-medium mb-1.5 block">
                API Key
              </label>
              <input
                id="api-key"
                type="password"
                value={configForm.apiKey || ""}
                onChange={(e) => setConfigForm({ ...configForm, apiKey: e.target.value })}
                placeholder="Enter your API key"
                className="w-full px-3 py-2 border rounded-md bg-background text-sm focus:outline-none focus:ring-2 focus:ring-primary"
              />
            </div>
            <div>
              <label htmlFor="api-secret" className="text-sm font-medium mb-1.5 block">
                API Secret (optional)
              </label>
              <input
                id="api-secret"
                type="password"
                value={configForm.apiSecret || ""}
                onChange={(e) => setConfigForm({ ...configForm, apiSecret: e.target.value })}
                placeholder="Enter your API secret"
                className="w-full px-3 py-2 border rounded-md bg-background text-sm focus:outline-none focus:ring-2 focus:ring-primary"
              />
            </div>
          </div>

          <DialogFooter>
            <Button variant="outline" onClick={() => setShowConnectModal(false)}>
              Cancel
            </Button>
            <Button onClick={submitConnect} disabled={isSubmitting}>
              {isSubmitting ? "Connecting..." : "Connect"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Disconnect Modal */}
      <Dialog open={showDisconnectModal} onOpenChange={setShowDisconnectModal}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Disconnect {selectedIntegration?.name}</DialogTitle>
            <DialogDescription>
              Are you sure you want to disconnect {selectedIntegration?.name}? This will stop
              all data synchronization.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button variant="outline" onClick={() => setShowDisconnectModal(false)}>
              Cancel
            </Button>
            <Button
              variant="destructive"
              onClick={submitDisconnect}
              disabled={isSubmitting}
            >
              {isSubmitting ? "Disconnecting..." : "Disconnect"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
